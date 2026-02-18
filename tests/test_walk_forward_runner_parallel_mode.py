from __future__ import annotations

import pytest

from run_strategy_test import BacktestReport
from walk_forward_runner import WalkForwardConfig, WalkForwardRunner


def _empty_report() -> BacktestReport:
    return BacktestReport(
        run_id="wf-test",
        ticker="MU",
        date="2026-02-03",
        start_time="2026-02-03T14:30:00",
        end_time="2026-02-03T20:00:00",
        duration_seconds=1.0,
        total_bars=10,
        bars_processed=10,
        total_trades=0,
        winning_trades=0,
        losing_trades=0,
        total_pnl_pct=0.0,
        total_pnl_dollars=0.0,
        total_costs=0.0,
        win_rate=0.0,
        avg_win_pct=0.0,
        avg_loss_pct=0.0,
        profit_factor=0.0,
        max_drawdown_pct=0.0,
        trades=[],
        decisions=[],
        errors=[],
    )


def test_build_start_overrides_for_parallel_all_strategies() -> None:
    runner = WalkForwardRunner(
        WalkForwardConfig(
            tickers=["MU"],
            start_date="2026-02-03",
            end_date="2026-02-03",
            verbose=False,
            parallel_all_strategies=True,
            strategy_selection_mode="adaptive_top_n",
            max_active_strategies=2,
        )
    )

    overrides = runner._build_start_overrides()
    assert overrides["strategy_selection_mode"] == "all_enabled"
    assert overrides["max_active_strategies"] == 20


@pytest.mark.asyncio
async def test_run_single_day_passes_selection_overrides_to_start() -> None:
    runner = WalkForwardRunner(
        WalkForwardConfig(
            tickers=["MU"],
            start_date="2026-02-03",
            end_date="2026-02-03",
            verbose=False,
            strategy_selection_mode="adaptive_top_n",
            max_active_strategies=7,
            parallel_all_strategies=False,
        )
    )

    captured = {}

    async def _fake_run_test(**kwargs):
        captured.update(kwargs)
        return _empty_report()

    runner.tester.run_test = _fake_run_test  # type: ignore[assignment]

    result = await runner.run_single_day("MU", "2026-02-03")

    assert captured["start_overrides"]["strategy_selection_mode"] == "adaptive_top_n"
    assert captured["start_overrides"]["max_active_strategies"] == 7
    assert result.total_trades == 0
