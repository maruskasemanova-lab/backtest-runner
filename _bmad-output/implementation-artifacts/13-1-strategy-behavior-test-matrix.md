# Story 13.1: Strategy Behavior Test Matrix

Status: done

## Story

As a strategy operator,  
I want deterministic behavior tests for strategy thresholds and guards,  
so that strategy parameter semantics stay stable across refactors and tuning runs.

## Acceptance Criteria

1. `AbsorptionReversal` tests assert trigger behavior and gating for `min_absorption_rate`.
2. `MomentumFlow` tests assert directional trigger behavior and aggression/position limits.
3. `ExhaustionFade` tests assert trigger behavior and gating for absorption/sweep/confidence.
4. Strategy module wiring (`strategy_factory`) is test-covered for expected flow strategy defaults.

## Tasks / Subtasks

- [x] Add behavior tests for `AbsorptionReversalStrategy` long/short triggers.
- [x] Add threshold guard tests for `min_absorption_rate` in `AbsorptionReversalStrategy`.
- [x] Add behavior tests for `MomentumFlowStrategy` long/short triggers.
- [x] Add guard tests for aggression threshold, open-position cap, and L2 coverage in `MomentumFlowStrategy`.
- [x] Add behavior tests for `ExhaustionFadeStrategy` long/short triggers.
- [x] Add guard tests for absorption threshold, sweep cap, and confidence floor in `ExhaustionFadeStrategy`.
- [x] Add `strategy_factory` registry tests for flow-strategy presence/defaults and fresh instance creation.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Completion Notes List

- Implemented a dedicated strategy behavior suite focused on threshold semantics and safety guards.
- Added explicit tests for `min_absorption_rate` behavior in both absorption-based strategies.
- Added module-level registry tests to catch accidental strategy wiring regressions.

### File List

- `/Users/hotovo/.gemini/antigravity/scratch/market_regime_detection/tests/test_flow_strategy_behavior.py`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/_bmad-output/implementation-artifacts/13-1-strategy-behavior-test-matrix.md`
