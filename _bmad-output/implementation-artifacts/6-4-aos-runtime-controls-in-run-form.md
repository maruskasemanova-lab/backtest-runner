# Story 6.4: AOS Runtime Controls in Run Form

Status: done

## Story

As a trading analyst,  
I want AOS-relevant controls directly in the run form,  
so that I can tune AOS behavior before run start without opening raw AOS JSON UI.

## Acceptance Criteria

1. Given ticker is selected, when run form loads, then AOS controls are prefilled from `/api/aos-config/{ticker}`.
2. Given user edits AOS controls in run form and starts run, then FE persists updates via `/api/aos-config/update` before `/api/run/start`.
3. Given main FE layout is shown, then raw AOS config panel is not visible.

## Tasks / Subtasks

- [x] Add AOS runtime control group to `RunConfig` (time filter, trading hours, long only, trailing stop)
- [x] Load ticker AOS config into run-form controls on ticker change
- [x] Persist merged ticker AOS config before run start while preserving existing `params` keys
- [x] Remove AOS panel from main app layout
- [x] Validate frontend build

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Completion Notes List

- Added AOS runtime controls into run form and wired them to ticker-level AOS fetch/save APIs.
- Form now persists AOS edits before run start; run then consumes updated file-driven AOS settings.
- Removed AOS component mount from `App` sidebar so raw source-of-truth text is hidden from normal FE workflow.
- Frontend build passed after integration.

### File List

- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/frontend/src/components/RunConfig.jsx`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/frontend/src/App.jsx`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/_bmad-output/implementation-artifacts/6-4-aos-runtime-controls-in-run-form.md`

### Change Log

- 2026-02-09: Added run-form AOS controls and removed raw AOS panel from main layout.
