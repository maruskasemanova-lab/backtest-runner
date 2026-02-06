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
| `wfo_optimizer.py` | yes | 654 | `7a5cd1a 2026-02-06` |
| `walk_forward_runner.py` | yes | 431 | `583f2bc 2026-02-06` |
| `performance_tracker.py` | yes | 749 | `583f2bc 2026-02-06` |
| `oos_validator.py` | yes | 187 | `-` |
| `monte_carlo.py` | yes | 151 | `-` |
| `tests/test_wfo_optimizer.py` | yes | 55 | `7a5cd1a 2026-02-06` |
| `tests/test_performance_tracker_time_buckets.py` | yes | 49 | `-` |

## Change Checks

- Score by executed strategy, not selected_strategy label.
- Keep strict chronological split for hold-out testing.
- Report regime/hour/weekday breakdowns.

## Prompt Primer

Load this file plus `bmad/context/generated/00-index.md`, then keep edits scoped to the file inventory unless interface changes are explicitly required.
