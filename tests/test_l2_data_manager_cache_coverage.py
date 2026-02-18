from __future__ import annotations

from pathlib import Path

import pandas as pd

import src.l2_data_manager as l2_data_manager_module
from src.l2_data_manager import L2DataManager
from src.parquet_compat import write_parquet_compat


def _write_mu_day_parquet(path: Path) -> None:
    rows = pd.DataFrame(
        {
            "ts_event": pd.to_datetime(
                [
                    "2026-02-10T09:00:00.123456Z",
                    "2026-02-10T16:00:00.654321Z",
                ],
                utc=True,
            ),
            "action": ["T", "A"],
            "side": ["B", "A"],
            "price": [100.25, 100.30],
            "size": [50.0, 70.0],
            "bid_px_00": [100.24, 100.29],
            "ask_px_00": [100.26, 100.31],
        }
    )
    write_parquet_compat(rows, path, index=False)


def test_load_data_reuses_cache_for_same_day_without_midnight_rows(
    tmp_path: Path,
    monkeypatch,
) -> None:
    l2_root = tmp_path / "l2"
    l2_root.mkdir(parents=True, exist_ok=True)
    day_file = l2_root / "MU_2026-02-10_2026-02-10.parquet"
    _write_mu_day_parquet(day_file)

    original_reader = l2_data_manager_module.read_parquet_compat
    calls = {"count": 0}

    def _counting_reader(*args, **kwargs):
        calls["count"] += 1
        return original_reader(*args, **kwargs)

    monkeypatch.setattr(l2_data_manager_module, "read_parquet_compat", _counting_reader)

    manager = L2DataManager(data_dirs=[str(l2_root)])
    manager.max_cached_tickers = 1
    manager.max_cached_rows = 1_000_000
    manager.max_cached_bytes = 64 * 1024 * 1024

    first = manager.load_data("MU", "2026-02-10", "2026-02-10")
    calls_after_first = calls["count"]
    second = manager.load_data("MU", "2026-02-10", "2026-02-10")

    assert first is not None
    assert second is not None
    assert len(first) == len(second) == 2
    assert calls_after_first >= 1
    assert calls["count"] == calls_after_first
