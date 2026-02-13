# Current State Map (Adaptive + Momentum + L2 + CVD)

## 1) End-to-end Runtime Path

### 1.1 Runner start flow
- Entry: `POST /api/run/start` -> `start_run()` in `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/src/services/start_run_service.py:266`.
- Execution config resolution (L2 gates, selection mode, risk/exits):
  - `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/src/services/start_run_execution_config_service.py:6`
- L2 enrichment and optional sessionization:
  - `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/src/services/start_run_data_service.py:757`
- Session config push to strategy API (`/api/session/config`) happens after enrichment and effective-L2 resolution:
  - call site in `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/src/services/start_run_service.py:573`

### 1.2 Strategy config ingest
- Strategy API endpoint: `/api/session/config` in `/Users/hotovo/.gemini/antigravity/scratch/market_regime_detection/api_server.py:506`.
- It sets session fields + run defaults (`set_run_defaults`) in day-trading manager.
- `momentum_diversification_json` is decoded and normalized in strategy API before storing in session/defaults.

### 1.3 Bar processing loop
- Runner sends bars through `SessionRunner._process_bar()`:
  - `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/session_runner.py:286`
- Payload includes base OHLCV + selected L2 keys via `L2_PAYLOAD_KEYS`:
  - `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/session_runner.py:36`
- Strategy receives via `BarInput`:
  - `/Users/hotovo/.gemini/antigravity/scratch/market_regime_detection/src/api_models.py:28`
- Strategy processing entrypoint:
  - `/Users/hotovo/.gemini/antigravity/scratch/market_regime_detection/api_server.py:244`
  - delegates to `DayTradingManager.process_bar()`.

## 2) Config Precedence (Current)

### 2.1 Momentum diversification precedence (runner side)
In `start_run()`:
1. request override
2. active adaptive profile runtime override
3. AOS ticker adaptive config
4. none

Source anchors:
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/src/services/start_run_service.py:379`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/src/services/start_run_service.py:400`

Effective payload is serialized as `momentum_diversification_json` and sent to strategy API.

### 2.2 Strategy-selection and max-active precedence
In `resolve_execution_config()`:
- `strategy_selection_mode`: profile -> request -> AOS
- `max_active_strategies`: profile -> request -> AOS

Source anchors:
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/src/services/start_run_execution_config_service.py:52`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/src/services/start_run_execution_config_service.py:80`

### 2.3 L2 enablement behavior
- Request + AOS flags determine requested L2.
- Guard can disable L2 on wide date ranges (`BACKTEST_RUN_L2_MAX_DAYS`).
- Effective `l2_confirm_enabled` becomes true only if L2 coverage exists.

Source anchors:
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/src/services/start_run_service.py:56`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/src/services/start_run_service.py:439`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/src/services/start_run_service.py:533`

## 3) Strategy Engine Logic Layout

### 3.1 Core adaptive + momentum routing surface
- Momentum config normalization:
  - `/Users/hotovo/.gemini/antigravity/scratch/market_regime_detection/src/day_trading_manager.py:756`
- Momentum config resolution for session:
  - `/Users/hotovo/.gemini/antigravity/scratch/market_regime_detection/src/day_trading_manager.py:1939`
- Multi-sleeve selection:
  - `/Users/hotovo/.gemini/antigravity/scratch/market_regime_detection/src/day_trading_manager.py:1956`
- Route candidate builder:
  - `/Users/hotovo/.gemini/antigravity/scratch/market_regime_detection/src/day_trading_manager.py:2036`
- Active strategy selection (mode + filters + route bias):
  - `/Users/hotovo/.gemini/antigravity/scratch/market_regime_detection/src/day_trading_manager.py:2118`

### 3.2 L2/CVD-style flow metric computation
- Computed on recent bars, no look-ahead, includes:
  - cumulative delta (CVD-like), signed aggression, directional consistency,
  - delta acceleration, delta-price divergence, flow_score,
  - last-bar body/close-location features.
- Function:
  - `/Users/hotovo/.gemini/antigravity/scratch/market_regime_detection/src/day_trading_manager.py:1734`

### 3.3 Signal gates (in order)
Inside trading bar processing:
1. L2 confirmation gate (`_passes_l2_confirmation`)
2. momentum_flow divergence confirmation gate
3. momentum diversification gate (single or sleeve-aware)

Anchors:
- call sequence around `/Users/hotovo/.gemini/antigravity/scratch/market_regime_detection/src/day_trading_manager.py:2951`
- L2 gate implementation: `/Users/hotovo/.gemini/antigravity/scratch/market_regime_detection/src/day_trading_manager.py:3987`
- momentum diversification gate implementation:
  - `/Users/hotovo/.gemini/antigravity/scratch/market_regime_detection/src/day_trading_manager.py:3740`
  - candidate evaluator: `/Users/hotovo/.gemini/antigravity/scratch/market_regime_detection/src/day_trading_manager.py:3563`

### 3.4 Position fail-fast behavior
- Momentum fail-fast exit uses selected sleeve config + short lookback flow flip checks.
- Function:
  - `/Users/hotovo/.gemini/antigravity/scratch/market_regime_detection/src/day_trading_manager.py:3825`

### 3.5 Regime refresh and switch guards
- Regime hysteresis and strategy-switch guard logic:
  - `/Users/hotovo/.gemini/antigravity/scratch/market_regime_detection/src/day_trading_manager.py:2456`
- Edge warmup/ramp adjustment:
  - `/Users/hotovo/.gemini/antigravity/scratch/market_regime_detection/src/day_trading_manager.py:2589`

## 4) Adaptive Tuner V1/V2 Wiring

### 4.1 Request model
- Includes v1 dimensions + v2 multi-dimensional and momentum-specific dimensions:
  - `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/src/models/tuner_requests.py:6`

### 4.2 V2 search space and candidate transform
- Search-space construction:
  - `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/src/services/adaptive_tuner_v2_service.py:28`
- Candidate -> ticker config materialization:
  - `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/src/services/adaptive_tuner_v2_service.py:492`

### 4.3 Candidate runtime evaluation
- V1 eval:
  - `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/src/services/adaptive_tuner_runtime_service.py:32`
- V2 eval:
  - `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/src/services/adaptive_tuner_runtime_service.py:160`
- V2 worker loop:
  - `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/src/services/adaptive_tuner_worker_service.py:37`
- V1 worker loop:
  - `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/src/services/adaptive_tuner_worker_service.py:361`

### 4.4 Active adaptive profile runtime overrides
- Candidate extraction + conversion to runtime overrides:
  - `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/src/services/strategy_api_profiles_service.py:38`
  - `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/src/services/strategy_api_profiles_service.py:65`
- Includes flattening from `momentum_*` keys into nested `momentum_diversification`.

## 5) L2/CVD Data Path (Runner Side)

- L2 minute feature map:
  - `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/src/l2_feature_service.py:43`
- Order-flow metrics (delta/cvd-like/acceleration/divergence/book pressure):
  - `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/src/order_flow_engine.py:174`
  - `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/src/order_flow_engine.py:254`
- Attach to bars:
  - `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/src/l2_feature_service.py:151`
- Sessionized-by-market-day behavior for comparable multi-day runs:
  - `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/src/services/start_run_data_service.py:787`
  - `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/src/services/start_run_data_service.py:841`

## 6) Frontend Config Surfaces

- Run-time override builder (`momentum_diversification_override` + sleeve editor):
  - `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/frontend/src/components/RunConfig.jsx:260`
- AOS editor builder (`adaptive.momentum_diversification` + sleeve editor):
  - `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/frontend/src/components/AOSOptimizations.jsx:274`

Both implement their own normalization/clamping logic in JS.

## 7) High-Signal Test Anchors

- Runner start + momentum override pass-through:
  - `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/tests/test_start_run_strategy_overrides_mode.py`
- Tuner v2 search/config/runtime expectations:
  - `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/tests/test_adaptive_tuner_api.py`
- Strategy selection and momentum route/sleeves behavior:
  - `/Users/hotovo/.gemini/antigravity/scratch/market_regime_detection/tests/test_day_trading_manager_strategy_selection_mode.py`
- Strategy run-default momentum override behavior:
  - `/Users/hotovo/.gemini/antigravity/scratch/market_regime_detection/tests/test_day_trading_manager_positioning_defaults.py`
