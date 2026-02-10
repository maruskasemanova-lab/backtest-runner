# Story 3.2: Monte Carlo CI Risk Gate

Status: done

## Story

As a risk owner,  
I want Monte Carlo drawdown thresholds enforced in CI-style execution,  
so that high-risk strategy variants fail fast.

## Acceptance Criteria

1. Given trade sequence inputs, when drawdown distribution is evaluated against threshold, then process emits explicit risk-gate result.
2. Given threshold breach, when process exits, then failure state is signaled.

## Tasks / Subtasks

- [x] Enforce non-zero exit on threshold breach
  - [x] Updated `monte_carlo.py` to exit with status `2` when P95 drawdown breaches configured limit.
- [x] Add risk-gate regression tests
  - [x] Added `tests/test_monte_carlo_risk_gate.py` for breach/non-breach exit behavior.
- [x] Run regression
  - [x] `PYTHONPATH=. pytest -q tests/test_monte_carlo_risk_gate.py`

## Dev Agent Record

### Agent Model Used

GPT-5 Codex (CLI)

### Completion Notes List

- Risk-gate now explicitly fails CI-style execution on breach while preserving explicit console output.

### File List

- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/monte_carlo.py`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/tests/test_monte_carlo_risk_gate.py`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/_bmad-output/implementation-artifacts/3-2-monte-carlo-ci-risk-gate.md`

### Change Log

- 2026-02-09: Implemented non-zero risk-gate exit + regression tests; story marked done.
