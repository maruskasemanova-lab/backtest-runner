from __future__ import annotations

import asyncio
from dataclasses import dataclass
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from src.services.run_control_service import RunControlDeps, delete_run, get_run_summary_db


@dataclass
class _DummyConfig:
    run_id: str = "run-1"
    ticker: str = "MU"
    date: str = "2026-02-11"
    date_from: str = "2026-02-11"
    date_to: str = "2026-02-12"
    strategy_api_url: str = "http://localhost:8001"


class _DummyRunner:
    def __init__(self):
        self.config = _DummyConfig()
        self.stopped = False
        self.closed = False

    def stop(self):
        self.stopped = True

    async def close_http_session(self):
        self.closed = True

    def get_summary(self):
        return {
            "run_id": self.config.run_id,
            "ticker": self.config.ticker,
            "session_summary": {"total_trades": 1},
            "resolved_config_snapshot": {
                "schema_version": 1,
                "run_key": (
                    f"{self.config.run_id}:{self.config.ticker}:"
                    f"{self.config.date_from}_to_{self.config.date_to}"
                ),
                "config_fingerprint": "cfg_exec123",
            },
        }


class _DummyRegistry:
    def __init__(self, run_key: str, runner: _DummyRunner):
        self._run_key = run_key
        self._runner = runner

    def require(self, run_id: str, ticker: str, date: str):
        _ = run_id, ticker, date
        return self._run_key, self._runner


class _CaptureRunReportsStore:
    def __init__(self):
        self.calls = []
        self.snapshot_rows = {}

    def upsert_run_summary(self, *, run_key: str, summary):
        self.calls.append({"run_key": run_key, "summary": summary})

    def upsert_run_config_snapshot(self, *, run_key: str, snapshot):
        snapshot_id = "rcs_test123"
        self.snapshot_rows[run_key] = {
            "snapshot_id": snapshot_id,
            "run_key": run_key,
            "payload": snapshot,
        }
        return self.snapshot_rows[run_key]

    def get_run_summary(self, *, run_key: str):
        for call in reversed(self.calls):
            if call["run_key"] == run_key:
                return {"run_key": run_key, "summary": call["summary"], "updated_at": "2026-02-11T10:00:00Z"}
        return None

    def get_run_config_snapshot(self, *, snapshot_id=None, run_key=None):
        _ = snapshot_id
        return self.snapshot_rows.get(run_key or "")


def test_delete_run_persists_summary_to_run_reports_store():
    runner = _DummyRunner()
    run_key = "run-1:MU:2026-02-11_to_2026-02-12"
    registry = _DummyRegistry(run_key, runner)
    active_runners = {run_key: runner}
    run_reports_store = _CaptureRunReportsStore()
    clear_calls = []

    async def _clear_remote(strategy_api_url: str, run_id: str, ticker: str):
        clear_calls.append((strategy_api_url, run_id, ticker))
        return None

    async def _noop(*args, **kwargs):
        _ = args, kwargs
        return None

    deps = RunControlDeps(
        run_registry=registry,
        active_runners=active_runners,
        marker_type_enum=None,
        logger=SimpleNamespace(error=lambda *args, **kwargs: None),
        save_remote_checkpoint=_noop,
        clear_remote_strategy_sessions=_clear_remote,
        configure_session=_noop,
        run_reports_store=run_reports_store,
    )

    result = asyncio.run(delete_run("run-1", "MU", "2026-02-11", deps))

    assert result["success"] is True
    assert result["deleted"] == run_key
    assert runner.stopped is True
    assert runner.closed is True
    assert run_reports_store.calls
    assert run_reports_store.calls[0]["run_key"] == run_key
    assert run_reports_store.calls[0]["summary"]["run_id"] == "run-1"
    assert run_reports_store.calls[0]["summary"]["resolved_config_snapshot_id"] == "rcs_test123"
    assert "resolved_config_snapshot" not in run_reports_store.calls[0]["summary"]
    assert run_key not in active_runners
    assert clear_calls == [("http://localhost:8001", "run-1", "MU")]


def test_get_run_summary_db_hydrates_externalized_config_snapshot():
    runner = _DummyRunner()
    run_key = "run-1:MU:2026-02-11_to_2026-02-12"
    store = _CaptureRunReportsStore()
    store.upsert_run_summary(
        run_key=run_key,
        summary={
            "run_id": "run-1",
            "ticker": "MU",
            "resolved_config_snapshot_id": "rcs_test123",
        },
    )
    store.snapshot_rows[run_key] = {
        "snapshot_id": "rcs_test123",
        "run_key": run_key,
        "payload": {
            "schema_version": 1,
            "run_key": run_key,
            "config_fingerprint": "cfg_exec123",
            "session_config_snapshot": {
                "regime_detection_minutes": 15,
                "strategy_selection_mode": "adaptive_top_n",
            },
        },
    }

    deps = RunControlDeps(
        run_registry=SimpleNamespace(build_key=lambda run_id, ticker, date: run_key),
        active_runners={},
        marker_type_enum=None,
        logger=SimpleNamespace(error=lambda *args, **kwargs: None),
        save_remote_checkpoint=lambda *args, **kwargs: None,
        clear_remote_strategy_sessions=lambda *args, **kwargs: None,
        configure_session=lambda *args, **kwargs: None,
        run_reports_store=store,
    )

    summary = get_run_summary_db("run-1", "MU", "2026-02-11", deps)

    assert summary["resolved_config_snapshot_id"] == "rcs_test123"
    assert summary["resolved_config_snapshot"]["config_fingerprint"] == "cfg_exec123"


def test_get_run_summary_db_rejects_legacy_summary_without_modern_snapshots():
    run_key = "run-1:MU:2026-02-11_to_2026-02-12"
    store = _CaptureRunReportsStore()
    store.upsert_run_summary(
        run_key=run_key,
        summary={
            "run_id": "run-1",
            "ticker": "MU",
            "playback_snapshot": {
                "encoding": "gzip+base64",
                "payload_b64": "abc",
            },
        },
    )

    deps = RunControlDeps(
        run_registry=SimpleNamespace(build_key=lambda run_id, ticker, date: run_key),
        active_runners={},
        marker_type_enum=None,
        logger=SimpleNamespace(error=lambda *args, **kwargs: None),
        save_remote_checkpoint=lambda *args, **kwargs: None,
        clear_remote_strategy_sessions=lambda *args, **kwargs: None,
        configure_session=lambda *args, **kwargs: None,
        run_reports_store=store,
    )

    with pytest.raises(HTTPException) as exc:
        get_run_summary_db("run-1", "MU", "2026-02-11", deps)

    assert exc.value.status_code == 404
    assert "Legacy run summary" in str(exc.value.detail)
