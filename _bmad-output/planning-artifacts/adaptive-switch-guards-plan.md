# Adaptive Switch Guards Plan (BMAD)

Date: 2026-02-09  
Primary Domain: `strategy-engine`  
Secondary Domains (contract-safe integration): `frontend`, `orchestration`

## Change Goal

Add configurable anti-churn switch guards for adaptive strategy switching and expose them in FE:

- hysteresis/min active time in bars before strategy set can switch,
- cooldown in bars after a switch.

## Scope

### In Scope

- Extend per-ticker adaptive config with:
  - `min_active_bars_before_switch`
  - `switch_cooldown_bars`
- FE (`AdaptiveStrategyStudio`) controls for both values.
- Runtime enforcement in `DayTradingManager._maybe_refresh_regime`.
- Regression tests for min-active and cooldown switch behavior.

### Out of Scope

- New API endpoints.
- Changes to no-lookahead / same-bar execution invariants.
- Strategy signal logic changes.

## Proposed Epic

## Epic 9: Adaptive Switch Stability Controls

Introduce explicit strategy-switch guards to reduce minute-by-minute adaptive oscillation.

### Story 9.1: Hysteresis + Cooldown Guards With FE Controls

As a trading operator,  
I want to configure switch guard thresholds from FE,  
so that adaptive strategy switching is stable and predictable.

Acceptance Criteria:

1. FE exposes `min_active_bars_before_switch` and `switch_cooldown_bars` in Adaptive Studio.
2. Values persist to AOS file through existing `/api/aos-config/update` flow.
3. Strategy engine blocks strategy-set switches until min-active threshold is satisfied.
4. Strategy engine blocks immediate repeated switches inside cooldown window.
5. Test coverage proves blocked and allowed switch scenarios.

## Validation Plan

1. `npm run build`
2. `pytest /Users/hotovo/.gemini/antigravity/scratch/market_regime_detection/tests/test_day_trading_manager_strategy_selection_mode.py`
3. `pytest tests/test_start_run_strategy_overrides_mode.py`
4. `python3 scripts/generate_context_pack.py`
5. `python3 scripts/validate_llm_context.py --strict`

## Risks

1. Overly high guard thresholds can delay legitimate regime response.
2. Poorly tuned thresholds can reduce trade opportunity density.
3. Missing fallback defaults could create ticker-specific drift; defaults must remain deterministic.
