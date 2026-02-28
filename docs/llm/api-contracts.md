# API Contracts

Contract summary for runner, strategy, and cross-service coupling.

## Runner API (Port 8002) - Key Contracts

### `GET /api/v2/auth/me` / `GET /api/v2/plans` / `GET /api/v2/usage`

Purpose: v2 SaaS auth/profile/limits surface for multi-tenant clients.

Auth contract:

- `Authorization: Bearer <JWT>` is required for all `/api/v2/*` endpoints except Stripe webhook.
- JWT verification uses `BACKTEST_JWT_SECRET` (fallback `SUPABASE_JWT_SECRET`).
- dev override: `BACKTEST_ALLOW_UNVERIFIED_JWT=1` allows payload decode without signature check.
- optional invite-only rollout gate: when `BACKTEST_INVITE_ONLY_BETA=1`, non-admin users must match one allowlist (`BACKTEST_INVITE_ALLOWLIST_USERS|TENANTS|EMAILS`) or receive `403 invite_only_beta`.

Response notes:

- v2 responses include `request_id`, `tenant_id`, `plan_tier`, and quota context.
- quota snapshots expose per-plan limits (`concurrent_runs`, `max_range_days`, `req_per_min`, `retention_days`).
- retention is hard-enforced server-side: terminal `runs/jobs` and old usage rows beyond `retention_days` are pruned during authenticated v2 traffic (active/queued records are preserved).

### `GET /api/v2/user/settings` / `PUT /api/v2/user/settings`

Purpose: persist authenticated user UI preferences/drafts as JSON settings on runner side.

Behavioral notes:

- settings are user-scoped (keyed by authenticated `user_id`); cross-user reads/writes are isolated.
- `GET` returns full settings object (`{}` when missing).
- `PUT` accepts `{ "settings": { ... } }` and merges top-level keys into existing settings.
- payload must remain JSON-serializable and is size-limited to `262144` bytes.
- current frontend integration stores run draft under `settings.run_config_draft` (ticker/date/profile intent).
- storage backend:
  - default: local SQLite (`user_settings` table in SaaS state DB).
  - optional prod: Supabase PostgREST adapter when `BACKTEST_SUPABASE_USER_SETTINGS_ENABLED=1` and backend has `BACKTEST_SUPABASE_URL` + `BACKTEST_SUPABASE_SERVICE_ROLE_KEY`.

### `GET /api/v2/datasets` / `GET /api/v2/datasets/{dataset_id}` / `POST /api/v2/datasets` / `DELETE /api/v2/datasets/{dataset_id}`

Purpose: persist authenticated user dataset metadata for private object-storage-backed uploads.

Behavioral notes:

- dataset rows are user-scoped (owned by authenticated `user_id`); non-admin callers cannot read or mutate another user’s dataset metadata.
- `GET /api/v2/datasets` lists caller-owned rows only and supports optional `status` filter plus bounded `limit`.
- `POST` accepts dataset metadata (`dataset_name`, optional `source_filename`, `s3_path`, `status`, `file_format`, `source_format`, `row_count`, `size_bytes`, `schema_name`, `metadata`).
- when `dataset_id` is omitted, backend generates `ds_<uuidhex>`.
- when `s3_path` is omitted, backend derives a default object key:
  - `s3://<BACKTEST_USER_DATASETS_BUCKET>/users/{user_id}/datasets/{dataset_id}.{file_format}` when `BACKTEST_USER_DATASETS_BUCKET` is set.
  - `users/{user_id}/datasets/{dataset_id}.{file_format}` when the bucket env is unset.
- storage backend:
  - default: local SQLite (`user_datasets` table in SaaS state DB).
  - optional prod: Supabase PostgREST adapter when `BACKTEST_SUPABASE_USER_DATASETS_ENABLED=1` and backend has `BACKTEST_SUPABASE_URL` + `BACKTEST_SUPABASE_SERVICE_ROLE_KEY`.

### `POST /api/v2/datasets/upload/csv`

Purpose: ingest a user-uploaded CSV payload, convert it to parquet, and upsert dataset metadata in one request.

Behavioral notes:

- request body is the raw CSV payload (no multipart dependency); metadata is passed as query params (`dataset_name` required, optional `dataset_id`, `source_filename`, `schema_name`, `delimiter`, `encoding`).
- upload size is guarded by `BACKTEST_USER_DATASET_UPLOAD_MAX_BYTES` (default `26214400` bytes).
- backend converts CSV -> parquet and stores a local cache copy under `BACKTEST_USER_DATASETS_LOCAL_CACHE_DIR`.
- storage mode is controlled by `BACKTEST_USER_DATASETS_STORAGE_MODE`:
  - `auto` (default): localhost/testserver uses local cache only; non-local hosts use remote mode when a bucket is configured, otherwise they fall back to local cache.
  - `local`: always local cache only.
  - `remote`: always attempt remote object-storage upload.
- in remote mode, backend uploads the parquet object when `BACKTEST_USER_DATASETS_BUCKET` resolves to an `s3://...` locator (or bucket name) using `BACKTEST_USER_DATASETS_S3_*` creds when set, otherwise falling back to existing `BACKTEST_REMOTE_S3_*` creds.
- forced `remote` mode without a configured bucket is rejected with `503 dataset_storage_unavailable` instead of silently writing local-only metadata.
- in local mode, the logical dataset path remains `users/{user_id}/datasets/{dataset_id}.parquet` and metadata records the local cache path plus `storage_mode=local_cache`.

### `GET /api/v2/ops/metrics`

Purpose: admin-only operational metrics for queue pressure, runtime HTTP health, and local SaaS DB footprint.

Behavioral notes:

- requires admin role (`role=admin` or `plan_tier=admin`); non-admin callers receive `403 forbidden`.
- queue payload includes `queued|running|completed|failed` heavy-job counters plus backlog utilization and heavy-job fail-rate.
- websocket payload includes active client count vs max configured capacity.
- runtime payload proxies in-process HTTP telemetry snapshot (`p50/p95` latency, 5xx error rate).
- storage payload exposes current SaaS DB path/existence/size for quick operational checks.

### `GET /api/v2/strategies/adaptive` / `POST /api/v2/strategies/adaptive` / `DELETE /api/v2/strategies/adaptive/{profile_id}`

Purpose: multi-tenant adaptive strategy profile storage with per-user and superuser-global scopes.

Behavioral notes:

- profile scope:
  - `user`: owned by authenticated user (default).
  - `global`: superuser/admin only.
- non-admin callers cannot create/update/delete `global` profiles.
- list endpoint returns caller-owned user profiles and (optionally) global profiles.
- delete endpoint enforces ownership (`user` owner or admin).
- payload fields include `ticker`, `profile_name`, `adaptive_version`, `candidate`, `metadata`.

### `POST /api/v2/runs` / `GET /api/v2/jobs/{job_id}`

Purpose: authenticated run orchestration with quota enforcement and async job polling.

Behavioral notes:

- run start is queued and returned as `job_id` (status `queued|running|completed|failed`).
- optional `dataset_id` lets authenticated callers run against a previously registered `user_datasets` parquet instead of the default OHLCV range resolver.
- when `dataset_id` is supplied, backend resolves it synchronously during `POST /api/v2/runs`, enforces ownership, and injects the local parquet cache path into `data_file`.
- local mode (`BACKTEST_USER_DATASETS_STORAGE_MODE=local`, or `auto` on localhost/testserver): runs use only the local parquet cache (`BACKTEST_USER_DATASETS_LOCAL_CACHE_DIR` or recorded `metadata.ingest.local_cache_path`).
- object-storage mode (`remote`, or `auto` on non-local hosts): when the local cache is missing, backend attempts to hydrate the parquet into local cache before queueing.
  - `s3://...` hydration uses `BACKTEST_USER_DATASETS_S3_*` creds (fallback `BACKTEST_REMOTE_S3_*`) and requires `boto3` in the backend runtime.
  - `http(s)://...` hydration is supported as read-only remote fetch using `BACKTEST_USER_DATASETS_REMOTE_TIMEOUT_SEC` (fallback `BACKTEST_REMOTE_TIMEOUT_SEC`).
- if neither local cache nor remote hydration is available, the request fails before queueing.
- optional `Idempotency-Key`/`X-Idempotency-Key` request header deduplicates repeated submissions and returns original `job_id` (`idempotent_replay=true`).
- queue dispatch is bounded by `BACKTEST_V2_WORKER_CONCURRENCY`; queued-heavy backlog is guarded by `BACKTEST_V2_MAX_QUEUE_BACKLOG`.
- transient job failures are retried with bounded attempts (`BACKTEST_V2_JOB_MAX_ATTEMPTS*`) and exponential backoff (`BACKTEST_V2_JOB_RETRY_*`).
- incident kill switch: when `BACKTEST_V2_HEAVY_OPS_ENABLED=0`, heavy ops return `503 heavy_ops_disabled` for non-admin callers.
- plan limit failures return `402` with `plan_limit_exceeded` payload.
- request-rate failures return `429` with `rate_limited` payload.
- backlog saturation returns `429` with `queue_backlog_exceeded`.
- non-admin callers cannot steer runner egress: `strategy_api_url` is forced to internal URL (`BACKTEST_INTERNAL_STRATEGY_API_URL`).
- admin callers may override `strategy_api_url` only when URL is in allowlist (`BACKTEST_STRATEGY_API_ALLOWLIST`).
- `GET /api/v2/jobs/{job_id}` includes `attempts`, `max_attempts`, and `idempotency_key` in the job payload.
- when `BACKTEST_SUPABASE_RUN_STATE_MIRROR_ENABLED=1`, the same job lifecycle is mirrored best-effort into Supabase `run_jobs`/`runs` for Realtime subscribers; API responses and SQLite dispatch semantics stay unchanged.
- current FE authenticated start path uses `/api/v2/runs` + `/api/v2/jobs/{job_id}` and only re-attaches to legacy `/api/run/*` endpoints after the async job reaches `completed`.

### `POST /api/v2/adaptive-tuner/run` / `POST /api/v2/data/download`

Purpose: authenticated async queue wrappers for heavy tuner/download operations.

Behavioral notes:

- both endpoints reuse v2 plan limits (`max_range_days`, `concurrent_runs`) and share heavy-job concurrency pool.
- both enqueue jobs in the same `/api/v2/jobs/{job_id}` lifecycle (`queued|running|completed|failed`).
- both support optional idempotency-key dedupe and bounded retry semantics identical to `POST /api/v2/runs`.
- `adaptive-tuner/run` applies the same strategy URL policy as `v2/runs` (non-admin forced to internal strategy URL).
- `data/download` returns queued job immediately; result payload is delivered through job polling.

### `POST /api/v2/billing/checkout` / `POST /api/v2/billing/portal` / `POST /api/v2/billing/webhook/stripe`

Purpose: Stripe billing lifecycle integration for FREE -> PREMIUM.

Behavioral notes:

- checkout/portal require authenticated caller and configured `STRIPE_SECRET_KEY`.
- webhook endpoint deduplicates events by Stripe `event_id` before processing.
- subscription lifecycle supports:
  - `cancel_at_period_end` scheduled downgrade (premium remains active until `current_period_end`).
  - grace workflow for payment failures (`invoice.payment_failed`) with configurable `BACKTEST_BILLING_GRACE_DAYS`.
  - automatic fallback to `free` after grace/period expiry.
- webhook processing writes an internal billing audit trail (`billing_audit_events`).

### `POST /api/run/start`

Purpose: Initialize run, load data, configure strategy session defaults, and prepare runner state.

Deployment note:

- `/api/run/*` playback endpoints are stateful (in-memory run registry). They require a persistent backend process.
- Serverless targets (for example Vercel/Lambda) are blocked with `HTTP 503`.

Important request fields:

- identity: `run_id`, `ticker`, `date` OR `date_from` + `date_to`
- optional intraday playback slice: `start_time`, `end_time` (ISO datetimes; when provided, runner bars are filtered to this sub-range inside the selected date/day window)
- optional trading-only intraday slice: `trade_start_time`, `trade_end_time` (ISO datetimes; bars outside this sub-range may still be loaded for warmup, but are sent to strategy API with `warmup_only=true` so entries/exits are suppressed)
- session scope override: optional `include_extended_hours` (`true` => include pre/post-market bars, `false` => regular session only, `null/omitted` => keep AOS time-filter behavior)
- execution realism: `account_size_usd`, `risk_per_trade_pct`, `max_fill_participation_rate`, `min_fill_ratio`
  - position sizing is fixed-notional by default from `account_size_usd` (then bounded by fill constraints and optional `max_position_notional_pct` cap); `risk_per_trade_pct` is kept for backward-compatible payloads.
- stop-risk policy: `stop_loss_mode` (`strategy|fixed|capped`), `fixed_stop_loss_pct` (`> 0` required when mode is `fixed` or `capped`)
- strategy trailing baseline: optional `trailing_stop_pct` (global trailing distance in %, applied as `global_trailing_stop_pct` on strategy API side)
- strategy exit/risk baselines: optional `global_exit_rr_ratio`, `global_risk_atr_stop_multiplier`, `global_risk_volume_stop_pct`, `global_risk_min_stop_loss_pct` (fanout as `global_*` strategy params)
- exit behavior: `enable_partial_take_profit`, `partial_take_profit_rr`, `time_exit_bars`, `adverse_flow_*`, `adverse_flow_consistency_threshold`, `adverse_book_pressure_threshold`
- L2 gating: `l2_only`, `l2_confirm_enabled`, `l2_min_*`, `l2_lookback_bars`
- options-flow gate: `tcbbo_gate_enabled`, `tcbbo_min_net_premium`, `tcbbo_sweep_boost`, `tcbbo_lookback_bars`
- intraday levels tracker (session-scoped): `intraday_levels_enabled`, `intraday_levels_swing_left_bars`, `intraday_levels_swing_right_bars`, `intraday_levels_test_tolerance_pct`, `intraday_levels_break_tolerance_pct`, `intraday_levels_breakout_volume_lookback`, `intraday_levels_breakout_volume_multiplier`, `intraday_levels_volume_profile_bin_size_pct`, `intraday_levels_value_area_pct`, `liquidity_sweep_detection_enabled`, `sweep_min_aggression_z`, `sweep_min_book_pressure_z`, `sweep_max_price_change_pct`
- intraday entry-quality gate controls: `intraday_levels_entry_quality_enabled`, `intraday_levels_min_levels_for_context`, `intraday_levels_entry_tolerance_pct`, `intraday_levels_break_cooldown_bars`, `intraday_levels_rotation_max_tests`, `intraday_levels_rotation_volume_max_ratio`, `intraday_levels_recent_bounce_lookback_bars`, `intraday_levels_require_recent_bounce_for_mean_reversion`, `intraday_levels_momentum_break_max_age_bars`, `intraday_levels_momentum_min_room_pct`, `intraday_levels_momentum_min_broken_ratio`, `intraday_levels_min_confluence_score`
- walking-forward intraday context controls: `intraday_levels_memory_enabled`, `intraday_levels_memory_min_tests`, `intraday_levels_memory_max_age_days`, `intraday_levels_memory_decay_after_days`, `intraday_levels_memory_decay_weight`, `intraday_levels_memory_max_levels`, `intraday_levels_opening_range_enabled`, `intraday_levels_opening_range_minutes`, `intraday_levels_opening_range_break_tolerance_pct`, `intraday_levels_poc_migration_enabled`, `intraday_levels_poc_migration_interval_bars`, `intraday_levels_poc_migration_trend_threshold_pct`, `intraday_levels_poc_migration_range_threshold_pct`, `intraday_levels_composite_profile_enabled`, `intraday_levels_composite_profile_days`, `intraday_levels_composite_profile_current_day_weight`
- advanced intraday context controls: `intraday_levels_spike_detection_enabled`, `intraday_levels_spike_min_wick_ratio`, `intraday_levels_prior_day_anchors_enabled`, `intraday_levels_gap_analysis_enabled`, `intraday_levels_gap_min_pct`, `intraday_levels_gap_momentum_threshold_pct`, `intraday_levels_rvol_filter_enabled`, `intraday_levels_rvol_lookback_bars`, `intraday_levels_rvol_min_threshold`, `intraday_levels_rvol_strong_threshold`, `intraday_levels_adaptive_window_enabled`, `intraday_levels_adaptive_window_min_bars`, `intraday_levels_adaptive_window_rvol_threshold`, `intraday_levels_adaptive_window_atr_ratio_max`, `intraday_levels_micro_confirmation_enabled`, `intraday_levels_micro_confirmation_bars`, `intraday_levels_micro_confirmation_disable_for_sweep`, `intraday_levels_micro_confirmation_sweep_bars`, `intraday_levels_micro_confirmation_require_intrabar`, `intraday_levels_micro_confirmation_intrabar_window_seconds`, `intraday_levels_micro_confirmation_intrabar_min_coverage_points`, `intraday_levels_micro_confirmation_intrabar_min_move_pct`, `intraday_levels_micro_confirmation_intrabar_min_push_ratio`, `intraday_levels_micro_confirmation_intrabar_max_spread_bps`, `intraday_levels_confluence_sizing_enabled`
- context-aware risk controls: `context_aware_risk_enabled`, `context_risk_sl_buffer_pct`, `context_risk_min_sl_pct`, `context_risk_min_room_pct`, `context_risk_min_effective_rr`, `context_risk_trailing_tighten_zone`, `context_risk_trailing_tighten_factor`, `context_risk_level_trail_enabled`, `context_risk_max_anchor_search_pct`, `context_risk_min_level_tests_for_sl`, `sweep_atr_buffer_multiplier`
- pullback quality/risk controls: `pullback_context_min_sl_pct`, `pullback_time_exit_bars`, `pullback_morning_window_enabled`, `pullback_entry_start_time`, `pullback_entry_end_time`, `pullback_require_poc_on_trade_side`, `pullback_block_choppy_macro`, `pullback_blocked_micro_regimes`, `pullback_min_price_trend_efficiency`, `pullback_break_even_proof_required`, `pullback_break_even_activation_min_r`, `pullback_break_even_l2_book_pressure_min`
- strategy selection: `strategy_selection_mode` (`adaptive_top_n|all_enabled`), `max_active_strategies`
- optional momentum nesting override: `momentum_diversification_override` (object, merged into strategy `adaptive.momentum_diversification` for this run only; supports single config and optional `sleeves[]` multi-sleeve layout)
- intrabar execution realism:
  - optional `trade_eval_mode` (`standard|intrabar_1s|intrabar_5s`) to select start-time trade evaluation path explicitly
  - optional legacy `intrabar_execution_recalc_1s` (when `trade_eval_mode` is omitted, defaults to auto-on when L2 is available)
- reset semantics: `comparable_mode`, `cold_start_each_day`, `checkpoint_path`, `auto_save_checkpoint`
- strategy defaults behavior: `apply_ticker_overrides_on_start` (`true` keeps legacy runner-side override apply; `false` preserves manual FE strategy edits)
- AOS sync behavior: `apply_aos_optimizations_on_start` (`true` applies remote strategy/AOS sync during start; `false` keeps local effective config only and skips slower remote fanout)

Runtime safety notes:

- when `l2_only=true` or `l2_confirm_enabled=true` and the requested range exceeds `BACKTEST_RUN_L2_MAX_DAYS` (default `10`) while `BACKTEST_RUN_L2_FORCE!=1`, run start fails with `HTTP 400` (no silent L2 downgrade).
- when `l2_only=true` or `l2_confirm_enabled=true`, missing L2 day coverage is treated as a hard start error (`HTTP 400`), not a silent fallback.
- when `liquidity_sweep_detection_enabled=true` and neither `l2_only` nor `l2_confirm_enabled` is requested, runner auto-enables `l2_confirm_enabled` (execution payload exposes `liquidity_sweep_l2_auto_enabled=true` + source).
- progressive run loading can remain enabled in `comparable_mode` (day-isolated audit) via `BACKTEST_PROGRESSIVE_LOAD_ALLOW_COMPARABLE_MODE=1` (default enabled) to avoid full-range L2 blocking at run start.
- comparable-mode progressive pacing can be tuned independently with `BACKTEST_PROGRESSIVE_LOAD_COMPARABLE_INITIAL_DAYS` and `BACKTEST_PROGRESSIVE_LOAD_COMPARABLE_CHUNK_DAYS` (defaults `1`/`1`).
- raw L2 dataframe cache is bounded by `BACKTEST_L2_CACHE_MAX_TICKERS`, `BACKTEST_L2_CACHE_MAX_ROWS`, and `BACKTEST_L2_CACHE_MAX_BYTES` (defaults favor memory safety over aggressive reuse).
- strategy update fanout (`/api/strategies/update` bursts during run start) is concurrency-limited by `BACKTEST_STRATEGY_UPDATE_MAX_CONCURRENCY` (default `8`) to reduce start latency without unbounded request pressure.
- runner->strategy API HTTP calls use bounded timeout `BACKTEST_STRATEGY_API_TIMEOUT_SECONDS` (default `6.0`) to fail fast when strategy API is slow/unreachable.
- when effective strategy mode resolves to `all_enabled`, runner performs best-effort pre-session strategy sync (`enabled=true` for every strategy currently returned by strategy API) so active strategy set is not accidentally constrained by stale per-strategy enabled flags.

Important response fields:

- `run_key`
- `strategy_state_reset`
- `checkpoint_loaded`
- `l2_applied` (effective L2 parameters and coverage stats)
- `execution_config` (effective execution defaults)
  - includes effective trade evaluation mode (`trade_eval_mode`) and intrabar checkpoint step (`intrabar_eval_step_seconds`)
  - includes effective `strategy_selection_mode` and `max_active_strategies`
  - includes `all_enabled_remote_sync` diagnostic payload when `strategy_selection_mode=all_enabled` (attempt/applied/strategy_count and sync status details)
  - includes `apply_aos_optimizations_on_start` (whether remote AOS sync was executed during start)
  - includes resolved intraday context/risk controls (spike/gap/RVOL/adaptive-window/micro-confirm/confluence-sizing and `context_risk_*` fields)
  - includes `momentum_diversification_applied`, `momentum_diversification_source` (`request|adaptive_profile|aos_config|none`), and effective `momentum_diversification`
  - active unified profile metadata is exposed via `aos_applied.unified_profile` when present
  - legacy combo/adaptive metadata remains for backward compatibility when unified profile is not active
- `start_timing` (start-phase timing diagnostics for FE/ops: `total_ms`, `slowest_phase`, `phases_ms`, and basic run context)

### `POST /api/run/prewarm`

Purpose: Warm run-start caches (bars/reference/L2 enrichment) for a ticker and date range without creating a run.

Compatibility notes:

- accepts `ticker` with `date` or `date_from/date_to` (scope `range`) and optional `prewarm_scope=ticker` to warm full available ticker coverage, plus optional L2 flags (`l2_only`, `l2_confirm_enabled`, `comparable_mode`).
- ticker-scope prewarm enforces an explicit L2 guard (`BACKTEST_PREWARM_TICKER_SCOPE_L2_MAX_DAYS`, default `10`): when exceeded and `BACKTEST_PREWARM_TICKER_SCOPE_L2_FORCE!=1`, prewarm fails with `HTTP 400` (no silent L2 downgrade).
- range-scope prewarm enforces run L2 guard (`BACKTEST_RUN_L2_MAX_DAYS`, default `10`): when exceeded and `BACKTEST_RUN_L2_FORCE!=1`, prewarm fails with `HTTP 400`.
- uses local AOS snapshot for time-filter/L2 defaults; does not reset or mutate remote strategy session state.
- accepts optional `include_extended_hours` session-scope override (same semantics as run start).
- returns `cache_hit` (`true` when identical request was already prewarmed in-memory during current backend process).
- server startup can auto-prewarm configured tickers (defaults to `MU`) via envs: `BACKTEST_STARTUP_PREWARM_ENABLED`, `BACKTEST_STARTUP_PREWARM_TICKERS`, `BACKTEST_STARTUP_PREWARM_L2_CONFIRM` (default `false`).
- ticker-scope prewarm can be reused for narrower date sub-ranges in later `POST /api/run/start` calls (same ticker/files/time-filter signature), so changing date windows no longer forces full file reload.

### `POST /api/data-loader/catalog/remote-sync`

Purpose: ingest remote catalog manifest entries (e.g. Cloudflare R2 manifest JSON) into local data catalog.

Request contract:

- optional query `url`; when omitted, service uses `BACKTEST_REMOTE_MANIFEST_URL`.

Response contract:

- returns `status`, `synced_entries`, and effective `manifest_url`.

Behavioral notes:

- remote entries are stored as unmanaged catalog rows (`managed=false`) and may point to `https://...` or `s3://bucket/key` objects.
- for `mbp-10` remote entries, coverage checks treat manifest rows as available; files are downloaded lazily into local cache on first range file resolution.
- cache target is controlled by `BACKTEST_REMOTE_CACHE_DIR`; HTTP timeout by `BACKTEST_REMOTE_TIMEOUT_SEC`.
- private S3/R2 fetches use `BACKTEST_REMOTE_S3_ENDPOINT` (or `BACKTEST_REMOTE_S3_ACCOUNT_ID`) + optional credentials `BACKTEST_REMOTE_S3_ACCESS_KEY_ID`/`BACKTEST_REMOTE_S3_SECRET_ACCESS_KEY`.

### `GET /api/available-data`

Purpose: expose available ticker/date coverage for run setup and tuner UX.

Request contract:

- optional query `refresh` (`true|false`, default `false`) to force catalog rescan before summarizing.

Response contract:

- `tickers[]`: symbols with discovered OHLCV and/or L2 catalog coverage.
- `l2_tickers[]`: symbols with discovered `mbp-10` coverage.
- `date_ranges.{ticker}`: effective OHLCV range (`start`, `end`, `files[]`).
- `l2_date_ranges.{ticker}`: L2 range (`start`, `end`, `files[]`).
- `l2_overlap_date_ranges.{ticker}`: calendar overlap window between OHLCV and L2 ranges.

Behavioral notes:

- OHLCV range uses effective file coverage (derived from timestamps), not only filename dates.
- `l2_overlap_date_ranges` is provided for L2-only UX clamping while keeping backward compatibility with existing `date_ranges`.

### `POST /api/run/diagnose`

Purpose: preflight diagnostics for one concrete run request (single day or range), with explicit reason codes for start failures.

Request contract:

- body follows `PrewarmRunRequest` shape (`ticker`, `date` or `date_from/date_to`, `l2_only`, `l2_confirm_enabled`, `comparable_mode`, ...)
- query: `probe_start` (`false` by default). When `true`, endpoint also runs heavy prewarm/start-probe for exact parity with start pipeline.

Response contract:

- always returns structured diagnostics payload (even when run would fail):
  - `ok` (`true|false`)
  - `mode` (`coverage_only` or probe mode)
  - `resolved` (effective range + L2 flags from prewarm status)
  - `coverage.ohlcv_1m` (covered/missing days metadata)
  - `coverage.l2_schemas[]` (per-schema covered/missing days metadata)
  - when `ok=false`: `status_code`, `error_kind`, `error`
  - when `ok=true`: `probe` summary (`bars`, `reference_bars`, L2 stats snapshot)

Behavioral notes:

- endpoint reuses run-start/prewarm validation path so diagnostics match real start behavior.
- in default `coverage_only` mode, endpoint also performs short-range OHLCV probe (L2 disabled) to catch calendar/file-range false positives such as market holidays with zero bars.
- common `error_kind` values include: `no_ohlcv_data`, `missing_l2_coverage`, `no_l2_aligned_bars`, `no_l2_data`.

### `POST /api/run/{run_id}/{ticker}/{date}/step|play|pause|resume|stop|restart`

Purpose: Control progression of an initialized run.

Compatibility notes:

- playback contract assumes the same backend process retains active run state across requests.
- `play` accepts body or query speed format (`max`, `10hz`, integer ms) and optional `trade_eval_mode` (`standard|intrabar_1s|intrabar_5s`) to switch execution evaluation path without restarting run.
- `step` accepts optional body `trade_eval_mode` (`standard|intrabar_1s|intrabar_5s`) so single-step evaluation can switch checkpoint granularity without restarting run.
- `restart` rewinds the existing in-memory run to bar zero (no re-load of source bars), clears remote strategy session state for that run+ticker, and reapplies stored session config before replay.
- marker/event ordering must remain stable for frontend playback.
- `POST /api/run/cache/flush?include_disk=true|false` clears run-start caches (bars/reference/L2 enrichment); use when reclaiming memory or forcing re-read from source files.

### `POST /api/run/{run_id}/{ticker}/{date}/intrabar_eval`

Purpose: side-effect-free intrabar slice evaluation for analyzer scrub mode.

Compatibility notes:

- route proxies request payload to strategy API `POST /api/session/intrabar_eval` using the active run session context.
- active runner identity is authoritative: `run_id` and `ticker` are overwritten from the in-memory run config before proxy.
- requires bar core fields in body (`timestamp`, `open`, `high`, `low`, `close`, `volume`).
- non-200 strategy responses are surfaced with the upstream HTTP status and detail.

### `GET /api/run/{run_id}/{ticker}/{date}/markers|summary|bars|state`

Purpose: Diagnostics and render payloads for frontend and analysis scripts.

Compatibility notes:

- marker schema changes require frontend compatibility checks.
- execution-layer pending/no-fill outcomes are emitted as marker type `execution_status` (with `details.execution_status`, `details.execution_action`, `details.reason`) and are intentionally excluded from `signals` counts, which remain based on `signal_generated`.
- summary fields are consumed by diagnostics history and regression workflows.
- `total_pnl_pct` in runner summary is normalized from `total_pnl_dollars / account_size_usd` to keep percent and dollar PnL directionally consistent.
- run `state` payload includes `selection_warnings[]` (resolved from strategy-selection responses) so FE can surface strict-selection config gaps without fallback.

### `GET /api/aos-config` / `GET /api/aos-config/{ticker}` / `POST /api/aos-config/update`

Purpose: Read and persist per-ticker AOS settings used by runner start and strategy selection.

Compatibility notes:

- `POST /api/aos-config/update` merges provided `config` object into existing ticker config.
- Adaptive selection settings are file-backed (`aos_optimization/aos_config.json`) and applied on next `POST /api/run/start`.
- Supported adaptive switch-guard keys include `adaptive.min_active_bars_before_switch` and `adaptive.switch_cooldown_bars`.
- Strategy combination profiles are also file-backed under each ticker (`strategy_combo_profiles`, `active_strategy_combo_profile_id`) and active profile params are applied at run start.
- Unified profiles are file-backed per ticker (`unified_profiles`, `active_unified_profile_id`) and carry both `strategy_profile` and `execution_profile` sections.

### `GET /api/strategy-combos/{ticker}` / `POST /api/strategy-combos/capture` / `POST /api/strategy-combos/apply`

Purpose: manage per-ticker strategy-parameter combination profiles and activate them for runtime use.

List contract (`GET /api/strategy-combos/{ticker}`):

- returns saved `profiles` and `active_profile_id` for ticker from AOS config.
- each profile carries `profile_id`, `profile_name`, timestamps, and `strategy_params` map.

Capture contract (`POST /api/strategy-combos/capture`):

- request: `ticker`, optional `profile_name`, `strategy_api_url`, `set_active`
- behavior: fetches current live strategy settings from strategy API and stores them as a combo profile in ticker AOS config.
- effect: when `set_active=true`, captured profile is marked active for next `POST /api/run/start`.

Apply contract (`POST /api/strategy-combos/apply`):

- request: `ticker`, `profile_id`, optional `strategy_api_url`, `apply_now`
- behavior: sets selected combo profile as ticker active profile in AOS config.
- effect: next `POST /api/run/start` applies profile strategy params automatically; when `apply_now=true` they are also pushed to strategy API immediately.

### `GET /api/profiles/{ticker}` / `POST /api/profiles/capture` / `POST /api/profiles/apply`

Purpose: manage unified per-ticker profiles that bundle strategy and execution config into one profile entity.

List contract (`GET /api/profiles/{ticker}`):

- returns saved `profiles` and `active_profile_id` for ticker from AOS config.
- each profile carries `profile_id`, `profile_name`, timestamps, `strategy_profile`, `execution_profile`.

Capture contract (`POST /api/profiles/capture`):

- request: `ticker`, optional `profile_name`, `strategy_api_url`, `set_active`
- behavior: fetches live strategy params from strategy API and captures current ticker strategy/execution settings into one unified profile.
- effect: when `set_active=true`, captured profile becomes ticker active unified profile.

Apply contract (`POST /api/profiles/apply`):

- request: `ticker`, `profile_id`, optional `strategy_api_url`, `apply_now`, `apply_execution`
- behavior: marks profile as active unified profile; can apply strategy params immediately (`apply_now`) and persist execution section into positioning config (`apply_execution`).
- effect: next `POST /api/run/start` prioritizes active unified profile over legacy combo/adaptive split paths.

### `GET /api/live-trader/runs` / `GET /api/live-trader/events/{run_id}` / `GET /api/live-trader/snapshot/{run_id}`

Purpose: expose JSONL artifacts from sibling realtime project (`ibkr-realtime-trader/artifacts`) for frontend live monitoring.

List contract (`GET /api/live-trader/runs`):

- query: `limit`, `active_only`
- returns discovered `run_id` values and per-stream file metadata (`runtime|decisions|signals|orders`)
- sorted by latest artifact update timestamp
- includes run `status` (`active|idle|finished|error`) and latest runtime summary (`profile_id`, `active_profile_id`, `execution_config`, latest `event`)

Events contract (`GET /api/live-trader/events/{run_id}`):

- query: `stream` (`runtime|decisions|signals|orders`), `limit`
- returns tail rows from selected stream as parsed JSON objects

Snapshot contract (`GET /api/live-trader/snapshot/{run_id}`):

- query: `tail_limit`
- returns per-stream existence/count/latest row for dashboard status cards
- includes aggregate `status` (`active|idle|finished|error`), `updated_at`, and top-level `runtime` latest summary

### `GET /api/reports/history/{ticker}`

Purpose: expose calendar-friendly aggregates from persisted run summaries so frontend Diagnostics can inspect previous runs and adaptive profile usage per day.

Query contract:

- `limit` (default `300`, max `5000`) limits number of matched report artifacts processed.
- `run_id` optional exact run-id filter (recommended for UI dropdown filtering).
- `run_id_contains` optional substring filter for historical run IDs.
- `adaptive_profile_id` optional adaptive profile filter. Exact metadata match is preferred; legacy report IDs with matching short token (e.g. `c4`) may be surfaced as hint matches.
  - additional legacy heuristic: when profile-id metadata is missing in report artifacts, endpoint may classify matches as `strategy_hint` by comparing report strategy names with strategy set saved in `aos_config` profile candidate.
- `include_multi_day` (default `true`) expands `YYYY-MM-DD_to_YYYY-MM-DD` labels into day-level calendar rows even when a day has zero closed trades.
- `include_zero_trade_runs` (default `false`) includes runs with no closed trades in history payload; day rows then carry zero trade/PnL values.

Response notes:

- returns report-level day aggregates merged by calendar day under `day_results[]` with:
  - day PnL (`pnl_pct`, `pnl_dollars`)
  - day trade count (`total_trades`)
  - day signal/regime counts from markers (`signals`, `regime_evaluations`)
  - day bars when resolvable (`processed_bars`, `total_bars`; often `null` for multi-day range artifacts)
  - `trade_details[]` including entry/exit reasons when available
  - `runs[]` summaries (run id, run key, saved-at, profile metadata, per-run day PnL/trades, plus run-level totals: `run_total_trades`, `run_total_pnl_pct`, `run_total_pnl_dollars`, `run_signals`, `run_regime_evaluations`, `run_processed_bars`, `run_total_bars`)
  - per-run request snapshot `run_request_config` (full `POST /api/run/start` payload when present in stored summary); for single-run days, `day_results[].run_request_config` mirrors that snapshot for convenience.
- includes `filter_options` payload for diagnostics dropdowns:
  - `filter_options.run_ids[]` with `run_id` and `latest_saved_at`
  - `filter_options.adaptive_profiles[]` merged from history metadata and `aos_optimization/aos_config.json`
- by default, report artifacts with zero closed trades are excluded from history payload and run dropdown options; set `include_zero_trade_runs=true` to include them.
- includes calendar metadata: `split`, `metrics`, `matched_reports`, `scanned_reports`.
- includes source metadata for diagnostics header rendering:
  - `source_mode` (`supabase_run_reports|sqlite_run_reports|run_reports_store`)
  - `source_path_hint` (`run_reports_store`)
- malformed historical artifacts are skipped and counted under `skipped_invalid_reports`.
- source resolution:
  - endpoint also merges currently active in-memory runs (`active_runners`) so Diagnostics can surface Strategy Analyzer sessions before explicit delete/final save.
  - endpoint reads `app.state.run_reports_store` as the authoritative persisted source (Supabase in prod, SQLite in local-by-default runtime).
- if no source data exists, endpoint returns `200` with empty `day_results`.

### `GET /api/reports/run-snapshot`

Purpose: fetch one persisted run playback snapshot by `run_key` for Diagnostics -> Strategy Analyzer fast open.

Query contract:

- `run_key` required, format `run_id:ticker:date_or_range`.

Response notes:

- checks active in-memory run first (`active_runners`) and returns live bars/markers/state when present.
- otherwise reads persisted `run_summaries` row from configured run-report store (Supabase or SQLite).
- expects compressed playback payload under `summary.playback_snapshot` (`encoding=gzip+base64`).
- returns:
  - `run_key`
  - `state` (read-only snapshot state with `is_snapshot=true`)
  - `bars[]`, `markers[]`
  - `summary` (same summary object but `playback_snapshot.payload_b64` removed from response)
  - `snapshot_meta` and `report_saved_at`
- if snapshot payload is missing (older run rows), endpoint returns `404` with guidance to rerun once with snapshot persistence enabled.

### `GET /api/system/l2/runtime` / `POST /api/system/l2/runtime`

Purpose: inspect and adjust runner-side L2 runtime knobs without restarting the API (useful for diagnostics/tuning fast-mode).

Runtime fields:

- `iceberg_detection_enabled` (`bool`) toggles expensive iceberg sequence detection during L2 feature-map build.
- `cache_max_tickers`, `cache_max_rows`, `cache_max_bytes` control raw L2 in-memory cache thresholds.

Compatibility notes:

- values apply to the current backend process only (runtime state, not persisted config files).
- `POST` validates cache fields as non-negative integers and returns both `updated` keys and full effective `runtime`.
- feature-map iceberg counters are disabled by default unless `BACKTEST_L2_INCLUDE_ICEBERGS_IN_FEATURE_MAP=1` is set.

### `GET /api/adaptive-tuner/options/{ticker}` / `POST /api/adaptive-tuner/profiles/apply` / `POST /api/adaptive-tuner/run` / `GET /api/adaptive-tuner/{job_id}` / `GET /api/adaptive-tuner`

Purpose: expose real ticker coverage for L2-aware tuning, manage saved tuned profiles, run adaptive strategy-selection tuning jobs (Adaptive Studio v1), poll job status/results, and list recent jobs.

Coverage/options contract (`GET /api/adaptive-tuner/options/{ticker}`):

- returns OHLCV range, L2 range, and OHLCV∩L2 overlap range from real local catalog coverage.
- includes `default_date_from/default_date_to` for prefill and `l2_overlap_days` list.
- includes saved `profiles` and `active_profile_id` from ticker AOS config.
- consumed by Adaptive Tuner, Adaptive Strategy Studio, and Backtest Run Config to expose selectable tuned-profile options.

Profile apply contract (`POST /api/adaptive-tuner/profiles/apply`):

- request: `ticker`, `profile_id`
- behavior: applies selected profile candidate into active ticker adaptive settings in `aos_config.json`
- behavior detail: clears `active_unified_profile_id` for that ticker so unified/profile selectors fall back to current combo+adaptive derived active profile instead of stale explicit unified snapshots.
- effect: next `POST /api/run/start` for ticker uses applied adaptive settings.
- used by Adaptive Tuner, Adaptive Strategy Studio, and optional Backtest pre-run profile selection.

Important request fields (`POST /api/adaptive-tuner/run`):

- identity/scope: `ticker`, `date_from`, `date_to`, `strategy_api_url`
- tuner mode: `method` (`grid|random|optuna`) and `n_trials`
- scoring: `score_metric` (`pnl_pct|pnl_dollars|win_rate|trade_adjusted`)
- reproducibility: `seed`
- compatibility: `adaptive_version` (`1` = flat tuning, `2` = multi-dimensional vector discovery)
- persistence: `persist_best` (when true, best candidate is saved into `aos_config.json`)
- L2 gating: `l2_required` (restrict evaluated dates to OHLCV+L2 overlap), `l2_confirm_enabled`, `l2_only`
- quick approximation: `quick_mode`, `quick_max_days`, `quick_trial_boost`
  - when enabled, tuner samples representative days from eligible range and scales trial budget by multiplier for faster broad screening
- optional v1 search-space fields:
  - `selection_modes`
  - `max_active_options`
  - `min_active_bars_options`
  - `switch_cooldown_bars_options`
  - `flow_bias_options`
  - `ohlcv_fallback_options`
- optional v2 momentum-diversification fields:
  - `momentum_diversification_enabled_options`, `momentum_route_enabled_options`
  - `momentum_min_flow_score_options`, `momentum_min_directional_consistency_options`
  - `momentum_min_signed_aggression_options`, `momentum_min_imbalance_options`
  - `momentum_min_cvd_options`, `momentum_min_directional_price_change_pct_options`
  - `momentum_min_price_trend_efficiency_options`, `momentum_min_last_bar_body_ratio_options`
  - `momentum_min_last_bar_close_location_options`
  - `momentum_min_delta_acceleration_options`, `momentum_min_delta_price_divergence_options`
  - `momentum_route_flow_score_impulse_options`
  - `momentum_fail_fast_exit_enabled_options`, `momentum_fail_fast_max_bars_options`

Important response fields:

- `POST /api/adaptive-tuner/run`: `job_id`, `status`, tuned date range metadata
- `GET /api/adaptive-tuner/{job_id}`: full job object including `source_effective_dates`, sampled `effective_dates`, `trial_budget`, `progress`, `trials`, `best_trial`, and completion/error metadata
- `GET /api/adaptive-tuner`: reverse-chronological list of job objects (bounded by `limit`)

## Strategy API (Port 8001) - Key Contracts

### `POST /api/session/config`

Purpose: Set per-session execution/risk/L2 defaults before bar processing.

Auth note:

- strategy API protects `/api/session/*`, `/api/orchestrator/*`, and strategy mutation routes when `STRATEGY_INTERNAL_API_TOKEN` is set.
- runner must send `x-internal-token` header value that matches strategy API token (typically via `BACKTEST_STRATEGY_INTERNAL_API_TOKEN` or `STRATEGY_INTERNAL_API_TOKEN`).
- transport compatibility: canonical runner path sends config as query params; strategy API also accepts JSON body fallback for manual/debug clients (when both are provided, explicit query keys win).

Key settings passed from runner:

- regime cadence: `regime_detection_minutes`, `regime_refresh_bars`
- risk/fill: `account_size_usd`, `risk_per_trade_pct`, `max_position_notional_pct`, `max_fill_participation_rate`, `min_fill_ratio`
  - session sizing targets fixed notional from `account_size_usd`; `max_position_notional_pct` remains an upper cap.
- stop-risk policy: `stop_loss_mode`, `fixed_stop_loss_pct` (`> 0` required when mode is `fixed` or `capped`)
- exits: `time_exit_bars`, `partial_take_profit_*`, `adverse_flow_*`, `adverse_flow_consistency_threshold`, `adverse_book_pressure_threshold`
  - optional runtime formula hooks for exit decisions: `time_exit_formula*`, `adverse_flow_exit_formula*`
- break-even governance:
  - activation thresholds: `break_even_min_hold_bars`, `break_even_activation_min_mfe_pct`, `break_even_activation_min_r`, `break_even_activation_min_r_trending_5m`, `break_even_activation_min_r_choppy_5m`
  - proof gating toggles/thresholds: `break_even_activation_use_levels`, `break_even_activation_use_l2`, `break_even_level_*`, `break_even_l2_*`
  - stop computation: `break_even_costs_pct`, `break_even_buffer_pct`, `break_even_min_buffer_pct`, `break_even_atr_buffer_k`, `break_even_5m_atr_buffer_k`, `break_even_tick_size`, `break_even_min_tick_buffer`
  - intrabar anti-spike: `break_even_anti_spike_bars`, `break_even_anti_spike_hits_required`, `break_even_anti_spike_require_close_beyond` (`breakeven_stop` confirms on 1s close-beyond OR required consecutive stop touches inside anti-spike window)
  - 5m contextual adaptation: `break_even_5m_no_go_proximity_pct`, `break_even_5m_mfe_atr_factor`, `break_even_5m_l2_bias_threshold`, `break_even_5m_l2_bias_tighten_factor`
  - optional runtime formula hooks (safe expression grammar, boolean result): `break_even_movement_formula*`, `break_even_proof_formula*`, `break_even_activation_formula*`, `break_even_trailing_handoff_formula*`
- global risk guardrails (via `/api/config/trading`): `portfolio_drawdown_halt_pct` (run-level halt), `headwind_activation_score` (cross-asset threshold boost trigger)
- L2 confirmation: `l2_confirm_enabled`, `l2_min_*`, `l2_lookback_bars`
- options-flow confirmation gate: `tcbbo_gate_enabled`, `tcbbo_min_net_premium`, `tcbbo_sweep_boost`, `tcbbo_lookback_bars`
- intraday-level runtime gating: same `intraday_levels_*` tracker + entry-quality fields used by runner start payload
- strategy selection: `strategy_selection_mode`, `max_active_strategies`
- momentum diversification override transport: `momentum_diversification_json` (JSON string; strategy API validates/normalizes into session defaults, including optional `sleeves[]` multi-sleeve definitions with per-sleeve thresholds)
- profile-driven runtime overrides: optional `regime_detection_minutes` / `regime_refresh_bars` cadence, optional `max_daily_trades` (`0` => unlimited for that session), and optional `mu_choppy_hard_block_enabled` (session override for MU CHOPPY guard)
- reset policy: `cold_start_each_day`

### `POST /api/session/bar`

Purpose: Process one bar in-session and return decision payload.

Required bar fields:

- identity/time: `run_id`, `ticker`, `timestamp`
- OHLCV: `open`, `high`, `low`, `close`, `volume`

Optional fields:

- `vwap`
- L2 feature vector fields (`l2_*`)
- L2 data-quality metadata (`l2_quality_flags`, `l2_quality`) for degraded-feed awareness
- optional 1-second intrabar quotes for current minute (`intrabar_quotes_1s`: `[{"s","bid","ask"}]`)
- cross-asset reference bar (`ref_*`)

Behavioral guarantee:

- Processing must be no-lookahead (current/past context only).

Compatibility note:

- Legacy candlestick/multi-layer config endpoints are removed; strategy execution is evidence-engine only.
- Optional per-strategy custom formulas are evaluated in-session:
  - entry gate: enabled `custom_entry_formula` can reject otherwise-valid entry signals.
  - exit gate: enabled `custom_exit_formula` can force-close active position (`custom_formula_exit`).
- Optional runtime exit-policy formulas are also supported in session config:
  - break-even hooks: movement/proof/final activation + trailing handoff
  - non-BE hooks: `time_exit`, `adverse_flow_exit`
  - invalid runtime formulas in `/api/session/config` are rejected with `HTTP 400`
- Session responses include `intraday_levels` snapshot payload (session-scoped S/R levels + bounce/break events + volume-profile POC/value area), and indicator payloads may include `indicators.intraday_levels` for strategy context. This state resets with each new session day.
- Entry evaluation responses can include `level_context` payload (gate result + checks + reasons + POC/VA context + composite profile/opening-range/POC-migration context + near confluence score + recent break/bounce context + optional `target_price_override` for MR).
- `position_opened.metadata` includes resolved entry risk payload (`risk_controls` + `context_risk`) computed from executed entry/SL/TP values; `context_risk` carries `sl_reason`, `tp_reason`, `effective_rr`, and `risk_pct` even when context-aware risk adjustment is disabled.
- Break-even diagnostics are session-native and propagated in payloads as `break_even` snapshot (state machine status, activation/proof diagnostics, computed stop/costs/buffer, anti-spike counters, runtime formula evaluation snapshots). Runner forwards this to marker details and market context.
- Closed-position payloads include flow diagnostics (`flow_strategy`, `book_pressure_confirmed`, `book_pressure_avg`, `book_pressure_trend`, `signed_aggression`, `flow_snapshot`), preserved `level_context`/`signal_metadata`, `break_even`, and `entry_quality_diagnostics` (first-bar stop-loss analysis tags + entry confluence/risk snapshot).
- Session summary now includes `entry_timing_diagnostics` and per-strategy `vwap_magnet_entry_timing_diagnostics` for fast-stop analysis.

### `GET /api/strategies` / `POST /api/strategies/update`

Purpose: expose/edit per-strategy runtime parameters used by strategy engine and session runtime.

Custom formula fields:

- `custom_entry_formula_enabled` (`bool`) + `custom_entry_formula` (`string`)
- `custom_exit_formula_enabled` (`bool`) + `custom_exit_formula` (`string`)
- optional liquidity sweep ownership fields:
  - `liquidity_sweep_signal_enabled` (`bool`) gates whether a strategy may own runtime `liquidity_sweep_confirmed` entries
  - `liquidity_sweep_signal_priority` (`int`) chooses the owner when `selected_strategy="adaptive"` and multiple active strategies are eligible

Behavioral notes:

- formula strings are validated server-side with restricted expression grammar (safe AST; no arbitrary code).
- update rejects invalid formulas with `HTTP 400`.
- strategy payload exposes supported formula variables and examples to drive frontend editors.
- liquidity sweep ownership fields are backward-compatible and only affect the synthetic sweep-confirmation signal path; the global session flag `liquidity_sweep_detection_enabled` still controls whether sweep detection runs at all.

## Cross-Service Coupling

### Runner -> Strategy configuration coupling

`/api/run/start` in runner must continue to pass effective execution and L2 settings to `/api/session/config`.

Runner no longer sends candlestick or multilayer payload updates.

### Runner -> Strategy bar payload coupling

SessionRunner payload field names must stay compatible with `BarInput` in strategy `src/api_models.py`.

### Strategy -> Runner/Frontend decision payload coupling

Session response markers and summary fields are transformed by runner and displayed by frontend.
Any marker schema change must include:

1. runner compatibility update
2. frontend compatibility update
3. marker schema tests/regressions

## Full Endpoint Catalog

Use generated endpoint inventory for complete route coverage:

- `bmad/context/generated/00-endpoint-map.md`
- `bmad/context/generated/00-machine-index.json`
