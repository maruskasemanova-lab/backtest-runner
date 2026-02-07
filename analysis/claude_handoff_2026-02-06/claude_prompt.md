# Prompt for Claude (Cloud Analysis)

Use the attached files to produce a **profitability-focused redesign proposal** for MU intraday flow trading.

## Files to consume
- `mu_internal_diagnostics.json`
- `run_summary.csv`
- `marker_counts.csv`
- `signal_events.csv`
- `trade_events.csv`
- `internal_blockers_report.md`
- `external_us_equity_trends_2026-02-06.md`

## Main objective
Maximize robust expectancy for MU scalping with account ~10k USD and daily target roughly 20-50 EUR equivalent, while keeping tail risk constrained.

## What to answer

1. Root-cause ranking
- Rank top 5 blockers by expected impact on expectancy.
- Distinguish between:
  - signal quality problem,
  - regime classification/churn problem,
  - execution/exit logic problem,
  - observability/data quality problem.

2. Parameter redesign
- Propose a concrete parameter set for:
  - `momentum_flow`, `absorption_reversal`, `exhaustion_fade`
  - multi-layer thresholds/weights
  - L2 confirmation gate
  - regime refresh cadence
  - position sizing and exits
- Explain why each change should improve PnL distribution (not only win rate).

3. Experiment matrix (must be actionable)
- Build a 2-week experiment plan with exact A/B tests.
- For each test define:
  - hypothesis,
  - metric(s),
  - pass/fail threshold,
  - minimum sample size,
  - expected side effects.

4. Trade filtering logic
- Design a filter to avoid weak entries around combined score 58-70.
- Include alternatives (hard cutoff vs conditional cutoff using flow consistency/book pressure).

5. Regime handling
- Propose a low-noise regime policy suitable for 1m bars.
- Suggest whether regime should refresh by bars, volatility trigger, or event trigger.

6. Risk and exits
- Evaluate whether current partial-take-profit on flow deterioration is overactive.
- Propose exit variants and when to use each (trend day vs choppy day).

7. Observability improvements
- Specify additional markers/telemetry needed so future diagnosis is deterministic.
- Include JSON schema fields to add per decision and per rejected signal.

## Constraints
- No look-ahead bias.
- Keep approach implementable in current Python architecture.
- Prefer minimal complexity increase for highest impact.

## Desired output format
- Section A: Executive summary (max 12 bullets)
- Section B: Ranked blockers with evidence table
- Section C: New parameter set (copy-paste JSON)
- Section D: Experiment matrix table
- Section E: Telemetry schema proposal
- Section F: Go/No-Go criteria for production

