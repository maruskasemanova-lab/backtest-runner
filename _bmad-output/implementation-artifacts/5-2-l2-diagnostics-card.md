# Story 5.2: L2 Diagnostics Card

Status: done

## Story

As a strategy researcher,  
I want a focused diagnostics card for L2 flow context,  
so that I can interpret signal quality without reading raw logs.

## Acceptance Criteria

1. Given session or marker context is selected in frontend, when diagnostics panel is rendered, then flow score, aggression, absorption, and large trader activity are shown.
2. Given diagnostics values, when viewed across sessions, then labeling remains consistent and readable.

## Tasks / Subtasks

- [x] Implement explicit L2 diagnostics rendering in FE decision details
  - [x] Added normalized extraction of L2 diagnostics sources from marker payload in `DecisionPanel.jsx`.
  - [x] Added dedicated `L2 Diagnostics` section with consistent labels (`Flow Score`, `Signed Aggression`, `Absorption Rate`, `Large Trader Activity`, `VWAP Execution Flow`).
- [x] Verify frontend build
  - [x] `cd frontend && npm run build`

## Dev Agent Record

### Agent Model Used

GPT-5 Codex (CLI)

### Completion Notes List

- FE now renders an explicit diagnostics card section for the required L2 metrics.

### File List

- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/frontend/src/components/DecisionPanel.jsx`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/_bmad-output/implementation-artifacts/5-2-l2-diagnostics-card.md`

### Change Log

- 2026-02-09: Added explicit L2 diagnostics section to FE decision panel and marked story done.
