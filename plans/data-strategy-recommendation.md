# Odporúčaná dátová stratégia

## Záver z analýzy

Máš **kvalitné OHLCV 1-minútové dáta** z Databento (Nasdaq TotalView-ITCH) pre 8 tickery (AAPL, AMD, AMZN, GOOGL, META, MSFT, NVDA, TSLA) za 6 mesiacov. L2 dáta máš iba **obmedzene** (niektoré dni v Lean formáte + live cez IBKR).

---

## Odporúčaný prístup: "OHLCV First, L2 Later"

### Fáza 1: OHLCV 1m Backtesting (Teraz)

**Použi**: Databento OHLCV 1-minútové dáta

**Prečo**:

- ✅ Máš 6 mesiacov histórie pre všetky tickery
- ✅ Vysoká kvalita (Nasdaq TotalView-ITCH)
- ✅ Rýchla iterácia stratégií
- ✅ Postačuje pre väčšinu stratégií

**Implementácia**:

```python
# Už existuje v data_loader.py
from data_loader import DataLoader

loader = DataLoader("/Users/hotovo/.gemini/antigravity/scratch/ibkr-l2-script/databento_data")
df = loader.load_csv("NVDA_ohlcv-1m_2025-08-01_2026-01-28.csv")
day_df = loader.filter_trading_day(df, "2026-01-27")
```

**Vhodné stratégie**:

- Regime detection (trending/choppy)
- Mean reversion
- Pullback trading
- VWAP strategies
- Gap trading
- Momentum

---

### Fáza 2: L2 Enrichment (Voliteľné)

**Použi**: L2 dáta pre vybrané dni kde sú dostupné

**Prečo**:

- Lepšie porozumenie liquidity
- Detekcia support/resistance "walls"
- Order flow confirmation

**Obmedzenia**:

- Nemáš L2 pre všetky dni
- Necelé dáta = skreslené výsledky
- Komplexnejšia implementácia

**Kedy použiť**:

- Ak máš L2 pre konkrétny deň, urob dodatočnú analýzu
- Porovnaj L2 vs OHLCV výsledky
- Zisti či L2 pridáva hodnotu

**Implementácia**:

```python
# Pre dni kde máš L2 dáta
from check_l2_data import check_data

# Analýza L2 štruktúry
check_data('GOOGL', '20251201')
```

---

### Fáza 3: Live L2 (Live Trading)

**Použi**: IBKR L2 cez `ib_insync`

**Prečo**:

- Real-time order book
- Live entry/exit confirmation
- Risk management

**Implementácia**:

```python
# Použi existujúci l2_viewer.py alebo analyze_l2_entry.py
from ib_insync import *

ib = IB()
ib.connect('127.0.0.1', 7497, clientId=1)
contract = Stock('NVDA', 'SMART', 'USD')
ticker = ib.reqMktDepth(contract, numRows=10, isSmartDepth=True)
# Analýza ticker.domBids a ticker.domAsks
```

---

## Konkrétne odporúčania

### Pre testovanie stratégií:

1. **Začni s OHLCV 1m**
   - Použi všetkých 6 mesiacov dát
   - Testuj na viacerých tickeroch
   - Rob walk-forward analýzu

2. **Fokus na kvalitu nie kvantitu**
   - Lepšie mať 6 mesiacov kvalitných OHLCV
   - Ako 10 dní L2 dát

3. **L2 ako enhancement nie core**
   - Core logika na OHLCV
   - L2 ako confirmation/filter

### Pre konkrétne stratégie:

| Stratégia        | Dátový typ           | Priorita   |
| ---------------- | -------------------- | ---------- |
| Regime detection | OHLCV 1m             | ⭐⭐⭐⭐⭐ |
| Mean reversion   | OHLCV 1m             | ⭐⭐⭐⭐⭐ |
| Pullback         | OHLCV 1m             | ⭐⭐⭐⭐⭐ |
| VWAP             | OHLCV 1m + VWAP calc | ⭐⭐⭐⭐⭐ |
| Gap trading      | OHLCV 1m             | ⭐⭐⭐⭐⭐ |
| Order flow       | L2 (live)            | ⭐⭐⭐     |
| Scalping         | L2 (live)            | ⭐⭐⭐     |

---

## Čo stiahnuť/aktualizovať

### Aktuálne máš:

- ✅ 6 mesiacov OHLCV 1m (august 2025 - január 2026)
- ✅ 8 tickery
- ⚠️ Obmedzené L2 (niektoré dni)

### Odporúčam stiahnuť:

1. **Viac tickery** (ak potrebuješ diverzifikáciu)
2. **Novšie dáta** (február 2026+)
3. **Trades data** (ak chceš execution analýzu)

**Ako**:

```python
# Použi existujúci download_databento.py
from download_databento import download_recent_data

# Stiahni nové dáta
download_recent_data(['SPY', 'QQQ'], days=30, schema="ohlcv-1m")
```

---

## Štruktúra pre prácu s dátami

```
ibkr-l2-script/databento_data/
├── raw/                    # Originálne stiahnuté dáta
│   ├── AAPL_ohlcv-1m_...
│   ├── NVDA_ohlcv-1m_...
│   └── ...
├── processed/              # Preprocesované dáta
│   ├── consolidated.parquet
│   └── by_ticker/
├── l2/                     # L2 dáta (kde dostupné)
│   └── GOOGL/
│       └── 20251201_quote.zip
└── cache/                  # Cache pre rýchle načítavanie
```

---

## Zhrnutie

| Aspekt               | Odporúčanie               |
| -------------------- | ------------------------- |
| **Primárny zdroj**   | Databento OHLCV 1m        |
| **Sekundárny zdroj** | L2 (pre vybrané dni/live) |
| **Formát**           | CSV/Parquet               |
| **Granularita**      | 1-minútové bary           |
| **História**         | 6+ mesiacov               |
| **Tickery**          | 8+ (pridaj podľa potreby) |

**Kľúčová správa**: Máš dostatok kvalitných dát pre testovanie. Nepotrebuješ sťahovať L2 históriu - OHLCV 1m postačuje pre väčšinu stratégií. L2 používaj len pre live trading alebo špecifické analýzy.
