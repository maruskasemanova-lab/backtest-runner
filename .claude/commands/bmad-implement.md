Implement the task with strict BMAD domain discipline.

Task:
$ARGUMENTS

Execution protocol:
1. Read `bmad/context/generated/00-index.md` and one domain pack.
2. Read `bmad/context/generated/00-machine-index.json`.
3. Implement minimal required edits.
4. Run compile/tests for impacted files.
5. Provide schema-first output:

```yaml
primary_domain: <domain-id>
primary_pack: bmad/context/generated/<domain>.md
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

Do not skip verification steps.
