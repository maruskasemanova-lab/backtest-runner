# Backend Refactor Hotspots Plan (BMAD)

Date: 2026-02-20  
Primary execution order: `orchestration` -> `strategy-engine` -> `data-l2`

## Goal

Identify the longest and least maintainable backend files, then define a BMAD-ready refactor architecture and execution plan that preserves:

- no-lookahead invariants,
- `signal_bar_index < entry_bar_index`,
- backward-compatible runner/strategy API contracts,
- deterministic `comparable_mode` cold-start behavior.

## How Hotspots Were Ranked

Composite score from:

- LOC (`wc -l`)
- complexity findings from `ruff` (`C901`, `PLR0912`, `PLR0915`)
- largest function size (AST length)
- branch density (AST conditional/control nodes)

Command inputs:

- `ruff check ... --select C901,PLR0912,PLR0915`
- AST scan over backend runtime modules in `backtest-runner` and `market_regime_detection`

## Backend Hotspots (Priority List)

| Priority | File | Domain | LOC | Ruff hits | Worst function |
|---|---|---|---:|---:|---|
| P0 | `src/services/start_run_execution_config_service.py` | orchestration | 1628 | 3 | `resolve_execution_config` @ line 7 (~1622 lines, C901=136) |
| P0 | `../market_regime_detection/src/day_trading_runtime_impl.py` | strategy-engine | 2833 | 19 | `runtime_process_trading_bar` @ line 1574 (~1017 lines, C901=86) |
| P0 | `src/services/start_run_service.py` | orchestration | 2225 | 6 | `start_run` @ line 617 (~1365 lines, C901=55) |
| P0 | `session_runner.py` | orchestration | 1647 | 13 | `_process_decision_markers` @ line 843 (~425 lines, C901=50) |
| P1 | `src/databento_service.py` | data-l2 | 1728 | 18 | `download` @ line 1480 (~219 lines) |
| P1 | `../market_regime_detection/src/day_trading_regime_impl.py` | strategy-engine | 1131 | 18 | `regime_calculate_order_flow_metrics` @ line 164 (~259 lines) |
| P1 | `src/routes/system_routes.py` | orchestration | 1618 | 15 | `get_saved_run_history` @ line 1380 (~239 lines, C901=27) |
| P1 | `src/l2_data_manager.py` | data-l2 | 1067 | 16 | `detect_icebergs` @ line 763 (~198 lines, C901=23) |
| P1 | `../market_regime_detection/src/exit_policy_engine.py` | strategy-engine | 2011 | 9 | `update_trailing_from_close` @ line 808 (~270 lines, C901=33) |
| P1 | `src/services/strategy_api_profiles_service.py` | orchestration | 792 | 11 | `apply_aos_optimizations` @ line 514 (~279 lines, C901=45) |
| P2 | `../market_regime_detection/api_server.py` | strategy-engine | 1405 | 6 | `configure_session` @ line 784 (~364 lines) |
| P2 | `api_server.py` | orchestration | 2657 | 4 | `_configure_session` @ line 1765 (~181 lines) |
| P2 | `../market_regime_detection/src/strategies/vwap_magnet.py` | strategy-engine | 295 | 3 | `generate_signal` @ line 104 (~179 lines, C901=20) |

Notes:

- `start_run_execution_config_service.py` and `day_trading_runtime_impl.py` are the highest-risk monoliths.
- `vwap_magnet.py` is not the largest file, but `generate_signal` is long/branchy and should be normalized with other strategy modules after P0/P1.

## Target Refactor Architecture

### 1) Orchestration Config Pipeline (P0)

Current issue:
- one giant resolver (`resolve_execution_config`) mixes parsing, defaults, overrides, validation, and contract shaping.

Target structure:

- `src/services/execution_config/resolver.py` (thin orchestration)
- `src/services/execution_config/defaults.py`
- `src/services/execution_config/profile_overrides.py`
- `src/services/execution_config/positioning_overrides.py`
- `src/services/execution_config/l2_and_intrabar.py`
- `src/services/execution_config/intraday_levels.py`
- `src/services/execution_config/context_risk.py`
- `src/services/execution_config/schema.py`

Contract guardrails:

- preserve output shape consumed by `/api/run/start` and strategy `/api/session/config`.
- keep all existing field aliases and fallback semantics.

### 2) Start Run Orchestrator Decomposition (P0)

Current issue:
- `start_run` handles orchestration, data loading, prewarm logic, API fanout, and telemetry in one path.

Target structure:

- `src/services/start_run/phases/resolve_inputs.py`
- `src/services/start_run/phases/load_data.py`
- `src/services/start_run/phases/apply_profiles.py`
- `src/services/start_run/phases/configure_strategy_session.py`
- `src/services/start_run/phases/register_run.py`
- `src/services/start_run/phases/emit_telemetry.py`

Pattern:

- explicit phase DTO (`StartRunContext`) passed step-by-step
- each phase pure where possible + deterministic side effects

### 3) Strategy Runtime Split (P0)

Current issue:
- `day_trading_runtime_impl.py` combines bar orchestration, entry-quality gate, indicator updates, and execution transitions.

Target structure:

- `../market_regime_detection/src/runtime/bar_pipeline.py`
- `../market_regime_detection/src/runtime/entry_quality_gate.py`
- `../market_regime_detection/src/runtime/indicator_runtime.py`
- `../market_regime_detection/src/runtime/position_transitions.py`
- `../market_regime_detection/src/runtime/intrabar_snapshot.py`

Safety boundary:

- keep event order deterministic: signal evaluation and execution sequencing must stay causal.
- enforce no same-bar signal execution invariant via shared guard helper.

### 4) Marker/Session Payload Builder Split (P0)

Current issue:
- `session_runner.py` marker builders are tightly coupled to payload shapes and diagnostics.

Target structure:

- `src/services/markers/marker_builder.py`
- `src/services/markers/market_context_builder.py`
- `src/services/markers/summary_builder.py`
- `src/services/markers/schema_guards.py`

Outcome:

- easier schema testing and safer payload evolution.

### 5) L2/Data Services Split (P1)

Current issue:
- `databento_service.py` + `l2_data_manager.py` mix file IO, catalog logic, and feature extraction wiring.

Target structure:

- `src/services/databento/catalog_service.py`
- `src/services/databento/download_service.py`
- `src/services/databento/range_resolver.py`
- `src/services/l2/feature_map_loader.py`
- `src/services/l2/iceberg_detector.py`
- `src/services/l2/sessionization.py`

### 6) Strategy Policy Modules (P1/P2)

Focus files:

- `day_trading_regime_impl.py`
- `exit_policy_engine.py`
- `strategies/vwap_magnet.py`

Target:

- split large policy functions into composable calculators with immutable inputs.
- make decision trace payload assembly explicit and unit-testable.

## BMAD Epic + Story Plan

Proposed epic: `EPIC-06: Backend Monolith Refactor`

Stories:

1. `BR-01` (orchestration, P0): split execution config resolver monolith.
2. `BR-02` (orchestration, P0): split `start_run` into deterministic phases.
3. `BR-03` (orchestration, P0): extract marker/summary builders from `session_runner.py`.
4. `BR-04` (strategy-engine, P0): split runtime pipeline in `day_trading_runtime_impl.py`.
5. `BR-05` (strategy-engine, P1): decompose regime + exit policy modules.
6. `BR-06` (data-l2, P1): split databento and L2 manager services.
7. `BR-07` (strategy-engine, P2): normalize large strategy modules (`vwap_magnet` + siblings).

## Test and Validation Gates

For every story:

- `python3 scripts/generate_context_pack.py`
- `python3 scripts/validate_llm_context.py --strict`

Domain tests:

- orchestration:
  - `pytest tests/test_no_lookahead.py tests/test_session_runner_markers.py tests/test_decision_tracker_schema_v2.py`
- strategy-engine:
  - `pytest /Users/hotovo/.gemini/antigravity/scratch/market_regime_detection/tests/test_trading_orchestrator_reset.py /Users/hotovo/.gemini/antigravity/scratch/market_regime_detection/tests/test_checkpoint.py`
- data-l2:
  - `pytest tests/test_l2_feature_aggregator.py tests/test_api_server_l2_sessionized.py`

## Residual Risks

1. Hidden coupling between config fields and frontend form defaults can break backward compatibility.
2. Strategy runtime splits can accidentally reorder execution logic; causality tests are mandatory.
3. L2 refactors can leak future data if minute/session boundaries are not preserved exactly.

## Rollback Strategy

1. Keep wrapper functions in original modules during each phase.
2. Route old call paths to new modules under feature flags until tests stabilize.
3. If any invariant test fails, revert current story only and keep previous decompositions intact.
