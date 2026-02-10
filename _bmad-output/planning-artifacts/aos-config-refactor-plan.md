# AOS Config Refactor Plan (BMAD)

Date: 2026-02-09  
Primary Domain: `frontend`  
Secondary Domain (contract-safe integration): `orchestration`

## Change Goal

Presunúť AOS konfiguráciu na plne file-driven model pre každý ticker, odstrániť hardcoded AOS UI bloky (Time Filter, Long Only, Trailing Stop) a používať vždy predvyplnenú konfiguráciu načítanú z `aos_config.json`.  
Upravená konfigurácia z FE sa musí po uložení použiť pri štarte runu.

## Scope

### In Scope

- Odstrániť z FE AOS panelu hardcoded sekcie:
  - `⏰ Time Filter` + pevný text s 14:00/15:00
  - `📈 Long Only Mode` + pevný text o short/long výsledkoch
  - `📏 Trailing Stop %` + pevný text o 2.0%/0.6%
- Nahradiť ich file-first editorom per ticker:
  - načítanie zo súboru cez existujúci endpoint `/api/aos-config`
  - predvyplnenie podľa zvoleného tickeru
  - uloženie úprav cez existujúci endpoint `/api/aos-config/update`
- Normalizovať AOS ticker shape v súbore tak, aby každý ticker mal konzistentné polia potrebné pre runtime aplikáciu.
- Pri štarte runu zachovať správanie: runner používa aktuálnu uloženú AOS konfiguráciu tickeru.

### Out of Scope

- Nové backend endpointy pre AOS.
- Zmena základných no-lookahead invariantov.
- Zmena core stratégie mimo konfigurácie.

## Proposed Epic

## Epic 6: File-Driven AOS Configuration in FE

Enable full per-ticker AOS configurability from FE without hardcoded UI assumptions, while preserving existing API contracts.

### Story 6.1: Remove Hardcoded AOS Controls

As a user,  
I want AOS UI without fixed heuristic cards for time filter/long-only/trailing-stop,  
so that UI reflects real config instead of static assumptions.

Acceptance Criteria:

1. AOS panel no longer renders fixed Time Filter / Long Only / Trailing Stop cards.
2. No hardcoded “optimization tip” text tied to one ticker profile remains.
3. FE build passes.

### Story 6.2: File-First Per-Ticker Prefill

As a user,  
I want selected ticker AOS config loaded from file and shown prefilled every time,  
so that I always edit current source-of-truth values.

Acceptance Criteria:

1. On ticker change, FE loads config from `/api/aos-config` and pre-fills editor with that ticker object.
2. FE does not inject ticker-specific hardcoded defaults that overwrite file values.
3. If ticker is missing in file, FE shows an explicit empty object state (`{}`) for that ticker.

### Story 6.3: Persist-and-Run Consistency

As a user,  
I want FE edits to be respected when I start a run,  
so that runtime behavior matches what I configured.

Acceptance Criteria:

1. Saving AOS ticker config in FE persists full ticker payload via `/api/aos-config/update`.
2. `/api/run/start` applies latest stored ticker config from `aos_config.json`.
3. Run response exposes applied AOS fields (`aos_applied`) for verification/debug.

## Technical Plan

1. Refactor `frontend/src/components/AOSOptimizations.jsx` to a file-driven editor-first layout.
2. Remove static benchmark/tip cards and fixed control cards.
3. Keep runtime-safe JSON validation before save.
4. Ensure state sync on ticker switch is deterministic and does not preserve stale draft from previous ticker.
5. Align `aos_optimization/aos_config.json` ticker entries to consistent top-level fields where missing (`time_filter_enabled`, `trading_hours`, `long_only`, `trailing_stop_pct`) using existing values where available.
6. Keep backend contract unchanged (`/api/aos-config`, `/api/aos-config/update`, `/api/run/start`).

## Validation Plan

Required:

1. `cd /Users/hotovo/.gemini/antigravity/scratch/backtest-runner/frontend && npm run build`
2. Start run smoke check in FE:
   - open ticker AOS config
   - edit + save
   - run start
   - confirm `aos_applied` in start response/state reflects saved values
3. `cd /Users/hotovo/.gemini/antigravity/scratch/backtest-runner && python3 scripts/generate_context_pack.py`
4. `cd /Users/hotovo/.gemini/antigravity/scratch/backtest-runner && python3 scripts/validate_llm_context.py --strict`

## Risks

1. Existing ticker configs with heterogeneous shapes can cause inconsistent FE display.
2. Unsaved FE edits can be mistaken as active config if UX does not clearly show save state.
3. Aggressive migration defaults for missing fields may alter runtime behavior if not reviewed.

## Rollback

1. Revert `AOSOptimizations.jsx` to previous commit.
2. Restore prior `aos_optimization/aos_config.json`.
3. Confirm start-run behavior with previous AOS settings.
