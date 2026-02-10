# Story 10.3: Backtest And Studio Profile Consumption

Status: done

## Story

As a trading operator,  
I want to select tuned adaptive profiles directly in backtest and inspect/load them in Adaptive Studio,  
so that tuner outputs are immediately usable in run setup and adaptive editing flows.

## Acceptance Criteria

1. Backtest form shows available tuned profiles for selected ticker.
2. Backtest start can apply selected profile before run start.
3. Adaptive Studio shows tuned profile list and active profile state.
4. Adaptive Studio can load profile candidate values into the editor form.
5. Adaptive Studio can set profile as active for next backtest run.
6. Existing API contracts remain backward compatible.

## Tasks / Subtasks

- [x] Extend `RunConfig.jsx` to load tuned profiles from `/api/adaptive-tuner/options/{ticker}`.
- [x] Add Backtest profile selector with active-profile fallback mode.
- [x] Apply selected profile through `/api/adaptive-tuner/profiles/apply` in run-start flow.
- [x] Extend `AdaptiveStrategyStudio.jsx` with tuned profile list and active badge.
- [x] Add Studio actions for loading candidate knobs and setting active profile.
- [x] Update frontend styling and LLM docs.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Completion Notes List

- Backtest now supports explicit adaptive tuned profile selection per ticker.
- Backtest start flow applies chosen profile first, then starts run with aligned effective adaptive knobs.
- Adaptive Studio now shows saved profiles, active profile id, profile candidate summaries, and two actions:
  - `Load To Editor` (local form update),
  - `Set Active` (persisted for next run via API).
- No API schema changes were required; implementation uses existing tuner options/apply endpoints.

### File List

- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/frontend/src/components/RunConfig.jsx`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/frontend/src/components/AdaptiveStrategyStudio.jsx`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/frontend/src/index.css`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/docs/llm/functionality-map.md`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/docs/llm/api-contracts.md`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/_bmad-output/planning-artifacts/adaptive-profile-consumption-plan.md`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/_bmad-output/implementation-artifacts/10-3-backtest-and-studio-profile-consumption.md`

### Change Log

- 2026-02-09: Implemented profile consumption flow across Backtest and Adaptive Studio.
