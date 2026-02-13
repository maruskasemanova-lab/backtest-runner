# Claude Prompt - Architecture Refactor Handoff

You are implementing a cleanup/refactor of a unified but currently hard-to-reason architecture around:
- adaptive strategy selection
- momentum diversification (including sleeves)
- L2/CVD-derived gating
- runner <-> strategy integration

## Repo Context
- Runner repo: `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner`
- Strategy repo: `/Users/hotovo/.gemini/antigravity/scratch/market_regime_detection`

Read these first:
1. `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/analysis/claude_handoff_architecture_2026-02-13/CURRENT_STATE_MAP.md`
2. `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/analysis/claude_handoff_architecture_2026-02-13/ARCHITECTURE_GAPS.md`
3. `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/analysis/claude_handoff_architecture_2026-02-13/FILE_INDEX.md`
4. `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/analysis/claude_handoff_architecture_2026-02-13/MU_CONFIG_SNAPSHOT.json`

## Objective
Restructure current implementation so behavior is deterministic and maintainable, while keeping backward compatibility and trading invariants.

## Hard Constraints (must keep)
- No look-ahead bias anywhere.
- No same-bar execution (`signal_bar_index < entry_bar_index`).
- `comparable_mode=true` remains cold-start and ignores warm checkpoints.
- L2 sessionized metrics continue resetting per market day when enabled.
- API contracts stay backward compatible unless intentionally versioned.

## What To Deliver
1. A short architecture decision note (what boundaries you introduced and why).
2. Code changes implementing those boundaries.
3. Updated docs for any contract/behavior deltas.
4. Test output for impacted domains.

## Priority Work Order
1. **Correctness first:** verify and fix L2 field handoff mismatch (`l2_book_pressure_delta` vs `l2_book_pressure_change`) without breaking existing payloads.
2. **Single source of truth for momentum config schema:** eliminate normalization drift across runner/strategy/frontend by introducing a canonical contract path (or explicit versioned adapters).
3. **Centralize effective runtime config resolution:** make source precedence explicit and testable (request vs profile vs AOS).
4. **Decouple strategy-engine policy modules:** split selection/routing/gating/fail-fast logic into smaller composable units with focused tests.

## Acceptance Criteria
- Existing behavior for untouched fields remains stable.
- New/updated tests cover:
  - momentum config precedence,
  - sleeve selection/gating,
  - L2 confirmation,
  - fail-fast exit,
  - runner->strategy payload compatibility.
- Deterministic outputs for repeated runs with same config/date range.

## Validation Commands
- `python3 scripts/generate_context_pack.py`
- `python3 scripts/validate_llm_context.py`
- `python3 scripts/validate_llm_context.py --strict`
- `pytest tests/test_no_lookahead.py tests/test_api_server_l2_sessionized.py tests/test_session_runner_markers.py tests/test_start_run_strategy_overrides_mode.py tests/test_adaptive_tuner_api.py`
- `pytest /Users/hotovo/.gemini/antigravity/scratch/market_regime_detection/tests/test_day_trading_manager_strategy_selection_mode.py /Users/hotovo/.gemini/antigravity/scratch/market_regime_detection/tests/test_day_trading_manager_positioning_defaults.py`

## Reporting Format
At the end, report:
- files changed
- contract deltas
- tests executed + outcomes
- residual risks
