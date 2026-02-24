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
| `frontend/src/main.tsx` | yes | 39 | `b9accc6 2026-02-18` |
| `frontend/src/App.tsx` | yes | 2704 | `8f49f06 2026-02-23` |
| `frontend/src/auth/supabaseAuth.ts` | yes | 385 | `b9accc6 2026-02-18` |
| `frontend/src/components/CandlestickChart.tsx` | yes | 839 | `1273b21 2026-02-23` |
| `frontend/src/components/DecisionPanel.tsx` | yes | 3085 | `1273b21 2026-02-23` |
| `frontend/src/components/SessionSummary.tsx` | yes | 165 | `1273b21 2026-02-23` |
| `frontend/src/components/RunConfig.tsx` | yes | 299 | `1273b21 2026-02-23` |
| `frontend/src/components/PlaybackControls.tsx` | yes | 262 | `b9accc6 2026-02-18` |
| `frontend/src/components/DataManager.tsx` | yes | 764 | `b9accc6 2026-02-18` |
| `frontend/src/components/AdaptiveStrategyStudio.tsx` | yes | 3004 | `b9accc6 2026-02-18` |
| `frontend/src/components/DiagnosticCalendar.tsx` | yes | 1262 | `1273b21 2026-02-23` |
| `frontend/src/components/StrategySettings.tsx` | yes | 928 | `1273b21 2026-02-23` |
| `frontend/src/components/AOSOptimizations.tsx` | yes | 1395 | `b9accc6 2026-02-18` |
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
