# Analýza existujúcej architektúry

## Súhrn 3 repozitárov

### 1. `bmad-backtest-lite` (LEAN Backtest Engine)

- **Účel**: Lean engine backtesting - spúšťa backtesty cez LEAN engine
- **Technológia**: Python s QCAlgorithm (QuantConnect LEAN framework)
- **Kľúčové komponenty**:
  - `TurekSniperPortfolio` - orchestrátor multi-asset stratégií
  - `SniperStrategy` - hlavná obchodná stratégia (Admiral, Gap Theory, Volume Profile)
  - `TurekSwingContext` - swing analýza
  - `TurekGapContext` - gap analýza
  - `TurekValueArea` - volume profile analýza
  - `TurekRecorder` - záznam obchodov pre replay
- **Problém**: Je to LEAN-specific, ťažko použiteľné pre rýchle testovanie nových prístupov

### 2. `market_regime_detection` (Strategy Evaluator)

- **Účel**: Detekcia trhového režimu a výber stratégie
- **Technológia**: FastAPI + Python
- **Kľúčové komponenty**:
  - `StrategyEngine` - orchestrátor stratégií
  - `DayTradingManager` - session-based manažment
  - Viacero stratégií: MeanReversion, Pullback, Momentum, Rotation, VWAPMagnet
  - `TrailingStopManager` - riadenie stop-lossov
- **API**: Port 8001, poskytuje `/api/state`, `/api/regime`, session endpoints

### 3. `backtest-runner` (Unified Backtest Runner)

- **Účel**: Walk-forward backtesting s vizualizáciou
- **Technológia**: FastAPI + React + WebSocket
- **Kľúčové komponenty**:
  - `DataLoader` - načítavanie CSV/Parquet dát z databento
  - `SessionRunner` - orchestrácia bar-by-bar feedovania
  - `DecisionTracker` - trackovanie rozhodnutí s vysvetleniami
  - `api_server.py` - FastAPI server na porte 8002
  - Frontend - TradingView chart s playback controls
- **API**: Port 8002, WebSocket `/ws/live`

## Aktuálny dátový tok

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Trading Data   │────▶│  Backtest Runner │────▶│ Strategy API    │
│  (CSV/Parquet)  │     │    (port 8002)   │     │  (port 8001)    │
└─────────────────┘     └────────┬─────────┘     └─────────────────┘
                                 │
                                 │ WebSocket
                                 ▼
                        ┌─────────────────┐
                        │    Frontend     │
                        │  (port 5173)    │
                        └─────────────────┘
```

## Identifikované medzery a problémy

### 1. **Chýbajúci spojovací interface**

- `bmad-backtest-lite` používa LEAN engine a nie je kompatibilný s `backtest-runner` architektúrou
- Stratégie v `bmad-backtest-lite` sú napísané pre QCAlgorithm, nie pre `StrategyEngine`
- Nie je jasné, ako prepojiť LEAN backtesty s vizualizáciou v `backtest-runner`

### 2. **Duplicitná logika**

- `SniperStrategy` v `bmad-backtest-lite` má vlastnú implementáciu:
  - Regime detection (cez `TurekSwingContext`)
  - Gap analýzu (`TurekGapContext`)
  - Volume Profile (`TurekValueArea`)
- `market_regime_detection` má vlastné stratégie a regime detection
- Nie je jasné, ktorý prístup je "zdroj pravdy"

### 3. **Nejednotné API**

- `bmad-backtest-lite` generuje `replay_log.json` súbory
- `backtest-runner` očakáva real-time WebSocket komunikáciu
- `market_regime_detection` má REST API
- Žiadny štandardizovaný formát pre výmenu dát

### 4. **Problém s testovaním**

- Nové prístupy sa musia implementovať v LEAN frameworku (komplexné)
- Alebo sa musia duplikovať do `market_regime_detection`
- Chýba jednoduchý spôsob ako rýchlo otestovať novú stratégiu

## Otázky na zváženie

1. **Máš v pláne používať LEAN engine (`bmad-backtest-lite`) spolu s `backtest-runner`?**
   - Ak áno, potrebujeme adapter/bridge
   - Ak nie, `bmad-backtest-lite` môže ostať ako legacy/LEAN-specific

2. **Ktoré stratégie sú prioritné?**
   - `SniperStrategy` (Turek) z `bmad-backtest-lite`?
   - Stratégie z `market_regime_detection` (MeanReversion, Pullback, atď.)?
   - Oboje?

3. **Aký je cieľ testovania?**
   - Porovnávať rôzne stratégie medzi sebou?
   - Vizualizovať existujúce LEAN backtesty?
   - Rýchlo iterovať nové prístupy?

## Možné riešenia

### Riešenie A: Nový interface repo (Strategy Adapter)

Vytvoriť 4. repo ktorý:

- Štandardizuje interface medzi `backtest-runner` a stratégiami
- Umožňuje plug-in architektúru pre rôzne stratégie
- Prekládá medzi `SniperStrategy` (LEAN) a `StrategyEngine` formátmi

### Riešenie B: Rozšíriť `market_regime_detection`

- Pridať podporu pre `SniperStrategy` logiku
- Urobiť ho hlavným "strategy providerom"
- `backtest-runner` zostáva ako orchestrátor + vizualizácia

### Riešenie C: Rozšíriť `backtest-runner`

- Pridať priamu podporu pre stratégie (bez `market_regime_detection`)
- Implementovať `SniperStrategy` priamo v `backtest-runner`
- Jednoduchšie, ale menej modulárne

### Riešenie D: LEAN Export/Import

- `bmad-backtest-lite` exportuje výsledky do štandardného formátu
- `backtest-runner` importuje a vizualizuje
- Žiadny real-time, iba post-hoc analýza
