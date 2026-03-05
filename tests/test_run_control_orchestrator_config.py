from __future__ import annotations

import asyncio
from dataclasses import dataclass
from types import SimpleNamespace

from src.services import strategy_api_session_service
from src.services.run_control_service import (
    RunControlDeps,
    play_run,
    step_run,
    update_orchestrator_config,
)


@dataclass
class _DummyConfig:
    run_id: str = "run-123"
    ticker: str = "MU"
    date: str = "2026-02-09"
    date_from: str = "2026-02-09"
    strategy_api_url: str = "http://localhost:8001"
    intrabar_execution_recalc_1s: bool = False
    intrabar_eval_step_seconds: int = 1


class _DummyRunner:
    def __init__(self) -> None:
        self.config = _DummyConfig()
        self.is_running = True
        self.is_paused = True
        self.last_run_speed = "max"

    def resume(self) -> None:
        self.is_paused = False

    async def step(self):
        return {"success": True}


class _DummyRegistry:
    def __init__(self, runner: _DummyRunner) -> None:
        self.runner = runner

    def require(self, run_id: str, ticker: str, date: str):
        _ = run_id, ticker, date
        return "run-123:MU:2026-02-09_to_2026-02-09", self.runner


class _RawRequest:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    async def json(self):
        return self._payload


def _build_deps(runner: _DummyRunner) -> RunControlDeps:
    async def _noop(*args, **kwargs):
        _ = args, kwargs
        return None

    logger = SimpleNamespace(
        error=lambda *args, **kwargs: None,
        warning=lambda *args, **kwargs: None,
        info=lambda *args, **kwargs: None,
    )
    return RunControlDeps(
        run_registry=_DummyRegistry(runner),
        active_runners={},
        marker_type_enum=None,
        logger=logger,
        save_remote_checkpoint=_noop,
        clear_remote_strategy_sessions=_noop,
        configure_session=_noop,
    )


def test_update_orchestrator_config_accepts_logger_only_integration_deps(monkeypatch):
    runner = _DummyRunner()
    deps = _build_deps(runner)
    captured: dict[str, object] = {}

    async def _fake_apply_orchestrator_config(strategy_api_url, config, integration_deps):
        captured["strategy_api_url"] = strategy_api_url
        captured["config"] = config
        captured["deps"] = integration_deps
        return {"ok": True}

    monkeypatch.setattr(
        strategy_api_session_service,
        "apply_orchestrator_config",
        _fake_apply_orchestrator_config,
    )

    result = asyncio.run(
        update_orchestrator_config(
            "run-123",
            "MU",
            "2026-02-09_to_2026-02-09",
            {"base_threshold": 49.5},
            deps,
        )
    )

    assert result == {"ok": True}
    assert captured["strategy_api_url"] == "http://localhost:8001"
    assert captured["config"] == {"base_threshold": 49.5}
    assert hasattr(captured["deps"], "logger")


def test_play_run_applies_threshold_overrides_without_typeerror(monkeypatch):
    runner = _DummyRunner()
    deps = _build_deps(runner)
    captured: dict[str, object] = {}

    async def _fake_apply_orchestrator_config(strategy_api_url, config, integration_deps):
        captured["strategy_api_url"] = strategy_api_url
        captured["config"] = config
        captured["deps"] = integration_deps
        return {"ok": True}

    monkeypatch.setattr(
        strategy_api_session_service,
        "apply_orchestrator_config",
        _fake_apply_orchestrator_config,
    )

    result = asyncio.run(
        play_run(
            "run-123",
            "MU",
            "2026-02-09_to_2026-02-09",
            deps,
            raw_request=_RawRequest({"threshold_overrides": {"base_threshold": 51.0}}),
        )
    )

    assert result["success"] is True
    assert result["resumed"] is True
    assert captured["strategy_api_url"] == "http://localhost:8001"
    assert captured["config"] == {"base_threshold": 51.0}
    assert hasattr(captured["deps"], "logger")


def test_step_run_applies_threshold_overrides_without_typeerror(monkeypatch):
    runner = _DummyRunner()
    deps = _build_deps(runner)
    captured: dict[str, object] = {}

    async def _fake_apply_orchestrator_config(strategy_api_url, config, integration_deps):
        captured["strategy_api_url"] = strategy_api_url
        captured["config"] = config
        captured["deps"] = integration_deps
        return {"ok": True}

    monkeypatch.setattr(
        strategy_api_session_service,
        "apply_orchestrator_config",
        _fake_apply_orchestrator_config,
    )

    result = asyncio.run(
        step_run(
            "run-123",
            "MU",
            "2026-02-09_to_2026-02-09",
            deps,
            raw_request=_RawRequest({"threshold_overrides": {"base_threshold": 53.0}}),
        )
    )

    assert result["success"] is True
    assert captured["strategy_api_url"] == "http://localhost:8001"
    assert captured["config"] == {"base_threshold": 53.0}
    assert hasattr(captured["deps"], "logger")
