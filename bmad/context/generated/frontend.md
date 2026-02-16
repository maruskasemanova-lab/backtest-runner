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
| `frontend/src/App.jsx` | yes | 1310 | `0452b19 2026-02-13` |
| `frontend/src/components/CandlestickChart.jsx` | yes | 773 | `5ba62b7 2026-02-08` |
| `frontend/src/components/DecisionPanel.jsx` | yes | 607 | `64da33c 2026-02-10` |
| `frontend/src/components/SessionSummary.jsx` | yes | 99 | `36d343c 2026-02-03` |
| `frontend/src/components/RunConfig.jsx` | yes | 3611 | `38387c6 2026-02-13` |
| `frontend/src/components/PlaybackControls.jsx` | yes | 262 | `0452b19 2026-02-13` |
| `frontend/src/components/DataManager.jsx` | yes | 696 | `baf7110 2026-02-07` |
| `frontend/src/components/AdaptiveStrategyStudio.jsx` | yes | 1447 | `a60ac04 2026-02-11` |
| `frontend/src/components/DiagnosticCalendar.jsx` | yes | 1095 | `-` |
| `frontend/src/components/StrategySettings.jsx` | yes | 1077 | `0452b19 2026-02-13` |
| `frontend/src/components/AOSOptimizations.jsx` | yes | 1422 | `0452b19 2026-02-13` |
| `frontend/src/components/IntrabarPanel.jsx` | yes | 186 | `5ba62b7 2026-02-08` |

## Change Checks

- Any API payload change must include frontend compatibility check.
- Keep desktop/mobile rendering stable.
- Preserve marker semantics (signal queued, position opened/closed).
- Live playback controls must remain consistent with backend state endpoints.

## Critical Invariants

- UI marker timeline must preserve backend event ordering.
- Schema changes in run/session endpoints require explicit UI fallback behavior.
- Chart annotations and session summary must remain backward compatible.
- Data manager operations must not block core playback controls.

## Test Targets

- `frontend/manual-smoke: start run -> play/pause/step -> markers -> summary`

## Key Symbols

- (no Python symbols discovered in mapped files)

## Endpoint Summary

| Method | Path | Handler | File |
|---|---|---|---|
| `-` | `-` | `-` | `-` |

## Prompt Primer

Load this domain pack with `bmad/context/generated/00-index.md` and `bmad/context/generated/00-machine-index.json`, then keep edits scoped to mapped files unless interface changes are explicit.
