# Walk-Forward Backtest Analysis Report

## Prehľad

**Obdobie**: 2026-01-20 až 2026-01-28  
**Tickery**: NVDA, TSLA, AAPL  
**Celkový počet dní**: 21 (7 dní × 3 tickery)  
**Celkový počet obchodov**: 37

---

## Kľúčové Metriky

| Metrika                          | Hodnota                       |
| -------------------------------- | ----------------------------- |
| **Celkový PnL**                  | -$93.01                       |
| **Win Rate**                     | 5.41% (2 výhry / 37 obchodov) |
| **Počet výherných dní**          | 0                             |
| **Počet stratových dní**         | 13                            |
| **Priemerný počet obchodov/deň** | 1.76                          |
| **Priemerný PnL/deň**            | -$4.43                        |

---

## Analýza podľa Tickerov

| Ticker | Obchody | PnL     | Priemer/Obchod |
| ------ | ------- | ------- | -------------- |
| NVDA   | 17      | -$38.93 | -$2.29         |
| TSLA   | 11      | -$34.30 | -$3.12         |
| AAPL   | 9       | -$19.78 | -$2.20         |

**Zistenie**: Všetky tickery boli stratové, najhoršie dopadol TSLA.

---

## Analýza podľa Režimu

| Režim       | Dní | Obchody | PnL     | Win Rate |
| ----------- | --- | ------- | ------- | -------- |
| **CHOPPY**  | 10  | 14      | -$32.05 | 0%       |
| **MIXED**   | 8   | 23      | -$60.96 | 8.7%     |
| **UNKNOWN** | 3   | 0       | $0.00   | N/A      |

**Zistenie**:

- CHOPPY režim generoval menej obchodov ale menšie straty
- MIXED režim bol najaktívnejší ale aj najstratovejší
- TRENDING režim nebol detegovaný vôbec

---

## Analýza podľa Stratégie

| Stratégia          | Dní | Obchody | PnL     | Win Rate |
| ------------------ | --- | ------- | ------- | -------- |
| **Mean Reversion** | 10  | 14      | -$32.05 | 0%       |
| **Rotation**       | 8   | 23      | -$60.96 | 8.7%     |

**Zistenie**:

- Obe stratégie boli stratové
- Rotation stratégia mala viac obchodov ale horšie výsledky
- Mean Reversion mal menšie priemerné straty na obchod

---

## Detailná Analýza Obchodov

### Výherné Obchody (len 2!)

| ID  | Stratégia | Ticker | Side | PnL %  | Dôvod       | Poznámka                   |
| --- | --------- | ------ | ---- | ------ | ----------- | -------------------------- |
| 4   | Rotation  | NVDA   | long | +0.03% | take_profit | Jediný výherný long obchod |
| 37  | Rotation  | AAPL   | long | +0.16% | end_of_day  | Náhodný zisk na konci dňa  |

### Problémové Vzory

1. **Príliš tesné stopy** (stop_loss príliš blízko):
   - Obchody 1, 2, 5, 6, 11, 12, 18, 25, 26, 27, 30, 35, 36
   - Všetky skončili stop_lossom do niekoľkých minút
   - Priemerná dĺžka: 1-2 bary

2. **Nesprávny smer**:
   - Väčšina short obchodov bola otvorená v rastúcom trhu
   - Väčšina long obchodov bola otvorená v klesajúcom trhu

3. **End of day exits**:
   - Obchody nútene zatvorené na konci dňa
   - Často s malými stratami alebo náhodnými ziskami

---

## Štatistické Zistenia

### Distribúcia Dĺžky Obchodov

| Dĺžka (bary) | Počet obchodov | Priemerný PnL |
| ------------ | -------------- | ------------- |
| 1-2          | 15             | -1.15%        |
| 3-10         | 12             | -1.02%        |
| 10+          | 10             | -0.85%        |

**Zistenie**: Kratšie obchody boli stratovejšie - indikácia príliš tesných stopov.

### Distribúcia podľa Exit Reason

| Dôvod         | Počet | Priemerný PnL |
| ------------- | ----- | ------------- |
| stop_loss     | 20    | -1.18%        |
| trailing_stop | 8     | -1.21%        |
| end_of_day    | 8     | -0.45%        |
| take_profit   | 1     | +0.03%        |

**Zistenie**:

- 76% obchodov skončilo na strate (stop_loss alebo trailing_stop)
- take_profit bol dosiahnutý len raz!

---

## Identifikované Problémy

### 1. **Príliš Agresívne Stopy**

- ATR násobiteľ 1.5-2.0 je príliš tesný pre intraday
- Odporúčanie: Zvýšiť na 2.5-3.0

### 2. **Nesprávna Detekcia Smeru**

- Stratégie často vstupujú proti trendu
- Potrebné lepšie potvrdenie smeru (viac indikátorov)

### 3. **Príliš Nízke Thresholdy**

- 0.8% VWAP deviation generuje príliš veľa falošných signálov
- Odporúčanie: Vrátiť na 1.2-1.5%

### 4. **Chýbajúci Trend Filter**

- Žiadny obchod nebol otvorený v TRENDING režime
- Režim detekcia nefunguje správne

### 5. **Príliš Skoré Vstupy**

- Obchody otvárané hneď po detekcii režimu
- Odporúčanie: Čakať na potvrdenie

---

## Odporúčania na Zlepšenie

### Krátkodobé (okamžité)

1. **Zvýšiť ATR násobiteľ** z 1.5 na 2.5-3.0
2. **Zvýšiť VWAP threshold** z 0.8% na 1.2%
3. **Pridať trend filter** - obchodovať len v smere trendu
4. **Znížiť počet obchodov** - kvalita nad kvantitou

### Strednodobé (1-2 týždne)

1. **Vylepšiť regime detection**:
   - Použiť viac dát (30-60 minút)
   - Pridať ADX indikátor
   - Kombinovať viac metrík

2. **Pridať market context**:
   - S&P 500 trend
   - Sektorový trend
   - VIX level

3. **Vylepšiť entry logiku**:
   - Čakať na pullback po signáli
   - Potvrdiť objemom
   - Pridať časové filtre (nie obchodovať otvorenie)

### Dlhodobé (1 mesiac+)

1. **Machine Learning**:
   - Trénovať model na historických dátach
   - Predikovať pravdepodobnosť úspechu signálu

2. **Portfolio Management**:
   - Max 1-2 obchody naraz
   - Daily loss limit
   - Position sizing podľa volatility

---

## Záver

Súčasné stratégie **nie sú profitabilné**. Win rate 5.41% je neudržateľný.

**Hlavné príčiny**:

1. Príliš tesné stop-lossy
2. Nesprávna detekcia smeru
3. Príliš veľa falošných signálov

**Ďalšie kroky**:

1. Implementovať odporúčané zmeny
2. Otestovať na menšom vzorku (1 ticker, 3 dni)
3. Postupne pridávať komplexitu

---

## Prílohy

- CSV s detailnými obchodmi: `trades_20260201_212054.csv`
- JSON report: `walk_forward_report_20260201_212054.json`
- Performance data: `performance_data_20260201_212054.json`
