"""
Order-flow feature engine built on raw MBP-10 data.

L2 Feature Definitions (l2fv-1.0)
=================================
Field Units & Semantics:
- l2_delta: shares (buy_volume - sell_volume)
- l2_imbalance: ratio [-1,1] = delta / volume (size-weighted)
- l2_book_pressure: ratio [-1,1] = (bid_depth - ask_depth) / total_depth
- l2_book_pressure_delta: ratio = book_pressure[t] - book_pressure[t-1]

Aggressor Classification Priority:
1. side field from source ("B" = buy aggressor, "A" = sell aggressor)
2. price >= ask -> buy; price <= bid -> sell
3. price vs mid: price >= mid -> buy; price < mid -> sell
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

import pandas as pd

from .l2_data_manager import L2DataManager

# Schema version for L2 feature vector contract
L2_SCHEMA_VERSION = "l2fv-1.0"


@dataclass
class OrderFlowSnapshot:
    """Snapshot of order-flow metrics for a single minute bar."""
    # Existing flow metrics (units: shares)
    delta: float
    cumulative_delta: float
    imbalance: float  # ratio [-1, 1]
    signed_aggression: float  # alias for imbalance
    absorption_rate: float  # [0, 1]

    # Book-pressure metrics
    bid_depth_total: float  # shares
    ask_depth_total: float  # shares
    book_pressure: float  # ratio [-1, 1]
    book_pressure_delta: float  # ratio (change vs previous bar)
    top_heavy_bid: float  # ratio [0, 1]
    top_heavy_ask: float  # ratio [0, 1]

    # Divergence / acceleration
    delta_price_divergence: float
    delta_acceleration: float  # shares

    # Quality metrics
    trade_ticks: int = 0
    book_updates: int = 0
    quality_flags: List[str] = field(default_factory=list)


@dataclass
class OrderFlowEngine:
    manager: L2DataManager

    @staticmethod
    def _to_utc_datetime(value: Any) -> datetime:
        dt = value if isinstance(value, datetime) else pd.to_datetime(value).to_pydatetime()
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    @classmethod
    def _minute_key(cls, value: Any) -> int:
        return int(cls._to_utc_datetime(value).timestamp() // 60)

    @staticmethod
    def _safe_div(numerator: float, denominator: float, default: float = 0.0) -> float:
        if denominator == 0:
            return default
        return numerator / denominator

    def _load_chunk(
        self,
        ticker: str,
        start_dt_utc: datetime,
        end_dt_utc: datetime,
    ) -> pd.DataFrame:
        start_date = start_dt_utc.strftime("%Y-%m-%d")
        end_date = end_dt_utc.strftime("%Y-%m-%d")
        loaded = self.manager.load_data(ticker, start_date, end_date)
        if loaded is None or ticker not in self.manager.data:
            return pd.DataFrame()
        df = self.manager.data[ticker]
        df = self.manager._normalize_datetime_index_utc(df)  # noqa: SLF001
        mask = (df.index >= start_dt_utc) & (df.index <= end_dt_utc)
        return df.loc[mask].copy()

    @staticmethod
    def _infer_trade_sign(row: pd.Series) -> float:
        side = str(row.get("side", "")).upper()
        price = float(row.get("price", 0.0) or 0.0)
        ask = float(row.get("ask_px_00", 0.0) or 0.0)
        bid = float(row.get("bid_px_00", 0.0) or 0.0)

        if side == "B":
            return 1.0
        if side == "A":
            return -1.0
        if ask > 0 and price >= ask:
            return 1.0
        if bid > 0 and price <= bid:
            return -1.0
        if ask > 0 and bid > 0:
            mid = (ask + bid) / 2.0
            return 1.0 if price >= mid else -1.0
        return 0.0

    def compute_book_pressure(
        self,
        ticker: str,
        start_dt_utc: datetime,
        end_dt_utc: datetime,
    ) -> Tuple[Dict[int, Dict[str, float]], Dict[str, Any]]:
        chunk = self._load_chunk(ticker, start_dt_utc, end_dt_utc)
        out: Dict[int, Dict[str, float]] = {}
        stats = {"depth_minutes": 0}
        if chunk.empty:
            return out, stats

        bid_cols = [f"bid_sz_{idx:02d}" for idx in range(10)]
        ask_cols = [f"ask_sz_{idx:02d}" for idx in range(10)]
        for col in bid_cols + ask_cols:
            if col not in chunk.columns:
                chunk[col] = 0.0

        pressure_keys = []
        for ts, group in chunk.groupby(pd.Grouper(freq="1min")):
            if group.empty:
                continue
            minute_key = self._minute_key(ts)

            bid_depth_rows = group[bid_cols].astype(float).clip(lower=0.0)
            ask_depth_rows = group[ask_cols].astype(float).clip(lower=0.0)

            bid_depth_total = float(bid_depth_rows.sum(axis=1).mean())
            ask_depth_total = float(ask_depth_rows.sum(axis=1).mean())
            denom = bid_depth_total + ask_depth_total
            book_pressure = self._safe_div(bid_depth_total - ask_depth_total, denom, 0.0)

            top_bid = float(bid_depth_rows["bid_sz_00"].mean())
            top_ask = float(ask_depth_rows["ask_sz_00"].mean())
            top_heavy_bid = self._safe_div(top_bid, bid_depth_total, 0.0)
            top_heavy_ask = self._safe_div(top_ask, ask_depth_total, 0.0)

            out[minute_key] = {
                "bid_depth_total": bid_depth_total,
                "ask_depth_total": ask_depth_total,
                "book_pressure": book_pressure,
                "book_pressure_delta": 0.0,
                "top_heavy_bid": top_heavy_bid,
                "top_heavy_ask": top_heavy_ask,
                "book_updates": len(group),
            }
            pressure_keys.append(minute_key)

        pressure_keys.sort()
        prev_pressure = 0.0
        for idx, minute_key in enumerate(pressure_keys):
            current = float(out[minute_key].get("book_pressure", 0.0))
            out[minute_key]["book_pressure_delta"] = current - prev_pressure if idx > 0 else 0.0
            prev_pressure = current

        stats["depth_minutes"] = len(out)
        return out, stats

    def compute_trade_flow(
        self,
        ticker: str,
        start_dt_utc: datetime,
        end_dt_utc: datetime,
    ) -> Tuple[Dict[int, Dict[str, float]], Dict[str, Any]]:
        chunk = self._load_chunk(ticker, start_dt_utc, end_dt_utc)
        out: Dict[int, Dict[str, float]] = {}
        stats = {"trade_minutes": 0, "trade_events": 0}
        if chunk.empty:
            return out, stats

        if "action" in chunk.columns:
            actions = chunk["action"].astype(str).str.upper()
            trades = chunk.loc[actions == "T"].copy()
        else:
            trades = chunk.copy()
        if trades.empty:
            return out, stats

        stats["trade_events"] = int(len(trades))

        minute_keys = []
        running_cumulative = 0.0
        prev_delta = 0.0
        for ts, group in trades.groupby(pd.Grouper(freq="1min")):
            if group.empty:
                continue
            minute_key = self._minute_key(ts)

            buy_volume = 0.0
            sell_volume = 0.0
            for _, row in group.iterrows():
                size = max(0.0, float(row.get("size", 0.0) or 0.0))
                sign = self._infer_trade_sign(row)
                if sign > 0:
                    buy_volume += size
                elif sign < 0:
                    sell_volume += size

            total_volume = buy_volume + sell_volume
            delta = buy_volume - sell_volume
            running_cumulative += delta
            imbalance = self._safe_div(delta, total_volume, 0.0)
            signed_aggression = self._safe_div(delta, total_volume, 0.0)

            prices = group["price"].astype(float) if "price" in group.columns else pd.Series(dtype=float)
            first_price = float(prices.iloc[0]) if len(prices) else 0.0
            last_price = float(prices.iloc[-1]) if len(prices) else 0.0
            price_change_pct = self._safe_div((last_price - first_price) * 100.0, first_price, 0.0)

            # Large flow + small price progress => absorption proxy in [0, 1].
            volume_score = max(0.0, min(1.0, total_volume / 5000.0))
            move_penalty = max(0.0, min(1.0, abs(price_change_pct) / 0.15))
            absorption_rate = max(0.0, min(1.0, volume_score * (1.0 - move_penalty)))

            vol_floor = max(abs(price_change_pct), 0.05)
            normalized_price = price_change_pct / vol_floor
            delta_price_divergence = signed_aggression - normalized_price
            delta_acceleration = delta - prev_delta
            prev_delta = delta

            out[minute_key] = {
                "delta": delta,
                "cumulative_delta": running_cumulative,
                "imbalance": imbalance,
                "signed_aggression": signed_aggression,
                "absorption_rate": absorption_rate,
                "delta_price_divergence": delta_price_divergence,
                "delta_acceleration": delta_acceleration,
                "buy_volume": buy_volume,
                "sell_volume": sell_volume,
                "volume": total_volume,
                "trade_ticks": len(group),
            }
            minute_keys.append(minute_key)

        stats["trade_minutes"] = len(out)
        return out, stats

    def build_enriched_feature_map(
        self,
        ticker: str,
        start_dt_utc: datetime,
        end_dt_utc: datetime,
    ) -> Tuple[Dict[int, Dict[str, float]], Dict[str, Any]]:
        trade_map, trade_stats = self.compute_trade_flow(ticker, start_dt_utc, end_dt_utc)
        book_map, book_stats = self.compute_book_pressure(ticker, start_dt_utc, end_dt_utc)

        feature_map: Dict[int, Dict[str, float]] = {}
        all_keys = sorted(set(trade_map.keys()) | set(book_map.keys()))
        running_cumulative = 0.0
        prev_delta = 0.0
        for minute_key in all_keys:
            trade = trade_map.get(minute_key, {})
            book = book_map.get(minute_key, {})

            delta = float(trade.get("delta", 0.0))
            running_cumulative = float(trade.get("cumulative_delta", running_cumulative + delta))
            delta_acceleration = float(trade.get("delta_acceleration", delta - prev_delta))
            prev_delta = delta

            snapshot = OrderFlowSnapshot(
                delta=delta,
                cumulative_delta=running_cumulative,
                imbalance=float(trade.get("imbalance", 0.0)),
                signed_aggression=float(trade.get("signed_aggression", 0.0)),
                absorption_rate=float(trade.get("absorption_rate", 0.0)),
                bid_depth_total=float(book.get("bid_depth_total", 0.0)),
                ask_depth_total=float(book.get("ask_depth_total", 0.0)),
                book_pressure=float(book.get("book_pressure", 0.0)),
                book_pressure_delta=float(book.get("book_pressure_delta", 0.0)),
                top_heavy_bid=float(book.get("top_heavy_bid", 0.0)),
                top_heavy_ask=float(book.get("top_heavy_ask", 0.0)),
                delta_price_divergence=float(trade.get("delta_price_divergence", 0.0)),
                delta_acceleration=delta_acceleration,
                trade_ticks=int(trade.get("trade_ticks", 0)),
                book_updates=int(book.get("book_updates", 0)),
            )

            feature_map[minute_key] = {
                # Schema version
                "l2_schema_version": L2_SCHEMA_VERSION,
                # Existing payload fields (units: shares)
                "l2_delta": snapshot.delta,
                "l2_buy_volume": float(trade.get("buy_volume", 0.0)),
                "l2_sell_volume": float(trade.get("sell_volume", 0.0)),
                "l2_volume": float(trade.get("volume", 0.0)),
                "l2_imbalance": snapshot.imbalance,
                # Additional flow-rich fields
                "l2_signed_aggression": snapshot.signed_aggression,
                "l2_absorption_rate": snapshot.absorption_rate,
                "l2_cumulative_delta": snapshot.cumulative_delta,
                "l2_delta_price_divergence": snapshot.delta_price_divergence,
                "l2_delta_acceleration": snapshot.delta_acceleration,
                # Book fields
                "l2_bid_depth_total": snapshot.bid_depth_total,
                "l2_ask_depth_total": snapshot.ask_depth_total,
                "l2_book_pressure": snapshot.book_pressure,
                "l2_book_pressure_delta": snapshot.book_pressure_delta,
                "l2_top_heavy_bid": snapshot.top_heavy_bid,
                "l2_top_heavy_ask": snapshot.top_heavy_ask,
                # Quality metrics
                "l2_quality_trade_ticks": snapshot.trade_ticks,
                "l2_quality_book_updates": snapshot.book_updates,
            }

        # Calculate coverage ratio
        expected_minutes = int((end_dt_utc - start_dt_utc).total_seconds() / 60)
        coverage_ratio = len(feature_map) / expected_minutes if expected_minutes > 0 else 0.0
        for minute_key in feature_map:
            feature_map[minute_key]["l2_quality_coverage_ratio"] = coverage_ratio

        stats = {
            "has_l2": bool(feature_map),
            "covered_minutes": len(feature_map),
            "trade_minutes": int(trade_stats.get("trade_minutes", 0)),
            "trade_events": int(trade_stats.get("trade_events", 0)),
            "depth_minutes": int(book_stats.get("depth_minutes", 0)),
            # Keep backwards-compatible naming for API responses.
            "footprint_bars": int(trade_stats.get("trade_minutes", 0)),
        }
        return feature_map, stats
