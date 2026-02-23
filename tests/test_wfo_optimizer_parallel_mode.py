from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

import wfo_optimizer


def test_param_grids_cover_all_registered_strategies() -> None:
    dtm_cls = getattr(wfo_optimizer, "DayTradingManager", None)
    assert dtm_cls is not None
    dtm = dtm_cls(regime_detection_minutes=0)
    missing = sorted(set(dtm.strategies.keys()) - set(wfo_optimizer.PARAM_GRIDS.keys()))
    assert not missing, f"Missing PARAM_GRIDS entries for strategies: {missing}"


def test_run_single_day_parallel_mode_aggregates_isolated_strategy_runs(
    monkeypatch,
) -> None:
    calls = []

    def _fake_isolated(**kwargs):
        calls.append(kwargs["strategy_name"])
        strat = kwargs["strategy_name"]
        pnl = 1.0 if strat == "momentum" else -0.5
        stats = {
            strat: {
                "pnl": pnl,
                "trades": 1.0,
                "wins": 1.0 if pnl > 0 else 0.0,
                "gross_wins": max(0.0, pnl),
                "gross_losses": abs(min(0.0, pnl)),
            }
        }
        return pnl, 1, 1 if pnl > 0 else 0, max(0.0, pnl), abs(min(0.0, pnl)), stats

    monkeypatch.setattr(
        wfo_optimizer, "_run_single_day_strategy_isolated", _fake_isolated
    )

    result = wfo_optimizer.run_single_day(
        ticker="MU",
        date="2026-02-03",
        day_rows=[object()],
        params_by_strategy={
            "momentum": {"x": 1},
            "pullback": {"y": 2},
        },
        parallel_all_strategies=True,
    )

    assert sorted(calls) == ["momentum", "pullback"]
    total_pnl, total_trades, total_wins, gross_wins, gross_losses, per_strategy = result
    assert total_pnl == 0.5
    assert total_trades == 2
    assert total_wins == 1
    assert gross_wins == 1.0
    assert gross_losses == 0.5
    assert sorted(per_strategy.keys()) == ["momentum", "pullback"]


def test_run_single_day_parallel_mode_sets_all_enabled_defaults(monkeypatch) -> None:
    captured = {}

    class _FakeDTM:
        def __init__(self, regime_detection_minutes: int = 30):
            self.regime_detection_minutes = regime_detection_minutes
            self.strategies = {
                "momentum": SimpleNamespace(),
                "pullback": SimpleNamespace(),
                "mean_reversion": SimpleNamespace(),
            }

        def set_run_defaults(self, **kwargs):
            captured["run_defaults"] = kwargs

        def process_bar(self, **_kwargs):
            return None

        def get_session(self, run_id: str, ticker: str, date: str):
            return SimpleNamespace(
                total_pnl=0.5,
                trades=[SimpleNamespace(strategy="momentum", pnl_pct=0.5)],
            )

    monkeypatch.setattr(wfo_optimizer, "DayTradingManager", _FakeDTM)

    day_rows = [
        SimpleNamespace(
            timestamp=pd.Timestamp("2026-02-03T14:30:00Z"),
            open=100.0,
            high=101.0,
            low=99.5,
            close=100.5,
            volume=120_000.0,
            vwap=100.3,
        )
    ]

    result = wfo_optimizer.run_single_day(
        ticker="MU",
        date="2026-02-03",
        day_rows=day_rows,
        params_by_strategy={},
        parallel_all_strategies=True,
    )

    assert captured["run_defaults"]["strategy_selection_mode"] == "all_enabled"
    assert captured["run_defaults"]["max_active_strategies"] == 3
    assert result[1] == 1


def test_run_walk_forward_propagates_parallel_mode(monkeypatch) -> None:
    monkeypatch.setattr(
        wfo_optimizer,
        "PARAM_GRIDS",
        {"momentum": {"x": [1]}},
    )

    optimize_flags = []
    evaluate_flags = []

    def _fake_optimize(
        *, strategy_name: str, dates, parallel_all_strategies: bool = False, **_kwargs
    ):
        optimize_flags.append(parallel_all_strategies)
        return wfo_optimizer.OptimizationResult(
            strategy=strategy_name,
            params={"x": 1},
            score=1.0,
            total_pnl_pct=1.0,
            trades=len(dates),
            win_rate=50.0,
            profit_factor=1.2,
            days_used=len(dates),
        )

    def _fake_evaluate(*, parallel_all_strategies: bool = False, **_kwargs):
        evaluate_flags.append(parallel_all_strategies)
        return 0.0, 0, 0, 0.0, 0.0

    monkeypatch.setattr(wfo_optimizer, "optimize_strategy_for_dates", _fake_optimize)
    monkeypatch.setattr(wfo_optimizer, "evaluate_on_dates", _fake_evaluate)

    dates = ["2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08"]
    day_rows_map = {date: [object()] for date in dates}

    result = wfo_optimizer.run_walk_forward(
        ticker="MU",
        all_dates=dates,
        day_rows_map=day_rows_map,
        train_days=2,
        test_days=1,
        parallel_all_strategies=True,
    )

    assert optimize_flags and all(optimize_flags)
    assert evaluate_flags and all(evaluate_flags)
    assert result.best_params == {"momentum": {"x": 1}}
