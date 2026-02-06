# BMAD Backlog

This folder contains the execution backlog for large-LLM collaboration.

## Files

- `epic-tracks.md`: human-readable plan (epics + stories + acceptance criteria).
- `story-board.json`: machine-friendly board for deterministic story selection.

## Working Loop

1. Choose the next story from `story-board.json` (or run `/bmad-next`).
2. Load:
   - `bmad/context/generated/00-index.md`
   - the domain pack for that story
   - the story entry from backlog
3. Create implementation plan with `/bmad-plan`.
4. Implement with `/bmad-implement`.
5. Review with `/bmad-review`.
6. Update story status in `story-board.json`.

## Status Values

- `todo`
- `in_progress`
- `blocked`
- `done`
