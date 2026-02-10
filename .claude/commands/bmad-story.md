Draft a story for this task using the project template.

Task:
$ARGUMENTS

Instructions:
1. Use `bmad/templates/story-template.md`.
2. Read `bmad/context/generated/00-machine-index.json`.
3. Read one primary domain pack from `bmad/context/generated/<domain>.md`.
4. Fill all sections with concrete paths, interfaces, and acceptance criteria.
5. Ensure the story references one primary domain from `component-map.json`.
6. Include explicit no-lookahead/risk checks when touching execution logic.

Output schema block first, then completed story markdown:

```yaml
primary_domain: <domain-id>
primary_pack: bmad/context/generated/<domain>.md
story_target_file: <path>
contracts_touched:
  - <contract-or-endpoint>
tests_to_run:
  - <test-or-command>
```
