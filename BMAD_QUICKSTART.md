# BMAD Quickstart For This Project

This repository uses a hybrid setup:

- Full BMAD-METHOD in `_bmad/` (official workflows, agents, `/bmad-help`)
- Project-specific BMAD context in `bmad/` (domain maps, generated packs, custom loop commands)

## 1) Install or refresh full BMAD-METHOD

From repo root:

```bash
./scripts/bootstrap_bmad.sh
```

This installs/upgrades BMAD-METHOD for Claude Code and keeps project custom commands.

## 2) Use official BMAD guidance when you want standard flow

Important: slash commands (`/bmad-help`, `/bmad-bmm-*`) are entered inside the IDE chat input (Claude/Codex), not directly in `zsh`.

- `/bmad-help` for context-aware next-step guidance
- `/bmad-agent-bmm-analyst`, `/bmad-agent-bmm-dev`, etc. for role-based execution
- `/bmad-bmm-*` commands for direct workflow execution

## 3) Use project custom loop when you want lightweight brownfield execution

- `/bmad-system-map` to route to the right project domain
- `/bmad-next` to pick next prioritized backlog story
- `/bmad-plan` to build a focused plan/story
- `/bmad-implement` to execute and test
- `/bmad-review` for regression/risk pass

## 3.1) Run BMAD through Codex

Start Codex with project-local prompts:

```bash
./scripts/codex-project.sh
```

Then in Codex chat input use:

- `/bmad-help`
- `/bmad-bmm-*` workflows
- `/bmad-agent-bmm-*` agents

Do not run `/bmad-help` directly in `zsh`.

If you use Codex Desktop app launched from Applications, sync to global prompts too and restart the app:

```bash
./scripts/sync_codex_prompts.sh --global
```

Then use `/bmad-help` in the desktop chat input.

## 3.2) Run BMAD through Claude

Claude commands are in `.claude/commands` and should be invoked with `bmad-*` names:

- `/bmad-help`
- `/bmad-system-map`
- `/bmad-plan`
- `/bmad-implement`
- `/bmad-review`

If command names ever appear without `bmad-` prefix after an upgrade, normalize them again:

```bash
./scripts/sync_claude_bmad_names.sh
```

## 4) Regenerate project context assets

```bash
python3 scripts/generate_context_pack.py
```

This refreshes:

- `bmad/context/generated/00-index.md`
- `bmad/context/generated/<domain>.md`
- `bmad/context/generated/00-machine-index.json`
- `bmad/context/generated/00-endpoint-map.md`

## 5) Validate project context integrity

```bash
python3 scripts/validate_llm_context.py
```

Stricter mode:

```bash
python3 scripts/validate_llm_context.py --strict
```

## 6) Required load order for project context

1. `docs/llm/README.md`
2. `docs/llm/functionality-map.md`
3. `docs/llm/api-contracts.md`
4. `docs/llm/invariants-and-validation.md`
5. `bmad/context/generated/00-index.md`
6. primary `bmad/context/generated/<domain>.md`
7. `bmad/context/generated/00-machine-index.json`
8. `bmad/context/generated/00-endpoint-map.md`

## 7) Backlog source of truth

- Human view: `bmad/backlog/epic-tracks.md`
- Machine view: `bmad/backlog/story-board.json`
- CLI helper: `python3 scripts/next_bmad_story.py`
