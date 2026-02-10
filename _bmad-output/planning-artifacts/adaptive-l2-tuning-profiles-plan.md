# Adaptive L2 Tuning Profiles Plan (BMAD)

Date: 2026-02-09  
Primary Domain: `orchestration`  
Secondary Domains (contract-safe integration): `frontend`, `optimization-validation`

## Change Goal

Make Adaptive Tuner explicitly L2-aware: show only real ticker coverage for tuning, store tuned adaptive profiles, and allow direct profile apply for next backtest runs.

## Scope

### In Scope

- Ticker-level tuner coverage endpoint based on real local catalog:
  - OHLCV range
  - L2 range
  - OHLCV+L2 overlap range and day list
- L2-required date filtering for adaptive tuner jobs.
- Save best-trial profile metadata in ticker AOS config.
- FE section listing saved adaptive tuned profiles per ticker.
- FE action to apply selected profile for backtest (`next /api/run/start`).

### Out of Scope

- Adaptive version 2+ tuner flows.
- Distributed job queue/persistence for in-memory job history.
- New strategy-engine internals.

## Proposed Story

### Story 10.2: L2 Coverage-Gated Tuning + Profile Apply Flow

As a trading operator,  
I want adaptive tuning to run only on real OHLCV+L2 covered dates and keep reusable tuned profiles,  
so that I can tune on valid data and apply chosen profiles directly to backtests.

Acceptance Criteria:

1. FE shows real OHLCV/L2/overlap coverage for selected ticker.
2. L2-required tuner mode evaluates only overlap days from requested range.
3. Completed tuner run stores best-trial profile in ticker AOS config.
4. FE lists saved adaptive tuned profiles for ticker.
5. FE can apply a selected profile for next backtest run.
6. Existing `/api/run/start` behavior remains backward compatible.

## Validation Plan

1. `pytest tests/test_adaptive_tuner_api.py tests/test_start_run_strategy_overrides_mode.py`
2. `npm run build`
3. `python3 scripts/generate_context_pack.py`
4. `python3 scripts/validate_llm_context.py --strict`
