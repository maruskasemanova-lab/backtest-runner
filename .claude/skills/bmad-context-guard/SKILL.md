---
name: bmad-context-guard
description: Enforce BMAD domain routing, invariant checks, Axon-first investigation, and required validation before finishing a task.
user-invocable: false
---

# BMAD Context Guard

Use this guardrail workflow before implementation and before final response.

## Inputs

- User task (explicit scope + constraints)
- `AGENTS.md`
- `CLAUDE.md`
- `docs/llm/README.md`
- `bmad/context/component-map.json`

## Execution Protocol

1. Choose exactly one primary domain from `bmad/context/component-map.json`.
2. Read context in this order:
   - `docs/llm/functionality-map.md`
   - `docs/llm/api-contracts.md`
   - `docs/llm/invariants-and-validation.md`
   - `bmad/context/generated/00-index.md`
   - `bmad/context/generated/<primary-domain>.md`
   - `bmad/context/generated/00-machine-index.json`
3. Run Axon-first discovery:
   - `axon_query` for symbol candidates
   - `axon_context` for top symbols
   - `axon_impact` before changing symbols
   - fallback to `rg` only for exact-text checks or when Axon is unavailable
4. Implement the smallest viable patch that solves the request.
5. Run required verification commands:
   - `python3 scripts/generate_context_pack.py`
   - `python3 scripts/validate_llm_context.py`
   - domain-targeted `pytest` from `bmad/context/component-map.json`
6. Report explicitly:
   - changed files
   - contract deltas (or none)
   - tests run + outcomes
   - residual risks

## Hard Invariants

- No look-ahead bias.
- No same-bar signal execution.
- Keep runner/strategy API contracts backward compatible unless intentionally versioned.
- `comparable_mode` must force cold start behavior.
- L2 sessionized metrics reset per market day when enabled.
