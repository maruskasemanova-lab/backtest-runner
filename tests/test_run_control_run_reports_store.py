from __future__ import annotations

import asyncio
from dataclasses import dataclass
from types import SimpleNamespace

from src.services.run_control_service import RunControlDeps, delete_run


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

    def upsert_run_summary(self, *, run_key: str, summary):
        self.calls.append({"run_key": run_key, "summary": summary})


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
    assert run_key not in active_runners
    assert clear_calls == [("http://localhost:8001", "run-1", "MU")]
