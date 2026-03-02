from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi import HTTPException

from src.routes import live_trader_routes


class _StubServices:
    def __init__(self, *, artifacts_dir: Path, state_store):
        self._artifacts_dir = artifacts_dir
        self.state_store = state_store
        self.logger = None
        self.live_run_active_window_seconds = 180

    def get_live_trader_artifacts_dir(self) -> Path:
        return self._artifacts_dir


class _StubStore:
    def __init__(self):
        self._runs = [
            {
                "run_id": "run-1",
                "status": "active",
                "updated_at": "2026-03-02T10:00:00Z",
                "streams": {},
                "runtime": {"event": "runtime_started", "ticker": "MU"},
                "ticker": "MU",
            }
        ]
        self._events = {
            ("run-1", "decisions"): [{"decision": {"action": "ENTER_LONG"}}]
        }
        self._stats = {
            ("run-1", "runtime"): {
                "count": 1,
                "updated_at": "2026-03-02T10:00:00Z",
                "latest": {"event": "runtime_started", "ticker": "MU"},
            },
            ("run-1", "decisions"): {
                "count": 1,
                "updated_at": "2026-03-02T10:00:01Z",
                "latest": {"decision": {"action": "ENTER_LONG"}},
            },
            ("run-1", "signals"): {"count": 0, "updated_at": None, "latest": None},
            ("run-1", "orders"): {"count": 0, "updated_at": None, "latest": None},
        }
        self.last_list_runs_args = None

    def list_live_trader_runs(self, *, limit: int, active_only: bool, active_window_seconds: int):
        self.last_list_runs_args = {
            "limit": limit,
            "active_only": active_only,
            "active_window_seconds": active_window_seconds,
        }
        return list(self._runs)

    def list_live_trader_events(self, *, run_id: str, stream: str, limit: int):
        _ = limit
        return list(self._events.get((run_id, stream), []))

    def get_live_trader_stream_stats(self, *, run_id: str, stream: str):
        return dict(self._stats.get((run_id, stream), {"count": 0, "latest": None, "updated_at": None}))


def test_list_live_trader_runs_requires_db_store(tmp_path: Path) -> None:
    services = _StubServices(artifacts_dir=tmp_path, state_store=object())
    with pytest.raises(HTTPException) as exc:
        asyncio.run(live_trader_routes.list_live_trader_runs(services=services))
    assert exc.value.status_code == 503


def test_list_live_trader_runs_uses_db_store(tmp_path: Path, monkeypatch) -> None:
    calls = {"sync": 0}

    def _sync_stub(*, artifacts_dir: Path, store, logger=None):
        _ = artifacts_dir, store, logger
        calls["sync"] += 1
        return {"inserted": 0}

    monkeypatch.setattr(live_trader_routes, "sync_live_trader_artifacts_to_store", _sync_stub)

    store = _StubStore()
    services = _StubServices(artifacts_dir=tmp_path, state_store=store)
    payload = asyncio.run(
        live_trader_routes.list_live_trader_runs(limit=25, active_only=True, services=services)
    )
    assert calls["sync"] == 1
    assert payload["source_mode"] == "sqlite_live_trader_events"
    assert payload["count"] == 1
    assert payload["runs"][0]["run_id"] == "run-1"
    assert store.last_list_runs_args == {
        "limit": 25,
        "active_only": True,
        "active_window_seconds": 180,
    }


def test_get_live_trader_snapshot_uses_db_store(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        live_trader_routes,
        "sync_live_trader_artifacts_to_store",
        lambda **kwargs: {"inserted": 0},
    )
    store = _StubStore()
    services = _StubServices(artifacts_dir=tmp_path, state_store=store)

    payload = asyncio.run(
        live_trader_routes.get_live_trader_snapshot(run_id="run-1", tail_limit=200, services=services)
    )
    assert payload["run_id"] == "run-1"
    assert payload["total_count"] == 2
    assert payload["runtime"]["ticker"] == "MU"
    assert payload["streams"]["decisions"]["count"] == 1
