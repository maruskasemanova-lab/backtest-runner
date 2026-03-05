from __future__ import annotations

import asyncio
import base64
import gzip
import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from decision_tracker import MarkerType
from session_runner import RunConfig, SessionRunner
from src.services.run_control_service import (
    RunControlDeps,
    get_run_state,
    play_run,
    restore_run_snapshot,
)


class _Registry:
    def __init__(self, active_runners):
        self._active_runners = active_runners

    @staticmethod
    def build_key(run_id: str, ticker: str, date: str) -> str:
        return f"{run_id}:{ticker}:{date}"

    def require(self, run_id: str, ticker: str, date: str):
        run_key = self.build_key(run_id, ticker, date)
        runner = self._active_runners.get(run_key)
        if runner is None:
            raise HTTPException(status_code=404, detail=f"Run not found: {run_key}")
        return run_key, runner


def _playback_snapshot_payload(*, run_key: str, bars: list[dict], markers: list[dict]) -> dict:
    raw_payload = {
        "schema_version": 1,
        "run_key": run_key,
        "created_at": "2026-03-05T10:00:00Z",
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


class _Store:
    def __init__(self, *, summary: dict, resolved_snapshot: dict):
        self._summary = summary
        self._resolved_snapshot = resolved_snapshot

    def get_run_summary(self, *, run_key: str):
        return {
            "run_key": run_key,
            "updated_at": "2026-03-05T11:00:00Z",
            "summary": dict(self._summary),
        }

    def get_run_config_snapshot(self, *, snapshot_id=None, run_key=None):
        return {
            "snapshot_id": str(snapshot_id or "rcs_test123"),
            "run_key": str(run_key or ""),
            "payload": dict(self._resolved_snapshot),
        }


def _build_deps(active_runners: dict, *, store: _Store) -> RunControlDeps:
    async def _noop(*args, **kwargs):
        _ = args, kwargs
        return None

    return RunControlDeps(
        run_registry=_Registry(active_runners),
        active_runners=active_runners,
        marker_type_enum=MarkerType,
        logger=SimpleNamespace(error=lambda *args, **kwargs: None),
        save_remote_checkpoint=_noop,
        clear_remote_strategy_sessions=_noop,
        configure_session=_noop,
        run_reports_store=store,
        l2_manager=None,
        run_config_cls=RunConfig,
        session_runner_cls=SessionRunner,
    )


def test_restore_run_snapshot_hydrates_externalized_config_and_registers_runner():
    run_key = "snapshot-run:MU:2026-02-13"
    bars = [
        {
            "timestamp": "2026-02-13T14:30:00+00:00",
            "open": 100.0,
            "high": 101.0,
            "low": 99.5,
            "close": 100.5,
            "volume": 1200.0,
        },
        {
            "timestamp": "2026-02-13T14:31:00+00:00",
            "open": 100.5,
            "high": 101.2,
            "low": 100.2,
            "close": 101.0,
            "volume": 900.0,
        },
    ]
    markers = [
        {
            "id": "m-1",
            "marker_type": "signal_generated",
            "timestamp": "2026-02-13T14:30:00+00:00",
            "bar_index": 0,
            "title": "Signal: BUY",
            "description": "Adaptive breakout",
            "price": 100.5,
            "strategy": "AdaptiveCore",
            "details": {"signal_type": "BUY"},
        }
    ]
    resolved_snapshot = {
        "schema_version": 1,
        "run_key": run_key,
        "control_plane_snapshot": {"config_fingerprint": "cfg_exec123"},
        "execution_config": {
            "trade_eval_mode": "intrabar_5s",
            "intrabar_eval_step_seconds": 5,
            "account_size_usd": 25000.0,
        },
        "run_request_config": {
            "strategy_api_url": "http://localhost:8001",
            "date_from": "2026-02-13",
            "date_to": "2026-02-13",
            "account_size_usd": 25000.0,
        },
        "session_config_snapshot": {
            "regime_detection_minutes": 21,
            "strategy_selection_mode": "adaptive_top_n",
            "max_active_strategies": 3,
            "l2_confirm_enabled": False,
        },
    }
    summary = {
        "run_id": "snapshot-run",
        "ticker": "MU",
        "date": "2026-02-13",
        "phase": "COMPLETED",
        "processed_bars": 2,
        "total_bars": 2,
        "session_summary": {"total_trades": 1, "trades": []},
        "resolved_config_snapshot_id": "rcs_test123",
        "playback_snapshot": _playback_snapshot_payload(
            run_key=run_key,
            bars=bars,
            markers=markers,
        ),
    }
    active_runners = {}
    deps = _build_deps(
        active_runners,
        store=_Store(summary=summary, resolved_snapshot=resolved_snapshot),
    )

    result = restore_run_snapshot("snapshot-run", "MU", "2026-02-13", deps)

    assert result["success"] is True
    assert result["restored"] is True
    assert result["state"]["snapshot_backed"] is True
    assert result["state"]["current_bar_index"] == 2
    runner = active_runners[run_key]
    assert runner._restart_session_config["strategy_selection_mode"] == "adaptive_top_n"
    assert (
        runner._resolved_config_snapshot["control_plane_snapshot"]["config_fingerprint"]
        == "cfg_exec123"
    )
    assert runner.get_markers()[0]["marker_type"] == "signal_generated"

    state = get_run_state("snapshot-run", "MU", "2026-02-13", deps)
    assert state["snapshot_backed"] is True
    assert state["report_saved_at"] == "2026-03-05T11:00:00Z"


def test_restore_run_snapshot_is_idempotent_when_runner_is_already_active():
    run_key = "snapshot-run:MU:2026-02-13"
    bars = [
        {
            "timestamp": "2026-02-13T14:30:00+00:00",
            "open": 100.0,
            "high": 101.0,
            "low": 99.5,
            "close": 100.5,
            "volume": 1200.0,
        }
    ]
    summary = {
        "run_id": "snapshot-run",
        "ticker": "MU",
        "date": "2026-02-13",
        "phase": "COMPLETED",
        "processed_bars": 1,
        "total_bars": 1,
        "resolved_config_snapshot": {
            "session_config_snapshot": {"regime_detection_minutes": 15}
        },
        "playback_snapshot": _playback_snapshot_payload(
            run_key=run_key,
            bars=bars,
            markers=[],
        ),
    }
    deps = _build_deps({}, store=_Store(summary=summary, resolved_snapshot={}))

    first = restore_run_snapshot("snapshot-run", "MU", "2026-02-13", deps)
    second = restore_run_snapshot("snapshot-run", "MU", "2026-02-13", deps)

    assert first["restored"] is True
    assert second["restored"] is False
    assert second["already_active"] is True
    assert second["state"]["snapshot_backed"] is True


def test_snapshot_backed_runner_rejects_play():
    run_key = "snapshot-run:MU:2026-02-13"
    bars = [
        {
            "timestamp": "2026-02-13T14:30:00+00:00",
            "open": 100.0,
            "high": 101.0,
            "low": 99.5,
            "close": 100.5,
            "volume": 1200.0,
        }
    ]
    summary = {
        "run_id": "snapshot-run",
        "ticker": "MU",
        "date": "2026-02-13",
        "phase": "COMPLETED",
        "processed_bars": 1,
        "total_bars": 1,
        "resolved_config_snapshot": {
            "session_config_snapshot": {"regime_detection_minutes": 15}
        },
        "playback_snapshot": _playback_snapshot_payload(
            run_key=run_key,
            bars=bars,
            markers=[],
        ),
    }
    active_runners = {}
    deps = _build_deps(
        active_runners,
        store=_Store(summary=summary, resolved_snapshot={}),
    )
    restore_run_snapshot("snapshot-run", "MU", "2026-02-13", deps)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(play_run("snapshot-run", "MU", "2026-02-13", deps))

    assert exc.value.status_code == 409
    assert "read-only" in str(exc.value.detail)
