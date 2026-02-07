# Claude Handoff Pack (MU) - 2026-02-06

This folder contains a ready-to-upload analysis pack for cloud review.

## Contents
- `mu_internal_diagnostics.json` - full normalized diagnostics extracted from local MU run artifacts.
- `run_summary.csv` - per-run KPI summary.
- `marker_counts.csv` - marker-type frequencies per run.
- `signal_events.csv` - all signal markers.
- `trade_events.csv` - trade-level enriched metrics (scores, L2, flow snapshot, confidence adjustments).
- `mu_config_snapshot.json` - snapshot of MU AOS config, MU strategy overrides, runtime multilayer config, runtime flow strategy parameters.
- `internal_blockers_report.md` - prioritized internal blocker analysis.
- `external_us_equity_trends_2026-02-06.md` - concise external market trends and implications.
- `claude_prompt.md` - copy-paste prompt for Claude cloud analysis.

## Suggested upload order
1. `internal_blockers_report.md`
2. `external_us_equity_trends_2026-02-06.md`
3. `mu_internal_diagnostics.json`
4. all CSV files
5. `claude_prompt.md`

## Optional
A compressed archive is available at:
- `analysis/claude_handoff_2026-02-06.tar.gz`
