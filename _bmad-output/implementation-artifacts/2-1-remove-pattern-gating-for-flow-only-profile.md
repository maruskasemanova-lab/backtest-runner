# Story 2.1: Remove Pattern Gating for Flow-Only Profile

Status: done

## Story

As a strategy researcher,  
I want a flow-only operation profile without candlestick pattern gating,  
so that flow strategies can run independently when appropriate.

## Acceptance Criteria

1. Given flow-only profile is enabled, when strategy decisions are evaluated, then candlestick pattern gating does not block flow-driven decisions.
2. Given strategy-only mode, when decision engine runs, then strategy-only operation remains functional.

## Tasks / Subtasks

- [x] Validate evidence-engine path removes legacy pattern dependency
  - [x] Confirmed evidence engine behavior by `tests/test_evidence_engine_no_candlestick.py`.
- [x] Validate marker/schema behavior no longer depends on pattern marker type
  - [x] Confirmed by `tests/test_decision_tracker_pattern_description.py`.
- [x] Run regression for no-lookahead compatibility
  - [x] `PYTHONPATH=. pytest -q tests/test_evidence_engine_no_candlestick.py tests/test_no_lookahead.py`

## Dev Agent Record

### Agent Model Used

GPT-5 Codex (CLI)

### Completion Notes List

- Story requirements already implemented in existing evidence-engine architecture.
- No code modifications required in this pass.

### File List

- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/_bmad-output/implementation-artifacts/2-1-remove-pattern-gating-for-flow-only-profile.md`

### Change Log

- 2026-02-09: Story validated and marked done.
