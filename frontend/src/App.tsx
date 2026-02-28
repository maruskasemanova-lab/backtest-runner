import {
  useState,
  useEffect,
  useRef,
  useCallback,
  useMemo,
} from 'react';
import {
  normalizeIsoDay,
  defaultStrategyApiUrl,
} from './utils';
import {
  type IntradayLevelsDialogSelection,
} from './intradayLevelsUtils';
import {
  type CandlestickChartBar,
  type CandlestickChartPriceRange,
  type CandlestickChartVisibleRange,
} from './components/CandlestickChart';
import AppSidebar from './components/AppSidebar';
import AppTopbar from './components/AppTopbar';
import AppViewRouter from './components/AppViewRouter';
import type {
  StrategyAnalyzerConditionsLiveAnalysis,
  StrategyAnalyzerDecisionMarker,
  StrategyAnalyzerOnEvaluateIntrabarSlice,
  StrategyAnalyzerRunBarLike,
} from './components/strategy-analyzer/types';
import {
  ACTIVE_RUNS_POLL_BACKTEST_VISIBLE_MS,
  ACTIVE_RUNS_POLL_OTHER_VISIBLE_MS,
  buildEffectiveExecutionConfigSnapshot,
  buildRunApiBase,
  buildRunKeyFromState,
  buildStrategyAnalyzerDayUrl,
  clampSidebarWidth,
  DEFAULT_FEATURE_FLAGS,
  extractLiveBarAnalysis,
  ICEBERG_FETCH_LIMIT,
  ICEBERG_FETCH_MIN_HIDDEN_SIZE,
  ICEBERG_FETCH_MIN_TRADE_SIZE,
  ICEBERG_RENDER_LIMIT,
  type DiagnosticAnalyzerOpenDayRequest,
  type InitialAppUrlState,
  mergeRunStateWithStreamBar,
  MOBILE_SIDEBAR_BREAKPOINT,
  normalizeNonEmptyToken,
  parseRunKey,
  readErrorDetail,
  readInitialAppUrlState,
  readInitialSidebarWidth,
  readStoredAuthToken,
  resolveRunDateWindow,
  resolveTradeModeFromExecutionConfig,
  RUN_CONFIG_PANEL_HOST_ID,
  RUN_ID_COLLISION_PATTERN,
  SIDEBAR_NAV_ITEMS,
  SIDEBAR_WIDTH_STORAGE_KEY,
  toChartBar,
  upsertDecisionMarker,
  upsertStreamChartBar,
  WS_CONNECT_ATTEMPTS_BEFORE_FALLBACK,
  WS_FALLBACK_NOTICE,
  WS_RECONNECT_BASE_MS,
  WS_RECONNECT_MAX_MS,
} from './app/appShared';
import {
  isRunStreamMessageRelevant,
  shouldQueueVisibilitySyncMessage,
} from './app/appWebSocketShared';
import { useAppAuthState } from './hooks/useAppAuthState';
import {
  useActiveRunsQuery,
  useIcebergsQuery,
  useL2FootprintQuery,
  useUsageSnapshotQuery,
} from './hooks/useAppServerQueries';
import { useAppPresentationData } from './hooks/useAppPresentationData';
import { useBacktestSidebarSections } from './hooks/useBacktestSidebarSections';
import { useChartSelectionActions } from './hooks/useChartSelectionActions';
import { useRunControlActions } from './hooks/useRunControlActions';
import { useRunSnapshotActions } from './hooks/useRunSnapshotActions';
import { useSidebarInteractions } from './hooks/useSidebarInteractions';
import { useRunWebSocket } from './hooks/useRunWebSocket';

function App() {
  const [initialUrlState] = useState<InitialAppUrlState>(() => readInitialAppUrlState());
  // Run state
  const [runKey, setRunKey] = useState(null);
  const [runState, setRunState] = useState(null);
  const [effectiveExecutionConfig, setEffectiveExecutionConfig] = useState(null);
  
  // Data
  const [bars, setBars] = useState<CandlestickChartBar[]>([]);
  const [markers, setMarkers] = useState<StrategyAnalyzerDecisionMarker[]>([]);
  const [selectedMarker, setSelectedMarker] = useState<StrategyAnalyzerDecisionMarker | null>(null);
  const [currentBar, setCurrentBar] = useState<StrategyAnalyzerRunBarLike | null>(null);
  const [latestBarAnalysis, setLatestBarAnalysis] = useState<StrategyAnalyzerConditionsLiveAnalysis>(null);
  const [selectedIntrabar, setSelectedIntrabar] = useState(null);
  const [selectedIntradayLevels, setSelectedIntradayLevels] = useState<IntradayLevelsDialogSelection | null>(null);
  const [selectedTicker, setSelectedTicker] = useState<string | null>(initialUrlState.selectedTicker);
  const [strategyApiUrl, setStrategyApiUrl] = useState(defaultStrategyApiUrl);
  const [diagnosticAnalyzerOpenDayRequest, setDiagnosticAnalyzerOpenDayRequest] =
    useState<DiagnosticAnalyzerOpenDayRequest | null>(initialUrlState.strategyAnalyzerOpenDayRequest);
  
  // View navigation
  const [activeView, setActiveView] = useState(initialUrlState.activeView); // "backtest" | "data-manager" | "adaptive-studio" | "adaptive-tuner" | "diagnostics" | "live-trader"
  const [isNavOpen, setIsNavOpen] = useState(false);
  const [downloadProgress, setDownloadProgress] = useState(null);
  const [activeSidebarNavItem, setActiveSidebarNavItem] = useState<string | null>(SIDEBAR_NAV_ITEMS[0]?.id ?? null);
  const [isSidebarRailExpanded, setIsSidebarRailExpanded] = useState(false);
  const [sidebarWidth, setSidebarWidth] = useState<number>(readInitialSidebarWidth);

  // L2 Data
  const [activeTab, setActiveTab] = useState("standard"); // "standard" or "l2"
  const [timeframe, setTimeframe] = useState("1min");
  
  // Chart Synchronization State
  const [chartState, setChartState] = useState<CandlestickChartVisibleRange | null>(null); // { from: number, to: number } (Time Range)
  const [priceRange, setPriceRange] = useState<CandlestickChartPriceRange>(null); // { from: number, to: number } (Price Range)

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
  const {
    authActionBusy,
    authSnapshot,
    handleAuthSignIn,
    handleAuthSignOut,
  } = useAppAuthState({ setRuntimeNotice });
  
  // WebSocket
  const barsLengthRef = useRef(0);
  const [isPageVisible, setIsPageVisible] = useState(() =>
    typeof document === 'undefined' ? true : document.visibilityState === 'visible'
  );
  const isPageVisibleRef = useRef(isPageVisible);
  const pendingVisibilitySyncRef = useRef(false);
  const sidebarRailRef = useRef<HTMLDivElement | null>(null);
  const activeRun = useMemo(() => parseRunKey(runKey), [runKey]);
  const activeRunId = activeRun?.runId || null;
  const activeRunTicker = activeRun?.ticker || null;
  const activeRunDate = activeRun?.date || null;
  const activeRunApiBase = useMemo(() => buildRunApiBase(activeRun), [activeRun]);
  const usageToken = useMemo(
    () => normalizeNonEmptyToken(authSnapshot.token) || readStoredAuthToken(),
    [authSnapshot.token]
  );
  const activeRunsPollInterval = useMemo(
    () =>
      activeView === 'backtest'
        ? ACTIVE_RUNS_POLL_BACKTEST_VISIBLE_MS
        : ACTIVE_RUNS_POLL_OTHER_VISIBLE_MS,
    [activeView]
  );
  const activeRunsQuery = useActiveRunsQuery({
    enabled: isPageVisible,
    refetchIntervalMs: activeRunsPollInterval,
    toRunKey: buildRunKeyFromState,
  });
  const activeRuns = useMemo(
    () => (Array.isArray(activeRunsQuery.data) ? activeRunsQuery.data : []),
    [activeRunsQuery.data]
  );
  const usageSnapshotQuery = useUsageSnapshotQuery({
    enabled: isPageVisible,
    token: usageToken,
    defaultFeatureFlags: DEFAULT_FEATURE_FLAGS,
  });
  const planTier = usageSnapshotQuery.data?.planTier || null;
  const quotaSnapshot = usageSnapshotQuery.data?.quotaSnapshot || null;
  const featureFlags = usageSnapshotQuery.data?.featureFlags || DEFAULT_FEATURE_FLAGS;
  const activeRunStateTicker = String(runState?.ticker || '').trim().toUpperCase();
  const activeRunDateWindow = useMemo(
    () => resolveRunDateWindow(runState),
    [runState?.date, runState?.date_from, runState?.date_to]
  );
  const l2FootprintQuery = useL2FootprintQuery({
    enabled: Boolean(runState && runKey && activeTab === 'l2'),
    ticker: activeRunStateTicker,
    timeframe,
    dateWindow: activeRunDateWindow,
  });
  const l2Data = l2FootprintQuery.data ?? null;
  const icebergsQuery = useIcebergsQuery({
    enabled: Boolean(runState && runKey && markerVisibility.icebergs),
    ticker: activeRunStateTicker,
    dateWindow: activeRunDateWindow,
    fetchLimit: ICEBERG_FETCH_LIMIT,
    minHiddenSize: ICEBERG_FETCH_MIN_HIDDEN_SIZE,
    minTradeSize: ICEBERG_FETCH_MIN_TRADE_SIZE,
  });
  const icebergs = markerVisibility.icebergs ? (icebergsQuery.data ?? []) : [];
  const refreshActiveRuns = useCallback(() => {
    activeRunsQuery.refetch().catch((error) => {
      console.debug('Failed to refresh active runs:', error);
    });
  }, [activeRunsQuery.refetch]);
  const hasActiveAttachedRun = useMemo(() => {
    if (!runState || typeof runState !== 'object') return false;
    // Keep config editable after load/initialize so profile and strategy can still be adjusted.
    return Boolean(runState.is_running || runState.is_paused);
  }, [runState]);

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
    setSelectedIntradayLevels(null);
    setIsPlaying(false);
    pendingVisibilitySyncRef.current = false;
    if (notice) {
      setRuntimeNotice(notice);
    }
  }, []);

  const handleOpenDiagnosticDayInAnalyzer = useCallback(
    ({ ticker, isoDate, runKey }: { ticker: string; isoDate: string; runKey?: string | null }) => {
      const normalizedTicker = String(ticker || '').trim().toUpperCase();
      const normalizedDate = normalizeIsoDay(isoDate);
      if (!normalizedDate) return;
      const normalizedRunKey = String(runKey || '').trim();
      const fallbackTicker = String(selectedTicker || 'MU').trim().toUpperCase() || 'MU';
      const nextTicker = normalizedTicker || fallbackTicker;
      const nextUrl = buildStrategyAnalyzerDayUrl({
        ticker: nextTicker,
        isoDate: normalizedDate,
        runKey: normalizedRunKey || null,
      });
      if (typeof window !== 'undefined' && nextUrl) {
        // Force URL-based open to avoid transient handoff/loading flicker between views.
        window.location.assign(nextUrl);
        return;
      }
      setSelectedTicker(nextTicker);
      setDiagnosticAnalyzerOpenDayRequest({
        requestId: Date.now() + Math.random(),
        ticker: nextTicker,
        isoDate: normalizedDate,
        runKey: normalizedRunKey || null,
      });
      setActiveView('strategy-analyzer');
      setIsNavOpen(false);
    },
    [selectedTicker]
  );

  const handleStrategyAnalyzerOpenDayRequestHandled = useCallback((requestId: number) => {
    setDiagnosticAnalyzerOpenDayRequest((current) => {
      if (!current) return current;
      return current.requestId === requestId ? null : current;
    });
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

  useEffect(() => {
    if (!activeRunsQuery.error) return;
    console.debug('Failed to refresh active runs:', activeRunsQuery.error);
  }, [activeRunsQuery.error]);

  useEffect(() => {
    if (!usageSnapshotQuery.error) return;
    console.debug('Failed to fetch v2 usage snapshot:', usageSnapshotQuery.error);
  }, [usageSnapshotQuery.error]);

  useEffect(() => {
    if (!l2FootprintQuery.error) return;
    console.error('L2 fetch error:', l2FootprintQuery.error);
  }, [l2FootprintQuery.error]);

  useEffect(() => {
    if (!icebergsQuery.error) return;
    console.error('Iceberg fetch error:', icebergsQuery.error);
  }, [icebergsQuery.error]);

  const handleWsMessage = useCallback((data) => {
    if (
      !isRunStreamMessageRelevant(data, {
        runKey,
        runId: activeRunId,
        ticker: activeRunTicker,
        date: activeRunDate,
      })
    ) {
      return;
    }

    if (shouldQueueVisibilitySyncMessage(data, isPageVisibleRef.current)) {
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
  const { isConnected, isPollingFallback } = useRunWebSocket({
    activeRunId,
    activeRunKey: runKey,
    onMessage: handleWsMessage,
    setRuntimeNotice,
    fallbackNotice: WS_FALLBACK_NOTICE,
    reconnectBaseMs: WS_RECONNECT_BASE_MS,
    reconnectMaxMs: WS_RECONNECT_MAX_MS,
    maxHandshakeAttempts: WS_CONNECT_ATTEMPTS_BEFORE_FALLBACK,
  });

  useEffect(() => {
    setIsNavOpen(false);
  }, [activeView]);
  
  // Handle new bar from WebSocket
  const handleEvaluateIntrabarSlice = useCallback<StrategyAnalyzerOnEvaluateIntrabarSlice>(async (ts: number) => {
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
  const handleNewBar = useCallback((bar: StrategyAnalyzerRunBarLike | null | undefined) => {
    const chartBar = toChartBar(bar);
    if (!chartBar) return;

    setBars((prev) => upsertStreamChartBar(prev, chartBar));
    setCurrentBar(bar);
    const liveBarAnalysis = extractLiveBarAnalysis(bar);
    if (liveBarAnalysis) {
      setLatestBarAnalysis(liveBarAnalysis);
    }
    setRunState((prev) => mergeRunStateWithStreamBar(prev, bar));
  }, []);
  
  // Handle new decision from WebSocket
  const handleNewDecision = useCallback((marker) => {
    setMarkers((prev) => upsertDecisionMarker(prev, marker));
  }, []);

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

  const {
    displayedBars,
    filteredMarkers,
    filteredIcebergs,
    showAdSlot,
    decisionEvents,
  } = useAppPresentationData({
    bars,
    timeframe,
    markers,
    markerVisibility,
    icebergs,
    icebergRenderLimit: ICEBERG_RENDER_LIMIT,
    featureFlags,
    planTier,
    activeView,
  });

  // Toggle marker visibility helper
  const toggleMarkerVisibility = useCallback((key) => {
      setMarkerVisibility(prev => ({ ...prev, [key]: !prev[key] }));
  }, []);

  const {
    handleStartRun,
    handleKillAndDeleteRun,
    handleReloadBacktest,
    handleAttachActiveRun,
    handleOpenStoredRunSnapshot,
  } = useRunSnapshotActions({
    runKey,
    activeRunApiBase,
    authToken: usageToken,
    isPageVisible,
    clearActiveRunState,
    refreshActiveRuns,
    pendingVisibilitySyncRef,
    readErrorDetail,
    parseRunKey,
    buildRunApiBase,
    toChartBar,
    buildEffectiveExecutionConfigSnapshot,
    resolveTradeModeFromExecutionConfig,
    runIdCollisionPattern: RUN_ID_COLLISION_PATTERN,
    defaultStrategyApiUrl,
    setRunKey,
    setRunState,
    setEffectiveExecutionConfig,
    setChartState,
    setPriceRange,
    setBars,
    setMarkers,
    setSelectedMarker,
    setCurrentBar,
    setSelectedIntrabar,
    setSelectedIntradayLevels,
    setSelectedTicker,
    setStrategyApiUrl,
    setIsPlaying,
    setIsReloadingSnapshot,
    setTradeEvaluationMode,
    setRuntimeNotice,
  });
  
  const {
    handleStep,
    handlePlay,
    handlePause,
    handleStop,
    handleReset,
  } = useRunControlActions({
    activeRunApiBase,
    runState,
    speed,
    tradeEvaluationMode,
    isPlaying,
    isPageVisible,
    isPollingFallback,
    isPageVisibleRef,
    barsLengthRef,
    clearActiveRunState,
    refreshActiveRuns,
    handleNewBar,
    toChartBar,
    setRuntimeNotice,
    setIsPlaying,
    setTradeEvaluationMode,
    setRunState,
    setBars,
    setCurrentBar,
  });

  const {
    handleMarkerClick,
    closeIntradayLevelsDialog,
    handleBarClick,
  } = useChartSelectionActions({
    decisionEvents,
    markers,
    timeframe,
    currentBar,
    latestBarAnalysis,
    setSelectedMarker,
    setSelectedIntrabar,
    setSelectedIntradayLevels,
  });

  const {
    sidebarNavItems,
    sidebarSectionsById,
    activeSidebarSectionId,
  } = useBacktestSidebarSections({
    sidebarNavConfig: SIDEBAR_NAV_ITEMS,
    activeSidebarNavItem,
    activeRuns,
    runKey,
    runState,
    markers,
    hasActiveAttachedRun,
    effectiveExecutionConfig,
    authToken: authSnapshot.token || '',
    selectedTicker,
    strategyApiUrl,
    isPlaying,
    speed,
    tradeEvaluationMode,
    isReloadingSnapshot,
    setSelectedTicker,
    setActiveView,
    setSpeed,
    setTradeEvaluationMode,
    handleStartRun,
    handleAttachRun: handleAttachActiveRun,
    handleKillRun: handleKillAndDeleteRun,
    handleStep,
    handlePlay,
    handlePause,
    handleStop,
    handleReloadBacktest,
    handleReset,
  });

  const {
    handleSidebarNavToggle,
    handleSidebarResizeMouseDown,
  } = useSidebarInteractions({
    sidebarNavItems,
    activeSidebarNavItem,
    activeSidebarSectionId,
    runConfigPanelHostId: RUN_CONFIG_PANEL_HOST_ID,
    setActiveSidebarNavItem,
    isSidebarRailExpanded,
    setIsSidebarRailExpanded,
    sidebarWidth,
    setSidebarWidth,
    clampSidebarWidth,
    mobileSidebarBreakpoint: MOBILE_SIDEBAR_BREAKPOINT,
    sidebarWidthStorageKey: SIDEBAR_WIDTH_STORAGE_KEY,
  });
  
  // Debug state moved to top level
  
  return (
    <div className="app-container">
      <AppSidebar
        activeSidebarNavItem={activeSidebarNavItem}
        activeSidebarSectionId={activeSidebarSectionId}
        activeView={activeView}
        isNavOpen={isNavOpen}
        onSetActiveView={setActiveView}
        onSetNavOpen={setIsNavOpen}
        onSidebarNavToggle={handleSidebarNavToggle}
        onSidebarResizeMouseDown={handleSidebarResizeMouseDown}
        runtimeNotice={runtimeNotice}
        sidebarNavItems={sidebarNavItems}
        sidebarRailRef={sidebarRailRef}
        sidebarSectionsById={sidebarSectionsById}
        sidebarWidth={sidebarWidth}
      />

      {/* Main Content Area */}
      <div className="app-main">
        {/* Slim Top Bar */}
        <AppTopbar
          isConnected={isConnected}
          planTier={planTier}
          quotaSnapshot={quotaSnapshot}
          authSnapshot={authSnapshot}
          authActionBusy={authActionBusy}
          onToggleSidebar={() => setIsNavOpen((prev) => !prev)}
          onSignIn={handleAuthSignIn}
          onSignOut={handleAuthSignOut}
        />

        {showAdSlot ? (
          <section className="ad-slot">
            <span className="ad-label">Sponsored</span>
            <span className="ad-text">Upgrade to PREMIUM for ad-free workspace and higher limits.</span>
          </section>
        ) : null}

        {/* View Content */}
        <AppViewRouter
          activeView={activeView}
          downloadProgress={downloadProgress}
          selectedTicker={selectedTicker}
          setSelectedTicker={setSelectedTicker}
          strategyApiUrl={strategyApiUrl}
          handleStartRun={handleStartRun}
          handlePlay={handlePlay}
          handlePause={handlePause}
          handleStep={handleStep}
          handleEvaluateIntrabarSlice={handleEvaluateIntrabarSlice}
          handleReset={handleReset}
          isPlaying={isPlaying}
          runKey={runKey}
          runState={runState}
          bars={bars}
          decisionEvents={decisionEvents}
          selectedMarker={selectedMarker}
          latestBarAnalysis={latestBarAnalysis}
          setSelectedMarker={setSelectedMarker}
          handleMarkerClick={handleMarkerClick}
          setActiveView={setActiveView}
          handleOpenStoredRunSnapshot={handleOpenStoredRunSnapshot}
          diagnosticAnalyzerOpenDayRequest={diagnosticAnalyzerOpenDayRequest}
          handleStrategyAnalyzerOpenDayRequestHandled={handleStrategyAnalyzerOpenDayRequestHandled}
          handleOpenDiagnosticDayInAnalyzer={handleOpenDiagnosticDayInAnalyzer}
          timeframe={timeframe}
          setTimeframe={setTimeframe}
          markerVisibility={markerVisibility}
          toggleMarkerVisibility={toggleMarkerVisibility}
          activeTab={activeTab}
          setActiveTab={setActiveTab}
          displayedBars={displayedBars}
          filteredMarkers={filteredMarkers}
          filteredIcebergs={filteredIcebergs}
          chartState={chartState}
          handleChartStateChange={handleChartStateChange}
          priceRange={priceRange}
          setPriceRange={setPriceRange}
          l2Data={l2Data}
          handleBarClick={handleBarClick}
          currentBar={currentBar}
          selectedIntrabar={selectedIntrabar}
          activeRun={activeRun}
          setSelectedIntrabar={setSelectedIntrabar}
          selectedIntradayLevels={selectedIntradayLevels}
          closeIntradayLevelsDialog={closeIntradayLevelsDialog}
        />
      </div>
    </div>
  );
}

export default App;
