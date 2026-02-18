from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from src.order_flow_engine import OrderFlowEngine


class _StubL2Manager:
    def __init__(self, df: pd.DataFrame):
        self._df = df

    def load_data(self, ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
        return self._df.copy()

    def _normalize_datetime_index_utc(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        out.index = pd.to_datetime(out.index, utc=True)
        return out


class _CountingStubL2Manager(_StubL2Manager):
    def __init__(self, df: pd.DataFrame):
        super().__init__(df)
        self.load_calls = 0

    def load_data(self, ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
        self.load_calls += 1
        return super().load_data(ticker, start_date, end_date)


def _make_df(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    df.index = pd.to_datetime(df.pop("ts"), utc=True)
    return df


def test_trade_flow_resets_cumulative_delta_by_market_day() -> None:
    df = _make_df(
        [
            {"ts": "2026-01-20T14:30:05Z", "action": "T", "side": "B", "size": 100.0, "price": 100.0},
            {"ts": "2026-01-20T14:31:05Z", "action": "T", "side": "B", "size": 100.0, "price": 100.2},
            {"ts": "2026-01-21T14:30:05Z", "action": "T", "side": "B", "size": 50.0, "price": 100.4},
        ]
    )
    engine = OrderFlowEngine(manager=_StubL2Manager(df))
    start_dt = datetime(2026, 1, 20, 14, 30, tzinfo=timezone.utc)
    end_dt = datetime(2026, 1, 21, 14, 31, tzinfo=timezone.utc)

    trade_map, _ = engine.compute_trade_flow("MU", start_dt, end_dt)
    minute_keys = sorted(trade_map.keys())

    assert len(minute_keys) == 3
    assert trade_map[minute_keys[0]]["cumulative_delta"] == 100.0
    assert trade_map[minute_keys[1]]["cumulative_delta"] == 200.0
    assert trade_map[minute_keys[2]]["cumulative_delta"] == 50.0


def test_book_pressure_clips_depth_outliers() -> None:
    rows: list[dict] = []
    for second in range(9):
        rows.append(
            {
                "ts": f"2026-01-20T14:30:{second:02d}Z",
                "bid_sz_00": 100.0,
                "ask_sz_00": 100.0,
            }
        )
    rows.append(
        {
            "ts": "2026-01-20T14:30:09Z",
            "bid_sz_00": 1_000_000.0,
            "ask_sz_00": 100.0,
        }
    )
    df = _make_df(rows)
    engine = OrderFlowEngine(manager=_StubL2Manager(df))
    start_dt = datetime(2026, 1, 20, 14, 30, tzinfo=timezone.utc)
    end_dt = datetime(2026, 1, 20, 14, 31, tzinfo=timezone.utc)

    book_map, _ = engine.compute_book_pressure("MU", start_dt, end_dt)
    assert len(book_map) == 1

    snapshot = next(iter(book_map.values()))
    assert abs(float(snapshot["book_pressure"])) < 0.25


def test_enriched_feature_map_includes_l2_quality_flags_payload() -> None:
    df = _make_df(
        [
            {
                "ts": "2026-01-20T14:30:05Z",
                "action": "T",
                "side": "B",
                "size": 100.0,
                "price": 100.0,
                "bid_sz_00": 120.0,
                "ask_sz_00": 100.0,
            }
        ]
    )
    engine = OrderFlowEngine(manager=_StubL2Manager(df))
    start_dt = datetime(2026, 1, 20, 14, 30, tzinfo=timezone.utc)
    end_dt = datetime(2026, 1, 20, 14, 35, tzinfo=timezone.utc)

    feature_map, _ = engine.build_enriched_feature_map("MU", start_dt, end_dt)
    assert len(feature_map) == 1
    minute_key, features = next(iter(feature_map.items()))
    assert isinstance(minute_key, int)

    flags = features.get("l2_quality_flags")
    quality = features.get("l2_quality")

    assert isinstance(flags, list)
    assert "LOW_COVERAGE" in flags
    assert isinstance(quality, dict)
    assert quality.get("flags") == flags


def test_enriched_feature_map_loads_l2_chunk_once() -> None:
    df = _make_df(
        [
            {
                "ts": "2026-01-20T14:30:05Z",
                "action": "T",
                "side": "B",
                "size": 100.0,
                "price": 100.0,
                "bid_sz_00": 120.0,
                "ask_sz_00": 100.0,
            },
            {
                "ts": "2026-01-20T14:31:05Z",
                "action": "T",
                "side": "A",
                "size": 40.0,
                "price": 99.8,
                "bid_sz_00": 110.0,
                "ask_sz_00": 130.0,
            },
        ]
    )
    manager = _CountingStubL2Manager(df)
    engine = OrderFlowEngine(manager=manager)
    start_dt = datetime(2026, 1, 20, 14, 30, tzinfo=timezone.utc)
    end_dt = datetime(2026, 1, 20, 14, 35, tzinfo=timezone.utc)

    feature_map, _ = engine.build_enriched_feature_map("MU", start_dt, end_dt)
    assert feature_map
    assert manager.load_calls == 1
