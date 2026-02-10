# Adaptive Profile Consumption Plan (BMAD)

Date: 2026-02-09  
Primary Domain: `frontend`  
Secondary Domains (contract-safe integration): `orchestration`

## Change Goal

Make saved adaptive tuner profiles directly usable from Backtest and fully inspectable in Adaptive Studio.

## Scope

### In Scope

- Backtest Run Config: expose ticker profile picker using `/api/adaptive-tuner/options/{ticker}`.
- Backtest start flow: optionally apply selected profile via `/api/adaptive-tuner/profiles/apply` before `/api/run/start`.
- Adaptive Studio: show saved profile list, active profile indicator, candidate summary, and actions:
  - load candidate knobs into editor,
  - set profile as active for next backtest.
- Keep existing API contracts and run/start backward compatibility unchanged.

### Out of Scope

- New adaptive candidate schema fields.
- Adaptive v2/v3 tuning logic.
- Strategy-engine internals.

## Proposed Story

### Story 10.3: Backtest + Studio Consumption of Tuned Adaptive Profiles

As a trading operator,  
I want to select tuned adaptive profiles directly in backtest and inspect/load them in Adaptive Studio,  
so that profile tuning outputs are immediately operational in run setup and strategy editing flows.

Acceptance Criteria:

1. Backtest form shows available tuned profiles for selected ticker.
2. Backtest start can apply a selected profile so the run uses that adaptive setup.
3. Adaptive Studio shows tuned profile list with active marker.
4. Adaptive Studio can load profile candidate knobs into editor without immediate save.
5. Adaptive Studio can apply a profile as active for next run.
6. Existing run/start contract remains backward compatible.

## Validation Plan

1. `npm run build`
2. `python3 scripts/generate_context_pack.py`
3. `python3 scripts/validate_llm_context.py --strict`
