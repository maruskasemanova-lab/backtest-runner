# Story 4.2: Decision Payload Schema Tests

Status: done

## Story

As a platform engineer,  
I want schema-level tests for decision and marker payloads,  
so that UI and downstream tools are protected from contract regressions.

## Acceptance Criteria

1. Given session runner emits marker/decision payloads, when schema tests execute, then payload structure is validated.
2. Given incompatible schema drift, when tests run, then drift is detected.

## Tasks / Subtasks

- [x] Validate schema test coverage
  - [x] Confirmed `tests/test_decision_tracker_schema_v2.py` and `tests/test_session_runner_markers.py`.
- [x] Execute schema regressions
  - [x] `PYTHONPATH=. pytest -q tests/test_decision_tracker_schema_v2.py tests/test_session_runner_markers.py`

## Dev Agent Record

### Agent Model Used

GPT-5 Codex (CLI)

### Completion Notes List

- Story already implemented; schema-level test coverage exists and passes.

### File List

- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/_bmad-output/implementation-artifacts/4-2-decision-payload-schema-tests.md`

### Change Log

- 2026-02-09: Story validated and marked done.
