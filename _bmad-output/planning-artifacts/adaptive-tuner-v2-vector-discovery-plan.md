# Adaptive Tuner v2 — Multi-Dimensional Vector Discovery Plan (BMAD)

Date: 2026-02-10  
Primary Domain: `orchestration`  
Secondary Domains (contract-safe integration): `strategy-engine`, `frontend`, `optimization-validation`

## Change Goal

Extend Adaptive Tuner from flat 6-dimension v1 search to multi-dimensional v2 vector discovery across strategy×L2×regime×evidence dimensions, enabling discovery of surprising performance relationships invisible to v1.

## Scope

### In Scope

- `AdaptiveTunerRequest` extended with v2 dimensions (strategy sets, L2 thresholds, regime filters, evidence params).
- V2 search space builder deriving defaults from AOS ticker config.
- V2 candidate config injector applying all dimensions to AOS config + strategy API.
- V2 evaluation collecting per-day regime distribution and per-strategy signal counts.
- Vector analysis engine computing dimension importance, interaction effects, and surprising vectors.
- V2 profiles stored in AOS config with `vector_analysis` metadata.
- Full backward compatibility with v1.

### Out of Scope

- Frontend v2 tuner UI (separate story).
- Distributed job execution.
- Changes to core strategy signal logic.
- Adaptive version 3+.

## Proposed Story

### Story AT-V2-01: Adaptive Tuner v2 — Multi-Dimensional Vector Discovery

As a trading operator,  
I want to discover which combinations of strategy + L2 thresholds + regime filter + evidence config produce the best results,  
so that I can find surprising performance vectors and set optimal configurations.

Acceptance Criteria:

1. `AdaptiveTunerRequest` accepts `adaptive_version=2` with strategy/L2/regime/evidence dimension options.
2. V2 search space builds from request options + AOS ticker defaults when options are `None`.
3. V2 candidate config injects all dimensions into AOS config for evaluation.
4. Vector analysis report shows dimension importance scores and top interaction effects.
5. Surprising vectors (high score from non-obvious configs) are flagged in analysis.
6. V2 profiles stored in AOS config with `vector_analysis` metadata.
7. V1 behavior remains fully backward compatible.
8. All existing tests pass without modification.

## Validation Plan

1. `pytest tests/test_adaptive_tuner_api.py -v`
2. `pytest tests/ -v --timeout=60`
3. `python3 scripts/generate_context_pack.py`
4. `python3 scripts/validate_llm_context.py --strict`

## Risks

1. V2 trials are expensive (full backtest each). Users need guidance on practical trial counts.
2. Config injection modifies both AOS config and strategy API state — careful restore-on-failure needed.
3. Vector analysis needs minimum ~30 trials for meaningful statistical conclusions.
