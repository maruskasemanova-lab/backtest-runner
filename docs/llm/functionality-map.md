# Functionality Map

End-to-end behavior map across `backtest-runner` and `market_regime_detection`.

## System Topology

- Runner API (`backtest-runner`, port `8002`): run lifecycle, bar playback, data loading, WebSocket fanout.
- Strategy API (`market_regime_detection`, port `8001`): session processing, regime/strategy decisions, trade lifecycle, learning state.
- Frontend (`frontend`, port `5173`): controls, charts, marker timeline, diagnostics.

## Core Runtime Flow

1. Client calls `POST /api/run/start` on runner.
2. Runner resolves data, conditionally applies ticker strategy overrides (`apply_ticker_overrides_on_start`), applies AOS config (including per-ticker strategy-selection mode, active strategy-parameter combination profile, and adaptive strategy preferences), optional L2 enrichment.
3. Runner configures strategy session via `POST /api/session/config` (risk/L2 + strategy-selection settings).
4. Runner creates `SessionRunner` and stores it in active run registry.
5. On `step/play`, runner sends each bar to strategy `POST /api/session/bar`.
6. When execution is active (open position or pending next-bar entry), runner may attach 1-second intrabar top-of-book quotes for that minute (`intrabar_quotes_1s`) to improve intrabar SL/TP ordering.
7. Strategy returns decision payload; runner maps it to markers and summary state.
8. Runner broadcasts bar + decision updates over `/ws/live`.
9. Frontend consumes updates and renders timeline/summary.

## Session And State Model

- Runner key: `run_id:ticker:date_or_range`.
- Strategy session keying: `run_id + ticker + date`.
- Checkpoint behavior:
- warm start: load checkpoint + session-scoped reset
- cold start: full reset
- comparable mode: forced cold start and checkpoint ignored

## L2 Pipeline Map

1. Raw L2 files resolved by `src/l2_data_manager.py`.
2. Order-flow features computed in `src/order_flow_engine.py`.
3. Optional intrabar second-level artifacts built by `src/intrabar_frame_builder.py`.
4. 1s -> 1m aggregation/sanity in `src/l2_feature_aggregator.py`.
5. Features attached to runner bars via `src/l2_feature_service.py`.
6. Optional execution-time intrabar quote replay (`intrabar_quotes_1s`) is loaded lazily per-minute and sent only on execution bars.
7. Optional sessionized daily reset for cumulative L2 metrics in runner API.

## Strategy Engine Internals

- `day_trading_manager.py`: main session logic, execution realism, exits, risk controls.
- Adaptive strategy switching supports config-driven switch guards (`min_active_bars_before_switch`, `switch_cooldown_bars`) from AOS ticker config.
- `evidence_decision.py`: evidence-based execution scoring (strategy + L2/feature context).
- `multi_layer_decision.py`: shared `DecisionResult` contract for downstream payload compatibility.
- `trading_orchestrator.py`: learning state and cross-session adaptation.
- `feature_store.py`, `ensemble_combiner.py`, `edge_monitor.py`, `checkpoint.py`: feature memory, calibration, edge health, persistence.

## Optimization/Validation Flow

- `wfo_optimizer.py`: rolling search across parameter grids.
- `oos_validator.py`: strict chronological split (train/validation/test).
- `walk_forward_runner.py`: date-range simulation + report generation.
- `monte_carlo.py`: drawdown distribution/risk gate from trade PnL sequences.
- Runner adaptive tuner (`POST /api/adaptive-tuner/run`): date-range candidate search for Adaptive Studio v1 controls with grid/random/optuna modes, optional L2-only date filtering, and optional best-candidate persistence.
- Runner adaptive tuner quick mode: optional approximate tuning path that samples representative days and boosts trial budget so more candidate combinations can be screened faster.

## Frontend Behavioral Ownership

- `App.jsx`: orchestration of controls + data fetches + socket handling.
- `RunConfig.jsx`: run/session execution parameters, including optional selection of a saved adaptive tuned profile (applied before next run start).
- `DecisionPanel.jsx`: marker timeline and explanation details.
- `CandlestickChart.jsx` + related components: visual representation of bars/markers.
- `StrategySettings.jsx`: strategy toggles + per-strategy parameter editing with capture/apply strategy-combination profiles per ticker.
- `AdaptiveStrategyStudio.jsx`: adaptive selection-flow editor (saved to `aos_config.json` via `/api/aos-config/update` and applied on next run) with tuned-profile list/load/apply actions and strategy-combination-aware recomposition.
- `AdaptiveTuner.jsx`: adaptive v1 tuner UI tab with real OHLCV/L2 coverage ranges, date-range trial execution, scored candidate ranking, saved tuned profile list, and apply-to-backtest action.
- `AdaptiveTuner.jsx` quick approximation controls: optional sampled-day tuning (`quick_mode`) with configurable `quick_max_days` and `quick_trial_boost`.

For concrete file ownership and symbol inventory, use generated domain packs.
