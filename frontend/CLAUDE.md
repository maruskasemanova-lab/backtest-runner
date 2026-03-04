# Frontend CLAUDE.md

Frontend-local instructions for Claude Code in `frontend/`.

## Scope

Applies when current working directory is `frontend/` (or when files inside this directory are actively read/edited).
Root `CLAUDE.md` still applies via ancestor loading.

## Primary Domain

Use domain: `frontend` from `bmad/context/component-map.json`.

Required reads before non-trivial edits:

1. `../docs/llm/functionality-map.md`
2. `../docs/llm/api-contracts.md`
3. `../docs/llm/invariants-and-validation.md`
4. `../bmad/context/generated/00-index.md`
5. `../bmad/context/generated/frontend.md`
6. `../bmad/context/generated/00-machine-index.json`

## Frontend Invariants

- Preserve marker ordering from backend payloads.
- Maintain fallback-safe behavior for endpoint schema drift.
- Keep playback controls aligned with backend state (`play/pause/step/stop`).
- Keep desktop and mobile rendering functional.

## Verification

- Run frontend build for structural regression checks: `npm run build`
- Run manual smoke path after UI behavior changes:
  - start run -> play/pause/step -> marker timeline -> session summary

## Notes

- Prefer minimal deltas in shared components (`App.tsx`, chart, run controls).
- If API payload assumptions change, list the contract delta explicitly in final output.
