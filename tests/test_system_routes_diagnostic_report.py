from __future__ import annotations

import json
import os
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.routes import system_routes


def _build_client(monkeypatch, tmp_path, *, state_setup=None):
    app = FastAPI()
    app.include_router(system_routes.router)
    monkeypatch.setattr(system_routes, "_project_root", lambda: tmp_path)
    if callable(state_setup):
        state_setup(app)
    return TestClient(app)


def _write_session_summary(tmp_path, folder_name: str, payload: dict) -> None:
    report_dir = tmp_path / "reports" / folder_name
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "session_summary.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )


def test_get_diagnostic_report_returns_payload(monkeypatch, tmp_path):
    report_dir = tmp_path / "reports" / "mu_diagnostic"
    report_dir.mkdir(parents=True, exist_ok=True)
    payload = {"phase": 0, "status": "ok", "day_results": [{"date": "2025-11-03"}]}
    (report_dir / "phase0_diagnostic.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )

    client = _build_client(monkeypatch, tmp_path)
    response = client.get("/api/reports/diagnostic/MU")

    assert response.status_code == 200
    assert response.json() == payload


def test_get_diagnostic_report_returns_404_when_missing(monkeypatch, tmp_path):
    client = _build_client(monkeypatch, tmp_path)

    response = client.get("/api/reports/diagnostic/MU")

    assert response.status_code == 404
    assert "phase0_diagnostic.json" in response.json()["detail"]


def test_get_diagnostic_report_rejects_invalid_ticker(monkeypatch, tmp_path):
    client = _build_client(monkeypatch, tmp_path)

    response = client.get("/api/reports/diagnostic/MU..")

    assert response.status_code == 400
    assert "Invalid ticker" in response.json()["detail"]


def test_get_diagnostic_report_rejects_invalid_json(monkeypatch, tmp_path):
    report_dir = tmp_path / "reports" / "mu_diagnostic"
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "phase0_diagnostic.json").write_text(
        "{invalid json}", encoding="utf-8"
    )

    client = _build_client(monkeypatch, tmp_path)
    response = client.get("/api/reports/diagnostic/MU")

    assert response.status_code == 500
    assert "not valid JSON" in response.json()["detail"]


def test_get_diagnostic_report_summary_only(monkeypatch, tmp_path):
    report_dir = tmp_path / "reports" / "mu_diagnostic"
    report_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "phase": 0,
        "status": "ok",
        "day_results": [{"date": "2025-11-03"}, {"date": "2025-11-04"}],
        "details": {"foo": "bar"},
    }
    (report_dir / "phase0_diagnostic.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )

    client = _build_client(monkeypatch, tmp_path)
    response = client.get("/api/reports/diagnostic/MU?summary_only=true")

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "diagnostic_summary"
    assert body["ticker"] == "MU"
    assert body["profile"] == "diagnostic"
    assert body["phase"] == 0
    assert body["day_results_count"] == 2
    assert "day_results" in body["keys"]


def test_get_diagnostic_report_uses_cache_when_file_unchanged(monkeypatch, tmp_path):
    class _StubStore:
        def __init__(self):
            self.cache = {}

        def diagnostic_cache_key(self, *, ticker, profile, phase):
            return f"{ticker}:{profile}:{phase}"

        def get_diagnostic_payload_cache(
            self, *, cache_key, source_path, source_mtime_ns
        ):
            item = self.cache.get((cache_key, source_path, source_mtime_ns))
            return item

        def upsert_diagnostic_payload_cache(
            self,
            *,
            cache_key,
            ticker,
            profile,
            phase,
            source_path,
            source_mtime_ns,
            payload,
        ):
            self.cache[(cache_key, source_path, source_mtime_ns)] = payload
            return {"cache_key": cache_key}

    report_dir = tmp_path / "reports" / "mu_diagnostic"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_file = report_dir / "phase0_diagnostic.json"
    payload = {"phase": 0, "status": "ok", "day_results": [{"date": "2025-11-03"}]}
    report_file.write_text(json.dumps(payload), encoding="utf-8")

    stub_store = _StubStore()
    client = _build_client(
        monkeypatch,
        tmp_path,
        state_setup=lambda app: setattr(
            app.state, "v2_services", SimpleNamespace(store=stub_store)
        ),
    )

    first = client.get("/api/reports/diagnostic/MU")
    assert first.status_code == 200
    assert first.json() == payload

    original_stat = report_file.stat()
    report_file.write_text("{invalid json", encoding="utf-8")
    os.utime(report_file, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))

    second = client.get("/api/reports/diagnostic/MU")
    assert second.status_code == 200
    assert second.json() == payload

    bypass = client.get("/api/reports/diagnostic/MU?refresh_cache=true")
    assert bypass.status_code == 500


def test_get_saved_run_history_aggregates_days_and_reasons(monkeypatch, tmp_path):
    _write_session_summary(
        tmp_path,
        "20260214_100000_MU_backtest-a",
        {
            "run_id": "backtest-a",
            "ticker": "MU",
            "date": "2026-02-03_to_2026-02-04",
            "processed_bars": 200,
            "total_bars": 200,
            "session_summary": {
                "total_trades": 2,
                "total_pnl_pct": 0.8,
                "total_pnl_dollars": 8.0,
                "trades": [
                    {
                        "trade_id": 1,
                        "strategy": "AdaptiveCore",
                        "side": "long",
                        "entry_time": "2026-02-03T14:30:00+00:00",
                        "exit_time": "2026-02-03T14:42:00+00:00",
                        "pnl_pct": 1.2,
                        "pnl_dollars": 12.0,
                        "bars_held": 13,
                        "exit_reason": "take_profit",
                    },
                    {
                        "trade_id": 2,
                        "strategy": "AdaptiveCore",
                        "side": "short",
                        "entry_time": "2026-02-04T15:10:00+00:00",
                        "exit_time": "2026-02-04T15:22:00+00:00",
                        "pnl_pct": -0.4,
                        "pnl_dollars": -4.0,
                        "bars_held": 13,
                        "exit_reason": "stop_loss",
                    },
                ],
            },
            "markers": [
                {
                    "marker_type": "entry_executed",
                    "timestamp": "2026-02-03T14:30:00+00:00",
                    "details": {"reasoning": "L2 breakout confirmation"},
                },
                {
                    "marker_type": "signal_generated",
                    "timestamp": "2026-02-03T14:29:00+00:00",
                    "strategy": "AdaptiveCore",
                },
                {
                    "marker_type": "regime_detected",
                    "timestamp": "2026-02-03T14:25:00+00:00",
                },
                {
                    "marker_type": "entry_executed",
                    "timestamp": "2026-02-04T15:10:00+00:00",
                    "details": {"reasoning": "Adaptive trend continuation"},
                },
                {
                    "marker_type": "signal_generated",
                    "timestamp": "2026-02-04T15:09:00+00:00",
                    "strategy": "AdaptiveCore",
                },
                {
                    "marker_type": "regime_detected",
                    "timestamp": "2026-02-04T15:00:00+00:00",
                },
            ],
            "aos_applied": {
                "adaptive_profile": {
                    "active_profile_id": "c4bb2197e651",
                    "profile_name": "c4 adaptive",
                }
            },
            "execution_config": {"active_adaptive_tuner_profile_id": "c4bb2197e651"},
        },
    )

    client = _build_client(monkeypatch, tmp_path)
    response = client.get("/api/reports/history/MU")
    assert response.status_code == 200

    payload = response.json()
    assert payload["source"] == "saved_run_history"
    assert payload["source_mode"] == "filesystem_reports"
    assert payload["source_path_hint"] == "reports/*/session_summary.json"
    assert payload["ticker"] == "MU"
    assert payload["split"]["start"] == "2026-02-03"
    assert payload["split"]["end"] == "2026-02-04"
    assert payload["metrics"]["total_trades"] == 2

    day_a = next(
        item for item in payload["day_results"] if item["date"] == "2026-02-03"
    )
    assert day_a["total_trades"] == 1
    assert day_a["signals"] == 1
    assert day_a["regime_evaluations"] == 1
    assert day_a["adaptive_profile_id"] == "c4bb2197e651"
    assert day_a["trade_details"][0]["entry_reason"] == "L2 breakout confirmation"
    assert day_a["trade_details"][0]["exit_reason"] == "take_profit"
    assert day_a["runs"][0]["run_total_trades"] == 2
    assert day_a["runs"][0]["run_total_pnl_pct"] == 0.8
    assert day_a["runs"][0]["run_total_pnl_dollars"] == 8.0
    assert day_a["runs"][0]["run_processed_bars"] == 200
    assert day_a["runs"][0]["run_total_bars"] == 200
    assert day_a["runs"][0]["run_signals"] == 2
    assert day_a["runs"][0]["run_regime_evaluations"] == 2
    assert day_a["runs"][0]["profile_match_mode"] is None

    day_b = next(
        item for item in payload["day_results"] if item["date"] == "2026-02-04"
    )
    assert day_b["total_trades"] == 1
    assert day_b["signals"] == 1
    assert day_b["regime_evaluations"] == 1
    assert day_b["trade_details"][0]["entry_reason"] == "Adaptive trend continuation"
    assert day_b["trade_details"][0]["exit_reason"] == "stop_loss"
    assert any(
        option["run_id"] == "backtest-a"
        for option in payload["filter_options"]["run_ids"]
    )
    assert any(
        option["profile_id"] == "c4bb2197e651"
        for option in payload["filter_options"]["adaptive_profiles"]
    )
    assert any(
        option["profile_id"] == "c4bb2197e651"
        for option in payload["filter_options"]["unified_profiles"]
    )


def test_get_saved_run_history_filters_by_profile_exact_only(monkeypatch, tmp_path):
    _write_session_summary(
        tmp_path,
        "20260214_100000_MU_diag-c4-legacy",
        {
            "run_id": "diag-c4-legacy",
            "ticker": "MU",
            "date": "2026-02-05",
            "session_summary": {
                "total_trades": 1,
                "trades": [
                    {
                        "trade_id": 9,
                        "strategy": "adaptive",
                        "side": "long",
                        "entry_time": "2026-02-05T14:30:00+00:00",
                        "exit_time": "2026-02-05T14:35:00+00:00",
                        "pnl_pct": 0.5,
                        "pnl_dollars": 5.0,
                        "bars_held": 6,
                    }
                ],
            },
            "markers": [],
        },
    )
    _write_session_summary(
        tmp_path,
        "20260214_101000_MU_exact",
        {
            "run_id": "diag-exact",
            "ticker": "MU",
            "date": "2026-02-06",
            "session_summary": {
                "total_trades": 1,
                "trades": [
                    {
                        "trade_id": 10,
                        "strategy": "adaptive",
                        "side": "short",
                        "entry_time": "2026-02-06T14:30:00+00:00",
                        "exit_time": "2026-02-06T14:35:00+00:00",
                        "pnl_pct": 0.25,
                        "pnl_dollars": 2.5,
                        "bars_held": 6,
                    }
                ],
            },
            "markers": [],
            "adaptive_profile_id": "c4bb2197e651",
        },
    )
    _write_session_summary(
        tmp_path,
        "20260214_102000_MU_other",
        {
            "run_id": "diag-other",
            "ticker": "MU",
            "date": "2026-02-07",
            "session_summary": {"total_trades": 1, "trades": []},
            "markers": [],
            "adaptive_profile_id": "different-profile",
        },
    )

    client = _build_client(monkeypatch, tmp_path)
    response = client.get("/api/reports/history/MU?adaptive_profile_id=c4bb2197e651")
    assert response.status_code == 200
    payload = response.json()

    result_days = [item["date"] for item in payload["day_results"]]
    assert result_days == ["2026-02-06"]

    day_exact = next(
        item for item in payload["day_results"] if item["date"] == "2026-02-06"
    )
    assert day_exact["runs"][0]["profile_match_mode"] == "exact"
    assert day_exact["adaptive_profile_id"] == "c4bb2197e651"


def test_get_saved_run_history_ignores_placeholder_profile_tokens(
    monkeypatch, tmp_path
):
    _write_session_summary(
        tmp_path,
        "20260214_103000_MU_placeholder-profile",
        {
            "run_id": "placeholder-profile",
            "ticker": "MU",
            "date": "2026-02-08",
            "session_summary": {
                "total_trades": 1,
                "trades": [
                    {
                        "trade_id": 21,
                        "strategy": "adaptive",
                        "side": "long",
                        "entry_time": "2026-02-08T14:30:00+00:00",
                        "exit_time": "2026-02-08T14:35:00+00:00",
                        "pnl_pct": 0.35,
                        "pnl_dollars": 3.5,
                        "bars_held": 5,
                    }
                ],
            },
            "markers": [],
            "report_metadata": {
                "adaptive_profile_id": "None",
                "adaptive_profile_name": "None",
            },
            "aos_applied": {
                "adaptive_profile": {
                    "active_profile_id": "None",
                    "profile_name": "None",
                }
            },
            "execution_config": {
                "active_adaptive_tuner_profile_id": "c4bb2197e651",
            },
        },
    )

    client = _build_client(monkeypatch, tmp_path)
    response = client.get("/api/reports/history/MU")
    assert response.status_code == 200
    payload = response.json()

    assert [item["date"] for item in payload["day_results"]] == ["2026-02-08"]
    row = payload["day_results"][0]
    assert row["adaptive_profile_id"] == "c4bb2197e651"
    assert row["runs"][0]["adaptive_profile_id"] == "c4bb2197e651"
    assert row["runs"][0]["profile_match_mode"] is None


def test_get_saved_run_history_filters_by_unified_profile_id(monkeypatch, tmp_path):
    _write_session_summary(
        tmp_path,
        "20260214_100000_MU_unified-a",
        {
            "run_id": "unified-a",
            "ticker": "MU",
            "date": "2026-02-08",
            "session_summary": {
                "total_trades": 1,
                "trades": [
                    {
                        "trade_id": 11,
                        "strategy": "adaptive",
                        "side": "long",
                        "entry_time": "2026-02-08T14:30:00+00:00",
                        "exit_time": "2026-02-08T14:35:00+00:00",
                        "pnl_pct": 0.4,
                        "pnl_dollars": 4.0,
                        "bars_held": 4,
                    }
                ],
            },
            "markers": [],
            "report_metadata": {
                "unified_profile_id": "unified-alpha",
                "unified_profile_name": "Unified Alpha",
            },
        },
    )
    _write_session_summary(
        tmp_path,
        "20260214_101000_MU_unified-b",
        {
            "run_id": "unified-b",
            "ticker": "MU",
            "date": "2026-02-09",
            "session_summary": {
                "total_trades": 1,
                "trades": [
                    {
                        "trade_id": 12,
                        "strategy": "adaptive",
                        "side": "short",
                        "entry_time": "2026-02-09T14:30:00+00:00",
                        "exit_time": "2026-02-09T14:35:00+00:00",
                        "pnl_pct": -0.2,
                        "pnl_dollars": -2.0,
                        "bars_held": 5,
                    }
                ],
            },
            "markers": [],
            "report_metadata": {
                "unified_profile_id": "unified-beta",
                "unified_profile_name": "Unified Beta",
            },
        },
    )

    client = _build_client(monkeypatch, tmp_path)
    response = client.get("/api/reports/history/MU?unified_profile_id=unified-alpha")
    assert response.status_code == 200
    payload = response.json()

    assert [item["date"] for item in payload["day_results"]] == ["2026-02-08"]
    assert payload["day_results"][0]["unified_profile_id"] == "unified-alpha"
    assert payload["day_results"][0]["runs"][0]["profile_match_mode"] == "exact"


def test_get_saved_run_history_excludes_zero_trade_reports(monkeypatch, tmp_path):
    _write_session_summary(
        tmp_path,
        "20260214_100000_MU_diag-c4-empty",
        {
            "run_id": "diag-c4-empty",
            "ticker": "MU",
            "date": "2026-02-03_to_2026-02-05",
            "session_summary": {"total_trades": 0, "trades": []},
            "markers": [],
        },
    )

    client = _build_client(monkeypatch, tmp_path)
    response = client.get("/api/reports/history/MU?adaptive_profile_id=c4bb2197e651")
    assert response.status_code == 200

    payload = response.json()
    assert payload["matched_reports"] == 0
    assert payload["day_results"] == []
    assert all(
        item["run_id"] != "diag-c4-empty"
        for item in payload["filter_options"]["run_ids"]
    )


def test_get_saved_run_history_can_include_zero_trade_reports(monkeypatch, tmp_path):
    _write_session_summary(
        tmp_path,
        "20260214_100000_MU_diag-c4-empty",
        {
            "run_id": "diag-c4-empty",
            "ticker": "MU",
            "date": "2026-02-03",
            "session_summary": {"total_trades": 0, "trades": []},
            "markers": [],
        },
    )

    client = _build_client(monkeypatch, tmp_path)
    response = client.get("/api/reports/history/MU?include_zero_trade_runs=true")
    assert response.status_code == 200

    payload = response.json()
    assert payload["matched_reports"] == 1
    assert [item["date"] for item in payload["day_results"]] == ["2026-02-03"]
    assert payload["day_results"][0]["total_trades"] == 0
    assert any(
        item["run_id"] == "diag-c4-empty"
        for item in payload["filter_options"]["run_ids"]
    )


def test_get_saved_run_history_filters_by_exact_run_id(monkeypatch, tmp_path):
    _write_session_summary(
        tmp_path,
        "20260214_100000_MU_run-a",
        {
            "run_id": "run-a",
            "ticker": "MU",
            "date": "2026-02-03",
            "session_summary": {"total_trades": 1, "trades": []},
            "markers": [],
        },
    )
    _write_session_summary(
        tmp_path,
        "20260214_101000_MU_run-b",
        {
            "run_id": "run-b",
            "ticker": "MU",
            "date": "2026-02-04",
            "session_summary": {"total_trades": 1, "trades": []},
            "markers": [],
        },
    )

    client = _build_client(monkeypatch, tmp_path)
    response = client.get("/api/reports/history/MU?run_id=run-b")
    assert response.status_code == 200

    payload = response.json()
    assert payload["matched_reports"] == 1
    assert [item["date"] for item in payload["day_results"]] == ["2026-02-04"]
    assert payload["day_results"][0]["runs"][0]["run_id"] == "run-b"


def test_get_saved_run_history_includes_aos_profile_options(monkeypatch, tmp_path):
    aos_dir = tmp_path / "aos_optimization"
    aos_dir.mkdir(parents=True, exist_ok=True)
    aos_payload = {
        "tickers": {
            "MU": {
                "active_adaptive_tuner_profile_id": "c4bb2197e651",
                "adaptive_tuner_profiles": [
                    {
                        "profile_id": "c4bb2197e651",
                        "created_at": "2026-02-11T04:43:39.570688Z",
                    },
                    {
                        "profile_id": "other-profile",
                        "created_at": "2026-02-10T04:43:39.570688Z",
                    },
                ],
            }
        }
    }
    (aos_dir / "aos_config.json").write_text(json.dumps(aos_payload), encoding="utf-8")

    _write_session_summary(
        tmp_path,
        "20260214_100000_MU_run-1",
        {
            "run_id": "run-1",
            "ticker": "MU",
            "date": "2026-02-03",
            "session_summary": {"total_trades": 0, "trades": []},
            "markers": [],
        },
    )

    client = _build_client(monkeypatch, tmp_path)
    response = client.get("/api/reports/history/MU")
    assert response.status_code == 200
    payload = response.json()

    profiles = payload["filter_options"]["adaptive_profiles"]
    c4_profile = next(item for item in profiles if item["profile_id"] == "c4bb2197e651")
    assert c4_profile["active"] is True
    assert "aos_config" in str(c4_profile.get("source"))


def test_get_saved_run_history_does_not_profile_match_legacy_reports(
    monkeypatch, tmp_path
):
    aos_dir = tmp_path / "aos_optimization"
    aos_dir.mkdir(parents=True, exist_ok=True)
    aos_payload = {
        "tickers": {
            "MU": {
                "adaptive_tuner_profiles": [
                    {
                        "profile_id": "c4f39c534169",
                        "candidate": {
                            "enabled_strategies": ["momentum_flow"],
                            "regime_strategy_map": None,
                        },
                    }
                ]
            }
        }
    }
    (aos_dir / "aos_config.json").write_text(json.dumps(aos_payload), encoding="utf-8")

    _write_session_summary(
        tmp_path,
        "20260214_100000_MU_legacy-momentum",
        {
            "run_id": "legacy-momentum",
            "ticker": "MU",
            "date": "2026-02-03",
            "session_summary": {
                "total_trades": 1,
                "trades": [
                    {
                        "trade_id": 1,
                        "strategy": "Momentum",
                        "side": "long",
                        "entry_time": "2026-02-03T14:30:00+00:00",
                        "exit_time": "2026-02-03T14:45:00+00:00",
                        "pnl_pct": 1.5,
                        "pnl_dollars": 15.0,
                    }
                ],
            },
            "markers": [],
        },
    )

    client = _build_client(monkeypatch, tmp_path)
    response = client.get("/api/reports/history/MU?adaptive_profile_id=c4f39c534169")
    assert response.status_code == 200
    payload = response.json()

    assert payload["matched_reports"] == 0
    assert payload["day_results"] == []


def test_get_saved_run_history_returns_empty_when_reports_dir_missing(
    monkeypatch, tmp_path
):
    client = _build_client(monkeypatch, tmp_path)
    response = client.get("/api/reports/history/MU")
    assert response.status_code == 200
    payload = response.json()
    assert payload["matched_reports"] == 0
    assert payload["day_results"] == []


def test_get_saved_run_history_reads_external_report_store(monkeypatch, tmp_path):
    class _StubRunReportsStore:
        def list_run_summaries(self, *, limit=300):
            _ = limit
            return [
                {
                    "run_key": "supabase-run:MU:2026-02-11",
                    "updated_at": "2026-02-14T10:00:00Z",
                    "summary": {
                        "run_id": "supabase-run",
                        "ticker": "MU",
                        "date": "2026-02-11",
                        "session_summary": {
                            "total_trades": 1,
                            "trades": [
                                {
                                    "trade_id": 1,
                                    "strategy": "AdaptiveCore",
                                    "side": "long",
                                    "entry_time": "2026-02-11T14:30:00+00:00",
                                    "exit_time": "2026-02-11T14:35:00+00:00",
                                    "pnl_pct": 0.2,
                                    "pnl_dollars": 2.0,
                                    "bars_held": 5,
                                }
                            ],
                        },
                        "markers": [],
                    },
                }
            ]

    client = _build_client(
        monkeypatch,
        tmp_path,
        state_setup=lambda app: setattr(
            app.state, "run_reports_store", _StubRunReportsStore()
        ),
    )
    response = client.get("/api/reports/history/MU")
    assert response.status_code == 200
    payload = response.json()
    assert payload["source_mode"] == "run_reports_store"
    assert payload["source_path_hint"] == "run_reports_store"
    assert payload["matched_reports"] == 1
    assert [item["date"] for item in payload["day_results"]] == ["2026-02-11"]
    assert payload["filter_options"]["run_ids"][0]["run_id"] == "supabase-run"


def test_get_saved_run_history_store_mode_does_not_fallback_to_filesystem(
    monkeypatch, tmp_path
):
    _write_session_summary(
        tmp_path,
        "20260214_100000_MU_filesystem-only",
        {
            "run_id": "filesystem-only",
            "ticker": "MU",
            "date": "2026-02-11",
            "session_summary": {
                "total_trades": 1,
                "trades": [
                    {
                        "trade_id": 1,
                        "strategy": "AdaptiveCore",
                        "side": "long",
                        "entry_time": "2026-02-11T14:30:00+00:00",
                        "exit_time": "2026-02-11T14:35:00+00:00",
                        "pnl_pct": 0.2,
                        "pnl_dollars": 2.0,
                        "bars_held": 5,
                    }
                ],
            },
            "markers": [],
        },
    )

    class _EmptyStore:
        def list_run_summaries(self, *, limit=300):
            _ = limit
            return []

    client = _build_client(
        monkeypatch,
        tmp_path,
        state_setup=lambda app: setattr(app.state, "run_reports_store", _EmptyStore()),
    )
    response = client.get("/api/reports/history/MU")
    assert response.status_code == 200
    payload = response.json()
    assert payload["source_mode"] == "run_reports_store"
    assert payload["source_path_hint"] == "run_reports_store"
    assert payload["matched_reports"] == 0
    assert payload["day_results"] == []


def test_get_saved_run_history_rejects_invalid_ticker(monkeypatch, tmp_path):
    client = _build_client(monkeypatch, tmp_path)
    response = client.get("/api/reports/history/MU..")
    assert response.status_code == 400
    assert "Invalid ticker" in response.json()["detail"]
