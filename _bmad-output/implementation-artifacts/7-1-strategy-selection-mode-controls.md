# Story 7.1: Strategy Selection Mode Controls + Runtime Apply

Status: done

## Story

As a trading analyst,  
I want to configure strategy-selection behavior from FE for each ticker,  
so that run-time strategy evaluation matches selected mode and limits.

## Acceptance Criteria

1. FE run form loads `strategy_selection_mode` and `max_active_strategies` from ticker config.
2. FE persists edited values via `/api/aos-config/update` before `/api/run/start`.
3. Runner forwards effective selection values to `/api/session/config`.
4. Strategy engine enforces:
   - `adaptive_top_n`: cap by `max_active_strategies`
   - `all_enabled`: include all enabled regime-compatible strategies.
5. Existing behavior remains backward compatible when new fields are absent.

## Tasks / Subtasks

- [x] Extend AOS runtime controls in `RunConfig` with strategy-selection fields
- [x] Persist per-ticker strategy-selection settings to AOS config
- [x] Extend runner request/session passthrough with additive selection fields
- [x] Extend strategy engine session defaults + runtime selector logic
- [x] Add regression tests for runner passthrough and strategy-selection behavior
- [x] Validate frontend build

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Completion Notes List

- Added FE controls for `strategy_selection_mode` and `max_active_strategies` in Run Config AOS section.
- FE now persists those values per ticker before run start (same source of truth flow via AOS config file).
- Runner now computes effective selection settings (request override > AOS value > default) and forwards them to strategy `/api/session/config`.
- Strategy engine now supports deterministic selection modes:
  - `adaptive_top_n` capped by configured max
  - `all_enabled` returns all enabled + regime-compatible strategies.
- Added tests covering runner passthrough and selection-mode behavior.

### File List

- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/frontend/src/components/RunConfig.jsx`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/api_server.py`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/tests/test_start_run_strategy_overrides_mode.py`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/aos_optimization/aos_config.json`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/docs/llm/functionality-map.md`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/docs/llm/api-contracts.md`
- `/Users/hotovo/.gemini/antigravity/scratch/market_regime_detection/api_server.py`
- `/Users/hotovo/.gemini/antigravity/scratch/market_regime_detection/src/day_trading_manager.py`
- `/Users/hotovo/.gemini/antigravity/scratch/market_regime_detection/tests/test_day_trading_manager_strategy_selection_mode.py`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/_bmad-output/planning-artifacts/strategy-selection-flow-fe-plan.md`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/_bmad-output/implementation-artifacts/7-1-strategy-selection-mode-controls.md`

### Change Log

- 2026-02-09: Implemented FE-driven strategy-selection mode controls and runtime apply path.
