# Story 13.2: Global vs Custom Trailing Source

Status: done

## Story

As a strategy operator,  
I want to choose trailing-stop source per strategy (`global` or `custom`),  
so that I can keep one module-level trailing baseline while selectively overriding strategies.

## Acceptance Criteria

1. Strategy API supports per-strategy `trailing_stop_mode` (`global|custom`).
2. Strategy API exposes `global_trailing_stop_pct` and computed `effective_trailing_stop_pct`.
3. Strategy signal generation uses effective trailing value based on selected mode.
4. Runner global trailing apply updates only global baseline, not per-strategy custom trailing params.
5. FE strategy editor allows selecting trailing source (`custom` or `global`) per strategy.

## File List

- `/Users/hotovo/.gemini/antigravity/scratch/market_regime_detection/src/strategies/base_strategy.py`
- `/Users/hotovo/.gemini/antigravity/scratch/market_regime_detection/src/strategies/*.py`
- `/Users/hotovo/.gemini/antigravity/scratch/market_regime_detection/api_server.py`
- `/Users/hotovo/.gemini/antigravity/scratch/market_regime_detection/tests/test_flow_strategy_behavior.py`
- `/Users/hotovo/.gemini/antigravity/scratch/market_regime_detection/tests/test_strategy_update_trailing_mode.py`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/src/services/strategy_api_updates_service.py`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/src/services/start_run_execution_config_service.py`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/src/services/start_run_service.py`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/src/aos_config.py`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/frontend/src/components/StrategySettings.tsx`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/frontend/src/components/RunConfig.tsx`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/frontend/src/components/AdaptiveStrategyStudio.tsx`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/tests/test_start_run_execution_config_service.py`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/tests/test_strategy_api_updates_service.py`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/docs/llm/api-contracts.md`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/docs/llm/functionality-map.md`
