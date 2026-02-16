from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from src.l2_data_manager import L2DataManager


def _raw_l2_df_for_two_minutes() -> pd.DataFrame:
    base = datetime(2026, 2, 10, 15, 0, 0, tzinfo=timezone.utc)
    rows = []
    for minute in (0, 1):
        for second in (0, 5, 10, 20, 40, 55):
            ts = base.replace(minute=base.minute + minute, second=second)
            rows.append(
                {
                    "ts_event": ts,
                    "action": "M" if second % 2 == 0 else "T",
                    "price": 100.0 + minute * 0.1 + second * 0.001,
                    "size": 100 + second,
                    "side": "B",
                    "bid_px_00": 99.9 + minute * 0.1,
                    "ask_px_00": 100.1 + minute * 0.1,
                    "bid_sz_00": 500.0 + second,
                    "ask_sz_00": 520.0 + second,
                }
            )
    df = pd.DataFrame(rows)
    df = df.set_index(pd.to_datetime(df["ts_event"], utc=True))
    df = df.drop(columns=["ts_event"])
    return df


def test_intrabar_frames_reuse_runtime_cache(monkeypatch):
    manager = L2DataManager(data_dirs=["/tmp"])
    manager.intrabar_runtime_cache_enabled = True
    manager.intrabar_runtime_cache_max_tickers = 1

    raw_df = _raw_l2_df_for_two_minutes()
    calls = {"count": 0}

    def _fake_load_data(ticker, start_date, end_date):
        calls["count"] += 1
        return raw_df

    monkeypatch.setattr(manager, "load_data", _fake_load_data)

    m0_start = datetime(2026, 2, 10, 15, 0, 0, tzinfo=timezone.utc)
    m0_end = datetime(2026, 2, 10, 15, 0, 59, tzinfo=timezone.utc)
    m1_start = datetime(2026, 2, 10, 15, 1, 0, tzinfo=timezone.utc)
    m1_end = datetime(2026, 2, 10, 15, 1, 59, tzinfo=timezone.utc)

    first = manager.get_intrabar_frames("MU", m0_start, m0_end)
    second = manager.get_intrabar_frames("MU", m1_start, m1_end)

    assert calls["count"] == 1
    assert not first.empty
    assert not second.empty

