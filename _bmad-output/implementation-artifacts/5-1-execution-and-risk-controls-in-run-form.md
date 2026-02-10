# Story 5.1: Execution and Risk Controls in Run Form

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a trading analyst,  
I want execution and risk controls available in the run form,  
so that I can configure run realism directly from the UI.

## Acceptance Criteria

1. Given the run configuration form is displayed, when user edits execution or risk fields, then controls map 1:1 to `/api/run/start` execution configuration.
2. Given the run configuration form is displayed, when a run is submitted, then payload reflects chosen values.

## Tasks / Subtasks

- [x] Validate and preserve existing execution/risk form mapping to runner start payload (AC: 1, 2)
  - [x] Verified `RunConfig` execution/risk fields remain exposed and passed in start payload.
  - [x] Verified no breaking changes to `/api/run/start` request structure from FE changes.
- [x] Integrate AOS controls into active FE layout to complete frontend-side run configurability (AC: 1, 2)
  - [x] Wired `AOSOptimizations` panel into main sidebar in `App.jsx`.
  - [x] Ensured panel uses runner AOS API (`/api/aos-config`, `/api/aos-config/update`) even when strategy API URL is set to port `8001`.
  - [x] Normalized persisted AOS ticker payload shape (`params.long_only`, `params.trailing_stop_pct`, `trading_hours`, `time_filter_enabled`) to stay compatible with existing backend merge semantics.
  - [x] Added advanced JSON editor for full per-ticker AOS config editing in FE, persisted via existing `/api/aos-config/update` contract.
- [x] Run targeted validation for FE and BMAD context integrity
  - [x] Built frontend bundle successfully.
  - [x] Re-generated context pack and validated in strict mode.

## Dev Notes

- Primary domain: `frontend`
- This story completion includes the requested AOS FE integration so AOS knobs are operable directly in UI (instead of API/file-only flow).
- Scope intentionally kept within existing contracts and current epic boundaries (no backend API changes introduced).

### References

- Story source and acceptance intent: `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/_bmad-output/planning-artifacts/epics.md`
- Original epic definition: `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/bmad/backlog/epic-tracks.md`
- UX alignment note: `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/_bmad-output/planning-artifacts/ux-minimal-fe-stories.md`
- Invariants and validation expectations: `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/docs/llm/invariants-and-validation.md`

## Dev Agent Record

### Agent Model Used

GPT-5 Codex (CLI)

### Debug Log References

- Build command: `cd /Users/hotovo/.gemini/antigravity/scratch/backtest-runner/frontend && npm run build`
- Context generation: `cd /Users/hotovo/.gemini/antigravity/scratch/backtest-runner && python3 scripts/generate_context_pack.py`
- Context validation: `cd /Users/hotovo/.gemini/antigravity/scratch/backtest-runner && python3 scripts/validate_llm_context.py`
- Strict validation: `cd /Users/hotovo/.gemini/antigravity/scratch/backtest-runner && python3 scripts/validate_llm_context.py --strict`

### Completion Notes List

- AOS panel is now rendered in the active app layout and bound to selected ticker context.
- AOS FE persistence now preserves and updates existing nested config shape used by backend apply logic.
- Full per-ticker AOS configuration is now editable from FE through an Advanced JSON editor (without backend contract changes).
- Existing run-form execution/risk payload mapping remains intact; no contract delta required.
- Frontend build and BMAD context validation (including strict mode) passed.
- Functional Verification: PASS (AOS panel mounted, granular controls + advanced JSON save path, frontend build green).

### File List

- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/frontend/src/App.jsx` (updated AOS panel mount in sidebar)
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/frontend/src/components/AOSOptimizations.jsx` (normalized controls + advanced JSON editor for full ticker config persistence)
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/_bmad-output/implementation-artifacts/5-1-execution-and-risk-controls-in-run-form.md` (new story artifact)
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/_bmad-output/implementation-artifacts/sprint-status.yaml` (updated story/epic statuses)
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/_bmad-output/implementation-artifacts/story-index.md` (updated story index)

### Change Log

- 2026-02-09: Implemented FE AOS panel integration and captured completion in BMAD implementation artifacts for Story 5.1.
- 2026-02-09: Added full per-ticker Advanced JSON AOS editing in FE and marked functional verification PASS.
