# Domain: Flow Strategy Engine

**ID:** `strategy-engine`

## Mission

Own regime detection, signal generation, position management, learning components, and execution realism.

## Depends On

- `orchestration`
- `data-l2`

## Entrypoints

- `../market_regime_detection/api_server.py`
- `../market_regime_detection/src/day_trading_manager.py`
- `../market_regime_detection/src/trading_orchestrator.py`

## File Inventory

| File | Exists | Lines | Last Commit |
|---|---:|---:|---|
| `../market_regime_detection/api_server.py` | yes | 875 | `04e0601 2026-02-13` |
| `../market_regime_detection/src/api_models.py` | yes | 116 | `04e0601 2026-02-13` |
| `../market_regime_detection/src/day_trading_manager.py` | yes | 1490 | `04e0601 2026-02-13` |
| `../market_regime_detection/src/multi_layer_decision.py` | yes | 60 | `5e15927 2026-02-10` |
| `../market_regime_detection/src/trading_orchestrator.py` | yes | 464 | `5e15927 2026-02-10` |
| `../market_regime_detection/src/feature_store.py` | yes | 874 | `cf2281d 2026-02-08` |
| `../market_regime_detection/src/ensemble_combiner.py` | yes | 446 | `5e15927 2026-02-10` |
| `../market_regime_detection/src/edge_monitor.py` | yes | 364 | `d33cc78 2026-02-07` |
| `../market_regime_detection/src/checkpoint.py` | yes | 284 | `d33cc78 2026-02-07` |
| `../market_regime_detection/src/adaptive_regime.py` | yes | 400 | `cf2281d 2026-02-08` |
| `../market_regime_detection/src/position_sizing.py` | yes | 145 | `d33cc78 2026-02-07` |
| `../market_regime_detection/src/evidence_decision.py` | yes | 543 | `04e0601 2026-02-13` |
| `../market_regime_detection/src/strategy_factory.py` | yes | 38 | `0d786b7 2026-02-11` |
| `../market_regime_detection/src/strategies/base_strategy.py` | yes | 355 | `0d786b7 2026-02-11` |
| `../market_regime_detection/src/strategies/momentum_flow.py` | yes | 172 | `0d786b7 2026-02-11` |
| `../market_regime_detection/src/strategies/absorption_reversal.py` | yes | 173 | `0d786b7 2026-02-11` |
| `../market_regime_detection/src/strategies/exhaustion_fade.py` | yes | 174 | `0d786b7 2026-02-11` |
| `../market_regime_detection/src/strategies/trailing_stop.py` | yes | 301 | `94c21fc 2026-02-01` |

## Change Checks

- No same-bar signal execution (signal bar index must be < entry bar index).
- Risk/execution changes must be reflected in config endpoints and tests.
- Keep flow metrics no-lookahead (past/current bars only).
- Session reset scope (session vs full) must remain explicit and test-covered.

## Critical Invariants

- Signal generation and execution must remain no-lookahead.
- Position sizing and fill simulation must respect configured risk caps.
- Checkpoint save/load must preserve learning state version compatibility.
- Run defaults must apply deterministically per run/ticker/date context.

## Test Targets

- `tests/test_execution_realism.py`
- `tests/test_multilayer_strategy_only_threshold.py`
- `tests/test_multilayer_weight_source.py`
- `tests/test_day_trading_manager_atr_fallback.py`
- `/Users/hotovo/.gemini/antigravity/scratch/market_regime_detection/tests/test_trading_orchestrator_reset.py`
- `/Users/hotovo/.gemini/antigravity/scratch/market_regime_detection/tests/test_checkpoint.py`
- `/Users/hotovo/.gemini/antigravity/scratch/market_regime_detection/tests/test_adaptive_regime.py`
- `/Users/hotovo/.gemini/antigravity/scratch/market_regime_detection/tests/test_feature_store.py`
- `/Users/hotovo/.gemini/antigravity/scratch/market_regime_detection/tests/test_edge_monitor.py`
- `/Users/hotovo/.gemini/antigravity/scratch/market_regime_detection/tests/test_ensemble_combiner.py`

## Key Symbols

### `../market_regime_detection/api_server.py`
- `async_function` `root` (line 54)
- `async_function` `get_state` (line 59)
- `async_function` `get_regime` (line 65)
- `async_function` `get_strategies` (line 85)
- `async_function` `toggle_strategy` (line 101)
- `async_function` `update_strategy` (line 121)
- `async_function` `get_signals` (line 155)
- `async_function` `get_positions` (line 165)
- `async_function` `get_trades` (line 176)
- `async_function` `get_performance` (line 186)
- `async_function` `step_backtest` (line 192)
- `async_function` `run_backtest` (line 199)
- ... 24 more symbols

### `../market_regime_detection/src/api_models.py`
- `class` `StrategyToggle` (line 11)
- `class` `StrategyUpdate` (line 16)
- `class` `TrailingStopConfig` (line 21)
- `class` `BarInput` (line 28)
- `class` `SessionQuery` (line 76)
- `class` `TradingConfig` (line 84)

### `../market_regime_detection/src/day_trading_manager.py`
- `class` `DayTradingManager` (line 80)

### `../market_regime_detection/src/multi_layer_decision.py`
- `class` `DecisionResult` (line 11)

### `../market_regime_detection/src/trading_orchestrator.py`
- `class` `OrchestratorConfig` (line 36)
- `class` `TradingOrchestrator` (line 76)

### `../market_regime_detection/src/feature_store.py`
- `class` `FeatureVector` (line 22)
- `class` `RollingStats` (line 110)
- `class` `FeatureStore` (line 154)

### `../market_regime_detection/src/ensemble_combiner.py`
- `class` `CalibratedSignal` (line 32)
- `class` `EnsembleScore` (line 43)
- `class` `SourcePerformance` (line 72)
- `class` `AdaptiveWeightCombiner` (line 106)

### `../market_regime_detection/src/edge_monitor.py`
- `class` `EdgeStatus` (line 32)
- `class` `RecommendedAction` (line 40)
- `class` `EdgeHealth` (line 48)
- `class` `TradeRecord` (line 75)
- `class` `StrategyEdgeTracker` (line 85)
- `class` `EdgeMonitor` (line 161)

### `../market_regime_detection/src/checkpoint.py`
- `function` `_serialize_isotonic` (line 36)
- `function` `_serialize_calibrator` (line 44)
- `function` `_serialize_edge_tracker` (line 56)
- `function` `_serialize_edge_monitor` (line 65)
- `function` `_serialize_source_perf` (line 76)
- `function` `_serialize_combiner` (line 85)
- `function` `_restore_isotonic` (line 101)
- `function` `restore_calibrator` (line 110)
- `function` `restore_edge_monitor` (line 127)
- `function` `_restore_source_perf` (line 157)
- `function` `restore_combiner` (line 167)
- `function` `save_checkpoint` (line 186)
- ... 2 more symbols

### `../market_regime_detection/src/adaptive_regime.py`
- `class` `RegimeState` (line 37)
- `class` `RuleBasedClassifier` (line 84)
- `class` `L2FlowClassifier` (line 133)
- `class` `VolatilityClassifier` (line 218)
- `class` `AdaptiveRegimeDetector` (line 263)

### `../market_regime_detection/src/position_sizing.py`
- `class` `SizingResult` (line 38)
- `class` `QualityPositionSizer` (line 58)

### `../market_regime_detection/src/evidence_decision.py`
- `class` `EvidenceSource` (line 38)
- `class` `EvidenceDecisionEngine` (line 48)

### `../market_regime_detection/src/strategy_factory.py`
- `function` `build_strategy_registry` (line 23)

### `../market_regime_detection/src/strategies/base_strategy.py`
- `class` `SignalType` (line 11)
- `class` `Regime` (line 19)
- `class` `Signal` (line 26)
- `class` `Position` (line 57)
- `class` `BaseStrategy` (line 161)

### `../market_regime_detection/src/strategies/momentum_flow.py`
- `class` `MomentumFlowStrategy` (line 12)

### `../market_regime_detection/src/strategies/absorption_reversal.py`
- `class` `AbsorptionReversalStrategy` (line 13)

### `../market_regime_detection/src/strategies/exhaustion_fade.py`
- `class` `ExhaustionFadeStrategy` (line 12)

### `../market_regime_detection/src/strategies/trailing_stop.py`
- `class` `StopType` (line 9)
- `class` `TrailingStopConfig` (line 20)
- `class` `TrailingStopManager` (line 31)

## Endpoint Summary

| Method | Path | Handler | File |
|---|---|---|---|
| `GET` | `/` | `root` | `../market_regime_detection/api_server.py` |
| `GET` | `/api/state` | `get_state` | `../market_regime_detection/api_server.py` |
| `GET` | `/api/regime` | `get_regime` | `../market_regime_detection/api_server.py` |
| `GET` | `/api/strategies` | `get_strategies` | `../market_regime_detection/api_server.py` |
| `POST` | `/api/strategies/toggle` | `toggle_strategy` | `../market_regime_detection/api_server.py` |
| `POST` | `/api/strategies/update` | `update_strategy` | `../market_regime_detection/api_server.py` |
| `GET` | `/api/signals` | `get_signals` | `../market_regime_detection/api_server.py` |
| `GET` | `/api/positions` | `get_positions` | `../market_regime_detection/api_server.py` |
| `GET` | `/api/trades` | `get_trades` | `../market_regime_detection/api_server.py` |
| `GET` | `/api/performance` | `get_performance` | `../market_regime_detection/api_server.py` |
| `POST` | `/api/step` | `step_backtest` | `../market_regime_detection/api_server.py` |
| `POST` | `/api/run` | `run_backtest` | `../market_regime_detection/api_server.py` |
| `POST` | `/api/reset` | `reset_engine` | `../market_regime_detection/api_server.py` |
| `GET` | `/api/current` | `get_current_price` | `../market_regime_detection/api_server.py` |
| `GET` | `/api/history` | `get_history` | `../market_regime_detection/api_server.py` |
| `GET` | `/api/indicators` | `get_all_indicators` | `../market_regime_detection/api_server.py` |
| `POST` | `/api/session/bar` | `process_bar` | `../market_regime_detection/api_server.py` |
| `GET` | `/api/session` | `get_session` | `../market_regime_detection/api_server.py` |
| `GET` | `/api/session/signals` | `get_session_signals` | `../market_regime_detection/api_server.py` |
| `GET` | `/api/session/trades` | `get_session_trades` | `../market_regime_detection/api_server.py` |
| `POST` | `/api/session/end` | `end_session` | `../market_regime_detection/api_server.py` |
| `GET` | `/api/sessions` | `list_sessions` | `../market_regime_detection/api_server.py` |
| `DELETE` | `/api/session` | `clear_session` | `../market_regime_detection/api_server.py` |
| `DELETE` | `/api/session/run` | `clear_run_sessions` | `../market_regime_detection/api_server.py` |
| `GET` | `/api/config/trading` | `get_trading_config` | `../market_regime_detection/api_server.py` |
| `POST` | `/api/config/trading` | `update_trading_config` | `../market_regime_detection/api_server.py` |
| `POST` | `/api/session/config` | `configure_session` | `../market_regime_detection/api_server.py` |
| `POST` | `/api/orchestrator/reset` | `reset_orchestrator_state` | `../market_regime_detection/api_server.py` |
| `GET` | `/api/system/health` | `get_system_health` | `../market_regime_detection/api_server.py` |
| `GET` | `/api/orchestrator/config` | `get_orchestrator_config` | `../market_regime_detection/api_server.py` |
| `POST` | `/api/orchestrator/config` | `update_orchestrator_config` | `../market_regime_detection/api_server.py` |
| `POST` | `/api/orchestrator/checkpoint/save` | `save_checkpoint` | `../market_regime_detection/api_server.py` |
| `POST` | `/api/orchestrator/checkpoint/load` | `load_checkpoint_endpoint` | `../market_regime_detection/api_server.py` |
| `GET` | `/api/orchestrator/checkpoints` | `list_checkpoints` | `../market_regime_detection/api_server.py` |
| `POST` | `/api/orchestrator/warmup` | `warmup_feature_store` | `../market_regime_detection/api_server.py` |
| `WEBSOCKET` | `/ws` | `websocket_endpoint` | `../market_regime_detection/api_server.py` |

## Prompt Primer

Load this domain pack with `bmad/context/generated/00-index.md` and `bmad/context/generated/00-machine-index.json`, then keep edits scoped to mapped files unless interface changes are explicit.
