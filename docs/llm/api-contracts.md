# API Contracts

Contract summary for runner, strategy, and cross-service coupling.

## Runner API (Port 8002) - Key Contracts

### `POST /api/run/start`

Purpose: Initialize run, load data, configure strategy session defaults, and prepare runner state.

Important request fields:

- identity: `run_id`, `ticker`, `date` OR `date_from` + `date_to`
- execution realism: `account_size_usd`, `risk_per_trade_pct`, `max_fill_participation_rate`, `min_fill_ratio`
- stop-risk policy: `stop_loss_mode` (`strategy|fixed|capped`), `fixed_stop_loss_pct`
- exit behavior: `enable_partial_take_profit`, `partial_take_profit_rr`, `time_exit_bars`, `adverse_flow_*`
- L2 gating: `l2_only`, `l2_confirm_enabled`, `l2_min_*`, `l2_lookback_bars`
- strategy selection: `strategy_selection_mode` (`adaptive_top_n|all_enabled`), `max_active_strategies`
- intrabar execution realism: optional `intrabar_execution_recalc_1s` (defaults to auto-on when L2 is available)
- reset semantics: `comparable_mode`, `cold_start_each_day`, `checkpoint_path`, `auto_save_checkpoint`
- strategy defaults behavior: `apply_ticker_overrides_on_start` (`true` keeps legacy runner-side override apply; `false` preserves manual FE strategy edits)

Important response fields:

- `run_key`
- `strategy_state_reset`
- `checkpoint_loaded`
- `l2_applied` (effective L2 parameters and coverage stats)
- `execution_config` (effective execution defaults)
  - includes effective `strategy_selection_mode` and `max_active_strategies`
  - active strategy-parameter combo application details are exposed through `aos_applied.strategy_combo` when present

### `POST /api/run/{run_id}/{ticker}/{date}/step|play|pause|resume|stop`

Purpose: Control progression of an initialized run.

Compatibility notes:

- `play` accepts body or query speed format (`max`, `10hz`, integer ms).
- marker/event ordering must remain stable for frontend playback.

### `GET /api/run/{run_id}/{ticker}/{date}/markers|summary|bars|state`

Purpose: Diagnostics and render payloads for frontend and analysis scripts.

Compatibility notes:

- marker schema changes require frontend compatibility checks.
- summary fields are consumed by reports and regression workflows.
- `total_pnl_pct` in runner summary is normalized from `total_pnl_dollars / account_size_usd` to keep percent and dollar PnL directionally consistent.

### `GET /api/aos-config` / `GET /api/aos-config/{ticker}` / `POST /api/aos-config/update`

Purpose: Read and persist per-ticker AOS settings used by runner start and strategy selection.

Compatibility notes:

- `POST /api/aos-config/update` merges provided `config` object into existing ticker config.
- Adaptive selection settings are file-backed (`aos_optimization/aos_config.json`) and applied on next `POST /api/run/start`.
- Supported adaptive switch-guard keys include `adaptive.min_active_bars_before_switch` and `adaptive.switch_cooldown_bars`.
- Strategy combination profiles are also file-backed under each ticker (`strategy_combo_profiles`, `active_strategy_combo_profile_id`) and active profile params are applied at run start.

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

Important response fields:

- `POST /api/adaptive-tuner/run`: `job_id`, `status`, tuned date range metadata
- `GET /api/adaptive-tuner/{job_id}`: full job object including `source_effective_dates`, sampled `effective_dates`, `trial_budget`, `progress`, `trials`, `best_trial`, and completion/error metadata
- `GET /api/adaptive-tuner`: reverse-chronological list of job objects (bounded by `limit`)

## Strategy API (Port 8001) - Key Contracts

### `POST /api/session/config`

Purpose: Set per-session execution/risk/L2 defaults before bar processing.

Key settings passed from runner:

- regime cadence: `regime_detection_minutes`, `regime_refresh_bars`
- risk/fill: `risk_per_trade_pct`, `max_position_notional_pct`, `max_fill_participation_rate`, `min_fill_ratio`
- stop-risk policy: `stop_loss_mode`, `fixed_stop_loss_pct`
- exits: `time_exit_bars`, `partial_take_profit_*`, `adverse_flow_*`
- L2 confirmation: `l2_confirm_enabled`, `l2_min_*`, `l2_lookback_bars`
- strategy selection: `strategy_selection_mode`, `max_active_strategies`
- reset policy: `cold_start_each_day`

### `POST /api/session/bar`

Purpose: Process one bar in-session and return decision payload.

Required bar fields:

- identity/time: `run_id`, `ticker`, `timestamp`
- OHLCV: `open`, `high`, `low`, `close`, `volume`

Optional fields:

- `vwap`
- L2 feature vector fields (`l2_*`)
- optional 1-second intrabar quotes for current minute (`intrabar_quotes_1s`: `[{"s","bid","ask"}]`)
- cross-asset reference bar (`ref_*`)

Behavioral guarantee:

- Processing must be no-lookahead (current/past context only).

Compatibility note:

- Legacy candlestick/multi-layer config endpoints are removed; strategy execution is evidence-engine only.

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
