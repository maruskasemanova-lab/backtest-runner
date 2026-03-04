---
description: Perform Axon-first investigation, then implement minimal changes with domain and contract safety.
argument-hint: "[task]"
allowed-tools: Read, Edit, Write, Grep, Glob, Bash(rg *), Bash(pytest *), mcp__axon__*
model: sonnet
---

Run an Axon-first investigation before implementation.

Task:
$ARGUMENTS

Execution protocol:
1. Route to one primary domain using `bmad/context/component-map.json`.
2. Read `bmad/context/generated/00-index.md`, the domain pack, and `bmad/context/generated/00-machine-index.json`.
3. Use Axon first (MCP tools preferred):
   - `axon_query` to find candidate symbols/files
   - `axon_context` on top symbols
   - `axon_impact` for any symbol likely to be changed
   - `axon_detect_changes` if a git diff is provided
4. Only then read code and implement minimal viable edits.
5. Run targeted tests for impacted domain.
6. Return a concise schema-first summary:

```yaml
primary_domain: <domain-id>
axon_trace:
  - query: <text>
    key_symbols: [<symbol>]
  - context: <symbol>
    notes: <one-line>
  - impact: <symbol>
    risk: <one-line>
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

Do not skip Axon steps unless Axon is unavailable; if unavailable, state the reason.
