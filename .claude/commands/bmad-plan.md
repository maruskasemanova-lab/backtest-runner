Create a focused implementation plan using BMAD domain context.

Task:
$ARGUMENTS

Required steps:
1. Read `bmad/context/generated/00-index.md`.
2. Read `bmad/context/generated/00-machine-index.json`.
3. Read the selected domain pack from `bmad/context/generated/<domain>.md`.
4. Produce schema-first plan:

```yaml
primary_domain: <domain-id>
primary_pack: bmad/context/generated/<domain>.md
problem: <problem-statement>
assumptions:
  - <assumption>
implementation_steps:
  - <step>
validation_steps:
  - <test-or-command>
rollback_strategy:
  - <rollback-step>
```

5. Keep the plan tied to concrete file paths.

Constraint:
- Avoid cross-domain edits unless contract changes are explicitly stated.
