"""Tests for IntrabarFrameBuilder."""
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

from src.intrabar_frame_builder import IntrabarFrameBuilder, INTRABAR_SCHEMA_VERSION


class MockL2DataManager:
    """Mock manager that returns synthetic L2 data."""
    
    def __init__(self, data: pd.DataFrame):
        self.data = {"TEST": data}
    
    def load_data(self, ticker, start_date, end_date):
        return self.data.get(ticker)
    
    @staticmethod
    def _normalize_datetime_index_utc(df: pd.DataFrame) -> pd.DataFrame:
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)
        if df.index.tz is None:
            df.index = df.index.tz_localize("UTC")
        return df


def _make_test_data() -> pd.DataFrame:
    """Create synthetic MBP-10 data for testing."""
    # Create 10 seconds of data with mixed book updates and trades
    base_ts = datetime(2026, 1, 20, 14, 30, 0, tzinfo=timezone.utc)
    
    rows = []
    
    # Second 0: Book update
    rows.append({
        "ts": base_ts,
        "action": "M",  # Book modification
        "price": 100.0,
        "size": 0,
        "side": "N",
        "bid_px_00": 99.95, "bid_sz_00": 500,
        "ask_px_00": 100.05, "ask_sz_00": 600,
        "bid_sz_01": 300, "ask_sz_01": 400,
    })
    
    # Second 1: Trade (buy aggressor)
    rows.append({
        "ts": base_ts.replace(second=1),
        "action": "T",
        "price": 100.05,
        "size": 100,
        "side": "B",  # Buy aggressor
        "bid_px_00": 99.95, "bid_sz_00": 500,
        "ask_px_00": 100.05, "ask_sz_00": 500,
    })
    
    # Second 2: Multiple trades
    rows.append({
        "ts": base_ts.replace(second=2, microsecond=100000),
        "action": "T",
        "price": 100.05,
        "size": 50,
        "side": "B",
        "bid_px_00": 99.95, "bid_sz_00": 500,
        "ask_px_00": 100.05, "ask_sz_00": 450,
    })
    rows.append({
        "ts": base_ts.replace(second=2, microsecond=500000),
        "action": "T",
        "price": 99.95,
        "size": 75,
        "side": "A",  # Sell aggressor
        "bid_px_00": 99.95, "bid_sz_00": 425,
        "ask_px_00": 100.05, "ask_sz_00": 450,
    })
    
    # Second 5: Book update after gap
    rows.append({
        "ts": base_ts.replace(second=5),
        "action": "M",
        "price": 100.0,
        "size": 0,
        "side": "N",
        "bid_px_00": 99.90, "bid_sz_00": 800,
        "ask_px_00": 100.10, "ask_sz_00": 700,
        "bid_sz_01": 400, "ask_sz_01": 500,
    })
    
    df = pd.DataFrame(rows)
    df = df.set_index(pd.to_datetime(df["ts"]))
    df = df.drop(columns=["ts"])
    
    # Fill missing columns with 0
    for i in range(10):
        for col in [f"bid_sz_{i:02d}", f"ask_sz_{i:02d}", 
                    f"bid_px_{i:02d}", f"ask_px_{i:02d}"]:
            if col not in df.columns:
                df[col] = 0.0 if "px" in col else 0
    
    return df


def test_intrabar_frame_builder_creates_second_grid():
    """Test that builder creates correct 1-second grid."""
    df = _make_test_data()
    manager = MockL2DataManager(df)
    builder = IntrabarFrameBuilder(manager=manager)
    
    start = datetime(2026, 1, 20, 14, 30, 0, tzinfo=timezone.utc)
    end = datetime(2026, 1, 20, 14, 30, 5, tzinfo=timezone.utc)
    
    frames = builder.build_frames("TEST", start, end)
    
    # Should have 6 seconds (0-5 inclusive)
    assert len(frames) == 6
    assert "ts_sec" in frames.columns
    assert "schema_version" in frames.columns
    assert frames["schema_version"].iloc[0] == INTRABAR_SCHEMA_VERSION


def test_intrabar_frame_builder_trade_aggregation():
    """Test that trades are correctly aggregated per second."""
    df = _make_test_data()
    manager = MockL2DataManager(df)
    builder = IntrabarFrameBuilder(manager=manager)
    
    start = datetime(2026, 1, 20, 14, 30, 0, tzinfo=timezone.utc)
    end = datetime(2026, 1, 20, 14, 30, 5, tzinfo=timezone.utc)
    
    frames = builder.build_frames("TEST", start, end)
    
    # Second 1: 100 shares buy
    sec1 = frames[frames["ts_sec"].dt.second == 1].iloc[0]
    assert sec1["buy_volume_sec"] == 100.0
    assert sec1["sell_volume_sec"] == 0.0
    assert sec1["delta_sec"] == 100.0
    assert sec1["trade_ticks_sec"] == 1
    
    # Second 2: 50 buy + 75 sell
    sec2 = frames[frames["ts_sec"].dt.second == 2].iloc[0]
    assert sec2["buy_volume_sec"] == 50.0
    assert sec2["sell_volume_sec"] == 75.0
    assert sec2["delta_sec"] == -25.0
    assert sec2["trade_ticks_sec"] == 2


def test_intrabar_frame_builder_book_locf():
    """Test that book features use LOCF (last observation carried forward)."""
    df = _make_test_data()
    manager = MockL2DataManager(df)
    builder = IntrabarFrameBuilder(manager=manager)
    
    start = datetime(2026, 1, 20, 14, 30, 0, tzinfo=timezone.utc)
    end = datetime(2026, 1, 20, 14, 30, 5, tzinfo=timezone.utc)
    
    frames = builder.build_frames("TEST", start, end)
    
    # Second 0 has book update
    sec0 = frames[frames["ts_sec"].dt.second == 0].iloc[0]
    assert sec0["has_book_coverage"] == True
    assert sec0["depth_bid_total"] > 0
    
    # Seconds 1-4 should carry forward from second 0
    # (trades update the index but book features carry forward)
    sec3 = frames[frames["ts_sec"].dt.second == 3].iloc[0]
    # Should have carried forward depth from most recent book update
    assert pd.notna(sec3["depth_bid_total"])
    
    # Second 5 has new book update
    sec5 = frames[frames["ts_sec"].dt.second == 5].iloc[0]
    assert sec5["depth_bid_total"] > 0


def test_intrabar_frame_builder_cumulative_delta():
    """Test that cumulative delta is computed correctly."""
    df = _make_test_data()
    manager = MockL2DataManager(df)
    builder = IntrabarFrameBuilder(manager=manager)
    
    start = datetime(2026, 1, 20, 14, 30, 0, tzinfo=timezone.utc)
    end = datetime(2026, 1, 20, 14, 30, 5, tzinfo=timezone.utc)
    
    frames = builder.build_frames("TEST", start, end)
    
    # Cumulative should be running sum
    # Sec 0: delta=0, cum=0
    # Sec 1: delta=100, cum=100
    # Sec 2: delta=-25, cum=75
    assert frames[frames["ts_sec"].dt.second == 0].iloc[0]["cum_delta_sec"] == 0.0
    assert frames[frames["ts_sec"].dt.second == 1].iloc[0]["cum_delta_sec"] == 100.0
    assert frames[frames["ts_sec"].dt.second == 2].iloc[0]["cum_delta_sec"] == 75.0


def test_intrabar_frame_builder_empty_data():
    """Test handling of empty data."""
    empty_df = pd.DataFrame()
    manager = MockL2DataManager(empty_df)
    builder = IntrabarFrameBuilder(manager=manager)
    
    start = datetime(2026, 1, 20, 14, 30, 0, tzinfo=timezone.utc)
    end = datetime(2026, 1, 20, 14, 30, 5, tzinfo=timezone.utc)
    
    frames = builder.build_frames("MISSING", start, end)
    
    assert frames.empty
