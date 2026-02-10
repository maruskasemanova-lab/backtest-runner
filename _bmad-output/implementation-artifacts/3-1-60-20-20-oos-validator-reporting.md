# Story 3.1: 60/20/20 OOS Validator Reporting

Status: done

## Story

As a quant developer,  
I want validator output split into train/validation/test reporting,  
so that I can distinguish tuning performance from hold-out performance.

## Acceptance Criteria

1. Given chronological split logic, when report output is generated, then train/validation/test buckets are present.
2. Given split output, when evaluated, then split boundaries are preserved without leakage.

## Tasks / Subtasks

- [x] Validate existing 60/20/20 split implementation
  - [x] Confirmed `split_dates_chronological(...)` and output sections in `oos_validator.py`.
- [x] Add explicit split regression tests
  - [x] Added `tests/test_oos_validator_split.py`.
- [x] Run regression
  - [x] `PYTHONPATH=. pytest -q tests/test_oos_validator_split.py`

## Dev Agent Record

### Agent Model Used

GPT-5 Codex (CLI)

### Completion Notes List

- Added dedicated unit coverage for chronological split and zero-trade win-rate behavior.

### File List

- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/tests/test_oos_validator_split.py`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/_bmad-output/implementation-artifacts/3-1-60-20-20-oos-validator-reporting.md`

### Change Log

- 2026-02-09: Added split coverage tests and marked story done.
