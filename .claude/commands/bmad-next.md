Select and prepare the next backlog story.

Context:
1. Read `bmad/backlog/story-board.json`.
2. Pick the highest-priority `todo` story (`P0` > `P1` > `P2`).
3. Read `bmad/context/generated/00-index.md`.
4. Read `bmad/context/generated/00-machine-index.json`.
5. Read the selected domain pack from `bmad/context/generated/<domain>.md`.

Output (schema-first):

```yaml
selected_story:
  id: <story-id>
  title: <story-title>
primary_domain: <domain-id>
primary_pack: bmad/context/generated/<domain>.md
why_now: <short-reason>
files_to_read_first:
  - <path>
implementation_plan:
  - <step>
tests_to_run:
  - <command-or-test-file>
definition_of_done:
  - <criterion>
```

Task override (optional):
$ARGUMENTS

If `$ARGUMENTS` includes a story ID, use that story instead of auto-selection.
