---
description: Audit dead code with Axon-first triage and produce a safe, reversible cleanup plan.
argument-hint: "[scope]"
allowed-tools: Read, Grep, Glob, Bash(rg *), Bash(pytest *), mcp__axon__*
model: sonnet
---

Run a BMAD + Axon dead-code audit and prepare a safe cleanup plan (and cleanup patch only when requested).

Task:
$ARGUMENTS

Execution protocol:
1. Route to one primary domain using `bmad/context/component-map.json`.
2. Read `bmad/context/generated/00-index.md`, the domain pack, and `bmad/context/generated/00-machine-index.json`.
3. Use Axon first (MCP tools preferred):
   - `axon_dead_code` to generate the candidate list
   - `axon_query` / `axon_context` on top candidates
   - `axon_impact` before deleting or modifying any symbol
4. Classify candidates into:
   - `safe_now` (verified unreferenced helpers/internal functions)
   - `framework_false_positive` (FastAPI routes, React handlers/hooks, websocket callbacks, decorators, exports)
   - `script_entrypoint_false_positive` (`if __name__ == "__main__"` / CLI scripts)
   - `needs_manual_verification` (public APIs, Pydantic models, dataclasses, dynamic/reflection usage)
5. For every `safe_now` candidate, verify with repository search before edits:
   - `rg` exact symbol search (outside the definition site)
   - check imports/exports
   - run `axon_impact`
6. Implement only a small safe batch unless user explicitly asks for a broad cleanup.
7. Run targeted tests for impacted domain. If no code edits were made, state audit-only.
8. If code/docs contracts changed, regenerate and validate LLM context packs.
9. Return schema-first output:

```yaml
primary_domain: <domain-id>
audit_scope: <paths-or-domain>
axon_dead_code:
  total_candidates: <n>
  triage:
    safe_now: <n>
    framework_false_positive: <n>
    script_entrypoint_false_positive: <n>
    needs_manual_verification: <n>
safe_cleanup_batch:
  - symbol: <name>
    file: <path>
    verification:
      rg_refs: <summary>
      impact: <summary>
    action: <delete|defer>
changed_files:
  - <path>
test_results:
  - command: <command>
    outcome: <pass-fail-summary>
contract_changes:
  - <none-or-change>
residual_risks:
  - <risk>
```

Safety rules:
- Do not delete route handlers/endpoints/components/classes only because Axon marks them dead.
- Prefer deprecate/comment/feature-flag over hard delete when API compatibility is uncertain.
- Keep batches small and reversible.
