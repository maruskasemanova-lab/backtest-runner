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
| `wfo_optimizer.py` | yes | 675 | `13f270b 2026-02-06` |
| `walk_forward_runner.py` | yes | 447 | `13f270b 2026-02-06` |
| `performance_tracker.py` | yes | 822 | `13f270b 2026-02-06` |
| `oos_validator.py` | yes | 187 | `13f270b 2026-02-06` |
| `monte_carlo.py` | yes | 178 | `64da33c 2026-02-10` |
| `tuning_runner.py` | yes | 340 | `583f2bc 2026-02-06` |
| `aos_walk_forward.py` | yes | 585 | `13f270b 2026-02-06` |
| `aos_optimizer.py` | yes | 572 | `9249b8b 2026-02-05` |
| `run_strategy_test.py` | yes | 552 | `97ee653 2026-02-08` |
| `batch_runner.py` | yes | 187 | `36d343c 2026-02-03` |

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
- `function` `suppress_output` (line 47)
- `class` `OptimizationResult` (line 110)
- `class` `TickerOptResult` (line 122)
- `function` `parse_date` (line 133)
- `function` `canonical_strategy_name` (line 137)
- `function` `date_range` (line 152)
- `function` `get_trading_dates` (line 165)
- `function` `grid` (line 191)
- `function` `run_single_day` (line 200)
- `function` `score_result` (line 287)
- `function` `optimize_strategy_for_dates` (line 314)
- `function` `evaluate_on_dates` (line 395)
- ... 2 more symbols

### `walk_forward_runner.py`
- `class` `WalkForwardConfig` (line 22)
- `class` `DailyResult` (line 34)
- `class` `WalkForwardRunner` (line 50)
- `async_function` `main` (line 411)

### `performance_tracker.py`
- `class` `Regime` (line 15)
- `class` `TradeRecord` (line 23)
- `class` `StrategyPerformance` (line 74)
- `class` `PerformanceTracker` (line 268)
- `function` `create_tracker` (line 762)

### `oos_validator.py`
- `class` `SplitResult` (line 25)
- `function` `split_dates_chronological` (line 31)
- `function` `build_day_rows_map` (line 53)
- `function` `win_rate` (line 86)
- `function` `run_for_ticker` (line 90)
- `function` `main` (line 141)

### `monte_carlo.py`
- `function` `_pick_pnl_column` (line 18)
- `function` `load_trade_pnls` (line 27)
- `function` `max_drawdown` (line 47)
- `function` `simulate_drawdown_distribution` (line 66)
- `function` `percentile` (line 93)
- `function` `summarize` (line 100)
- `function` `main` (line 125)

### `tuning_runner.py`
- `function` `suppress_output` (line 40)
- `class` `TuneResult` (line 52)
- `function` `parse_date` (line 60)
- `function` `date_range` (line 64)
- `function` `load_ticker_df` (line 77)
- `function` `get_available_dates` (line 90)
- `function` `select_training_dates` (line 95)
- `function` `run_day` (line 101)
- `function` `score_result` (line 143)
- `function` `grid` (line 152)
- `function` `tune_strategy_for_ticker` (line 160)
- `function` `evaluate_test_week` (line 201)
- ... 1 more symbols

### `aos_walk_forward.py`
- `class` `AOSConfig` (line 40)
- `class` `DailyAOSResult` (line 49)
- `class` `AOSWalkForwardRunner` (line 68)
- `async_function` `main` (line 548)

### `aos_optimizer.py`
- `class` `OptimizationResult` (line 37)
- `class` `TickerProfile` (line 52)
- `class` `AOSOptimizer` (line 65)
- `class` `AOSRunner` (line 420)
- `function` `create_aos_config` (line 487)

### `run_strategy_test.py`
- `class` `TradeResult` (line 19)
- `class` `BacktestReport` (line 39)
- `class` `StrategyTester` (line 73)
- `async_function` `main` (line 521)

### `batch_runner.py`
- `class` `BatchReport` (line 19)
- `class` `BatchRunner` (line 54)
- `async_function` `main` (line 169)

## Endpoint Summary

| Method | Path | Handler | File |
|---|---|---|---|
| `-` | `-` | `-` | `-` |

## Prompt Primer

Load this domain pack with `bmad/context/generated/00-index.md` and `bmad/context/generated/00-machine-index.json`, then keep edits scoped to mapped files unless interface changes are explicit.
