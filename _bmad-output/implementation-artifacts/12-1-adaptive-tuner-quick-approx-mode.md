# Story 12.1: Adaptive Tuner Quick Approx Mode

Status: done

## Story

As a trading operator,  
I want a quick approximation mode for adaptive tuning,  
so that I can evaluate more combinations faster and keep full-range tuning for confirmation runs.

## Acceptance Criteria

1. Backend accepts quick mode fields (`quick_mode`, `quick_max_days`, `quick_trial_boost`).
2. Quick mode samples representative days from eligible date ranges.
3. Quick mode scales effective trial budget and reports it in job metadata.
4. FE exposes quick mode controls and budget preview.
5. FE shows sampled-day and trial-budget details in job status.
6. Existing standard tuning behavior remains backward compatible.

## Tasks / Subtasks

- [x] Extend `AdaptiveTunerRequest` with quick mode fields.
- [x] Add date sampling helper for representative quick-day subsets.
- [x] Add trial budget resolver with optional quick boost.
- [x] Wire quick metadata into `/api/adaptive-tuner/run` response + job payload.
- [x] Apply quick trial budgeting to both v1 and v2 tuner workers.
- [x] Expose quick mode controls in `AdaptiveTuner.jsx`.
- [x] Add backend tests for quick sampling and metadata.
- [x] Update docs and BMAD artifacts.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Completion Notes List

- Added deterministic quick-day sampling (`_sample_evenly_spaced_days`) to keep chronology and coverage spread.
- Added unified trial-budget resolver (`_resolve_tuner_trial_budget`) used by both v1 and v2 tuner jobs.
- Added quick metadata to job payload/summary:
  - source vs sampled effective days
  - trial budget requested/boost/effective
- Added FE quick mode toggle and controls:
  - quick sample days
  - trial boost multiplier
  - effective trial budget preview before run
- Preserved backward compatibility: default behavior stays standard tuning when quick mode is not enabled.

### File List

- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/api_server.py`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/frontend/src/components/AdaptiveTuner.jsx`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/tests/test_adaptive_tuner_api.py`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/docs/llm/functionality-map.md`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/docs/llm/api-contracts.md`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/_bmad-output/planning-artifacts/adaptive-tuner-quick-approx-plan.md`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/_bmad-output/implementation-artifacts/12-1-adaptive-tuner-quick-approx-mode.md`

### Change Log

- 2026-02-10: Implemented quick approximate adaptive tuner mode with sampled-day evaluation and boosted trial budget.
