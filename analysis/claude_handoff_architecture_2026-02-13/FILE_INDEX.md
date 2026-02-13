# File Index (Fast Navigation)

## Runner: Start + Config + L2
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/src/services/start_run_service.py`
  - Orchestration entry, config precedence, configure-session call.
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/src/services/start_run_execution_config_service.py`
  - Effective execution config precedence logic.
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/src/services/start_run_data_service.py`
  - L2 enrichment, caching, sessionized-by-market-day behavior.
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/src/momentum_diversification.py`
  - Runner-side momentum payload normalizer.

## Runner: Tuner
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/src/models/tuner_requests.py`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/src/services/adaptive_tuner_v2_service.py`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/src/services/adaptive_tuner_runtime_service.py`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/src/services/adaptive_tuner_worker_service.py`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/src/services/strategy_api_profiles_service.py`

## Runner <-> Strategy payload boundary
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/session_runner.py`
  - `L2_PAYLOAD_KEYS`, bar payload to strategy.
- `/Users/hotovo/.gemini/antigravity/scratch/market_regime_detection/src/api_models.py`
  - `BarInput` accepted fields.
- `/Users/hotovo/.gemini/antigravity/scratch/market_regime_detection/api_server.py`
  - `/api/session/bar` + `/api/session/config` handlers.

## Strategy engine (core)
- `/Users/hotovo/.gemini/antigravity/scratch/market_regime_detection/src/day_trading_manager.py`
  - Selection, adaptive routing, L2 gate, momentum gate, fail-fast, run-default application.

## Frontend config surfaces
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/frontend/src/components/RunConfig.jsx`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/frontend/src/components/AOSOptimizations.jsx`

## Config state
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/aos_optimization/aos_config.json`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/strategy_overrides.json`
