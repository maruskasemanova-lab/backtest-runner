# LLM Context Pack

This directory is the curated manual context for LLM-assisted development in the dual-service stack.

## Read Order

1. `docs/llm/functionality-map.md`
2. `docs/llm/api-contracts.md`
3. `docs/llm/invariants-and-validation.md`
4. `bmad/context/generated/00-index.md`
5. `bmad/context/generated/<domain>.md`
6. `bmad/context/generated/00-machine-index.json`
7. `bmad/context/generated/00-endpoint-map.md`
8. `docs/llm/adaptive-tuning-c4x3.md` (for C4-like parallel tuning requests)

## Why Two Layers Exist

- Manual docs (`docs/llm/*`) capture behavior, intent, and guardrails.
- Generated docs (`bmad/context/generated/*`) capture file inventory, symbols, and endpoints from current code.

Use both in every non-trivial task.

## Axon (MCP + CLI) Workflow

Axon complements BMAD context packs with structural graph queries (symbols, callers/callees, impact, dead code).

Recommended sequence for non-trivial changes:

1. `./scripts/axon-flow.sh index` (or use MCP auto-start with `axon serve --watch`)
2. `axon_query` / `axon_context` / `axon_impact` (via MCP) or `./scripts/axon-flow.sh q|ctx|impact`
3. Read BMAD generated domain pack + machine index
4. Implement minimal change
5. Re-run targeted tests + `./scripts/axon-flow.sh refresh-context` when docs/context changed

## Update Workflow

1. Update code and/or `bmad/context/component-map.json`.
2. Regenerate packs:

```bash
python3 scripts/generate_context_pack.py
```

3. Validate consistency:

```bash
python3 scripts/validate_llm_context.py
```

For stricter gating:

```bash
python3 scripts/validate_llm_context.py --strict
```

## Domain Routing

Primary domain must be one of:

- `orchestration`
- `strategy-engine`
- `data-l2`
- `optimization-validation`
- `frontend`

If you touch another domain, document interface and behavior impact explicitly.
