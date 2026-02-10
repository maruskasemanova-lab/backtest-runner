# Story 10.1: Adaptive Studio Tuner Tab And v1 Search

Status: done

## Story

As a trading operator,  
I want to run adaptive tuning for selected date ranges and inspect ranked candidates,  
so that I can tune Adaptive Studio v1 settings and optionally persist the best result.

## Acceptance Criteria

1. FE exposes a dedicated `Adaptive Tuner` top-level tab.
2. FE submits tuner jobs with method/date/search-space inputs.
3. Backend provides `run`, `status`, and `list` endpoints for tuner jobs.
4. Tuner jobs evaluate candidates over date ranges and produce comparable scores.
5. FE displays progress, best trial, trials list, and day-level result details.
6. `optuna` mode falls back to random if dependency is not installed.
7. Persist-best mode updates AOS config; non-persist mode restores original config.
8. Existing `/api/run/start` behavior remains backward compatible.

## Tasks / Subtasks

- [x] Add `Adaptive Tuner` tab in app navigation.
- [x] Implement `AdaptiveTuner.jsx` with form, polling, and results views.
- [x] Add tuner page/table/progress CSS and responsive scrolling behavior.
- [x] Add `AdaptiveTunerRequest` and search helpers in runner API.
- [x] Add adaptive tuner job orchestration with grid/random/optuna execution.
- [x] Add adaptive tuner API endpoints for run/status/list.
- [x] Add backend tests for tuner request validation and job scheduling.
- [x] Update LLM docs with tuner flow and API contract sections.
- [x] Regenerate and validate context pack.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Completion Notes List

- Added new FE top-level view `Adaptive Tuner` and routed it from `App.jsx`.
- Implemented `AdaptiveTuner.jsx` for:
  - ticker/date range setup,
  - method + score metric selection,
  - configurable v1 search-space CSV fields,
  - job start, polling, progress bar, best-trial preview, trial ranking table, and day-level drill-down.
- Implemented in-memory runner job orchestration with new endpoints:
  - `POST /api/adaptive-tuner/run`
  - `GET /api/adaptive-tuner/{job_id}`
  - `GET /api/adaptive-tuner`
- Added grid/random candidate generation and optuna fallback support.
- Added optional best-candidate persistence to AOS config with safe restore behavior when not persisting.
- Added API-level tests for adaptive tuner search normalization, scoring behavior, version guard, and job queue creation.

### File List

- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/frontend/src/App.jsx`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/frontend/src/components/AdaptiveTuner.jsx`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/frontend/src/index.css`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/api_server.py`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/tests/test_adaptive_tuner_api.py`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/docs/llm/functionality-map.md`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/docs/llm/api-contracts.md`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/_bmad-output/planning-artifacts/adaptive-studio-tuner-plan.md`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/_bmad-output/implementation-artifacts/10-1-adaptive-studio-tuner-tab-and-v1-search.md`

### Change Log

- 2026-02-09: Implemented Adaptive Studio Tuner tab, job APIs, tests, and BMAD artifacts.
