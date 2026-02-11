# Analýza projektu: Automatický obchodný systém

**Dátum analýzy:** 2026-02-11  
**Analyzované repozitáre:** `backtest-runner`, `market_regime_detection`

---

## 1. Executive Summary

Projekt je **dobre architektonicky štruktúrovaný** s jasným rozdelením zodpovedností medzi dva mikroslužby a frontend. Dokumentácia je na vysokej úrovni s explicitnými invariantmi a API kontraktmi. Existujú však oblasti, ktoré si vyžadujú pozornosť z hľadiska údržby a potenciálnych regresií.

### Celkové hodnotenie: **B+ (85/100)**

| Kategória     | Skóre | Poznámky                               |
| ------------- | ----- | -------------------------------------- |
| Architektúra  | A     | Jasné domény, dobrá separácia          |
| Dokumentácia  | A     | Výborná LLM-ready dokumentácia         |
| Kvalita kódu  | B     | Niekoľko oblastí na zlepšenie          |
| Test pokrytie | B+    | Dobré kritické testy, chýba integrácia |
| Čitateľnosť   | B     | Veľké súbory, komplexná logika         |
| Regresia      | B-    | Identifikované rizikové oblasti        |

---

## 2. Architektúra systému

### 2.1 Topológia

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Frontend (React)                             │
│                         Port 5173                                    │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────────────┐ │
│  │ RunConfig    │ │ Candlestick  │ │ AdaptiveStrategyStudio      │ │
│  │ PlaybackCtrl │ │ DecisionPanel│ │ AdaptiveTuner               │ │
│  └──────────────┘ └──────────────┘ └──────────────────────────────┘ │
└────────────────────────────┬────────────────────────────────────────┘
                             │ WebSocket + REST
┌────────────────────────────▼────────────────────────────────────────┐
│                    Backtest Runner API                               │
│                         Port 8002                                    │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────────────┐ │
│  │ api_server   │ │session_runner│ │ L2 Feature Service          │ │
│  │ data_loader  │ │decision_track│ │ Order Flow Engine           │ │
│  └──────────────┘ └──────────────┘ └──────────────────────────────┘ │
└────────────────────────────┬────────────────────────────────────────┘
                             │ HTTP POST /api/session/bar
┌────────────────────────────▼────────────────────────────────────────┐
│                   Strategy Engine API                                │
│                         Port 8001                                    │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────────────┐ │
│  │ day_trading  │ │ evidence_    │ │ Strategies (10+)            │ │
│  │ _manager     │ │ decision     │ │ momentum_flow, absorption,  │ │
│  │ orchestrator │ │ combiner     │ │ exhaustion_fade, etc.       │ │
│  └──────────────┘ └──────────────┘ └──────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 Doménové rozdelenie

Domény sú **správne definované** v [`bmad/context/component-map.json`](bmad/context/component-map.json):

1. **orchestration** - Run lifecycle, API contracts, data routing
2. **strategy-engine** - Regime detection, signal generation, position management
3. **data-l2** - L2 acquisition, minute alignment, flow-feature extraction
4. **optimization-validation** - Parameter search, walk-forward, OOS validation
5. **frontend** - Playback UI, chart rendering, diagnostics

---

## 3. Silné stránky projektu

### 3.1 Výborná dokumentácia

- **LLM-ready kontext** v [`docs/llm/`](docs/llm/) - funkčnostná mapa, API kontrakty, invarianty
- **AGENTS.md** s jasnými pravidlami pre AI asistentov
- **Generované kontextové balíčky** v `bmad/context/generated/`

### 3.2 Jasné invarianty

Definované v [`docs/llm/invariants-and-validation.md`](docs/llm/invariants-and-validation.md):

```python
# Kritické invarianty:
# - No-lookahead v bar processing, L2 features, decision logic
# - signal_bar_index < entry_bar_index (žiadna same-bar exekúcia)
# - comparable_mode vynucuje cold start
# - L2 sessionized metrics reset per market day
```

### 3.3 Dobre štruktúrované testy

- [`tests/test_no_lookahead.py`](tests/test_no_lookahead.py) - kritický invariant test
- [`tests/test_session_runner_markers.py`](tests/test_session_runner_markers.py) - marker schema
- [`tests/test_adaptive_tuner_api.py`](tests/test_adaptive_tuner_api.py) - tuner API

### 3.4 Separácia stratégií

Každá stratégia má vlastný súbor v [`market_regime_detection/src/strategies/`](../market_regime_detection/src/strategies/):

- [`base_strategy.py`](../market_regime_detection/src/strategies/base_strategy.py) - spoločné rozhranie
- [`momentum_flow.py`](../market_regime_detection/src/strategies/momentum_flow.py), [`absorption_reversal.py`](../market_regime_detection/src/strategies/absorption_reversal.py), [`exhaustion_fade.py`](../market_regime_detection/src/strategies/exhaustion_fade.py) - flow-aware stratégie

---

## 4. Identifikované problémy a riziká

### 4.1 🔴 Kritické: Veľkosť api_server.py

**Problém:** [`api_server.py`](api_server.py) má **>5000 riadkov** kódu.

**Dôsledky:**

- Ťažká navigácia a údržba
- Vysoká kognitívna záťaž pre vývojárov
- Zvýšené riziko regresie pri zmenách

**Odporúčanie:**

```
Rozdeliť na moduly:
- api_server.py (core routes, app setup)
- routes/run_routes.py (run lifecycle)
- routes/aos_routes.py (AOS config)
- routes/tuner_routes.py (adaptive tuner)
- routes/live_trader_routes.py (live monitoring)
- services/momentum_diversification.py (normalization logic)
```

### 4.2 🔴 Kritické: Duplicitná normalizácia timestampov

**Problém:** Timestamp normalizácia je implementovaná na viacerých miestach:

| Súbor                                                       | Funkcia              | Riadky  |
| ----------------------------------------------------------- | -------------------- | ------- |
| [`session_runner.py`](session_runner.py:127)                | `_to_utc_datetime()` | 127-138 |
| [`src/l2_feature_service.py`](src/l2_feature_service.py:25) | `to_utc_datetime()`  | 25-36   |
| [`api_server.py`](api_server.py:471)                        | `_parse_utc_iso()`   | 471-483 |

**Riziko:** Ak sa zmení logika v jednom mieste, ostatné môžu byť nekonzistentné.

**Odporúčanie:**

```python
# Vytvoriť src/time_utils.py
def normalize_to_utc(value: Any) -> datetime:
    """Single source of truth for timestamp normalization."""
    ...

def epoch_minute_key(value: Any) -> int:
    """Convert to UTC epoch minute key."""
    ...
```

### 4.3 🟡 Stredné: Komplexný stav v api_server.py

**Problém:** Globálny stav v [`api_server.py`](api_server.py:57-74):

```python
# Global State
data_loader = DataLoader()
l2_manager = L2DataManager()
l2_features = L2FeatureService(manager=l2_manager, logger=logger)
active_runners: Dict[str, SessionRunner] = {}
connected_clients: List[WebSocket] = []
databento_svc = DatabentoService()
adaptive_tuner_jobs: Dict[str, Dict[str, Any]] = {}
adaptive_tuner_slots = asyncio.Semaphore(MAX_PARALLEL_ADAPTIVE_TUNERS)
adaptive_tuner_merge_lock = asyncio.Lock()
```

**Riziko:** Ťažké testovanie, potenciálne race conditions.

**Odporúčanie:** Použiť dependency injection pattern alebo FastAPI's `app.state`.

### 4.4 🟡 Stredné: Chýbajúce typové anotácie

**Problém:** Niektoré funkcie majú nekompletné typové anotácie:

```python
# api_server.py - príklad
def _normalize_momentum_diversification_payload(
    raw: Any,  # ❌ Malo by byť Dict[str, Any]
    *,
    include_sleeves: bool = True,
) -> Optional[Dict[str, Any]]:
```

**Odporúčanie:** Pridať `mypy --strict` do CI pipeline.

### 4.5 🟡 Stredné: Frontend komponenty sú veľké

**Problém:** Frontend komponenty ako [`AdaptiveTuner.jsx`](frontend/src/components/AdaptiveTuner.jsx) a [`AdaptiveStrategyStudio.jsx`](frontend/src/components/AdaptiveStrategyStudio.jsx) sú komplexné.

**Odporúčanie:** Extrahovať pomocné funkcie do samostatných modulov:

```
frontend/src/utils/
  - formNormalization.js
  - csvParsing.js
  - apiClient.js
```

### 4.6 🟢 Nízke: TODO komentár v produkte

**Problém:** Jeden TODO v [`api_server.py:5765`](api_server.py:5765):

```python
# TODO: Optimize to avoid reloading if already in memory
l2_manager.load_data(ticker, start_date, end_date)
```

**Odporúčanie:** Založiť ticket/issue alebo odstrániť TODO.

---

## 5. Analýza regresných rizík

### 5.1 Vysoké riziko: API kontrakty medzi službami

**Kritická cesta:** `Runner API` → `Strategy API` → `Frontend`

Zmeny v nasledujúcich oblastiach môžu spôsobiť regresiu:

| Endpoint                 | Závislosti                                 | Riziko  |
| ------------------------ | ------------------------------------------ | ------- |
| `POST /api/session/bar`  | SessionRunner, DayTradingManager, Frontend | Vysoké  |
| `POST /api/run/start`    | RunConfig, AOS config, Strategy config     | Vysoké  |
| `GET /api/run/*/markers` | DecisionTracker, Frontend DecisionPanel    | Stredné |

**Mitigácia:** Pridať integračné testy medzi službami.

### 5.2 Stredné riziko: L2 feature schema

**Problém:** L2 feature keys sú definované na dvoch miestach:

1. [`session_runner.py:36-53`](session_runner.py:36) - `L2_PAYLOAD_KEYS`
2. [`src/l2_feature_service.py:109-132`](src/l2_feature_service.py:109) - feature bucket defaults

**Riziko:** Ak sa pridá/odstráni feature, musí sa aktualizovať na oboch miestach.

**Mitigácia:** Centralizovať definíciu do `src/l2_schema.py`.

### 5.3 Stredné riziko: Momentum diversification normalizácia

**Problém:** Komplexná normalizačná logika v [`api_server.py:123-260`](api_server.py:123) (`_normalize_momentum_diversification_payload`).

**Riziko:** Zmeny v schéme môžu ovplyvniť:

- Adaptive tuner
- Adaptive Strategy Studio
- Run config

**Mitigácia:** Extrahovať do samostatného modulu s testami.

---

## 6. Odporúčania

### 6.1 Krátkodobé (1-2 týždne)

1. **Vytvoriť `src/time_utils.py`** - centralizovať timestamp normalizáciu
2. **Pridať integračné testy** medzi Runner a Strategy API
3. **Extrahovať momentum diversification logiku** do samostatného modulu

### 6.2 Strednodobé (1-2 mesiace)

1. **Rozdeliť `api_server.py`** na menšie moduly
2. **Implementovať dependency injection** pre globálny stav
3. **Pridať `mypy --strict`** do CI

### 6.3 Dlhodobé (3+ mesiace)

1. **Vytvoriť L2 schema definíciu** ako single source of truth
2. **Implementovať kontraktové testy** pre API zmeny
3. **Refaktorovať frontend komponenty** do menších, testovateľných jednotiek

---

## 7. Záver

Projekt je **architektonicky zdravý** s výbornou dokumentáciou a jasnými invariantmi. Hlavné problémy sú v oblastiach:

1. **Veľkosť hlavného API súboru** - potrebné rozdelenie
2. **Duplicitná logika** - timestamp normalizácia, L2 schema
3. **Globálny stav** - potrebné dependency injection

Tieto problémy **nespôsobujú okamžité regresie**, ale zvyšujú technický dlh a riziko budúcich chýb. Odporúčam postupnú refaktorizáciu podľa prioritizovaného zoznamu vyššie.

---

## 8. Príloha: Zoznam analyzovaných súborov

### Backend (backtest-runner)

- [`api_server.py`](api_server.py) - hlavné API
- [`session_runner.py`](session_runner.py) - session orchestrácia
- [`data_loader.py`](data_loader.py) - načítanie dát
- [`decision_tracker.py`](decision_tracker.py) - tracking rozhodnutí
- [`performance_tracker.py`](performance_tracker.py) - tracking výkonnosti
- [`wfo_optimizer.py`](wfo_optimizer.py) - walk-forward optimalizácia
- [`oos_validator.py`](oos_validator.py) - out-of-sample validácia
- [`src/l2_feature_service.py`](src/l2_feature_service.py) - L2 features
- [`src/l2_data_manager.py`](src/l2_data_manager.py) - L2 data management
- [`src/order_flow_engine.py`](src/order_flow_engine.py) - order flow analýza

### Strategy Engine (market_regime_detection)

- [`src/day_trading_manager.py`](../market_regime_detection/src/day_trading_manager.py) - session manager
- [`src/evidence_decision.py`](../market_regime_detection/src/evidence_decision.py) - decision engine
- [`src/ensemble_combiner.py`](../market_regime_detection/src/ensemble_combiner.py) - ensemble logic
- [`src/trading_orchestrator.py`](../market_regime_detection/src/trading_orchestrator.py) - orchestrácia
- [`src/strategies/*.py`](../market_regime_detection/src/strategies/) - jednotlivé stratégie

### Frontend

- [`frontend/src/App.jsx`](frontend/src/App.jsx) - hlavná aplikácia
- [`frontend/src/components/AdaptiveTuner.jsx`](frontend/src/components/AdaptiveTuner.jsx) - tuner UI
- [`frontend/src/components/AdaptiveStrategyStudio.jsx`](frontend/src/components/AdaptiveStrategyStudio.jsx) - strategy studio
- [`frontend/src/components/DecisionPanel.jsx`](frontend/src/components/DecisionPanel.jsx) - decision vizualizácia

### Testy

- [`tests/test_no_lookahead.py`](tests/test_no_lookahead.py) - kritický invariant test
- [`tests/test_session_runner_markers.py`](tests/test_session_runner_markers.py) - marker tests
- [`tests/test_adaptive_tuner_api.py`](tests/test_adaptive_tuner_api.py) - tuner API tests
- [`tests/test_l2_feature_aggregator.py`](tests/test_l2_feature_aggregator.py) - L2 tests
