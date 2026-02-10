# Story 10.2: L2 Coverage Tuning And Profile Apply

Status: done

## Story

As a trading operator,  
I want adaptive tuning limited to real OHLCV+L2 covered dates with reusable tuned profiles,  
so that I can tune on valid data and apply selected profiles directly to backtests.

## Acceptance Criteria

1. FE displays real OHLCV/L2/overlap coverage for selected ticker.
2. Tuner can enforce L2-required day filtering.
3. Best trial from completed tuner runs is saved as a reusable ticker profile.
4. FE shows saved adaptive tuned profiles list.
5. FE can apply a selected profile to AOS config for next backtest run.
6. Backward compatibility is preserved for existing run/start flow.

## Tasks / Subtasks

- [x] Add coverage/options endpoint for tuner (`/api/adaptive-tuner/options/{ticker}`).
- [x] Add profile-apply endpoint (`/api/adaptive-tuner/profiles/apply`).
- [x] Add L2-required date resolution for run endpoint.
- [x] Persist best trial as `adaptive_tuner_profiles` in ticker AOS config.
- [x] Extend `AdaptiveTuner.jsx` with real coverage card, L2-required controls, profile list, apply action.
- [x] Add FE styles for profile list/actions.
- [x] Add/extend backend tests for L2-date resolution and profile apply behavior.
- [x] Update LLM docs + regenerate context pack.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Completion Notes List

- Added real ticker coverage payload (OHLCV, L2, overlap days) for tuner prefill and UI.
- Added L2-required day filtering so requested ranges are constrained to valid overlap days when enabled.
- Added profile persistence from best trial to AOS config with `profile_id` metadata.
- Added profile apply API to promote selected tuned profile into active ticker adaptive settings.
- Extended Adaptive Tuner FE with:
  - real coverage display,
  - L2-required/strict L2 toggles,
  - saved profile list,
  - Apply-To-Backtest action.

### File List

- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/api_server.py`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/frontend/src/components/AdaptiveTuner.jsx`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/frontend/src/index.css`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/tests/test_adaptive_tuner_api.py`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/docs/llm/functionality-map.md`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/docs/llm/api-contracts.md`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/_bmad-output/planning-artifacts/adaptive-l2-tuning-profiles-plan.md`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/_bmad-output/implementation-artifacts/10-2-l2-coverage-tuning-and-profile-apply.md`

### Change Log

- 2026-02-09: Implemented L2 coverage-gated tuning and adaptive tuned profile apply flow.
