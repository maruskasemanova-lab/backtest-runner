from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.l2_data_manager import L2DataManager
from src.l2_feature_service import L2FeatureService
from src.parquet_compat import write_parquet_compat


def test_build_feature_map_prefers_precomputed_features(
    tmp_path: Path,
    monkeypatch,
) -> None:
    precomputed_dir = tmp_path / "l2_precomputed"
    precomputed_dir.mkdir(parents=True, exist_ok=True)

    minute_keys = [
        int(datetime(2026, 2, 10, 14, 30, tzinfo=timezone.utc).timestamp() // 60),
        int(datetime(2026, 2, 10, 14, 31, tzinfo=timezone.utc).timestamp() // 60),
    ]
    precomputed = pd.DataFrame(
        {
            "minute_key": minute_keys,
            "l2_schema_version": ["l2fv-1.0", "l2fv-1.0"],
            "l2_delta": [15.0, -10.0],
            "l2_buy_volume": [120.0, 80.0],
            "l2_sell_volume": [105.0, 90.0],
            "l2_volume": [225.0, 170.0],
            "l2_imbalance": [0.066, -0.059],
            "l2_bid_depth_total": [5000.0, 4800.0],
            "l2_ask_depth_total": [4700.0, 4900.0],
            "l2_book_pressure": [0.031, -0.010],
            "l2_book_pressure_change": [0.0, -0.041],
            "l2_quality_trade_ticks": [12, 10],
            "l2_quality_book_updates": [40, 38],
            "l2_quality_coverage_ratio": [1.0, 1.0],
            "l2_iceberg_buy_count": [1.0, 0.0],
            "l2_iceberg_sell_count": [0.0, 2.0],
            "l2_iceberg_bias": [1.0, -2.0],
        }
    )
    write_parquet_compat(
        precomputed, precomputed_dir / "MU_2026-02-10.parquet", index=False
    )

    monkeypatch.setenv("BACKTEST_L2_PRECOMPUTED_FEATURES_ENABLED", "1")
    monkeypatch.setenv("BACKTEST_L2_PRECOMPUTED_DIR", str(precomputed_dir))

    manager = L2DataManager(data_dirs=[str(tmp_path / "missing_raw_l2")])

    def _unexpected_raw_load(*_args, **_kwargs):
        raise AssertionError("Raw load_data should not run when precomputed exists")

    monkeypatch.setattr(manager, "load_data", _unexpected_raw_load)

    service = L2FeatureService(
        manager=manager, logger=logging.getLogger("test-l2-precomputed")
    )
    feature_map, stats = service.build_feature_map(
        ticker="MU",
        start_dt_utc=datetime(2026, 2, 10, 14, 30, tzinfo=timezone.utc),
        end_dt_utc=datetime(2026, 2, 10, 14, 31, tzinfo=timezone.utc),
    )

    assert len(feature_map) == 2
    assert int(stats.get("covered_minutes", 0)) == 2
    assert bool(stats.get("has_l2")) is True
    assert str(stats.get("source")) == "precomputed"
    assert int(stats.get("trade_events", 0)) == 22
