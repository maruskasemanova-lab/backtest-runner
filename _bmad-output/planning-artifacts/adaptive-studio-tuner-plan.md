# Adaptive Studio Tuner Plan (BMAD)

Date: 2026-02-09  
Primary Domain: `orchestration`  
Secondary Domains (contract-safe integration): `frontend`, `optimization-validation`

## Change Goal

Add a dedicated Adaptive Tuner tab that runs date-range tuning jobs for Adaptive Studio v1 settings, supports grid/random/optuna-style search, and shows ranked trial results in FE.

## Scope

### In Scope

- New top-level FE tab: `Adaptive Tuner`.
- Tuner UI for:
  - ticker + date range,
  - method (`grid`, `random`, `optuna` with fallback),
  - score metric and trial count,
  - v1 search-space controls (selection mode, top-N, min-active, cooldown, flow-bias, fallback).
- New runner endpoints:
  - `POST /api/adaptive-tuner/run`
  - `GET /api/adaptive-tuner/{job_id}`
  - `GET /api/adaptive-tuner`
- Background tuner job execution with day-by-day run scoring.
- Optional persistence of best candidate into `aos_optimization/aos_config.json`.
- FE results view: progress, best candidate, trials table, per-day trial outcomes.

### Out of Scope

- Adaptive version > v1 tuning.
- External/distributed job queue workers.
- Rework of core strategy signal logic.
- Replacement of existing WFO/OOS pipelines.

## Proposed Epic

## Epic 10: Adaptive Studio Tuner (v1)

Enable practical tuning workflows for Adaptive Studio v1 by exposing an interactive FE tuner tied to runner-side search execution.

### Story 10.1: Adaptive Tuner Tab + Job API + Trial Results

As a trading operator,  
I want to run adaptive tuning across selected dates and see ranked candidates,  
so that I can iteratively improve adaptive v1 behavior and optionally persist the best setup.

Acceptance Criteria:

1. App navigation includes a new `Adaptive Tuner` tab.
2. FE can submit tuner jobs with ticker/date range/method/metric/search-space inputs.
3. Backend exposes job start + polling + listing APIs for adaptive tuner jobs.
4. Job execution evaluates candidates over selected dates and computes deterministic score output.
5. FE shows progress, best candidate summary, trials table, and day-level results.
6. `optuna` mode gracefully falls back to random search when package is unavailable.
7. `persist_best=true` writes best v1 candidate to AOS config; otherwise original AOS config is restored.
8. Existing run/start and adaptive behavior remain backward compatible.

## Validation Plan

1. `npm run build`
2. `pytest tests/test_adaptive_tuner_api.py tests/test_start_run_strategy_overrides_mode.py`
3. `python3 scripts/generate_context_pack.py`
4. `python3 scripts/validate_llm_context.py --strict`

## Risks

1. Tuner jobs temporarily mutating AOS file during evaluation can affect concurrently started manual runs.
2. Broad search spaces can make job runtime long on large date ranges.
3. Score choice may favor too-few-trade candidates without domain-specific constraints.
