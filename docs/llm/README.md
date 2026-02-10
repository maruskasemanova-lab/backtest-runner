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

## Why Two Layers Exist

- Manual docs (`docs/llm/*`) capture behavior, intent, and guardrails.
- Generated docs (`bmad/context/generated/*`) capture file inventory, symbols, and endpoints from current code.

Use both in every non-trivial task.

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
