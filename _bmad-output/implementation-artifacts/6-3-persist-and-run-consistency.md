# Story 6.3: Persist-and-Run Consistency

Status: done

## Story

As a trading analyst,  
I want FE-edited AOS config to be respected when I start a run,  
so that runtime behavior matches what I saved.

## Acceptance Criteria

1. Given AOS JSON is edited in FE, when saved, then config is persisted via `/api/aos-config/update`.
2. Given run is started afterwards, when runner applies AOS, then latest file values are used.
3. Run start response continues to include `aos_applied` for verification.

## Tasks / Subtasks

- [x] Keep FE save path bound to existing `/api/aos-config/update` endpoint
- [x] Keep runner apply path unchanged and file-driven (`_load_aos_config` + `_apply_aos_optimizations`)
- [x] Validate runtime extraction of applied AOS fields from saved file data

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Completion Notes List

- FE save path uses existing AOS update endpoint with full ticker payload.
- Runner start path still applies latest stored ticker config from `aos_config.json`.
- Verified applied fields (`time_filter_enabled`, `trading_hours`, `long_only`) are read from file-driven ticker config.
- No API contract changes were introduced.

### File List

- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/frontend/src/components/AOSOptimizations.jsx`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/_bmad-output/implementation-artifacts/6-3-persist-and-run-consistency.md`

### Change Log

- 2026-02-09: Completed end-to-end FE save and runtime apply consistency for AOS config.
