# Functionality Map

End-to-end behavior map across `backtest-runner` and `market_regime_detection`.

## System Topology

- Runner API (`backtest-runner`, port `8002`): run lifecycle, bar playback, data loading, WebSocket fanout.
- Strategy API (`market_regime_detection`, port `8001`): session processing, regime/strategy decisions, trade lifecycle, learning state.
- Frontend (`frontend`, port `5173`): controls, charts, marker timeline, diagnostics.

## Core Runtime Flow

1. Client calls `POST /api/run/start` on runner.
2. Runner resolves data, conditionally applies ticker strategy overrides (`apply_ticker_overrides_on_start`), applies AOS config (including per-ticker strategy-selection mode plus active unified profile when present, otherwise legacy strategy-combo + adaptive profile paths), applies optional run-level session scope override (`include_extended_hours`), optional L2 enrichment.
3. Runner configures strategy session via `POST /api/session/config` (risk/L2 + strategy-selection settings, plus optional profile runtime overrides like daily-trade cap and MU choppy hard-block switch).
4. Runner creates `SessionRunner` and stores it in active run registry.
5. On `step/play`, runner sends each bar to strategy `POST /api/session/bar`.
6. When intrabar execution mode is enabled, runner may attach 1-second intrabar top-of-book quotes for that minute (`intrabar_quotes_1s`) on each processed bar to support entry/exit logic.
7. Strategy returns decision payload; runner maps it to markers and summary state.
8. Runner broadcasts bar + decision updates over `/ws/live`.
9. Frontend consumes updates and renders timeline/summary.

## SaaS V2 Flow (Auth + Quotas)

1. Client calls `/api/v2/auth/me` and `/api/v2/usage` with Bearer JWT.
2. Runner resolves effective plan tier (`free|premium|admin`) and enforces req/min throttling.
3. Client submits `POST /api/v2/runs`; backend enforces concurrent-run and date-range limits.
4. v2 run request is queued as async job; client polls `GET /api/v2/jobs/{job_id}`.
5. Optional `Idempotency-Key` deduplicates repeated submit calls and reuses the original `job_id`.
6. Heavy jobs are retried with bounded attempts/backoff for transient failures, and queued jobs can be resumed from job polling if worker task was interrupted.
7. Global queued-heavy backlog is bounded (`BACKTEST_V2_MAX_QUEUE_BACKLOG`) to protect API process memory.
8. Non-admin v2 requests always route strategy calls to internal strategy API URL.
9. Heavy background tasks (`v2/runs`, `v2/adaptive-tuner/run`, `v2/data/download`) share the same concurrency budget per user.
10. Stripe webhook lifecycle keeps PREMIUM through `cancel_at_period_end` and optional payment-failure grace window, then downgrades to FREE automatically.
11. Rollout hardening: optional `invite-only beta` gate for authenticated users and optional heavy-op kill switch for incident response.
12. Retention control: per-plan retention is enforced by backend cleanup of terminal DB rows so FREE tier does not accumulate unbounded historical state.
13. Admin operations can query `/api/v2/ops/metrics` to watch queue saturation, HTTP latency/error trends, websocket load, and SaaS DB growth.
14. Adaptive strategy profiles are multi-tenant: each user manages personal profiles while superuser/admin can publish global profiles.
15. Large diagnostic JSON reads can be cached in SaaS store and optionally queried via compact summary mode (`summary_only=true`) to reduce heavy payload reads.
16. Frontend can persist user-scoped UI draft settings (for example run ticker/date/profile draft) via `/api/v2/user/settings` (`GET`/`PUT`) when authenticated; backend stores them in SQLite by default or Supabase Postgres when external settings adapter is enabled.
17. Optional remote market-data manifest (`BACKTEST_REMOTE_MANIFEST_URL`) can hydrate catalog entries from object storage (e.g. R2) via `https://...` or `s3://...`; remote files are pulled lazily to `BACKTEST_REMOTE_CACHE_DIR` when selected for run data resolution.
18. Run-report history is store-backed in both prod and local runtimes: Supabase `run_summaries` when configured, otherwise local SQLite `run_summaries`; filesystem `reports/` artifacts are used only when no run-reports store is configured.

## Session And State Model

- Runner key: `run_id:ticker:date_or_range`.
- Strategy session keying: `run_id + ticker + date`.
- Checkpoint behavior:
- warm start: load checkpoint + session-scoped reset
- cold start: full reset
- comparable mode: forced cold start and checkpoint ignored

## L2 Pipeline Map

1. Raw L2 files resolved by `src/l2_data_manager.py`.
2. Optional precomputed minute feature maps loaded from `BACKTEST_L2_PRECOMPUTED_DIR` when available.
3. Fallback order-flow feature computation in `src/order_flow_engine.py` when precomputed data is unavailable.
4. Optional intrabar second-level artifacts built by `src/intrabar_frame_builder.py`.
5. 1s -> 1m aggregation/sanity in `src/l2_feature_aggregator.py`.
6. Features attached to runner bars via `src/l2_feature_service.py`.
7. Optional execution-time intrabar quote replay (`intrabar_quotes_1s`) is loaded lazily per-minute and sent on each processed bar when intrabar mode is enabled.
8. Optional sessionized daily reset for cumulative L2 metrics in runner API.

## Strategy Engine Internals

- `day_trading_manager.py`: main session logic, execution realism, exits, risk controls.
- Adaptive strategy switching supports config-driven switch guards (`min_active_bars_before_switch`, `switch_cooldown_bars`) from AOS ticker config.
- `evidence_decision.py`: evidence-based execution scoring (strategy + L2/feature context).
- `multi_layer_decision.py`: shared `DecisionResult` contract for downstream payload compatibility.
- `trading_orchestrator.py`: learning state and cross-session adaptation.
- `feature_store.py`, `ensemble_combiner.py`, `edge_monitor.py`, `checkpoint.py`: feature memory, calibration, edge health, persistence.

## Optimization/Validation Flow

- `wfo_optimizer.py`: rolling search across parameter grids, with optional parallel strategy execution mode (`--parallel-all-strategies` => `all_enabled` selection).
- `oos_validator.py`: strict chronological split (train/validation/test).
- `walk_forward_runner.py`: date-range simulation + report generation, with optional all-strategy parallel selection (`--parallel-all-strategies` or explicit `--strategy-selection-mode` / `--max-active-strategies`).
- `monte_carlo.py`: drawdown distribution/risk gate from trade PnL sequences.
- Runner adaptive tuner (`POST /api/adaptive-tuner/run`): date-range candidate search for adaptive v1/v2 controls with grid/random/optuna modes, optional L2-only date filtering, optional momentum-diversification dimensions (L2/CVD-aware momentum gating + fail-fast), and optional best-candidate persistence.
- Runner adaptive tuner quick mode: optional approximate tuning path that samples representative days and boosts trial budget so more candidate combinations can be screened faster.

## Frontend Behavioral Ownership

- `App.tsx`: orchestration of controls + data fetches + socket handling.
- `RunConfig.tsx`: run/session execution parameters, including optional selection of one saved unified profile (rendered as `Strategy profile` and `Execution profile` tabs, applied before next run start), optional pre/post-market inclusion toggle (`include_extended_hours`), and optional momentum-diversification override (`single` or `sleeves[]` multi-sleeve JSON).
- `RunConfig.tsx`: preserves draft form state across sidebar collapse/remount and page reload via local browser storage (`backtest_runner.run_config_draft.v2`), and when signed-in syncs that draft to `/api/v2/user/settings` so ticker/date/profile intent is restored per user.
- `main.tsx` + `auth/supabaseAuth.ts`: Supabase-backed Google OAuth bootstrap (`/auth/callback`) with JWT token sync into `backtest_jwt`/`supabase_jwt` keys used by v2 API requests (`VITE_SUPABASE_PUBLISHABLE_KEY`, legacy fallback `VITE_SUPABASE_ANON_KEY`, optional `VITE_SUPABASE_OAUTH_REDIRECT_URL` override for proxied/public-origin deploys).
- `DecisionPanel.tsx`: marker timeline and explanation details.
- `CandlestickChart.tsx` + related components: visual representation of bars/markers.
- `StrategySettings.tsx`: strategy toggles + per-strategy parameter editing with capture/apply strategy-combination profiles per ticker, including per-strategy `exit_mode|risk_mode` (`custom|global`), built-in entry/exit rule visibility, and optional custom formula rules (`custom_entry_formula*`, `custom_exit_formula*`) for user-defined entry/exit gating.
- `AdaptiveStrategyStudio.tsx`: adaptive selection-flow editor with Global Modules execution controls; saves adaptive fields plus execution `positioning` snapshot to `aos_config.json` via `/api/aos-config/update` for next-run apply, with tuned-profile list/load/apply actions and strategy-combination-aware recomposition.
- `AdaptiveTuner.tsx`: adaptive v1 tuner UI tab with real OHLCV/L2 coverage ranges, date-range trial execution, scored candidate ranking, saved tuned profile list, and apply-to-backtest action.
- `AdaptiveTuner.tsx` quick approximation controls: optional sampled-day tuning (`quick_mode`) with configurable `quick_max_days` and `quick_trial_boost`.
- `LiveTraderMonitor.tsx`: live stream monitor tab that reads realtime trader artifact streams (`runtime|decisions|signals|orders`) via runner API.

For concrete file ownership and symbol inventory, use generated domain packs.
