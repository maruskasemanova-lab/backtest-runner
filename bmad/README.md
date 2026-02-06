# BMAD Workspace

This folder makes the project editable by large LLMs (Claude, Codex, GPT) in a
modular way, without losing system context.

## Goals

- Keep a stable architecture map for both services:
  - `backtest-runner` (port `8002`)
  - `market_regime_detection` (port `8001`)
- Partition work into domains with explicit boundaries.
- Generate compact context packs that can be loaded per task.
- Preserve a single "whole-system" index for cross-domain changes.

## Main Files

- `context/component-map.json`: canonical domain map.
- `context/generated/`: generated context packs (do not edit manually).
- `templates/`: story/task templates for structured LLM execution.
- `workflows/`: BMAD-style workflow adapted to this project.
- `backlog/`: epic tracks + machine-readable story board.

## Refresh Context Packs

Run:

```bash
python3 scripts/generate_context_pack.py
```

This regenerates `bmad/context/generated/*.md` from `component-map.json`.

## Claude Commands

Project commands are in `.claude/commands/`:

- `/bmad-system-map`
- `/bmad-plan`
- `/bmad-story`
- `/bmad-implement`
- `/bmad-review`

Use these with a generated context pack to keep prompts focused.
