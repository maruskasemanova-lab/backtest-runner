# BMAD Context Index

**Project:** Backtest Runner + Market Regime Detection

Dual-service intraday backtesting platform with L2 flow-aware strategy execution and React frontend.

## Services

| Service | Port | Responsibility |
|---|---:|---|
| `market_regime_detection` | 8001 | Regime detection, strategy selection, signal/execution lifecycle |
| `backtest-runner` | 8002 | Data orchestration, bar playback, session control, WebSocket broadcast |
| `frontend` | 5173 | Visualization, controls, diagnostics |

## Data Flow

CSV/Parquet -> DataLoader -> SessionRunner -> POST /api/session/bar -> DayTradingManager -> decisions/trades -> WebSocket -> frontend

## Domains

| Domain ID | Title | Pack |
|---|---|---|
| `orchestration` | Run Orchestration API | `bmad/context/generated/orchestration.md` |
| `strategy-engine` | Flow Strategy Engine | `bmad/context/generated/strategy-engine.md` |
| `data-l2` | L2 Data & Features | `bmad/context/generated/data-l2.md` |
| `optimization-validation` | Optimization & Validation | `bmad/context/generated/optimization-validation.md` |
| `frontend` | Frontend | `bmad/context/generated/frontend.md` |

## Generated Assets

- `bmad/context/generated/00-machine-index.json` (symbols + routes)
- `bmad/context/generated/00-endpoint-map.md` (global endpoint catalog)

## How To Use

- Pick one primary domain for the task.
- Load the primary domain pack plus `00-machine-index.json`.
- Keep changes local first; list contract deltas when crossing domains.
