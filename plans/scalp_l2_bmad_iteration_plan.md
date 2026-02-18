# Scalp L2 BMAD Iteration Plan

## Domain
- Primary: `optimization-validation`
- Touchpoints: `data-l2`, `strategy-engine`

## Objective
- Improve `scalp_l2_intrabar` robustness without overfit.
- Keep fee-aware evaluation and compare regular vs extended session impact.

## Phase 0 - Inputs
- Video transcript extraction from user-provided YouTube links:
  - `reports/youtube_transcripts_raw.json`
  - `reports/youtube_transcript_keyword_scan.json`
- Current combo baseline:
  - `mu_scalp_intrabar_fee_v1`

## Phase 1 - Baseline Diagnostics
- Run baseline on short windows (1 day each) in `intrabar_5s`.
- Record:
  - `total_pnl_pct`, `total_trades`, `win_rate_pct`
  - `entry_volume_ratio_vs_median`
  - runtime (`elapsed_sec`)

## Phase 2 - Parameter Stress Tests
- Keep strategy set fixed (scalp-only enabled via combo).
- Stress families:
  - Flow loosen/tighten
  - Volume participation/coverage gates
  - Spread/cost strictness
- Use single-day A/B checks first, then promote only survivors.

## Phase 3 - Robustness Gate
- Gate before accepting candidate:
  - Non-negative PnL on at least 2 distinct days
  - No catastrophic trade count collapse (unless explicitly intended)
  - Stable fee-aware expectancy (`avg_pnl_pct` not dominated by one outlier)

## Phase 4 - Session Scope Check
- Compare `include_extended_hours=false` vs `true` for winner.
- Accept extended hours only if:
  - incremental edge is positive and
  - runtime/trade-noise penalty is justified.

## Phase 5 - Roll-forward
- Expand from 1-day checks to 2-3 day windows only for winners.
- Keep holdout days untouched until finalist stage.
- Archive run artifacts to `reports/` with deterministic naming.

## Current artifacts
- `reports/scalp_l2_research_quick.json`
- `reports/scalp_l2_research_quick_v2.json`
- `reports/scalp_l2_research_volume_only.json`
- `reports/scalp_l2_research_loose_only.json`
- `reports/scalp_l2_research_intrabar_compare.json`
- `reports/scalp_l2_research_baseline_extended_check.json`

