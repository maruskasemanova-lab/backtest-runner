# BMAD Plan: Refaktor `day_trading_runtime_impl`

## Domain Routing
- Primary domain: `strategy-engine`
- Touchpoints: `orchestration` (payloady pre markery/reporting), `data-l2` (intrabar/L2 flow polia)

## Ciel
- Rozdelit `market_regime_detection/src/day_trading_runtime_impl.py` na logicke casti.
- Vytiahnut spolocnu logiku do zdielanych helperov/abstrakcii.
- Zachovat aktualne funkcionalne spravanie a API kontrakty.
- Zachovat kriticke invarianty: no-lookahead, no same-bar execution, deterministicke pending flow.

## Baseline (pred refaktorom)
- Subor ma ~3535 riadkov.
- Najvacsie bloky:
- `runtime_process_trading_bar` (~1356 riadkov)
- `runtime_evaluate_intraday_levels_entry_quality` (~767 riadkov)
- `runtime_process_bar` (~268 riadkov)
- V kode je duplicita pri zatvarani pozicie + skladani payloadov.
- V kode je ad-hoc debug I/O (`/tmp/sweep_debug.log`, `print(...)`), co miesa domenu a observability.
- V `DayTradingManager` chyba wrapper `_evaluate_intraday_levels_entry_quality`, hoci testy ho pouzivaju (kompatibilitne riziko).

## Refaktor Scope (MVP)
- Zamerat sa len na runtime vrstvu:
- `market_regime_detection/src/day_trading_runtime_impl.py`
- nove runtime moduly v `market_regime_detection/src/` (bez zmeny endpoint kontraktov)
- `market_regime_detection/src/day_trading_manager.py` (iba delegacne wrappery)
- testy v `market_regime_detection/tests/*` + `backtest-runner/tests/test_day_trading_runtime_guards.py`

## Target Struktura (po refaktore)
- `market_regime_detection/src/day_trading_runtime_impl.py`
  - kompatibilitny facade: exportuje rovnake `runtime_*` funkcie ako dnes.
- `market_regime_detection/src/day_trading_runtime_intrabar.py`
  - `_calculate_intrabar_1s_snapshot`
  - `_micro_confirmation_snapshot`
  - `_intrabar_confirmation_snapshot`
- `market_regime_detection/src/day_trading_runtime_sweep.py`
  - `_liquidity_sweep_nearest_level`
  - `runtime_detect_liquidity_sweep`
  - `_resolve_liquidity_sweep_confirmation`
- `market_regime_detection/src/day_trading_runtime_entry_quality.py`
  - `runtime_evaluate_intraday_levels_entry_quality`
  - strategicke rule evaluatory (`vwap_magnet`, `rotation`, `mean_reversion`, `momentum`)
  - zdielane utility pre confluence/gap/value-area/poc checks
- `market_regime_detection/src/day_trading_runtime_position_flow.py`
  - pending-signal execution flow (micro/intrabar/context-risk)
  - active-position lifecycle (hard exits, partial, fail-fast, time/adverse, trailing)
  - spolocny helper `_close_position_and_build_payload(...)`
- `market_regime_detection/src/day_trading_runtime_signal_flow.py`
  - signal pipeline + gate sequence + rejection payload builder
  - `runtime_generate_signal`
- `market_regime_detection/src/day_trading_runtime_indicators.py`
  - `runtime_calculate_indicators`
- `market_regime_detection/src/day_trading_runtime_portfolio.py`
  - `_portfolio_drawdown_snapshot`
  - realized/unrealized pnl helpery

## Abstrakcie, ktore zavedies
- `RuntimeBarContext` dataclass:
  - `session`, `bar`, `timestamp`, `current_bar_index`, `current_price`, `session_key`
- `GateDecision` dataclass:
  - `passed`, `reason`, `details`
- `EntryQualitySnapshot` dataclass:
  - normalizovany snapshot levelov, eventov, volume profile a configu
- `CloseAction` helper:
  - unifikuje opakovany pattern: close trade -> update session -> payload marker

## Fazy Implementacie

## Faza 0: Stabilizacia kontraktu pred rozsekavanim
- Pridaj delegacny wrapper do `DayTradingManager`:
- `_evaluate_intraday_levels_entry_quality(...) -> runtime_evaluate_intraday_levels_entry_quality(...)`
- Odstran hardcoded debug `print`/`/tmp` I/O z runtime cesty a nahrad `logger.debug`.
- Acceptance:
- existujuce runtime testy bezi bez zmeny behavioru.

## Faza 1: Extrakcia pure helperov (bez behavioralnych zmien)
- Presun intrabar/sweep/pnl helpery do novych modulov.
- V `day_trading_runtime_impl.py` nechaj iba import-forwarding.
- Acceptance:
- nezmenene vystupne payload kluce pre testovane scenare.

## Faza 2: Entry-quality gate modularizacia
- Rozdel `runtime_evaluate_intraday_levels_entry_quality` na:
- builder snapshotu
- shared checks
- strategy-specific rules
- Udrz identicky shape `context_payload` (`checks`, `stats`, `reasons`, `target_price_override`).
- Acceptance:
- testy gate + mean-reversion target override prejdu bez delta.

## Faza 3: Trading bar pipeline decomposition
- Rozdel `runtime_process_trading_bar` na deterministicke kroky:
- `handle_portfolio_halt`
- `execute_pending_signal`
- `manage_active_position`
- `enforce_daily_loss`
- `refresh_regime_and_maybe_generate_signal`
- Vytiahni spolocnu close payload logiku.
- Acceptance:
- ziadna zmena v pravidle `signal_bar_index < entry_bar_index`.
- stale marker payload kluce ostavaju kompatibilne.

## Faza 4: `runtime_process_bar` phase handlers
- Rozdel na handlery pre:
- premarket
- regime_detection
- trading
- end_of_day
- Zachovaj identicke transition pravidla `SessionPhase`.
- Acceptance:
- `process_bar` vracia rovnake top-level fields ako dnes.

## Faza 5: Context pack + docs sync
- Aktualizuj `bmad/context/component-map.json`:
- pridaj runtime moduly pod `strategy-engine` file inventory
- Regeneruj a validuj context pack.
- Acceptance:
- machine index uz obsahuje runtime moduly/symboly.

## Test Plan (gating)
- Baseline / strategy runtime:
- `pytest -q tests/test_day_trading_runtime_guards.py`
- `pytest -q /Users/hotovo/.gemini/antigravity/scratch/market_regime_detection/tests/test_day_trading_runtime_micro_confirmation.py`
- `pytest -q /Users/hotovo/.gemini/antigravity/scratch/market_regime_detection/tests/test_day_trading_runtime_intrabar_indicator.py`
- `PYTHONPATH=/Users/hotovo/.gemini/antigravity/scratch/market_regime_detection pytest -q /Users/hotovo/.gemini/antigravity/scratch/market_regime_detection/tests/test_liquidity_sweep_detection.py`
- `pytest -q /Users/hotovo/.gemini/antigravity/scratch/market_regime_detection/tests/test_intraday_levels_entry_quality_gate.py`
- Domain smoke:
- `pytest -q tests/test_execution_realism.py`
- `pytest -q /Users/hotovo/.gemini/antigravity/scratch/market_regime_detection/tests/test_trading_orchestrator_reset.py /Users/hotovo/.gemini/antigravity/scratch/market_regime_detection/tests/test_checkpoint.py`
- Required BMAD verification:
- `python3 scripts/generate_context_pack.py`
- `python3 scripts/validate_llm_context.py`
- `python3 scripts/validate_llm_context.py --strict`

## Contract Deltas
- Planovana delta API kontraktov: `none`.
- Interna delta:
- runtime internals budu modularne, ale verejne `DayTradingManager` delegacne metody ostanu kompatibilne.

## Rizika
- Tiche regresie v shape metadata payloadov (`signal_rejected`, `position_closed`, `level_context`).
- Import cycle riziko medzi novymi runtime modulmi a managerom.
- Performance regresia pri nadmernom kopirovani dict payloadov.

## Mitigacie
- Golden-path payload testy pre 3 hlavne vetvy:
- `signal_queued`
- `signal_rejected`
- `position_closed_*`
- Keep-facade approach: ziadny caller nebude importovat nove moduly priamo.
- Po kazdej faze spustit iba relevantny subset testov + final full domain gate.

## Definition of Done
- `day_trading_runtime_impl.py` je facade (bez 1000+ riadkovych metod).
- `runtime_process_trading_bar` a `runtime_evaluate_intraday_levels_entry_quality` su rozbite na male testovatelne celky.
- Ziadna zmena kritickych invariantov (no-lookahead, no same-bar execution).
- Vsetky uvedene gating testy prejdu.
- BMAD context pack je aktualizovany a validovany.
