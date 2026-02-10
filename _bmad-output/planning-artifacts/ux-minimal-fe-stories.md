# UX Minimal Design Note (FE-01..FE-03)

## Purpose

This artifact provides minimal UX alignment for frontend stories already defined in epic tracks:

- `FE-01` Add execution/risk controls to run form
- `FE-02` L2 diagnostics card
- `FE-03` Marker detail drill-down for partial and adverse-flow exits

It does not introduce new scope. It only clarifies interaction details already implied by:

- `plans/final-architecture-plan.md`
- `bmad/backlog/epic-tracks.md`
- `_bmad-output/planning-artifacts/PRD.md`

## Primary Users

1. Trading analyst running backtest sessions and reviewing outcomes.
2. Strategy researcher tuning execution/risk behavior and reading diagnostics.

## UX Principles

1. Controls before diagnostics: configuration first, analysis second.
2. Keep playback readable: no diagnostic panel should block timeline comprehension.
3. Explanations must be actionable: every metric should map to a decision context.

## Journey Mapping

### Journey J1: Configure and Run (FE-01)

As a trading analyst, I want to set execution/risk controls before starting a run so that run behavior matches my test hypothesis.

Key interaction points:

- User opens Run Config form.
- User edits execution/risk fields mapped to runner start payload.
- User starts run and sees effective configuration reflected in session context.

### Journey J2: Inspect L2 Diagnostics (FE-02)

As a strategy researcher, I want to inspect L2 diagnostics while reviewing markers so that I can explain why entries/exits happened.

Key interaction points:

- User selects marker or bar.
- User opens diagnostics card.
- User sees flow score, aggression, absorption, and large trader activity values.

### Journey J3: Drill Into Exit Details (FE-03)

As a trading analyst, I want marker-level exit detail so that I can verify partial exits and adverse-flow behavior.

Key interaction points:

- User clicks marker in timeline or chart.
- User opens marker detail panel.
- User sees exit reason, cost components, and partial/adverse-flow specifics.

## Story-Level UX Acceptance Criteria

### FE-01 UX AC

**Given** the Run Config panel is open  
**When** the user edits execution/risk controls  
**Then** the UI clearly labels each control and preserves the chosen values in the start request payload  
**And** the mapping remains aligned to `/api/run/start` fields.

### FE-02 UX AC

**Given** a bar or marker with L2 context is selected  
**When** the diagnostics card is shown  
**Then** flow score, aggression, absorption, and large trader activity are visible in one view  
**And** values use consistent labeling across sessions.

### FE-03 UX AC

**Given** marker details are opened for an exit event  
**When** the event is a partial or adverse-flow exit  
**Then** the panel displays the specific exit reason and cost components  
**And** the information is readable without leaving the current playback context.

## Component Alignment

- Run controls: `frontend/src/components/RunConfig.jsx`
- Diagnostics and marker detail: `frontend/src/components/DecisionPanel.jsx`
- Session summary context: `frontend/src/components/SessionSummary.jsx`

## Out of Scope

1. New visual themes, branding, or layout redesign.
2. New frontend feature tracks outside `FE-01..FE-03`.
3. Additional APIs beyond existing contracts.

