# Adaptive Studio Epic Plan (BMAD)

Date: 2026-02-09  
Primary Domain: `frontend`  
Secondary Domains (contract-safe integration): `strategy-engine`, `orchestration`

## Change Goal

Add a third top-level UI tab (`Adaptive Studio`) where operators can configure adaptive strategy-selection behavior per ticker, persist it to AOS source-of-truth, and apply it on the next run start.

## Scope

### In Scope

- Third tab in app navigation: `Adaptive Studio`.
- New FE editor for per-ticker adaptive selection flow:
  - `strategy_selection_mode`
  - `max_active_strategies`
  - flow-bias toggle + ordered flow-bias strategy list
  - OHLCV fallback toggle
  - ordered macro regime preferences
  - ordered micro-regime preferences
- Visual decision-flow diagram reflecting effective adaptive settings.
- Persistence through existing AOS endpoints:
  - `GET /api/aos-config/{ticker}`
  - `POST /api/aos-config/update`
- Strategy-engine runtime adoption of persisted adaptive settings in `_select_strategies`.

### Out of Scope

- New API endpoints for adaptive config.
- Changes to no-lookahead, same-bar execution, comparable mode semantics.
- Rework of individual strategy signal/exit internals.

## Proposed Epic

## Epic 8: Adaptive Strategy Studio

Expose and operationalize adaptive selection decision controls through FE with a visual flow model.

### Story 8.1: Adaptive Studio UI + Runtime Wiring

As a trading operator,  
I want to configure adaptive strategy selection in a dedicated FE studio,  
so that per-ticker decision flow is transparent, editable, and applied deterministically on next run.

Acceptance Criteria:

1. App navigation contains a third tab `Adaptive Studio`.
2. Adaptive Studio loads per-ticker adaptive settings from AOS config via API.
3. Adaptive Studio allows editing and saving adaptive settings without raw JSON editing.
4. Adaptive Studio displays a visual decision-flow diagram reflecting current settings.
5. Strategy engine `_select_strategies` honors saved adaptive settings for selection behavior.
6. Saved settings are applied on next `POST /api/run/start`.

## Validation Plan

1. `npm run build`
2. `pytest tests/test_start_run_strategy_overrides_mode.py`
3. `pytest /Users/hotovo/.gemini/antigravity/scratch/market_regime_detection/tests/test_day_trading_manager_strategy_selection_mode.py`
4. `python3 scripts/generate_context_pack.py`
5. `python3 scripts/validate_llm_context.py --strict`

## Risks

1. Misconfigured preference lists can reduce candidate diversity and trade frequency.
2. `all_enabled` mode can still increase compute/load due to larger candidate set.
3. If ticker config is partially defined, default preference fallbacks must remain deterministic.
