from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

import pytest
from fastapi import HTTPException

from src.services.run_control_service import RunControlDeps, restart_run


@dataclass
class _DummyConfig:
    run_id: str
    ticker: str
    date: str
    date_from: str
    strategy_api_url: str


class _DummyRunner:
    def __init__(self):
        self.config = _DummyConfig(
            run_id="r1",
            ticker="NVDA",
            date="2026-02-01_to_2026-02-10",
            date_from="2026-02-01",
            strategy_api_url="http://localhost:8001",
        )
        self.is_running = False
        self.is_paused = False
        self.current_bar_index = 17
        self._restart_session_date = "2026-02-01"
        self._restart_session_config = {
            "regime_detection_minutes": 15,
            "regime_refresh_bars": 15,
            "account_size_usd": 10000.0,
            "risk_per_trade_pct": 1.0,
            "max_position_notional_pct": 100.0,
            "max_fill_participation_rate": 0.2,
            "min_fill_ratio": 0.35,
            "enable_partial_take_profit": False,
            "partial_take_profit_rr": 1.5,
            "partial_take_profit_fraction": 0.5,
            "trailing_activation_pct": 0.45,
            "break_even_buffer_pct": 0.0,
            "break_even_min_hold_bars": 2,
            "trailing_enabled_in_choppy": False,
            "time_exit_bars": 40,
            "adverse_flow_exit_enabled": True,
            "adverse_flow_threshold": 0.12,
            "adverse_flow_min_hold_bars": 3,
            "adverse_flow_consistency_threshold": 0.2,
            "adverse_book_pressure_threshold": -0.05,
            "stop_loss_mode": "strategy",
            "fixed_stop_loss_pct": 0.0,
            "l2_confirm_enabled": True,
            "l2_min_delta": 0.0,
            "l2_min_imbalance": 0.0,
            "l2_min_iceberg_bias": 0.0,
            "l2_lookback_bars": 3,
            "l2_min_participation_ratio": 0.0,
            "l2_min_directional_consistency": 0.0,
            "l2_min_signed_aggression": 0.0,
            "cold_start_each_day": False,
            "strategy_selection_mode": "adaptive_top_n",
            "max_active_strategies": 3,
            "momentum_diversification_json": None,
        }
        self.reset_calls = 0

    def reset_for_replay(self):
        self.reset_calls += 1
        self.current_bar_index = 0
        self.is_running = False
        self.is_paused = False

    def get_state(self):
        return {
            "run_id": self.config.run_id,
            "ticker": self.config.ticker,
            "date": self.config.date,
            "current_bar_index": self.current_bar_index,
            "phase": "INITIALIZED",
        }


class _DummyRegistry:
    def __init__(self, runner):
        self.runner = runner

    def require(self, run_id: str, ticker: str, date: str):
        return f"{run_id}:{ticker}:{date}", self.runner


def _build_deps(runner: _DummyRunner, calls: dict) -> RunControlDeps:
    async def _clear_remote(strategy_api_url: str, run_id: str, ticker: str):
        calls["clear"] = (strategy_api_url, run_id, ticker)

    async def _configure_session(
        strategy_api_url: str, run_id: str, ticker: str, date: str, **kwargs
    ):
        calls["configure"] = (strategy_api_url, run_id, ticker, date, kwargs)

    return RunControlDeps(
        run_registry=_DummyRegistry(runner),
        active_runners={},
        marker_type_enum=None,
        logger=None,
        reports_dir=Path("."),
        save_remote_checkpoint=None,
        clear_remote_strategy_sessions=_clear_remote,
        configure_session=_configure_session,
    )


def test_restart_run_rewinds_without_reloading_bars():
    runner = _DummyRunner()
    calls = {}
    deps = _build_deps(runner, calls)

    result = asyncio.run(restart_run("r1", "NVDA", "2026-02-01_to_2026-02-10", deps))

    assert result["success"] is True
    assert result["restarted"] is True
    assert result["state"]["current_bar_index"] == 0
    assert runner.reset_calls == 1

    assert calls["clear"] == ("http://localhost:8001", "r1", "NVDA")
    cfg_call = calls["configure"]
    assert cfg_call[0] == "http://localhost:8001"
    assert cfg_call[1] == "r1"
    assert cfg_call[2] == "NVDA"
    assert cfg_call[3] == "2026-02-01"
    assert cfg_call[4]["strategy_selection_mode"] == "adaptive_top_n"


def test_restart_run_rejects_active_run():
    runner = _DummyRunner()
    runner.is_running = True
    deps = _build_deps(runner, {})

    with pytest.raises(HTTPException) as exc:
        asyncio.run(restart_run("r1", "NVDA", "2026-02-01_to_2026-02-10", deps))

    assert exc.value.status_code == 409
