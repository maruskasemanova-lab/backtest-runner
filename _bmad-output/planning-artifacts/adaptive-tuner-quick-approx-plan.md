# Adaptive Tuner Quick Approx Mode Plan (BMAD)

Date: 2026-02-10  
Primary Domain: `orchestration`  
Secondary Domains (contract-safe integration): `frontend`, `optimization-validation`

## Change Goal

Add a `quick` tuner option that approximates evaluation by sampling representative days and boosting trial budget, so users can scan more candidate combinations in less wall-clock time.

## Scope

### In Scope

- Extend adaptive tuner request contract with:
  - `quick_mode`
  - `quick_max_days`
  - `quick_trial_boost`
- Quick day sampling from eligible date range (chronology preserved).
- Trial budget scaling in quick mode for both v1 and v2 tuner workers.
- Job/summary metadata showing source-day count vs sampled-day count and effective trial budget.
- FE controls for quick mode and preview of effective trial budget.
- Unit tests for sampling + trial budget + quick API metadata.

### Out of Scope

- Distributed or parallel multi-process tuning engine.
- Intraday bar-level downsampling.
- Any changes to strategy decision logic or execution realism invariants.

## Proposed Story

### Story 12.1: Adaptive Tuner Quick Approx Mode

As a trading operator,  
I want a quick approximation mode for adaptive tuning,  
so that I can explore many combinations faster before running slower full-range confirmation tuning.

Acceptance Criteria:

1. Backend accepts `quick_mode`, `quick_max_days`, and `quick_trial_boost`.
2. When quick mode is on, tuner evaluates sampled representative days from eligible dates.
3. Trial budget is boosted by configured multiplier and reflected in job metadata.
4. FE exposes quick mode toggle and parameters.
5. FE displays effective trial budget and sampled-day metadata in job status.
6. Existing non-quick tuning behavior remains backward compatible.

## Validation Plan

1. `pytest tests/test_adaptive_tuner_api.py -v`
2. `python3 scripts/generate_context_pack.py`
3. `python3 scripts/validate_llm_context.py`
4. `python3 scripts/validate_llm_context.py --strict`
5. `npm run build` (frontend)

## Risks

1. Quick mode may miss date-specific edge cases due to reduced day coverage.
2. Boosted trial counts can still be slow on very broad search spaces.
3. Users may over-trust quick results without full-range confirmation.
