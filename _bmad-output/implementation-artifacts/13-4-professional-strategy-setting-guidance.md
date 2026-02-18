# 13-4 Professional Strategy Setting Guidance

## Domain
- frontend

## Goal
- Extend per-strategy settings with practical professional guidance for:
  - what to tune
  - expected behavior of key thresholds
  - what to monitor while tuning

## Implementation

### 1) Per-field professional guidance
- Added `PRO_FIELD_GUIDE` mapping in `frontend/src/components/StrategySettings.tsx`.
- Covers strategy fields exposed by `/api/strategies` (including flow, risk, intrabar/scalp fields).
- Each field now has:
  - compact `Pro: <range>` hint visible in UI
  - hover title with expected behavior and tuning intent

### 2) Per-strategy Professional Playbook
- Added `PRO_STRATEGY_PLAYBOOK` + fallback `DEFAULT_PRO_PLAYBOOK` in `frontend/src/components/StrategySettings.tsx`.
- For each strategy card (expanded view), UI now renders:
  - `Professional Playbook` section
  - key professional watchpoints tied to strategy-specific parameters

### 3) UI control
- Added toolbar toggle `Pro Notes` to enable/disable professional guidance blocks.

### 4) Styling
- Added new styles in `frontend/src/index.css`:
  - `sc-chip-btn-pro`
  - `sc-pro-card`, `sc-pro-title`, `sc-pro-grid`, `sc-pro-item`, `sc-pro-key`
  - `sc-field-meta`

## Files changed
- `frontend/src/components/StrategySettings.tsx`
- `frontend/src/index.css`

## Validation
- `npm run build` (frontend): passed
- `python3 scripts/generate_context_pack.py`: passed
- `python3 scripts/validate_llm_context.py`: passed
- `python3 scripts/validate_llm_context.py --strict`: passed

## Notes
- No backend/API contract changes.
- Guidance is advisory UI metadata only; strategy execution semantics unchanged.
