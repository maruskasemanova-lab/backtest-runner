# Anti-Lookahead Refactor Plan

## Ciel

Odstranit exekucny a intrabar look-ahead bias z pipeline:

- `backtest-runner` (feed/orchestracia)
- `market_regime_detection` (signal + exekucia)
- optimizer/reporting vrstva

Plan je navrhnuty tak, aby bol implementovatelny po moduloch a overitelny testami.

## Aktualne P0/P1 problemy (kde vznikne bias)

1. Signal sa generuje z kompletneho baru `t` a vstup sa plni na close toho isteho baru.
- `../market_regime_detection/src/day_trading_manager.py:652`
- `../market_regime_detection/src/day_trading_manager.py:667`
- `../market_regime_detection/src/day_trading_manager.py:1249`
- `../market_regime_detection/src/day_trading_manager.py:1396`

2. Trailing stop sa updatne z close a hned sa v tom istom bare testuje intrabar low/high.
- `../market_regime_detection/src/day_trading_manager.py:1013`
- `../market_regime_detection/src/day_trading_manager.py:1017`
- `../market_regime_detection/src/day_trading_manager.py:1032`

3. Pri stop/TP triggeri je fill na `bar.close`, nie na trigger cene.
- `../market_regime_detection/src/day_trading_manager.py:1039`
- `../market_regime_detection/src/day_trading_manager.py:1046`
- `../market_regime_detection/src/day_trading_manager.py:1052`
- `../market_regime_detection/src/day_trading_manager.py:1412`

4. V jednom bare sa vie pozicia zavriet aj znovu otvorit.
- `../market_regime_detection/src/day_trading_manager.py:1052`
- `../market_regime_detection/src/day_trading_manager.py:1102`
- `../market_regime_detection/src/day_trading_manager.py:1179`

5. WFO cast pracuje s `selected_strategy="adaptive"` namiesto realne obchodovanej strategie.
- `../market_regime_detection/src/day_trading_manager.py:622`
- `wfo_optimizer.py:221`
- `wfo_optimizer.py:294`

## Target event model (bez look-ahead)

Pre kazdy bar `t`:

1. `OPEN(t)`: spracuj pending vstup z baru `t-1`.
2. `INTRABAR(t)`: vyhodnot vystupy pre existujuce pozicie (SL/TP/trailing) podla jasneho fill pravidla.
3. `CLOSE(t)`: vypocitaj signal na zaklade dat po `CLOSE(t)` a vytvor `pending order` na `OPEN(t+1)`.

Zakladne pravidla:

- signal nikdy neotvara obchod v tom istom bare
- trailing update je efektivny az od dalsieho baru
- v jednom bare maximalne jedna transakcia na stranu (zabranit close+reopen)

## Modulove zmeny

### 1) DayTradingManager (core exekucia)

Subor:
- `../market_regime_detection/src/day_trading_manager.py`

Pridat datove struktury:

- `PendingOrder`:
  - `created_at_bar_index`
  - `side`
  - `strategy`
  - `signal_price`
  - `stop_loss`
  - `take_profit`
  - `trailing_stop_pct`
  - `metadata`
- `ExecutionConfig`:
  - `signal_execution_mode`: `NEXT_BAR_OPEN`
  - `intrabar_fill_mode`: `CONSERVATIVE`
  - `trailing_update_mode`: `CLOSE_TO_NEXT_BAR`
  - `allow_same_bar_reentry`: `False`

Refactor `_process_trading_bar` na 3 kroky:

1. `_apply_pending_entry_at_open(session, bar, timestamp)`
2. `_process_intrabar_exits(session, bar, timestamp)`
3. `_evaluate_close_and_queue_signal(session, bar, timestamp)`

Detail pravidiel:

- Entry fill:
  - cena: `bar.open`
  - reason: `signal_from_prev_bar`
- Exit fill:
  - pri SL: fill na `stop_loss` (plus slippage model)
  - pri TP: fill na `take_profit` (plus slippage model)
  - ak SL aj TP v jednom bare: konzervativny tie-break (pre long preferuj SL)
- Trailing:
  - update trailing stavu na `CLOSE(t)`, aktivny od `t+1`
- Reentry guard:
  - ak sa v bare pozicia zavrie, nova sa v tom istom bare neotvori

### 2) Session summary a Trade payload

Subor:
- `../market_regime_detection/src/day_trading_manager.py`

Rozsirit `DayTrade` metadata:

- `entry_bar_index`
- `exit_bar_index`
- `entry_fill_type` (`open_next_bar`, `manual`, ...)
- `exit_fill_type` (`stop`, `target`, `eod`, ...)
- `entry_signal_bar_index`

Ciel:
- auditovatelnost a dokazatelna causalita (`signal_bar < entry_bar`)

### 3) Signal generation boundary

Subory:
- `../market_regime_detection/src/day_trading_manager.py`
- `../market_regime_detection/src/multi_layer_decision.py`
- strategie v `../market_regime_detection/src/strategies/*.py`

Pravidlo:
- signal computation pouziva data po `CLOSE(t)`, ale exekucia je az na `OPEN(t+1)`.
- ziadna cast signalu nesmie mat pristup k baru `t+1`.

### 4) Friday/day filter governance

Subor:
- `../market_regime_detection/src/day_trading_manager.py`

Odstranit hardcoded `No Fridays` default.
- dnes: `../market_regime_detection/src/day_trading_manager.py:490`
- target: iba config-driven (`avoid_days`) alebo explicitny runner filter.

### 5) WFO consistency

Subor:
- `wfo_optimizer.py`

Namiesto porovnania `selected_strategy` pouzit skutocne obchodovane strategie z `session.trades`.

Target scoring:
- hodnotit iba obchody patriace k testovanej strategii
- oddelit `strategy_selected_label` od `executed_trade_strategy`

## Test plan (acceptance)

### Unit testy (market_regime_detection)

1. `test_signal_executes_on_next_bar_open`
- Given signal na bare `t`
- Expect entry na `open(t+1)` a nie `close(t)`

2. `test_no_same_bar_close_and_reopen`
- Given exit trigger v bare `t`
- Expect ziadna nova pozicia v tom istom bare

3. `test_trailing_update_applies_next_bar_only`
- Given trailing update na close `t`
- Expect intrabar trigger v `t` sa nevyhodnocuje s novym trailingom

4. `test_stop_and_target_same_bar_uses_conservative_tie_break`
- Given bar kde pre long plati `low <= stop` aj `high >= target`
- Expect exit `stop_loss`

5. `test_trade_audit_fields_are_causal`
- `entry_signal_bar_index < entry_bar_index <= exit_bar_index`

### Integration testy (backtest-runner + strategy API)

1. `test_single_day_causality`
- replay fixnej sady barov
- assert:
  - no same-bar entry from fresh signal
  - no same-bar reentry po close

2. `test_summary_consistency`
- suma trade PnL == session summary PnL (tolerancia pre rounding)

3. `test_time_and_day_filters`
- pri `avoid_days=["Friday"]` sa Friday netraduje
- bez `avoid_days` Friday bezi normalne

### Optimizer testy

1. `test_wfo_scores_by_executed_trade_strategy`
- synthetic session s `selected_strategy="adaptive"` a trade-mi z roznych strategii
- scorer musi pocitat iba cieleny strategy subset

## Rollout plan

Faza 1:
- zaviest `ExecutionConfig` a novy event loop za feature flagom
- default nech je stary rezim, aby sa nerozbili stare reporty

Faza 2:
- doplnit unit + integration testy
- porovnat old/new na rovnakom datasete

Faza 3:
- prepnúť default na `NEXT_BAR_OPEN`
- ponechat fallback flag pre rychly rollback

Faza 4:
- upravit WFO scoring na executed-trade strategy
- regenerovat `strategy_overrides.json` z clean WFO

## Definition of done

Hotovo je az ked:

1. ziadny test neukaze same-bar entry z noveho signalu
2. trailing/SL/TP poradie je deterministicke a zdokumentovane
3. WFO nehodnoti `adaptive` label ako realnu strategiu
4. 3-mesacny OOS replay bezi bez mock fallbacku a je reprodukovatelny
5. trade log obsahuje audit polia pre causal check
