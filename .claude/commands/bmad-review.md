---
description: Perform risk-first BMAD review focused on regressions, invariants, contract breaks, and missing tests.
argument-hint: "[scope]"
allowed-tools: Read, Grep, Glob, Bash(pytest *), Bash(rg *), mcp__axon__*
model: sonnet
---

Perform a risk-first code review for this task.

Scope:
$ARGUMENTS

Review priorities (in order):
1. Behavioral regressions
2. Look-ahead bias leaks
3. Execution/risk model inconsistencies
4. API contract breaks (runner <-> strategy API <-> frontend)
5. Missing tests

Required context files:
1. `bmad/context/generated/00-index.md`
2. `bmad/context/generated/00-machine-index.json`
3. Relevant domain packs in `bmad/context/generated/<domain>.md`

Output format (schema-first):

```yaml
primary_domain: <domain-id>
secondary_domains:
  - <domain-id>
findings:
  - severity: <P0|P1|P2|P3>
    file: <path>
    issue: <description>
open_questions:
  - <question>
suggested_fixes:
  - <fix>
```
