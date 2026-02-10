# Story 8.1: Adaptive Studio Decision-Flow Configurator

Status: done

## Story

As a trading operator,  
I want a dedicated Adaptive Studio tab for configuring adaptive strategy-selection logic,  
so that per-ticker decision flow is visible, editable, and applied on next run start.

## Acceptance Criteria

1. FE has a third top-level tab `Adaptive Studio`.
2. Adaptive Studio loads ticker-specific adaptive config from `/api/aos-config/{ticker}`.
3. Adaptive Studio persists updates through `/api/aos-config/update` without raw JSON editing.
4. Adaptive Studio includes a visual decision-flow diagram.
5. Strategy engine `_select_strategies` uses saved adaptive config (`adaptive.*`) for runtime selection.
6. Saved settings are applied on the next `POST /api/run/start`.

## Tasks / Subtasks

- [x] Add `Adaptive Studio` tab in app shell navigation.
- [x] Implement `AdaptiveStrategyStudio` component with per-ticker load/save flow.
- [x] Implement visual decision-flow diagram + runtime preview in FE.
- [x] Extend strategy-engine AOS config normalization with `adaptive` block.
- [x] Extend `_select_strategies` to honor adaptive macro/micro preferences and flow toggles.
- [x] Add tests for adaptive priority override and flow-bias toggle behavior.
- [x] Validate frontend build, runner/engine tests, and strict context checks.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Completion Notes List

- Added a new `Adaptive Studio` tab in `App.jsx` and routed it as a dedicated full-page view.
- Implemented `/frontend/src/components/AdaptiveStrategyStudio.jsx` with:
  - ticker-aware config loading from `/api/aos-config/{ticker}`,
  - save flow to `/api/aos-config/update`,
  - editable adaptive controls (mode/top-N/flow-bias/fallback + macro/micro ordered preferences),
  - visual decision-flow diagram and runtime preview summary.
- Added adaptive studio styling and responsive behavior in `frontend/src/index.css`.
- Strategy engine now normalizes and stores `adaptive` ticker config and applies it in `_select_strategies`.
- Runner AOS apply payload now preserves `adaptive` block in `aos_applied` for diagnostics.
- Added strategy-engine tests validating adaptive override and flow-bias toggle behavior.

### File List

- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/frontend/src/App.jsx`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/frontend/src/components/AdaptiveStrategyStudio.jsx`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/frontend/src/index.css`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/api_server.py`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/docs/llm/functionality-map.md`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/docs/llm/api-contracts.md`
- `/Users/hotovo/.gemini/antigravity/scratch/market_regime_detection/src/day_trading_manager.py`
- `/Users/hotovo/.gemini/antigravity/scratch/market_regime_detection/tests/test_day_trading_manager_strategy_selection_mode.py`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/_bmad-output/planning-artifacts/adaptive-studio-epic-plan.md`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/_bmad-output/implementation-artifacts/8-1-adaptive-studio-decision-flow-configurator.md`

### Change Log

- 2026-02-09: Implemented Adaptive Studio FE + strategy-engine adaptive selection wiring.
