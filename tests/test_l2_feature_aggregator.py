"""Tests for L2FeatureAggregator."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys

import pandas as pd
import numpy as np
import pytest

# Add project root to path
_PROJECT_ROOT = str(Path(__file__).resolve().parents[1])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from src.l2_feature_aggregator import L2FeatureAggregator, AggregationResult


def _make_1s_frames(n_seconds: int = 60) -> pd.DataFrame:
    """Create synthetic 1s frames for one minute."""
    base_ts = datetime(2026, 1, 20, 14, 30, 0, tzinfo=timezone.utc)
    
    data = []
    for s in range(n_seconds):
        ts = base_ts.replace(second=s)
        data.append({
            "ts_sec": ts,
            "buy_volume_sec": 100.0 + s,  # varying buy volume
            "sell_volume_sec": 80.0 + s,  # varying sell volume
            "delta_sec": 20.0,  # constant delta (buy - sell)
            "trade_ticks_sec": 5,
            "book_updates_sec": 10,
            "depth_bid_total": 5000.0,
            "depth_ask_total": 4500.0,
            "imbalance_sec": 0.05,
            "book_pressure_sec": 0.1 + s * 0.001,  # slowly increasing
            "spread_bps": 5.0,
            "has_book_coverage": True,
        })
    
    return pd.DataFrame(data)


def test_aggregate_minute_sums_volumes():
    """Test that volume columns are summed correctly."""
    df_1s = _make_1s_frames(60)
    minute_key = int(datetime(2026, 1, 20, 14, 30, 0, tzinfo=timezone.utc).timestamp())
    
    result = L2FeatureAggregator.aggregate_minute(df_1s, minute_key)
    
    # buy_volume should be sum(100+s for s in 0..59) = 60*100 + sum(0..59) = 6000 + 1770 = 7770
    assert result.features["l2_buy_volume"] == pytest.approx(7770.0)
    assert result.features["l2_sell_volume"] == pytest.approx(6570.0)  # 60*80 + 1770
    assert result.features["l2_volume"] == pytest.approx(7770.0 + 6570.0)


def test_aggregate_minute_averages_book_metrics():
    """Test that book metrics are averaged correctly."""
    df_1s = _make_1s_frames(60)
    minute_key = int(datetime(2026, 1, 20, 14, 30, 0, tzinfo=timezone.utc).timestamp())
    
    result = L2FeatureAggregator.aggregate_minute(df_1s, minute_key)
    
    assert result.features["l2_bid_depth_total"] == pytest.approx(5000.0)
    assert result.features["l2_ask_depth_total"] == pytest.approx(4500.0)
    assert result.features["l2_imbalance"] == pytest.approx(0.05)


def test_aggregate_minute_book_pressure_delta():
    """Test that book_pressure_delta is LAST - FIRST."""
    df_1s = _make_1s_frames(60)
    minute_key = int(datetime(2026, 1, 20, 14, 30, 0, tzinfo=timezone.utc).timestamp())
    
    result = L2FeatureAggregator.aggregate_minute(df_1s, minute_key)
    
    # pressure starts at 0.1, ends at 0.1 + 59*0.001 = 0.159
    expected_delta = 0.159 - 0.1
    assert result.features["l2_book_pressure_change"] == pytest.approx(expected_delta)


def test_aggregate_minute_delta_consistency():
    """Test that delta sanity check passes when delta = buy - sell."""
    df_1s = _make_1s_frames(60)
    minute_key = int(datetime(2026, 1, 20, 14, 30, 0, tzinfo=timezone.utc).timestamp())
    
    result = L2FeatureAggregator.aggregate_minute(df_1s, minute_key)
    
    # delta_sec is constant 20, so total is 60*20 = 1200
    assert result.features["l2_delta"] == pytest.approx(1200.0)
    
    # But buy - sell = 7770 - 6570 = 1200 ✓
    # Sanity check should pass
    assert not any("DELTA_MISMATCH" in f for f in result.sanity_flags)


def test_aggregate_minute_volume_mismatch_flag():
    """Test that volume mismatch raises sanity flag."""
    df_1s = _make_1s_frames(60)
    minute_key = int(datetime(2026, 1, 20, 14, 30, 0, tzinfo=timezone.utc).timestamp())
    
    # Expected OHLCV volume is way off
    result = L2FeatureAggregator.aggregate_minute(
        df_1s, minute_key, 
        expected_volume=50000.0,  # Much higher than actual
        volume_tolerance=0.01,
    )
    
    assert any("VOLUME_MISMATCH" in f for f in result.sanity_flags)


def test_aggregate_minute_low_coverage_flag():
    """Test that low coverage raises warning flag."""
    df_1s = _make_1s_frames(20)  # Only 20 seconds of data
    minute_key = int(datetime(2026, 1, 20, 14, 30, 0, tzinfo=timezone.utc).timestamp())
    
    result = L2FeatureAggregator.aggregate_minute(df_1s, minute_key)
    
    assert result.coverage_ratio == pytest.approx(20/60)
    assert any("LOW_COVERAGE" in f for f in result.sanity_flags)


def test_aggregate_session():
    """Test aggregating multiple minutes."""
    # Create 2 minutes of data
    frames = []
    for minute in range(2):
        base_ts = datetime(2026, 1, 20, 14, 30 + minute, 0, tzinfo=timezone.utc)
        for s in range(60):
            frames.append({
                "ts_sec": base_ts.replace(second=s),
                "buy_volume_sec": 100.0,
                "sell_volume_sec": 50.0,
                "delta_sec": 50.0,
                "trade_ticks_sec": 5,
                "book_updates_sec": 10,
                "depth_bid_total": 5000.0,
                "depth_ask_total": 4500.0,
                "imbalance_sec": 0.05,
                "book_pressure_sec": 0.1,
                "spread_bps": 5.0,
                "has_book_coverage": True,
            })
    
    df_1s = pd.DataFrame(frames)
    
    df_1m, stats = L2FeatureAggregator.aggregate_session(df_1s)
    
    assert len(df_1m) == 2
    assert stats["minutes"] == 2
    assert stats["minutes_with_flags"] == 0


def test_aggregate_empty():
    """Test handling empty data."""
    df_1s = pd.DataFrame()
    minute_key = int(datetime(2026, 1, 20, 14, 30, 0, tzinfo=timezone.utc).timestamp())
    
    result = L2FeatureAggregator.aggregate_minute(df_1s, minute_key)
    
    assert result.coverage_ratio == 0.0
    assert "NO_DATA" in result.sanity_flags
