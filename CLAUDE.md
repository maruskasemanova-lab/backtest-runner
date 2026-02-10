# CLAUDE.md

Claude workflow contract for this repository.

## BMAD-First Command Mode (Claude)

Default to BMAD command flow for implementation work unless user explicitly asks to skip workflow steps:

1. `/bmad-help`
2. `/bmad-system-map`
3. `/bmad-plan`
4. `/bmad-implement`
5. `/bmad-review`

For full official BMAD-METHOD workflows, use `/bmad-bmm-*` and `/bmad-agent-bmm-*`.
Command IDs in `.claude/commands` are normalized to `bmad-*` via `scripts/sync_claude_bmad_names.sh` (also run by `scripts/bootstrap_bmad.sh`).

## Mandatory Load Order

1. `docs/llm/README.md`
2. `docs/llm/functionality-map.md`
3. `docs/llm/api-contracts.md`
4. `docs/llm/invariants-and-validation.md`
5. `bmad/context/generated/00-index.md`
6. Primary domain pack in `bmad/context/generated/<domain>.md`
7. `bmad/context/generated/00-machine-index.json`
8. `bmad/context/generated/00-endpoint-map.md`

## Mandatory Routing Step

Before implementation, select exactly one primary domain and list any secondary domains only when interfaces are impacted.

## Output Contract

For planning and implementation responses, use this structure:

```yaml
primary_domain: <domain-id>
secondary_domains:
  - <domain-id>
problem: <one-paragraph>
scope:
  in:
    - <item>
  out:
    - <item>
steps:
  - <ordered actionable step>
contracts:
  - endpoint: <path>
    change: <none|backward-compatible|breaking>
tests:
  - command: <command>
    expectation: <result>
risks:
  - severity: <P0|P1|P2|P3>
    detail: <risk>
```

## Guardrails

- No look-ahead behavior anywhere in backtests and strategy decisions.
- Preserve event semantics for markers (`signal queued`, `position opened`, `position closed`).
- Explicitly list runner-strategy-frontend contract impacts before cross-domain edits.
- Keep changes minimal and test-backed.

## Validation Before Final Answer

- `python3 scripts/generate_context_pack.py`
- `python3 scripts/validate_llm_context.py`
- impacted `pytest` suites
