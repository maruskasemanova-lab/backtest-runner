export const COST_LABEL_BY_KEY = {
  slippage: "Slippage",
  commission: "Commission",
  reg_fee: "Reg Fee",
  sec_fee: "SEC Fee",
  finra_fee: "FINRA Fee",
  market_impact: "Market Impact",
  dynamic_slippage_per_share: "Dynamic Slippage / Share",
  participation_ratio: "Participation Ratio",
  total: "Total Cost",
};
export const DECISION_REASON_TRANSLATIONS = {
  sk: {
    fallback_original: "Pôvodná hodnota zo stratégie",
    strategy_take_profit: "Vypočítané priamo špecifickou logikou zvolenej stratégie",
    strategy_stop_loss: "Vypočítané priamo špecifickou logikou zvolenej stratégie",
    fixed_stop_loss_pct: "Fixný percentuálny SL",
    capped_fixed_floor: "SL orezaný minimálnou podlahou",
    anchored: "Ukotvené na úroveň",
    anchored_target: "TP ukotvený na cieľ",
    no_target_level: "Bez cieľovej úrovne",
    no_nearby_level: "Bez blízkej úrovne",
    no_valid_anchor: "Bez validného anchoru",
    fallback_rr: "Fallback na pôvodný RR",
    fallback_atr: "Fallback na pôvodný SL",
    invalid_entry: "Neplatný vstup",
  },
  en: {
    fallback_original: "Original strategy value",
    strategy_take_profit: "Computed by the strategy's native logic",
    strategy_stop_loss: "Computed by the strategy's native logic",
    fixed_stop_loss_pct: "Fixed stop loss pct",
    capped_fixed_floor: "Capped fixed floor",
    anchored: "Anchored to level",
    anchored_target: "Anchored target",
    no_target_level: "No target level",
    no_nearby_level: "No nearby level",
    no_valid_anchor: "No valid anchor",
    fallback_rr: "Fallback to original RR",
    fallback_atr: "Fallback to original SL",
    invalid_entry: "Invalid entry",
  },
};

export const BREAK_EVEN_TRIGGER_TRANSLATIONS = {
  sk: {
    movement_threshold: "MFE/R threshold splnený",
    levels_proof: "Levels dôkaz",
    l2_proof: "L2 dôkaz",
    blocked_no_go: "No-go blokácia",
    close_confirmed: "Close potvrdenie",
    partial_take_profit_protect: "Ochrana po partial TP",
    context_flow_reversal: "Risk-off po flow reversal",
    manual: "Manuálne",
  },
  en: {
    movement_threshold: "Movement threshold met",
    levels_proof: "Levels proof",
    l2_proof: "L2 proof",
    blocked_no_go: "No-go blocked",
    close_confirmed: "Close confirmed",
    partial_take_profit_protect: "Partial TP protect",
    context_flow_reversal: "Flow reversal risk-off",
    manual: "Manual",
  },
};

export const DECISION_LABELS = {
  sk: {
    "Exit Full Screen": "Ukončiť celú obrazovku",
    "Full Screen": "Celá obrazovka",
    "Details": "Detaily",
    "Raw": "Raw",
    "Decision Log": "Log rozhodnutí",
    "No decisions yet. Start the backtest to see trading decisions appear here.":
      "Zatiaľ nie sú žiadne rozhodnutia. Spustite backtest a rozhodnutia sa zobrazia tu.",
    "No trading decisions in this run yet.": "V tomto behu zatiaľ nie sú obchodné rozhodnutia.",
    "No non-decision events in this run yet.": "V tomto behu zatiaľ nie sú neobchodné udalosti.",
    "Load older": "Načítať staršie",
    "remaining": "zostáva",
    "Decisions": "Rozhodnutia",
    "Events": "Udalosti",
    "Reason": "Dôvod",
    "No description": "Bez popisu",
    "net loss": "čistá strata",
    "Decision": "Rozhodnutie",
    "Event Type": "Typ udalosti",
    "Time": "Čas",
    "Price": "Cena",
    "Side": "Smer",
    "Strategy": "Stratégia",
    "Confidence": "Dôvera",
    "Stop Loss": "Stop Loss",
    "Take Profit": "Take Profit",
    "R:R Ratio": "Pomer R:R",
    "Exit Reason": "Dôvod výstupu",
    "PnL": "PnL",
    "PnL $": "PnL $",
    "Bars Held": "Držané bary",
    "Reasoning": "Odôvodnenie",
    "Trading Costs": "Obchodné náklady",
    "L2 Diagnostics": "L2 diagnostika",
    "Flow Score": "Flow skóre",
    "Signed Aggression": "Podpísaná agresia",
    "L2 Aggression Z": "L2 agresia Z",
    "L2 Book Pressure Z": "L2 book pressure Z",
    "Absorption Rate": "Miera absorpcie",
    "Large Trader Activity": "Aktivita veľkých hráčov",
    "VWAP Execution Flow": "VWAP execution flow",
    "Sweep Detected": "Sweep detekovaný",
    "L2 Source": "L2 zdroj",
    "Intraday Levels": "Intraday úrovne",
    "Tracker": "Sledovanie",
    "Active / Tested / Broken": "Aktívne / testované / prelomené",
    "Bounce / Break Events": "Odrazy / prelomenia",
    "POC": "POC",
    "Value Area": "Value Area",
    "Latest Event": "Posledná udalosť",
    "Level Context Gate": "Gate kontextu úrovní",
    "Status": "Stav",
    "Gate Reason": "Dôvod gate",
    "Near Tested Levels": "Blízke testované úrovne",
    "Value Area Position": "Pozícia vo Value Area",
    "POC On Trade Side": "POC na strane obchodu",
    "Room To Next Opposite Level": "Priestor k opačnej úrovni",
    "Fail Reasons": "Dôvody blokácie",
    "Entry Timing Diagnostics": "Diagnostika načasovania vstupu",
    "First-Bar Stop Loss": "Stop loss v prvom bare",
    "Stop Distance": "Vzdialenosť stopu",
    "VWAP Distance": "Vzdialenosť od VWAP",
    "Confluence Score": "Skóre konfluencie",
    "Diagnosis Tags": "Diagnostické tagy",
    "Signal Data (All Indicators)": "Dáta signálu (všetky indikátory)",
    "Additional Details": "Doplnkové detaily",
    "Decision Action": "Akcia rozhodnutia",
    "Decision Phase": "Fáza rozhodnutia",
    "Regime / Micro": "Režim / mikro",
    "Selected Strategy": "Vybraná stratégia",
    "SL Reason": "Dôvod SL",
    "TP Reason": "Dôvod TP",
    "Effective RR": "Efektívne RR",
    "Risk %": "Riziko %",
    "Break-even State": "Break-even stav",
    "Break-even Trigger": "Break-even trigger",
    "Break-even Proof": "Break-even dôkaz",
    "Break-even Stop": "Break-even stop",
    "Break-even Costs %": "Break-even costs %",
    "Break-even Buffer %": "Break-even buffer %",
    "Break-even Anti-Spike": "Break-even anti-spike",
    "Complete Decision Payload": "Kompletný payload rozhodnutia",
    "Language": "Jazyk",
    "Enabled": "Zapnuté",
    "Disabled": "Vypnuté",
    "PASSED": "PREŠLO",
    "BLOCKED": "BLOKOVANÉ",
    "yes": "áno",
    "no": "nie",
    "Source unavailable": "Zdroj nie je dostupný",
    "fallback_original": "fallback_original",
    "strategy_take_profit": "strategy_take_profit",
  },
  en: {
    "Exit Full Screen": "Exit Full Screen",
    "Full Screen": "Full Screen",
    "Details": "Details",
    "Raw": "Raw",
    "Decision Log": "Decision Log",
    "No decisions yet. Start the backtest to see trading decisions appear here.":
      "No decisions yet. Start the backtest to see trading decisions appear here.",
    "No trading decisions in this run yet.": "No trading decisions in this run yet.",
    "No non-decision events in this run yet.": "No non-decision events in this run yet.",
    "Load older": "Load older",
    "remaining": "remaining",
    "Decisions": "Decisions",
    "Events": "Events",
    "Reason": "Reason",
    "No description": "No description",
    "net loss": "net loss",
    "Decision": "Decision",
    "Event Type": "Event Type",
    "Time": "Time",
    "Price": "Price",
    "Side": "Side",
    "Strategy": "Strategy",
    "Confidence": "Confidence",
    "Stop Loss": "Stop Loss",
    "Take Profit": "Take Profit",
    "R:R Ratio": "R:R Ratio",
    "Exit Reason": "Exit Reason",
    "PnL": "PnL",
    "PnL $": "PnL $",
    "Bars Held": "Bars Held",
    "Reasoning": "Reasoning",
    "Trading Costs": "Trading Costs",
    "L2 Diagnostics": "L2 Diagnostics",
    "Flow Score": "Flow Score",
    "Signed Aggression": "Signed Aggression",
    "L2 Aggression Z": "L2 Aggression Z",
    "L2 Book Pressure Z": "L2 Book Pressure Z",
    "Absorption Rate": "Absorption Rate",
    "Large Trader Activity": "Large Trader Activity",
    "VWAP Execution Flow": "VWAP Execution Flow",
    "Sweep Detected": "Sweep Detected",
    "L2 Source": "L2 Source",
    "Intraday Levels": "Intraday Levels",
    "Tracker": "Tracker",
    "Active / Tested / Broken": "Active / Tested / Broken",
    "Bounce / Break Events": "Bounce / Break Events",
    "POC": "POC",
    "Value Area": "Value Area",
    "Latest Event": "Latest Event",
    "Level Context Gate": "Level Context Gate",
    "Status": "Status",
    "Gate Reason": "Gate Reason",
    "Near Tested Levels": "Near Tested Levels",
    "Value Area Position": "Value Area Position",
    "POC On Trade Side": "POC On Trade Side",
    "Room To Next Opposite Level": "Room To Next Opposite Level",
    "Fail Reasons": "Fail Reasons",
    "Entry Timing Diagnostics": "Entry Timing Diagnostics",
    "First-Bar Stop Loss": "First-Bar Stop Loss",
    "Stop Distance": "Stop Distance",
    "VWAP Distance": "VWAP Distance",
    "Confluence Score": "Confluence Score",
    "Diagnosis Tags": "Diagnosis Tags",
    "Signal Data (All Indicators)": "Signal Data (All Indicators)",
    "Additional Details": "Additional Details",
    "Decision Action": "Decision Action",
    "Decision Phase": "Decision Phase",
    "Regime / Micro": "Regime / Micro",
    "Selected Strategy": "Selected Strategy",
    "SL Reason": "SL Reason",
    "TP Reason": "TP Reason",
    "Effective RR": "Effective RR",
    "Risk %": "Risk %",
    "Break-even State": "Break-even State",
    "Break-even Trigger": "Break-even Trigger",
    "Break-even Proof": "Break-even Proof",
    "Break-even Stop": "Break-even Stop",
    "Break-even Costs %": "Break-even Costs %",
    "Break-even Buffer %": "Break-even Buffer %",
    "Break-even Anti-Spike": "Break-even Anti-Spike",
    "Complete Decision Payload": "Complete Decision Payload",
    "Language": "Language",
    "Enabled": "Enabled",
    "Disabled": "Disabled",
    "PASSED": "PASSED",
    "BLOCKED": "BLOCKED",
    "yes": "yes",
    "no": "no",
    "Source unavailable": "Source unavailable",
    "fallback_original": "fallback_original",
    "strategy_take_profit": "strategy_take_profit",
  },
};

export const DECISION_TOOLTIPS = {
  sk: {
    "Event Type":
      "Typ markeru z backendu (napr. entry_executed, stop_loss_hit). Slúži na určenie, ktorá logika a ktoré polia sa majú zobraziť.",
    "Time":
      "Čas udalosti podľa timestampu markeru. Ide o čas, kedy runner zaevidoval rozhodnutie alebo obchodnú udalosť.",
    "Price":
      "Cena priamo z markeru. Pri vstupe je to vstupná cena, pri výstupe výstupná cena udalosti.",
    "Side":
      "Smer pozície: long alebo short. Ovláda interpretáciu rizika, room aj smeru SL/TP.",
    "Strategy":
      "Stratégia, ktorá rozhodnutie vygenerovala alebo bola vybraná v danom kroku.",
    "Confidence":
      "Dôvera signálu v percentách. Je výsledkom skórovania a kalibrácie na strane stratégie.",
    "Stop Loss":
      "Aktuálny stop-loss pri vstupe. Môže byť upravený risk logikou (napr. capped/strategy/context).",
    "Take Profit":
      "Aktuálny take-profit pri vstupe. Môže zostať pôvodný alebo byť prekotvený podľa kontextu.",
    "R:R Ratio":
      "Pomer odmeny k riziku vypočítaný zo vzdialeností TP a SL od vstupu.",
    "Exit Reason":
      "Dôvod ukončenia pozície (napr. stop_loss, take_profit, time_exit, breakeven_stop). Pri breakeven_stop pozri BE sekciu: stav, stop úroveň, costs a buffer.",
    "PnL":
      "Výsledok obchodu v percentách účtu (normalizované cez veľkosť účtu).",
    "PnL $":
      "Výsledok obchodu v dolároch po započítaní nákladov podľa payloadu výstupu.",
    "Bars Held":
      "Koľko barov bola pozícia otvorená medzi vstupom a výstupom.",
    "Reasoning":
      "Textové odôvodnenie rozhodnutia zo stratégie. Pomáha pri auditovaní prečo bol vstup/výstup vykonaný.",
    "Trading Costs":
      "Rozpad transakčných nákladov použitých v simulácii (slippage, komisie, poplatky, impact).",
    "Flow Score":
      "Súhrnné L2 flow skóre zo zvoleného zdroja pre tento marker. Vyššie absolútne hodnoty zvyčajne znamenajú silnejší order-flow signál.",
    "Signed Aggression":
      "Podpísaná agresia toku objednávok. Kladná hodnota favorizuje nákupný tlak, záporná predajný tlak.",
    "L2 Aggression Z":
      "Z-score normalizovaná agresia proti rolling baseline; extrémy signalizujú neštandardný flow.",
    "L2 Book Pressure Z":
      "Z-score normalizovaný tlak knihy objednávok voči baseline.",
    "Absorption Rate":
      "Miera absorpcie agresívnych objednávok pasívnou stranou knihy. Vyššie číslo často znamená väčšiu absorpciu.",
    "Large Trader Activity":
      "Odhad aktivity veľkých účastníkov trhu (blokové alebo výrazné objednávky).",
    "VWAP Execution Flow":
      "Metrika exekučného toku voči VWAP. Tu sa zobrazuje iba hodnota zo striktne určeného backend poľa bez fallbacku.",
    "Sweep Detected":
      "Či backend označil tento marker ako potvrdený liquidity sweep trigger.",
    "L2 Source":
      "Presná cesta v payload-e, z ktorej sa čítajú L2 metriky pre aktuálny marker.",
    "Intraday Levels":
      "Sekcia intraday support/resistance a volume-profile kontextu pre daný čas rozhodnutia.",
    "Tracker":
      "Stav intraday trackeru úrovní. Ak je vypnutý, nové úrovne a udalosti sa negenerujú.",
    "Active / Tested / Broken":
      "Počet aktívnych, otestovaných a prelomených úrovní v čase markeru.",
    "Bounce / Break Events":
      "Počet zaznamenaných odrazov a prelomení úrovní.",
    "POC":
      "Point of Control cena z volume profilu (cena s najvyšším objemom).",
    "Value Area":
      "Rozsah cien (low-high), kde sa zobchodovala hlavná časť objemu.",
    "Latest Event":
      "Najnovšia úrovňová udalosť (bounce/break) v okolí rozhodnutia.",
    "Level Context Gate":
      "Výsledok gatingu kvality vstupu podľa intraday úrovní a kontextových kontrol.",
    "Status":
      "Či gate prešiel alebo blokoval vstup v danom okamihu.",
    "Gate Reason":
      "Hlavný dôvod výsledku gate (passed/blocked/disabled a pod.).",
    "Near Tested Levels":
      "Počet blízkych úrovní, ktoré boli už testované, čo zvyšuje kvalitu kontextu.",
    "Value Area Position":
      "Poloha ceny voči value area (inside/above/below).",
    "POC On Trade Side":
      "Či je POC na preferovanej strane obchodu podľa smeru.",
    "Room To Next Opposite Level":
      "Priestor v percentách k najbližšej opačnej úrovni; pomáha odhadnúť potenciál pohybu.",
    "Fail Reasons":
      "Zoznam konkrétnych dôvodov, pre ktoré gate vstup zablokoval.",
    "Entry Timing Diagnostics":
      "Diagnostika kvality načasovania vstupu, hlavne pre rýchle stop-loss výstupy.",
    "First-Bar Stop Loss":
      "Či bol obchod ukončený stop-lossom už v prvom bare po vstupe.",
    "Stop Distance":
      "Vzdialenosť stop-lossu od vstupu v percentách.",
    "VWAP Distance":
      "Vzdialenosť vstupnej ceny od VWAP v percentách.",
    "Confluence Score":
      "Skóre súbehu faktorov (úrovne, profil, kontext) v mieste vstupu.",
    "Diagnosis Tags":
      "Tagy sumarizujúce pravdepodobné príčiny nekvalitného vstupu alebo rýchleho stopu.",
    "Signal Data (All Indicators)":
      "Kompletné indikátory/metadáta signálu priamo zo stratégie.",
    "Additional Details":
      "Ďalšie polia z payloadu, ktoré sa nezmestili do špecializovaných sekcií.",
    "Decision Action":
      "Hlavná akcia rozhodovacieho stroja v danom kroku (napr. open/hold/skip).",
    "Decision Phase":
      "Fáza pipeline rozhodovania (detekcia, gate, exekúcia, manažment).",
    "Regime / Micro":
      "Makro a mikro režim trhu, v ktorom sa rozhodovalo.",
    "Selected Strategy":
      "Stratégia, ktorú rozhodovacia logika vybrala pre tento krok.",
    "SL Reason":
      "Dôvod nastavenia stop-lossu z context_risk. Napr. anchored_support alebo capped_fixed_floor.",
    "TP Reason":
      "Dôvod nastavenia take-profitu z context_risk. `fallback_original` znamená, že sa TP neprepisoval a zostal pôvodný zo stratégie.",
    "Effective RR":
      "Efektívny pomer room/risk po finálnom SL/TP. Počíta sa ako room_pct / risk_pct.",
    "Risk %":
      "Percento rizika z ceny vstupu po finálnom SL: abs(entry - SL) / entry * 100.",
    "Break-even State":
      "Stav BE automatu: idle → armed → moved → locked → handoff.",
    "Break-even Trigger":
      "Podmienky aktivácie BE na close 1m: MFE/R threshold + min hold + proof gating.",
    "Break-even Proof":
      "Detail dôkazu pre BE aktiváciu (levels a/alebo L2), vrátane no-go blokácie pri silnej blízkej úrovni.",
    "Break-even Stop":
      "Výsledná BE stop cena po započítaní costs a bufferu. Nie je to holé entry.",
    "Break-even Costs %":
      "Nákladová zložka BE (fees/slippage + polovica spreadu), použitá pri výpočte BE stopu.",
    "Break-even Buffer %":
      "Buffer nad/pod cost-aware BE (min/ATR/tick komponent), aby stop nebol citlivý na mikro-šum.",
    "Break-even Anti-Spike":
      "Intrabar anti-spike filter po aktivácii BE: počas anti-spike okna sa stop potvrdí cez 1s close-beyond ALEBO po dosiahnutí required consecutive hits.",
    "Complete Decision Payload":
      "Plný JSON payload pre audit. Je to zdroj pravdy pre všetky zobrazené hodnoty v Decision Log.",
    "Slippage":
      "Sklz medzi očakávanou a realizovanou cenou exekúcie v simulácii.",
    "Commission":
      "Komisný poplatok brokera započítaný do PnL.",
    "Reg Fee":
      "Regulačné poplatky (ak sú v modeli aktívne).",
    "SEC Fee":
      "SEC poplatok podľa modelu nákladov.",
    "FINRA Fee":
      "FINRA poplatok podľa modelu nákladov.",
    "Market Impact":
      "Odhad trhového dopadu exekúcie pri danej likvidite a participácii.",
    "Dynamic Slippage / Share":
      "Dynamický sklz na akciu podľa likvidity a účasti objednávky.",
    "Participation Ratio":
      "Pomer veľkosti exekúcie ku objemu baru.",
    "Total Cost":
      "Celkové náklady obchodu ako súčet všetkých cost zložiek.",
    _default:
      "Hodnota z decision payloadu. Slúži na audit rozhodnutia, výpočtu alebo exekúcie v danom kroku.",
  },
  en: {},
};

