from __future__ import annotations

import asyncio
from dataclasses import dataclass
from types import SimpleNamespace

import numpy as np
from fastapi.encoders import jsonable_encoder

from src.services.run_control_service import RunControlDeps, play_run, step_run


@dataclass
class _DummyConfig:
    run_id: str = "r1"
    ticker: str = "MU"
    date: str = "2026-02-03"
    date_from: str = "2026-02-03"
    strategy_api_url: str = "http://localhost:8001"
    intrabar_execution_recalc_1s: bool = True
    intrabar_eval_step_seconds: int = 1


class _DummyRunner:
    def __init__(self):
        self.config = _DummyConfig()
        self.is_running = True
        self.is_paused = True
        self.last_run_speed = "10hz"
        self.current_step = 0

    def resume(self):
        self.is_paused = False

    async def step(self):
        self.current_step += 1
        return {"success": True, "bar_index": self.current_step}


class _DummyRegistry:
    def __init__(self, runner):
        self.runner = runner

    def require(self, run_id: str, ticker: str, date: str):
        return f"{run_id}:{ticker}:{date}", self.runner


def _build_deps(runner: _DummyRunner) -> RunControlDeps:
    async def _noop(*args, **kwargs):
        return None

    return RunControlDeps(
        run_registry=_DummyRegistry(runner),
        active_runners={},
        marker_type_enum=None,
        logger=SimpleNamespace(error=lambda *args, **kwargs: None),
        save_remote_checkpoint=_noop,
        clear_remote_strategy_sessions=_noop,
        configure_session=_noop,
    )


def test_play_resume_sets_standard_trade_eval_mode():
    runner = _DummyRunner()
    deps = _build_deps(runner)
    request = SimpleNamespace(speed_ms="10hz", trade_eval_mode="standard")

    result = asyncio.run(play_run("r1", "MU", "2026-02-03", deps, request=request))

    assert result["success"] is True
    assert result["resumed"] is True
    assert result["trade_eval_mode"] == "standard"
    assert runner.config.intrabar_execution_recalc_1s is False
    assert runner.config.intrabar_eval_step_seconds == 1
    assert runner.is_paused is False


def test_play_resume_sets_intrabar_trade_eval_mode_from_bool_payload():
    runner = _DummyRunner()
    runner.config.intrabar_execution_recalc_1s = False
    deps = _build_deps(runner)

    class _RawRequest:
        async def json(self):
            return {"speed_ms": "10hz", "trade_eval_mode": True}

    result = asyncio.run(
        play_run(
            "r1", "MU", "2026-02-03", deps, request=None, raw_request=_RawRequest()
        )
    )

    assert result["success"] is True
    assert result["resumed"] is True
    assert result["trade_eval_mode"] == "intrabar_1s"
    assert runner.config.intrabar_execution_recalc_1s is True
    assert runner.config.intrabar_eval_step_seconds == 1


def test_play_resume_sets_intrabar_5s_trade_eval_mode():
    runner = _DummyRunner()
    runner.config.intrabar_execution_recalc_1s = False
    runner.config.intrabar_eval_step_seconds = 1
    deps = _build_deps(runner)
    request = SimpleNamespace(speed_ms="10hz", trade_eval_mode="intrabar_5s")

    result = asyncio.run(play_run("r1", "MU", "2026-02-03", deps, request=request))

    assert result["success"] is True
    assert result["resumed"] is True
    assert result["trade_eval_mode"] == "intrabar_5s"
    assert runner.config.intrabar_execution_recalc_1s is True
    assert runner.config.intrabar_eval_step_seconds == 5


def test_step_switches_trade_eval_mode_to_intrabar_5s():
    runner = _DummyRunner()
    runner.config.intrabar_execution_recalc_1s = False
    runner.config.intrabar_eval_step_seconds = 1
    deps = _build_deps(runner)
    request = SimpleNamespace(trade_eval_mode="intrabar_5s")

    result = asyncio.run(step_run("r1", "MU", "2026-02-03", deps, request=request))

    assert result["success"] is True
    assert result["trade_eval_mode"] == "intrabar_5s"
    assert runner.config.intrabar_execution_recalc_1s is True
    assert runner.config.intrabar_eval_step_seconds == 5


def test_step_switches_trade_eval_mode_from_raw_payload_bool():
    runner = _DummyRunner()
    runner.config.intrabar_execution_recalc_1s = False
    runner.config.intrabar_eval_step_seconds = 1
    deps = _build_deps(runner)

    class _RawRequest:
        async def json(self):
            return {"trade_eval_mode": True}

    result = asyncio.run(
        step_run(
            "r1",
            "MU",
            "2026-02-03",
            deps,
            request=None,
            raw_request=_RawRequest(),
        )
    )

    assert result["success"] is True
    assert result["trade_eval_mode"] == "intrabar_1s"
    assert runner.config.intrabar_execution_recalc_1s is True
    assert runner.config.intrabar_eval_step_seconds == 1


def test_step_normalizes_numpy_datetime64_for_json_encoding():
    class _NumpyRunner(_DummyRunner):
        async def step(self):
            return {
                "success": True,
                "bar_index": 1,
                "bar_time": np.datetime64("2026-02-11T15:31:00"),
            }

    runner = _NumpyRunner()
    deps = _build_deps(runner)

    result = asyncio.run(step_run("r1", "MU", "2026-02-03", deps))
    encoded = jsonable_encoder(result)

    assert encoded["success"] is True
    assert encoded["bar_index"] == 1
    assert encoded["bar_time"] == "2026-02-11T15:31:00"
