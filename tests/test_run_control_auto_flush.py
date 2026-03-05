from __future__ import annotations

import asyncio
from dataclasses import dataclass
from types import SimpleNamespace

from src.services import run_control_service
from src.services.run_control_service import RunControlDeps, play_run


@dataclass
class _DummyConfig:
    run_id: str = "run-1"
    ticker: str = "MU"
    date: str = "2026-02-11"
    date_from: str = "2026-02-11"
    date_to: str = ""
    strategy_api_url: str = "http://localhost:8001"


class _DummyRunner:
    def __init__(self):
        self.config = _DummyConfig()
        self.is_running = False
        self.is_paused = False
        self.phase = "INITIALIZED"
        self.bars = [{"close": 1.0}, {"close": 2.0}]
        self.current_bar_index = 0
        self.closed = False

    async def run_all(self, speed_ms="max"):
        _ = speed_ms
        self.is_running = False
        self.current_bar_index = len(self.bars)
        self.phase = "END_OF_DAY"
        return self.get_summary()

    async def close_http_session(self):
        self.closed = True

    def get_summary(self):
        return {
            "run_id": self.config.run_id,
            "ticker": self.config.ticker,
            "phase": self.phase,
        }


class _PartialRunner(_DummyRunner):
    async def run_all(self, speed_ms="max"):
        _ = speed_ms
        self.is_running = False
        self.current_bar_index = 1
        self.phase = "RUNNING"
        return self.get_summary()


class _DummyRegistry:
    def __init__(self, run_key: str, runner):
        self._run_key = run_key
        self._runner = runner

    def require(self, run_id: str, ticker: str, date: str):
        _ = run_id, ticker, date
        return self._run_key, self._runner


class _CaptureRunReportsStore:
    def __init__(self):
        self.calls = []

    def upsert_run_summary(self, *, run_key: str, summary):
        self.calls.append({"run_key": run_key, "summary": summary})


class _RawJsonRequest:
    def __init__(self, payload):
        self._payload = payload

    async def json(self):
        return self._payload


def _capture_tasks(monkeypatch):
    scheduled = []

    def _fake_create_task(coro):
        scheduled.append(coro)
        return SimpleNamespace(cancel=lambda: True)

    monkeypatch.setattr(run_control_service.asyncio, "create_task", _fake_create_task)
    return scheduled


def test_play_run_auto_flushes_successful_completed_run(monkeypatch):
    runner = _DummyRunner()
    run_key = "run-1:MU:2026-02-11"
    active_runners = {run_key: runner}
    run_reports_store = _CaptureRunReportsStore()
    scheduled = _capture_tasks(monkeypatch)
    clear_calls = []

    async def _clear_remote(strategy_api_url: str, run_id: str, ticker: str):
        clear_calls.append((strategy_api_url, run_id, ticker))
        return None

    async def _noop(*args, **kwargs):
        _ = args, kwargs
        return None

    deps = RunControlDeps(
        run_registry=_DummyRegistry(run_key, runner),
        active_runners=active_runners,
        marker_type_enum=None,
        logger=SimpleNamespace(error=lambda *args, **kwargs: None),
        save_remote_checkpoint=_noop,
        clear_remote_strategy_sessions=_clear_remote,
        configure_session=_noop,
        run_reports_store=run_reports_store,
    )

    result = asyncio.run(play_run("run-1", "MU", "2026-02-11", deps))

    assert result["success"] is True
    assert run_key in active_runners
    assert len(scheduled) == 1

    asyncio.run(scheduled.pop())

    assert run_key not in active_runners
    assert runner.closed is True
    assert clear_calls == [("http://localhost:8001", "run-1", "MU")]
    assert run_reports_store.calls
    assert run_reports_store.calls[0]["run_key"] == run_key


def test_play_run_keeps_incomplete_run_in_memory(monkeypatch):
    runner = _PartialRunner()
    run_key = "run-1:MU:2026-02-11"
    active_runners = {run_key: runner}
    scheduled = _capture_tasks(monkeypatch)
    clear_calls = []

    async def _clear_remote(strategy_api_url: str, run_id: str, ticker: str):
        clear_calls.append((strategy_api_url, run_id, ticker))
        return None

    async def _noop(*args, **kwargs):
        _ = args, kwargs
        return None

    deps = RunControlDeps(
        run_registry=_DummyRegistry(run_key, runner),
        active_runners=active_runners,
        marker_type_enum=None,
        logger=SimpleNamespace(error=lambda *args, **kwargs: None),
        save_remote_checkpoint=_noop,
        clear_remote_strategy_sessions=_clear_remote,
        configure_session=_noop,
    )

    result = asyncio.run(play_run("run-1", "MU", "2026-02-11", deps))

    assert result["success"] is True
    assert len(scheduled) == 1

    asyncio.run(scheduled.pop())

    assert run_key in active_runners
    assert runner.closed is False
    assert clear_calls == []


def test_play_run_keeps_completed_run_when_requested(monkeypatch):
    runner = _DummyRunner()
    run_key = "run-1:MU:2026-02-11"
    active_runners = {run_key: runner}
    run_reports_store = _CaptureRunReportsStore()
    scheduled = _capture_tasks(monkeypatch)
    clear_calls = []

    async def _clear_remote(strategy_api_url: str, run_id: str, ticker: str):
        clear_calls.append((strategy_api_url, run_id, ticker))
        return None

    async def _noop(*args, **kwargs):
        _ = args, kwargs
        return None

    deps = RunControlDeps(
        run_registry=_DummyRegistry(run_key, runner),
        active_runners=active_runners,
        marker_type_enum=None,
        logger=SimpleNamespace(error=lambda *args, **kwargs: None),
        save_remote_checkpoint=_noop,
        clear_remote_strategy_sessions=_clear_remote,
        configure_session=_noop,
        run_reports_store=run_reports_store,
    )

    result = asyncio.run(
        play_run(
            "run-1",
            "MU",
            "2026-02-11",
            deps,
            raw_request=_RawJsonRequest({"keep_in_memory_after_completion": True}),
        )
    )

    assert result["success"] is True
    assert run_key in active_runners
    assert len(scheduled) == 1

    asyncio.run(scheduled.pop())

    assert run_key in active_runners
    assert runner.closed is False
    assert clear_calls == []
    assert run_reports_store.calls
