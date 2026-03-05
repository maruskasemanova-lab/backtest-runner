from __future__ import annotations

import base64
import gzip
import json
from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.routes import system_routes


def _fixture_report_updated_at(folder_name: str) -> str | None:
    token = str(folder_name or "").strip()
    if len(token) < 15:
        return None
    try:
        parsed = datetime.strptime(token[:15], "%Y%m%d_%H%M%S")
    except ValueError:
        return None
    return parsed.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


class _FixtureRunReportsStore:
    def __init__(self, root):
        self._root = root

    def list_run_summaries(self, *, limit=300):
        query_limit = max(1, min(int(limit or 300), 5000))
        reports_root = self._root / "reports"
        if not reports_root.exists():
            return []

        rows = []
        report_files = sorted(
            reports_root.glob("*/session_summary.json"),
            key=lambda path: path.parent.name,
            reverse=True,
        )
        for report_file in report_files[:query_limit]:
            try:
                payload = json.loads(report_file.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(payload, dict):
                continue
            run_id = str(payload.get("run_id") or "").strip()
            ticker = str(payload.get("ticker") or "").strip()
            date_label = str(payload.get("date") or "").strip()
            run_key = (
                f"{run_id}:{ticker}:{date_label}"
                if run_id and ticker and date_label
                else report_file.parent.name
            )
            rows.append(
                {
                    "run_key": run_key,
                    "updated_at": _fixture_report_updated_at(report_file.parent.name),
                    "summary": payload,
                }
            )
        return rows


def _derive_run_key_from_payload(payload: dict) -> str:
    run_id = str(payload.get("run_id") or "").strip()
    ticker = str(payload.get("ticker") or "").strip().upper()
    date_label = str(payload.get("date") or "").strip()
    if run_id and ticker and date_label:
        return f"{run_id}:{ticker}:{date_label}"
    return ""


def _fixture_playback_snapshot_payload(
    *,
    run_key: str,
    bars: list[dict],
    markers: list[dict],
) -> dict:
    raw_payload = {
        "schema_version": 1,
        "run_key": run_key,
        "created_at": "2026-02-26T00:00:00Z",
        "bars": bars,
        "markers": markers,
    }
    encoded = json.dumps(raw_payload, separators=(",", ":")).encode("utf-8")
    compressed = gzip.compress(encoded, compresslevel=6)
    return {
        "schema_version": 1,
        "encoding": "gzip+base64",
        "bars_count": len(bars),
        "markers_count": len(markers),
        "payload_b64": base64.b64encode(compressed).decode("ascii"),
        "uncompressed_bytes": len(encoded),
        "compressed_bytes": len(compressed),
        "skip_reason": None,
    }


def _modernize_summary_payload(payload: dict) -> dict:
    normalized = dict(payload)
    if normalized.pop("__legacy_persisted_artifact__", False):
        return normalized

    run_key = _derive_run_key_from_payload(normalized)
    if not run_key:
        return normalized

    date_label = str(normalized.get("date") or "").strip()
    ticker = str(normalized.get("ticker") or "").strip().upper()
    run_id = str(normalized.get("run_id") or "").strip()

    resolved_snapshot = (
        dict(normalized.get("resolved_config_snapshot"))
        if isinstance(normalized.get("resolved_config_snapshot"), dict)
        else {}
    )
    if not resolved_snapshot:
        resolved_snapshot = {
            "schema_version": 1,
            "run_id": run_id,
            "ticker": ticker,
            "date_label": date_label,
            "run_key": run_key,
        }
    if "run_key" not in resolved_snapshot:
        resolved_snapshot["run_key"] = run_key
    if "run_id" not in resolved_snapshot:
        resolved_snapshot["run_id"] = run_id
    if "ticker" not in resolved_snapshot:
        resolved_snapshot["ticker"] = ticker
    if "date_label" not in resolved_snapshot:
        resolved_snapshot["date_label"] = date_label
    for field in (
        "report_metadata",
        "control_plane_snapshot",
        "aos_applied",
        "execution_config",
        "run_request_config",
        "l2_applied",
    ):
        if field not in resolved_snapshot and isinstance(normalized.get(field), dict):
            resolved_snapshot[field] = dict(normalized.get(field))
    if not isinstance(resolved_snapshot.get("session_config_snapshot"), dict):
        resolved_snapshot["session_config_snapshot"] = {
            "regime_detection_minutes": 15,
            "strategy_selection_mode": "adaptive_top_n",
            "max_active_strategies": 3,
        }
    normalized["resolved_config_snapshot"] = resolved_snapshot

    if not isinstance(normalized.get("playback_snapshot"), dict):
        markers = (
            list(normalized.get("markers"))
            if isinstance(normalized.get("markers"), list)
            else []
        )
        session_summary = (
            normalized.get("session_summary", {})
            if isinstance(normalized.get("session_summary"), dict)
            else {}
        )
        trades = (
            session_summary.get("trades", [])
            if isinstance(session_summary.get("trades"), list)
            else []
        )
        timestamp = ""
        for marker in markers:
            if isinstance(marker, dict):
                timestamp = str(marker.get("timestamp") or "").strip()
                if timestamp:
                    break
        if not timestamp:
            for trade in trades:
                if not isinstance(trade, dict):
                    continue
                timestamp = str(
                    trade.get("entry_time") or trade.get("exit_time") or ""
                ).strip()
                if timestamp:
                    break
        if not timestamp:
            anchor = date_label.split("_to_", 1)[0] if "_to_" in date_label else date_label
            timestamp = f"{anchor}T14:30:00+00:00" if anchor else "2026-02-01T14:30:00+00:00"
        normalized["playback_snapshot"] = _fixture_playback_snapshot_payload(
            run_key=run_key,
            bars=[
                {
                    "timestamp": timestamp,
                    "open": 100.0,
                    "high": 100.0,
                    "low": 100.0,
                    "close": 100.0,
                    "volume": 1.0,
                }
            ],
            markers=markers,
        )

    return normalized


def _build_client(monkeypatch, tmp_path, *, state_setup=None):
    app = FastAPI()
    app.include_router(system_routes.router)
    monkeypatch.setattr(system_routes, "_project_root", lambda: tmp_path)
    if callable(state_setup):
        state_setup(app)
    if getattr(app.state, "run_reports_store", None) is None:
        app.state.run_reports_store = _FixtureRunReportsStore(tmp_path)
        app.state.run_reports_source_mode = "sqlite_run_reports"
    elif not getattr(app.state, "run_reports_source_mode", None):
        app.state.run_reports_source_mode = "run_reports_store"
    return TestClient(app)


def _write_session_summary(tmp_path, folder_name: str, payload: dict) -> None:
    report_dir = tmp_path / "reports" / folder_name
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "session_summary.json").write_text(
        json.dumps(_modernize_summary_payload(payload)), encoding="utf-8"
    )


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
    assert payload["source_mode"] == "sqlite_run_reports"
    assert payload["source_path_hint"] == "run_reports_store"
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
    assert day_a["runs"][0]["run_key"] == "backtest-a:MU:2026-02-03_to_2026-02-04"
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


def test_get_saved_run_history_includes_run_request_config_snapshot(
    monkeypatch, tmp_path
):
    _write_session_summary(
        tmp_path,
        "20260214_100000_MU_config-snapshot",
        {
            "run_id": "config-snapshot",
            "ticker": "MU",
            "date": "2026-02-10",
            "session_summary": {
                "total_trades": 1,
                "trades": [
                    {
                        "trade_id": 31,
                        "strategy": "AdaptiveCore",
                        "side": "long",
                        "entry_time": "2026-02-10T14:30:00+00:00",
                        "exit_time": "2026-02-10T14:35:00+00:00",
                        "pnl_pct": 0.2,
                        "pnl_dollars": 2.0,
                        "bars_held": 6,
                    }
                ],
            },
            "markers": [],
            "run_request_config": {
                "run_id": "config-snapshot",
                "ticker": "MU",
                "date": "2026-02-10",
                "trade_eval_mode": "intrabar_5s",
                "l2_confirm_enabled": True,
                "strategy_time_windows": {"momentum_flow": {"enabled": False}},
            },
        },
    )

    client = _build_client(monkeypatch, tmp_path)
    response = client.get("/api/reports/history/MU")
    assert response.status_code == 200
    payload = response.json()
    assert [item["date"] for item in payload["day_results"]] == ["2026-02-10"]

    day_row = payload["day_results"][0]
    assert day_row["run_request_config"]["trade_eval_mode"] == "intrabar_5s"
    assert day_row["run_request_config"]["l2_confirm_enabled"] is True

    run_row = day_row["runs"][0]
    assert run_row["run_request_config"]["trade_eval_mode"] == "intrabar_5s"
    assert run_row["run_request_config"]["strategy_time_windows"] == {
        "momentum_flow": {"enabled": False}
    }


def test_get_saved_run_history_prefers_resolved_config_snapshot(monkeypatch, tmp_path):
    _write_session_summary(
        tmp_path,
        "20260301_100000_MU_resolved-config",
        {
            "run_id": "resolved-config",
            "ticker": "MU",
            "date": "2026-02-11",
            "session_summary": {
                "total_trades": 1,
                "trades": [
                    {
                        "trade_id": 41,
                        "strategy": "AdaptiveCore",
                        "side": "long",
                        "entry_time": "2026-02-11T14:30:00+00:00",
                        "exit_time": "2026-02-11T14:36:00+00:00",
                        "pnl_pct": 0.3,
                        "pnl_dollars": 3.0,
                        "bars_held": 7,
                    }
                ],
            },
            "markers": [],
            "resolved_config_snapshot": {
                "schema_version": 1,
                "run_id": "resolved-config",
                "ticker": "MU",
                "date_label": "2026-02-11",
                "run_key": "resolved-config:MU:2026-02-11",
                "config_fingerprint": "cfg_exec123",
                "control_plane_snapshot": {
                    "config_fingerprint": "cfg_exec123",
                    "aos_applied_fingerprint": "cfg_aos456",
                },
                "report_metadata": {
                    "adaptive_profile_id": "adaptive-alpha",
                    "adaptive_profile_name": "Adaptive Alpha",
                    "config_fingerprint": "cfg_exec123",
                },
                "execution_config": {
                    "config_fingerprint": "cfg_exec123",
                    "trade_eval_mode": "intrabar_5s",
                },
                "run_request_config": {
                    "trade_eval_mode": "intrabar_5s",
                    "l2_confirm_enabled": True,
                },
                "aos_applied": {
                    "adaptive_profile": {
                        "active_profile_id": "adaptive-alpha",
                        "profile_name": "Adaptive Alpha",
                    }
                },
            },
        },
    )

    client = _build_client(monkeypatch, tmp_path)
    response = client.get("/api/reports/history/MU")
    assert response.status_code == 200
    payload = response.json()

    day_row = payload["day_results"][0]
    run_row = day_row["runs"][0]
    assert day_row["run_request_config"]["trade_eval_mode"] == "intrabar_5s"
    assert run_row["execution_config"]["trade_eval_mode"] == "intrabar_5s"
    assert run_row["control_plane_snapshot"]["config_fingerprint"] == "cfg_exec123"
    assert day_row["resolved_config_snapshot"]["config_fingerprint"] == "cfg_exec123"
    assert day_row["adaptive_profile_id"] == "adaptive-alpha"
    assert day_row["config_fingerprints"] == ["cfg_exec123"]


def test_get_saved_run_history_hydrates_externalized_resolved_config_snapshot(
    monkeypatch, tmp_path
):
    run_key = "resolved-store:MU:2026-02-11"

    class _SnapshotStore:
        def list_run_summaries(self, *, limit=300):
            _ = limit
            return [
                {
                    "run_key": run_key,
                    "updated_at": "2026-03-01T10:00:00Z",
                    "summary": {
                        "run_id": "resolved-store",
                        "ticker": "MU",
                        "date": "2026-02-11",
                        "session_summary": {
                            "total_trades": 1,
                            "trades": [
                                {
                                    "trade_id": 51,
                                    "strategy": "AdaptiveCore",
                                    "side": "long",
                                    "entry_time": "2026-02-11T14:30:00+00:00",
                                    "exit_time": "2026-02-11T14:36:00+00:00",
                                    "pnl_pct": 0.25,
                                    "pnl_dollars": 2.5,
                                    "bars_held": 6,
                                }
                            ],
                        },
                        "markers": [],
                        "resolved_config_snapshot_id": "rcs_test123",
                    },
                }
            ]

        def get_run_config_snapshot(self, *, snapshot_id=None, run_key=None):
            assert snapshot_id == "rcs_test123"
            assert run_key == "resolved-store:MU:2026-02-11"
            return {
                "snapshot_id": "rcs_test123",
                "run_key": run_key,
                "payload": {
                    "schema_version": 1,
                    "run_key": run_key,
                    "config_fingerprint": "cfg_exec123",
                    "report_metadata": {
                        "adaptive_profile_id": "adaptive-store",
                    },
                    "execution_config": {
                        "trade_eval_mode": "intrabar_5s",
                        "config_fingerprint": "cfg_exec123",
                    },
                    "run_request_config": {
                        "trade_eval_mode": "intrabar_5s",
                    },
                },
            }

    client = _build_client(
        monkeypatch,
        tmp_path,
        state_setup=lambda app: setattr(app.state, "run_reports_store", _SnapshotStore()),
    )
    response = client.get("/api/reports/history/MU")
    assert response.status_code == 200
    payload = response.json()

    day_row = payload["day_results"][0]
    run_row = day_row["runs"][0]
    assert run_row["resolved_config_snapshot_id"] == "rcs_test123"
    assert run_row["resolved_config_snapshot"]["config_fingerprint"] == "cfg_exec123"
    assert run_row["execution_config"]["trade_eval_mode"] == "intrabar_5s"
    assert day_row["adaptive_profile_id"] == "adaptive-store"


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
                    "summary": _modernize_summary_payload(
                        {
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
                        }
                    ),
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


def test_get_saved_run_history_includes_active_runner_summary(monkeypatch, tmp_path):
    active_summary = {
        "run_id": "analyzer-live",
        "ticker": "MU",
        "date": "2026-02-13_to_2026-02-13",
        "processed_bars": 12,
        "total_bars": 300,
        "session_summary": {
            "total_trades": 0,
            "trades": [],
        },
        "markers": [],
    }

    class _ActiveRunner:
        def get_summary(self):
            return dict(active_summary)

    def _state_setup(app):
        app.state.api_services = SimpleNamespace(
            active_runners={
                "analyzer-live:MU:2026-02-13_to_2026-02-13": _ActiveRunner()
            }
        )

    client = _build_client(monkeypatch, tmp_path, state_setup=_state_setup)
    response = client.get("/api/reports/history/MU?include_zero_trade_runs=true")
    assert response.status_code == 200
    payload = response.json()

    assert payload["matched_reports"] == 1
    assert [item["date"] for item in payload["day_results"]] == ["2026-02-13"]
    assert payload["day_results"][0]["runs"][0]["run_id"] == "analyzer-live"
    assert (
        payload["day_results"][0]["runs"][0]["run_key"]
        == "analyzer-live:MU:2026-02-13_to_2026-02-13"
    )
    assert payload["filter_options"]["run_ids"][0]["run_id"] == "analyzer-live"


def test_get_saved_run_history_dedupes_active_runner_when_store_has_same_run(
    monkeypatch, tmp_path
):
    shared_summary = {
        "run_id": "analyzer-live",
        "ticker": "MU",
        "date": "2026-02-11",
        "processed_bars": 25,
        "total_bars": 25,
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
    }

    class _StoreWithRun:
        def list_run_summaries(self, *, limit=300):
            _ = limit
            return [
                {
                    "run_key": "analyzer-live:MU:2026-02-11",
                    "updated_at": "2026-02-14T10:00:00Z",
                    "summary": dict(shared_summary),
                }
            ]

    class _ActiveRunner:
        def get_summary(self):
            return dict(shared_summary)

    def _state_setup(app):
        app.state.run_reports_store = _StoreWithRun()
        app.state.api_services = SimpleNamespace(
            active_runners={"analyzer-live:MU:2026-02-11": _ActiveRunner()}
        )

    client = _build_client(monkeypatch, tmp_path, state_setup=_state_setup)
    response = client.get("/api/reports/history/MU")
    assert response.status_code == 200
    payload = response.json()

    assert payload["matched_reports"] == 1
    assert [item["date"] for item in payload["day_results"]] == ["2026-02-11"]
    assert payload["day_results"][0]["report_count"] == 1
    assert len(payload["day_results"][0]["runs"]) == 1


def test_get_saved_run_history_rejects_invalid_ticker(monkeypatch, tmp_path):
    client = _build_client(monkeypatch, tmp_path)
    response = client.get("/api/reports/history/MU..")
    assert response.status_code == 400
    assert "Invalid ticker" in response.json()["detail"]


def _build_playback_snapshot_payload(*, run_key: str, bars: list[dict], markers: list[dict]) -> dict:
    raw_payload = {
        "schema_version": 1,
        "run_key": run_key,
        "created_at": "2026-02-26T00:00:00Z",
        "bars": bars,
        "markers": markers,
    }
    encoded = json.dumps(raw_payload, separators=(",", ":")).encode("utf-8")
    compressed = gzip.compress(encoded, compresslevel=6)
    return {
        "schema_version": 1,
        "encoding": "gzip+base64",
        "bars_count": len(bars),
        "markers_count": len(markers),
        "payload_b64": base64.b64encode(compressed).decode("ascii"),
        "uncompressed_bytes": len(encoded),
        "compressed_bytes": len(compressed),
        "skip_reason": None,
    }


def test_get_run_playback_snapshot_from_store(monkeypatch, tmp_path):
    run_key = "snapshot-run:MU:2026-02-13"
    bars = [
        {
            "timestamp": "2026-02-13T14:30:00+00:00",
            "open": 100.0,
            "high": 101.0,
            "low": 99.5,
            "close": 100.5,
            "volume": 1200.0,
            "bar_index": 0,
            "time": 1770993000,
        },
        {
            "timestamp": "2026-02-13T14:31:00+00:00",
            "open": 100.5,
            "high": 101.2,
            "low": 100.2,
            "close": 101.0,
            "volume": 900.0,
            "bar_index": 1,
            "time": 1770993060,
        },
    ]
    markers = [
        {
            "id": "m-1",
            "marker_type": "signal_generated",
            "timestamp": "2026-02-13T14:30:00+00:00",
            "strategy": "AdaptiveCore",
        }
    ]
    _write_session_summary(
        tmp_path,
        "20260214_100000_MU_snapshot-run",
        {
            "run_id": "snapshot-run",
            "ticker": "MU",
            "date": "2026-02-13",
            "phase": "COMPLETED",
            "processed_bars": 2,
            "total_bars": 2,
            "session_summary": {"total_trades": 1, "trades": []},
            "markers": markers,
            "playback_snapshot": _build_playback_snapshot_payload(
                run_key=run_key,
                bars=bars,
                markers=markers,
            ),
        },
    )

    client = _build_client(monkeypatch, tmp_path)
    response = client.get(f"/api/reports/run-snapshot?run_key={run_key}")
    assert response.status_code == 200
    payload = response.json()

    assert payload["run_key"] == run_key
    assert payload["source"] == "run_reports_store"
    assert payload["state"]["run_id"] == "snapshot-run"
    assert payload["state"]["ticker"] == "MU"
    assert payload["state"]["is_running"] is False
    assert payload["state"]["total_bars"] == 2
    assert len(payload["bars"]) == 2
    assert len(payload["markers"]) == 1
    assert payload["summary"]["playback_snapshot"]["encoding"] == "gzip+base64"
    assert "payload_b64" not in payload["summary"]["playback_snapshot"]


def test_get_run_playback_snapshot_hydrates_externalized_config_snapshot(
    monkeypatch, tmp_path
):
    run_key = "snapshot-store:MU:2026-02-13"
    bars = [
        {"timestamp": "2026-02-13T14:30:00+00:00", "close": 100.5},
        {"timestamp": "2026-02-13T14:31:00+00:00", "close": 101.0},
    ]
    markers = []

    class _SnapshotStore:
        def get_run_summary(self, *, run_key):
            assert run_key == "snapshot-store:MU:2026-02-13"
            return {
                "run_key": run_key,
                "updated_at": "2026-03-01T10:00:00Z",
                "summary": {
                    "run_id": "snapshot-store",
                    "ticker": "MU",
                    "date": "2026-02-13",
                    "phase": "COMPLETED",
                    "processed_bars": 2,
                    "total_bars": 2,
                    "session_summary": {"total_trades": 1, "trades": []},
                    "markers": markers,
                    "resolved_config_snapshot_id": "rcs_test123",
                    "playback_snapshot": _build_playback_snapshot_payload(
                        run_key=run_key,
                        bars=bars,
                        markers=markers,
                    ),
                },
            }

        def get_run_config_snapshot(self, *, snapshot_id=None, run_key=None):
            assert snapshot_id == "rcs_test123"
            assert run_key == "snapshot-store:MU:2026-02-13"
            return {
                "snapshot_id": "rcs_test123",
                "run_key": run_key,
                "payload": {
                    "schema_version": 1,
                    "run_key": run_key,
                    "config_fingerprint": "cfg_exec123",
                },
            }

    client = _build_client(
        monkeypatch,
        tmp_path,
        state_setup=lambda app: setattr(app.state, "run_reports_store", _SnapshotStore()),
    )
    response = client.get(f"/api/reports/run-snapshot?run_key={run_key}")
    assert response.status_code == 200
    payload = response.json()

    assert payload["summary"]["resolved_config_snapshot_id"] == "rcs_test123"
    assert payload["summary"]["resolved_config_snapshot"]["config_fingerprint"] == "cfg_exec123"


def test_get_run_playback_snapshot_without_payload_returns_404(monkeypatch, tmp_path):
    run_key = "no-snapshot:MU:2026-02-13"
    _write_session_summary(
        tmp_path,
        "20260214_100000_MU_no-snapshot",
        {
            "__legacy_persisted_artifact__": True,
            "run_id": "no-snapshot",
            "ticker": "MU",
            "date": "2026-02-13",
            "session_summary": {"total_trades": 0, "trades": []},
            "markers": [],
        },
    )

    client = _build_client(monkeypatch, tmp_path)
    response = client.get(f"/api/reports/run-snapshot?run_key={run_key}")
    assert response.status_code == 404
    assert "Legacy run artifacts are no longer supported" in response.json()["detail"]


def test_get_run_playback_snapshot_rejects_legacy_summary_without_resolved_snapshot(
    monkeypatch, tmp_path
):
    run_key = "legacy-no-config:MU:2026-02-13"
    _write_session_summary(
        tmp_path,
        "20260214_100000_MU_legacy-no-config",
        {
            "__legacy_persisted_artifact__": True,
            "run_id": "legacy-no-config",
            "ticker": "MU",
            "date": "2026-02-13",
            "phase": "COMPLETED",
            "processed_bars": 1,
            "total_bars": 1,
            "playback_snapshot": _build_playback_snapshot_payload(
                run_key=run_key,
                bars=[{"timestamp": "2026-02-13T14:30:00+00:00", "close": 100.0}],
                markers=[],
            ),
        },
    )

    client = _build_client(monkeypatch, tmp_path)
    response = client.get(f"/api/reports/run-snapshot?run_key={run_key}")
    assert response.status_code == 404
    assert "Legacy run artifacts are no longer supported" in response.json()["detail"]


def test_get_saved_run_history_skips_legacy_persisted_rows_without_modern_artifacts(
    monkeypatch, tmp_path
):
    _write_session_summary(
        tmp_path,
        "20260214_100000_MU_legacy-history",
        {
            "__legacy_persisted_artifact__": True,
            "run_id": "legacy-history",
            "ticker": "MU",
            "date": "2026-02-13",
            "processed_bars": 1,
            "total_bars": 1,
            "session_summary": {"total_trades": 1, "trades": []},
        },
    )

    client = _build_client(monkeypatch, tmp_path)
    response = client.get("/api/reports/history/MU")
    assert response.status_code == 200
    payload = response.json()

    assert payload["matched_reports"] == 0
    assert payload["skipped_invalid_reports"] >= 1
    assert payload["day_results"] == []
