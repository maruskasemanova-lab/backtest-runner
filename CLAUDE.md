# CLAUDE.md

Persistent context for Claude Code in this repository.

## Project Context

`backtest-runner` is the orchestration/API layer (port `8002`) for intraday backtests.  
It drives bar playback, optional L2 enrichment, strategy API session calls (`market_regime_detection`, port `8001`), and frontend telemetry (`frontend`, port `5173`).

The most sensitive area is Adaptive Tuning + AOS config persistence (`aos_optimization/aos_config.json`), because tuner trials intentionally rewrite ticker config during evaluation.

## Source Of Truth (Read In Order)

1. `docs/llm/README.md`
2. `docs/llm/functionality-map.md`
3. `docs/llm/api-contracts.md`
4. `docs/llm/invariants-and-validation.md`
5. `bmad/context/generated/00-index.md`
6. `bmad/context/generated/<domain>.md`
7. `bmad/context/generated/00-machine-index.json`
8. `bmad/context/generated/00-endpoint-map.md`

If docs conflict with code, code wins. Update docs in the same change.

## Domain Routing

Pick one primary domain from `bmad/context/component-map.json`:

- `orchestration`
- `strategy-engine`
- `data-l2`
- `optimization-validation`
- `frontend`

For adaptive tuner behavior and AOS file semantics, primary domain is typically `orchestration`.

## Repo Map (High Level)

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
- Start strategy API (`8001`): `cd /Users/hotovo/.gemini/antigravity/scratch/market_regime_detection && python -m uvicorn api_server:app --port 8001 --reload`
- Start runner API (`8002`): `python -m uvicorn api_server:app --port 8002 --reload`
- Start frontend (`5173`): `cd frontend && npm run dev`
- Generate context pack: `python3 scripts/generate_context_pack.py`
- Validate context pack: `python3 scripts/validate_llm_context.py`
- Strict validation: `python3 scripts/validate_llm_context.py --strict`
- Adaptive tuner tests: `pytest tests/test_adaptive_tuner_api.py`

## Adaptive Tuning Engine (Critical)

### Entry Points

- `POST /api/adaptive-tuner/run`
- `GET /api/adaptive-tuner/{job_id}`
- `GET /api/adaptive-tuner`
- `GET /api/adaptive-tuner/options/{ticker}`
- `POST /api/adaptive-tuner/profiles/apply`

### Runtime Flow

1. Validate ticker/date range and resolve `effective_dates` (optionally OHLCV∩L2 overlap when `l2_required=true`).
2. Optional quick mode samples representative days (`quick_max_days`) and inflates trial budget (`quick_trial_boost`).
3. Create in-memory job record in `adaptive_tuner_jobs`.
4. Spawn async worker:
   - v1: `_run_adaptive_tuner_job`
   - v2: `_run_v2_adaptive_tuner_job`
5. For each trial, worker builds candidate config and **temporarily writes it to `aos_config.json`**.
6. Candidate is evaluated by running backtests day-by-day via `start_run(...)` + `runner.run_all(...)`.
7. Best trial is tracked; final profile entry is saved to `adaptive_tuner_profiles` (max 30).
8. If `persist_best=true`, best candidate is also applied into active ticker config; otherwise profile is saved without forcing active config replacement (unless no active profile exists yet).

### v1 vs v2

- v1 tunes adaptive selection controls (mode/top-n/switch hysteresis/flow-bias/fallback toggles).
- v2 adds multidimensional vector search (strategy set, regime filter sets, L2 thresholds, evidence params, per-strategy params, time windows, exit thresholds) plus optional vector analysis.
- v2 treats `grid` request as `random` due combinatorial explosion.

### Scoring

- Metrics: `pnl_pct`, `pnl_dollars`, `win_rate`, `trade_adjusted`, `robust`.
- `robust` penalizes instability/low-quality trade distributions; v2 uses temporal fold logic when enough days are available.

## AOS File Semantics (`aos_optimization/aos_config.json`)

### Source Of Truth

- Path: `AOS_CONFIG_PATH = <repo>/aos_optimization/aos_config.json`
- Helpers:
  - read: `_load_aos_config()` -> `load_json_file(...)`
  - write: `_save_aos_config(...)` -> `save_json_file(...)`
- Writes replace the whole JSON payload (pretty-printed), no append-only journal.

### Endpoints/Flows That Write This File

- `POST /api/aos-config/update`: merge ticker config patch and save.
- `POST /api/strategy-combos/capture`: add combo profile (and optionally mark active), save.
- `POST /api/strategy-combos/apply`: set active combo profile, save.
- `POST /api/adaptive-tuner/profiles/apply`: applies selected tuned candidate into ticker config + sets active profile id, save.
- `POST /api/adaptive-tuner/run` workers: repeatedly save temporary per-trial configs, then save final config/profile.

### What `POST /api/run/start` Does

- Reads AOS config (`_apply_aos_optimizations`) and applies settings to strategy API/runtime.
- Does **not** persist AOS file itself.
- But frontend `RunConfig` may call `/api/aos-config/update` and `/api/adaptive-tuner/profiles/apply` just before `run/start`, so a user-triggered run can mutate AOS indirectly.

### Overwrite/Restore Behavior During Tuning

- During tuner execution, temporary trial candidates are intentionally written to disk.
- On normal completion, final config is rewritten with profile list + optional persisted best candidate.
- On handled exception, worker attempts to restore `original_config`.
- If process crashes hard mid-job, temporary config may remain on disk.

### Concurrency Caveat

- `adaptive_tuner_lock` serializes tuner workers with each other.
- Other write endpoints are not guarded by that same lock.
- Running manual AOS updates/profile applies concurrently with tuner can produce last-write-wins behavior.

## Invariants (Do Not Break)

- No look-ahead bias in bars, L2 features, or decision logic.
- No same-bar signal execution (`signal_bar_index < entry_bar_index`).
- Runner/strategy API contracts remain backward compatible unless intentionally versioned.
- `comparable_mode=true` forces cold start and ignores warm-start checkpoint loading.
- L2 sessionized cumulative metrics reset per market day when enabled.

## Required Change Protocol

1. Route task to one primary domain.
2. Load domain pack + machine index.
3. Implement minimal viable change.
4. Run required validation commands and domain tests.
5. Report: files changed, contract deltas, tests run/results, residual risks.

## Validation Before Final Answer

- `python3 scripts/generate_context_pack.py`
- `python3 scripts/validate_llm_context.py`
- impacted domain tests from `bmad/context/component-map.json`
