# Story 9.1: Adaptive Switch Guards (Hysteresis + Cooldown)

Status: done

## Story

As a trading operator,  
I want to configure minimum active duration and cooldown for adaptive strategy switches,  
so that strategy selection does not thrash bar-to-bar.

## Acceptance Criteria

1. Adaptive Studio exposes `min_active_bars_before_switch` and `switch_cooldown_bars` controls.
2. FE persists both values to ticker adaptive config via `/api/aos-config/update`.
3. Strategy engine enforces min-active guard before allowing strategy switch.
4. Strategy engine enforces cooldown guard after switch.
5. Tests cover blocked and allowed switch scenarios.

## Tasks / Subtasks

- [x] Extend FE adaptive form model with switch guard fields.
- [x] Add FE controls + save wiring for both fields.
- [x] Extend strategy-engine adaptive config normalization.
- [x] Add runtime switch-guard enforcement in `_maybe_refresh_regime`.
- [x] Add tests for min-active block, cooldown block, and successful switch after thresholds.
- [x] Run build/test/context validation.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Completion Notes List

- Added `min_active_bars_before_switch` and `switch_cooldown_bars` to Adaptive Studio editor and persistence payload.
- Added `last_strategy_switch_bar_index` session tracking in strategy engine.
- Implemented switch-guard logic in `_maybe_refresh_regime`:
  - blocks strategy-set change if min-active bars not reached,
  - blocks strategy-set change during cooldown window,
  - keeps regime refresh cadence and diagnostics payload deterministic.
- Added test coverage for each requested behavior.

### File List

- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/frontend/src/components/AdaptiveStrategyStudio.jsx`
- `/Users/hotovo/.gemini/antigravity/scratch/market_regime_detection/src/day_trading_manager.py`
- `/Users/hotovo/.gemini/antigravity/scratch/market_regime_detection/tests/test_day_trading_manager_strategy_selection_mode.py`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/docs/llm/functionality-map.md`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/docs/llm/api-contracts.md`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/_bmad-output/planning-artifacts/adaptive-switch-guards-plan.md`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/_bmad-output/implementation-artifacts/9-1-adaptive-switch-guards-hysteresis-and-cooldown.md`

### Change Log

- 2026-02-09: Implemented configurable adaptive switch guards with FE controls and tests.
