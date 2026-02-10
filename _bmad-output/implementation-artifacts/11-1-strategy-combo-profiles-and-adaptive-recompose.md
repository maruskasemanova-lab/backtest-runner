# Story 11.1: Strategy Combo Profiles And Adaptive Recompose

Status: done

## Story

As a trading operator,  
I want to save and switch strategy parameter combinations from FE and recompose Adaptive Studio around active combinations,  
so that adaptive selection setup remains consistent with the strategy parameter set used in runs.

## Acceptance Criteria

1. FE can capture current strategy settings into named combo profiles per ticker.
2. FE can list and activate saved combo profiles.
3. Active combo profile persists in AOS config and is applied at run start.
4. Adaptive Studio displays strategy combo profiles and active combo id.
5. Adaptive Studio can recompose adaptive preference lists from selected combo.
6. Existing runner/strategy API behavior remains backward compatible.

## Tasks / Subtasks

- [x] Add runner combo endpoints:
  - `GET /api/strategy-combos/{ticker}`
  - `POST /api/strategy-combos/capture`
  - `POST /api/strategy-combos/apply`
- [x] Persist combo profiles in ticker AOS config (`strategy_combo_profiles`, `active_strategy_combo_profile_id`).
- [x] Apply active combo profile params during runner AOS apply stage (`/api/run/start` flow).
- [x] Extend `StrategySettings.jsx` with combo capture/list/apply UI and event dispatch.
- [x] Extend `AdaptiveStrategyStudio.jsx` with combo list/active visibility and recomposition action.
- [x] Add orchestration tests for combo capture/apply API flow.
- [x] Update LLM docs and regenerate/validate context pack.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Completion Notes List

- Added strategy-combo profile storage and lifecycle under ticker AOS config.
- Added combo capture from live strategy API settings (no manual JSON required in FE).
- Added immediate + next-run activation flow for strategy-combo profiles.
- Added Adaptive Studio recomposition action that filters adaptive preference lists to enabled strategies from selected combo.
- Preserved existing endpoints and run/start contracts.

### File List

- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/api_server.py`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/frontend/src/components/StrategySettings.jsx`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/frontend/src/components/AdaptiveStrategyStudio.jsx`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/tests/test_strategy_combo_profiles_api.py`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/docs/llm/functionality-map.md`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/docs/llm/api-contracts.md`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/_bmad-output/planning-artifacts/strategy-combo-adaptive-recomposition-plan.md`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/_bmad-output/implementation-artifacts/11-1-strategy-combo-profiles-and-adaptive-recompose.md`

### Change Log

- 2026-02-09: Implemented strategy-combo profile management and Adaptive Studio recomposition flow.
