# Strategy Selection Flow via FE (BMAD)

Date: 2026-02-09  
Primary Domain: `frontend`  
Secondary Domains (contract-safe integration): `orchestration`, `strategy-engine`

## Change Goal

Sprístupniť kompletné nastavenie strategy-selection flow cez FE UI tak, aby:

- používateľ vedel pre ticker nastaviť execution mód (`adaptive_top_n` vs `all_enabled`) a limit aktívnych stratégií,
- FE predvyplnil tieto hodnoty z ticker configu,
- uložené hodnoty sa aplikovali pri ďalšom `POST /api/run/start`.

## Scope

### In Scope

- FE (`RunConfig`) rozšírenie AOS runtime sekcie o:
  - `strategy_selection_mode`
  - `max_active_strategies`
- Načítanie/persist per-ticker hodnôt cez existujúci flow:
  - `GET /api/aos-config/{ticker}`
  - `POST /api/aos-config/update`
- Runner passthrough do strategy API session config:
  - `strategy_selection_mode`
  - `max_active_strategies`
- Strategy engine runtime aplikácia módu:
  - `adaptive_top_n`: rešpektuje `max_active_strategies`
  - `all_enabled`: použije všetky enabled + regime-kompatibilné stratégie

### Out of Scope

- Nové endpointy pre stratégie alebo AOS.
- Zmena no-lookahead, same-bar, checkpoint/comparable invariants.
- Zmena business logiky jednotlivých stratégií (signal generation/exit rules).

## Proposed Epic

## Epic 7: FE-Driven Strategy Selection Flow

Enable per-ticker strategy-selection mode controls directly in FE and make runtime behavior deterministic on run start.

### Story 7.1: Strategy Selection Mode Controls + Runtime Apply

As a trading analyst,  
I want to set strategy selection behavior from FE for each ticker,  
so that run-time evaluation matches my configured mode without hidden defaults.

Acceptance Criteria:

1. FE run form shows `strategy_selection_mode` and `max_active_strategies` prefilled from selected ticker config.
2. FE persists these values to ticker AOS config before run start.
3. Runner sends effective values to strategy session config.
4. Strategy engine applies:
   - `adaptive_top_n`: limit = `max_active_strategies`
   - `all_enabled`: evaluate all enabled + regime-compatible strategies.
5. Existing API contracts remain backward compatible (new fields are additive and optional).

## Validation Plan

1. `npm run build` (frontend)
2. `pytest tests/test_start_run_strategy_overrides_mode.py` (runner contract/passthrough)
3. `pytest tests/test_day_trading_manager_strategy_selection_mode.py` (strategy-selection behavior)
4. `python3 scripts/generate_context_pack.py`
5. `python3 scripts/validate_llm_context.py --strict`

## Risks

1. Pri `all_enabled` môže narásť počet candidate signalov a zmeniť sa trade density.
2. Ak ticker config chýba, fallback môže maskovať, že profil nebol explicitne definovaný.
3. Nevalidné FE hodnoty (napr. `max_active_strategies`) musia byť striktne normalizované.
