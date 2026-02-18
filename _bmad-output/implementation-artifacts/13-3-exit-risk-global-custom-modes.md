# 13-3 Exit/Risk Global-Custom Modes

## Scope
- Add per-strategy `exit_mode` and `risk_mode` (`custom|global`)
- Keep `trailing_stop_mode` backward-compatible as alias to `exit_mode`
- Group global exit/risk defaults in modules and fanout to strategy API at run start

## Backend
- Strategy engine (`market_regime_detection`):
  - `BaseStrategy` resolves effective exit/risk params from `global_*` vs local params
  - Strategies use effective values for RR/ATR/volume/min-stop computations
  - `/api/strategies/update` supports `exit_mode`, `risk_mode`, and global `exit/risk` params
- Runner (`backtest-runner`):
  - `StartRunRequest` supports global module fields:
    - `global_exit_rr_ratio`
    - `global_risk_atr_stop_multiplier`
    - `global_risk_volume_stop_pct`
    - `global_risk_min_stop_loss_pct`
  - `resolve_execution_config` resolves effective values + sources from request/positioning/adaptive profile
  - Global strategy fanout sends trailing + exit/risk baselines to all strategies

## Frontend
- `RunConfig`: new global module fields under stop/risk panel and run payload
- `StrategySettings`: per-strategy `Exit Source` + `Risk Source` selectors
- `AdaptiveStrategyStudio`: new module fields for global exit/risk baselines
- UI terminology updated to `Global Modules`

## Tests
- Strategy engine tests cover global/custom exit+risk behavior and API update handling
- Runner tests cover global fanout payload and execution-config resolution of new fields
