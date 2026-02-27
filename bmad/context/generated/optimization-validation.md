# Domain: Optimization & Validation

**ID:** `optimization-validation`

## Mission

Own parameter search, walk-forward, OOS validation, and Monte Carlo robustness analysis.

## Depends On

- `orchestration`
- `strategy-engine`

## Entrypoints

- `wfo_optimizer.py`
- `walk_forward_runner.py`
- `oos_validator.py`
- `monte_carlo.py`

## File Inventory

| File | Exists | Lines | Last Commit |
|---|---:|---:|---|
| `wfo_optimizer.py` | yes | 911 | `1273b21 2026-02-23` |
| `walk_forward_runner.py` | yes | 526 | `1273b21 2026-02-23` |
| `performance_tracker.py` | yes | 876 | `1273b21 2026-02-23` |
| `oos_validator.py` | yes | 223 | `1273b21 2026-02-23` |
| `monte_carlo.py` | yes | 193 | `1273b21 2026-02-23` |
| `tuning_runner.py` | yes | 359 | `1273b21 2026-02-23` |
| `aos_walk_forward.py` | yes | 633 | `1273b21 2026-02-23` |
| `aos_optimizer.py` | yes | 422 | `1273b21 2026-02-23` |
| `run_strategy_test.py` | yes | 644 | `1273b21 2026-02-23` |
| `batch_runner.py` | yes | 214 | `1273b21 2026-02-23` |

## Change Checks

- Score by executed strategy, not selected_strategy label.
- Keep strict chronological split for hold-out testing.
- Report regime/hour/weekday breakdowns.
- Monte Carlo risk gate behavior must be deterministic with seed control.

## Critical Invariants

- Train/validation/test chronology must never be shuffled for OOS reports.
- Optimization grids and evaluated overrides must remain auditable.
- Performance accounting must include costs consistently.
- Risk threshold checks must produce machine-checkable pass/fail outputs.

## Test Targets

- `tests/test_wfo_optimizer.py`
- `tests/test_performance_tracker_time_buckets.py`

## Key Symbols

### `wfo_optimizer.py`
- `function` `_load_day_trading_manager` (line 32)
- `function` `suppress_output` (line 66)
- `class` `OptimizationResult` (line 169)
- `class` `TickerOptResult` (line 181)
- `function` `canonical_strategy_name` (line 192)
- `function` `get_trading_dates` (line 207)
- `function` `grid` (line 237)
- `function` `_session_metrics` (line 246)
- `function` `_process_day_with_manager` (line 290)
- `function` `_run_single_day_strategy_isolated` (line 319)
- `function` `run_single_day` (line 360)
- `function` `score_result` (line 454)
- ... 4 more symbols

### `walk_forward_runner.py`
- `class` `WalkForwardConfig` (line 21)
- `class` `DailyResult` (line 37)
- `class` `WalkForwardRunner` (line 54)
- `async_function` `main` (line 459)

### `performance_tracker.py`
- `class` `Regime` (line 16)
- `class` `TradeRecord` (line 25)
- `class` `StrategyPerformance` (line 95)
- `class` `PerformanceTracker` (line 298)

### `oos_validator.py`
- `class` `SplitResult` (line 30)
- `function` `split_dates_chronological` (line 36)
- `function` `build_day_rows_map` (line 60)
- `function` `win_rate` (line 99)
- `function` `run_for_ticker` (line 103)
- `function` `main` (line 174)

### `monte_carlo.py`
- `function` `_pick_pnl_column` (line 18)
- `function` `load_trade_pnls` (line 27)
- `function` `max_drawdown` (line 47)
- `function` `simulate_drawdown_distribution` (line 66)
- `function` `percentile` (line 93)
- `function` `summarize` (line 103)
- `function` `main` (line 130)

### `tuning_runner.py`
- `function` `suppress_output` (line 40)
- `class` `TuneResult` (line 53)
- `function` `parse_date` (line 61)
- `function` `date_range` (line 65)
- `function` `load_ticker_df` (line 78)
- `function` `get_available_dates` (line 91)
- `function` `select_training_dates` (line 96)
- `function` `run_day` (line 104)
- `function` `score_result` (line 146)
- `function` `grid` (line 155)
- `function` `tune_strategy_for_ticker` (line 163)
- `function` `evaluate_test_week` (line 210)
- ... 1 more symbols

### `aos_walk_forward.py`
- `class` `AOSConfig` (line 40)
- `class` `DailyAOSResult` (line 50)
- `class` `AOSWalkForwardRunner` (line 70)
- `async_function` `main` (line 591)

### `aos_optimizer.py`
- `class` `OptimizationResult` (line 37)
- `class` `TickerProfile` (line 53)
- `class` `AOSOptimizer` (line 67)

### `run_strategy_test.py`
- `class` `TradeResult` (line 19)
- `class` `BacktestReport` (line 40)
- `class` `StrategyTester` (line 75)
- `async_function` `main` (line 594)

### `batch_runner.py`
- `class` `BatchReport` (line 19)
- `class` `BatchRunner` (line 55)
- `async_function` `main` (line 187)

## Endpoint Summary

| Method | Path | Handler | File |
|---|---|---|---|
| `-` | `-` | `-` | `-` |

## Prompt Primer

Load this domain pack with `bmad/context/generated/00-index.md` and `bmad/context/generated/00-machine-index.json`, then keep edits scoped to mapped files unless interface changes are explicit.
