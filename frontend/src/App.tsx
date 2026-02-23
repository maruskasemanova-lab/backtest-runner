import { useState, useEffect, useRef, useCallback, useMemo, type MouseEvent as ReactMouseEvent } from 'react';
import {
  toUnixSeconds,
  toIsoTimestamp,
  normalizeText,
  normalizeIsoDay,
  defaultStrategyApiUrl,
  resolveWsLiveUrl,
  wsFeatureEnabled,
} from './utils';
import CandlestickChart from './components/CandlestickChart';
import FootprintChart from './components/FootprintChart';
import PlaybackControls from './components/PlaybackControls';
import DecisionPanel from './components/DecisionPanel';
import SessionSummary from './components/SessionSummary';
import RunConfig from './components/RunConfig';
import StrategyModuleToggles from './components/StrategyModuleToggles';
import ExecutionModuleToggles from './components/ExecutionModuleToggles';
import DataManager from './components/DataManager';
import IntrabarPanel from './components/IntrabarPanel';
import AdaptiveStrategyStudio from './components/AdaptiveStrategyStudio';
import AdaptiveTuner from './components/AdaptiveTuner';
import LiveTraderMonitor from './components/LiveTraderMonitor';
import DiagnosticCalendar from './components/DiagnosticCalendar';
import StrategyAnalyzer from './components/StrategyAnalyzer';
import {
  isSupabaseAuthEnabled,
  signInWithGoogle,
  signOutSupabase,
  subscribeAuthSnapshot,
  type AuthSnapshot,
} from './auth/supabaseAuth';


const scoreMarkerMatch = (candidate, target) => {
  if (!candidate || !target) return Number.NEGATIVE_INFINITY;

  const candidateId = normalizeText(candidate.id);
  const targetId = normalizeText(target.id);
  if (candidateId && targetId && candidateId === targetId) {
    return Number.POSITIVE_INFINITY;
  }

  let score = 0;

  const candidateType = normalizeText(candidate.marker_type);
  const targetType = normalizeText(target.marker_type);
  if (candidateType && targetType) {
    score += candidateType === targetType ? 500 : -200;
  }

  const candidateSide = normalizeText(candidate.side ?? candidate.details?.side);
  const targetSide = normalizeText(target.side ?? target.details?.side);
  if (candidateSide && targetSide && candidateSide === targetSide) {
    score += 180;
  }

  const candidateStrategy = normalizeText(candidate.strategy);
  const targetStrategy = normalizeText(target.strategy);
  if (candidateStrategy && targetStrategy && candidateStrategy === targetStrategy) {
    score += 140;
  }

  const candidateRegime = normalizeText(candidate.regime);
  const targetRegime = normalizeText(target.regime);
  if (candidateRegime && targetRegime && candidateRegime === targetRegime) {
    score += 120;
  }

  const candidateSignal = normalizeText(candidate.details?.signal_type);
  const targetSignal = normalizeText(target.details?.signal_type);
  if (candidateSignal && targetSignal && candidateSignal === targetSignal) {
    score += 80;
  }

  const candidateRun = normalizeText(candidate.run_id ?? candidate.details?.run_id);
  const targetRun = normalizeText(target.run_id ?? target.details?.run_id);
  if (candidateRun && targetRun && candidateRun === targetRun) {
    score += 90;
  }

  const candidateTicker = normalizeText(candidate.ticker ?? candidate.details?.ticker);
  const targetTicker = normalizeText(target.ticker ?? target.details?.ticker);
  if (candidateTicker && targetTicker && candidateTicker === targetTicker) {
    score += 60;
  }

  const candidateTitle = normalizeText(candidate.title);
  const targetTitle = normalizeText(target.title);
  if (candidateTitle && targetTitle && candidateTitle === targetTitle) {
    score += 40;
  }

  const candidateTs = toUnixSeconds(candidate.time ?? candidate.timestamp);
  const targetTs = toUnixSeconds(target.time ?? target.timestamp);
  if (Number.isFinite(candidateTs) && Number.isFinite(targetTs)) {
    const diff = Math.abs(candidateTs - targetTs);
    if (diff <= 1) score += 220;
    else if (diff <= 5) score += 170;
    else if (diff <= 60) score += 120;
    else if (diff <= 300) score += 70;
    else if (diff <= 1800) score += 20;
    else score -= Math.min(220, diff / 20);
  }

  const candidatePrice = Number(candidate.price);
  const targetPrice = Number(target.price);
  if (Number.isFinite(candidatePrice) && Number.isFinite(targetPrice)) {
    const diff = Math.abs(candidatePrice - targetPrice);
    score += 120 / (1 + diff);
  }

  return score;
};

const parseRunKey = (value) => {
  const raw = String(value || '').trim();
  if (!raw) return null;
  const parts = raw.split(':');
  if (parts.length < 3) return null;
  const date = parts.pop();
  const ticker = parts.pop();
  const runId = parts.join(':');
  if (!runId || !ticker || !date) return null;
  return { runId, ticker, date };
};

const buildRunKeyFromState = (runStateRow) => {
  if (!runStateRow || typeof runStateRow !== 'object') return null;
  const runId = String(runStateRow.run_id || '').trim();
  const ticker = String(runStateRow.ticker || '').trim();
  const date = String(runStateRow.date || '').trim();
  if (!runId || !ticker || !date) return null;
  return `${runId}:${ticker}:${date}`;
};

const buildRunApiBase = (runParts) => {
  if (!runParts) return null;
  return `/api/run/${encodeURIComponent(runParts.runId)}/${encodeURIComponent(runParts.ticker)}/${encodeURIComponent(runParts.date)}`;
};

const RUN_RANGE_LABEL_PATTERN = /^(\d{4}-\d{2}-\d{2})_to_(\d{4}-\d{2}-\d{2})$/;
const RUN_ID_COLLISION_PATTERN = /Run already exists:/i;

const resolveRunDateWindow = (stateRow) => {
  const row = stateRow && typeof stateRow === 'object' ? stateRow : {};
  const rawDate = String(row.date || '').trim();
  const rangeMatch = rawDate.match(RUN_RANGE_LABEL_PATTERN);
  const from = normalizeIsoDay(row.date_from) || normalizeIsoDay(rangeMatch?.[1]) || normalizeIsoDay(rawDate);
  let to = normalizeIsoDay(row.date_to) || normalizeIsoDay(rangeMatch?.[2]) || from;
  if (!from) return null;
  if (!to || to < from) {
    to = from;
  }
  return {
    dateFrom: from,
    dateTo: to,
    startTime: `${from}T04:00:00Z`,
    endTime: `${to}T20:00:00Z`,
  };
};

const readErrorDetail = async (response, fallback) => {
  const backup = response.clone();
  try {
    const payload = await response.json();
    if (payload && typeof payload === "object") {
      const detail = payload.detail ?? payload.error ?? payload.message;
      if (detail !== null && detail !== undefined && String(detail).trim()) {
        return String(detail);
      }
    }
  } catch (_error) {
    // Fallback to plain-text body below.
  }

  try {
    const raw = await backup.text();
    const text = String(raw || "").trim();
    if (text) return text;
  } catch (_error) {
    // Ignore and use fallback.
  }

  return String(fallback || "").trim() || "Unknown error";
};

const normalizeNonEmptyToken = (value) => {
  const token = String(value ?? '').trim();
  return token || '';
};

const pickFirstNonEmptyToken = (...values) => {
  for (const value of values) {
    const token = normalizeNonEmptyToken(value);
    if (token) return token;
  }
  return '';
};

const extractRunProfileMetadata = (payload) => {
  const row = payload && typeof payload === 'object' ? payload : {};
  const reportMeta =
    row.report_metadata && typeof row.report_metadata === 'object' ? row.report_metadata : {};
  const aosApplied = row.aos_applied && typeof row.aos_applied === 'object' ? row.aos_applied : {};
  const unifiedMeta =
    aosApplied.unified_profile && typeof aosApplied.unified_profile === 'object'
      ? aosApplied.unified_profile
      : {};
  const adaptiveMeta =
    aosApplied.adaptive_profile && typeof aosApplied.adaptive_profile === 'object'
      ? aosApplied.adaptive_profile
      : {};
  const comboMeta =
    aosApplied.strategy_combo && typeof aosApplied.strategy_combo === 'object'
      ? aosApplied.strategy_combo
      : {};

  return {
    unified_profile_id: pickFirstNonEmptyToken(
      reportMeta.unified_profile_id,
      row.unified_profile_id,
      unifiedMeta.active_profile_id,
      unifiedMeta.profile_id,
    ),
    unified_profile_name: pickFirstNonEmptyToken(
      reportMeta.unified_profile_name,
      row.unified_profile_name,
      unifiedMeta.profile_name,
    ),
    adaptive_profile_id: pickFirstNonEmptyToken(
      reportMeta.adaptive_profile_id,
      row.adaptive_profile_id,
      adaptiveMeta.active_profile_id,
      adaptiveMeta.profile_id,
    ),
    strategy_combo_profile_id: pickFirstNonEmptyToken(
      reportMeta.strategy_combo_profile_id,
      row.strategy_combo_profile_id,
      comboMeta.active_profile_id,
      comboMeta.profile_id,
    ),
  };
};

const buildEffectiveExecutionConfigSnapshot = (payload) => {
  if (!payload || typeof payload !== 'object') return null;

  const executionConfig =
    payload.execution_config && typeof payload.execution_config === 'object'
      ? { ...payload.execution_config }
      : {};
  const profileMeta = extractRunProfileMetadata(payload);

  if (profileMeta.unified_profile_id && !normalizeNonEmptyToken(executionConfig.unified_profile_id)) {
    executionConfig.unified_profile_id = profileMeta.unified_profile_id;
  }
  if (
    profileMeta.unified_profile_name &&
    !normalizeNonEmptyToken(executionConfig.unified_profile_name)
  ) {
    executionConfig.unified_profile_name = profileMeta.unified_profile_name;
  }
  if (profileMeta.adaptive_profile_id && !normalizeNonEmptyToken(executionConfig.adaptive_profile_id)) {
    executionConfig.adaptive_profile_id = profileMeta.adaptive_profile_id;
  }
  if (
    profileMeta.strategy_combo_profile_id &&
    !normalizeNonEmptyToken(executionConfig.strategy_combo_profile_id)
  ) {
    executionConfig.strategy_combo_profile_id = profileMeta.strategy_combo_profile_id;
  }

  return Object.keys(executionConfig).length ? executionConfig : null;
};

const toChartBar = (bar) => {
  if (!bar || typeof bar !== 'object') return null;
  const time = toUnixSeconds(bar.timestamp ?? bar.time);
  const open = Number(bar.open);
  const high = Number(bar.high);
  const low = Number(bar.low);
  const close = Number(bar.close);
  const volume = Number(bar.volume);

  if (!Number.isFinite(time)) return null;
  if (!Number.isFinite(open) || !Number.isFinite(high) || !Number.isFinite(low) || !Number.isFinite(close)) {
    return null;
  }

  const nestedAnalysis =
    (bar.analysis && typeof bar.analysis === 'object' ? bar.analysis : null) ||
    (bar.strategy_analysis && typeof bar.strategy_analysis === 'object' ? bar.strategy_analysis : null) ||
    null;
  const layerScores =
    (bar.layer_scores && typeof bar.layer_scores === 'object' ? bar.layer_scores : null) ||
    (nestedAnalysis?.layer_scores && typeof nestedAnalysis.layer_scores === 'object'
      ? nestedAnalysis.layer_scores
      : null);
  const signalRejected =
    (bar.signal_rejected && typeof bar.signal_rejected === 'object' ? bar.signal_rejected : null) ||
    (nestedAnalysis?.signal_rejected && typeof nestedAnalysis.signal_rejected === 'object'
      ? nestedAnalysis.signal_rejected
      : null);
  const candidateDiagnostics =
    (bar.candidate_diagnostics && typeof bar.candidate_diagnostics === 'object'
      ? bar.candidate_diagnostics
      : null) ||
    (nestedAnalysis?.candidate_diagnostics && typeof nestedAnalysis.candidate_diagnostics === 'object'
      ? nestedAnalysis.candidate_diagnostics
      : null);
  const intrabarEvalTrace =
    (bar.intrabar_eval_trace && typeof bar.intrabar_eval_trace === 'object'
      ? bar.intrabar_eval_trace
      : null) ||
    (nestedAnalysis?.intrabar_eval_trace && typeof nestedAnalysis.intrabar_eval_trace === 'object'
      ? nestedAnalysis.intrabar_eval_trace
      : null);
  const nestedWarmupOnly =
    typeof nestedAnalysis?.warmup_only === 'boolean' ? nestedAnalysis.warmup_only : undefined;
  const nestedBarIndex = nestedAnalysis?.bar_index;

  return {
    time,
    open,
    high,
    low,
    close,
    volume: Number.isFinite(volume) ? volume : 0,
    // Preserve runtime analysis payload on streamed bars so analyzer can scrub
    // historical conditions bar-by-bar without changing chart rendering logic.
    ...(layerScores
      ? {
          layer_scores: layerScores,
          signal_rejected: signalRejected,
          candidate_diagnostics: candidateDiagnostics,
          intrabar_eval_trace: intrabarEvalTrace || undefined,
          warmup_only:
            typeof bar.warmup_only === 'boolean'
              ? bar.warmup_only
              : nestedWarmupOnly,
          bar_index:
            Number.isFinite(Number(bar.bar_index))
              ? Number(bar.bar_index)
              : (Number.isFinite(Number(nestedBarIndex)) ? Number(nestedBarIndex) : undefined),
          timestamp: typeof bar.timestamp === 'string' ? bar.timestamp : undefined,
          ...(nestedAnalysis ? { analysis: nestedAnalysis } : {}),
        }
      : {}),
  };
};

const VIEW_TABS = [
  { id: 'backtest', label: 'Backtest', icon: '📈' },
  { id: 'data-manager', label: 'Data Manager', icon: '💾' },
  { id: 'strategy-analyzer', label: 'Strategy Analyzer', icon: '🔬' },
  { id: 'adaptive-studio', label: 'Adaptive Studio', icon: '🧪' },
  { id: 'adaptive-tuner', label: 'Adaptive Tuner', icon: '⚙️' },
  { id: 'diagnostics', label: 'Diagnostics', icon: '🔍' },
  { id: 'live-trader', label: 'Live Trader', icon: '🔴' },
];

const SIDEBAR_NAV_ITEMS = [
  { id: 'dates', label: 'Date Range', icon: '🗓', sectionId: 'run-config', runConfigMode: 'dates', focusFieldId: 'date_from', rangeLabel: 'A1' },
  { id: 'profiles', label: 'Profiles', icon: '🧩', sectionId: 'run-config', runConfigMode: 'profiles', focusFieldId: 'unified_profile_section', rangeLabel: 'A2' },
  { id: 'start-mode', label: 'Start Mode', icon: '🚀', sectionId: 'run-config', runConfigMode: 'start', focusFieldId: 'start_mode_section', rangeLabel: 'A3' },
  { id: 'strategies', label: 'Strategies', icon: '🎛', sectionId: 'strategy-settings', focusFieldId: null, rangeLabel: 'B' },
  { id: 'modules', label: 'Global Modules', icon: '🔧', sectionId: 'execution-modules', focusFieldId: null, rangeLabel: 'E' },
  { id: 'playback', label: 'Playback', icon: '▶', sectionId: 'playback-controls', focusFieldId: null, rangeLabel: 'C' },
  { id: 'summary', label: 'Summary', icon: '📊', sectionId: 'session-summary', focusFieldId: null, rangeLabel: 'D' },
] as const;
const RUN_CONFIG_PANEL_HOST_ID =
  SIDEBAR_NAV_ITEMS.find((item) => item.sectionId === 'run-config')?.id || 'dates';
const DEFAULT_FEATURE_FLAGS = { ads_enabled: false, ads_provider: 'none', ads_placements: [] };
const WS_FALLBACK_NOTICE = 'WebSocket unavailable on this deployment. Using polling mode.';
const WS_RECONNECT_BASE_MS = 800;
const WS_RECONNECT_MAX_MS = 8000;
const WS_CONNECT_ATTEMPTS_BEFORE_FALLBACK = 8;
const USAGE_POLL_VISIBLE_MS = 20000;
const USAGE_POLL_HIDDEN_MS = 120000;
const ACTIVE_RUNS_POLL_BACKTEST_VISIBLE_MS = 8000;
const ACTIVE_RUNS_POLL_OTHER_VISIBLE_MS = 30000;
const RUN_STATE_POLL_VISIBLE_MS = 1000;
const RUN_STATE_POLL_HIDDEN_MS = 5000;
const ICEBERG_FETCH_LIMIT = 400;
const ICEBERG_FETCH_MIN_HIDDEN_SIZE = 120;
const ICEBERG_FETCH_MIN_TRADE_SIZE = 250;
const ICEBERG_RENDER_LIMIT = 240;
const EMPTY_AUTH_SNAPSHOT: AuthSnapshot = {
  enabled: isSupabaseAuthEnabled(),
  signedIn: false,
  email: null,
  userId: null,
  token: null,
};

type SidebarNavItem = (typeof SIDEBAR_NAV_ITEMS)[number];

const SIDEBAR_WIDTH_STORAGE_KEY = 'backtest_runner.sidebar_width';
const SIDEBAR_MIN_WIDTH = 280;
const SIDEBAR_MAX_WIDTH = 760;
const MOBILE_SIDEBAR_BREAKPOINT = 992;

const clampSidebarWidth = (value: number) => {
  if (!Number.isFinite(value)) return 340;
  return Math.min(SIDEBAR_MAX_WIDTH, Math.max(SIDEBAR_MIN_WIDTH, Math.round(value)));
};

const readInitialSidebarWidth = () => {
  if (typeof window === 'undefined') return 340;
  const raw = window.localStorage.getItem(SIDEBAR_WIDTH_STORAGE_KEY);
  const parsed = Number(raw);
  return clampSidebarWidth(parsed);
};

function App() {
  // Run state
  const [runKey, setRunKey] = useState(null);
  const [runState, setRunState] = useState(null);
  const [effectiveExecutionConfig, setEffectiveExecutionConfig] = useState(null);
  const [isConnected, setIsConnected] = useState(false);
  const [activeRuns, setActiveRuns] = useState([]);
  
  // Data
  const [bars, setBars] = useState([]);
  const [markers, setMarkers] = useState([]);
  const [selectedMarker, setSelectedMarker] = useState(null);
  const [currentBar, setCurrentBar] = useState(null);
  const [latestBarAnalysis, setLatestBarAnalysis] = useState<any>(null);
  const [selectedIntrabar, setSelectedIntrabar] = useState(null);
  const [selectedTicker, setSelectedTicker] = useState(null);
  const [strategyApiUrl, setStrategyApiUrl] = useState(defaultStrategyApiUrl);
  
  // View navigation
  const [activeView, setActiveView] = useState("backtest"); // "backtest" | "data-manager" | "adaptive-studio" | "adaptive-tuner" | "diagnostics" | "live-trader"
  const [isNavOpen, setIsNavOpen] = useState(false);
  const [downloadProgress, setDownloadProgress] = useState(null);
  const [activeSidebarNavItem, setActiveSidebarNavItem] = useState<string | null>(SIDEBAR_NAV_ITEMS[0]?.id ?? null);
  const [isSidebarRailExpanded, setIsSidebarRailExpanded] = useState(false);
  const [sidebarWidth, setSidebarWidth] = useState<number>(readInitialSidebarWidth);

  // L2 Data
  const [activeTab, setActiveTab] = useState("standard"); // "standard" or "l2"
  const [l2Data, setL2Data] = useState(null);
  const [icebergs, setIcebergs] = useState([]);
  const [timeframe, setTimeframe] = useState("1min");
  
  // Chart Synchronization State
  const [chartState, setChartState] = useState(null); // { from: number, to: number } (Time Range)
  const [priceRange, setPriceRange] = useState(null); // { from: number, to: number } (Price Range)

  // Marker visibility toggles
  const [markerVisibility, setMarkerVisibility] = useState({
    entries: true,
    exits: true,
    icebergs: false,
    regime: true,
    strategy: true
  });

  // ...

  const [isPlaying, setIsPlaying] = useState(false);
  const [isReloadingSnapshot, setIsReloadingSnapshot] = useState(false);
  const [speed, setSpeed] = useState('10hz'); // Default: 10 updates per second (string for hz, number for ms)
  const [tradeEvaluationMode, setTradeEvaluationMode] = useState('standard'); // Faster default: minute-bar eval even during open trades
  const [runtimeNotice, setRuntimeNotice] = useState('');
  const [planTier, setPlanTier] = useState(null);
  const [quotaSnapshot, setQuotaSnapshot] = useState(null);
  const [featureFlags, setFeatureFlags] = useState(DEFAULT_FEATURE_FLAGS);
  const [authSnapshot, setAuthSnapshot] = useState<AuthSnapshot>(EMPTY_AUTH_SNAPSHOT);
  const [authActionBusy, setAuthActionBusy] = useState(false);
  
  // WebSocket
  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const wsPollingFallbackRef = useRef(false);
  const isMountedRef = useRef(true); // Track mount status
  const barsLengthRef = useRef(0);
  const [isPageVisible, setIsPageVisible] = useState(() =>
    typeof document === 'undefined' ? true : document.visibilityState === 'visible'
  );
  const isPageVisibleRef = useRef(isPageVisible);
  const pendingVisibilitySyncRef = useRef(false);
  const sidebarRailRef = useRef<HTMLDivElement | null>(null);
  const sidebarResizeStateRef = useRef<{ startX: number; startWidth: number } | null>(null);
  const activeRun = useMemo(() => parseRunKey(runKey), [runKey]);
  const activeRunId = activeRun?.runId || null;
  const activeRunTicker = activeRun?.ticker || null;
  const activeRunDate = activeRun?.date || null;
  const activeRunApiBase = useMemo(() => buildRunApiBase(activeRun), [activeRun]);
  const hasActiveAttachedRun = useMemo(() => {
    if (!runState || typeof runState !== 'object') return false;
    // Keep config editable after load/initialize so profile and strategy can still be adjusted.
    return Boolean(runState.is_running || runState.is_paused);
  }, [runState]);

  const fetchActiveRuns = useCallback(async () => {
    try {
      const resp = await fetch('/api/runs');
      if (!resp.ok) return;
      const payload = await resp.json();
      const rows = Array.isArray(payload) ? payload : [];
      const normalized = rows
        .map((row) => {
          const key = buildRunKeyFromState(row);
          if (!key) return null;
          return {
            ...row,
            run_key: key,
          };
        })
        .filter(Boolean);
      setActiveRuns(normalized);
    } catch (error) {
      console.debug('Failed to refresh active runs:', error);
    }
  }, []);

  const clearActiveRunState = useCallback((notice = '') => {
    setRunKey(null);
    setRunState(null);
    setEffectiveExecutionConfig(null);
    setBars([]);
    setMarkers([]);
    setSelectedMarker(null);
    setCurrentBar(null);
    setLatestBarAnalysis(null);
    setSelectedIntrabar(null);
    setIsPlaying(false);
    pendingVisibilitySyncRef.current = false;
    if (notice) {
      setRuntimeNotice(notice);
    }
  }, []);

  // Track mount status
  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    isPageVisibleRef.current = isPageVisible;
  }, [isPageVisible]);

  useEffect(() => {
    barsLengthRef.current = Array.isArray(bars) ? bars.length : 0;
  }, [bars]);

  useEffect(() => {
    if (typeof document === 'undefined') return undefined;
    const handleVisibilityChange = () => {
      setIsPageVisible(document.visibilityState === 'visible');
    };
    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, []);

  const fetchUsageSnapshot = useCallback(async () => {
    try {
      const token =
        window.localStorage.getItem('backtest_jwt') ||
        window.localStorage.getItem('supabase_jwt') ||
        '';
      if (!token) {
        setPlanTier(null);
        setQuotaSnapshot(null);
        setFeatureFlags(DEFAULT_FEATURE_FLAGS);
        return;
      }
      const resp = await fetch('/api/v2/usage', {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      if (!resp.ok) return;
      const payload = await resp.json();
      if (payload && typeof payload === 'object') {
        setPlanTier(payload.plan_tier || null);
        setQuotaSnapshot(payload.quota_snapshot || null);
        if (payload.feature_flags && typeof payload.feature_flags === 'object') {
          setFeatureFlags(payload.feature_flags);
        }
      }
    } catch (error) {
      console.debug('Failed to fetch v2 usage snapshot:', error);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    const refresh = async () => {
      if (cancelled || !isPageVisibleRef.current) return;
      await fetchUsageSnapshot();
    };
    if (isPageVisible) {
      refresh();
    }
    const timer = setInterval(
      refresh,
      isPageVisible ? USAGE_POLL_VISIBLE_MS : USAGE_POLL_HIDDEN_MS
    );
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [fetchUsageSnapshot, isPageVisible]);

  useEffect(() => {
    const unsubscribe = subscribeAuthSnapshot((snapshot) => {
      setAuthSnapshot(snapshot);
    });
    return () => {
      unsubscribe();
    };
  }, []);

  useEffect(() => {
    fetchUsageSnapshot().catch(() => null);
  }, [authSnapshot.token, fetchUsageSnapshot]);

  const handleAuthSignIn = useCallback(async () => {
    if (authActionBusy) return;
    setAuthActionBusy(true);
    setRuntimeNotice('');
    try {
      await signInWithGoogle();
    } catch (error) {
      console.error('Google sign-in failed:', error);
      setRuntimeNotice('Google sign-in failed.');
    } finally {
      setAuthActionBusy(false);
    }
  }, [authActionBusy]);

  const handleAuthSignOut = useCallback(async () => {
    if (authActionBusy) return;
    setAuthActionBusy(true);
    setRuntimeNotice('');
    try {
      await signOutSupabase();
      setPlanTier(null);
      setQuotaSnapshot(null);
      setFeatureFlags(DEFAULT_FEATURE_FLAGS);
    } catch (error) {
      console.error('Sign-out failed:', error);
      setRuntimeNotice('Sign-out failed.');
    } finally {
      setAuthActionBusy(false);
    }
  }, [authActionBusy]);

  const hydrateRunSnapshot = useCallback(async (targetRunKey: string, options: Record<string, any> = {}) => {
    const { showBusy = true } = options;
    const parsed = parseRunKey(targetRunKey);
    if (!parsed) return false;

    if (showBusy) {
      setIsReloadingSnapshot(true);
    }

    try {
      const runApiBase = buildRunApiBase(parsed);
      if (!runApiBase) return false;

      const [stateResp, barsResp, markersResp, summaryResp] = await Promise.all([
        fetch(`${runApiBase}/state`),
        fetch(`${runApiBase}/bars`),
        fetch(`${runApiBase}/markers`),
        fetch(`${runApiBase}/summary`),
      ]);

      if (!stateResp.ok || !barsResp.ok) {
        return false;
      }

      const statePayload = await stateResp.json();
      const barsPayload = await barsResp.json();
      const markersPayload = markersResp.ok ? await markersResp.json() : [];
      const summaryPayload = summaryResp.ok ? await summaryResp.json() : null;
      const nextExecutionConfig = buildEffectiveExecutionConfigSnapshot(summaryPayload);

      const rawBars = Array.isArray(barsPayload?.bars) ? barsPayload.bars : [];
      const chartBars = rawBars
        .map((bar) => toChartBar(bar))
        .filter(Boolean)
        .sort((a, b) => a.time - b.time);
      const nextMarkers = Array.isArray(markersPayload) ? markersPayload : [];

      setRunKey(targetRunKey);
      setRunState(statePayload && typeof statePayload === 'object' ? statePayload : null);
      setEffectiveExecutionConfig(nextExecutionConfig);
      setChartState(null);
      setPriceRange(null);
      setBars(chartBars);
      setMarkers(nextMarkers);
      setCurrentBar(rawBars.length ? rawBars[rawBars.length - 1] : null);
      setSelectedIntrabar(null);
      setSelectedMarker((prevSelected) => {
        if (!prevSelected?.id) return null;
        return nextMarkers.find((candidate) => candidate?.id === prevSelected.id) || null;
      });
      setSelectedTicker(parsed.ticker || null);
      setIsPlaying(Boolean(statePayload?.is_running && !statePayload?.is_paused));
      if (typeof nextExecutionConfig?.intrabar_execution_recalc_1s === 'boolean') {
        setTradeEvaluationMode((prev) => {
          if (!nextExecutionConfig.intrabar_execution_recalc_1s) return 'standard';
          return prev === 'intrabar_5s' ? 'intrabar_5s' : 'intrabar_1s';
        });
      }
      return true;
    } catch (error) {
      console.error('Snapshot reload failed:', error);
      return false;
    } finally {
      if (showBusy) {
        setIsReloadingSnapshot(false);
      }
    }
  }, []);

  useEffect(() => {
    if (!isPageVisible || !runKey) return;
    if (!pendingVisibilitySyncRef.current) return;
    pendingVisibilitySyncRef.current = false;
    hydrateRunSnapshot(runKey, { showBusy: false }).catch((error) => {
      console.warn('Snapshot refresh after tab visibility change failed:', error);
    });
  }, [hydrateRunSnapshot, isPageVisible, runKey]);

  // Connect WebSocket - dependent only on hostname
  useEffect(() => {
    let disposed = false;
    let connectAttempts = 0;

    if (!wsFeatureEnabled) {
      wsPollingFallbackRef.current = true;
      setIsConnected(true);
      return () => {};
    }

    const connectWs = () => {
      if (disposed) return;
      if (wsPollingFallbackRef.current) return;

      // Avoid multiple connections
      if (wsRef.current && (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING)) {
        return;
      }

      console.log('Connecting WebSocket...');
      // Clean up existing closed/closing socket just in case
      if (wsRef.current) {
        try { wsRef.current.close(); } catch(e) {}
        wsRef.current = null;
      }

      const ws = new WebSocket(resolveWsLiveUrl());
      let openedOnce = false;
      wsRef.current = ws;
      
      ws.onopen = () => {
        if (disposed || !isMountedRef.current) {
            ws.close();
            return;
        }
        openedOnce = true;
        connectAttempts = 0;
        console.log('WebSocket connected');
        setIsConnected(true);
        setRuntimeNotice((prev) => (prev === WS_FALLBACK_NOTICE ? '' : prev));
        // Subscription will be handled by the other useEffect
      };
      
      ws.onmessage = (event) => {
        if (disposed || !isMountedRef.current) return;
        try {
            const data = JSON.parse(event.data);
            handleWsMessage(data);
        } catch (err) {
            console.error("Failed to parse WS message:", err);
        }
      };
      
      ws.onclose = () => {
        if (disposed || !isMountedRef.current) return;
        if (!openedOnce) {
          connectAttempts += 1;
          if (connectAttempts >= WS_CONNECT_ATTEMPTS_BEFORE_FALLBACK) {
            // After repeated failed handshakes, degrade to polling mode.
            wsPollingFallbackRef.current = true;
            setIsConnected(true);
            setRuntimeNotice((prev) => (prev ? prev : WS_FALLBACK_NOTICE));
            wsRef.current = null;
            return;
          }
          setIsConnected(false);
          const backoffMs = Math.min(
            WS_RECONNECT_MAX_MS,
            WS_RECONNECT_BASE_MS * (2 ** Math.max(0, connectAttempts - 1)),
          );
          if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
          reconnectTimeoutRef.current = setTimeout(connectWs, backoffMs);
          wsRef.current = null;
          return;
        }
        console.log('WebSocket disconnected');
        setIsConnected(false);
        wsRef.current = null;
        
        // Reconnect after transient network drops.
        if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = setTimeout(connectWs, WS_RECONNECT_BASE_MS);
      };
      
      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        // Do not agressively close here, let onclose handle it or browser handle it
      };
    };
    
    connectWs();
    
    return () => {
      disposed = true;
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      if (wsRef.current) {
        try {
          wsRef.current.close();
        } catch (error) {
          console.debug('WS close during cleanup failed:', error);
        }
        wsRef.current = null;
      }
    };
  }, []); // Empty dependency array - connect once on mount

  // Handle subscriptions when activeRunId changes or socket connects
  useEffect(() => {
     const subscribe = () => {
        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN && activeRunId) {
            console.log(`Subscribing to run: ${activeRunId}`);
            wsRef.current.send(JSON.stringify({ type: 'subscribe', run_id: activeRunId, run_key: runKey || null }));
        }
     };

     // Subscribe immediately if open, or wait for connection
     if (isConnected) {
         subscribe();
     } else {
         // The onopen handler in the connection effect could handle this, 
         // but since we split them, we can just watch isConnected here.
     }
  }, [activeRunId, isConnected, runKey]);

  const handleWsMessage = useCallback((data) => {
    const msgRunKey = data?.run_key ? String(data.run_key) : null;
    const msgRunId = data?.run_id ? String(data.run_id) : null;
    const msgTicker = data?.ticker ? String(data.ticker).toUpperCase() : null;
    const msgDate = data?.date ? String(data.date) : null;
    const currentTicker = activeRunTicker ? String(activeRunTicker).toUpperCase() : null;

    // Backend broadcasts all runs; ignore frames that do not belong to the active run.
    if (runKey && msgRunKey && msgRunKey !== runKey) return;
    if (activeRunId && msgRunId && msgRunId !== activeRunId) return;
    if (currentTicker && msgTicker && msgTicker !== currentTicker) return;
    if (activeRunDate && msgDate && msgDate !== activeRunDate) return;

    if (!isPageVisibleRef.current && (data.type === 'bar' || data.type === 'decision')) {
      pendingVisibilitySyncRef.current = true;
      return;
    }
    
    if (data.type === 'bar') {
      handleNewBar(data.bar);
    } else if (data.type === 'decision') {
      handleNewDecision(data.marker);
    } else if (data.type === 'download_progress') {
      setDownloadProgress(data);
    }
  }, [activeRunDate, activeRunId, activeRunTicker, runKey]);

  useEffect(() => {
    if (!isPageVisible) return undefined;
    let cancelled = false;
    const refresh = async () => {
      if (cancelled) return;
      await fetchActiveRuns();
    };
    const intervalMs =
      activeView === 'backtest'
        ? ACTIVE_RUNS_POLL_BACKTEST_VISIBLE_MS
        : ACTIVE_RUNS_POLL_OTHER_VISIBLE_MS;
    refresh();
    const timer = setInterval(refresh, intervalMs);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [activeView, fetchActiveRuns, isPageVisible]);

  useEffect(() => {
    setIsNavOpen(false);
  }, [activeView]);
  
  // Handle new bar from WebSocket
  const handleEvaluateIntrabarSlice = useCallback(async (ts: number) => {
    if (!activeRunApiBase) return null;
    // Find the minute bar that contains this checkpoint timestamp
    const targetBar = bars.find(b => b.time <= ts && ts < b.time + 60);
    if (!targetBar) return null;
    
    try {
      const resp = await fetch(`${activeRunApiBase}/intrabar_eval`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          run_id: activeRunId,
          ticker: activeRunTicker,
          timestamp: new Date(ts * 1000).toISOString(),
          open: targetBar.open,
          high: targetBar.high,
          low: targetBar.low,
          close: targetBar.close,
          volume: targetBar.volume,
          intrabar_quotes_1s: targetBar.intrabar_1s || [],
        }),
      });
      if (!resp.ok) return null;
      return await resp.json();
    } catch (e) {
      console.error("Intrabar eval failed", e);
      return null;
    }
  }, [activeRunApiBase, activeRunId, activeRunTicker, bars]);

  // Handle new bar from WebSocket
  const handleNewBar = useCallback((bar) => {
    const chartBar = toChartBar(bar);
    if (!chartBar) return;
    
    setBars((prev) => {
      if (!prev.length) return [chartBar];
      const last = prev[prev.length - 1];
      if (Math.abs(Number(last?.time || 0) - Number(chartBar.time || 0)) < 0.0001) {
        const next = [...prev];
        next[next.length - 1] = chartBar;
        return next;
      }
      return [...prev, chartBar];
    });
    setCurrentBar(bar);
    // Extract live strategy analysis from bar payload (injected by session_runner).
    const nestedAnalysis =
      (bar?.analysis && typeof bar.analysis === 'object' ? bar.analysis : null) ||
      (bar?.strategy_analysis && typeof bar.strategy_analysis === 'object' ? bar.strategy_analysis : null) ||
      null;
    const liveLayerScores =
      (bar?.layer_scores && typeof bar.layer_scores === 'object' ? bar.layer_scores : null) ||
      (nestedAnalysis?.layer_scores && typeof nestedAnalysis.layer_scores === 'object'
        ? nestedAnalysis.layer_scores
        : null);
    const liveIntrabarEvalTrace =
      (bar?.intrabar_eval_trace && typeof bar.intrabar_eval_trace === 'object'
        ? bar.intrabar_eval_trace
        : null) ||
      (nestedAnalysis?.intrabar_eval_trace && typeof nestedAnalysis.intrabar_eval_trace === 'object'
        ? nestedAnalysis.intrabar_eval_trace
        : null);
    const liveTraceCheckpoints = Array.isArray(liveIntrabarEvalTrace?.checkpoints) ? liveIntrabarEvalTrace.checkpoints : [];
    const liveLatestCheckpoint =
      liveTraceCheckpoints.length > 0 ? liveTraceCheckpoints[liveTraceCheckpoints.length - 1] : null;
    if (liveLayerScores) {
      setLatestBarAnalysis({
        layer_scores: liveLayerScores,
        signal_rejected:
          (bar?.signal_rejected && typeof bar.signal_rejected === 'object' ? bar.signal_rejected : null) ||
          (nestedAnalysis?.signal_rejected && typeof nestedAnalysis.signal_rejected === 'object'
            ? nestedAnalysis.signal_rejected
            : null),
        candidate_diagnostics:
          (bar?.candidate_diagnostics && typeof bar.candidate_diagnostics === 'object'
            ? bar.candidate_diagnostics
            : null) ||
          (nestedAnalysis?.candidate_diagnostics && typeof nestedAnalysis.candidate_diagnostics === 'object'
            ? nestedAnalysis.candidate_diagnostics
            : null),
        intrabar_eval_trace:
          liveIntrabarEvalTrace,
        intrabar_1s:
          (liveLatestCheckpoint?.intrabar_1s && typeof liveLatestCheckpoint.intrabar_1s === 'object'
            ? liveLatestCheckpoint.intrabar_1s
            : null),
        bar_index:
          Number.isFinite(Number(bar?.bar_index))
            ? Number(bar.bar_index)
            : (Number.isFinite(Number(nestedAnalysis?.bar_index)) ? Number(nestedAnalysis.bar_index) : null),
        warmup_only:
          typeof bar?.warmup_only === 'boolean'
            ? bar.warmup_only
            : Boolean(nestedAnalysis?.warmup_only),
      });
    }
    setRunState(prev => {
      if (!prev) return null;

      const totalBars = Number(prev.total_bars || 0);
      const streamIndex = Number(bar?.bar_index);
      const legacyIndex = Number(bar?.index);

      const rawCurrent = Number.isFinite(streamIndex)
        ? streamIndex + 1
        : (Number.isFinite(legacyIndex)
            ? legacyIndex + 1
            : Number(prev.current_bar_index || 0) + 1);

      const current = totalBars > 0
        ? Math.min(totalBars, Math.max(0, rawCurrent))
        : Math.max(0, rawCurrent);
      const progress = totalBars > 0
        ? Math.min(100, Math.max(0, (current / totalBars) * 100))
        : 0;

      return {
        ...prev,
        current_bar_index: current,
        progress_pct: progress,
      };
    });
  }, []);
  
  // Handle new decision from WebSocket
  const handleNewDecision = useCallback((marker) => {
    setMarkers(prev => {
      const idx = prev.findIndex(m => m.id === marker.id);
      if (idx !== -1) {
        // Merge/update existing marker to avoid duplicates and keep latest info
        const next = [...prev];
        next[idx] = { ...prev[idx], ...marker };
        return next;
      }
      return [...prev, marker];
    });
  }, []);

  const displayedBars = useMemo(() => {
      if (timeframe === '1min') return bars;
      if (!bars.length) return [];

      const tfMinutes = parseInt(timeframe);
      if (isNaN(tfMinutes)) return bars;
      
      const interval = tfMinutes * 60; // seconds
      const groups = new Map();

      bars.forEach(bar => {
          const time = bar.time; // seconds
          // quantize time to interval start
          const bucket = Math.floor(time / interval) * interval;
           
          if (!groups.has(bucket)) {
              groups.set(bucket, {
                  time: bucket,
                  open: bar.open,
                  high: bar.high,
                  low: bar.low,
                  close: bar.close,
                  volume: bar.volume,
                  count: 1
              });
          } else {
              const b = groups.get(bucket);
              b.high = Math.max(b.high, bar.high);
              b.low = Math.min(b.low, bar.low);
              b.close = bar.close;
              b.volume += bar.volume;
              b.count++;
          }
      });
      
      return Array.from(groups.values()).sort((a,b) => a.time - b.time);
  }, [bars, timeframe]);

  // Stable chart state change handler
  const handleChartStateChange = useCallback((newState) => {
      setChartState(prev => {
          if (prev && newState && 
              Math.abs(prev.from - newState.from) < 0.001 && 
              Math.abs(prev.to - newState.to) < 0.001) {
              return prev;
          }
          return newState;
      });
  }, []);

  // Filter markers based on visibility toggles
  const filteredMarkers = useMemo(() => {
      if (!markers || markers.length === 0) return [];
      return markers.filter(m => {
          const type = m.marker_type;
          if (type === 'entry_executed' && !markerVisibility.entries) return false;
          if ((type === 'exit_executed' || type === 'stop_loss_hit' || type === 'take_profit_hit') && !markerVisibility.exits) return false;
          if (type === 'regime_detected' && !markerVisibility.regime) return false;
          if (type === 'strategy_selected' && !markerVisibility.strategy) return false;
          return true;
      });
  }, [markers, markerVisibility]);

  const filteredIcebergs = useMemo(() => {
      if (!markerVisibility.icebergs) return [];
      return icebergs.slice(0, ICEBERG_RENDER_LIMIT);
  }, [icebergs, markerVisibility.icebergs]);

  const showAdSlot = useMemo(() => {
    if (!featureFlags || !featureFlags.ads_enabled) return false;
    if (String(planTier || '').toLowerCase() !== 'free') return false;
    return ['data-manager', 'adaptive-studio', 'diagnostics'].includes(activeView);
  }, [featureFlags, planTier, activeView]);

  const icebergDecisionMarkers = useMemo(() => {
    if (!icebergs || icebergs.length === 0) return [];

    return icebergs
      .map((iceberg, idx) => {
        const rawTime = toUnixSeconds(iceberg?.time ?? iceberg?.timestamp);
        const timestamp = iceberg?.timestamp || toIsoTimestamp(rawTime);
        if (!timestamp) return null;

        const tradeSize = Number(iceberg?.trade_size ?? 0);
        const hiddenSize = Number(iceberg?.hidden_size ?? 0);
        const totalSize = tradeSize + hiddenSize;
        const side = typeof iceberg?.side === 'string' ? iceberg.side.toLowerCase() : null;
        const price = Number(iceberg?.price);
        const normalizedPrice = Number.isFinite(price) ? price : null;
        const sideLabel = side ? side.toUpperCase() : 'UNKNOWN';
        const readableSide = side === 'buy' ? 'BUY support' : side === 'sell' ? 'SELL resistance' : 'unknown side';

        return {
          ...iceberg,
          id: iceberg.id || `iceberg-${timestamp}-${normalizedPrice ?? 'na'}-${idx}`,
          marker_type: 'iceberg_detected',
          title: iceberg.title || `Iceberg ${sideLabel}`,
          description: iceberg.description || `Detected ${readableSide} iceberg`,
          timestamp,
          time: rawTime,
          side,
          price: normalizedPrice,
          details: {
            ...(iceberg.details || {}),
            iceberg_side: side,
            iceberg_price: normalizedPrice,
            trade_size: tradeSize,
            hidden_size: hiddenSize,
            total_size: totalSize,
          },
        };
      })
      .filter(Boolean)
      .sort((left, right) => Number(left.time || 0) - Number(right.time || 0))
      .slice(-ICEBERG_RENDER_LIMIT);
  }, [icebergs]);

  const decisionEvents = useMemo(
    () => markerVisibility.icebergs ? [...markers, ...icebergDecisionMarkers] : markers,
    [markers, icebergDecisionMarkers, markerVisibility.icebergs]
  );

  // Toggle marker visibility helper
  const toggleMarkerVisibility = useCallback((key) => {
      setMarkerVisibility(prev => ({ ...prev, [key]: !prev[key] }));
  }, []);

  // Fetch L2 footprint only when L2 tab is active.
  useEffect(() => {
      if (!runState || !runKey || activeTab !== 'l2') return;
      const ticker = String(runState?.ticker || '').trim().toUpperCase();
      const dateWindow = resolveRunDateWindow(runState);
      if (!ticker || !dateWindow) return;

      const controller = new AbortController();
      const fetchL2 = async () => {
        try {
          const params = new URLSearchParams({
            start_time: dateWindow.startTime,
            end_time: dateWindow.endTime,
            timeframe,
          });
          const l2Res = await fetch(`/api/l2/footprint/${ticker}?${params.toString()}`, {
            signal: controller.signal,
          });
          if (!l2Res.ok) {
            console.error("L2 fetch failed", l2Res.status);
            return;
          }
          const data = await l2Res.json();
          if (controller.signal.aborted) return;
          setL2Data({
            ...data,
            date_from: dateWindow.dateFrom,
            date_to: dateWindow.dateTo,
            timeframe,
          });
        } catch (error) {
          if (controller.signal.aborted) return;
          console.error("L2 fetch error:", error);
        }
      };

      fetchL2();
      return () => {
        controller.abort();
      };
  }, [activeTab, runKey, runState?.ticker, runState?.date, runState?.date_from, runState?.date_to, timeframe]);

  // Fetch iceberg markers only when iceberg overlay is enabled.
  useEffect(() => {
      if (!runState || !runKey || !markerVisibility.icebergs) {
        setIcebergs([]);
        return;
      }
      const ticker = String(runState?.ticker || '').trim().toUpperCase();
      const dateWindow = resolveRunDateWindow(runState);
      if (!ticker || !dateWindow) {
        setIcebergs([]);
        return;
      }

      const controller = new AbortController();
      const fetchIcebergs = async () => {
        try {
          const params = new URLSearchParams({
            start_time: dateWindow.startTime,
            end_time: dateWindow.endTime,
            limit: String(ICEBERG_FETCH_LIMIT),
            min_hidden_size: String(ICEBERG_FETCH_MIN_HIDDEN_SIZE),
            min_trade_size: String(ICEBERG_FETCH_MIN_TRADE_SIZE),
            sort: 'hidden_size',
          });
          const response = await fetch(`/api/l2/icebergs/${ticker}?${params.toString()}`, {
            signal: controller.signal,
          });
          if (!response.ok) {
            console.error("Iceberg fetch failed", response.status);
            setIcebergs([]);
            return;
          }
          const payload = await response.json();
          if (controller.signal.aborted) return;
          setIcebergs(Array.isArray(payload) ? payload : []);
        } catch (error) {
          if (controller.signal.aborted) return;
          console.error("Iceberg fetch error:", error);
          setIcebergs([]);
        }
      };

      fetchIcebergs();
      return () => {
        controller.abort();
      };
  }, [markerVisibility.icebergs, runKey, runState?.ticker, runState?.date, runState?.date_from, runState?.date_to]);
  
  // Start a new run
  const handleStartRun = useCallback(async (config) => {
    try {
      setRuntimeNotice('');
      setSelectedTicker(config.ticker || null);
      setStrategyApiUrl(config.strategy_api_url || defaultStrategyApiUrl);
      const resp = await fetch('/api/run/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config)
      });
      
      if (!resp.ok) {
        const detail = await readErrorDetail(resp, `HTTP ${resp.status}`);
        throw new Error(detail || 'Failed to start run');
      }
      
      const data = await resp.json();
      const key = String(data.run_key || '');
      const parsedRun = parseRunKey(key);
      if (!parsedRun) {
        throw new Error('Invalid run key returned by backend.');
      }

      setRunKey(key);
      fetchActiveRuns().catch(() => null);
      const nextExecutionConfig = buildEffectiveExecutionConfigSnapshot(data);
      setEffectiveExecutionConfig(nextExecutionConfig);
      if (typeof nextExecutionConfig?.intrabar_execution_recalc_1s === 'boolean') {
        setTradeEvaluationMode((prev) => {
          if (!nextExecutionConfig.intrabar_execution_recalc_1s) return 'standard';
          return prev === 'intrabar_5s' ? 'intrabar_5s' : 'intrabar_1s';
        });
      }
      
      // Reset state
      setChartState(null);
      setPriceRange(null);
      setBars([]);
      setMarkers([]);
      setSelectedMarker(null);
      setCurrentBar(null);
      setSelectedIntrabar(null);
      setIsPlaying(false);
      pendingVisibilitySyncRef.current = false;
      
      // Fetch initial state
      const runApiBase = buildRunApiBase(parsedRun);
      const stateResp = await fetch(`${runApiBase}/state`);
      if (!stateResp.ok) {
        const detail = await readErrorDetail(stateResp, `HTTP ${stateResp.status}`);
        throw new Error(`Failed to load run state: ${detail}`);
      }
      const state = await stateResp.json();
      setRunState(state);

      // Seed chart from processed bars so chart is visible even when WS lags.
      try {
        const barsResp = await fetch(`${runApiBase}/bars`);
        if (barsResp.ok) {
          const barsPayload = await barsResp.json();
          const rawBars = Array.isArray(barsPayload?.bars) ? barsPayload.bars : [];
          const chartBars = rawBars
            .map((bar) => toChartBar(bar))
            .filter(Boolean)
            .sort((a, b) => a.time - b.time);
          if (chartBars.length > 0) {
            setBars(chartBars);
            setCurrentBar(rawBars[rawBars.length - 1] || null);
          }
        }
      } catch (barsError) {
        console.debug('Initial bars snapshot load failed:', barsError);
      }
      
      // Subscribe WebSocket
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(
          JSON.stringify({ type: 'subscribe', run_id: parsedRun.runId, run_key: key })
        );
      }
      
      return data;
    } catch (error) {
      const message = String((error as any)?.message || '');
      if (!RUN_ID_COLLISION_PATTERN.test(message)) {
        console.error('Start run error:', error);
      }
      throw error;
    }
  }, [fetchActiveRuns]);
  
  // Step forward one bar
  // Step forward one bar
  const handleStep = useCallback(async () => {
    if (!activeRunApiBase) return;
    
    try {
      const resp = await fetch(`${activeRunApiBase}/step`, {
        method: 'POST'
      });
      const data = await resp.json();
      
      if (data.success && data.bar) {
        handleNewBar(data.bar);
        
        // Update state
        setRunState(prev => {
          if (!prev) return prev;
          const totalBars = Number(prev.total_bars || 0);
          const rawCurrent = Number(data.bar_index || 0) + 1;
          const current = totalBars > 0
            ? Math.min(totalBars, Math.max(0, rawCurrent))
            : Math.max(0, rawCurrent);
          const progress = totalBars > 0
            ? Math.min(100, Math.max(0, (current / totalBars) * 100))
            : Number(data.progress_pct || 0);
          return {
            ...prev,
            current_bar_index: current,
            phase: data.phase,
            progress_pct: progress
          };
        });
      }
      
      return data;
    } catch (error) {
      console.error('Step error:', error);
    }
  }, [activeRunApiBase, handleNewBar]);
  
  // Play/auto-advance
  const handlePlay = useCallback(async (playOptions = null) => {
    if (!activeRunApiBase) return;
    
    try {
      // Support both hz (string) and ms (number) formats
      let speedParam;
      if (typeof speed === 'string') {
        // 'max', '10hz', '5hz', etc.
        speedParam = speed;
      } else if (speed === 0) {
        speedParam = 'max';
      } else {
        speedParam = speed;
      }
      
      const overrideTradeEvalMode = String(playOptions?.trade_eval_mode || '').trim().toLowerCase();
      const requestedTradeEvalMode =
        overrideTradeEvalMode === 'intrabar_5s' ||
        overrideTradeEvalMode === 'intrabar_1s' ||
        overrideTradeEvalMode === 'standard'
          ? overrideTradeEvalMode
          : tradeEvaluationMode;

      const response = await fetch(`${activeRunApiBase}/play`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          speed_ms: speedParam,
          trade_eval_mode: requestedTradeEvalMode
        })
      });
      if (!response.ok) {
        let detailMessage = `HTTP ${response.status}`;
        try {
          const detail = await response.json();
          if (detail?.detail) detailMessage = String(detail.detail);
          else if (detail?.error) detailMessage = String(detail.error);
        } catch (_) {}
        if (response.status === 404) {
          clearActiveRunState(
            'Active run no longer exists on backend (likely after restart/reload). Start backtest again.'
          );
          return;
        }
        setRuntimeNotice(`Play failed: ${detailMessage}`);
        setIsPlaying(false);
        console.error('Play request failed:', response.status, detailMessage);
        return;
      }
      const playPayload = await response.json().catch(() => ({}));
      const effectiveTradeMode = String(playPayload?.trade_eval_mode || '').trim().toLowerCase();
      if (effectiveTradeMode === 'intrabar_5s' || effectiveTradeMode === 'intrabar_1s' || effectiveTradeMode === 'standard') {
        setTradeEvaluationMode(effectiveTradeMode);
      }
      setRuntimeNotice('');
      setIsPlaying(true);
    } catch (error) {
      setRuntimeNotice(`Play error: ${error?.message || 'Unknown error'}`);
      setIsPlaying(false);
      console.error('Play error:', error);
    }
  }, [activeRunApiBase, clearActiveRunState, speed, tradeEvaluationMode]);
  
  // Pause
  const handlePause = useCallback(async () => {
    if (!activeRunApiBase) return;
    
    try {
      await fetch(`${activeRunApiBase}/pause`, {
        method: 'POST'
      });
      setIsPlaying(false);
    } catch (error) {
      console.error('Pause error:', error);
    }
  }, [activeRunApiBase]);

  // Poll run state while playing so phase/progress stay in sync in range runs.
  useEffect(() => {
    if (!activeRunApiBase || !isPlaying) return undefined;

    let cancelled = false;
    const pollState = async () => {
      if (cancelled) return;
      try {
        const resp = await fetch(`${activeRunApiBase}/state`);
        if (!resp.ok) {
          if (resp.status === 404) {
            if (!cancelled) {
              cancelled = true;
              setIsPlaying(false);
              setRunState((prev) => {
                if (!prev) return prev;
                return {
                  ...prev,
                  is_running: false
                };
              });
            }
            return;
          }
          console.warn('State poll failed:', resp.status, resp.statusText);
          return;
        }
        const state = await resp.json();
        if (cancelled) return;
        if (isPageVisibleRef.current) {
          setRunState(state);
        }
        const processedCount = Number(state?.current_bar_index || 0);
        const localBarsCount = Number(barsLengthRef.current || 0);
        const shouldSyncBars =
          processedCount > 0 &&
          (wsPollingFallbackRef.current || processedCount > localBarsCount);
        if (shouldSyncBars) {
          try {
            const barsResp = await fetch(`${activeRunApiBase}/bars`);
            if (barsResp.ok) {
              const barsPayload = await barsResp.json();
              const rawBars = Array.isArray(barsPayload?.bars) ? barsPayload.bars : [];
              if (rawBars.length > localBarsCount) {
                const chartBars = rawBars
                  .map((bar) => toChartBar(bar))
                  .filter(Boolean)
                  .sort((a, b) => a.time - b.time);
                setBars(chartBars);
                setCurrentBar(rawBars[rawBars.length - 1] || null);
              }
            }
          } catch (barsError) {
            console.debug('Bars poll sync failed:', barsError);
          }
        }
        if (!state?.is_running) {
          setIsPlaying(false);
        }
      } catch (error) {
        if (!cancelled) {
          setIsPlaying(false);
        }
        console.error('State poll error:', error);
      }
    };

    pollState();
    const interval = setInterval(
      pollState,
      isPageVisible ? RUN_STATE_POLL_VISIBLE_MS : RUN_STATE_POLL_HIDDEN_MS
    );
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [activeRunApiBase, isPageVisible, isPlaying]);
  
  // Stop
  const handleStop = useCallback(async () => {
    if (!activeRunApiBase) return;
    
    try {
      await fetch(`${activeRunApiBase}/stop`, {
        method: 'POST'
      });
      setIsPlaying(false);
      fetchActiveRuns().catch(() => null);
    } catch (error) {
      console.error('Stop error:', error);
    }
  }, [activeRunApiBase, fetchActiveRuns]);
  
  // Reset run
  const handleReset = useCallback(async () => {
    if (!activeRunApiBase) return;
    
    try {
      await fetch(activeRunApiBase, {
        method: 'DELETE'
      });
      clearActiveRunState('');
      setRuntimeNotice('');
      fetchActiveRuns().catch(() => null);
    } catch (error) {
      console.error('Reset error:', error);
    }
  }, [activeRunApiBase, clearActiveRunState, fetchActiveRuns]);

  const handleKillAndDeleteRun = useCallback(async (targetRunKey: string) => {
    const normalizedRunKey = String(targetRunKey || '').trim();
    const parsed = parseRunKey(normalizedRunKey);
    if (!parsed) {
      throw new Error('Invalid run key.');
    }
    const runApiBase = buildRunApiBase(parsed);
    if (!runApiBase) {
      throw new Error('Invalid run path.');
    }

    setRuntimeNotice('');
    try {
      const stopResp = await fetch(`${runApiBase}/stop`, { method: 'POST' });
      if (!stopResp.ok && stopResp.status !== 404) {
        const stopDetail = await readErrorDetail(stopResp, `HTTP ${stopResp.status}`);
        console.warn('Stop before delete returned error:', stopDetail);
      }
    } catch (stopError) {
      console.warn('Stop before delete failed:', stopError);
    }

    const deleteResp = await fetch(runApiBase, { method: 'DELETE' });
    if (!deleteResp.ok) {
      const detail = await readErrorDetail(deleteResp, `HTTP ${deleteResp.status}`);
      throw new Error(detail || 'Failed to delete run.');
    }

    if (normalizedRunKey === String(runKey || '').trim()) {
      clearActiveRunState('');
    }
    fetchActiveRuns().catch(() => null);
  }, [clearActiveRunState, fetchActiveRuns, runKey]);

  const handleReloadBacktest = useCallback(async () => {
    if (!runKey || !activeRunApiBase) return;

    setIsReloadingSnapshot(true);
    try {
      const restartResp = await fetch(`${activeRunApiBase}/restart`, { method: 'POST' });
      if (!restartResp.ok) {
        // Backward-compatible fallback while backend restart endpoint is unavailable.
        const fallbackReloaded = await hydrateRunSnapshot(runKey, { showBusy: false });
        if (!fallbackReloaded) {
          const detail = await restartResp.json().catch(() => ({}));
          throw new Error(detail?.detail || `HTTP ${restartResp.status}`);
        }
        return;
      }

      const reloaded = await hydrateRunSnapshot(runKey, { showBusy: false });
      if (!reloaded) {
        console.warn('Backtest restart completed, but snapshot refresh failed.');
      }
    } catch (error) {
      console.error('Backtest restart failed:', error);
    } finally {
      setIsReloadingSnapshot(false);
    }
  }, [activeRunApiBase, hydrateRunSnapshot, runKey]);

  const handleAttachActiveRun = useCallback(async (targetRunKey) => {
    const ok = await hydrateRunSnapshot(targetRunKey, { showBusy: true });
    if (!ok) {
      setRuntimeNotice('Failed to attach selected run snapshot.');
      return;
    }
    setRuntimeNotice('');
  }, [hydrateRunSnapshot]);
  
  // Click marker on chart
  const handleMarkerClick = useCallback((markerOrId) => {
    if (!markerOrId) return;

    if (typeof markerOrId !== 'object') {
      const marker = decisionEvents.find((eventMarker) => eventMarker.id === markerOrId);
      if (marker) {
        setSelectedMarker({
          ...marker,
          __selectionSource: "chart",
        });
      }
      return;
    }

    let bestMatch = null;
    let bestScore = Number.NEGATIVE_INFINITY;
    decisionEvents.forEach((eventMarker) => {
      const score = scoreMarkerMatch(eventMarker, markerOrId);
      if (score > bestScore) {
        bestScore = score;
        bestMatch = eventMarker;
      }
    });

    if (bestMatch && bestScore > 100) {
      setSelectedMarker({
        ...bestMatch,
        __selectionSource: "chart",
      });
      return;
    }

    setSelectedMarker({
      ...markerOrId,
      __selectionSource: "chart",
    });
  }, [decisionEvents]);

  const activeRunConfigSidebarMode = useMemo<'all' | 'dates' | 'profiles' | 'start'>(() => {
    const activeItem = SIDEBAR_NAV_ITEMS.find((item) => item.id === activeSidebarNavItem);
    if (!activeItem || activeItem.sectionId !== 'run-config') {
      return 'all';
    }
    return activeItem.runConfigMode || 'all';
  }, [activeSidebarNavItem]);

  const runConfigSidebarContent = useMemo(() => (
    <RunConfig
      onStart={handleStartRun}
      isRunning={hasActiveAttachedRun}
      onTickerChange={setSelectedTicker}
      effectiveExecutionConfig={effectiveExecutionConfig}
      activeRuns={activeRuns}
      activeRunKey={runKey}
      onAttachRun={handleAttachActiveRun}
      onKillRun={handleKillAndDeleteRun}
      sidebarSubsection={activeRunConfigSidebarMode}
      authToken={authSnapshot.token || ''}
      activeRunState={runState}
    />
  ), [
    activeRuns,
    activeRunConfigSidebarMode,
    authSnapshot.token,
    effectiveExecutionConfig,
    handleAttachActiveRun,
    handleKillAndDeleteRun,
    handleStartRun,
    hasActiveAttachedRun,
    runState,
    runKey,
  ]);

  const strategySettingsSidebarContent = useMemo(() => (
    <StrategyModuleToggles
      apiUrl={strategyApiUrl}
      selectedTicker={selectedTicker}
      onNavigateToStudio={() => setActiveView('adaptive-studio')}
    />
  ), [selectedTicker, strategyApiUrl]);

  const executionModulesSidebarContent = useMemo(() => (
    <ExecutionModuleToggles />
  ), []);

  const playbackSidebarContent = useMemo(() => {
    if (!runKey) return null;
    return (
      <PlaybackControls
        runState={runState}
        isPlaying={isPlaying}
        speed={speed}
        tradeEvaluationMode={tradeEvaluationMode}
        isReloading={isReloadingSnapshot}
        onSpeedChange={setSpeed}
        onTradeEvaluationModeChange={setTradeEvaluationMode}
        onStep={handleStep}
        onPlay={handlePlay}
        onPause={handlePause}
        onStop={handleStop}
        onReload={handleReloadBacktest}
        onReset={handleReset}
      />
    );
  }, [
    handlePause,
    handlePlay,
    handleReloadBacktest,
    handleReset,
    handleStep,
    handleStop,
    isPlaying,
    isReloadingSnapshot,
    runKey,
    runState,
    speed,
    tradeEvaluationMode,
  ]);

  const sessionSummarySidebarContent = useMemo(() => {
    if (!runState) return null;
    return <SessionSummary runState={runState} markers={markers} />;
  }, [markers, runState]);

  const sidebarSections = useMemo(() => {
    const sections: Array<{
      id: string;
      title: string;
      rangeLabel: string;
      maxHeight: number;
      content: any;
    }> = [
      {
        id: 'run-config',
        title: 'Run Configuration',
        rangeLabel: 'Range A',
        maxHeight: 780,
        content: runConfigSidebarContent,
      },
      {
        id: 'strategy-settings',
        title: 'Strategy Settings',
        rangeLabel: 'Range B',
        maxHeight: 720,
        content: strategySettingsSidebarContent,
      },
      {
        id: 'execution-modules',
        title: 'Global Modules',
        rangeLabel: 'Range E',
        maxHeight: 720,
        content: executionModulesSidebarContent,
      },
    ];

    if (playbackSidebarContent) {
      sections.push({
        id: 'playback-controls',
        title: 'Playback Controls',
        rangeLabel: 'Range C',
        maxHeight: 420,
        content: playbackSidebarContent,
      });
    }

    if (sessionSummarySidebarContent) {
      sections.push({
        id: 'session-summary',
        title: 'Session Summary',
        rangeLabel: 'Range D',
        maxHeight: 340,
        content: sessionSummarySidebarContent,
      });
    }

    return sections;
  }, [
    executionModulesSidebarContent,
    playbackSidebarContent,
    runConfigSidebarContent,
    sessionSummarySidebarContent,
    strategySettingsSidebarContent,
  ]);

  const sidebarNavItems = useMemo(() => {
    const availableSectionIds = new Set(sidebarSections.map((section) => section.id));
    return SIDEBAR_NAV_ITEMS.filter((item) => availableSectionIds.has(item.sectionId));
  }, [sidebarSections]);

  const sidebarSectionsById = useMemo(() => {
    const map = new Map<string, (typeof sidebarSections)[number]>();
    sidebarSections.forEach((section) => {
      map.set(section.id, section);
    });
    return map;
  }, [sidebarSections]);

  const activeSidebarSectionId = useMemo(() => {
    const activeItem = sidebarNavItems.find((item) => item.id === activeSidebarNavItem);
    return activeItem?.sectionId || null;
  }, [activeSidebarNavItem, sidebarNavItems]);

  const isSidebarExpanded =
    isSidebarRailExpanded && sidebarNavItems.length > 0;

  const focusSidebarField = useCallback((fieldId: string | null) => {
    if (!fieldId) return;
    window.setTimeout(() => {
      const element = document.getElementById(fieldId);
      if (!element) return;
      element.scrollIntoView({ behavior: 'smooth', block: 'center' });
      element.classList.add('sidebar-field-focus');
      window.setTimeout(() => {
        element.classList.remove('sidebar-field-focus');
      }, 920);
    }, 110);
  }, []);

  useEffect(() => {
    if (!sidebarNavItems.length) {
      setActiveSidebarNavItem(null);
      return;
    }
    setActiveSidebarNavItem((prev) => {
      if (prev === null) {
        return null;
      }
      if (prev && sidebarNavItems.some((item) => item.id === prev)) {
        return prev;
      }
      return sidebarNavItems[0].id;
    });
  }, [sidebarNavItems]);



  const handleSidebarNavToggle = useCallback((item: SidebarNavItem) => {
    const runConfigSectionOpen = activeSidebarSectionId === 'run-config';
    const clickedRunConfigHost = item.sectionId === 'run-config' && item.id === RUN_CONFIG_PANEL_HOST_ID;
    const isClosingCurrentItem = activeSidebarNavItem === item.id;
    const collapsingRunConfigHost =
      clickedRunConfigHost && activeSidebarNavItem === RUN_CONFIG_PANEL_HOST_ID;

    if (item.sectionId === 'run-config') {
      // Collapse only when re-clicking the currently active run-config item.
      // This keeps the RunConfig subtree mounted when switching Date Range <-> Profiles.
      if (runConfigSectionOpen && (isClosingCurrentItem || collapsingRunConfigHost)) {
        setActiveSidebarNavItem(null);
        return;
      }
    } else if (isClosingCurrentItem) {
      setActiveSidebarNavItem(null);
      return;
    }

    setActiveSidebarNavItem(item.id);
    setIsSidebarRailExpanded(true);
    window.setTimeout(() => {
      const navElement = document.getElementById(`sidebar-nav-${item.id}`);
      navElement?.scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'nearest' });
    }, 40);
    focusSidebarField(item.focusFieldId);
  }, [activeSidebarNavItem, activeSidebarSectionId, focusSidebarField]);

  const handleSidebarMouseEnter = useCallback(() => {
    setIsSidebarRailExpanded(true);
  }, []);

  const handleSidebarMouseLeave = useCallback(() => {
    setIsSidebarRailExpanded(false);
  }, []);

  const handleSidebarResizeMouseDown = useCallback((event: ReactMouseEvent<HTMLDivElement>) => {
    if (typeof window === 'undefined') return;
    if (window.innerWidth <= MOBILE_SIDEBAR_BREAKPOINT) return;
    event.preventDefault();
    const startWidth = clampSidebarWidth(sidebarWidth);
    sidebarResizeStateRef.current = {
      startX: event.clientX,
      startWidth,
    };

    const onMouseMove = (moveEvent: MouseEvent) => {
      if (!sidebarResizeStateRef.current) return;
      const deltaX = moveEvent.clientX - sidebarResizeStateRef.current.startX;
      const nextWidth = clampSidebarWidth(sidebarResizeStateRef.current.startWidth + deltaX);
      setSidebarWidth(nextWidth);
    };

    const onMouseUp = () => {
      sidebarResizeStateRef.current = null;
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onMouseUp);
    };

    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);
  }, [sidebarWidth]);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    window.localStorage.setItem(SIDEBAR_WIDTH_STORAGE_KEY, String(clampSidebarWidth(sidebarWidth)));
  }, [sidebarWidth]);
  
  // Debug state moved to top level
  
  return (
    <div className="app-container">
      {/* Dark Sidebar */}
      <aside
        className={`app-sidebar ${isNavOpen ? 'mobile-open' : ''}`}
        style={{ width: `${clampSidebarWidth(sidebarWidth)}px`, minWidth: `${clampSidebarWidth(sidebarWidth)}px` }}
      >
        <div className="sidebar-brand">
          <span className="sidebar-brand-icon">📈</span>
          <div className="sidebar-brand-text">
            <span className="sidebar-brand-name">Backtest Runner</span>
            <span className="sidebar-brand-tagline">Trading Workspace</span>
          </div>
        </div>

        <nav className="sidebar-main-nav">
          {VIEW_TABS.map((tab) => (
            <button
              key={tab.id}
              className={`sidebar-nav-btn ${activeView === tab.id ? 'active' : ''}`}
              onClick={() => { setActiveView(tab.id); setIsNavOpen(false); }}
              title={tab.label}
            >
              <span className="sidebar-nav-icon">{tab.icon}</span>
              <span className="sidebar-nav-label">{tab.label}</span>
            </button>
          ))}
        </nav>

        {activeView === 'backtest' && sidebarNavItems.length > 0 && (
          <>
            <div className="sidebar-divider" />
            <div className="sidebar-section-nav" ref={sidebarRailRef}>
              {runtimeNotice && (
                <div className="sidebar-notice">
                  {runtimeNotice}
                </div>
              )}

              {sidebarNavItems.map((item, itemIndex) => {
                const section = sidebarSectionsById.get(item.sectionId);
                if (!section) return null;
                const isActiveItem = activeSidebarNavItem === item.id;
                const isRunConfigItem = section.id === 'run-config';

                return (
                  <div
                    key={item.id}
                    className={`sidebar-section-entry ${!isRunConfigItem && isActiveItem ? 'open' : ''}`}
                    style={{ order: itemIndex * 2 }}
                  >
                    <button
                      id={`sidebar-nav-${item.id}`}
                      type="button"
                      className={`sidebar-section-btn ${isActiveItem ? 'active' : ''}`}
                      onClick={() => handleSidebarNavToggle(item)}
                      aria-expanded={isActiveItem}
                      title={`${item.label} (${item.rangeLabel})`}
                    >
                      <span className="sidebar-section-icon">{item.icon}</span>
                      <span className="sidebar-section-label">{item.label}</span>
                      <span className="sidebar-section-badge">{item.rangeLabel}</span>
                      <span className={`sidebar-section-caret ${isActiveItem ? 'open' : ''}`}>▾</span>
                    </button>
                    {/* Non-run-config items render their panel inline */}
                    {!isRunConfigItem && isActiveItem && (
                      <div className="sidebar-panel">
                        <div className="sidebar-panel-content">
                          {section.content}
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
              {/* Shared run-config panel: always at same tree position to prevent remount,
                  CSS order places it visually after the active run-config nav item */}
              {activeSidebarSectionId === 'run-config' && (() => {
                const section = sidebarSectionsById.get('run-config');
                if (!section) return null;
                const activeIdx = sidebarNavItems.findIndex((i) => i.id === activeSidebarNavItem);
                return (
                  <div
                    className="sidebar-section-entry open"
                    style={{ order: activeIdx >= 0 ? activeIdx * 2 + 1 : 999 }}
                  >
                    <div className="sidebar-panel">
                      <div className="sidebar-panel-content">
                        {section.content}
                      </div>
                    </div>
                  </div>
                );
              })()}
            </div>
          </>
        )}
        <div
          className="sidebar-resize-handle"
          onMouseDown={handleSidebarResizeMouseDown}
          role="separator"
          aria-orientation="vertical"
          aria-label="Resize sidebar"
          title="Drag to resize sidebar"
        />
      </aside>

      {/* Mobile overlay */}
      {isNavOpen && <div className="sidebar-overlay" onClick={() => setIsNavOpen(false)} />}

      {/* Main Content Area */}
      <div className="app-main">
        {/* Slim Top Bar */}
        <header className="app-topbar">
          <button
            type="button"
            className="sidebar-mobile-toggle"
            onClick={() => setIsNavOpen((prev) => !prev)}
            aria-label="Toggle sidebar"
          >
            <span /><span /><span />
          </button>

          <div className="topbar-spacer" />

          <div className="topbar-status">
            <div className="connection-indicator">
              <span className={`status-dot ${isConnected ? 'connected' : ''}`} />
              <span>{isConnected ? 'Connected' : 'Disconnected'}</span>
            </div>
            <span className={`plan-badge plan-${String(planTier || 'free').toLowerCase()}`}>
              {String(planTier || 'free').toUpperCase()}
            </span>
            {quotaSnapshot?.usage && quotaSnapshot?.limits ? (
              <span className="quota-badge">
                {quotaSnapshot.usage.active_runs || 0}/{quotaSnapshot.limits.concurrent_runs || 0} runs
              </span>
            ) : null}
            {authSnapshot.enabled ? (
              authSnapshot.signedIn ? (
                <>
                  <span className="auth-user-badge" title={authSnapshot.userId || undefined}>
                    {authSnapshot.email || authSnapshot.userId || 'Signed In'}
                  </span>
                  <button
                    type="button"
                    className="auth-action-btn"
                    disabled={authActionBusy}
                    onClick={handleAuthSignOut}
                  >
                    {authActionBusy ? '...' : 'Sign Out'}
                  </button>
                </>
              ) : (
                <button
                  type="button"
                  className="auth-action-btn"
                  disabled={authActionBusy}
                  onClick={handleAuthSignIn}
                >
                  {authActionBusy ? '...' : 'Sign In (Google)'}
                </button>
              )
            ) : (
              <span className="auth-user-badge auth-disabled">Auth Off</span>
            )}
          </div>
        </header>

        {showAdSlot ? (
          <section className="ad-slot">
            <span className="ad-label">Sponsored</span>
            <span className="ad-text">Upgrade to PREMIUM for ad-free workspace and higher limits.</span>
          </section>
        ) : null}

        {/* View Content */}
        <div className="app-view">
          {activeView === 'data-manager' ? (
            <DataManager downloadProgress={downloadProgress} />
          ) : activeView === 'strategy-analyzer' ? (
            <StrategyAnalyzer
              selectedTicker={selectedTicker}
              onTickerChange={setSelectedTicker}
              strategyApiUrl={strategyApiUrl}
              onStartRun={handleStartRun}
              onPlayRun={handlePlay}
              onPauseRun={handlePause}
              onStepRun={handleStep}
              onEvaluateIntrabarSlice={handleEvaluateIntrabarSlice}
              onClearRun={handleReset}
              isPlayingRun={isPlaying}
              attachedRunKey={runKey}
              attachedRunState={runState}
              attachedRunBars={bars}
              decisionEvents={decisionEvents}
              selectedMarker={selectedMarker}
              latestBarAnalysis={latestBarAnalysis}
              onDecisionSelectMarker={setSelectedMarker}
              onChartMarkerClick={handleMarkerClick}
              onSwitchToBacktest={() => setActiveView('backtest')}
            />
          ) : activeView === 'adaptive-studio' ? (
            <AdaptiveStrategyStudio
              selectedTicker={selectedTicker}
              onTickerChange={setSelectedTicker}
              strategyApiUrl={strategyApiUrl}
            />
          ) : activeView === 'adaptive-tuner' ? (
            <AdaptiveTuner
              selectedTicker={selectedTicker}
              onTickerChange={setSelectedTicker}
              strategyApiUrl={strategyApiUrl}
            />
          ) : activeView === 'diagnostics' ? (
            <DiagnosticCalendar />
          ) : activeView === 'live-trader' ? (
            <LiveTraderMonitor />
          ) : (
          <main className="app-content">
        {/* Left Sidebar */}
        {/* Chart area — sidebar is now outside app-content */}
        
        {/* Chart */}
        <section className="card chart-container">
          <div className="card-header">
            <span className="card-title">
              {runState
                ? `${runState.ticker} - ${
                    runState.date_from && runState.date_to
                      ? `${runState.date_from} → ${runState.date_to}`
                      : runState.date
                  }`
                : 'Price Chart'}
            </span>
            {runState && (
              <span className={`phase-badge ${runState.phase?.toLowerCase()}`}>
                {runState.phase}
              </span>
            )}
            <div className="chart-toolbar">
                <select
                    className="chart-timeframe"
                    value={timeframe}
                    onChange={(e) => setTimeframe(e.target.value)}
                >
                    <option value="1min">1 Min</option>
                    <option value="5min">5 Min</option>
                    <option value="15min">15 Min</option>
                    <option value="30min">30 Min</option>
                    <option value="1h">1 Hour</option>
                </select>
                
                {/* Marker Visibility Toggles */}
                <div className="marker-toggles">
                    <button
                        className={`toggle-btn ${markerVisibility.entries ? 'active' : ''}`}
                        onClick={() => toggleMarkerVisibility('entries')}
                        title="Toggle Entry Markers"
                    >
                        E
                    </button>
                    <button
                        className={`toggle-btn ${markerVisibility.exits ? 'active' : ''}`}
                        onClick={() => toggleMarkerVisibility('exits')}
                        title="Toggle Exit/SL/TP Markers"
                    >
                        X
                    </button>
                    <button
                        className={`toggle-btn ${markerVisibility.icebergs ? 'active' : ''}`}
                        onClick={() => toggleMarkerVisibility('icebergs')}
                        title="Toggle Iceberg Markers"
                    >
                        ❄️
                    </button>
                    <button
                        className={`toggle-btn ${markerVisibility.regime ? 'active' : ''}`}
                        onClick={() => toggleMarkerVisibility('regime')}
                        title="Toggle Regime Markers"
                    >
                        R
                    </button>
                    <button
                        className={`toggle-btn ${markerVisibility.strategy ? 'active' : ''}`}
                        onClick={() => toggleMarkerVisibility('strategy')}
                        title="Toggle Strategy Markers"
                    >
                        S
                    </button>
                </div>
                
                <button
                    className={`chart-tab ${activeTab === 'standard' ? 'active' : ''}`}
                    onClick={() => setActiveTab('standard')}
                >
                    Candles
                </button>
                <button
                    className={`chart-tab ${activeTab === 'l2' ? 'active' : ''}`}
                    onClick={() => setActiveTab('l2')}
                >
                    L2 Footprint
                </button>
            </div>
          </div>
          <div className="chart-wrapper">
            {activeTab === 'standard' ? (
                <CandlestickChart 
                  bars={displayedBars} 
                  markers={filteredMarkers}
                  icebergs={filteredIcebergs}
                  onMarkerClick={handleMarkerClick}
                  onBarClick={setSelectedIntrabar}
                  selectedMarker={selectedMarker}
                  chartState={chartState}
                  onChartStateChange={handleChartStateChange}
                  priceRange={priceRange}
                  onPriceRangeChange={setPriceRange}
                  l2Data={l2Data} 
                />
            ) : (
                <FootprintChart 
                  bars={displayedBars} 
                  markers={filteredMarkers}
                  icebergs={filteredIcebergs}
                  onMarkerClick={handleMarkerClick}
                  selectedMarker={selectedMarker}
                  l2Data={l2Data}
                  chartState={chartState}
                  onChartStateChange={handleChartStateChange}
                  priceRange={priceRange}
                  onPriceRangeChange={setPriceRange}
                />
            )}
          </div>
          {currentBar && (
            <div className="current-bar-info">
              <div className="bar-stat">
                <div className="bar-stat-value">${currentBar.open?.toFixed(2)}</div>
                <div className="bar-stat-label">Open</div>
              </div>
              <div className="bar-stat">
                <div className="bar-stat-value up">${currentBar.high?.toFixed(2)}</div>
                <div className="bar-stat-label">High</div>
              </div>
              <div className="bar-stat">
                <div className="bar-stat-value down">${currentBar.low?.toFixed(2)}</div>
                <div className="bar-stat-label">Low</div>
              </div>
              <div className="bar-stat">
                <div className={`bar-stat-value ${currentBar.close >= currentBar.open ? 'up' : 'down'}`}>
                  ${currentBar.close?.toFixed(2)}
                </div>
                <div className="bar-stat-label">Close</div>
              </div>
            </div>
          )}
          {/* Intrabar Panel - shown when a bar is clicked */}
          {selectedIntrabar && activeRun && (
            <IntrabarPanel
              runId={activeRun.runId}
              ticker={activeRun.ticker}
              date={activeRun.date}
              selectedBar={selectedIntrabar}
              onClose={() => setSelectedIntrabar(null)}
            />
          )}
        </section>
        
        {/* Right Panel - Decisions */}
        <aside className="card decision-panel">
          <div className="card-header">
            <span className="card-title">Decisions</span>
            <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>
              {decisionEvents.length} total
            </span>
          </div>
          <div className="card-body">
            <DecisionPanel 
              markers={decisionEvents}
              selectedMarker={selectedMarker}
              onSelectMarker={setSelectedMarker}
            />
          </div>
        </aside>
          </main>
          )}
        </div>
      </div>
    </div>
  );
}

export default App;
