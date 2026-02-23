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
from typing import Dict, Optional, TYPE_CHECKING

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

    def _ensure_polars_columns(self, lf: pl.LazyFrame) -> pl.LazyFrame:
        """Ensure all required columns exist in the LazyFrame."""
        schema = lf.collect_schema()
        new_cols = []
        for col in self.BID_SIZE_COLS + self.ASK_SIZE_COLS:
            if col not in schema:
                new_cols.append(pl.lit(0.0).alias(col))
        for col in self.BID_PRICE_COLS + self.ASK_PRICE_COLS:
            if col not in schema:
                new_cols.append(pl.lit(None).cast(pl.Float64).alias(col))
        if new_cols:
            lf = lf.with_columns(new_cols)
        return lf

    def _build_book_features(
        self,
        df: pd.DataFrame,
        second_grid: pd.DatetimeIndex,
    ) -> pd.DataFrame:
        """Build book features using LOCF (last observation carried forward) via Polars."""
        import polars as pl

        if df.empty:
            return pd.DataFrame(
                index=second_grid,
                columns=[
                    "depth_bid_total",
                    "depth_ask_total",
                    "imbalance_sec",
                    "book_pressure_sec",
                    "spread_bps",
                    "top_bid_sz",
                    "top_ask_sz",
                    "top_bid_px",
                    "top_ask_px",
                    "book_updates_sec",
                    "has_book_coverage",
                ],
            )
            
        pdf = pl.from_pandas(df.reset_index())
        pdf = pdf.lazy()
        
        # Ensure 'ts_event' is the time column (from df.index)
        if df.index.name and df.index.name in pdf.collect_schema():
            time_col = df.index.name
        else:
            time_col = "index"

        if "action" in pdf.collect_schema():
            books = pdf.filter(pl.col("action").cast(pl.Utf8).str.to_uppercase() != "T")
        else:
            books = pdf

        books = self._ensure_polars_columns(books)

        # Compute depth and top of book features
        books = books.with_columns([
            pl.sum_horizontal([pl.col(c).cast(pl.Float64).fill_null(0.0).clip(lower_bound=0.0) for c in self.BID_SIZE_COLS]).alias("depth_bid_total"),
            pl.sum_horizontal([pl.col(c).cast(pl.Float64).fill_null(0.0).clip(lower_bound=0.0) for c in self.ASK_SIZE_COLS]).alias("depth_ask_total"),
            pl.col("bid_px_00").cast(pl.Float64).alias("top_bid_px"),
            pl.col("ask_px_00").cast(pl.Float64).alias("top_ask_px"),
            pl.col("bid_sz_00").cast(pl.Float64).alias("top_bid_sz"),
            pl.col("ask_sz_00").cast(pl.Float64).alias("top_ask_sz"),
        ])

        # Compute imbalance and spread
        books = books.with_columns([
            pl.when((pl.col("depth_bid_total") + pl.col("depth_ask_total")) > 0)
              .then((pl.col("depth_bid_total") - pl.col("depth_ask_total")) / (pl.col("depth_bid_total") + pl.col("depth_ask_total")))
              .otherwise(0.0).alias("imbalance_sec"),
            pl.when((pl.col("top_bid_px") + pl.col("top_ask_px")) > 0)
              .then((pl.col("top_ask_px") - pl.col("top_bid_px")) / ((pl.col("top_bid_px") + pl.col("top_ask_px")) / 2.0) * 10000)
              .otherwise(None).alias("spread_bps")
        ])
        
        books = books.with_columns([
            pl.col("imbalance_sec").alias("book_pressure_sec")
        ])

        # Group by 1 second intervals and aggregate
        # Using group_by_dynamic to resample
        book_sec = books.sort(time_col).group_by_dynamic(
            time_col,
            every="1s"
        ).agg([
            pl.col("depth_bid_total").last(),
            pl.col("depth_ask_total").last(),
            pl.col("imbalance_sec").last(),
            pl.col("book_pressure_sec").last(),
            pl.col("spread_bps").last(),
            pl.col("top_bid_sz").last(),
            pl.col("top_ask_sz").last(),
            pl.col("top_bid_px").last(),
            pl.col("top_ask_px").last(),
            pl.len().alias("book_updates_sec") # count of rows
        ]).collect()

        # Convert back to pandas
        book_pd = book_sec.to_pandas()
        if book_pd.empty:
            book_pd = pd.DataFrame(index=second_grid)
        else:
            book_pd.set_index(time_col, inplace=True)
            book_pd.index = book_pd.index.tz_localize("UTC") if book_pd.index.tz is None else book_pd.index.tz_convert("UTC")

        book_pd["has_book_coverage"] = book_pd["depth_bid_total"].notna()

        # Reindex to full second grid and Forward fill
        book_pd = book_pd.reindex(second_grid)
        
        feature_cols = [
            "depth_bid_total", "depth_ask_total", "imbalance_sec", "book_pressure_sec",
            "spread_bps", "top_bid_sz", "top_ask_sz", "top_bid_px", "top_ask_px"
        ]
        book_pd[feature_cols] = book_pd[feature_cols].ffill()
        
        book_pd["book_updates_sec"] = book_pd["book_updates_sec"].fillna(0).astype(int)

        return book_pd

    def _build_trade_features(
        self,
        df: pd.DataFrame,
        second_grid: pd.DatetimeIndex,
    ) -> pd.DataFrame:
        """Build trade features by aggregating per second using Polars."""
        import polars as pl
        
        if df.empty:
            return pd.DataFrame(
                index=second_grid,
                columns=[
                    "buy_volume_sec",
                    "sell_volume_sec",
                    "delta_sec",
                    "trade_ticks_sec",
                ],
            ).fillna(0)
            
        pdf = pl.from_pandas(df.reset_index())
        pdf = pdf.lazy()
        
        # Ensure 'ts_event' is the time column (from df.index)
        if df.index.name and df.index.name in pdf.collect_schema():
            time_col = df.index.name
        else:
            time_col = "index"

        if "action" in pdf.collect_schema():
            trades = pdf.filter(pl.col("action").cast(pl.Utf8).str.to_uppercase() == "T")
        else:
            trades = pdf

        trades = self._ensure_polars_columns(trades)
        schema = trades.collect_schema()

        # Infer trade sign natively in polars
        # Need to handle missing optional side/price columns gracefully
        side_expr = pl.col("side").cast(pl.Utf8).str.to_uppercase() if "side" in schema else pl.lit("N")
        price_expr = pl.col("price").cast(pl.Float64).fill_null(0.0) if "price" in schema else pl.lit(0.0)
        ask_px_expr = pl.col("ask_px_00").cast(pl.Float64).fill_null(0.0) if "ask_px_00" in schema else pl.lit(0.0)
        bid_px_expr = pl.col("bid_px_00").cast(pl.Float64).fill_null(0.0) if "bid_px_00" in schema else pl.lit(0.0)

        trades = trades.with_columns([
            pl.when(side_expr == "B").then(1.0)
            .when(side_expr == "A").then(-1.0)
            .when((ask_px_expr > 0) & (price_expr >= ask_px_expr)).then(1.0)
            .when((bid_px_expr > 0) & (price_expr <= bid_px_expr)).then(-1.0)
            .when((ask_px_expr > 0) & (bid_px_expr > 0)).then(
                pl.when(price_expr >= (ask_px_expr + bid_px_expr) / 2.0).then(1.0).otherwise(-1.0)
            ).otherwise(0.0).alias("sign")
        ])

        size_expr = pl.col("size").cast(pl.Float64).fill_null(0.0).clip(lower_bound=0.0) if "size" in schema else pl.lit(0.0)

        trades = trades.with_columns([
            pl.when(pl.col("sign") > 0).then(size_expr).otherwise(0.0).alias("buy_volume"),
            pl.when(pl.col("sign") < 0).then(size_expr).otherwise(0.0).alias("sell_volume"),
        ])

        trade_sec = trades.sort(time_col).group_by_dynamic(
            time_col,
            every="1s"
        ).agg([
            pl.col("buy_volume").sum().alias("buy_volume_sec"),
            pl.col("sell_volume").sum().alias("sell_volume_sec"),
            pl.len().alias("trade_ticks_sec")
        ]).collect()

        trade_pd = trade_sec.to_pandas()
        if trade_pd.empty:
            trade_pd = pd.DataFrame(index=second_grid, columns=["buy_volume_sec", "sell_volume_sec", "trade_ticks_sec"])
        else:
            trade_pd.set_index(time_col, inplace=True)
            trade_pd.index = trade_pd.index.tz_localize("UTC") if trade_pd.index.tz is None else trade_pd.index.tz_convert("UTC")

        trade_pd["delta_sec"] = trade_pd["buy_volume_sec"] - trade_pd["sell_volume_sec"]
        
        # Reindex to grid (no ffill for trades, use 0)
        trade_pd = trade_pd.reindex(second_grid).fillna(0)
        trade_pd["trade_ticks_sec"] = trade_pd["trade_ticks_sec"].astype(int)

        return trade_pd

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

        return self.build_frames_from_loaded(loaded, start_dt_utc, end_dt_utc)

    def build_frames_from_loaded(
        self,
        loaded: pd.DataFrame,
        start_dt_utc: datetime,
        end_dt_utc: datetime,
    ) -> pd.DataFrame:
        """Build 1-second frames using already loaded raw L2 data."""
        if loaded is None:
            return pd.DataFrame()

        df = self.manager._normalize_datetime_index_utc(loaded)
        if not df.index.is_monotonic_increasing:
            df = df.sort_index()

        # Fast indexed time-slice (avoids full O(n) boolean mask per minute).
        df = df.loc[start_dt_utc:end_dt_utc].copy()

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
        frames["coverage_ratio"] = (
            covered_seconds / total_seconds if total_seconds > 0 else 0.0
        )

        # Reset index to make ts_sec a column
        frames = frames.reset_index().rename(columns={"index": "ts_sec"})

        return frames
