# Story 5.3: Marker Drill-Down for Exit Reasons and Costs

Status: done

## Story

As a trading analyst,  
I want marker drill-down for partial and adverse-flow exits,  
so that I can verify exit behavior and cost attribution.

## Acceptance Criteria

1. Given marker detail view is opened for an exit event, when event is partial or adverse-flow driven, then view includes exit reason and relevant cost components.
2. Given detail interaction, when reviewing exits, then user can inspect details without leaving playback context.

## Tasks / Subtasks

- [x] Validate marker detail rendering for exit reason + cost fields
  - [x] Confirmed in `frontend/src/components/DecisionPanel.jsx` (`Exit Reason`, PnL, costs section, additional details).
- [x] Validate payload schema support
  - [x] Confirmed by `tests/test_decision_tracker_schema_v2.py` and `tests/test_session_runner_markers.py`.
- [x] Verify frontend build
  - [x] `cd frontend && npm run build`

## Dev Agent Record

### Agent Model Used

GPT-5 Codex (CLI)

### Completion Notes List

- Story behavior already present and validated; no additional code change required in this pass.

### File List

- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/_bmad-output/implementation-artifacts/5-3-marker-drill-down-for-exit-reasons-and-costs.md`

### Change Log

- 2026-02-09: Story validated and marked done.
