from __future__ import annotations

import asyncio

import pytest

from run_strategy_test import BacktestReport, TradeResult
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


def test_run_single_day_passes_selection_overrides_to_start() -> None:
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

    result = asyncio.run(runner.run_single_day("MU", "2026-02-03"))

    assert captured["start_overrides"]["strategy_selection_mode"] == "adaptive_top_n"
    assert captured["start_overrides"]["max_active_strategies"] == 7
    assert result.total_trades == 0


def test_run_single_day_tracks_level_fade_setup_breakdown() -> None:
    runner = WalkForwardRunner(
        WalkForwardConfig(
            tickers=["MU"],
            start_date="2026-02-03",
            end_date="2026-02-03",
            verbose=False,
        )
    )

    async def _fake_run_test(**_kwargs):
        report = _empty_report()
        report.regime_detected = "MIXED"
        report.trades = [
            TradeResult(
                id=1,
                strategy="level_fade",
                side="long",
                entry_price=100.0,
                exit_price=100.5,
                entry_time="2026-02-03T14:31:00",
                exit_time="2026-02-03T14:35:00",
                size=100,
                pnl_pct=0.5,
                pnl_dollars=50.0,
                exit_reason="take_profit",
                gross_pnl_pct=0.6,
                total_costs=1.0,
                signal_metadata={"level_fade": {"setup_type_guess": "touch_hold"}},
                flow_snapshot={},
            ),
            TradeResult(
                id=2,
                strategy="level_fade",
                side="long",
                entry_price=100.0,
                exit_price=99.7,
                entry_time="2026-02-03T15:01:00",
                exit_time="2026-02-03T15:06:00",
                size=100,
                pnl_pct=-0.3,
                pnl_dollars=-30.0,
                exit_reason="stop_loss",
                gross_pnl_pct=-0.2,
                total_costs=1.0,
                signal_metadata={"level_fade": {"setup_type_guess": "sweep_reclaim"}},
                flow_snapshot={},
            ),
        ]
        report.total_trades = 2
        report.winning_trades = 1
        report.losing_trades = 1
        report.total_pnl_pct = 0.2
        report.total_pnl_dollars = 20.0
        report.total_costs = 2.0
        report.win_rate = 50.0
        return report

    runner.tester.run_test = _fake_run_test  # type: ignore[assignment]

    day_result = asyncio.run(runner.run_single_day("MU", "2026-02-03"))
    runner.results = [day_result]
    report = runner._generate_report()

    breakdown = report["level_fade_setup_breakdown"]
    assert breakdown["touch_hold"]["total_trades"] == 1
    assert breakdown["sweep_reclaim"]["total_trades"] == 1
    assert breakdown["touch_hold"]["win_rate"] == 100.0
    assert breakdown["sweep_reclaim"]["win_rate"] == 0.0
