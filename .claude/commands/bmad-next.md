Select and prepare the next backlog story.

Context:
1. Read `bmad/backlog/story-board.json`.
2. Pick the highest-priority `todo` story (`P0` > `P1` > `P2`).
3. Read `bmad/context/generated/00-index.md` and the selected domain pack.

Output:
- `selected_story` (id + title)
- `why_now` (short reason)
- `files_to_read_first` (max 8)
- `implementation_plan` (5-10 concrete steps)
- `tests_to_run`
- `definition_of_done`

Task override (optional):
$ARGUMENTS

If `$ARGUMENTS` includes a story ID, use that story instead of auto-selection.
