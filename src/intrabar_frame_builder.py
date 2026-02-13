"""
Intrabar 1-second frame builder for L2 visualization.

Generates second-level features from raw MBP-10 data:
- Book features: LOCF (last observation carried forward)
- Trade features: per-second aggregation
- Quality metrics: coverage and update counts
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional, TYPE_CHECKING

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from .l2_data_manager import L2DataManager

# Schema version for intrabar frames
INTRABAR_SCHEMA_VERSION = "intrabar-1.0"


@dataclass
class IntrabarFrameBuilder:
    """Builds 1-second frames from raw MBP-10 data."""

    manager: "L2DataManager"

    # Column definitions
    BID_SIZE_COLS = [f"bid_sz_{i:02d}" for i in range(10)]
    ASK_SIZE_COLS = [f"ask_sz_{i:02d}" for i in range(10)]
    BID_PRICE_COLS = [f"bid_px_{i:02d}" for i in range(10)]
    ASK_PRICE_COLS = [f"ask_px_{i:02d}" for i in range(10)]

    @staticmethod
    def _to_utc_datetime(value: Any) -> datetime:
        """Convert value to UTC datetime."""
        if isinstance(value, datetime):
            dt = value
        else:
            dt = pd.to_datetime(value).to_pydatetime()
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    @staticmethod
    def _safe_div(num: float, den: float, default: float = 0.0) -> float:
        """Safe division with default for zero denominator."""
        return num / den if den != 0 else default

    @staticmethod
    def _infer_trade_sign(row: pd.Series) -> float:
        """Infer trade direction: +1 buy, -1 sell, 0 unknown.
        
        Priority:
        1. side field ('B'/'A')
        2. price vs BBO
        3. price vs mid
        """
        side = str(row.get("side", "")).upper()
        if side == "B":
            return 1.0
        if side == "A":
            return -1.0

        price = float(row.get("price", 0.0) or 0.0)
        ask = float(row.get("ask_px_00", 0.0) or 0.0)
        bid = float(row.get("bid_px_00", 0.0) or 0.0)

        if ask > 0 and price >= ask:
            return 1.0
        if bid > 0 and price <= bid:
            return -1.0
        if ask > 0 and bid > 0:
            mid = (ask + bid) / 2.0
            return 1.0 if price >= mid else -1.0
        return 0.0

    def _ensure_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Ensure all required columns exist."""
        for col in self.BID_SIZE_COLS + self.ASK_SIZE_COLS:
            if col not in df.columns:
                df[col] = 0.0
        for col in self.BID_PRICE_COLS + self.ASK_PRICE_COLS:
            if col not in df.columns:
                df[col] = np.nan
        return df

    def _build_book_features(
        self,
        df: pd.DataFrame,
        second_grid: pd.DatetimeIndex,
    ) -> pd.DataFrame:
        """Build book features using LOCF (last observation carried forward).
        
        For each second, use the last known book state.
        """
        # Filter non-trade events (book updates)
        if "action" in df.columns:
            book_events = df[df["action"].astype(str).str.upper() != "T"].copy()
        else:
            book_events = df.copy()

        if book_events.empty:
            # Return empty frame with correct columns
            return pd.DataFrame(
                index=second_grid,
                columns=[
                    "depth_bid_total", "depth_ask_total", "imbalance_sec",
                    "book_pressure_sec", "spread_bps", "top_bid_sz", "top_ask_sz",
                    "top_bid_px", "top_ask_px", "book_updates_sec", "has_book_coverage",
                ],
            )

        book_events = self._ensure_columns(book_events)

        # Floor to seconds
        book_events = book_events.copy()
        book_events["ts_sec"] = book_events.index.floor("1s")

        # Compute features per row (before aggregation)
        bid_totals = book_events[self.BID_SIZE_COLS].astype(float).clip(lower=0).sum(axis=1)
        ask_totals = book_events[self.ASK_SIZE_COLS].astype(float).clip(lower=0).sum(axis=1)
        
        book_events["depth_bid_total"] = bid_totals
        book_events["depth_ask_total"] = ask_totals
        
        total_depth = bid_totals + ask_totals
        book_events["imbalance_sec"] = np.where(
            total_depth > 0,
            (bid_totals - ask_totals) / total_depth,
            0.0
        )
        book_events["book_pressure_sec"] = book_events["imbalance_sec"]
        
        # Spread in basis points
        top_bid = book_events["bid_px_00"].astype(float)
        top_ask = book_events["ask_px_00"].astype(float)
        mid = (top_bid + top_ask) / 2.0
        book_events["spread_bps"] = np.where(
            mid > 0,
            (top_ask - top_bid) / mid * 10000,
            np.nan
        )
        
        book_events["top_bid_sz"] = book_events["bid_sz_00"].astype(float)
        book_events["top_ask_sz"] = book_events["ask_sz_00"].astype(float)
        book_events["top_bid_px"] = top_bid
        book_events["top_ask_px"] = top_ask

        # Group by second, take last observation
        feature_cols = [
            "depth_bid_total", "depth_ask_total", "imbalance_sec",
            "book_pressure_sec", "spread_bps", "top_bid_sz", "top_ask_sz",
            "top_bid_px", "top_ask_px",
        ]
        
        # Count updates per second
        update_counts = book_events.groupby("ts_sec").size().rename("book_updates_sec")
        
        # Last observation per second
        book_sec = book_events.groupby("ts_sec")[feature_cols].last()
        book_sec = book_sec.join(update_counts)

        # Reindex to grid with forward fill (LOCF)
        book_sec = book_sec.reindex(second_grid)
        
        # Track coverage before ffill
        book_sec["has_book_coverage"] = book_sec["depth_bid_total"].notna()
        
        # Forward fill for LOCF
        book_sec[feature_cols] = book_sec[feature_cols].ffill()
        
        # Fill update counts with 0 for seconds without updates
        book_sec["book_updates_sec"] = book_sec["book_updates_sec"].fillna(0).astype(int)

        return book_sec

    def _build_trade_features(
        self,
        df: pd.DataFrame,
        second_grid: pd.DatetimeIndex,
    ) -> pd.DataFrame:
        """Build trade features by aggregating per second."""
        # Filter for trades only
        if "action" in df.columns:
            trades = df[df["action"].astype(str).str.upper() == "T"].copy()
        else:
            trades = df.copy()

        if trades.empty:
            return pd.DataFrame(
                index=second_grid,
                columns=[
                    "buy_volume_sec", "sell_volume_sec", "delta_sec",
                    "trade_ticks_sec",
                ],
            ).fillna(0)

        trades = self._ensure_columns(trades)

        # Floor to seconds
        trades["ts_sec"] = trades.index.floor("1s")

        # Classify each trade
        def classify_row(row):
            size = max(0.0, float(row.get("size", 0.0) or 0.0))
            sign = self._infer_trade_sign(row)
            return pd.Series({
                "buy_volume": size if sign > 0 else 0.0,
                "sell_volume": size if sign < 0 else 0.0,
            })

        classified = trades.apply(classify_row, axis=1)
        trades["buy_volume"] = classified["buy_volume"]
        trades["sell_volume"] = classified["sell_volume"]

        # Aggregate per second
        trade_sec = trades.groupby("ts_sec").agg({
            "buy_volume": "sum",
            "sell_volume": "sum",
            "size": "count",  # trade ticks
        }).rename(columns={
            "buy_volume": "buy_volume_sec",
            "sell_volume": "sell_volume_sec", 
            "size": "trade_ticks_sec",
        })

        trade_sec["delta_sec"] = trade_sec["buy_volume_sec"] - trade_sec["sell_volume_sec"]

        # Reindex to grid (no ffill for trades, use 0)
        trade_sec = trade_sec.reindex(second_grid).fillna(0)
        trade_sec["trade_ticks_sec"] = trade_sec["trade_ticks_sec"].astype(int)

        return trade_sec

    def build_frames(
        self,
        ticker: str,
        start_dt_utc: datetime,
        end_dt_utc: datetime,
    ) -> pd.DataFrame:
        """Build 1-second frames for the given time range.
        
        Args:
            ticker: Stock ticker
            start_dt_utc: Start time (UTC)
            end_dt_utc: End time (UTC)
            
        Returns:
            DataFrame with 1-second features indexed by ts_sec (UTC)
        """
        # Load raw data
        start_date = start_dt_utc.strftime("%Y-%m-%d")
        end_date = end_dt_utc.strftime("%Y-%m-%d")
        
        loaded = self.manager.load_data(ticker, start_date, end_date)
        if loaded is None:
            return pd.DataFrame()

        df = loaded
        df = self.manager._normalize_datetime_index_utc(df)
        
        # Filter to time range
        mask = (df.index >= start_dt_utc) & (df.index <= end_dt_utc)
        df = df.loc[mask].copy()

        if df.empty:
            return pd.DataFrame()

        # Create 1-second grid
        second_grid = pd.date_range(
            start=start_dt_utc.replace(microsecond=0),
            end=end_dt_utc.replace(microsecond=0),
            freq="1s",
            tz=timezone.utc,
        )

        # Build features
        book_features = self._build_book_features(df, second_grid)
        trade_features = self._build_trade_features(df, second_grid)

        # Combine
        frames = book_features.join(trade_features, how="outer")

        # Compute cumulative delta (within the range)
        frames["cum_delta_sec"] = frames["delta_sec"].fillna(0).cumsum()

        # Add schema version
        frames["schema_version"] = INTRABAR_SCHEMA_VERSION

        # Compute coverage ratio
        total_seconds = len(second_grid)
        covered_seconds = frames["has_book_coverage"].sum()
        frames["coverage_ratio"] = covered_seconds / total_seconds if total_seconds > 0 else 0.0

        # Reset index to make ts_sec a column
        frames = frames.reset_index().rename(columns={"index": "ts_sec"})

        return frames

    def build_frames_for_minute(
        self,
        ticker: str,
        minute_start_utc: datetime,
    ) -> pd.DataFrame:
        """Build 1-second frames for a single minute bar.
        
        Convenience method for the bar-details API endpoint.
        """
        minute_end_utc = minute_start_utc.replace(second=59, microsecond=999999)
        return self.build_frames(ticker, minute_start_utc, minute_end_utc)
