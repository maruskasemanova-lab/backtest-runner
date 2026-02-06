# Domain: Flow Strategy Engine

**ID:** `strategy-engine`

## Mission

Own regime detection, signal generation, position management, and execution realism.

## Depends On

- `orchestration`
- `data-l2`

## Entrypoints

- `../market_regime_detection/api_server.py`
- `../market_regime_detection/src/day_trading_manager.py`

## File Inventory

| File | Exists | Lines | Last Commit |
|---|---:|---:|---|
| `../market_regime_detection/api_server.py` | yes | 653 | `7e5a643 2026-02-06` |
| `../market_regime_detection/src/day_trading_manager.py` | yes | 2789 | `7e5a643 2026-02-06` |
| `../market_regime_detection/src/multi_layer_decision.py` | yes | 302 | `081b3fa 2026-02-06` |
| `../market_regime_detection/src/strategy_factory.py` | yes | 35 | `7e5a643 2026-02-06` |
| `../market_regime_detection/src/strategies/base_strategy.py` | yes | 281 | `1876ce2 2026-02-05` |
| `../market_regime_detection/src/strategies/momentum_flow.py` | yes | 161 | `081b3fa 2026-02-06` |
| `../market_regime_detection/src/strategies/absorption_reversal.py` | yes | 163 | `081b3fa 2026-02-06` |
| `../market_regime_detection/src/strategies/exhaustion_fade.py` | yes | 163 | `081b3fa 2026-02-06` |

## Change Checks

- No same-bar signal execution (signal bar index must be < entry bar index).
- Risk/execution changes must be reflected in config endpoints and tests.
- Keep flow metrics no-lookahead (past/current bars only).

## Prompt Primer

Load this file plus `bmad/context/generated/00-index.md`, then keep edits scoped to the file inventory unless interface changes are explicitly required.
