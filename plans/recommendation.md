# Odporúčanie: Ako použiť existujúcu architektúru

## Verdikt: **NIE**, nepotrebuješ vytvárať nové repo

Existujúca architektúra `backtest-runner` + `market_regime_detection` už poskytuje všetko potrebné pre testovanie stratégií. Potrebuješ len **jasne definovať, ktoré stratégie chceš testovať**.

---

## Prečo nové repo NIE JE potrebné

### 1. `backtest-runner` už JE ten interface

- `backtest-runner` funguje ako orchestrátor medzi dátami a stratégiami
- `SessionRunner` poskytuje bar-by-bar feedovanie
- `DecisionTracker` trackuje všetky rozhodnutia
- WebSocket poskytuje real-time vizualizáciu

### 2. `market_regime_detection` už má stratégie

- 5 rôznych stratégií (MeanReversion, Pullback, Momentum, Rotation, VWAPMagnet)
- Regime detection
- Trailing stop management
- Session-based trading

### 3. Problém nie je v architektúre, ale v obsahu

- `bmad-backtest-lite` (LEAN) je **oddelený svet** - tam sú Turek stratégie
- `market_regime_detection` má **iné** stratégie
- Ak chceš testovať Turek stratégie, musíš ich **portnúť** do `market_regime_detection` formátu

---

## Čo potrebuješ urobiť

### Ak chceš testovať existujúce stratégie v `market_regime_detection`:

**Už to máš hotové!** Stačí spustiť:

```bash
# Terminal 1: Strategy Evaluator
cd /Users/hotovo/.gemini/antigravity/scratch/market_regime_detection
python -m uvicorn api_server:app --port 8001 --reload

# Terminal 2: Backtest Runner
cd /Users/hotovo/.gemini/antigravity/scratch/backtest-runner
python -m uvicorn api_server:app --port 8002 --reload

# Terminal 3: Frontend
cd /Users/hotovo/.gemini/antigravity/scratch/backtest-runner/frontend
npm run dev
```

### Ak chceš testovať Turek/Sniper stratégie:

**Potrebuješ portnúť** `SniperStrategy` logiku z `bmad-backtest-lite` do `market_regime_detection` formátu:

1. Vytvoriť novú stratégiu v `market_regime_detection/src/strategies/sniper_strategy.py`
2. Implementovať `BaseStrategy` interface
3. Pridať do `StrategyEngine` v `market_regime_detection`

### Ak chceš rýchlo testovať nové prístupy:

**Použi `market_regime_detection` ako framework**:

1. Vytvor nový súbor v `market_regime_detection/src/strategies/moja_strategia.py`
2. Dediť z `BaseStrategy`
3. Implementovať `generate_signal()` metódu
4. Pridať do `StrategyEngine.strategies` dict

---

## Odporúčaná štruktúra pre testovanie

```
market_regime_detection/
├── src/
│   ├── strategies/
│   │   ├── base_strategy.py          # Interface
│   │   ├── mean_reversion.py         # Existujúca
│   │   ├── pullback.py               # Existujúca
│   │   ├── momentum.py               # Existujúca
│   │   ├── rotation.py               # Existujúca
│   │   ├── vwap_magnet.py            # Existujúca
│   │   ├── sniper_strategy.py        # NOVÉ: Turek Sniper
│   │   └── experimental/             # NOVÉ: Adresár pre experimenty
│   │       ├── sniper_v2.py
│   │       ├── gap_based.py
│   │       └── ...
│   ├── strategy_engine.py            # Registruje všetky stratégie
│   └── day_trading_manager.py        # Session management
```

---

## Kedy by si MOHOL potrebovať nové repo

Nové repo by malo zmysel len ak:

1. **Chceš úplne iný prístup** - napr. reinforcement learning, genetic algorithms
2. **Chceš podporu pre iné jazyky** - napr. C++ stratégie, Rust engine
3. **Chceš distribuovaný systém** - viacero workerov, cloud deployment
4. **Chceš historickú kompatibilitu** - podpora starých LEAN backtest formátov

---

## Konkrétny akčný plán

### Pre rýchle testovanie nových prístupov:

1. **Použi existujúcu architektúru** (`backtest-runner` + `market_regime_detection`)
2. **Pridávaj nové stratégie** do `market_regime_detection/src/strategies/`
3. **Porovnávaj výsledky** cez `run_strategy_test.py` v `backtest-runner`

### Pre Turek stratégie:

1. **Portni `SniperStrategy`** z `bmad-backtest-lite` do `market_regime_detection` formátu
2. **Zachovaj** LEAN verziu pre porovnanie
3. **Porovnaj výsledky** medzi LEAN a novou implementáciou

### Pre LEAN-specific funkcionalitu:

1. **Ponechaj `bmad-backtest-lite`** ako LEAN engine
2. **Exportuj výsledky** do JSON formátu kompatibilného s `backtest-runner`
3. **Použi `backtest-runner`** iba pre vizualizáciu (post-hoc)

---

## Záver

**Nevytváraj nové repo.** Miesto toho:

- Rozšír `market_regime_detection` o nové stratégie
- Použi `backtest-runner` pre orchestráciu a vizualizáciu
- `bmad-backtest-lite` ponechaj ako LEAN-specific (voliteľné)

Táto architektúra ti umožní rýchlo iterovať nové prístupy bez zbytočného overheadu.
