# Strategy Combo + Adaptive Recomposition Plan (BMAD)

Date: 2026-02-09  
Primary Domain: `frontend`  
Secondary Domains (contract-safe integration): `orchestration`, `strategy-engine`

## Change Goal

Enable configurable strategy parameter combinations from FE and make Adaptive Studio able to recompose adaptive preferences using those combinations.

## Scope

### In Scope

- Runner API support for strategy combination profiles per ticker:
  - list combos,
  - capture current strategy API settings as combo,
  - set combo active (and optional immediate apply).
- Persist combo profiles in ticker AOS config.
- Apply active combo profile automatically in runner `/api/run/start` AOS apply stage.
- FE Strategy panel support to:
  - capture current strategy settings as named combo,
  - list saved combos,
  - set selected combo active.
- Adaptive Studio support to:
  - show active strategy combo,
  - list saved combos,
  - trigger adaptive preference recomposition from selected combo.

### Out of Scope

- Strategy-engine model redesign.
- Adaptive version 2+ tuning redesign.
- Distributed combo storage.

## Proposed Epic

## Epic 11: Strategy Combination Profiles + Adaptive Studio Recomposition

Allow strategy parameter combinations to be captured and reused across runs while keeping Adaptive Studio aligned to enabled strategy sets.

### Story 11.1: Capture/Apply Strategy Combos + Recompose Adaptive Studio

As a trading operator,  
I want to save and switch strategy parameter combinations from FE and recompose Adaptive Studio around active combinations,  
so that adaptive selection setup stays consistent with the strategy parameter set I actually run.

Acceptance Criteria:

1. FE can capture current strategy settings into a named combo profile per ticker.
2. FE can list and activate saved combo profiles.
3. Active combo profile is persisted in AOS config and applied during next run start.
4. Adaptive Studio shows combo profiles and active combo id.
5. Adaptive Studio can recompose preference lists from selected combo enabled strategies.
6. Existing run/start and strategy update contracts remain backward compatible.

## Validation Plan

1. `pytest -q tests/test_strategy_combo_profiles_api.py tests/test_adaptive_tuner_api.py tests/test_start_run_strategy_overrides_mode.py`
2. `npm run build`
3. `python3 scripts/generate_context_pack.py`
4. `python3 scripts/validate_llm_context.py --strict`
