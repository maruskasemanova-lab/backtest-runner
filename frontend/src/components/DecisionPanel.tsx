import { memo, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { toUnixSeconds } from "../utils";

const DECISION_MARKER_TYPES = new Set([
  'entry_executed',
  'exit_executed',
  'stop_loss_hit',
  'take_profit_hit',
  'signal_generated',
  'execution_status',
  'trailing_stop_updated',
]);
const EXIT_MARKER_TYPES = new Set([
  'exit_executed',
  'stop_loss_hit',
  'take_profit_hit',
  'time_exit',
]);
const L2_DIAGNOSTIC_KEYS = [
  'flow_score',
  'signed_aggression',
  'l2_aggression_z',
  'l2_book_pressure_z',
  'absorption_rate',
  'large_trader_activity',
  'vwap_execution_flow',
];
const DECISION_LIST_INITIAL_ROWS = 320;
const DECISION_LIST_LOAD_STEP = 320;
const DEFAULT_ACCOUNT_SIZE = 10_000;
const DECISION_PANEL_LANGUAGE_STORAGE_KEY = "backtest_runner.decision_panel_language";
const SUPPORTED_DECISION_LANGUAGES = new Set(["sk", "en"]);
const COST_LABEL_BY_KEY = {
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
const DECISION_REASON_TRANSLATIONS = {
  sk: {
    fallback_original: "Pôvodná hodnota zo stratégie",
    strategy_take_profit: "TP zo stratégie",
    strategy_stop_loss: "SL zo stratégie",
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
    strategy_take_profit: "Strategy take profit",
    strategy_stop_loss: "Strategy stop loss",
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

const BREAK_EVEN_TRIGGER_TRANSLATIONS = {
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

const DECISION_LABELS = {
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

const DECISION_TOOLTIPS = {
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

const TOOLTIP_BASE_LABEL_ALIASES = {
  "Strategy (Entry)": "Strategy",
  "Strategy (Gate)": "Strategy",
  "Near Tested Levels (Gate)": "Near Tested Levels",
  "Near Tested Levels (Entry Timing)": "Near Tested Levels",
  "POC On Trade Side (Gate)": "POC On Trade Side",
  "POC On Trade Side (Entry Timing)": "POC On Trade Side",
  "VWAP Execution Flow (L2 Diagnostics)": "VWAP Execution Flow",
  "VWAP Execution Flow (Decision Log)": "VWAP Execution Flow",
};

const resolveTooltipBaseLabel = (label) => {
  const normalized = String(label || "").trim();
  if (!normalized) return "";
  const aliased = TOOLTIP_BASE_LABEL_ALIASES[normalized];
  if (aliased) return aliased;
  return normalized.replace(/\s+\([^)]*\)\s*$/, "");
};

const formatTooltipRuntimeValue = (value) => {
  if (value === null || value === undefined) return "n/a";
  if (typeof value === "number") {
    if (!Number.isFinite(value)) return "n/a";
    if (Math.abs(value) >= 1000) return value.toLocaleString("en-US", { maximumFractionDigits: 6 });
    return Number.isInteger(value) ? String(value) : value.toFixed(6).replace(/0+$/, "").replace(/\.$/, "");
  }
  if (typeof value === "boolean") return value ? "true" : "false";
  if (Array.isArray(value)) {
    if (!value.length) return "[]";
    return value.map((item) => formatTooltipRuntimeValue(item)).join(", ");
  }
  if (typeof value === "object") {
    const entries = Object.entries(value);
    if (!entries.length) return "{}";
    return entries
      .slice(0, 8)
      .map(([key, item]) => `${key}: ${formatTooltipRuntimeValue(item)}`)
      .join(" | ");
  }
  return String(value);
};

const resolveDecisionLanguage = () => {
  if (typeof window === "undefined") return "sk";
  const stored = String(
    window.localStorage.getItem(DECISION_PANEL_LANGUAGE_STORAGE_KEY) || "",
  ).trim().toLowerCase();
  if (SUPPORTED_DECISION_LANGUAGES.has(stored)) return stored;
  return "sk";
};

const isDecisionMarker = (marker) => DECISION_MARKER_TYPES.has(marker?.marker_type);


const formatGenericValue = (value) => {
  if (value === null || value === undefined) return 'n/a';
  if (typeof value === 'number') {
    if (!Number.isFinite(value)) return 'n/a';
    return Number.isInteger(value) ? String(value) : value.toFixed(4);
  }
  if (typeof value === 'boolean') return value ? 'true' : 'false';
  if (Array.isArray(value)) {
    if (!value.length) return '[]';
    return value.map((item) => {
      if (typeof item === 'object' && item !== null) return JSON.stringify(item);
      return String(item);
    }).join(', ');
  }
  if (typeof value === 'object') {
    const entries = Object.entries(value);
    if (!entries.length) return '{}';
    return entries
      .slice(0, 10)
      .map(([k, v]) => `${k}: ${formatGenericValue(v)}`)
      .join(' | ');
  }
  return String(value);
};

// Recursive function to render values (from ChartTooltip)
const renderValue = (val, keyPrefix = '') => {
  if (val === null || val === undefined) return 'N/A';
  
  if (typeof val === 'object' && !Array.isArray(val)) {
    if (Object.keys(val).length === 0) return '{}';
    
    return (
      <div className="object-container" style={{ marginLeft: '10px', borderLeft: '2px solid rgba(15, 23, 42, 0.1)', paddingLeft: '8px' }}>
        {Object.entries(val).map(([k, v]) => (
          <div key={`${keyPrefix}-${k}`} className="object-row" style={{ marginTop: '4px' }}>
            <span className="object-key" style={{ fontWeight: 500, color: 'var(--text-secondary)', fontSize: '0.85em' }}>{k}:</span>
            <div className="nested-object">
              {renderValue(v, `${keyPrefix}-${k}`)}
            </div>
          </div>
        ))}
      </div>
    );
  }
  
  if (Array.isArray(val)) {
    if (val.length === 0) return '[]';
    return (
      <div className="object-container" style={{ marginLeft: '10px', borderLeft: '2px solid rgba(15, 23, 42, 0.1)', paddingLeft: '8px' }}>
        {val.map((v, i) => (
           <div key={`${keyPrefix}-${i}`} className="object-row" style={{ marginTop: '4px' }}>
            <span className="object-key" style={{ fontWeight: 500, color: 'var(--text-secondary)', fontSize: '0.85em' }}>[{i}]:</span>
             <div className="nested-object">
               {renderValue(v, `${keyPrefix}-${i}`)}
             </div>
           </div>
        ))}
      </div>
    );
  }
  
  if (typeof val === 'number') {
    return <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.9em' }}>{Math.abs(val) < 0.01 ? val.toFixed(6) : val.toFixed(4)}</span>;
  }
  
  return <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.9em' }}>{String(val)}</span>;
};

const toFiniteNumber = (value) => {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
};

const resolvePnlPct = (details, pnlDollars) => {
  const explicitPct = toFiniteNumber(details?.pnl_pct);
  if (explicitPct !== null) return explicitPct;

  const dollars = Number(pnlDollars);
  if (!Number.isFinite(dollars)) return null;

  const notional = toFiniteNumber(details?.position_notional_usd);
  if (notional !== null && notional > 0) {
    return (dollars / notional) * 100;
  }

  return (dollars / DEFAULT_ACCOUNT_SIZE) * 100;
};

const isObjectRecord = (value) =>
  Boolean(value) && typeof value === 'object' && !Array.isArray(value);

const getL2MetricFromSource = (source, metricKey) => {
  if (!isObjectRecord(source)) return null;
  const direct = toFiniteNumber(source[metricKey]);
  if (direct !== null) return direct;
  const prefixed = toFiniteNumber(source[`l2_${metricKey}`]);
  if (prefixed !== null) return prefixed;
  return null;
};

const getBooleanMetricFromSource = (source, metricKey) => {
  if (!isObjectRecord(source)) return null;
  const direct = source[metricKey];
  if (typeof direct === "boolean") return direct;
  const prefixed = source[`l2_${metricKey}`];
  if (typeof prefixed === "boolean") return prefixed;
  return null;
};

const normalizeL2SourceSnapshot = (source) => {
  if (!isObjectRecord(source)) return null;
  const normalized = { ...source };
  L2_DIAGNOSTIC_KEYS.forEach((metricKey) => {
    if (normalized[metricKey] == null) {
      const resolved = getL2MetricFromSource(source, metricKey);
      if (resolved !== null) {
        normalized[metricKey] = resolved;
      }
    }
  });
  if (normalized.sweep_detected == null) {
    const sweepDetected = getBooleanMetricFromSource(source, "sweep_detected");
    if (sweepDetected !== null) {
      normalized.sweep_detected = sweepDetected;
    }
  }
  return normalized;
};

const buildRiskControlsCandidates = ({ details, signalMetadata, marketContext }) => {
  const detailMetadata = isObjectRecord(details?.metadata) ? details.metadata : null;
  return [
    { path: "details.metadata.risk_controls", value: detailMetadata?.risk_controls },
    { path: "details.risk_controls", value: details?.risk_controls },
    {
      path: "details.entry_quality_diagnostics.risk_controls",
      value: details?.entry_quality_diagnostics?.risk_controls,
    },
    { path: "details.signal_metadata.risk_controls", value: details?.signal_metadata?.risk_controls },
    { path: "signal_metadata.risk_controls", value: signalMetadata?.risk_controls },
    { path: "market_context.risk_controls", value: marketContext?.risk_controls },
  ];
};

const resolveRiskControls = (params) => {
  const candidates = buildRiskControlsCandidates(params);
  const selected = candidates.find((candidate) => isObjectRecord(candidate.value));
  return {
    value: selected?.value || null,
    sourcePath: selected?.path || "n/a",
    candidates,
  };
};

const buildContextRiskCandidates = ({ details, signalMetadata, marketContext, riskControls }) => {
  const detailMetadata = isObjectRecord(details?.metadata) ? details.metadata : null;
  return [
    { path: "details.context_risk", value: details?.context_risk },
    { path: "details.metadata.context_risk", value: detailMetadata?.context_risk },
    {
      path: "details.metadata.risk_controls.context_risk",
      value: detailMetadata?.risk_controls?.context_risk,
    },
    { path: "details.risk_controls.context_risk", value: details?.risk_controls?.context_risk },
    {
      path: "details.entry_quality_diagnostics.risk_controls.context_risk",
      value: details?.entry_quality_diagnostics?.risk_controls?.context_risk,
    },
    {
      path: "details.signal_metadata.risk_controls.context_risk",
      value: details?.signal_metadata?.risk_controls?.context_risk,
    },
    { path: "signal_metadata.risk_controls.context_risk", value: signalMetadata?.risk_controls?.context_risk },
    { path: "market_context.risk_controls.context_risk", value: marketContext?.risk_controls?.context_risk },
    { path: "resolved_risk_controls.context_risk", value: riskControls?.context_risk },
  ];
};

const resolveContextRisk = (params) => {
  const candidates = buildContextRiskCandidates(params);
  const selected = candidates.find((candidate) => isObjectRecord(candidate.value));
  return {
    value: selected?.value || null,
    sourcePath: selected?.path || "n/a",
    candidates,
  };
};

const buildBreakEvenCandidates = ({ details, signalMetadata, marketContext }) => [
  { path: "details.break_even", value: details?.break_even },
  {
    path: "details.signal_metadata.break_even",
    value: details?.signal_metadata?.break_even,
  },
  {
    path: "details.entry_quality_diagnostics.break_even",
    value: details?.entry_quality_diagnostics?.break_even,
  },
  { path: "details.market_context.break_even", value: details?.market_context?.break_even },
  { path: "signal_metadata.break_even", value: signalMetadata?.break_even },
  { path: "market_context.break_even", value: marketContext?.break_even },
];

const resolveBreakEven = (params) => {
  const candidates = buildBreakEvenCandidates(params);
  const selected = candidates.find((candidate) => isObjectRecord(candidate.value));
  return {
    value: selected?.value || null,
    sourcePath: selected?.path || "n/a",
    candidates,
  };
};

const buildL2CandidateSources = (marker, details, metadata) => {
  const markerType = String(marker?.marker_type || '').trim();
  const detailMetadata = isObjectRecord(details?.metadata) ? details.metadata : null;
  const signalMetadata = isObjectRecord(details?.signal_metadata) ? details.signal_metadata : null;
  const metadataContext = isObjectRecord(metadata) ? metadata : null;
  const marketL2 = isObjectRecord(details?.market_context?.l2) ? details.market_context.l2 : null;

  const candidates = [];
  const pushCandidate = (sourcePath, source) => {
    if (!isObjectRecord(source)) return;
    candidates.push({ sourcePath, source });
  };

  if (markerType === 'entry_executed') {
    pushCandidate('details.metadata.order_flow', detailMetadata?.order_flow ?? metadataContext?.order_flow);
    pushCandidate('details.signal_metadata.order_flow', signalMetadata?.order_flow);
    pushCandidate('details.flow_snapshot', details?.flow_snapshot);
  } else if (markerType === 'signal_generated') {
    pushCandidate('details.flow_snapshot', details?.flow_snapshot);
    pushCandidate('details.signal_metadata.order_flow', signalMetadata?.order_flow);
    pushCandidate('details.metadata.order_flow', detailMetadata?.order_flow ?? metadataContext?.order_flow);
  } else if (EXIT_MARKER_TYPES.has(markerType)) {
    pushCandidate('details.signal_metadata.order_flow', signalMetadata?.order_flow);
    pushCandidate('details.flow_snapshot', details?.flow_snapshot);
    pushCandidate('details.metadata.order_flow', detailMetadata?.order_flow ?? metadataContext?.order_flow);
  } else {
    pushCandidate('details.flow_snapshot', details?.flow_snapshot);
    pushCandidate('details.signal_metadata.order_flow', signalMetadata?.order_flow);
    pushCandidate('details.metadata.order_flow', detailMetadata?.order_flow ?? metadataContext?.order_flow);
  }

  pushCandidate('details.order_flow', details?.order_flow);
  pushCandidate('marker.order_flow', marker?.order_flow);
  pushCandidate('details.market_context.l2', marketL2);

  return candidates;
};

const resolveL2Source = (marker, details, metadata) => {
  const candidates = buildL2CandidateSources(marker, details, metadata);
  const candidateDiagnostics = candidates.map(({ sourcePath, source }) => {
    const availableMetrics = L2_DIAGNOSTIC_KEYS.filter(
      (metricKey) => getL2MetricFromSource(source, metricKey) !== null,
    );
    return {
      sourcePath,
      score: availableMetrics.length,
      availableMetrics,
    };
  });
  let best = null;

  for (let idx = 0; idx < candidates.length; idx += 1) {
    const candidate = candidates[idx];
    const score = candidateDiagnostics[idx]?.score || 0;
    if (score <= 0) continue;
    if (!best || score > best.score) {
      best = { ...candidate, score, candidateIndex: idx };
    }
  }

  if (!best) {
    return {
      source: null,
      sourcePath: 'n/a',
      candidateDiagnostics,
    };
  }

  return {
    source: best.source,
    sourcePath: best.sourcePath,
    candidateDiagnostics,
  };
};

const extractL2Diagnostics = (marker, details, metadata) => {
  const { source, sourcePath, candidateDiagnostics } = resolveL2Source(marker, details, metadata);

  const flowScore = getL2MetricFromSource(source, 'flow_score');
  const signedAggression = getL2MetricFromSource(source, 'signed_aggression');
  const l2AggressionZ = getL2MetricFromSource(source, 'l2_aggression_z');
  const l2BookPressureZ = getL2MetricFromSource(source, 'l2_book_pressure_z');
  const absorptionRate = getL2MetricFromSource(source, 'absorption_rate');
  const largeTraderActivity = getL2MetricFromSource(source, 'large_trader_activity');
  const vwapExecutionFlow = getL2MetricFromSource(source, 'vwap_execution_flow');
  const detailMetadata = isObjectRecord(details?.metadata) ? details.metadata : null;
  const signalMetadata = isObjectRecord(details?.signal_metadata) ? details.signal_metadata : null;
  const sweepDetected =
    getBooleanMetricFromSource(source, 'sweep_detected') ??
    (typeof details?.sweep_detected === "boolean" ? details.sweep_detected : null) ??
    (typeof detailMetadata?.sweep_detected === "boolean" ? detailMetadata.sweep_detected : null) ??
    (typeof signalMetadata?.sweep_detected === "boolean" ? signalMetadata.sweep_detected : null) ??
    (typeof detailMetadata?.sweep_triggered === "boolean" ? detailMetadata.sweep_triggered : null);

  const hasAny = [
    flowScore,
    signedAggression,
    l2AggressionZ,
    l2BookPressureZ,
    absorptionRate,
    largeTraderActivity,
    vwapExecutionFlow,
  ].some((value) => value !== null) || sweepDetected !== null;

  return {
    hasAny,
    flowScore,
    signedAggression,
    l2AggressionZ,
    l2BookPressureZ,
    absorptionRate,
    largeTraderActivity,
    vwapExecutionFlow,
    sweepDetected,
    sourcePath,
    candidateDiagnostics,
  };
};

const extractIntradayLevels = (marker, details, metadata) => {
  const candidates = [
    details?.intraday_levels,
    details?.metadata?.intraday_levels,
    details?.indicators?.intraday_levels,
    metadata?.intraday_levels,
    marker?.intraday_levels,
  ];
  const payload = candidates.find(
    (candidate) => candidate && typeof candidate === "object" && !Array.isArray(candidate),
  );
  if (!payload) {
    return { hasAny: false, enabled: true, stats: {}, volumeProfile: {}, latestEvent: null };
  }
  const stats =
    payload.stats && typeof payload.stats === "object" && !Array.isArray(payload.stats)
      ? payload.stats
      : {};
  const volumeProfile =
    payload.volume_profile &&
    typeof payload.volume_profile === "object" &&
    !Array.isArray(payload.volume_profile)
      ? payload.volume_profile
      : {};
  const latestEvent =
    payload.latest_event && typeof payload.latest_event === "object" ? payload.latest_event : null;
  return {
    hasAny: true,
    enabled: payload.enabled !== false,
    stats,
    volumeProfile,
    latestEvent,
  };
};

const extractLevelContext = (marker, details, metadata) => {
  const candidates = [
    details?.level_context,
    details?.metadata?.level_context,
    details?.signal_metadata?.level_context,
    metadata?.level_context,
    marker?.level_context,
  ];
  const payload = candidates.find(
    (candidate) => candidate && typeof candidate === "object" && !Array.isArray(candidate),
  );
  if (!payload) {
    return { hasAny: false, payload: {}, checks: {}, reasons: [] };
  }
  const checks =
    payload.checks && typeof payload.checks === "object" && !Array.isArray(payload.checks)
      ? payload.checks
      : {};
  const reasons = Array.isArray(payload.reasons)
    ? payload.reasons.map((item) => String(item || "")).filter(Boolean)
    : [];
  return {
    hasAny: true,
    payload,
    checks,
    reasons,
  };
};

const extractEntryQualityDiagnostics = (marker, details, metadata) => {
  const candidates = [
    details?.entry_quality_diagnostics,
    details?.metadata?.entry_quality_diagnostics,
    metadata?.entry_quality_diagnostics,
    marker?.entry_quality_diagnostics,
  ];
  const payload = candidates.find(
    (candidate) => candidate && typeof candidate === "object" && !Array.isArray(candidate),
  );
  if (!payload) {
    return { hasAny: false, payload: {}, tags: [] };
  }
  const tags = Array.isArray(payload.first_bar_stop_tags)
    ? payload.first_bar_stop_tags.map((item) => String(item || "")).filter(Boolean)
    : [];
  return {
    hasAny: true,
    payload,
    tags,
  };
};

const extractDecisionLogPayload = (marker, details, metadata) => {
  const markerType = String(marker?.marker_type || '').trim();
  const marketContext =
    details?.market_context && typeof details.market_context === "object" ? details.market_context : null;
  const signalMetadata =
    markerType === 'entry_executed'
      ? details?.metadata && typeof details.metadata === "object"
        ? details.metadata
        : null
      : details?.signal_metadata && typeof details.signal_metadata === "object"
        ? details.signal_metadata
        : null;
  const levelContext =
    details?.level_context && typeof details.level_context === "object"
      ? details.level_context
      : signalMetadata?.level_context && typeof signalMetadata.level_context === "object"
        ? signalMetadata.level_context
        : null;
  const intradayLevels =
    details?.intraday_levels && typeof details.intraday_levels === "object"
      ? details.intraday_levels
      : signalMetadata?.intraday_levels && typeof signalMetadata.intraday_levels === "object"
        ? signalMetadata.intraday_levels
        : null;
  const flowSnapshot = normalizeL2SourceSnapshot(
    resolveL2Source(marker, details, signalMetadata).source,
  );
  const entryQualityDiagnostics =
    details?.entry_quality_diagnostics && typeof details.entry_quality_diagnostics === "object"
      ? details.entry_quality_diagnostics
      : null;
  const riskControlsResolution = resolveRiskControls({
    details,
    signalMetadata,
    marketContext,
  });
  const contextRiskResolution = resolveContextRisk({
    details,
    signalMetadata,
    marketContext,
    riskControls: riskControlsResolution.value,
  });
  const breakEvenResolution = resolveBreakEven({
    details,
    signalMetadata,
    marketContext,
  });
  const decisionState =
    marketContext?.decision_state && typeof marketContext.decision_state === "object"
      ? marketContext.decision_state
      : null;

  const payload = {
    marker_meta: {
      id: marker?.id ?? null,
      marker_type: marker?.marker_type ?? null,
      timestamp: marker?.timestamp ?? marker?.time ?? null,
      title: marker?.title ?? null,
      description: marker?.description ?? null,
      side: marker?.side ?? null,
      strategy: marker?.strategy ?? null,
      price: marker?.price ?? null,
      confidence: marker?.confidence ?? null,
    },
    decision_state: decisionState,
    signal_metadata: signalMetadata,
    level_context: levelContext,
    intraday_levels: intradayLevels,
    flow_snapshot: flowSnapshot,
    market_context: marketContext,
    entry_quality_diagnostics: entryQualityDiagnostics,
    risk_controls: riskControlsResolution.value,
    context_risk: contextRiskResolution.value,
    context_risk_source_path: contextRiskResolution.sourcePath,
    context_risk_candidates: contextRiskResolution.candidates,
    break_even: breakEvenResolution.value,
    break_even_source_path: breakEvenResolution.sourcePath,
    break_even_candidates: breakEvenResolution.candidates,
    risk_controls_source_path: riskControlsResolution.sourcePath,
    risk_controls_candidates: riskControlsResolution.candidates,
    metadata,
    details,
  };

  const hasAny = Object.values(payload).some((value) => value != null);
  return {
    hasAny,
    payload,
  };
};

function DecisionPanel({ markers, selectedMarker, onSelectMarker }) {
  const [detailTab, setDetailTab] = useState('details');
  const [listTab, setListTab] = useState('decisions');
  const [visibleRows, setVisibleRows] = useState(DECISION_LIST_INITIAL_ROWS);
  const [isDetailFullscreen, setIsDetailFullscreen] = useState(false);
  const [uiLanguage, setUiLanguage] = useState(resolveDecisionLanguage);
  const [activeHelpTooltip, setActiveHelpTooltip] = useState(null);
  const itemRefs = useRef(new Map());
  const autoScrollStateRef = useRef({ markerIdentity: '', listTab: '', done: false });

  useEffect(() => {
    if (typeof window === "undefined") return;
    window.localStorage.setItem(DECISION_PANEL_LANGUAGE_STORAGE_KEY, uiLanguage);
  }, [uiLanguage]);

  useEffect(() => {
    if (!selectedMarker) {
      setIsDetailFullscreen(false);
      return;
    }
    setDetailTab('details');
    if (selectedMarker?.__selectionSource === "decision_panel") {
      setIsDetailFullscreen(true);
    } else if (selectedMarker?.__selectionSource === "chart") {
      setIsDetailFullscreen(false);
    }
  }, [
    selectedMarker?.id,
    selectedMarker?.timestamp,
    selectedMarker?.time,
    selectedMarker?.__selectionSource,
  ]);

  useEffect(() => {
    setActiveHelpTooltip(null);
  }, [
    selectedMarker?.id,
    selectedMarker?.timestamp,
    selectedMarker?.time,
    detailTab,
    uiLanguage,
    isDetailFullscreen,
  ]);

  useEffect(() => {
    if (!activeHelpTooltip) return undefined;
    const clearTooltip = () => setActiveHelpTooltip(null);
    window.addEventListener("scroll", clearTooltip, true);
    window.addEventListener("resize", clearTooltip);
    return () => {
      window.removeEventListener("scroll", clearTooltip, true);
      window.removeEventListener("resize", clearTooltip);
    };
  }, [activeHelpTooltip]);

  useEffect(() => {
    if (!activeHelpTooltip?.pinned) return undefined;
    const handlePointerDown = (event) => {
      const target = event.target;
      if (
        target instanceof Element &&
        (
          target.closest(".detail-label-help") ||
          target.closest(".detail-label-trigger") ||
          target.closest(".decision-help-inline")
        )
      ) {
        return;
      }
      setActiveHelpTooltip(null);
    };
    window.addEventListener("pointerdown", handlePointerDown, true);
    return () => window.removeEventListener("pointerdown", handlePointerDown, true);
  }, [activeHelpTooltip?.pinned]);

  useEffect(() => {
    if (!isDetailFullscreen) return undefined;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const handleKeyDown = (event) => {
      if (event.key === 'Escape') {
        setIsDetailFullscreen(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = previousOverflow;
    };
  }, [isDetailFullscreen]);

  useEffect(() => {
    if (!selectedMarker) return;
    setListTab(isDecisionMarker(selectedMarker) ? 'decisions' : 'events');
  }, [selectedMarker?.id, selectedMarker?.timestamp, selectedMarker?.time, selectedMarker?.marker_type]);

  useEffect(() => {
    setVisibleRows(DECISION_LIST_INITIAL_ROWS);
  }, [listTab]);

  // Format time
  const formatTime = (timestamp) => {
    if (!timestamp) return 'N/A';
    const date = new Date(timestamp);
    if (Number.isNaN(date.getTime())) return 'N/A';
    return date.toLocaleTimeString('en-US', { 
      hour: '2-digit', 
      minute: '2-digit',
      second: '2-digit',
      hour12: false 
    });
  };

  const formatPrice = (value) => {
    const number = Number(value);
    return Number.isFinite(number) ? `$${number.toFixed(2)}` : 'N/A';
  };

  const getMarkerIdentity = (marker) => {
    if (!marker) return '';
    if (marker.id) return `id:${marker.id}`;
    return [
      marker.marker_type || 'marker',
      marker.timestamp || marker.time || 'na',
      marker.price ?? 'na',
      marker.side || 'na',
    ].join('|');
  };

  const getMarkerKey = (marker, idx = 0) => {
    return marker.id || `${marker.marker_type || 'marker'}-${marker.timestamp || marker.time || 'na'}-${idx}`;
  };

  const isSameMarker = (a, b) => {
    if (!a || !b) return false;
    if (a.id && b.id && a.id === b.id) return true;
    return (
      String(a.marker_type || '') === String(b.marker_type || '') &&
      String(a.timestamp || '') === String(b.timestamp || '') &&
      String(a.time || '') === String(b.time || '') &&
      Number(a.price ?? NaN) === Number(b.price ?? NaN)
    );
  };
  
  // Get marker icon (context-aware: TP with net loss shows red)
  const getMarkerIcon = (marker) => {
    const markerType = marker.marker_type;
    const markerPnlUsd = marker?.details?.pnl_usd ?? marker?.details?.pnl_dollars;
    const markerPnlPct = resolvePnlPct(marker?.details, markerPnlUsd);
    // If take-profit but after costs it's a loss, show red icon
    if (markerType === 'take_profit_hit' && markerPnlPct !== null && markerPnlPct <= 0) {
      return '🔴';
    }
    const icons = {
      regime_detected: '🎯',
      strategy_selected: '📋',
      signal_generated: '📊',
      execution_status: '⏳',
      entry_executed: '🟢',
      exit_executed: '⚪',
      stop_loss_hit: '🔴',
      take_profit_hit: '💰',
      iceberg_detected: '❄️',
      trailing_stop_updated: '📍',
      session_started: '🏁',
      session_ended: '🏆',
    };
    return icons[markerType] || '📌';
  };

  const renderTitle = (marker) => {
    const markerPnlUsd = marker?.details?.pnl_usd ?? marker?.details?.pnl_dollars;
    const markerPnlPct = resolvePnlPct(marker?.details, markerPnlUsd);
    if (marker.marker_type === 'take_profit_hit' && markerPnlPct !== null && markerPnlPct <= 0) {
      return `${marker.title || t("Take Profit")} (${t("net loss")})`;
    }
    return marker.title || marker.marker_type || t("Decision");
  };

  const formatExitMetrics = (marker) => {
    if (!['exit_executed', 'stop_loss_hit', 'take_profit_hit'].includes(marker.marker_type)) {
      return null;
    }
    const details = marker.details || {};
    const pnlUsd = details.pnl_usd ?? details.pnl_dollars;
    const pnlPct = resolvePnlPct(details, pnlUsd);
    const costUsd = details.cost_usd ?? details.costs?.total;
    const costPct = details.cost_pct;
    const barsHeld = details.bars_held;

    const parts = [];
    if (pnlPct != null || pnlUsd != null) {
      const pctText = pnlPct != null ? `${pnlPct >= 0 ? '+' : ''}${Number(pnlPct).toFixed(2)}%` : "n/a";
      const usdText = pnlUsd != null ? `${Number(pnlUsd) >= 0 ? '+' : ''}$${Number(pnlUsd).toFixed(2)}` : "n/a";
      parts.push(`PnL: ${pctText} (${usdText})`);
    }
    if (costUsd != null) {
      const costUsdText = `$${Number(costUsd).toFixed(2)}`;
      const costPctText = costPct != null ? ` (${Number(costPct).toFixed(2)}%)` : '';
      parts.push(`Costs: ${costUsdText}${costPctText}`);
    }
    if (barsHeld != null) {
      parts.push(`Held: ${Number(barsHeld)}`);
    }
    return parts.length ? parts.join(" | ") : null;
  };

  const decisionMarkers = useMemo(
    () => (markers || []).filter(isDecisionMarker),
    [markers]
  );
  const eventMarkers = useMemo(
    () => (markers || []).filter((marker) => !isDecisionMarker(marker)),
    [markers]
  );
  const visibleMarkers = useMemo(
    () => (listTab === 'decisions' ? decisionMarkers : eventMarkers),
    [decisionMarkers, eventMarkers, listTab]
  );
  const renderedMarkers = useMemo(
    () => [...visibleMarkers].reverse().slice(0, visibleRows),
    [visibleMarkers, visibleRows]
  );
  const hasMoreRows = renderedMarkers.length < visibleMarkers.length;

  useEffect(() => {
    if (!selectedMarker) return;
    const reversed = [...visibleMarkers].reverse();
    const selectedIndex = reversed.findIndex((marker) => isSameMarker(selectedMarker, marker));
    if (selectedIndex < 0) return;
    const neededRows = selectedIndex + 1;
    setVisibleRows((prev) =>
      prev >= neededRows ? prev : Math.min(visibleMarkers.length, neededRows + 20)
    );
  }, [
    selectedMarker?.id,
    selectedMarker?.timestamp,
    selectedMarker?.time,
    selectedMarker?.marker_type,
    visibleMarkers.length,
    listTab,
  ]);

  useEffect(() => {
    if (!selectedMarker || isDetailFullscreen) return;
    const markerIdentity = getMarkerIdentity(selectedMarker);
    const keyChanged =
      autoScrollStateRef.current.markerIdentity !== markerIdentity ||
      autoScrollStateRef.current.listTab !== listTab;
    let matchedNode = null;

    for (let idx = 0; idx < renderedMarkers.length; idx += 1) {
      const marker = renderedMarkers[idx];
      if (!isSameMarker(selectedMarker, marker)) continue;
      const key = getMarkerKey(marker, idx);
      matchedNode = itemRefs.current.get(key) || null;
      break;
    }

    if (!matchedNode || !matchedNode.scrollIntoView) {
      if (keyChanged) {
        autoScrollStateRef.current = { markerIdentity, listTab, done: false };
      }
      return;
    }

    if (!keyChanged && autoScrollStateRef.current.done) return;
    matchedNode.scrollIntoView({ block: 'nearest', behavior: 'auto' });
    autoScrollStateRef.current = { markerIdentity, listTab, done: true };
  }, [
    selectedMarker?.id,
    selectedMarker?.timestamp,
    selectedMarker?.time,
    selectedMarker?.marker_type,
    renderedMarkers.length,
    listTab,
    isDetailFullscreen,
  ]);

  if (!markers || markers.length === 0) {
    return (
      <div className="decision-list">
        <div className="empty-state">
          <div className="icon">📭</div>
          <p>
            {DECISION_LABELS[uiLanguage]?.[
              "No decisions yet. Start the backtest to see trading decisions appear here."
            ] || "No decisions yet. Start the backtest to see trading decisions appear here."}
          </p>
        </div>
      </div>
    );
  }

  const selectedEventTime = toUnixSeconds(selectedMarker?.time ?? selectedMarker?.timestamp);
  const selectedTicker = selectedMarker?.ticker ?? selectedMarker?.details?.ticker;
  const selectedRunId = selectedMarker?.run_id ?? selectedMarker?.details?.run_id;
  
  // Prepare metadata for rendering
  const details = selectedMarker?.details || {};
  const metadata = details.metadata || {};
  const l2Diagnostics = extractL2Diagnostics(selectedMarker, details, metadata);
  const intradayLevels = extractIntradayLevels(selectedMarker, details, metadata);
  const levelContext = extractLevelContext(selectedMarker, details, metadata);
  const entryQualityDiagnostics = extractEntryQualityDiagnostics(selectedMarker, details, metadata);
  const decisionLog = extractDecisionLogPayload(selectedMarker, details, metadata);

  const t = (text) =>
    DECISION_LABELS[uiLanguage]?.[text] ??
    DECISION_LABELS.en?.[text] ??
    text;
  const renderYesNo = (flag) => (flag ? t("yes") : t("no"));
  const renderEnabled = (flag) => (flag ? t("Enabled") : t("Disabled"));
  const renderGateStatus = (flag) => (flag ? t("PASSED") : t("BLOCKED"));
  const renderCostLabel = (key) => {
    const mapped = COST_LABEL_BY_KEY[key];
    if (mapped) return mapped;
    return key.charAt(0).toUpperCase() + key.slice(1).replace('_', ' ');
  };
  const translateReasonToken = (rawToken) => {
    const token = String(rawToken || "").trim();
    if (!token) return token;
    const translations =
      DECISION_REASON_TRANSLATIONS[uiLanguage] ?? DECISION_REASON_TRANSLATIONS.en;
    const exact = translations[token];
    if (exact) return `${exact} (${token})`;

    const separators = [token.indexOf(":"), token.indexOf("(")].filter(
      (index) => index > 0,
    );
    if (!separators.length) return token;

    const splitIndex = Math.min(...separators);
    const prefix = token.slice(0, splitIndex);
    const translatedPrefix = translations[prefix];
    if (!translatedPrefix) return token;
    return `${translatedPrefix}${token.slice(splitIndex)} (${token})`;
  };
  const renderReasonValue = (value) => {
    const raw = String(value || "").trim();
    if (!raw) return "n/a";
    return raw
      .split("|")
      .map((token) => translateReasonToken(token))
      .join(" | ");
  };
  const detailSignalMetadata = isObjectRecord(details?.signal_metadata) ? details.signal_metadata : null;
  const detailMarketContext = isObjectRecord(details?.market_context) ? details.market_context : null;
  const riskControlsResolution = resolveRiskControls({
    details,
    signalMetadata: detailSignalMetadata,
    marketContext: detailMarketContext,
  });
  const contextRiskResolution = resolveContextRisk({
    details,
    signalMetadata: detailSignalMetadata,
    marketContext: detailMarketContext,
    riskControls: riskControlsResolution.value,
  });
  const breakEvenResolution = resolveBreakEven({
    details,
    signalMetadata: detailSignalMetadata,
    marketContext: detailMarketContext,
  });
  const contextRiskFieldSource = (fieldName) =>
    contextRiskResolution.sourcePath === "n/a"
      ? "context_risk (unavailable)"
      : `${contextRiskResolution.sourcePath}.${fieldName}`;
  const breakEvenSourcePath = String(
    decisionLog.payload?.break_even_source_path || breakEvenResolution.sourcePath || "n/a",
  );
  const breakEvenPayload = isObjectRecord(decisionLog.payload?.break_even)
    ? decisionLog.payload.break_even
    : null;
  const breakEvenComputed = isObjectRecord(breakEvenPayload?.computed_break_even)
    ? breakEvenPayload.computed_break_even
    : null;
  const breakEvenBuffer = isObjectRecord(breakEvenComputed?.buffer)
    ? breakEvenComputed.buffer
    : null;
  const breakEvenFieldSource = (fieldName) =>
    breakEvenSourcePath === "n/a"
      ? "break_even (unavailable)"
      : `${breakEvenSourcePath}.${fieldName}`;
  const formatPctValue = (value, digits = 4) => {
    const numeric = toFiniteNumber(value);
    return numeric == null ? "n/a" : `${numeric.toFixed(digits)}%`;
  };
  const translateBreakEvenToken = (rawToken) => {
    const token = String(rawToken || "").trim();
    if (!token) return token;
    const translations =
      BREAK_EVEN_TRIGGER_TRANSLATIONS[uiLanguage] ??
      BREAK_EVEN_TRIGGER_TRANSLATIONS.en;
    const mapped = translations[token];
    return mapped ? `${mapped} (${token})` : token;
  };
  const renderBreakEvenTrigger = (rawValue) => {
    const raw = String(rawValue || "").trim();
    if (!raw) return "n/a";
    return raw
      .split("|")
      .map((token) => translateBreakEvenToken(token))
      .join(" | ");
  };
  const renderBreakEvenProof = (payload) => {
    if (!isObjectRecord(payload)) return "n/a";
    const levels = isObjectRecord(payload.levels_proof) ? payload.levels_proof : null;
    const l2 = isObjectRecord(payload.l2_proof) ? payload.l2_proof : null;
    if (!levels && !l2) return "n/a";
    const parts = [];
    if (levels) {
      const levelState = levels.passed ? "pass" : "fail";
      const levelNoGo = levels.no_go_blocked ? "/no-go" : "";
      parts.push(`levels:${levelState}${levelNoGo}`);
    }
    if (l2) {
      parts.push(`l2:${l2.passed ? "pass" : "fail"}`);
    }
    return parts.join(" | ") || "n/a";
  };
  const breakEvenStopDisplayValue = toFiniteNumber(
    breakEvenComputed?.updated_stop_loss ??
    breakEvenComputed?.stop_level ??
    breakEvenPayload?.stop_loss,
  );
  const breakEvenStopSource =
    breakEvenComputed?.updated_stop_loss != null
      ? breakEvenFieldSource("computed_break_even.updated_stop_loss")
      : breakEvenComputed?.stop_level != null
        ? breakEvenFieldSource("computed_break_even.stop_level")
        : breakEvenPayload?.stop_loss != null
          ? breakEvenFieldSource("stop_loss")
          : breakEvenFieldSource("computed_break_even.stop_level");
  const breakEvenAntiSpikeSummary = breakEvenPayload
    ? `${Number(breakEvenPayload.anti_spike_bars_remaining || 0)} bars / ${Number(
        breakEvenPayload.anti_spike_consecutive_hits || 0,
      )}/${Number(
        breakEvenPayload.anti_spike_consecutive_hits_required || 0,
      )} hits / closeBeyond=${breakEvenPayload.anti_spike_require_close_beyond ? "true" : "false"}`
    : "n/a";
  const describePathPresence = (value) => {
    if (isObjectRecord(value)) return uiLanguage === "en" ? "object" : "objekt";
    if (value === null) return "null";
    if (value === undefined) return uiLanguage === "en" ? "missing" : "chýba";
    if (Array.isArray(value)) return `${uiLanguage === "en" ? "array" : "pole"}(${value.length})`;
    return String(value);
  };
  const isRuntimeMissing = (value) => {
    if (value === null || value === undefined) return true;
    if (typeof value !== "string") return false;
    const normalized = value.trim().toLowerCase();
    return (
      normalized === "" ||
      normalized === "n/a" ||
      normalized === "na" ||
      normalized === "null" ||
      normalized === "undefined"
    );
  };
  const numericEntryPrice = toFiniteNumber(details?.entry_price);
  const numericStopLoss = toFiniteNumber(details?.stop_loss);
  const numericTakeProfit = toFiniteNumber(details?.take_profit);
  const fallbackRiskPct =
    numericEntryPrice !== null &&
    numericStopLoss !== null &&
    numericEntryPrice !== 0
      ? (Math.abs(numericEntryPrice - numericStopLoss) / Math.abs(numericEntryPrice)) * 100
      : null;
  const fallbackApproxRr =
    numericEntryPrice !== null &&
    numericStopLoss !== null &&
    numericTakeProfit !== null &&
    Math.abs(numericEntryPrice - numericStopLoss) > 0
      ? Math.abs(numericTakeProfit - numericEntryPrice) /
        Math.abs(numericEntryPrice - numericStopLoss)
      : null;
  const buildContextRiskMissingLines = (fieldKey) => {
    const lines = [];
    lines.push(
      uiLanguage === "en"
        ? "Why n/a: context_risk field is unavailable for this marker."
        : "Prečo n/a: pole context_risk nie je pre tento marker dostupné.",
    );
    lines.push(
      uiLanguage === "en"
        ? `Resolved context_risk source: ${contextRiskResolution.sourcePath}`
        : `Nájdený zdroj context_risk: ${contextRiskResolution.sourcePath}`,
    );

    const checkedPaths = contextRiskResolution.candidates
      .slice(0, 7)
      .map((candidate) => `- ${candidate.path}: ${describePathPresence(candidate.value)}`);
    if (checkedPaths.length) {
      lines.push(uiLanguage === "en" ? "Checked paths:" : "Kontrolované cesty:");
      lines.push(...checkedPaths);
    }

    const riskControls = riskControlsResolution.value;
    if (isObjectRecord(riskControls)) {
      const summaryBits = [];
      if (riskControls.stop_loss_mode != null) {
        summaryBits.push(`stop_loss_mode=${riskControls.stop_loss_mode}`);
      }
      if (riskControls.fixed_stop_loss_pct != null) {
        summaryBits.push(`fixed_stop_loss_pct=${formatTooltipRuntimeValue(riskControls.fixed_stop_loss_pct)}%`);
      }
      if (riskControls.effective_stop_loss != null) {
        summaryBits.push(`effective_stop_loss=${formatTooltipRuntimeValue(riskControls.effective_stop_loss)}`);
      }
      if (riskControls.strategy_stop_loss != null) {
        summaryBits.push(`strategy_stop_loss=${formatTooltipRuntimeValue(riskControls.strategy_stop_loss)}`);
      }
      if (summaryBits.length) {
        lines.push(
          uiLanguage === "en"
            ? `Related risk_controls (${riskControlsResolution.sourcePath}): ${summaryBits.join(", ")}`
            : `Súvisiace risk_controls (${riskControlsResolution.sourcePath}): ${summaryBits.join(", ")}`,
        );
      }
    }

    if (fieldKey === "risk_pct" && fallbackRiskPct !== null) {
      lines.push(
        uiLanguage === "en"
          ? `Fallback computed risk% from entry/SL: ${fallbackRiskPct.toFixed(4)}%`
          : `Fallback výpočet rizika z entry/SL: ${fallbackRiskPct.toFixed(4)}%`,
      );
    }
    if (fieldKey === "effective_rr" && fallbackApproxRr !== null) {
      lines.push(
        uiLanguage === "en"
          ? `Approx RR from entry/SL/TP (fallback): ${fallbackApproxRr.toFixed(4)}`
          : `Približné RR z entry/SL/TP (fallback): ${fallbackApproxRr.toFixed(4)}`,
      );
    }
    if (fieldKey === "tp_reason" && numericTakeProfit !== null) {
      lines.push(
        uiLanguage === "en"
          ? "TP value exists, but TP reason token is absent in context_risk."
          : "TP hodnota existuje, ale dôvod TP token v context_risk chýba.",
      );
    }
    if (fieldKey === "sl_reason" && numericStopLoss !== null) {
      lines.push(
        uiLanguage === "en"
          ? "SL value exists, but SL reason token is absent in context_risk."
          : "SL hodnota existuje, ale dôvod SL token v context_risk chýba.",
      );
    }

    return lines;
  };
  const buildBreakEvenMissingLines = (fieldKey) => {
    const lines = [];
    lines.push(
      uiLanguage === "en"
        ? "Why n/a: break_even field is unavailable for this marker."
        : "Prečo n/a: pole break_even nie je pre tento marker dostupné.",
    );
    lines.push(
      uiLanguage === "en"
        ? `Resolved break_even source: ${breakEvenSourcePath}`
        : `Nájdený zdroj break_even: ${breakEvenSourcePath}`,
    );

    const checkedPaths = (breakEvenResolution.candidates || [])
      .slice(0, 7)
      .map((candidate) => `- ${candidate.path}: ${describePathPresence(candidate.value)}`);
    if (checkedPaths.length) {
      lines.push(uiLanguage === "en" ? "Checked paths:" : "Kontrolované cesty:");
      lines.push(...checkedPaths);
    }

    const exitReason = String(details?.exit_reason || "").trim().toLowerCase();
    if (exitReason === "breakeven_stop") {
      lines.push(
        uiLanguage === "en"
          ? "Exit reason is breakeven_stop, but BE diagnostics payload is missing."
          : "Exit reason je breakeven_stop, ale diagnostický BE payload chýba.",
      );
    }
    if (fieldKey === "computed_break_even" && breakEvenPayload?.activation_reason) {
      lines.push(
        uiLanguage === "en"
          ? `Activation trigger exists: ${renderBreakEvenTrigger(breakEvenPayload.activation_reason)}`
          : `Trigger aktivácie existuje: ${renderBreakEvenTrigger(breakEvenPayload.activation_reason)}`,
      );
    }

    return lines;
  };
  const buildVwapFlowValueLines = (value, sourcePath) => {
    if (value === null || value === undefined) {
      return [
        uiLanguage === "en"
          ? "Why n/a: selected flow snapshot has no vwap_execution_flow metric."
          : "Prečo n/a: zvolený flow snapshot neobsahuje metriku vwap_execution_flow.",
      ];
    }
    if (Number(value) === 0) {
      return [
        uiLanguage === "en"
          ? "0.000 is a valid neutral reading, not a missing value."
          : "0.000 je validná neutrálna hodnota, nie chýbajúci údaj.",
        uiLanguage === "en"
          ? `Metric source: ${sourcePath || "n/a"}`
          : `Zdroj metriky: ${sourcePath || "n/a"}`,
      ];
    }
    return [];
  };
  const tooltipLocaleText =
    uiLanguage === "en"
      ? {
          value: "Current value",
          source: "Resolved source",
          l2Title: "L2 source selection",
          chosen: "Chosen source",
          unavailable: "Value not present on selected source",
        }
      : {
          value: "Aktuálna hodnota",
          source: "Použitý zdroj",
          l2Title: "Výber L2 zdroja",
          chosen: "Zvolený zdroj",
          unavailable: "Hodnota nie je na zvolenom zdroji",
        };
  const baseTooltipFor = (label) => {
    const baseLabel = resolveTooltipBaseLabel(label);
    return (
      DECISION_TOOLTIPS[uiLanguage]?.[baseLabel] ??
      DECISION_TOOLTIPS.sk?.[baseLabel] ??
      DECISION_TOOLTIPS.sk?._default ??
      ""
    );
  };
  const l2CandidateFlowLines = (l2Diagnostics.candidateDiagnostics || []).map((candidate) => {
    const metrics =
      candidate.availableMetrics?.length > 0
        ? candidate.availableMetrics.join(", ")
        : (uiLanguage === "en" ? "no metrics" : "žiadne metriky");
    const selectedSuffix =
      candidate.sourcePath === l2Diagnostics.sourcePath
        ? ` [${uiLanguage === "en" ? "used" : "použité"}]`
        : "";
    return `- ${candidate.sourcePath}: ${candidate.score}/${L2_DIAGNOSTIC_KEYS.length} (${metrics})${selectedSuffix}`;
  });

  const runtimeTooltipByLabel = {};
  const setRuntimeTooltip = (label, value, source, flow = []) => {
    runtimeTooltipByLabel[label] = {
      value,
      source,
      flow: Array.isArray(flow) ? flow.filter(Boolean) : [flow].filter(Boolean),
    };
  };

  setRuntimeTooltip("Event Type", selectedMarker?.marker_type ?? "n/a", "marker.marker_type");
  setRuntimeTooltip(
    "Time",
    selectedMarker?.timestamp ?? selectedMarker?.time ?? "n/a",
    "marker.timestamp / marker.time",
  );
  setRuntimeTooltip("Price", selectedMarker?.price ?? "n/a", "marker.price");
  setRuntimeTooltip("Side", selectedMarker?.side ?? "n/a", "marker.side");
  setRuntimeTooltip(
    "Strategy (Entry)",
    selectedMarker?.strategy ?? metadata?.strategy ?? "Unknown",
    selectedMarker?.strategy ? "marker.strategy" : "details.metadata.strategy",
  );
  setRuntimeTooltip(
    "Confidence",
    selectedMarker?.confidence ?? "n/a",
    "marker.confidence",
    uiLanguage === "en"
      ? "Displayed as percentage in UI."
      : "V UI sa zobrazuje ako percento.",
  );
  setRuntimeTooltip("Stop Loss", details?.stop_loss ?? "n/a", "details.stop_loss");
  setRuntimeTooltip("Take Profit", details?.take_profit ?? "n/a", "details.take_profit");
  setRuntimeTooltip("R:R Ratio", details?.risk_reward ?? "n/a", "details.risk_reward");
  setRuntimeTooltip("Exit Reason", details?.exit_reason ?? "n/a", "details.exit_reason");
  setRuntimeTooltip(
    "PnL",
    resolvePnlPct(details, details?.pnl_dollars ?? details?.pnl_usd),
    "details.pnl_pct (fallback: pnl_dollars/position_notional_usd, then account default)",
  );
  setRuntimeTooltip(
    "PnL $",
    details?.pnl_dollars ?? details?.pnl_usd ?? "n/a",
    "details.pnl_dollars / details.pnl_usd",
  );
  setRuntimeTooltip("Bars Held", details?.bars_held ?? "n/a", "details.bars_held");
  setRuntimeTooltip("Reasoning", details?.reasoning ?? "n/a", "details.reasoning");

  Object.entries(details?.costs || {}).forEach(([costKey, costValue]) => {
    setRuntimeTooltip(
      renderCostLabel(costKey),
      costValue,
      `details.costs.${costKey}`,
      uiLanguage === "en"
        ? "Included in net trade PnL."
        : "Táto položka je zahrnutá v net PnL obchodu.",
    );
  });

  const l2SourceFlowNotes = [
    `${tooltipLocaleText.chosen}: ${l2Diagnostics.sourcePath || "n/a"}`,
    `${tooltipLocaleText.l2Title}:`,
    ...l2CandidateFlowLines,
  ];
  setRuntimeTooltip(
    "Flow Score",
    l2Diagnostics.flowScore,
    l2Diagnostics.sourcePath,
    l2SourceFlowNotes,
  );
  setRuntimeTooltip(
    "Signed Aggression",
    l2Diagnostics.signedAggression,
    l2Diagnostics.sourcePath,
    l2SourceFlowNotes,
  );
  setRuntimeTooltip(
    "L2 Aggression Z",
    l2Diagnostics.l2AggressionZ,
    l2Diagnostics.sourcePath,
    l2SourceFlowNotes,
  );
  setRuntimeTooltip(
    "L2 Book Pressure Z",
    l2Diagnostics.l2BookPressureZ,
    l2Diagnostics.sourcePath,
    l2SourceFlowNotes,
  );
  setRuntimeTooltip(
    "Absorption Rate",
    l2Diagnostics.absorptionRate,
    l2Diagnostics.sourcePath,
    l2SourceFlowNotes,
  );
  setRuntimeTooltip(
    "Large Trader Activity",
    l2Diagnostics.largeTraderActivity,
    l2Diagnostics.sourcePath,
    l2SourceFlowNotes,
  );
  setRuntimeTooltip(
    "VWAP Execution Flow (L2 Diagnostics)",
    l2Diagnostics.vwapExecutionFlow,
    l2Diagnostics.sourcePath,
    [
      ...l2SourceFlowNotes,
      ...buildVwapFlowValueLines(
        l2Diagnostics.vwapExecutionFlow,
        l2Diagnostics.sourcePath || "n/a",
      ),
    ],
  );
  setRuntimeTooltip(
    "L2 Source",
    l2Diagnostics.sourcePath,
    "resolved in resolveL2Source()",
    l2SourceFlowNotes,
  );
  setRuntimeTooltip(
    "Sweep Detected",
    l2Diagnostics.sweepDetected,
    l2Diagnostics.sourcePath,
    l2SourceFlowNotes,
  );

  setRuntimeTooltip("Tracker", intradayLevels.enabled, "details.intraday_levels.enabled");
  setRuntimeTooltip(
    "Active / Tested / Broken",
    `${Number(intradayLevels.stats.active_levels || 0)} / ${Number(intradayLevels.stats.tested_levels || 0)} / ${Number(intradayLevels.stats.broken_levels || 0)}`,
    "details.intraday_levels.stats.*",
  );
  setRuntimeTooltip(
    "Bounce / Break Events",
    `${Number(intradayLevels.stats.bounce_events || 0)} / ${Number(intradayLevels.stats.break_events || 0)}`,
    "details.intraday_levels.stats.bounce_events / break_events",
  );
  setRuntimeTooltip(
    "POC",
    intradayLevels.volumeProfile.poc_price ?? "n/a",
    "details.intraday_levels.volume_profile.poc_price",
  );
  setRuntimeTooltip(
    "Value Area",
    intradayLevels.volumeProfile.value_area_low != null &&
      intradayLevels.volumeProfile.value_area_high != null
      ? `${intradayLevels.volumeProfile.value_area_low} - ${intradayLevels.volumeProfile.value_area_high}`
      : "n/a",
    "details.intraday_levels.volume_profile.value_area_low / value_area_high",
  );
  setRuntimeTooltip("Latest Event", intradayLevels.latestEvent ?? "n/a", "details.intraday_levels.latest_event");

  setRuntimeTooltip("Status", levelContext.payload?.passed, "details.level_context.passed");
  setRuntimeTooltip(
    "Strategy (Gate)",
    levelContext.payload?.strategy_key ?? "n/a",
    "details.level_context.strategy_key",
  );
  setRuntimeTooltip("Gate Reason", levelContext.payload?.reason ?? "n/a", "details.level_context.reason");
  setRuntimeTooltip(
    "Near Tested Levels (Gate)",
    levelContext.payload?.stats?.near_tested_levels_count ?? 0,
    "details.level_context.stats.near_tested_levels_count",
  );
  setRuntimeTooltip(
    "Value Area Position",
    levelContext.payload?.volume_profile?.value_area_position ?? "n/a",
    "details.level_context.volume_profile.value_area_position",
  );
  setRuntimeTooltip(
    "POC On Trade Side (Gate)",
    levelContext.payload?.volume_profile?.poc_on_trade_side,
    "details.level_context.volume_profile.poc_on_trade_side",
  );
  setRuntimeTooltip(
    "Room To Next Opposite Level",
    levelContext.payload?.room_to_next_opposite_level_pct ?? "n/a",
    "details.level_context.room_to_next_opposite_level_pct",
  );
  setRuntimeTooltip("Fail Reasons", levelContext.reasons, "details.level_context.reasons");

  setRuntimeTooltip(
    "First-Bar Stop Loss",
    entryQualityDiagnostics.payload?.is_first_bar_stop_loss,
    "details.entry_quality_diagnostics.is_first_bar_stop_loss",
  );
  setRuntimeTooltip(
    "Stop Distance",
    entryQualityDiagnostics.payload?.stop_distance_pct ?? "n/a",
    "details.entry_quality_diagnostics.stop_distance_pct",
  );
  setRuntimeTooltip(
    "VWAP Distance",
    entryQualityDiagnostics.payload?.vwap_distance_pct ?? "n/a",
    "details.entry_quality_diagnostics.vwap_distance_pct",
  );
  setRuntimeTooltip(
    "Confluence Score",
    entryQualityDiagnostics.payload?.near_confluence_score ?? "n/a",
    "details.entry_quality_diagnostics.near_confluence_score",
  );
  setRuntimeTooltip(
    "Near Tested Levels (Entry Timing)",
    entryQualityDiagnostics.payload?.near_tested_levels_count ?? "n/a",
    "details.entry_quality_diagnostics.near_tested_levels_count",
  );
  setRuntimeTooltip(
    "POC On Trade Side (Entry Timing)",
    entryQualityDiagnostics.payload?.poc_on_trade_side,
    "details.entry_quality_diagnostics.poc_on_trade_side",
  );
  setRuntimeTooltip("Diagnosis Tags", entryQualityDiagnostics.tags, "details.entry_quality_diagnostics.first_bar_stop_tags");

  setRuntimeTooltip(
    "Decision Action",
    decisionLog.payload?.decision_state?.action ?? "n/a",
    "details.market_context.decision_state.action",
  );
  setRuntimeTooltip(
    "Decision Phase",
    decisionLog.payload?.decision_state?.phase ?? "n/a",
    "details.market_context.decision_state.phase",
  );
  setRuntimeTooltip(
    "Regime / Micro",
    `${decisionLog.payload?.decision_state?.regime || "n/a"} / ${decisionLog.payload?.decision_state?.micro_regime || "n/a"}`,
    "details.market_context.decision_state.regime / micro_regime",
  );
  setRuntimeTooltip(
    "Selected Strategy",
    decisionLog.payload?.decision_state?.selected_strategy || selectedMarker?.strategy || "n/a",
    "details.market_context.decision_state.selected_strategy",
  );
  setRuntimeTooltip(
    "SL Reason",
    decisionLog.payload?.context_risk?.sl_reason ?? "n/a",
    contextRiskFieldSource("sl_reason"),
    decisionLog.payload?.context_risk?.sl_reason
      ? [
          uiLanguage === "en"
            ? `Interpreted: ${renderReasonValue(decisionLog.payload.context_risk.sl_reason)}`
            : `Interpretované: ${renderReasonValue(decisionLog.payload.context_risk.sl_reason)}`,
        ]
      : buildContextRiskMissingLines("sl_reason"),
  );
  setRuntimeTooltip(
    "TP Reason",
    decisionLog.payload?.context_risk?.tp_reason ?? "n/a",
    contextRiskFieldSource("tp_reason"),
    [
      decisionLog.payload?.context_risk?.tp_reason &&
      String(decisionLog.payload.context_risk.tp_reason).includes("fallback_original")
        ? (uiLanguage === "en"
          ? "TP stayed at original strategy target (no context override)."
          : "TP ostal na pôvodnom targete stratégie (bez context override).")
        : "",
      decisionLog.payload?.context_risk?.tp_reason
        ? (uiLanguage === "en"
          ? `Interpreted: ${renderReasonValue(decisionLog.payload.context_risk.tp_reason)}`
          : `Interpretované: ${renderReasonValue(decisionLog.payload.context_risk.tp_reason)}`)
        : "",
      ...(!decisionLog.payload?.context_risk?.tp_reason ? buildContextRiskMissingLines("tp_reason") : []),
    ],
  );
  setRuntimeTooltip(
    "Effective RR",
    decisionLog.payload?.context_risk?.effective_rr ?? "n/a",
    contextRiskFieldSource("effective_rr"),
    decisionLog.payload?.context_risk?.room_pct != null &&
    decisionLog.payload?.context_risk?.risk_pct != null
      ? [
          uiLanguage === "en"
            ? `Formula: room_pct (${formatTooltipRuntimeValue(decisionLog.payload.context_risk.room_pct)}) / risk_pct (${formatTooltipRuntimeValue(decisionLog.payload.context_risk.risk_pct)})`
            : `Vzorec: room_pct (${formatTooltipRuntimeValue(decisionLog.payload.context_risk.room_pct)}) / risk_pct (${formatTooltipRuntimeValue(decisionLog.payload.context_risk.risk_pct)})`,
        ]
      : (isRuntimeMissing(decisionLog.payload?.context_risk?.effective_rr)
        ? buildContextRiskMissingLines("effective_rr")
        : []),
  );
  setRuntimeTooltip(
    "Risk %",
    decisionLog.payload?.context_risk?.risk_pct ?? "n/a",
    contextRiskFieldSource("risk_pct"),
    [
      (details?.entry_price != null && details?.stop_loss != null)
        ? (
          uiLanguage === "en"
            ? `Formula: abs(entry (${formatTooltipRuntimeValue(details.entry_price)}) - SL (${formatTooltipRuntimeValue(details.stop_loss)})) / entry * 100`
            : `Vzorec: abs(entry (${formatTooltipRuntimeValue(details.entry_price)}) - SL (${formatTooltipRuntimeValue(details.stop_loss)})) / entry * 100`
        )
        : "",
      ...(isRuntimeMissing(decisionLog.payload?.context_risk?.risk_pct)
        ? buildContextRiskMissingLines("risk_pct")
        : []),
    ],
  );
  setRuntimeTooltip(
    "Break-even State",
    breakEvenPayload?.state ?? "n/a",
    breakEvenFieldSource("state"),
    [
      breakEvenPayload?.active != null
        ? (
          uiLanguage === "en"
            ? `Active: ${formatTooltipRuntimeValue(breakEvenPayload.active)}`
            : `Aktívne: ${formatTooltipRuntimeValue(breakEvenPayload.active)}`
        )
        : "",
      breakEvenPayload?.arm_bar_index != null
        ? (
          uiLanguage === "en"
            ? `Arm bar: ${formatTooltipRuntimeValue(breakEvenPayload.arm_bar_index)}`
            : `Arm bar: ${formatTooltipRuntimeValue(breakEvenPayload.arm_bar_index)}`
        )
        : "",
      breakEvenPayload?.move_bar_index != null
        ? (
          uiLanguage === "en"
            ? `Move bar: ${formatTooltipRuntimeValue(breakEvenPayload.move_bar_index)}`
            : `Move bar: ${formatTooltipRuntimeValue(breakEvenPayload.move_bar_index)}`
        )
        : "",
      ...(!breakEvenPayload ? buildBreakEvenMissingLines("state") : []),
    ],
  );
  setRuntimeTooltip(
    "Break-even Trigger",
    renderBreakEvenTrigger(breakEvenPayload?.activation_reason),
    breakEvenFieldSource("activation_reason"),
    [
      breakEvenPayload?.activation_reason
        ? (
          uiLanguage === "en"
            ? `Raw token(s): ${breakEvenPayload.activation_reason}`
            : `Raw token(y): ${breakEvenPayload.activation_reason}`
        )
        : "",
      breakEvenPayload?.movement_passed != null
        ? `movement_passed=${formatTooltipRuntimeValue(breakEvenPayload.movement_passed)}`
        : "",
      breakEvenPayload?.proof_passed != null
        ? `proof_passed=${formatTooltipRuntimeValue(breakEvenPayload.proof_passed)}`
        : "",
      breakEvenPayload?.no_go_blocked != null
        ? `no_go_blocked=${formatTooltipRuntimeValue(breakEvenPayload.no_go_blocked)}`
        : "",
      ...(!breakEvenPayload?.activation_reason ? buildBreakEvenMissingLines("activation_reason") : []),
    ],
  );
  setRuntimeTooltip(
    "Break-even Proof",
    renderBreakEvenProof(breakEvenPayload),
    `${breakEvenFieldSource("levels_proof")} | ${breakEvenFieldSource("l2_proof")}`,
    [
      isObjectRecord(breakEvenPayload?.levels_proof)
        ? `levels: passed=${formatTooltipRuntimeValue(breakEvenPayload.levels_proof.passed)}; no_go=${formatTooltipRuntimeValue(breakEvenPayload.levels_proof.no_go_blocked)}; close_confirmed=${formatTooltipRuntimeValue(breakEvenPayload.levels_proof.close_confirmed)}`
        : "",
      isObjectRecord(breakEvenPayload?.l2_proof)
        ? `l2: passed=${formatTooltipRuntimeValue(breakEvenPayload.l2_proof.passed)}; signed=${formatTooltipRuntimeValue(breakEvenPayload.l2_proof.directional_signed_aggression)}; imbalance=${formatTooltipRuntimeValue(breakEvenPayload.l2_proof.directional_imbalance)}`
        : "",
      ...(isObjectRecord(breakEvenPayload?.levels_proof) || isObjectRecord(breakEvenPayload?.l2_proof)
        ? []
        : buildBreakEvenMissingLines("proof")),
    ],
  );
  setRuntimeTooltip(
    "Break-even Stop",
    breakEvenStopDisplayValue ?? "n/a",
    breakEvenStopSource,
    [
      breakEvenComputed?.entry_price != null
        ? (
          uiLanguage === "en"
            ? `Entry: ${formatTooltipRuntimeValue(breakEvenComputed.entry_price)}`
            : `Entry: ${formatTooltipRuntimeValue(breakEvenComputed.entry_price)}`
        )
        : "",
      breakEvenComputed?.total_costs_pct != null
        ? (
          uiLanguage === "en"
            ? `Total costs %: ${formatPctValue(breakEvenComputed.total_costs_pct, 5)}`
            : `Celkové costs %: ${formatPctValue(breakEvenComputed.total_costs_pct, 5)}`
        )
        : "",
      breakEvenBuffer?.selected_buffer_pct != null
        ? (
          uiLanguage === "en"
            ? `Selected buffer %: ${formatPctValue(breakEvenBuffer.selected_buffer_pct, 5)}`
            : `Zvolený buffer %: ${formatPctValue(breakEvenBuffer.selected_buffer_pct, 5)}`
        )
        : "",
      ...((breakEvenStopDisplayValue == null) ? buildBreakEvenMissingLines("computed_break_even") : []),
    ],
  );
  setRuntimeTooltip(
    "Break-even Costs %",
    breakEvenComputed?.total_costs_pct ?? "n/a",
    breakEvenFieldSource("computed_break_even.total_costs_pct"),
    [
      breakEvenComputed?.base_costs_pct != null
        ? `base_costs_pct=${formatPctValue(breakEvenComputed.base_costs_pct, 5)}`
        : "",
      breakEvenComputed?.spread_component_pct != null
        ? `spread_component_pct=${formatPctValue(breakEvenComputed.spread_component_pct, 5)}`
        : "",
      breakEvenComputed?.spread_bps != null
        ? `spread_bps=${formatTooltipRuntimeValue(breakEvenComputed.spread_bps)}`
        : "",
      ...(breakEvenComputed?.total_costs_pct == null
        ? buildBreakEvenMissingLines("computed_break_even.total_costs_pct")
        : []),
    ],
  );
  setRuntimeTooltip(
    "Break-even Buffer %",
    breakEvenBuffer?.selected_buffer_pct ?? "n/a",
    breakEvenFieldSource("computed_break_even.buffer.selected_buffer_pct"),
    [
      breakEvenBuffer?.base_buffer_pct != null
        ? `base=${formatPctValue(breakEvenBuffer.base_buffer_pct, 5)}`
        : "",
      breakEvenBuffer?.min_buffer_pct != null
        ? `min=${formatPctValue(breakEvenBuffer.min_buffer_pct, 5)}`
        : "",
      breakEvenBuffer?.atr_buffer_pct != null
        ? `atr_1m=${formatPctValue(breakEvenBuffer.atr_buffer_pct, 5)}`
        : "",
      breakEvenBuffer?.atr5_buffer_pct != null
        ? `atr_5m=${formatPctValue(breakEvenBuffer.atr5_buffer_pct, 5)}`
        : "",
      breakEvenBuffer?.tick_buffer_pct != null
        ? `tick=${formatPctValue(breakEvenBuffer.tick_buffer_pct, 5)}`
        : "",
      breakEvenBuffer?.selected_buffer_abs != null
        ? `selected_abs=${formatTooltipRuntimeValue(breakEvenBuffer.selected_buffer_abs)}`
        : "",
      ...(breakEvenBuffer?.selected_buffer_pct == null
        ? buildBreakEvenMissingLines("computed_break_even.buffer")
        : []),
    ],
  );
  setRuntimeTooltip(
    "Break-even Anti-Spike",
    breakEvenAntiSpikeSummary,
    `${breakEvenFieldSource("anti_spike_bars_remaining")} | ${breakEvenFieldSource("anti_spike_consecutive_hits")} | ${breakEvenFieldSource("anti_spike_consecutive_hits_required")} | ${breakEvenFieldSource("anti_spike_require_close_beyond")}`,
    [
      breakEvenPayload?.anti_spike_bars_remaining != null
        ? `bars_remaining=${formatTooltipRuntimeValue(breakEvenPayload.anti_spike_bars_remaining)}`
        : "",
      breakEvenPayload?.anti_spike_consecutive_hits != null
        ? `hits=${formatTooltipRuntimeValue(breakEvenPayload.anti_spike_consecutive_hits)}`
        : "",
      breakEvenPayload?.anti_spike_consecutive_hits_required != null
        ? `required_hits=${formatTooltipRuntimeValue(breakEvenPayload.anti_spike_consecutive_hits_required)}`
        : "",
      breakEvenPayload?.anti_spike_require_close_beyond != null
        ? `require_close_beyond=${formatTooltipRuntimeValue(breakEvenPayload.anti_spike_require_close_beyond)}`
        : "",
      uiLanguage === "en"
        ? "Trigger rule: close-beyond OR required consecutive hits."
        : "Trigger pravidlo: close-beyond ALEBO required consecutive hits.",
      ...(!breakEvenPayload ? buildBreakEvenMissingLines("anti_spike") : []),
    ],
  );
  setRuntimeTooltip(
    "VWAP Execution Flow (Decision Log)",
    decisionLog.payload?.flow_snapshot?.vwap_execution_flow ?? "n/a",
    `decisionLog.payload.flow_snapshot.vwap_execution_flow (${l2Diagnostics.sourcePath || "n/a"})`,
    [
      ...l2SourceFlowNotes,
      ...buildVwapFlowValueLines(
        decisionLog.payload?.flow_snapshot?.vwap_execution_flow,
        l2Diagnostics.sourcePath || "n/a",
      ),
    ],
  );
  setRuntimeTooltip("Complete Decision Payload", "JSON payload", "decisionLog.payload");

  const runtimeTooltipFor = (label) => {
    const runtime =
      runtimeTooltipByLabel[label] ??
      runtimeTooltipByLabel[resolveTooltipBaseLabel(label)] ??
      null;
    if (!runtime) return "";
    const lines = [];
    lines.push(`${tooltipLocaleText.value}: ${formatTooltipRuntimeValue(runtime.value)}`);
    if (runtime.source) {
      lines.push(`${tooltipLocaleText.source}: ${runtime.source}`);
    }
    runtime.flow.forEach((line) => lines.push(line));
    return lines.join("\n");
  };
  const tooltipFor = (label) => {
    const base = baseTooltipFor(label);
    const runtime = runtimeTooltipFor(label);
    return [base, runtime].filter((part) => String(part || "").trim()).join("\n\n");
  };
  const resolveHelpTooltipPosition = (anchorRect) => {
    if (typeof window === "undefined") {
      return {
        top: anchorRect.bottom + 10,
        left: anchorRect.left,
        maxWidth: 520,
        placeAbove: false,
      };
    }
    const viewportWidth = Math.max(window.innerWidth || 0, 320);
    const viewportHeight = Math.max(window.innerHeight || 0, 320);
    const maxWidth = Math.min(520, Math.max(280, viewportWidth - 24));
    const horizontalPadding = 12;
    const idealLeft = anchorRect.left + (anchorRect.width / 2) - (maxWidth / 2);
    const left = Math.min(
      Math.max(horizontalPadding, idealLeft),
      Math.max(horizontalPadding, viewportWidth - maxWidth - horizontalPadding),
    );
    const placeAbove = anchorRect.bottom > viewportHeight * 0.72;
    const top = placeAbove ? Math.max(10, anchorRect.top - 10) : (anchorRect.bottom + 10);
    return { top, left, maxWidth, placeAbove };
  };
  const showHelpTooltip = (event, tooltipText, pinned = false) => {
    const text = String(tooltipText || "").trim();
    if (!text) return;
    const anchorRect = event.currentTarget.getBoundingClientRect();
    setActiveHelpTooltip({
      ...resolveHelpTooltipPosition(anchorRect),
      text,
      pinned,
    });
  };
  const hideHelpTooltip = () => {
    setActiveHelpTooltip((previous) => (previous?.pinned ? previous : null));
  };
  const togglePinnedHelpTooltip = (event, tooltipText) => {
    event.preventDefault();
    event.stopPropagation();
    const text = String(tooltipText || "").trim();
    if (!text) return;
    const anchorElement =
      event.currentTarget instanceof Element ? event.currentTarget : null;
    const nextPosition = anchorElement
      ? resolveHelpTooltipPosition(anchorElement.getBoundingClientRect())
      : { top: 12, left: 12, maxWidth: 420, placeAbove: false };
    setActiveHelpTooltip((previous) => {
      if (previous?.pinned && previous?.text === text) {
        return null;
      }
      return {
        ...nextPosition,
        text,
        pinned: true,
      };
    });
  };
  const renderDetailLabel = (label, tooltipLabelOrOptions = label, style = undefined) => {
    const optionsObject =
      tooltipLabelOrOptions &&
      typeof tooltipLabelOrOptions === "object" &&
      !Array.isArray(tooltipLabelOrOptions)
        ? tooltipLabelOrOptions
        : null;
    const tooltipLabel = optionsObject
      ? optionsObject.tooltipLabel || label
      : (tooltipLabelOrOptions || label);
    const effectiveStyle = optionsObject ? optionsObject.style : style;
    const runtimeOverride = optionsObject
      ? {
          value: optionsObject.runtimeValue,
          source: optionsObject.runtimeSource,
          flow: Array.isArray(optionsObject.runtimeFlow)
            ? optionsObject.runtimeFlow
            : [optionsObject.runtimeFlow].filter(Boolean),
        }
      : null;
    const tooltipText = runtimeOverride
      ? [
          baseTooltipFor(tooltipLabel),
          `${tooltipLocaleText.value}: ${formatTooltipRuntimeValue(runtimeOverride.value)}`,
          runtimeOverride.source ? `${tooltipLocaleText.source}: ${runtimeOverride.source}` : "",
          ...(runtimeOverride.flow || []),
        ]
          .filter((part) => String(part || "").trim())
          .join("\n\n")
      : tooltipFor(tooltipLabel);
    return (
      <span className="detail-label-with-tooltip">
        <button
          type="button"
          className="detail-label-trigger"
          aria-label={tooltipText}
          style={effectiveStyle}
          onMouseEnter={(event) => showHelpTooltip(event, tooltipText, false)}
          onMouseLeave={hideHelpTooltip}
          onFocus={(event) => showHelpTooltip(event, tooltipText, false)}
          onBlur={hideHelpTooltip}
          onClick={(event) => togglePinnedHelpTooltip(event, tooltipText)}
          onKeyDown={(event) => {
            if (event.key === "Enter" || event.key === " ") {
              togglePinnedHelpTooltip(event, tooltipText);
            }
            if (event.key === "Escape") {
              setActiveHelpTooltip(null);
            }
          }}
        >
          {t(label)}
        </button>
        <button
          type="button"
          className="detail-label-help"
          aria-label={tooltipText}
          aria-expanded={Boolean(activeHelpTooltip && activeHelpTooltip.text === tooltipText)}
          onMouseEnter={(event) => showHelpTooltip(event, tooltipText, false)}
          onMouseLeave={hideHelpTooltip}
          onFocus={(event) => showHelpTooltip(event, tooltipText, false)}
          onBlur={hideHelpTooltip}
          onClick={(event) => togglePinnedHelpTooltip(event, tooltipText)}
          onKeyDown={(event) => {
            if (event.key === "Enter" || event.key === " ") {
              togglePinnedHelpTooltip(event, tooltipText);
            }
            if (event.key === "Escape") {
              setActiveHelpTooltip(null);
            }
          }}
        >
          i
        </button>
      </span>
    );
  };
  
  // Helper to render sections
  const renderSectionHeader = (title) => (
    <div className="detail-item" style={{ gridColumn: '1 / -1', borderTop: '1px solid var(--border-color)', paddingTop: 'var(--spacing-sm)', marginTop: 'var(--spacing-xs)', marginBottom: 'var(--spacing-xs)' }}>
      {renderDetailLabel(title, title, { fontWeight: 600, color: 'var(--text-primary)' })}
    </div>
  );

  const renderDecisionDetail = (fullscreen = false) => (
    <div
      className={`decision-detail ${fullscreen ? 'fullscreen' : ''}`}
      onClick={(event) => {
        if (fullscreen) {
          event.stopPropagation();
        }
      }}
    >
      <div className="decision-detail-header">
        <h4>
          {getMarkerIcon(selectedMarker)} {renderTitle(selectedMarker)}
        </h4>
        <div className="decision-detail-header-actions">
          <div className="decision-language-toggle" title={t("Language")}>
            <button
              type="button"
              className={`btn btn-secondary decision-detail-expand-btn ${uiLanguage === "sk" ? "active" : ""}`}
              onClick={() => setUiLanguage("sk")}
            >
              SK
            </button>
            <button
              type="button"
              className={`btn btn-secondary decision-detail-expand-btn ${uiLanguage === "en" ? "active" : ""}`}
              onClick={() => setUiLanguage("en")}
            >
              EN
            </button>
          </div>
          <button
            type="button"
            className="btn btn-secondary decision-detail-expand-btn"
            onClick={() => setIsDetailFullscreen((prev) => !prev)}
            title={fullscreen ? t("Exit Full Screen") : t("Full Screen")}
          >
            {fullscreen ? t("Exit Full Screen") : t("Full Screen")}
          </button>
        </div>
      </div>
      <div className="decision-detail-tabs">
        <button
          className={`decision-detail-tab ${detailTab === 'details' ? 'active' : ''}`}
          onClick={() => setDetailTab('details')}
        >
          {t("Details")}
        </button>
        <button
          className={`decision-detail-tab ${detailTab === 'raw' ? 'active' : ''}`}
          onClick={() => setDetailTab('raw')}
        >
          {t("Raw")}
        </button>
        <button
          className={`decision-detail-tab ${detailTab === 'decision_log' ? 'active' : ''}`}
          onClick={() => setDetailTab('decision_log')}
        >
          {t("Decision Log")}
        </button>
      </div>
      {activeHelpTooltip?.pinned && (
        <div className="decision-help-inline" role="note">
          <div className="decision-help-inline-head">
            <strong>{uiLanguage === "en" ? "Tooltip detail" : "Detail tooltipu"}</strong>
            <button
              type="button"
              className="decision-help-inline-close"
              onClick={() => setActiveHelpTooltip(null)}
              aria-label={uiLanguage === "en" ? "Close tooltip detail" : "Zavrieť detail tooltipu"}
            >
              ×
            </button>
          </div>
          <pre className="decision-help-inline-body">{activeHelpTooltip.text}</pre>
        </div>
      )}
      {detailTab === 'details' && (
        <>
          <div className="detail-grid">
            {/* Basic Info */}
            <div className="detail-item">
              {renderDetailLabel("Event Type")}
              <span className="detail-value">{selectedMarker.marker_type || 'n/a'}</span>
            </div>
            <div className="detail-item">
              {renderDetailLabel("Time")}
              <span className="detail-value">
                {formatTime(selectedMarker.timestamp)}
              </span>
            </div>
            <div className="detail-item">
              {renderDetailLabel("Price")}
              <span className="detail-value">
                {formatPrice(selectedMarker.price)}
              </span>
            </div>
            {selectedMarker.side && (
              <div className="detail-item">
                {renderDetailLabel("Side")}
                <span className="detail-value" style={{ 
                  color: selectedMarker.side === 'long' ? 'var(--accent-green)' : 'var(--accent-red)',
                  fontWeight: 700 
                }}>
                  {String(selectedMarker.side).toUpperCase()}
                </span>
              </div>
            )}
            
            {/* Entry Specifics */}
            {selectedMarker.marker_type === 'entry_executed' && (
              <>
                <div className="detail-item">
                  {renderDetailLabel("Strategy", "Strategy (Entry)")}
                  <span className="detail-value">{selectedMarker.strategy || metadata.strategy || 'Unknown'}</span>
                </div>
                <div className="detail-item">
                  {renderDetailLabel("Confidence")}
                  <span className="detail-value">
                    {selectedMarker.confidence != null ? Number(selectedMarker.confidence).toFixed(0) : 'N/A'}%
                  </span>
                </div>
                {details.stop_loss && (
                   <div className="detail-item">
                    {renderDetailLabel("Stop Loss")}
                    <span className="detail-value">${details.stop_loss.toFixed(2)}</span>
                  </div>
                )}
                {details.take_profit && (
                   <div className="detail-item">
                    {renderDetailLabel("Take Profit")}
                    <span className="detail-value">${details.take_profit.toFixed(2)}</span>
                  </div>
                )}
                {details.risk_reward && (
                   <div className="detail-item">
                    {renderDetailLabel("R:R Ratio")}
                    <span className="detail-value">{details.risk_reward.toFixed(2)}</span>
                  </div>
                )}
              </>
            )}

            {/* Exit Specifics */}
            {['exit_executed', 'stop_loss_hit', 'take_profit_hit'].includes(selectedMarker.marker_type) && (
               <>
                <div className="detail-item">
                  {renderDetailLabel("Exit Reason")}
                  <span className="detail-value">{details.exit_reason || 'Unknown'}</span>
                </div>
                {(details.pnl_dollars != null || details.pnl_usd != null) && (
                  <div className="detail-item">
                    {renderDetailLabel("PnL")}
                    <span className={`detail-value ${(resolvePnlPct(details, details.pnl_dollars ?? details.pnl_usd) ?? 0) >= 0 ? 'positive' : 'negative'}`}>
                      {(() => {
                        const pct = resolvePnlPct(details, details.pnl_dollars ?? details.pnl_usd);
                        if (pct == null) return 'n/a';
                        return `${pct >= 0 ? '+' : ''}${pct.toFixed(2)}%`;
                      })()}
                    </span>
                  </div>
                )}
                {(details.pnl_dollars != null || details.pnl_usd != null) && (
                  <div className="detail-item">
                    {renderDetailLabel("PnL $")}
                    <span className={`detail-value ${(details.pnl_dollars ?? details.pnl_usd) >= 0 ? 'positive' : 'negative'}`}>
                      {(details.pnl_dollars ?? details.pnl_usd) >= 0 ? '+' : ''}${Number(details.pnl_dollars ?? details.pnl_usd).toFixed(2)}
                    </span>
                  </div>
                )}
                {details.bars_held && (
                  <div className="detail-item">
                    {renderDetailLabel("Bars Held")}
                    <span className="detail-value">{details.bars_held}</span>
                  </div>
                )}
               </>
            )}

            {/* Reasoning Section */}
            {details.reasoning && (
               <div style={{ gridColumn: '1 / -1', marginTop: '10px', padding: '10px', background: 'rgba(15, 23, 42, 0.04)', borderRadius: '4px' }}>
                 <div style={{ marginBottom: '5px' }}>{renderDetailLabel("Reasoning", "Reasoning", { fontWeight: 600 })}</div>
                 <div className="detail-value" style={{ whiteSpace: 'normal', fontSize: '0.9em', lineHeight: '1.4' }}>{details.reasoning}</div>
               </div>
            )}

            {/* Costs Breakdown */}
            {details.costs && (
              <>
                {renderSectionHeader("Trading Costs")}
                 {Object.entries(details.costs).map(([k, v]) => (
                 <div className="detail-item" key={`cost-${k}`}>
                    {renderDetailLabel(renderCostLabel(k), {
                      tooltipLabel: renderCostLabel(k),
                      runtimeValue: v,
                      runtimeSource: `details.costs.${k}`,
                    })}
                    <span className="detail-value">${Number(v).toFixed(4)}</span>
                  </div>
                ))}
              </>
            )}

            {l2Diagnostics.hasAny && (
              <>
                {renderSectionHeader("L2 Diagnostics")}
                {l2Diagnostics.flowScore != null && (
                  <div className="detail-item">
                    {renderDetailLabel("Flow Score")}
                    <span className="detail-value">{l2Diagnostics.flowScore.toFixed(1)}</span>
                  </div>
                )}
                {l2Diagnostics.signedAggression != null && (
                  <div className="detail-item">
                    {renderDetailLabel("Signed Aggression")}
                    <span className="detail-value">{l2Diagnostics.signedAggression.toFixed(3)}</span>
                  </div>
                )}
                {l2Diagnostics.l2AggressionZ != null && (
                  <div className="detail-item">
                    {renderDetailLabel("L2 Aggression Z")}
                    <span className="detail-value">{l2Diagnostics.l2AggressionZ.toFixed(3)}</span>
                  </div>
                )}
                {l2Diagnostics.l2BookPressureZ != null && (
                  <div className="detail-item">
                    {renderDetailLabel("L2 Book Pressure Z")}
                    <span className="detail-value">{l2Diagnostics.l2BookPressureZ.toFixed(3)}</span>
                  </div>
                )}
                {l2Diagnostics.absorptionRate != null && (
                  <div className="detail-item">
                    {renderDetailLabel("Absorption Rate")}
                    <span className="detail-value">{l2Diagnostics.absorptionRate.toFixed(3)}</span>
                  </div>
                )}
                {l2Diagnostics.largeTraderActivity != null && (
                  <div className="detail-item">
                    {renderDetailLabel("Large Trader Activity")}
                    <span className="detail-value">{l2Diagnostics.largeTraderActivity.toFixed(3)}</span>
                  </div>
                )}
                {l2Diagnostics.vwapExecutionFlow != null && (
                  <div className="detail-item">
                    {renderDetailLabel("VWAP Execution Flow", "VWAP Execution Flow (L2 Diagnostics)")}
                    <span className="detail-value">{l2Diagnostics.vwapExecutionFlow.toFixed(3)}</span>
                  </div>
                )}
                {l2Diagnostics.sweepDetected != null && (
                  <div className="detail-item">
                    {renderDetailLabel("Sweep Detected")}
                    <span className="detail-value">
                      {l2Diagnostics.sweepDetected ? t("yes") : t("no")}
                    </span>
                  </div>
                )}
                <div className="detail-item">
                  {renderDetailLabel("L2 Source")}
                  <span className="detail-value">
                    {l2Diagnostics.sourcePath || t("Source unavailable")}
                  </span>
                </div>
              </>
            )}

            {intradayLevels.hasAny && (
              <>
                {renderSectionHeader("Intraday Levels")}
                <div className="detail-item">
                  {renderDetailLabel("Tracker")}
                  <span className="detail-value">
                    {renderEnabled(intradayLevels.enabled)}
                  </span>
                </div>
                <div className="detail-item">
                  {renderDetailLabel("Active / Tested / Broken")}
                  <span className="detail-value">
                    {Number(intradayLevels.stats.active_levels || 0)} /{" "}
                    {Number(intradayLevels.stats.tested_levels || 0)} /{" "}
                    {Number(intradayLevels.stats.broken_levels || 0)}
                  </span>
                </div>
                <div className="detail-item">
                  {renderDetailLabel("Bounce / Break Events")}
                  <span className="detail-value">
                    {Number(intradayLevels.stats.bounce_events || 0)} /{" "}
                    {Number(intradayLevels.stats.break_events || 0)}
                  </span>
                </div>
                <div className="detail-item">
                  {renderDetailLabel("POC")}
                  <span className="detail-value">
                    {intradayLevels.volumeProfile.poc_price != null
                      ? Number(intradayLevels.volumeProfile.poc_price).toFixed(2)
                      : "n/a"}
                  </span>
                </div>
                <div className="detail-item">
                  {renderDetailLabel("Value Area")}
                  <span className="detail-value">
                    {intradayLevels.volumeProfile.value_area_low != null &&
                    intradayLevels.volumeProfile.value_area_high != null
                      ? `${Number(intradayLevels.volumeProfile.value_area_low).toFixed(2)} - ${Number(intradayLevels.volumeProfile.value_area_high).toFixed(2)}`
                      : "n/a"}
                  </span>
                </div>
                {intradayLevels.latestEvent && (
                  <div className="detail-item">
                    {renderDetailLabel("Latest Event")}
                    <span className="detail-value">
                      {String(intradayLevels.latestEvent.event_type || "event")}
                      {intradayLevels.latestEvent.direction
                        ? ` (${String(intradayLevels.latestEvent.direction)})`
                        : ""}
                      {intradayLevels.latestEvent.price != null
                        ? ` @ ${Number(intradayLevels.latestEvent.price).toFixed(2)}`
                        : ""}
                    </span>
                  </div>
                )}
              </>
            )}

            {levelContext.hasAny && (
              <>
                {renderSectionHeader("Level Context Gate")}
                <div className="detail-item">
                  {renderDetailLabel("Status")}
                  <span className="detail-value">
                    {renderGateStatus(levelContext.payload.passed)}
                  </span>
                </div>
                <div className="detail-item">
                  {renderDetailLabel("Strategy", "Strategy (Gate)")}
                  <span className="detail-value">
                    {String(levelContext.payload.strategy_key || "n/a")}
                  </span>
                </div>
                <div className="detail-item">
                  {renderDetailLabel("Gate Reason")}
                  <span className="detail-value">
                    {String(levelContext.payload.reason || "n/a")}
                  </span>
                </div>
                <div className="detail-item">
                  {renderDetailLabel("Near Tested Levels", "Near Tested Levels (Gate)")}
                  <span className="detail-value">
                    {Number(levelContext.payload?.stats?.near_tested_levels_count || 0)}
                  </span>
                </div>
                <div className="detail-item">
                  {renderDetailLabel("Value Area Position")}
                  <span className="detail-value">
                    {String(levelContext.payload?.volume_profile?.value_area_position || "n/a")}
                  </span>
                </div>
                <div className="detail-item">
                  {renderDetailLabel("POC On Trade Side", "POC On Trade Side (Gate)")}
                  <span className="detail-value">
                    {renderYesNo(levelContext.payload?.volume_profile?.poc_on_trade_side)}
                  </span>
                </div>
                <div className="detail-item">
                  {renderDetailLabel("Room To Next Opposite Level")}
                  <span className="detail-value">
                    {levelContext.payload?.room_to_next_opposite_level_pct != null
                      ? `${Number(levelContext.payload.room_to_next_opposite_level_pct).toFixed(3)}%`
                      : "n/a"}
                  </span>
                </div>
                {levelContext.reasons.length > 0 && (
                  <div className="detail-item" style={{ gridColumn: "1 / -1" }}>
                    {renderDetailLabel("Fail Reasons")}
                    <span className="detail-value">{levelContext.reasons.join(", ")}</span>
                  </div>
                )}
              </>
            )}

            {entryQualityDiagnostics.hasAny && (
              <>
                {renderSectionHeader("Entry Timing Diagnostics")}
                <div className="detail-item">
                  {renderDetailLabel("First-Bar Stop Loss")}
                  <span className="detail-value">
                    {renderYesNo(entryQualityDiagnostics.payload?.is_first_bar_stop_loss)}
                  </span>
                </div>
                <div className="detail-item">
                  {renderDetailLabel("Stop Distance")}
                  <span className="detail-value">
                    {entryQualityDiagnostics.payload?.stop_distance_pct != null
                      ? `${Number(entryQualityDiagnostics.payload.stop_distance_pct).toFixed(3)}%`
                      : "n/a"}
                  </span>
                </div>
                <div className="detail-item">
                  {renderDetailLabel("VWAP Distance")}
                  <span className="detail-value">
                    {entryQualityDiagnostics.payload?.vwap_distance_pct != null
                      ? `${Number(entryQualityDiagnostics.payload.vwap_distance_pct).toFixed(3)}%`
                      : "n/a"}
                  </span>
                </div>
                <div className="detail-item">
                  {renderDetailLabel("Confluence Score")}
                  <span className="detail-value">
                    {entryQualityDiagnostics.payload?.near_confluence_score != null
                      ? Number(entryQualityDiagnostics.payload.near_confluence_score)
                      : "n/a"}
                  </span>
                </div>
                <div className="detail-item">
                  {renderDetailLabel("Near Tested Levels", "Near Tested Levels (Entry Timing)")}
                  <span className="detail-value">
                    {entryQualityDiagnostics.payload?.near_tested_levels_count != null
                      ? Number(entryQualityDiagnostics.payload.near_tested_levels_count)
                      : "n/a"}
                  </span>
                </div>
                <div className="detail-item">
                  {renderDetailLabel("POC On Trade Side", "POC On Trade Side (Entry Timing)")}
                  <span className="detail-value">
                    {renderYesNo(entryQualityDiagnostics.payload?.poc_on_trade_side)}
                  </span>
                </div>
                {entryQualityDiagnostics.tags.length > 0 && (
                  <div className="detail-item" style={{ gridColumn: "1 / -1" }}>
                    {renderDetailLabel("Diagnosis Tags")}
                    <span className="detail-value">{entryQualityDiagnostics.tags.join(", ")}</span>
                  </div>
                )}
              </>
            )}

            {/* Signal Data (Recursive) */}
            {Object.keys(metadata).length > 0 && (
              <>
                 {renderSectionHeader("Signal Data (All Indicators)")}
                 <div style={{ gridColumn: '1 / -1' }}>
                   {Object.entries(metadata)
                    .filter(([key]) => key !== 'strategy')
                    .map(([key, value]) => (
                      <div key={key} style={{ marginBottom: '8px' }}>
                        <span style={{ fontWeight: 600, fontSize: '0.9em', color: 'var(--text-primary)' }}>{key}:</span>
                        <div style={{ marginTop: '2px' }}>
                          {renderValue(value, key)}
                        </div>
                      </div>
                   ))}
                 </div>
              </>
            )}

            {/* Fallback for other details */}
            {Object.entries(details).length > 0 && !details.metadata && !details.costs && (
               <>
                {renderSectionHeader("Additional Details")}
                {Object.entries(details).map(([key, value]) => {
                  if (['metadata', 'costs', 'reasoning', 'pnl_pct', 'pnl_usd', 'pnl_dollars', 'stop_loss', 'take_profit', 'exit_reason', 'risk_reward'].includes(key)) return null;
                  return (
                    <div className="detail-item" key={key}>
                      {renderDetailLabel(key, {
                        tooltipLabel: key,
                        runtimeValue: value,
                        runtimeSource: `details.${key}`,
                      })}
                      <span className="detail-value">{formatGenericValue(value)}</span>
                    </div>
                  );
                })}
               </>
            )}
           </div>
        </>
      )}
      {detailTab === 'raw' && (
        <pre className="decision-raw-json">{JSON.stringify(selectedMarker, null, 2)}</pre>
      )}
      {detailTab === 'decision_log' && (
        <>
          <div className="detail-grid">
            <div className="detail-item">
              {renderDetailLabel("Decision Action")}
              <span className="detail-value">
                {String(decisionLog.payload?.decision_state?.action || "n/a")}
              </span>
            </div>
            <div className="detail-item">
              {renderDetailLabel("Decision Phase")}
              <span className="detail-value">
                {String(decisionLog.payload?.decision_state?.phase || "n/a")}
              </span>
            </div>
            <div className="detail-item">
              {renderDetailLabel("Regime / Micro")}
              <span className="detail-value">
                {String(decisionLog.payload?.decision_state?.regime || "n/a")} /{" "}
                {String(decisionLog.payload?.decision_state?.micro_regime || "n/a")}
              </span>
            </div>
            <div className="detail-item">
              {renderDetailLabel("Selected Strategy")}
              <span className="detail-value">
                {String(decisionLog.payload?.decision_state?.selected_strategy || selectedMarker?.strategy || "n/a")}
              </span>
            </div>
            <div className="detail-item">
              {renderDetailLabel("SL Reason")}
              <span className="detail-value">
                {renderReasonValue(decisionLog.payload?.context_risk?.sl_reason)}
              </span>
            </div>
            <div className="detail-item">
              {renderDetailLabel("TP Reason")}
              <span className="detail-value">
                {renderReasonValue(decisionLog.payload?.context_risk?.tp_reason)}
              </span>
            </div>
            <div className="detail-item">
              {renderDetailLabel("Effective RR")}
              <span className="detail-value">
                {decisionLog.payload?.context_risk?.effective_rr != null
                  ? Number(decisionLog.payload.context_risk.effective_rr).toFixed(4)
                  : "n/a"}
              </span>
            </div>
            <div className="detail-item">
              {renderDetailLabel("Risk %")}
              <span className="detail-value">
                {decisionLog.payload?.context_risk?.risk_pct != null
                  ? `${Number(decisionLog.payload.context_risk.risk_pct).toFixed(4)}%`
                  : "n/a"}
              </span>
            </div>
            <div className="detail-item">
              {renderDetailLabel("Break-even State")}
              <span className="detail-value">
                {String(breakEvenPayload?.state || "n/a")}
              </span>
            </div>
            <div className="detail-item">
              {renderDetailLabel("Break-even Trigger")}
              <span className="detail-value">
                {renderBreakEvenTrigger(breakEvenPayload?.activation_reason)}
              </span>
            </div>
            <div className="detail-item">
              {renderDetailLabel("Break-even Proof")}
              <span className="detail-value">
                {renderBreakEvenProof(breakEvenPayload)}
              </span>
            </div>
            <div className="detail-item">
              {renderDetailLabel("Break-even Stop")}
              <span className="detail-value">
                {breakEvenStopDisplayValue != null
                  ? Number(breakEvenStopDisplayValue).toFixed(4)
                  : "n/a"}
              </span>
            </div>
            <div className="detail-item">
              {renderDetailLabel("Break-even Costs %")}
              <span className="detail-value">
                {formatPctValue(breakEvenComputed?.total_costs_pct, 5)}
              </span>
            </div>
            <div className="detail-item">
              {renderDetailLabel("Break-even Buffer %")}
              <span className="detail-value">
                {formatPctValue(breakEvenBuffer?.selected_buffer_pct, 5)}
              </span>
            </div>
            <div className="detail-item">
              {renderDetailLabel("Break-even Anti-Spike")}
              <span className="detail-value">
                {breakEvenAntiSpikeSummary}
              </span>
            </div>
            <div className="detail-item">
              {renderDetailLabel("VWAP Execution Flow", "VWAP Execution Flow (Decision Log)")}
              <span className="detail-value">
                {decisionLog.payload?.flow_snapshot?.vwap_execution_flow != null
                  ? Number(decisionLog.payload.flow_snapshot.vwap_execution_flow).toFixed(3)
                  : "n/a"}
              </span>
            </div>
            <div className="detail-item" style={{ gridColumn: "1 / -1" }}>
              {renderDetailLabel("Complete Decision Payload")}
              <pre className="decision-raw-json" style={{ marginTop: 8 }}>
                {JSON.stringify(decisionLog.payload, null, 2)}
              </pre>
            </div>
          </div>
        </>
      )}
    </div>
  );

  return (
    <>
      <div className="decision-list-tabs">
        <button
          className={`decision-list-tab ${listTab === 'decisions' ? 'active' : ''}`}
          onClick={() => setListTab('decisions')}
        >
          {t("Decisions")} ({decisionMarkers.length})
        </button>
        <button
          className={`decision-list-tab ${listTab === 'events' ? 'active' : ''}`}
          onClick={() => setListTab('events')}
        >
          {t("Events")} ({eventMarkers.length})
        </button>
      </div>
      <div className="decision-list">
        {visibleMarkers.length === 0 && (
          <div className="empty-state">
            <div className="icon">🗂️</div>
            <p>
              {listTab === 'decisions'
                ? t('No trading decisions in this run yet.')
                : t('No non-decision events in this run yet.')}
            </p>
          </div>
        )}
        {renderedMarkers.map((marker, idx) => {
          const exitMetrics = formatExitMetrics(marker);
          const markerKey = getMarkerKey(marker, idx);
          const selected = isSameMarker(selectedMarker, marker);
          const markerDetails = marker?.details || {};
          const markerMetadata = markerDetails?.metadata || {};
          const markerIntradayLevels = extractIntradayLevels(
            marker,
            markerDetails,
            markerMetadata,
          );
          const markerIntradayEvent =
            markerIntradayLevels?.latestEvent &&
            typeof markerIntradayLevels.latestEvent === "object"
              ? markerIntradayLevels.latestEvent
              : null;
          const markerIntradayEventType = String(
            markerIntradayEvent?.event_type || "",
          ).toLowerCase();
          const markerIntradayEventDirection = String(
            markerIntradayEvent?.direction || "",
          ).toLowerCase();
          const markerIntradayEventLabel = markerIntradayEvent
            ? `Levels ${markerIntradayEventType || "event"}${markerIntradayEventDirection ? ` ${markerIntradayEventDirection}` : ""}${
                markerIntradayEvent.price != null
                  ? ` @ ${Number(markerIntradayEvent.price).toFixed(2)}`
                  : ""
              }`
            : "";
          const markerIntradayEventColor =
            markerIntradayEventType === "break"
              ? "var(--accent-green)"
              : markerIntradayEventType === "bounce"
                ? "var(--text-secondary)"
                : "var(--text-muted)";
          return (
          <div
            key={markerKey}
            ref={(node) => {
              if (node) itemRefs.current.set(markerKey, node);
              else itemRefs.current.delete(markerKey);
            }}
            className={`decision-item ${marker.marker_type} ${selected ? 'selected' : ''}`}
            onClick={() => {
              setIsDetailFullscreen(true);
              onSelectMarker({
                ...marker,
                __selectionSource: "decision_panel",
              });
            }}
          >
            <div className="decision-header">
              <span className="decision-title">
                {getMarkerIcon(marker)} {renderTitle(marker)}
              </span>
              <span className="decision-time">{formatTime(marker.timestamp)}</span>
            </div>
            <div className="decision-description">
              {exitMetrics
                ? `${t("Reason")}: ${marker.details?.exit_reason || "n/a"}`
                : (marker.description || t("No description"))}
              {exitMetrics && (
                <div style={{ marginTop: 4, color: 'var(--text-muted)', fontSize: '0.78rem', fontWeight: 600 }}>
                  {exitMetrics}
                </div>
              )}
              {markerIntradayEvent && (
                <div
                  style={{
                    marginTop: 4,
                    color: markerIntradayEventColor,
                    fontSize: "0.75rem",
                    fontWeight: 600,
                  }}
                >
                  {markerIntradayEventLabel}
                </div>
              )}
            </div>
          </div>
        );})}
      </div>
      {hasMoreRows && (
        <div style={{ padding: '0 var(--spacing-sm) var(--spacing-sm)' }}>
          <button
            type="button"
            className="btn btn-secondary tw-full-btn"
            onClick={() =>
              setVisibleRows((prev) =>
                Math.min(visibleMarkers.length, prev + DECISION_LIST_LOAD_STEP)
              )
            }
          >
            {t('Load older')} ({visibleMarkers.length - renderedMarkers.length} {t('remaining')})
          </button>
        </div>
      )}

      {activeHelpTooltip && !activeHelpTooltip.pinned &&
        createPortal(
          <div
            className={`decision-help-tooltip ${activeHelpTooltip.placeAbove ? "above" : ""}`}
            role="tooltip"
            aria-live="polite"
            style={{
              top: activeHelpTooltip.top,
              left: activeHelpTooltip.left,
              maxWidth: activeHelpTooltip.maxWidth,
            }}
          >
            {activeHelpTooltip.text}
          </div>,
          document.body,
        )}
      
      {/* Detail Panel */}
      {selectedMarker && (
        <>
          {!isDetailFullscreen && renderDecisionDetail(false)}
          {isDetailFullscreen &&
            createPortal(
              <>
                <div
                  className="decision-detail-backdrop"
                  onClick={() => setIsDetailFullscreen(false)}
                />
                {renderDecisionDetail(true)}
              </>,
              document.body,
            )}
        </>
      )}
    </>
  );
}

export default memo(DecisionPanel);
