# Domain: Frontend

**ID:** `frontend`

## Mission

Own playback UI, chart rendering, and operational diagnostics.

## Depends On

- `orchestration`
- `strategy-engine`

## Entrypoints

- `frontend/src/App.tsx`
- `frontend/src/components`

## File Inventory

| File | Exists | Lines | Last Commit |
|---|---:|---:|---|
| `frontend/src/main.tsx` | yes | 74 | `f30de01 2026-03-05` |
| `frontend/src/App.tsx` | yes | 820 | `f894916 2026-03-04` |
| `frontend/src/auth/supabaseAuth.ts` | yes | 385 | `b9accc6 2026-02-18` |
| `frontend/src/components/CandlestickChart.tsx` | yes | 345 | `065f203 2026-03-04` |
| `frontend/src/components/decision-panel/DecisionPanel.tsx` | yes | 307 | `f30de01 2026-03-05` |
| `frontend/src/components/SessionSummary.tsx` | yes | 330 | `f30de01 2026-03-05` |
| `frontend/src/components/RunConfig.tsx` | yes | 420 | `f30de01 2026-03-05` |
| `frontend/src/components/PlaybackControls.tsx` | yes | 169 | `f30de01 2026-03-05` |
| `frontend/src/components/DataManager.tsx` | yes | 345 | `0248cab 2026-02-28` |
| `frontend/src/components/AdaptiveStrategyStudio.tsx` | yes | 352 | `d064025 2026-03-01` |
| `frontend/src/components/diagnostic-calendar/DiagnosticCalendar.tsx` | yes | 108 | `0d50960 2026-03-04` |
| `frontend/src/components/StrategySettings.tsx` | yes | 658 | `51e9988 2026-03-02` |
| `frontend/src/components/AOSOptimizations.tsx` | yes | 386 | `f30de01 2026-03-05` |
| `frontend/src/components/IntrabarPanel.tsx` | yes | 186 | `b9accc6 2026-02-18` |

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
