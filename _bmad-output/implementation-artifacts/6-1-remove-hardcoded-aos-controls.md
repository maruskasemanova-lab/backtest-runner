# Story 6.1: Remove Hardcoded AOS Controls

Status: done

## Story

As a trading analyst,  
I want AOS UI without hardcoded time/long-only/trailing cards,  
so that UI reflects only real per-ticker configuration from file.

## Acceptance Criteria

1. Given AOS panel is rendered, when reviewing controls, then no fixed Time Filter / Long Only / Trailing Stop cards are shown.
2. Given AOS panel is rendered, when reviewing helper text, then no hardcoded ticker-specific profitability claims are present.
3. Frontend build passes.

## Tasks / Subtasks

- [x] Remove hardcoded control cards and benchmark/tips sections from AOS panel
- [x] Keep editor-focused UI for ticker config management
- [x] Validate frontend build

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Completion Notes List

- Removed static AOS sections (`Time Filter`, `Long Only`, `Trailing Stop`, benchmark card, optimization tips).
- AOS panel is no longer mounted in the main FE layout (users do not see raw AOS config UI during normal workflow).
- Frontend build passed.

### File List

- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/frontend/src/App.jsx`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/frontend/src/components/AOSOptimizations.jsx`
- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/_bmad-output/implementation-artifacts/6-1-remove-hardcoded-aos-controls.md`

### Change Log

- 2026-02-09: Removed hardcoded AOS controls and completed Story 6.1.
- 2026-02-09: Removed AOS panel from main FE layout so only FE-level effects are visible.
