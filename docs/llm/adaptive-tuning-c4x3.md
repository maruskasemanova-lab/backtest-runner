# Adaptive Tuning Playbook (C4x3)

Deterministic workflow for `MU` adaptive tuning when user asks for:
- "similar to c4"
- "3 independent tunings"
- "better without overfit"

## Goals

1. Preserve c4 momentum edge as baseline reference.
2. Add one choppy/reversal-focused search.
3. Add one balanced multi-regime search.
4. Keep trial scope statistically safer (avoid accidental overfit expansion).

## Mandatory Runtime Rules

1. Run at most `3` tuner jobs in parallel.
2. Use separate `strategy_api_url` ports per parallel job (do not share one port).
3. Keep `quick_mode=true`, `quick_max_days=8`, `quick_trial_boost=1` unless user overrides.
4. Keep `score_metric=robust`, `adaptive_version=2`, `l2_required=true`, `l2_only=true`, `comparable_mode=true`.
5. Use fixed seeds for reproducibility:
- baseline: `42`
- choppy: `113`
- balanced: `271`

## Three Search Profiles

### A) Baseline Momentum Anchor

- Keep c4 spirit: trend-first, low complexity.
- Strategy sets should favor `momentum` and `momentum_flow`.
- Regime maps should mostly skip `CHOPPY` or keep it conservative.

### B) Choppy/Reversal Specialist

- Focus on `exhaustion_fade`, `absorption_reversal`, optional `mean_reversion`.
- Include explicit `CHOPPY` allocations in `regime_strategy_map_sets`.
- Keep stricter evidence and L2 thresholds than baseline.

### C) Balanced Regime Diversifier

- Blend trend + reversal in one search.
- Allow `TRENDING`, `MIXED`, `CHOPPY` with map-conditioned strategy routing.
- Keep moderate complexity; avoid exploding option counts.

## Run Procedure

1. Start/check one backtest-runner instance.
2. Start/check three independent strategy API instances (3 distinct ports).
3. Submit three `POST /api/adaptive-tuner/run` jobs with the profiles above.
4. Poll job status until all are `completed` or `failed`.
5. Compare:
- best score (`robust`)
- consistency (`valid_days`, trade distribution)
- regime behavior in `best_trial.day_results[*].regime_breakdown` when present.
6. Recommend one winner and one fallback profile (do not auto-apply unless requested).

## Safety Gates

1. If any job has `< 8` effective days, mark result as low confidence.
2. If a job runs against shared `strategy_api_url`, flag interference risk.
3. Never overwrite user active profile automatically unless `persist_best=true` was explicitly requested.
