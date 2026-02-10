---
stepsCompleted: []
inputDocuments:
  - _bmad-output/planning-artifacts/PRD.md
  - _bmad-output/planning-artifacts/architecture-existing.md
  - _bmad-output/planning-artifacts/stories-existing.md
  - _bmad-output/planning-artifacts/ux-minimal-fe-stories.md
---

# backtest-runner - Epic Breakdown

## Overview

This document provides the epic and story breakdown for backtest-runner, aligned to existing architecture and epic tracks only.

## Requirements Inventory

### Functional Requirements

- FR-ER-01: Partial Fill Participation Caps
- FR-ER-02: Exit Validation Coverage
- FR-ER-03: Cross-Service Execution Config Propagation
- FR-FF-01: Flow-Only Operation Path
- FR-FF-02: Microstructure Metric Expansion
- FR-FF-03: Flow Strategy Tuning Matrix
- FR-OV-01: 60/20/20 OOS Reporting
- FR-OV-02: Monte Carlo Risk Gate
- FR-OV-03: Regime/Time Segmented Ranking
- FR-AO-01: Contract Documentation
- FR-AO-02: Decision Payload Schema Safety
- FR-AO-03: Regime Refresh Telemetry
- FR-FE-01: Frontend Run Controls
- FR-FE-02: L2 Diagnostics Visibility
- FR-FE-03: Marker Drill-Down

### NonFunctional Requirements

- NFR-1: No-Lookahead Safety
- NFR-2: Contract Stability
- NFR-3: Observability and Debuggability
- NFR-4: Analytical Robustness
- NFR-5: Operational UX Clarity

### Additional Requirements

- Keep two-service architecture (`backtest-runner` + `market_regime_detection`).
- Keep scope constrained to EPIC-01..EPIC-05.
- Keep LEAN integration optional and outside required implementation scope.

### FR Coverage Map

- FR-ER-01 -> Epic 1 / Story 1.1
- FR-ER-02 -> Epic 1 / Story 1.2
- FR-ER-03 -> Epic 1 / Story 1.3
- FR-FF-01 -> Epic 2 / Story 2.1
- FR-FF-02 -> Epic 2 / Story 2.2
- FR-FF-03 -> Epic 2 / Story 2.3
- FR-OV-01 -> Epic 3 / Story 3.1
- FR-OV-02 -> Epic 3 / Story 3.2
- FR-OV-03 -> Epic 3 / Story 3.3
- FR-AO-01 -> Epic 4 / Story 4.1
- FR-AO-02 -> Epic 4 / Story 4.2
- FR-AO-03 -> Epic 4 / Story 4.3
- FR-FE-01 -> Epic 5 / Story 5.1
- FR-FE-02 -> Epic 5 / Story 5.2
- FR-FE-03 -> Epic 5 / Story 5.3

## Epic List

1. Epic 1: Execution Realism and Risk Engine
2. Epic 2: Flow-First Signal System
3. Epic 3: Optimization and OOS Discipline
4. Epic 4: API Contracts and Observability
5. Epic 5: Frontend Expert Mode

## Epic 1: Execution Realism and Risk Engine

Strengthen execution realism and risk controls so backtest outcomes are less overfit and closer to deployable behavior.

### Story 1.1: Partial Fill Participation Caps

As a strategy researcher,  
I want entry fills capped by deterministic participation limits,  
So that fill assumptions stay realistic under liquidity constraints.

**Acceptance Criteria:**

**Given** an entry signal is generated on a bar with limited liquidity  
**When** the order is processed by execution logic  
**Then** filled size is capped by configured participation constraints and bar liquidity  
**And** `fill_ratio` is recorded for the resulting fill event.

### Story 1.2: Time Exit and Adverse Flow Exit Validation

As a strategy researcher,  
I want time exit and adverse-flow exits validated with tests,  
So that exit behavior remains reliable under regression.

**Acceptance Criteria:**

**Given** a running position with configured time and adverse-flow exits  
**When** exit conditions are reached in simulation  
**Then** exit reason is assigned correctly for each condition  
**And** regression tests covering both exit paths pass.

### Story 1.3: Cross-Service Execution Config Contract Hardening

As a platform engineer,  
I want execution configuration passed consistently from runner to strategy service,  
So that run behavior matches configured controls end-to-end.

**Acceptance Criteria:**

**Given** execution and risk fields are supplied to runner start  
**When** session configuration is sent to strategy service  
**Then** effective execution knobs are forwarded without omission  
**And** values are reflected consistently in downstream session behavior.

## Epic 2: Flow-First Signal System

Shift decisioning toward flow and microstructure context so L2-aware strategies are primary where coverage exists.

### Story 2.1: Remove Pattern Gating for Flow-Only Profile

As a strategy researcher,  
I want a flow-only operation profile without candlestick pattern gating,  
So that flow strategies can run independently when appropriate.

**Acceptance Criteria:**

**Given** flow-only profile is enabled  
**When** strategy decisions are evaluated  
**Then** candlestick pattern gating does not block flow-driven decisions  
**And** strategy-only mode remains operational.

### Story 2.2: Extend Microstructure Metrics

As a strategy researcher,  
I want additional microstructure metrics in decision context,  
So that strategy confidence can use richer flow evidence.

**Acceptance Criteria:**

**Given** session bars include available L2 context  
**When** regime and strategy evaluation runs  
**Then** large trader and VWAP execution flow metrics are computed and exposed  
**And** metrics are visible in regime payload or layer scoring output.

### Story 2.3: Flow Strategy Tuning Matrix

As a quant developer,  
I want optimization grids to include flow strategy families,  
So that tuning compares relevant flow configurations systematically.

**Acceptance Criteria:**

**Given** optimization/validation tooling is configured for parameter search  
**When** tuning matrices are generated  
**Then** parameter grids include `momentum_flow`, `absorption_reversal`, and `exhaustion_fade` families  
**And** generated outputs remain compatible with validator workflows.

## Epic 3: Optimization and OOS Discipline

Enforce chronological validation discipline and robustness reporting across tuning and evaluation workflows.

### Story 3.1: 60/20/20 OOS Validator Reporting

As a quant developer,  
I want validator output split into train/validation/test reporting,  
So that I can distinguish tuning performance from hold-out performance.

**Acceptance Criteria:**

**Given** a validation run is executed with chronological split logic  
**When** report output is generated  
**Then** train, validation, and test metrics are present per ticker  
**And** split boundaries are preserved without leakage.

### Story 3.2: Monte Carlo CI Risk Gate

As a risk owner,  
I want Monte Carlo drawdown thresholds enforced in CI-style execution,  
So that high-risk strategy variants fail fast.

**Acceptance Criteria:**

**Given** trade sequence inputs are available for Monte Carlo analysis  
**When** drawdown distribution is evaluated against configured threshold  
**Then** the process emits explicit risk-gate result  
**And** threshold breach is signaled as failure state.

### Story 3.3: Walk-Forward Regime/Hour/Weekday Ranking

As a strategy researcher,  
I want walk-forward reports segmented by regime, hour, and weekday,  
So that I can identify context-specific strengths and weaknesses.

**Acceptance Criteria:**

**Given** walk-forward simulation results are available  
**When** summary report is produced  
**Then** `hourly_summary` and `weekday_summary` are included  
**And** rankings remain aligned with regime-level breakdowns.

## Epic 4: API Contracts and Observability

Harden cross-service contracts and diagnostics to keep refactors safe and debuggable.

### Story 4.1: Contract Table for Start and Session Config APIs

As a platform engineer,  
I want field-level contract documentation for runner and session config APIs,  
So that integration expectations are explicit and stable.

**Acceptance Criteria:**

**Given** current API behavior and defaults  
**When** contract documentation is updated  
**Then** `/api/run/start` and `/api/session/config` field tables are documented with defaults  
**And** documentation aligns with current behavior.

### Story 4.2: Decision Payload Schema Tests

As a platform engineer,  
I want schema-level tests for decision and marker payloads,  
So that UI and downstream tools are protected from contract regressions.

**Acceptance Criteria:**

**Given** session runner emits marker and decision payloads  
**When** schema or snapshot tests are executed  
**Then** payload structure is validated against expected shape  
**And** incompatible schema drift is detected by tests.

### Story 4.3: Regime Refresh Telemetry Expansion

As a strategy operator,  
I want telemetry to include regime transitions and causes,  
So that decision behavior can be audited and debugged.

**Acceptance Criteria:**

**Given** regime refresh logic is triggered during session processing  
**When** telemetry event is emitted  
**Then** previous regime, new regime, and cause metrics are included  
**And** telemetry remains available for diagnostics workflows.

## Epic 5: Frontend Expert Mode

Improve diagnostics usability in frontend while preserving playback clarity and operator control.

### Story 5.1: Execution and Risk Controls in Run Form

As a trading analyst,  
I want execution and risk controls available in the run form,  
So that I can configure run realism directly from the UI.

**Acceptance Criteria:**

**Given** the run configuration form is displayed  
**When** user edits execution or risk fields  
**Then** controls map 1:1 to `/api/run/start` execution configuration  
**And** submitted payload reflects chosen values.

### Story 5.2: L2 Diagnostics Card

As a strategy researcher,  
I want a focused diagnostics card for L2 flow context,  
So that I can interpret signal quality without reading raw logs.

**Acceptance Criteria:**

**Given** session or marker context is selected in frontend  
**When** diagnostics panel is rendered  
**Then** flow score, aggression, absorption, and large trader activity are shown  
**And** values are presented in a consistent and readable format.

### Story 5.3: Marker Drill-Down for Exit Reasons and Costs

As a trading analyst,  
I want marker drill-down for partial and adverse-flow exits,  
So that I can verify exit behavior and cost attribution.

**Acceptance Criteria:**

**Given** a marker detail view is opened for an exit event  
**When** the event is partial or adverse-flow driven  
**Then** the detail view includes exit reason and relevant cost components  
**And** the user can review details without losing playback context.

