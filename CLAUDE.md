# CLAUDE.md

Persistent context for Claude Code in this repository.

## Project Context

`backtest-runner` is the orchestration/API layer (port `8002`) for intraday backtests.
It drives bar playback, optional L2 enrichment, strategy API session calls (`market_regime_detection`, port `8001`), and frontend telemetry (`frontend`, port `5173`).

Most sensitive subsystem: Adaptive Tuning + AOS persistence (`aos_optimization/aos_config.json`) because tuner trials intentionally rewrite ticker config during evaluation.

## Source Of Truth (Read In Order)

1. `docs/llm/README.md`
2. `docs/llm/functionality-map.md`
3. `docs/llm/api-contracts.md`
4. `docs/llm/invariants-and-validation.md`
5. `bmad/context/generated/00-index.md`
6. `bmad/context/generated/<domain>.md`
7. `bmad/context/generated/00-machine-index.json`
8. `bmad/context/generated/00-endpoint-map.md`
9. `docs/llm/adaptive-tuning-c4x3.md` (only for C4-like/parallel adaptive tuning requests)

If docs conflict with code, code is authoritative. Update docs in the same change.

## Domain Routing

Pick exactly one primary domain from `bmad/context/component-map.json`:

- `orchestration`
- `strategy-engine`
- `data-l2`
- `optimization-validation`
- `frontend`

For adaptive tuner behavior and AOS semantics, primary domain is usually `orchestration`.

## Core Invariants (Do Not Break)

- No look-ahead bias in bars, L2 features, or decision logic.
- No same-bar signal execution (`signal_bar_index < entry_bar_index`).
- Runner/strategy API contracts remain backward compatible unless intentionally versioned.
- `comparable_mode=true` forces cold start and ignores warm-start checkpoint loading.
- L2 sessionized cumulative metrics reset per market day when enabled.

## Command / Agent / Skill Workflow

- Commands live in `.claude/commands/` and should include YAML frontmatter (`description` minimum).
- Reusable procedural guardrails live in `.claude/skills/`.
- Complex multi-step tasks can be delegated by command to an agent in `.claude/agents/`.
- Prefer command entry points; use agents for bounded delegation; use skills for reusable deterministic workflows.

Relevant project artifacts:

- Command: `.claude/commands/bmad-orchestrate.md`
- Agent: `.claude/agents/bmad-orchestration-agent.md`
- Skill: `.claude/skills/bmad-context-guard/SKILL.md`

## Repo Map (High-Level)

- `api_server.py`: runner API, adaptive tuner jobs, AOS/profile endpoints, run lifecycle.
- `session_runner.py`: bar stepping/playback, marker lifecycle, summary/report integration.
- `data_loader.py`: OHLCV load/filter utilities.
- `src/l2_*`: L2 loading/feature computation/sessionized normalization.
- `aos_optimization/aos_config.json`: persisted per-ticker AOS + adaptive tuned profiles.
- `tests/test_adaptive_tuner_api.py`: adaptive tuner behavior and profile persistence tests.
- `frontend/src/components/AdaptiveTuner.jsx`: tuner UI, run job + apply profile actions.
- `frontend/src/components/AdaptiveStrategyStudio.jsx`: edit/save adaptive config.
- `frontend/src/components/RunConfig.jsx`: applies selected adaptive profile before run start.

See also `docs/REPO_MAP.md` (generated).

## Quick Commands

- Install backend deps: `python3 -m pip install -r requirements.txt`
- Start strategy API (`8001`):
  - `cd /Users/hotovo/.gemini/antigravity/scratch/market_regime_detection && python -m uvicorn api_server:app --port 8001 --reload`
- Start runner API (`8002`): `python -m uvicorn api_server:app --port 8002 --reload`
- Start frontend (`5173`): `cd frontend && npm run dev`
- Generate context pack: `python3 scripts/generate_context_pack.py`
- Validate context pack: `python3 scripts/validate_llm_context.py`
- Strict validation: `python3 scripts/validate_llm_context.py --strict`

## Adaptive Tuning (Critical Notes)

### Entry points

- `POST /api/adaptive-tuner/run`
- `GET /api/adaptive-tuner/{job_id}`
- `GET /api/adaptive-tuner`
- `GET /api/adaptive-tuner/options/{ticker}`
- `POST /api/adaptive-tuner/profiles/apply`

### File semantics (`aos_optimization/aos_config.json`)

- Source of truth path: `AOS_CONFIG_PATH` in this repo.
- Writes are whole-file rewrites via `_save_aos_config(...)`, not append-only logs.
- Tuner workers intentionally write temporary trial configs.
- On normal completion, final config/profile is rewritten.
- On handled exceptions, worker attempts to restore original config.
- Hard crashes mid-job can leave temporary config persisted.

### Concurrency caveat

- Parallel tuner slots are capped at 3 (`MAX_PARALLEL_ADAPTIVE_TUNERS`).
- For full isolation of external strategy runtime behavior, use distinct `strategy_api_url` ports.

### Standard C4x3 workflow

When asked for "like c4" or "3 independent tunings", follow `docs/llm/adaptive-tuning-c4x3.md`.

## Required Change Protocol

1. Route task to one primary domain.
2. Load primary generated domain pack + machine index.
3. Use Axon first when available (`query -> context -> impact`).
4. Implement minimal viable change.
5. Run required validation commands + impacted domain tests.
6. Report: changed files, contract deltas, tests run/results, residual risks.

## Validation Before Final Answer

- `python3 scripts/generate_context_pack.py`
- `python3 scripts/validate_llm_context.py`
- domain-specific `pytest` targets from `bmad/context/component-map.json`
