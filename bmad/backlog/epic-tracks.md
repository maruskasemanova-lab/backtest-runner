# Epic Tracks

This roadmap is optimized for your dual-service architecture and flow-first strategy stack.

## EPIC-01: Execution Realism & Risk Engine (P0)

Objective: make backtest execution assumptions harder to overfit and closer to live constraints.

Success metrics:
- No-lookahead invariants preserved.
- Cost model covers slippage, fees, and market impact consistently.
- Risk controls are configurable per run and visible in API responses.

Stories:
- `ER-01` Partial-fill model with deterministic participation caps.
  - Domain: `strategy-engine`
  - Key files: `../market_regime_detection/src/day_trading_manager.py`, `../market_regime_detection/api_server.py`
  - Acceptance: entry fills capped by bar liquidity and recorded via `fill_ratio`.
- `ER-02` Time exit + adverse flow exit validation pack.
  - Domain: `strategy-engine`
  - Key files: `../market_regime_detection/src/day_trading_manager.py`, `tests/test_execution_realism.py`
  - Acceptance: unit tests cover both exits and remain green.
- `ER-03` Cross-service execution config contract hardening.
  - Domain: `orchestration`
  - Key files: `api_server.py`, `../market_regime_detection/api_server.py`
  - Acceptance: all execution knobs passed from runner to strategy service.

## EPIC-02: Flow-First Signal System (P1)

Objective: reduce dependence on candlestick layer and let L2 microstructure drive decisions.

Success metrics:
- Flow strategies are primary candidates when L2 coverage is present.
- Candlestick layer is optional and low-impact by default.
- Signal confidence relies on flow metrics + historical edge adjustment.

Stories:
- `FF-01` Remove pattern gating from flow-only operation profile.
  - Domain: `strategy-engine`
  - Key files: `../market_regime_detection/src/multi_layer_decision.py`, `../market_regime_detection/src/day_trading_manager.py`
  - Acceptance: strategy-only mode works without pattern detections.
- `FF-02` Extend microstructure metrics: large trader + VWAP execution flow.
  - Domain: `strategy-engine`
  - Key files: `../market_regime_detection/src/day_trading_manager.py`
  - Acceptance: metrics appear in regime payload and layer scores.
- `FF-03` Strategy tuning matrix for flow strategies.
  - Domain: `optimization-validation`
  - Key files: `wfo_optimizer.py`, `oos_validator.py`
  - Acceptance: parameter grids include `momentum_flow`, `absorption_reversal`, `exhaustion_fade`.

## EPIC-03: Optimization & OOS Discipline (P1)

Objective: separate tuning from final evaluation and quantify robustness.

Success metrics:
- Dedicated hold-out test split exists and is never used during search.
- Monte Carlo DD analysis runs from trade CSVs.
- Reports include regime/hour/weekday breakdowns.

Stories:
- `OV-01` 60/20/20 OOS validator reporting improvements.
  - Domain: `optimization-validation`
  - Key files: `oos_validator.py`
  - Acceptance: output contains train/validation/test metrics per ticker.
- `OV-02` Monte Carlo CI hook for risk threshold.
  - Domain: `optimization-validation`
  - Key files: `monte_carlo.py`
  - Acceptance: script returns non-zero (or explicit flag) when P95 DD exceeds threshold.
- `OV-03` Ranking by regime/hour/day in walk-forward report.
  - Domain: `optimization-validation`
  - Key files: `performance_tracker.py`, `walk_forward_runner.py`
  - Acceptance: report JSON includes `hourly_summary` and `weekday_summary`.

## EPIC-04: API Contracts & Observability (P2)

Objective: keep large refactors safe through explicit contracts and diagnostics.

Success metrics:
- API contract changes are versioned or backward-compatible.
- Session diagnostics expose enough data for replay/debug.
- Frontend receives stable marker schemas.

Stories:
- `AO-01` Contract table for `/api/run/start` and `/api/session/config`.
  - Domain: `orchestration`
  - Key files: `README.md`, `bmad/context/component-map.json`
  - Acceptance: documented field-level contract and defaults.
- `AO-02` Decision payload schema tests.
  - Domain: `orchestration`
  - Key files: `session_runner.py`, `tests/*`
  - Acceptance: snapshot or schema test for marker payloads.
- `AO-03` Regime refresh telemetry expansion.
  - Domain: `strategy-engine`
  - Key files: `../market_regime_detection/src/day_trading_manager.py`
  - Acceptance: telemetry contains previous/new regime + cause metrics.

## EPIC-05: Frontend Expert Mode (P2)

Objective: make diagnostics actionable while keeping playback UX clear.

Success metrics:
- L2 flow diagnostics visible without opening raw logs.
- Risk/execution knobs editable from run config.
- Marker timeline supports fast root-cause tracing.

Stories:
- `FE-01` Add execution/risk controls to run form.
  - Domain: `frontend`
  - Key files: `frontend/src/components/RunConfig.jsx`
  - Acceptance: controls map 1:1 to `/api/run/start` execution config.
- `FE-02` L2 diagnostics card.
  - Domain: `frontend`
  - Key files: `frontend/src/components/DecisionPanel.jsx`, `frontend/src/components/SessionSummary.jsx`
  - Acceptance: shows flow score, aggression, absorption, large trader activity.
- `FE-03` Marker detail drill-down for partial exits and adverse flow exits.
  - Domain: `frontend`
  - Key files: `frontend/src/components/DecisionPanel.jsx`
  - Acceptance: marker details show new exit reasons and cost components.
