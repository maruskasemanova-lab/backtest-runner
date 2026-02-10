# Story 1.2: Time Exit and Adverse Flow Exit Validation

Status: done

## Story

As a strategy researcher,  
I want time exit and adverse-flow exits validated with tests,  
so that exit behavior remains reliable under regression.

## Acceptance Criteria

1. Given a running position with configured time and adverse-flow exits, when exit conditions are reached in simulation, then exit reason is assigned correctly for each condition.
2. Given regression tests covering both exit paths, when test suite runs, then tests pass.

## Tasks / Subtasks

- [x] Validate time-exit path end-to-end
  - [x] Confirmed `test_time_exit_closes_stale_position` in `tests/test_execution_realism.py`.
- [x] Validate adverse-flow path end-to-end
  - [x] Confirmed `test_adverse_flow_exit_closes_against_flow` in `tests/test_execution_realism.py`.
- [x] Execute targeted regression for exit logic
  - [x] `PYTHONPATH=. pytest -q tests/test_execution_realism.py tests/test_no_lookahead.py`

## Dev Agent Record

### Agent Model Used

GPT-5 Codex (CLI)

### Completion Notes List

- Existing implementation and tests already satisfy Story 1.2 acceptance criteria.
- No source-code changes were required for this story in this pass.

### File List

- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/_bmad-output/implementation-artifacts/1-2-time-exit-and-adverse-flow-exit-validation.md`

### Change Log

- 2026-02-09: Story validated against existing tests and marked done.
