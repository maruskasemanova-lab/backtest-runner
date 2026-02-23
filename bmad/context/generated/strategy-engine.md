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
| `../market_regime_detection/api_server.py` | yes | 1632 | `19dba61 2026-02-22` |
| `../market_regime_detection/src/api_models.py` | yes | 229 | `19dba61 2026-02-22` |
| `../market_regime_detection/src/day_trading_manager.py` | yes | 1718 | `19dba61 2026-02-22` |
| `../market_regime_detection/src/intraday_levels.py` | yes | 1342 | `a415569 2026-02-19` |
| `../market_regime_detection/src/multi_layer_decision.py` | yes | 41 | `19dba61 2026-02-22` |
| `../market_regime_detection/src/trading_orchestrator.py` | yes | 462 | `19dba61 2026-02-22` |
| `../market_regime_detection/src/feature_store.py` | yes | 900 | `caaa48e 2026-02-16` |
| `../market_regime_detection/src/ensemble_combiner.py` | yes | 461 | `19dba61 2026-02-22` |
| `../market_regime_detection/src/edge_monitor.py` | yes | 364 | `d33cc78 2026-02-07` |
| `../market_regime_detection/src/checkpoint.py` | yes | 284 | `d33cc78 2026-02-07` |
| `../market_regime_detection/src/adaptive_regime.py` | yes | 417 | `cf2281d 2026-02-08` |
| `../market_regime_detection/src/position_sizing.py` | yes | 145 | `d33cc78 2026-02-07` |
| `../market_regime_detection/src/evidence_decision.py` | yes | 529 | `19dba61 2026-02-22` |
| `../market_regime_detection/src/strategy_factory.py` | yes | 38 | `caaa48e 2026-02-16` |
| `../market_regime_detection/src/strategies/base_strategy.py` | yes | 561 | `f7e8133 2026-02-19` |
| `../market_regime_detection/src/strategies/momentum_flow.py` | yes | 176 | `a415569 2026-02-19` |
| `../market_regime_detection/src/strategies/absorption_reversal.py` | yes | 177 | `a415569 2026-02-19` |
| `../market_regime_detection/src/strategies/exhaustion_fade.py` | yes | 178 | `a415569 2026-02-19` |
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
- `function` `_apply_cors_headers_for_error` (line 111)
- `async_function` `_internal_api_token_guard` (line 135)
- `async_function` `root` (line 169)
- `async_function` `get_state` (line 174)
- `async_function` `get_regime` (line 180)
- `async_function` `get_strategies` (line 200)
- `async_function` `toggle_strategy` (line 216)
- `async_function` `update_strategy` (line 236)
- `async_function` `get_signals` (line 355)
- `async_function` `get_positions` (line 365)
- `async_function` `get_trades` (line 376)
- `async_function` `get_performance` (line 386)
- ... 27 more symbols

### `../market_regime_detection/src/api_models.py`
- `class` `StrategyToggle` (line 11)
- `class` `StrategyUpdate` (line 16)
- `class` `TrailingStopConfig` (line 21)
- `class` `BarInput` (line 28)
- `class` `SessionQuery` (line 79)
- `class` `TradingConfig` (line 87)

### `../market_regime_detection/src/day_trading_manager.py`
- `class` `DayTradingManager` (line 68)

### `../market_regime_detection/src/intraday_levels.py`
- `function` `_to_float` (line 8)
- `function` `_new_state` (line 17)
- `function` `ensure_intraday_levels_state` (line 129)
- `function` `_level_tolerance` (line 190)
- `function` `_trim_sequence` (line 194)
- `function` `_append_event` (line 202)
- `function` `_append_swing_point` (line 208)
- `function` `_register_level_from_swing` (line 228)
- `function` `_detect_and_register_swings` (line 287)
- `function` `_detect_and_register_spike_level` (line 352)
- `function` `_update_gap_context` (line 399)
- `function` `_true_range` (line 498)
- ... 12 more symbols

### `../market_regime_detection/src/multi_layer_decision.py`
- `class` `DecisionResult` (line 11)

### `../market_regime_detection/src/trading_orchestrator.py`
- `class` `OrchestratorConfig` (line 36)
- `class` `TradingOrchestrator` (line 75)

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
- `class` `RegimeState` (line 36)
- `class` `RuleBasedClassifier` (line 83)
- `class` `L2FlowClassifier` (line 132)
- `class` `VolatilityClassifier` (line 231)
- `class` `AdaptiveRegimeDetector` (line 276)

### `../market_regime_detection/src/position_sizing.py`
- `class` `SizingResult` (line 38)
- `class` `QualityPositionSizer` (line 58)

### `../market_regime_detection/src/evidence_decision.py`
- `class` `EvidenceSource` (line 38)
- `class` `EvidenceDecisionEngine` (line 48)

### `../market_regime_detection/src/strategy_factory.py`
- `function` `build_strategy_registry` (line 23)

### `../market_regime_detection/src/strategies/base_strategy.py`
- `class` `SignalType` (line 17)
- `class` `Regime` (line 25)
- `class` `Signal` (line 32)
- `class` `Position` (line 63)
- `class` `BaseStrategy` (line 203)

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
| `POST` | `/api/session/intrabar_eval` | `evaluate_intrabar_slice` | `../market_regime_detection/api_server.py` |
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
