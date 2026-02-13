"""
L2 Feature Aggregator: Aggregate 1-second frames to 1-minute features.

Ensures consistency between 1s → 1m aggregation with sanity checks.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


@dataclass
class AggregationResult:
    """Result of 1s → 1m aggregation with quality metrics."""
    
    features: Dict[str, float]
    minute_key: int
    coverage_ratio: float
    seconds_with_data: int
    sanity_flags: List[str] = field(default_factory=list)
    
    @property
    def is_valid(self) -> bool:
        """Returns True if no sanity flags were raised."""
        return len(self.sanity_flags) == 0


class L2FeatureAggregator:
    """Aggregate 1-second frames to 1-minute features.
    
    Aggregation Rules:
    - Volume metrics (buy, sell, delta, total): SUM
    - Depth metrics (bid, ask totals): AVG
    - Ratio metrics (imbalance, pressure): AVG
    - book_pressure_delta: LAST - FIRST
    - Count metrics (ticks, updates): SUM
    """
    
    # Columns to sum
    SUM_COLUMNS = [
        "buy_volume_sec", "sell_volume_sec", "delta_sec",
        "trade_ticks_sec", "book_updates_sec",
    ]
    
    # Columns to average
    AVG_COLUMNS = [
        "depth_bid_total", "depth_ask_total",
        "imbalance_sec", "book_pressure_sec",
        "spread_bps", "top_bid_sz", "top_ask_sz",
    ]
    
    # Mapping from 1s column names to 1m output names
    COLUMN_MAPPING = {
        "buy_volume_sec": "l2_buy_volume",
        "sell_volume_sec": "l2_sell_volume", 
        "delta_sec": "l2_delta",
        "trade_ticks_sec": "l2_quality_trade_ticks",
        "book_updates_sec": "l2_quality_book_updates",
        "depth_bid_total": "l2_bid_depth_total",
        "depth_ask_total": "l2_ask_depth_total",
        "imbalance_sec": "l2_imbalance",
        "book_pressure_sec": "l2_book_pressure",
        "spread_bps": "l2_spread_bps",
        "top_bid_sz": "l2_top_bid_sz",
        "top_ask_sz": "l2_top_ask_sz",
    }

    @classmethod
    def aggregate_minute(
        cls,
        df_1s: pd.DataFrame,
        minute_key: int,
        expected_volume: Optional[float] = None,
        volume_tolerance: float = 0.01,
    ) -> AggregationResult:
        """Aggregate 1-second frames for a single minute.
        
        Args:
            df_1s: DataFrame with 1s features (should have 60 rows for full minute)
            minute_key: Unix timestamp of minute start
            expected_volume: Optional OHLCV volume for sanity check
            volume_tolerance: Tolerance for volume mismatch (default 1%)
            
        Returns:
            AggregationResult with aggregated features and quality metrics
        """
        sanity_flags: List[str] = []
        features: Dict[str, float] = {}
        
        if df_1s.empty:
            return AggregationResult(
                features={},
                minute_key=minute_key,
                coverage_ratio=0.0,
                seconds_with_data=0,
                sanity_flags=["NO_DATA"],
            )
        
        # Calculate coverage
        seconds_with_data = len(df_1s)
        coverage_ratio = seconds_with_data / 60.0
        
        # Check book coverage specifically
        if "has_book_coverage" in df_1s.columns:
            book_coverage = df_1s["has_book_coverage"].sum() / 60.0
        else:
            book_coverage = coverage_ratio
        
        features["l2_quality_coverage_ratio"] = coverage_ratio
        features["l2_quality_book_coverage_ratio"] = book_coverage
        
        # SUM aggregations
        for col in cls.SUM_COLUMNS:
            if col in df_1s.columns:
                out_col = cls.COLUMN_MAPPING.get(col, f"l2_{col}")
                features[out_col] = float(df_1s[col].sum())
        
        # AVG aggregations
        for col in cls.AVG_COLUMNS:
            if col in df_1s.columns:
                out_col = cls.COLUMN_MAPPING.get(col, f"l2_{col}")
                features[out_col] = float(df_1s[col].mean())
        
        # book_pressure_delta: LAST - FIRST
        if "book_pressure_sec" in df_1s.columns:
            first_pressure = float(df_1s["book_pressure_sec"].iloc[0])
            last_pressure = float(df_1s["book_pressure_sec"].iloc[-1])
            features["l2_book_pressure_change"] = last_pressure - first_pressure
        
        # Compute l2_volume
        buy_vol = features.get("l2_buy_volume", 0.0)
        sell_vol = features.get("l2_sell_volume", 0.0)
        features["l2_volume"] = buy_vol + sell_vol
        
        # === SANITY CHECKS ===
        
        # Check 1: delta == buy - sell
        delta = features.get("l2_delta", 0.0)
        expected_delta = buy_vol - sell_vol
        if abs(delta - expected_delta) > 0.01:
            sanity_flags.append(f"DELTA_MISMATCH: {delta} != {expected_delta}")
        
        # Check 2: volume matches OHLCV volume (if provided)
        if expected_volume is not None and expected_volume > 0:
            l2_volume = features.get("l2_volume", 0.0)
            volume_diff = abs(l2_volume - expected_volume) / expected_volume
            if volume_diff > volume_tolerance:
                sanity_flags.append(
                    f"VOLUME_MISMATCH: L2={l2_volume:.0f} vs OHLCV={expected_volume:.0f} "
                    f"(diff={volume_diff*100:.1f}%)"
                )
        
        # Check 3: coverage warning
        if coverage_ratio < 0.5:
            sanity_flags.append(f"LOW_COVERAGE: {coverage_ratio*100:.0f}%")
        
        return AggregationResult(
            features=features,
            minute_key=minute_key,
            coverage_ratio=coverage_ratio,
            seconds_with_data=seconds_with_data,
            sanity_flags=sanity_flags,
        )

    @classmethod
    def aggregate_session(
        cls,
        df_1s: pd.DataFrame,
        expected_volumes: Optional[Dict[int, float]] = None,
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """Aggregate all 1s frames in a session to 1m features.
        
        Args:
            df_1s: DataFrame with 1s features indexed by ts_sec
            expected_volumes: Optional dict of minute_key → OHLCV volume
            
        Returns:
            Tuple of (df_1m features, aggregation stats)
        """
        if df_1s.empty:
            return pd.DataFrame(), {"minutes": 0, "flags": []}
        
        # Ensure ts_sec is datetime
        if "ts_sec" in df_1s.columns:
            df_1s = df_1s.copy()
            if not pd.api.types.is_datetime64_any_dtype(df_1s["ts_sec"]):
                df_1s["ts_sec"] = pd.to_datetime(df_1s["ts_sec"])
            df_1s["minute_key"] = df_1s["ts_sec"].apply(
                lambda t: int(t.replace(second=0, microsecond=0).timestamp())
            )
        elif isinstance(df_1s.index, pd.DatetimeIndex):
            df_1s = df_1s.copy()
            df_1s["minute_key"] = df_1s.index.floor("1min").astype(int) // 10**9
        else:
            return pd.DataFrame(), {"minutes": 0, "flags": ["NO_TIMESTAMP"]}
        
        results = []
        all_flags = []
        expected_volumes = expected_volumes or {}
        
        for minute_key, group in df_1s.groupby("minute_key"):
            expected_vol = expected_volumes.get(int(minute_key))
            result = cls.aggregate_minute(group, int(minute_key), expected_vol)
            
            row = {"minute_key": minute_key, **result.features}
            results.append(row)
            
            if result.sanity_flags:
                all_flags.append({
                    "minute_key": minute_key,
                    "flags": result.sanity_flags,
                })
        
        df_1m = pd.DataFrame(results)
        
        stats = {
            "minutes": len(results),
            "minutes_with_flags": len(all_flags),
            "flags": all_flags,
        }
        
        return df_1m, stats
