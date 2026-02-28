from __future__ import annotations

from pathlib import Path

import pandas as pd

import src.tcbbo_analyzer as tcbbo_analyzer_module
from src.parquet_compat import write_parquet_compat
from src.tcbbo_analyzer import TCBBOAnalyzer, build_tcbbo_feature_map


def _occ_symbol(opt_type: str) -> str:
    return f"MU    260213{opt_type}00417500"


def test_tcbbo_analyzer_load_uses_projected_parquet_columns(
    tmp_path: Path,
    monkeypatch,
) -> None:
    parquet_path = tmp_path / "MU_OPRA_tcbbo_20260203_20260203.parquet"
    write_parquet_compat(
        pd.DataFrame(
            {
                "ts_event": [
                    "2026-02-03T14:30:00Z",
                    "2026-02-03T14:31:00Z",
                ],
                "symbol": [_occ_symbol("C"), _occ_symbol("P")],
                "price": [1.20, 1.10],
                "size": [10, 5],
                "bid_px_00": [1.00, 1.10],
                "ask_px_00": [1.20, None],
                "publisher_id": [7, 8],
                "ignored": ["a", "b"],
            }
        ),
        parquet_path,
        index=False,
    )

    calls: dict[str, list[str]] = {}
    original_reader = tcbbo_analyzer_module.read_parquet_compat

    def _capturing_reader(path, columns=None):
        calls["columns"] = list(columns or [])
        return original_reader(path, columns=columns)

    monkeypatch.setattr(tcbbo_analyzer_module, "read_parquet_compat", _capturing_reader)

    loaded = TCBBOAnalyzer().load(parquet_path)

    assert "ignored" not in calls["columns"]
    assert set(TCBBOAnalyzer._required_parquet_columns()).issubset(calls["columns"])
    assert len(loaded) == 1
    assert loaded["underlying"].iloc[0] == "MU"
    assert loaded["opt_type"].iloc[0] == "C"


def test_build_tcbbo_feature_map_preserves_minute_flow_output(tmp_path: Path) -> None:
    parquet_path = tmp_path / "MU_OPRA_tcbbo_20260203_20260203.parquet"
    write_parquet_compat(
        pd.DataFrame(
            {
                "ts_event": [
                    "2026-02-03T14:30:00Z",
                    "2026-02-03T14:30:30Z",
                ],
                "symbol": [_occ_symbol("C"), _occ_symbol("P")],
                "price": [1.20, 1.10],
                "size": [10, 5],
                "bid_px_00": [1.00, 1.10],
                "ask_px_00": [1.20, 1.30],
                "publisher_id": [1, 2],
            }
        ),
        parquet_path,
        index=False,
    )

    feature_map, stats = build_tcbbo_feature_map(parquet_path)

    assert len(feature_map) == 1
    only_key = next(iter(feature_map))
    assert only_key == "2026-02-03T14:30:00+00:00"
    assert feature_map[only_key]["tcbbo_trade_count"] == 2
    assert feature_map[only_key]["tcbbo_has_data"] is True
    assert feature_map[only_key]["tcbbo_net_premium"] == 1750.0
    assert stats["tcbbo_total_trades"] == 2
    assert stats["tcbbo_classified_trades"] == 2
    assert stats["tcbbo_minutes_covered"] == 1
