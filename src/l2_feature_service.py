"""
L2 feature extraction and minute-level bar enrichment.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

import pandas as pd

from .l2_data_manager import L2DataManager
from .order_flow_engine import OrderFlowEngine


@dataclass
class L2FeatureService:
    """Build and attach L2 features for minute bars."""

    manager: L2DataManager
    logger: logging.Logger

    @staticmethod
    def to_utc_datetime(value: Any) -> datetime:
        """Best-effort conversion to timezone-aware UTC datetime."""
        if isinstance(value, datetime):
            dt = value
        else:
            dt = pd.to_datetime(value).to_pydatetime()

        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    @classmethod
    def epoch_minute_key(cls, value: Any) -> int:
        dt_utc = cls.to_utc_datetime(value)
        return int(dt_utc.timestamp() // 60)

    def build_feature_map(
        self,
        ticker: str,
        start_dt_utc: datetime,
        end_dt_utc: datetime,
    ) -> Tuple[Dict[int, Dict[str, float]], Dict[str, Any]]:
        """
        Build minute-level L2 features keyed by UTC epoch-minute.

        Features:
        - l2_delta
        - l2_buy_volume / l2_sell_volume / l2_volume
        - l2_imbalance
        - l2_bid_depth_total / l2_ask_depth_total
        - l2_book_pressure / l2_book_pressure_delta
        - l2_iceberg_buy_count / l2_iceberg_sell_count / l2_iceberg_bias
        """
        feature_map: Dict[int, Dict[str, float]] = {}
        stats = {
            "has_l2": False,
            "footprint_bars": 0,
            "icebergs": 0,
            "covered_minutes": 0,
        }

        try:
            flow_engine = OrderFlowEngine(manager=self.manager)
            feature_map, flow_stats = flow_engine.build_enriched_feature_map(
                ticker=ticker,
                start_dt_utc=start_dt_utc,
                end_dt_utc=end_dt_utc,
            )
            stats.update(flow_stats)
        except Exception as e:
            self.logger.warning(f"OrderFlowEngine build failed for {ticker}: {e}")
            feature_map = {}
            stats.update(
                {
                    "has_l2": False,
                    "footprint_bars": 0,
                    "covered_minutes": 0,
                }
            )

        try:
            icebergs = self.manager.detect_icebergs(
                ticker=ticker,
                start_time=start_dt_utc,
                end_time=end_dt_utc,
            )
        except Exception as e:
            self.logger.warning(f"L2 iceberg detection failed for {ticker}: {e}")
            icebergs = []

        stats["icebergs"] = len(icebergs)
        for ice in icebergs:
            ts = ice.get("time")
            if not ts:
                continue
            try:
                minute_key = self.epoch_minute_key(ts)
            except Exception:
                continue

            bucket = feature_map.setdefault(
                minute_key,
                {
                    "l2_delta": 0.0,
                    "l2_buy_volume": 0.0,
                    "l2_sell_volume": 0.0,
                    "l2_volume": 0.0,
                    "l2_imbalance": 0.0,
                    "l2_signed_aggression": 0.0,
                    "l2_absorption_rate": 0.0,
                    "l2_cumulative_delta": 0.0,
                    "l2_delta_price_divergence": 0.0,
                    "l2_delta_acceleration": 0.0,
                    "l2_bid_depth_total": 0.0,
                    "l2_ask_depth_total": 0.0,
                    "l2_book_pressure": 0.0,
                    "l2_book_pressure_delta": 0.0,
                    "l2_top_heavy_bid": 0.0,
                    "l2_top_heavy_ask": 0.0,
                    "l2_iceberg_buy_count": 0.0,
                    "l2_iceberg_sell_count": 0.0,
                    "l2_iceberg_bias": 0.0,
                    "l2_quality_trade_ticks": 0,
                    "l2_quality_book_updates": 0,
                    "l2_quality_coverage_ratio": 0.0,
                },
            )
            bucket.setdefault("l2_iceberg_buy_count", 0.0)
            bucket.setdefault("l2_iceberg_sell_count", 0.0)
            bucket.setdefault("l2_iceberg_bias", 0.0)
            side = str(ice.get("side", "")).lower()
            if side == "buy":
                bucket["l2_iceberg_buy_count"] += 1.0
            elif side == "sell":
                bucket["l2_iceberg_sell_count"] += 1.0
            bucket["l2_iceberg_bias"] = (
                bucket["l2_iceberg_buy_count"] - bucket["l2_iceberg_sell_count"]
            )

        stats["covered_minutes"] = len(feature_map)
        stats["has_l2"] = stats["covered_minutes"] > 0
        return feature_map, stats

    @classmethod
    def attach_features(
        cls,
        bars: List[Dict[str, Any]],
        feature_map: Dict[int, Dict[str, float]],
        l2_only: bool = False,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Attach minute-aligned L2 features to bars."""
        if not bars:
            return bars, {"bars_with_l2": 0, "bars_total": 0}

        enriched: List[Dict[str, Any]] = []
        bars_with_l2 = 0
        for bar in bars:
            minute_key = cls.epoch_minute_key(bar.get("timestamp"))
            feats = feature_map.get(minute_key)
            if feats:
                bars_with_l2 += 1
                bar = {**bar, **feats}
            if not l2_only or feats:
                enriched.append(bar)

        stats = {
            "bars_with_l2": bars_with_l2,
            "bars_total": len(bars),
            "bars_after_filter": len(enriched),
        }
        return enriched, stats
