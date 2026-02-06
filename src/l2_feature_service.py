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
        - l2_iceberg_buy_count / l2_iceberg_sell_count / l2_iceberg_bias
        """
        feature_map: Dict[int, Dict[str, float]] = {}
        stats = {
            "has_l2": False,
            "footprint_bars": 0,
            "icebergs": 0,
            "covered_minutes": 0,
        }

        start_date = start_dt_utc.strftime("%Y-%m-%d")
        end_date = end_dt_utc.strftime("%Y-%m-%d")
        loaded = self.manager.load_data(ticker, start_date, end_date)
        if loaded is None:
            return feature_map, stats

        try:
            fp_bars = self.manager.get_footprint_bars(
                ticker=ticker,
                start_time=start_dt_utc,
                end_time=end_dt_utc,
                timeframe="1min",
            )
        except Exception as e:
            self.logger.warning(f"L2 footprint aggregation failed for {ticker}: {e}")
            fp_bars = []

        stats["footprint_bars"] = len(fp_bars)
        for fp in fp_bars:
            try:
                minute_key = int(float(fp.get("time", 0)) // 60)
            except (TypeError, ValueError):
                continue

            levels = fp.get("levels") or {}
            buy_volume = 0.0
            sell_volume = 0.0
            if isinstance(levels, dict):
                for level in levels.values():
                    if not isinstance(level, dict):
                        continue
                    buy_volume += float(level.get("buy", 0) or 0)
                    sell_volume += float(level.get("sell", 0) or 0)

            total_volume = float(fp.get("volume", 0) or 0)
            if total_volume <= 0:
                total_volume = buy_volume + sell_volume

            denom = buy_volume + sell_volume
            imbalance = ((buy_volume - sell_volume) / denom) if denom > 0 else 0.0

            feature_map[minute_key] = {
                "l2_delta": float(fp.get("delta", 0) or 0),
                "l2_buy_volume": buy_volume,
                "l2_sell_volume": sell_volume,
                "l2_volume": total_volume,
                "l2_imbalance": imbalance,
                "l2_iceberg_buy_count": 0.0,
                "l2_iceberg_sell_count": 0.0,
                "l2_iceberg_bias": 0.0,
            }

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
                    "l2_iceberg_buy_count": 0.0,
                    "l2_iceberg_sell_count": 0.0,
                    "l2_iceberg_bias": 0.0,
                },
            )
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

