# Finálny architektonický plán

## Záver z analýzy

**Nepotrebuješ vytvárať nové repo.** Existujúca architektúra `backtest-runner` + `market_regime_detection` je dostatočná pre testovanie stratégií.

---

## Odporúčaná architektúra

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         TESTING WORKFLOW                                │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────┐     ┌──────────────────┐     ┌─────────────────────┐
│  Data Source    │────▶│  Backtest Runner │────▶│  Strategy Engine    │
│  (Databento)    │     │   (Port 8002)    │     │   (Port 8001)       │
│                 │     │                  │     │                     │
│  CSV/Parquet    │     │  - SessionRunner │     │  - Regime Detection │
│                 │     │  - DataLoader    │     │  - Strategy Select  │
│                 │     │  - DecisionTrack │     │  - Risk Management  │
└─────────────────┘     └────────┬─────────┘     └─────────────────────┘
                                 │
                                 │ WebSocket
                                 │
                                 ▼
                        ┌─────────────────┐
                        │    Frontend     │
                        │  (Port 5173)    │
                        │                 │
                        │  - TradingView  │
                        │  - Playback     │
                        │  - Decisions    │
                        └─────────────────┘
```

---

## Štruktúra pre testovanie stratégií

### 1. `market_regime_detection` - Strategy Provider

```
market_regime_detection/
├── src/
│   ├── strategies/
│   │   ├── base_strategy.py          # Interface pre všetky stratégie
│   │   ├── mean_reversion.py         # Existujúca
│   │   ├── pullback.py               # Existujúca
│   │   ├── momentum.py               # Existujúca
│   │   ├── rotation.py               # Existujúca
│   │   ├── vwap_magnet.py            # Existujúca
│   │   ├── sniper/                   # NOVÉ: Turek Sniper port
│   │   │   ├── __init__.py
│   │   │   ├── sniper_strategy.py    # Hlavná stratégia
│   │   │   ├── swing_context.py      # Admiral logika
│   │   │   ├── gap_context.py        # Gap analýza
│   │   │   └── value_area.py         # Volume profile
│   │   └── experimental/             # NOVÉ: Rýchle experimenty
│   │       ├── __init__.py
│   │       └── [nové stratégie]
│   ├── strategy_engine.py            # Registruje všetky stratégie
│   └── day_trading_manager.py        # Session management
```

### 2. `backtest-runner` - Orchestrator & Visualizer

Už existuje, žiadne zmeny nie sú potrebné:

- `SessionRunner` - feedovanie barov
- `DecisionTracker` - trackovanie rozhodnutí
- `api_server.py` - FastAPI
- Frontend - vizualizácia

### 3. `bmad-backtest-lite` - LEAN Engine (Voliteľné)

Ponechať ako LEAN-specific riešenie:

- Pre finálne backtesty cez LEAN
- Export výsledkov do JSON
- Porovnanie s `market_regime_detection` výsledkami

---

## Workflow pre testovanie novej stratégie

### Krok 1: Vytvoriť stratégiu v `market_regime_detection`

```python
# market_regime_detection/src/strategies/experimental/my_strategy.py

from ..base_strategy import BaseStrategy, Signal, SignalType

class MyStrategy(BaseStrategy):
    """Moja experimentálna stratégia."""

    def __init__(self):
        super().__init__("my_strategy")
        # Inicializácia

    def generate_signal(self, data, context):
        # Logika stratégie
        if condition:
            return Signal(
                type=SignalType.ENTRY_LONG,
                price=data['close'],
                confidence=0.8,
                reason="Môj dôvod"
            )
        return None
```

### Krok 2: Registrovať v `StrategyEngine`

```python
# V strategy_engine.py pridať:
from .strategies.experimental.my_strategy import MyStrategy

self.strategies = {
    # ... existujúce stratégie
    'my_strategy': MyStrategy(),
}
```

### Krok 3: Spustiť test

```bash
# 1. Strategy Evaluator
cd market_regime_detection
python -m uvicorn api_server:app --port 8001

# 2. Backtest Runner
cd backtest-runner
python -m uvicorn api_server:app --port 8002

# 3. Frontend
cd backtest-runner/frontend
npm run dev

# 4. Otvoriť http://localhost:5173
```

### Krok 4: Analyzovať výsledky

- Vizualizácia v prehliadači
- Report cez `run_strategy_test.py`
- Porovnanie s inými stratégiami

---

## Kedy použiť ktorý prístup

| Scenár                 | Použi                                                            |
| ---------------------- | ---------------------------------------------------------------- |
| Rýchly experiment      | `market_regime_detection` + `backtest-runner`                    |
| Nová stratégia         | Pridať do `market_regime_detection/src/strategies/experimental/` |
| Turek/Sniper stratégia | Portnúť do `market_regime_detection/src/strategies/sniper/`      |
| Finálny LEAN backtest  | `bmad-backtest-lite` (pôvodný)                                   |
| Porovnanie výsledkov   | Oba, export JSON, porovnanie                                     |

---

## Rozdiely medzi LEAN a novým prístupom

| Aspekt               | LEAN (`bmad-backtest-lite`)  | Nový prístup (`market_regime_detection`) |
| -------------------- | ---------------------------- | ---------------------------------------- |
| **Engine**           | QuantConnect LEAN            | Vlastný Python                           |
| **Broker simulácia** | Realistická (slippage, fill) | Zjednodušená                             |
| **Rýchlosť**         | Pomalšie (C# core)           | Rýchlejšie (pure Python)                 |
| **Iterácia**         | Pomalá (rebuild)             | Rýchla (hot reload)                      |
| **Vizualizácia**     | Obmedzená                    | Plná (TradingView)                       |
| **Vhodné pre**       | Finálne backtesty            | Rýchle experimenty                       |

---

## Odporúčané nasledujúce kroky

### Ak chceš začať okamžite:

1. Spusti existujúcu architektúru (3 terminály)
2. Otestuj s existujúcimi stratégiami
3. Pridaj novú stratégiu do `experimental/`

### Ak chceš Turek stratégie:

1. Portni `SniperStrategy` z `bmad-backtest-lite`
2. Implementuj `BaseStrategy` interface
3. Porovnaj výsledky s LEAN verziou

### Ak chceš len vizualizovať LEAN výsledky:

1. Uprav `TurekRecorder` v `bmad-backtest-lite` na export do `backtest-runner` formátu
2. Importuj do `backtest-runner` (post-hoc, nie real-time)
3. Vizualizuj

---

## Zhrnutie

**Nepotrebuješ nové repo.** Použi:

- `backtest-runner` ako orchestrátor a vizualizátor
- `market_regime_detection` ako strategy engine
- Rozšír `market_regime_detection` o nové stratégie podľa potreby

Táto architektúra ti dáva:

- ✅ Rýchlu iteráciu nových prístupov
- ✅ Plnú vizualizáciu s TradingView
- ✅ Jednoduché porovnávanie stratégií
- ✅ Čistý interface pre nové stratégie
- ✅ Zachovanie LEAN kompatibility (voliteľné)
