# AGENTS.md

Deterministic operating guide for coding agents (Codex/GPT/Claude) in this repository.

## Scope

- Primary repo: `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner`
- Sibling strategy repo: `/Users/hotovo/.gemini/antigravity/scratch/market_regime_detection`

## Source Of Truth Order

1. `docs/llm/README.md`
2. `docs/llm/functionality-map.md`
3. `docs/llm/api-contracts.md`
4. `docs/llm/invariants-and-validation.md`
5. `bmad/context/generated/00-index.md`
6. `bmad/context/generated/<domain>.md`
7. `bmad/context/generated/00-machine-index.json`
8. `bmad/context/generated/00-endpoint-map.md`
9. `docs/llm/adaptive-tuning-c4x3.md` (for C4-like/parallel tuning requests)

If documentation conflicts with code, code is authoritative. Update docs in the same change.

## Domain Discipline

Select one primary domain from `bmad/context/component-map.json`:

- `orchestration`
- `strategy-engine`
- `data-l2`
- `optimization-validation`
- `frontend`

Avoid cross-domain edits unless contract changes are explicit and listed.

## Do-Not-Break Invariants

- No look-ahead bias in bar processing, L2 features, and decision logic.
- No same-bar signal execution (`signal_bar_index < entry_bar_index`).
- Runner and strategy API contracts remain backward compatible unless versioned intentionally.
- `comparable_mode` forces cold start and ignores warm-start checkpoint loading.
- L2 sessionized metrics reset per market day when enabled.

## Required Change Protocol

1. Route task to primary domain.
2. Load generated domain pack and machine index.
3. Implement minimal viable change.
4. Run targeted tests for impacted domains.
5. Report:
- files changed
- contract deltas
- tests executed + outcomes
- residual risks

## Adaptive Tuning Shortcut

When request asks for "like c4", "new adaptive strategy", or "3 independent tunings":
- use `docs/llm/adaptive-tuning-c4x3.md`
- keep parallel job count at most 3
- prefer distinct `strategy_api_url` ports for each parallel job

## Required Verification Commands

- `python3 scripts/generate_context_pack.py`
- `python3 scripts/validate_llm_context.py`
- Domain-specific `pytest` commands from `bmad/context/component-map.json` test targets.

Use `python3 scripts/validate_llm_context.py --strict` for stricter local/CI gating.
