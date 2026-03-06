import json

from src.services.run_reports_read.history_models import HistoryAccumulator, HistoryQuery
from src.services.run_reports_read.history_profile_options import (
    build_history_profile_options,
)
from src.services.run_reports_read.history_sources import process_history_payload


def test_build_history_profile_options_merges_history_and_aos_sources(tmp_path):
    aos_dir = tmp_path / "aos_optimization"
    aos_dir.mkdir(parents=True, exist_ok=True)
    (aos_dir / "aos_config.json").write_text(
        json.dumps(
            {
                "tickers": {
                    "MU": {
                        "active_unified_profile_id": "unified-live",
                        "unified_profiles": [
                            {
                                "profile_id": "unified-live",
                                "profile_name": "Live Profile",
                                "created_at": "2026-03-01T10:00:00Z",
                            }
                        ],
                        "active_adaptive_tuner_profile_id": "adaptive-live",
                        "adaptive_tuner_profiles": [
                            {
                                "profile_id": "adaptive-live",
                                "profile_name": "Adaptive Live",
                                "created_at": "2026-03-01T11:00:00Z",
                            }
                        ],
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    profile_options = build_history_profile_options(
        project_root=tmp_path,
        ticker="MU",
        history_profile_names={
            "unified-history": {"Unified History"},
            "adaptive-history": {"Adaptive History"},
        },
    )

    unified_ids = [item["profile_id"] for item in profile_options["unified_profiles"]]
    adaptive_ids = [item["profile_id"] for item in profile_options["adaptive_profiles"]]
    assert unified_ids[0] == "unified-live"
    assert adaptive_ids[0] == "adaptive-live"
    assert "unified-history" in unified_ids
    assert "adaptive-history" in adaptive_ids
    assert profile_options["unified_profiles"][0]["active"] is True
    assert profile_options["adaptive_profiles"][0]["active"] is True


def test_process_history_payload_deduplicates_identity_but_keeps_latest_saved_at():
    query = HistoryQuery(
        safe_ticker="MU",
        run_id_exact_filter="",
        run_id_contains_filter="",
        requested_profile_id="",
        include_multi_day=True,
        include_zero_trade_runs=True,
    )
    accumulator = HistoryAccumulator()
    payload = {
        "run_id": "diag-1",
        "ticker": "MU",
        "date": "2026-03-01",
        "session_summary": {"total_trades": 0, "trades": []},
        "execution_config": {"unified_profile_id": "unified-a"},
    }

    process_history_payload(
        accumulator=accumulator,
        query=query,
        payload=payload,
        report_dir_name="20260301_120000_MU_diag-1",
        report_saved_at="2026-03-01T12:00:00Z",
        run_key="diag-1:MU:2026-03-01",
    )
    process_history_payload(
        accumulator=accumulator,
        query=query,
        payload=payload,
        report_dir_name="20260301_130000_MU_diag-1",
        report_saved_at="2026-03-01T13:00:00Z",
        run_key="diag-1:MU:2026-03-01",
    )

    assert accumulator.matched_reports == 1
    assert len(accumulator.day_rows) == 1
    assert accumulator.run_latest_saved_at["diag-1"] == "2026-03-01T13:00:00+00:00"
    assert accumulator.history_profile_names["unified-a"] == set()
