# Domain: Frontend

**ID:** `frontend`

## Mission

Own playback UI, chart rendering, and operational diagnostics.

## Depends On

- `orchestration`
- `strategy-engine`

## Entrypoints

- `frontend/src/App.jsx`
- `frontend/src/components`

## File Inventory

| File | Exists | Lines | Last Commit |
|---|---:|---:|---|
| `frontend/src/App.jsx` | yes | 599 | `583f2bc 2026-02-06` |
| `frontend/src/components/CandlestickChart.jsx` | yes | 612 | `583f2bc 2026-02-06` |
| `frontend/src/components/DecisionPanel.jsx` | yes | 283 | `583f2bc 2026-02-06` |
| `frontend/src/components/SessionSummary.jsx` | yes | 99 | `36d343c 2026-02-03` |
| `frontend/src/components/RunConfig.jsx` | yes | 353 | `583f2bc 2026-02-06` |

## Change Checks

- Any API payload change must include frontend compatibility check.
- Keep desktop/mobile rendering stable.
- Preserve marker semantics (signal queued, position opened/closed).

## Prompt Primer

Load this file plus `bmad/context/generated/00-index.md`, then keep edits scoped to the file inventory unless interface changes are explicitly required.
