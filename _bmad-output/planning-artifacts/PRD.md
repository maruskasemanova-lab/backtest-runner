---
stepsCompleted: []
date: '2026-02-09'
classification:
  domain: general
  projectType: other
  domainContext: algorithmic-trading
  lifecycle: brownfield
inputDocuments:
  - _bmad-output/planning-artifacts/architecture-existing.md
  - _bmad-output/planning-artifacts/stories-existing.md
  - plans/final-architecture-plan.md
  - plans/architecture-analysis.md
  - bmad/backlog/epic-tracks.md
workflowType: 'prd'
---

# Product Requirements Document - backtest-runner

**Author:** Codex  
**Date:** 2026-02-09

## Executive Summary

This PRD defines the product requirements for improving the existing dual-service trading stack:

- `backtest-runner` (orchestration + visualization)
- `market_regime_detection` (strategy engine)

The architecture source states that a new repository is not required. Scope is aligned to the already-defined epic tracks (EPIC-01..EPIC-05) and existing architecture decisions only.

## Background and Problem Statement

From the source architecture analysis:

- The current system already supports bar-by-bar testing and visualization, but execution realism and contract hardening need improvement.
- There is architecture ambiguity around LEAN (`bmad-backtest-lite`) integration vs. the dual-service stack.
- There are known risks around duplicated strategy logic and unclear source-of-truth boundaries.

From epic tracks, the planned direction is to:

- strengthen execution realism and risk controls,
- prioritize flow/L2-first decisioning,
- enforce optimization and out-of-sample discipline,
- stabilize API/marker contracts,
- improve frontend diagnostics and controls.

## Product Goals

1. Improve backtest realism and reduce overfitting risk in execution behavior.
2. Make flow-first (L2/microstructure) decisioning the primary strategy path where coverage exists.
3. Enforce chronological validation discipline (train/validation/test split + Monte Carlo risk gating).
4. Keep cross-service API contracts stable and observable during refactors.
5. Improve operator diagnostics in frontend without changing the core dual-service topology.

## Success Criteria

The PRD is considered successful when the outcomes below are met, directly aligned to epic success metrics:

1. No-lookahead invariants remain preserved while execution realism is increased.
2. Execution cost/risk model coverage includes slippage/fees/impact controls as documented in epic acceptance criteria.
3. Flow-first strategies are primary when L2 coverage exists; candlestick dependence is reduced.
4. OOS workflow enforces strict train/validation/test separation and Monte Carlo drawdown gating.
5. API contract and marker schema changes remain backward-compatible (or explicitly versioned/documented).
6. Frontend exposes execution/risk controls and L2 diagnostics with clear marker drill-down behavior.

## Product Scope

### In Scope

1. All stories in EPIC-01 through EPIC-05 as defined in `bmad/backlog/epic-tracks.md`.
2. Changes spanning strategy engine, runner orchestration, optimization/validation pipeline, and frontend diagnostics.
3. Documentation and testing work explicitly listed in epic acceptance criteria.

### Out of Scope

1. Creating a new repository or replacing the two-service architecture.
2. Mandatory LEAN bridge/integration work in this cycle.
3. New feature tracks that are not part of EPIC-01..EPIC-05.

## Non-Goals

1. Creating a new repository or replacing the current two-service architecture.
2. Replacing the runner/strategy split with a monolith.
3. Defining new feature tracks outside EPIC-01..EPIC-05.
4. Committing to mandatory LEAN integration in this PRD (source marks LEAN path as optional).

## Architecture Constraints and System Context

The architecture source defines this runtime flow:

1. Data source (CSV/Parquet, Databento-derived inputs) feeds `backtest-runner`.
2. `backtest-runner` orchestrates session progression and forwards bars to strategy API.
3. `market_regime_detection` processes regime/strategy decisions and risk behavior.
4. Frontend consumes playback/decision outputs for visualization.

Required constraints from source documents:

- Keep `backtest-runner` + `market_regime_detection` as primary architecture.
- Keep LEAN path optional (final backtests / comparison) and not core runtime dependency.
- Maintain cross-service compatibility while implementing epic stories.

## Users and Core Workflows

Primary user/operator workflow from source:

1. Start strategy service (`market_regime_detection`, port `8001`).
2. Start runner API (`backtest-runner`, port `8002`).
3. Start frontend (`5173`) and run playback/testing sessions.
4. Evaluate strategy behavior, exits, diagnostics, and reports.
5. Iterate strategy/risk/config changes by epic/story priorities.

## Scope and Phasing

Scope is defined by epic tracks exactly as written:

### Phase P0 (MVP baseline hardening)

- EPIC-01: Execution Realism & Risk Engine

### Phase P1 (core performance and robustness uplift)

- EPIC-02: Flow-First Signal System
- EPIC-03: Optimization & OOS Discipline

### Phase P2 (safety + operator UX refinement)

- EPIC-04: API Contracts & Observability
- EPIC-05: Frontend Expert Mode

## Functional Requirements

Each requirement below maps directly to epic stories and acceptance statements.

### FR-ER-01: Partial Fill Participation Caps

- The system shall cap entry fills by deterministic participation constraints and bar liquidity.
- Fill behavior shall be recorded through `fill_ratio`.
- Source story: `ER-01`.

### FR-ER-02: Exit Validation Coverage

- The strategy engine shall support time exit and adverse-flow exits with regression test coverage.
- Source story: `ER-02`.

### FR-ER-03: Cross-Service Execution Config Propagation

- Runner `/api/run/start` execution controls shall be passed through to strategy configuration.
- Source story: `ER-03`.

### FR-FF-01: Flow-Only Operation Path

- The system shall support flow-only operation without candlestick pattern gating.
- Source story: `FF-01`.

### FR-FF-02: Microstructure Metric Expansion

- Strategy decision context shall include extended microstructure metrics (including large trader activity and VWAP execution flow).
- Source story: `FF-02`.

### FR-FF-03: Flow Strategy Tuning Matrix

- Optimization workflows shall include flow-strategy parameter grids for listed strategy families.
- Source story: `FF-03`.

### FR-OV-01: 60/20/20 OOS Reporting

- Validator outputs shall include train/validation/test metrics per ticker.
- Source story: `OV-01`.

### FR-OV-02: Monte Carlo Risk Gate

- Monte Carlo workflow shall provide CI-compatible threshold gating behavior for drawdown risk.
- Source story: `OV-02`.

### FR-OV-03: Regime/Time Segmented Ranking

- Walk-forward reporting shall include regime/hour/weekday summaries as specified.
- Source story: `OV-03`.

### FR-AO-01: Contract Documentation

- Contract table coverage shall exist for `/api/run/start` and `/api/session/config` defaults/fields.
- Source story: `AO-01`.

### FR-AO-02: Decision Payload Schema Safety

- Marker/decision payload schemas shall be regression-checked by tests.
- Source story: `AO-02`.

### FR-AO-03: Regime Refresh Telemetry

- Regime refresh telemetry shall include old/new regime and cause metrics.
- Source story: `AO-03`.

### FR-FE-01: Frontend Run Controls

- Frontend run form shall expose execution/risk controls mapping to `/api/run/start`.
- Source story: `FE-01`.

### FR-FE-02: L2 Diagnostics Visibility

- Frontend diagnostics shall expose flow score/aggression/absorption/large trader activity.
- Source story: `FE-02`.

### FR-FE-03: Marker Drill-Down

- Marker detail UI shall support partial exits and adverse-flow exit cost/reason breakdown.
- Source story: `FE-03`.

## Non-Functional Requirements

NFRs are constrained to source success metrics and architecture constraints.

### NFR-1: No-Lookahead Safety

- No-lookahead behavior must remain preserved in all execution realism and optimization workstreams.
- Source linkage: EPIC-01 success metrics.

### NFR-2: Contract Stability

- API and marker contracts must remain backward-compatible or be explicitly versioned/documented.
- Source linkage: EPIC-04 objective/success metrics.

### NFR-3: Observability and Debuggability

- Session diagnostics and telemetry must support replay/debug safety at scale of refactors.
- Source linkage: EPIC-04 success metrics.

### NFR-4: Analytical Robustness

- OOS and Monte Carlo outputs must preserve strict tuning-vs-evaluation separation and explicit risk signaling.
- Source linkage: EPIC-03 objective/success metrics.

### NFR-5: Operational UX Clarity

- Frontend must keep playback clear while adding expert diagnostics/controls.
- Source linkage: EPIC-05 objective/success metrics.

## Epic and Story Traceability

| Epic | Story | Requirement | Key Files (from source) |
| --- | --- | --- | --- |
| EPIC-01 | ER-01 | FR-ER-01 | `../market_regime_detection/src/day_trading_manager.py`, `../market_regime_detection/api_server.py` |
| EPIC-01 | ER-02 | FR-ER-02 | `../market_regime_detection/src/day_trading_manager.py`, `tests/test_execution_realism.py` |
| EPIC-01 | ER-03 | FR-ER-03 | `api_server.py`, `../market_regime_detection/api_server.py` |
| EPIC-02 | FF-01 | FR-FF-01 | `../market_regime_detection/src/multi_layer_decision.py`, `../market_regime_detection/src/day_trading_manager.py` |
| EPIC-02 | FF-02 | FR-FF-02 | `../market_regime_detection/src/day_trading_manager.py` |
| EPIC-02 | FF-03 | FR-FF-03 | `wfo_optimizer.py`, `oos_validator.py` |
| EPIC-03 | OV-01 | FR-OV-01 | `oos_validator.py` |
| EPIC-03 | OV-02 | FR-OV-02 | `monte_carlo.py` |
| EPIC-03 | OV-03 | FR-OV-03 | `performance_tracker.py`, `walk_forward_runner.py` |
| EPIC-04 | AO-01 | FR-AO-01 | `README.md`, `bmad/context/component-map.json` |
| EPIC-04 | AO-02 | FR-AO-02 | `session_runner.py`, `tests/*` |
| EPIC-04 | AO-03 | FR-AO-03 | `../market_regime_detection/src/day_trading_manager.py` |
| EPIC-05 | FE-01 | FR-FE-01 | `frontend/src/components/RunConfig.jsx` |
| EPIC-05 | FE-02 | FR-FE-02 | `frontend/src/components/DecisionPanel.jsx`, `frontend/src/components/SessionSummary.jsx` |
| EPIC-05 | FE-03 | FR-FE-03 | `frontend/src/components/DecisionPanel.jsx` |

## Delivery Readiness Criteria

The implementation phase should proceed only when:

1. PRD scope remains constrained to the five existing epics.
2. Story-level acceptance criteria remain unchanged from `epic-tracks.md`.
3. Architecture assumptions remain on the two-service baseline (`backtest-runner` + `market_regime_detection`).

## Conflicts & Questions

1. **Backtest-runner change scope conflict**
   - `plans/final-architecture-plan.md` states runner requires no changes.
   - `bmad/backlog/epic-tracks.md` includes direct runner/frontend changes (`ER-03`, `AO-02`, `FE-*`).
   - **Question:** Should “no runner changes needed” be treated as historical guidance, with epic-track scope taking precedence?

2. **LEAN integration ambiguity**
   - Architecture analysis lists LEAN integration/bridge paths as open options.
   - Epic tracks define no LEAN integration stories.
   - **Question:** Is LEAN explicitly out-of-scope for the current PRD implementation cycle?

3. **Sniper strategy scope gap**
   - Final architecture mentions potential `sniper/` strategy port and `experimental/` strategy expansion.
   - Epic tracks do not include a dedicated Sniper migration story.
   - **Question:** Should Sniper migration be deferred to a separate epic after EPIC-01..EPIC-05?

4. **Source-of-truth for strategy set**
   - Architecture analysis highlights duplicate logic risk between LEAN and `market_regime_detection`.
   - Epic tracks assume the dual-service path but do not define consolidation criteria.
   - **Question:** What is the explicit source-of-truth policy for strategy logic during migration/experimentation?
