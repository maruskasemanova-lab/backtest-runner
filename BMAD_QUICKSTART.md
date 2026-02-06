# BMAD Quickstart For This Project

This project uses a lightweight BMAD adaptation for brownfield work.

## 1) Optional: Install official BMAD assets

From repo root:

```bash
npx bmad-method install
```

If you use Claude Code, select Claude support during install.

## 2) Use the project BMAD map

Generate context packs:

```bash
python3 scripts/generate_context_pack.py
```

Read:

- `bmad/context/generated/00-index.md`
- one domain pack matching your task

## 3) Run Claude command workflow

- `/bmad-system-map` to route to correct domain
- `/bmad-next` to pick next prioritized backlog story
- `/bmad-plan` to build task plan/story
- `/bmad-implement` to execute and test
- `/bmad-review` for regression/risk pass

## 4) Keep context in sync

After structural/API ownership changes:

1. Update `bmad/context/component-map.json`
2. Re-run `python3 scripts/generate_context_pack.py`

## 5) Backlog source of truth

- Human view: `bmad/backlog/epic-tracks.md`
- Machine view: `bmad/backlog/story-board.json`
- CLI helper: `python3 scripts/next_bmad_story.py`
