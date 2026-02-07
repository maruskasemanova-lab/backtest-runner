# MU Profitability Blockers (Internal Diagnostics)

Generated: 2026-02-06 UTC
Scope: local artifacts `mu_*.json`, `mu_*trades*.csv`, current config in `aos_optimization/aos_config.json`, runtime behavior in `market_regime_detection/src/day_trading_manager.py`.

## Executive Signal
- The system is no longer "no-trade", but still too unstable for consistent daily scalping.
- Main problem is not one setting only; it is a stack interaction: **regime churn + weak-signal entries near threshold + aggressive online confidence penalty + exit behavior clipping winners**.

## Key Facts
- Runs analyzed: 10
- Runs with trades: 5
- Total trades: 12
- Aggregate PnL across these artifacts: **-140.78 USD**
- Mean signal-to-pattern conversion: **0.98%** (very sparse signal extraction)
- MU day 2026-02-03 still mostly loses (3 trades, -58.77 USD)
- MU day 2026-02-04 can win (2 trades, +77.60 USD), so strategy can work in specific flow conditions.

## Strong Evidence of Blockers

### 1) Borderline confidence trades are net negative
From `trade_events.csv` / `mu_internal_diagnostics.json`:
- Combined score bucket `58-70`: 2 trades, 0 wins, **-124.94 USD** total.
- Combined score bucket `>70`: 6 trades, 4 wins, **+85.00 USD** total.

Interpretation:
- Signals that barely pass threshold (e.g. 58.5 vs 58.0) are low quality and dominate losses.
- Current thresholding allows too many marginal flow entries.

### 2) Regime refresh is too jumpy for 1m scalping
From run markers:
- 2026-02-03: 16 regime detections, 15 regime transitions.
- 2026-02-04: 18 regime detections, 17 regime transitions.

Interpretation:
- Macro regime flips every ~10-12 bars create strategy context instability.
- Even if flow strategy is selected, supporting context and thresholds keep changing intra-session.

### 3) Online edge penalty is too aggressive at low sample size
Observed in `signal_metadata.confidence_adjustment`:
- After first loser, second signal gets `edge_adjustment = -12` (hard floor).

Code reference:
- `day_trading_manager.py::_strategy_edge_adjustment` clamps adjustment to `[-12, +12]` and applies early.

Interpretation:
- One trade can heavily suppress next signals before statistical significance exists.
- This can kill valid follow-up opportunities.

### 4) Exit logic cuts upside too quickly in mixed flow
From 2026-02-03/04 trades:
- Partial exits triggered by `partial_take_profit_flow_deterioration` occur very quickly.
- Holding times often short (0-5 min on losing day).

Interpretation:
- In choppy/mixed tapes this is protective, but may over-trim expectancy when trend resumes.
- On bad day, stop-loss dominates; on good day, one large winner rescued PnL.

### 5) Observability gaps make diagnosis harder
- `strategy_selected` markers often miss rich details (selected strategy breakdown not persisted).
- `regime_detected` marker details do not consistently include micro-regime field.

Interpretation:
- Hard to attribute misses to exact gate (regime, multilayer, l2 confirmation, ranking) post-run.

### 6) Data coverage gap can silently block evaluation days
- `mu_2026-02-05.json` failed with `No data available for the specified date/range`.

Interpretation:
- Validation can be biased by missing OHLC window alignment even when L2 exists.

## What likely blocks profitability most (ranked)
1. Weak entries near threshold (`combined 58-70`) with poor expectancy.
2. Regime churn frequency on 1m bars creating context noise.
3. Early over-penalization via `edge_adjustment=-12` after tiny sample.
4. Exit rules asymmetry (fast de-risking + stop concentration) reducing right-tail capture.
5. Missing-day data pipeline checks reducing OOS reliability.

## Concrete Hypotheses to test next (for Claude)
1. Enforce a higher quality floor for flow entries:
   - `combined_score >= 65` OR `strategy_score >= 72` when no strong pattern.
2. Slow regime refresh during active session:
   - test `regime_refresh_bars`: 12 -> 24/30.
3. Warmup edge adjustment:
   - disable edge adjustment for first N trades per strategy (e.g. N=5), then ramp to full.
4. Tighten directional alignment for momentum flow:
   - require signal direction consistency with recent `price_change_pct` sign or micro-regime.
5. Exit policy variants:
   - compare current partial-flow-deterioration vs delayed partial (min hold bars / min R multiple).
6. Add diagnostics marker for every rejected candidate with exact gate reason.

## Files Included for Analysis
- `mu_internal_diagnostics.json`
- `run_summary.csv`
- `marker_counts.csv`
- `signal_events.csv`
- `trade_events.csv`

