# Analýza dostupných dát

## Prehľad dátových zdrojov

### 1. Databento dáta (Používané v `backtest-runner`)

**Lokalita**: `/Users/hotovo/.gemini/antigravity/scratch/ibkr-l2-script/databento_data/`

**Formát**: OHLCV 1-minútové dáta z Nasdaq TotalView-ITCH (XNAS.ITCH)

**Dostupné tickery**:

- AAPL, AMD, AMZN, GOOGL, META, MSFT, NVDA, TSLA
- Dátumové rozsahy: 2025-08-01 až 2026-01-28
- Niektoré majú aj kratšie rozsahy (napr. 2025-12-29 až 2026-01-28)

**Štruktúra CSV súborov**:

```csv
ts_event,rtype,publisher_id,instrument_id,open,high,low,close,volume,symbol
2025-08-01 08:00:00+00:00,33,2,11667,174.49,175.0,174.08,174.2,12597,NVDA
```

**Časové pásmo**: UTC (08:00 = 3:00 AM ET pre-market)

**Kvalita**:

- ✅ Vysoká presnosť (Nasdaq TotalView-ITCH)
- ✅ Obsahuje pre-market dáta (od 4:00 AM ET)
- ✅ 1-minútová granularita
- ❌ Iba OHLCV (žiadne L2/depth dáta)

---

### 2. L2 (Level 2) dáta - IBKR/Lean

**Lokalita**: `/Users/hotovo/.gemini/antigravity/scratch/bmad-trading/Data/equity/usa/tick/`

**Formát**: Quote dáta (bid/ask/veľkosť) v ZIP súboroch

**Štruktúra**:

```csv
timestamp,bid,bid_size,ask,ask_size,exchange,cond1,cond2
090000000,15000,100,15001,200,N,0,0
```

**Použitie v kóde**:

- [`check_l2_data.py`](/Users/hotovo/.gemini/antigravity/scratch/ibkr-l2-script/check_l2_data.py:1) - analýza L2 dát
- [`l2_viewer.py`](/Users/hotovo/.gemini/antigravity/scratch/ibkr-l2-script/l2_viewer.py:1) - live L2 z IBKR
- [`analyze_l2_entry.py`](/Users/hotovo/.gemini/antigravity/scratch/ibkr-l2-script/analyze_l2_entry.py:1) - entry analýza cez L2

**Kvalita**:

- ✅ Order book depth (top 10-20 levels)
- ✅ Bid/ask veľkosti
- ✅ Real-time (cez IBKR API)
- ❌ Historické L2 dáta sú obmedzené (len niektoré dni)
- ❌ Vyžaduje IBKR subscription

---

### 3. Live dáta z IBKR

**Použitie**:

- [`l2_viewer.py`](/Users/hotovo/.gemini/antigravity/scratch/ibkr-l2-script/l2_viewer.py:1) - live order book
- [`analyze_l2_entry.py`](/Users/hotovo/.gemini/antigravity/scratch/ibkr-l2-script/analyze_l2_entry.py:1) - live entry analýza

**Dostupné**:

- Market depth (L2)
- Tick-by-tick data
- Real-time quotes

**Obmedzenia**:

- Iba live (nie historické)
- Vyžaduje pripojenie k TWS/Gateway
- Rate limiting

---

## Porovnanie dátových typov

| Typ           | Zdroj     | Formát      | Použitie     | Kvalita    |
| ------------- | --------- | ----------- | ------------ | ---------- |
| **OHLCV 1m**  | Databento | CSV/Parquet | Backtesting  | ⭐⭐⭐⭐⭐ |
| **L2 Quotes** | IBKR/Lean | ZIP/CSV     | Analýza      | ⭐⭐⭐     |
| **Live L2**   | IBKR API  | Real-time   | Live trading | ⭐⭐⭐⭐   |
| **Trades**    | Databento | CSV         | Execution    | ⭐⭐⭐⭐⭐ |

---

## Máš L2 dáta? Áno, ale...

### Čo máš:

1. **Historické OHLCV 1m** - Databento (kvalitné, ale bez depth)
2. **Historické L2 quotes** - Lean format (obmedzené, niektoré dni)
3. **Live L2** - IBKR API (pre live trading)

### Čo NEMÁŠ:

1. **Historické L2 tick dáta** - Pre backtesting s order book
2. **Trades data** - Individual executions (nie sú k dispozícii)
3. **Full market depth history** - Top 10-20 levels historicky

---

## Oplatí sa používať L2 dáta?

### Pre backtesting: **Čiastočne**

**Výhody L2**:

- Lepšie porozumenie liquidity
- Detekcia support/resistance levels (walls)
- Order flow analýza
- Presnejšie entry/exit simulácie

**Nevýhody**:

- Obmedzená história (nemáš L2 pre všetky dni)
- Komplexita implementácie
- Necelé dáta = skreslené výsledky

### Odporúčanie:

**Fáza 1: OHLCV 1m (teraz)**

- Použi Databento dáta
- Otestuj stratégie na 1m granularite
- Rýchla iterácia

**Fáza 2: Enrich s L2 (neskôr)**

- Pre dni kde máš L2 dáta, urob detailnú analýzu
- Porovnaj L2 vs OHLCV výsledky
- Zisti či L2 pridáva hodnotu

**Fáza 3: Live L2 (live trading)**

- Použi IBKR L2 pre live entries
- Risk management cez order book

---

## Konkrétne dáta pre testovanie

### Dostupné pre backtesting:

```
AAPL: 2025-08-01 až 2026-01-28 (6 mesiacov)
AMD:  2025-08-01 až 2026-01-28 (6 mesiacov)
AMZN: 2025-08-01 až 2026-01-28 (6 mesiacov)
GOOGL: 2025-08-01 až 2026-01-28 (6 mesiacov)
META: 2025-08-01 až 2026-01-28 (6 mesiacov)
MSFT: 2025-08-01 až 2026-01-28 (6 mesiacov)
NVDA:  2025-08-01 až 2026-01-28 (6 mesiacov)
TSLA:  2025-08-01 až 2026-01-28 (6 mesiacov)
```

### Parquet súbory:

- `january_2026_1min.parquet` - všetky tickery za január 2026
- `january_2026_daily.parquet` - daily dáta

### L2 dáta:

- K dispozícii pre vybrané dni (napr. GOOGL 20251201)
- Formát: `YYYYMMDD_quote.zip`
- Vyžaduje manuálnu kontrolu dostupnosti

---

## Odporúčaná dátová stratégia

### Pre rýchle testovanie:

```python
# Použi Databento OHLCV 1m
data_loader = DataLoader("/Users/hotovo/.gemini/antigravity/scratch/ibkr-l2-script/databento_data")
df = data_loader.load_csv("NVDA_ohlcv-1m_2025-08-01_2026-01-28.csv")
```

### Pre detailnú analýzu:

```python
# Pre dni kde máš L2, urob dodatočnú analýzu
# Porovnaj s OHLCV výsledkami
```

### Pre live trading:

```python
# Použi IBKR L2 cez ib_insync
# Implementuj order book analýzu
```

---

## Zhrnutie

| Otázka                    | Odpoveď                                     |
| ------------------------- | ------------------------------------------- |
| Mám L2 dáta?              | Áno, ale obmedzené                          |
| Oplatí sa ich používať?   | Pre live áno, pre backtest čiastočne        |
| Čo použiť pre testovanie? | Databento OHLCV 1m                          |
| Aký je hlavný zdroj?      | Databento (Nasdaq TotalView-ITCH)           |
| Kvalita dát?              | Vysoká pre OHLCV, obmedzená pre L2 históriu |
