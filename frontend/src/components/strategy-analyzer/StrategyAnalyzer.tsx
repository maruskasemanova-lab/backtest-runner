import { useState, useEffect, useCallback, useRef, useMemo } from "react";
import IntradayLevelsDialog from "../IntradayLevelsDialog";
import StrategyAnalyzerAttachedPanels from "./StrategyAnalyzerAttachedPanels";
import StrategyAnalyzerChartPanel from "./StrategyAnalyzerChartPanel";
import StrategyAnalyzerDecisionsContent from "./StrategyAnalyzerDecisionsContent";
import StrategyAnalyzerEntryConditionsContent from "./StrategyAnalyzerEntryConditionsContent";
import StrategyAnalyzerUnifiedConfigWrapper from "./StrategyAnalyzerUnifiedConfigWrapper";
import StrategyAnalyzerHeaderControls from "./StrategyAnalyzerHeaderControls";
import StrategyAnalyzerRangeActions from "./StrategyAnalyzerRangeActions";
import type {
  StrategyAnalyzerChartHandle,
  StrategyAnalyzerAttachedRunState,
  StrategyAnalyzerChartMarkerClickTarget,
  StrategyAnalyzerConditionsLiveAnalysis,
  StrategyAnalyzerDecisionMarker,
  StrategyAnalyzerOnClearRun,
  StrategyAnalyzerOnEvaluateIntrabarSlice,
  StrategyAnalyzerOnPauseRun,
  StrategyAnalyzerOnRunControl,
  StrategyAnalyzerOnStartRun,
  StrategyAnalyzerTimelineCacheState,
  StrategyAnalyzerTradeEvalMode,
  StrategyAnalyzerRunBarLike,
} from "./types";
import { useStrategyAnalyzerChartData } from "./useStrategyAnalyzerChartData";
import { useStrategyAnalyzerConditions } from "./useStrategyAnalyzerConditions";
import { useIntradayLevelsDialog } from "./useIntradayLevelsDialog";
import { useStrategyAnalyzerBarsLoader } from "./useStrategyAnalyzerBarsLoader";
import { useStrategyAnalyzerPlaybackProgress } from "./useStrategyAnalyzerPlaybackProgress";
import { useStrategyAnalyzerRangePlayback } from "./useStrategyAnalyzerRangePlayback";
import { useStrategyAnalyzerRunOrchestration } from "./useStrategyAnalyzerRunOrchestration";
import { useStrategyAnalyzerTickerCatalog } from "./useStrategyAnalyzerTickerCatalog";
import { useStrategyAnalyzerTimelineCache } from "./useStrategyAnalyzerTimelineCache";
import { useStrategyAnalyzerRangeScrub } from "./useStrategyAnalyzerRangeScrub";
import {
  type StrategyAnalyzerOpenDayRequest,
  useStrategyAnalyzerOpenDayRequest,
} from "./useStrategyAnalyzerOpenDayRequest";
import { useStrategyAnalyzerWfo } from "./useStrategyAnalyzerWfo";

interface StrategyAnalyzerProps {
  selectedTicker: string | null;
  onTickerChange: (ticker: string) => void;
  strategyApiUrl: string;
  onStartRun?: StrategyAnalyzerOnStartRun;
  onPlayRun?: StrategyAnalyzerOnRunControl;
  onPauseRun?: StrategyAnalyzerOnPauseRun;
  onStepRun?: StrategyAnalyzerOnRunControl;
  onEvaluateIntrabarSlice?: StrategyAnalyzerOnEvaluateIntrabarSlice;
  onClearRun?: StrategyAnalyzerOnClearRun;
  isPlayingRun?: boolean;
  attachedRunKey?: string | null;
  attachedRunState?: StrategyAnalyzerAttachedRunState | null;
  attachedRunBars?: StrategyAnalyzerRunBarLike[];
  decisionEvents?: StrategyAnalyzerDecisionMarker[];
  selectedMarker?: StrategyAnalyzerDecisionMarker | null;
  latestBarAnalysis?: StrategyAnalyzerConditionsLiveAnalysis;
  onDecisionSelectMarker?: (marker: StrategyAnalyzerDecisionMarker) => void;
  onChartMarkerClick?: (markerOrId: StrategyAnalyzerChartMarkerClickTarget) => void;
  onSwitchToBacktest?: () => void;
  onOpenStoredRunSnapshot?: (runKey: string) => Promise<boolean>;
  openDayRequest?: StrategyAnalyzerOpenDayRequest | null;
  onOpenDayRequestHandled?: (requestId: number) => void;
}

/* ── component ───────────────────────────────────────────────────── */
export default function StrategyAnalyzer({
  selectedTicker,
  onTickerChange,
  strategyApiUrl,
  onStartRun,
  onPlayRun,
  onPauseRun,
  onStepRun,
  onClearRun,
  isPlayingRun = false,
  attachedRunKey,
  attachedRunState,
  attachedRunBars = [],
  decisionEvents = [],
  selectedMarker = null,
  latestBarAnalysis = null,
  onDecisionSelectMarker,
  onChartMarkerClick,
  onSwitchToBacktest,
  onEvaluateIntrabarSlice,
  onOpenStoredRunSnapshot,
  openDayRequest = null,
  onOpenDayRequestHandled,
}: StrategyAnalyzerProps) {
  // chart load
  const [ticker, setTicker] = useState(selectedTicker || "MU");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [warmupBars, setWarmupBars] = useState(240);

  // range selection
  const [rangeSelectMode, setRangeSelectMode] = useState(false);
  const [selectedRangeFrom, setSelectedRangeFrom] = useState<string | null>(null);
  const [selectedRangeTo, setSelectedRangeTo] = useState<string | null>(null);
  const chartRef = useRef<StrategyAnalyzerChartHandle | null>(null);
  const [rangeScrubOffset, setRangeScrubOffset] = useState(0);
  const [analyzerTradeEvalMode, setAnalyzerTradeEvalMode] = useState<StrategyAnalyzerTradeEvalMode>("intrabar_5s");

  // ── incremental caching refs for performance ─────────────────────
  // These refs hold pre-computed data structures that are incrementally
  // updated when new bars arrive, avoiding O(n) recomputation each time.
  const timelineCacheRef = useRef<StrategyAnalyzerTimelineCacheState>({
    processedRunBarCount: 0,
    runBarsByTime: new Map(),
    progressedTradeBars: [],
    timelinePoints: [],
    observedCheckpointCounts: [],
    warmupDone: 0,
    tradeDone: 0,
    startTime: null,
    endTime: null,
    rangeKey: null,
  });

  // strategy editor modal
  const [showStrategyEditor, setShowStrategyEditor] = useState(false);
  const [isConditionsDetached, setIsConditionsDetached] = useState(false);
  const [isDecisionsDetached, setIsDecisionsDetached] = useState(false);

  // run state
  const [analyzerRunKey, setAnalyzerRunKey] = useState<string | null>(null);

  const resetSelectionForNewData = useCallback(() => {
    setSelectedRangeFrom(null);
    setSelectedRangeTo(null);
    setRangeScrubOffset(0);
    setAnalyzerRunKey(null);
  }, []);

  const { bars, loading, barCount, loadBars, resetBarsState } = useStrategyAnalyzerBarsLoader({
    ticker,
    dateFrom,
    dateTo,
    setError,
    resetSelectionForNewData,
  });
  const {
    analyzerChartState,
    rangePlaybackMeta,
    selectedRangeWindow,
    handleAnalyzerChartStateChange,
  } = useStrategyAnalyzerRangePlayback({
    bars,
    selectedRangeFrom,
    selectedRangeTo,
    warmupBars,
  });

  const resetForTickerChange = useCallback(() => {
    resetBarsState();
    resetSelectionForNewData();
  }, [resetBarsState, resetSelectionForNewData]);

  const { tickers, loadingTickers, handleTickerChange } = useStrategyAnalyzerTickerCatalog({
    selectedTicker,
    onTickerChange,
    setTicker,
    setDateFrom,
    setDateTo,
    resetForTickerChange,
  });

  const isAnalyzerAttachedRun = useMemo(
    () =>
      Boolean(
        analyzerRunKey &&
          attachedRunKey &&
          String(analyzerRunKey).trim() === String(attachedRunKey).trim()
      ),
    [analyzerRunKey, attachedRunKey]
  );
  const analyzerDecisionEvents: StrategyAnalyzerDecisionMarker[] = isAnalyzerAttachedRun ? decisionEvents : [];
  const analyzerRunPhase = isAnalyzerAttachedRun ? String(attachedRunState?.phase || "").trim() : "";
  const analyzerRunFinished = isAnalyzerAttachedRun && !attachedRunState?.is_running && analyzerRunPhase === "COMPLETED";
  const { timelineCacheVersion } = useStrategyAnalyzerTimelineCache({
    isAnalyzerAttachedRun,
    rangePlaybackMeta,
    analyzerRunKey,
    attachedRunBars,
    timelineCacheRef,
  });
  const {
    rangeScrubBase,
    rangeScrubMeta,
    focusSelectedRangeOffset,
    moveSelectedRangeByStep,
  } = useStrategyAnalyzerRangeScrub({
    isAnalyzerAttachedRun,
    isPlayingRun,
    rangePlaybackMeta,
    timelineCacheVersion,
    timelineCacheRef,
    rangeScrubOffset,
    setRangeScrubOffset,
  });

  const { analyzerPlaybackProgress } = useStrategyAnalyzerPlaybackProgress({
    isAnalyzerAttachedRun,
    rangePlaybackMeta,
    timelineCacheVersion,
    attachedRunState,
    timelineCacheRef,
  });
  const analyzerDisplayPhase = analyzerPlaybackProgress?.isInitializing
    ? "INITIALIZING"
    : analyzerRunPhase;
  const { analyzerChartMarkers, chartBars } = useStrategyAnalyzerChartData({
    bars,
    isAnalyzerAttachedRun,
    analyzerRunFinished,
    selectedRangeWindow,
    rangeScrubMeta,
    analyzerDecisionEvents,
    timelineCacheVersion,
    timelineCacheRef,
  });
  const { runLoading, handleStartTest, handleClearAnalyzerRun } = useStrategyAnalyzerRunOrchestration({
    selectedRangeFrom,
    selectedRangeTo,
    ticker,
    strategyApiUrl,
    analyzerTradeEvalMode,
    rangePlaybackMeta,
    onStartRun,
    onSwitchToBacktest,
    onClearRun,
    isAnalyzerAttachedRun,
    setError,
    setRangeScrubOffset,
    setAnalyzerRunKey,
  });
  const {
    wfoEnabled,
    setWfoEnabled,
    wfoGridConfig,
    updateWfoGridConfig,
    estimatedCombinationCount,
    wfoIsRunning,
    wfoProgressLabel,
    rankedWfoResults,
    selectedWfoVariantId,
    bestWfoVariantId,
    handleRunWfo,
    handleSelectWfoVariant,
  } = useStrategyAnalyzerWfo({
    selectedRangeFrom,
    selectedRangeTo,
    ticker,
    strategyApiUrl,
    analyzerTradeEvalMode,
    rangePlaybackMeta,
    onOpenStoredRunSnapshot,
    setError,
    setRangeScrubOffset,
    setAnalyzerRunKey,
  });
  const {
    isScrubbingLiveEval,
    scrubbedConditionsActive,
    effectiveConditionsMarker,
    stableConditionsLiveAnalysis,
    hasConditionsPanelData,
    conditionsPanelBadge,
  } = useStrategyAnalyzerConditions({
    rangeScrubMeta,
    selectedMarker,
    latestBarAnalysis,
    onEvaluateIntrabarSlice,
  });
  const {
    selectedIntradayLevels,
    handleAnalyzerBarClick,
    closeIntradayLevelsDialog,
  } = useIntradayLevelsDialog({
    analyzerDecisionEvents,
    stableConditionsLiveAnalysis,
    analyzerRunKey,
    selectedRangeFrom,
    selectedRangeTo,
  });

  useEffect(() => {
    if (isAnalyzerAttachedRun) return;
    setIsConditionsDetached(false);
    setIsDecisionsDetached(false);
  }, [isAnalyzerAttachedRun]);

  useStrategyAnalyzerOpenDayRequest({
    openDayRequest,
    onOpenDayRequestHandled,
    onOpenStoredRunSnapshot,
    loadingTickers,
    tickersLength: tickers.length,
    selectedTicker,
    ticker,
    onTickerChange,
    setTicker,
    setDateFrom,
    setDateTo,
    setError,
    setRangeSelectMode,
    setSelectedRangeFrom,
    setSelectedRangeTo,
    setRangeScrubOffset,
    setAnalyzerRunKey,
    resetForTickerChange,
    resetSelectionForNewData,
    loading,
    dateFrom,
    dateTo,
    loadBars,
  });

  /* ── range selection callback ──────────────────────────────────── */
  const handleRangeSelected = useCallback((from: string, to: string) => {
    setSelectedRangeFrom(from);
    setSelectedRangeTo(to);
    setRangeScrubOffset(0);
    setRangeSelectMode(false);
  }, []);

  const handleClearRange = useCallback(() => {
    setSelectedRangeFrom(null);
    setSelectedRangeTo(null);
    setRangeScrubOffset(0);
  }, []);

  const handleStartAction = useCallback(() => {
    if (wfoEnabled) {
      void handleRunWfo();
      return;
    }
    void handleStartTest();
  }, [wfoEnabled, handleRunWfo, handleStartTest]);

  const detachedToggleButtonStyle = {
    padding: "2px 8px",
    borderRadius: "var(--radius-sm)",
    border: "1px solid var(--border-color)",
    background: "var(--bg-secondary)",
    color: "var(--text-secondary)",
    fontSize: "0.72rem",
    fontWeight: 600,
    cursor: "pointer",
  };

  const entryConditionsContent = (
    <StrategyAnalyzerEntryConditionsContent
      effectiveConditionsMarker={effectiveConditionsMarker}
      stableConditionsLiveAnalysis={stableConditionsLiveAnalysis}
      isScrubbingLiveEval={isScrubbingLiveEval}
    />
  );

  const decisionsContent = (
    <StrategyAnalyzerDecisionsContent
      analyzerDecisionEvents={analyzerDecisionEvents}
      selectedMarker={selectedMarker}
      onDecisionSelectMarker={onDecisionSelectMarker}
    />
  );

  /* ── render ────────────────────────────────────────────────────── */
  return (
    <div className="strategy-analyzer" style={{ display: "flex", flexDirection: "column", gap: "0.75rem", height: "100%", padding: "0.75rem" }}>
      <StrategyAnalyzerHeaderControls
        tickers={tickers}
        ticker={ticker}
        onTickerChange={handleTickerChange}
        dateFrom={dateFrom}
        dateTo={dateTo}
        setDateFrom={setDateFrom}
        setDateTo={setDateTo}
        loadBars={loadBars}
        loading={loading}
        barCount={barCount}
        warmupBars={warmupBars}
        onWarmupBarsChange={setWarmupBars}
        isAnalyzerAttachedRun={isAnalyzerAttachedRun}
        analyzerTradeEvalMode={analyzerTradeEvalMode}
        onAnalyzerTradeEvalModeChange={setAnalyzerTradeEvalMode}
        runLoading={runLoading || wfoIsRunning}
        isPlayingRun={isPlayingRun}
        analyzerRunFinished={analyzerRunFinished}
        onPlayRun={onPlayRun}
        onPauseRun={onPauseRun}
        onStepRun={onStepRun}
        onClearAnalyzerRun={handleClearAnalyzerRun}
        analyzerPlaybackProgress={analyzerPlaybackProgress}
        attachedRunState={attachedRunState}
        rankedWfoResults={rankedWfoResults}
        selectedWfoVariantId={selectedWfoVariantId}
        bestWfoVariantId={bestWfoVariantId}
        onSelectWfoVariant={handleSelectWfoVariant}
      />

      {/* ── Error ──────────────────────────────────────────────── */}
      {error && (
        <div className="card" style={{ padding: "0.5rem 1rem", color: "var(--accent-red)", fontSize: "0.85rem" }}>
          {error}
          <button onClick={() => setError(null)} style={{ marginLeft: 8, cursor: "pointer", background: "none", border: "none", color: "var(--text-muted)" }}>
            dismiss
          </button>
        </div>
      )}

      <div
        style={{
          flex: 1,
          minHeight: 0,
          display: "flex",
          gap: "0.75rem",
          flexWrap: "wrap",
          alignItems: "stretch",
        }}
      >
        <div
          style={{
            flex: "1 1 760px",
            minWidth: 0,
            minHeight: 0,
            display: "flex",
            flexDirection: "column",
            gap: "0.75rem",
          }}
        >
          <StrategyAnalyzerChartPanel
            bars={bars}
            ticker={ticker}
            dateFrom={dateFrom}
            dateTo={dateTo}
            loading={loading}
            isAnalyzerAttachedRun={isAnalyzerAttachedRun}
            analyzerDisplayPhase={analyzerDisplayPhase}
            selectedRangeFrom={selectedRangeFrom}
            selectedRangeTo={selectedRangeTo}
            rangeSelectMode={rangeSelectMode}
            onToggleRangeSelectMode={() => setRangeSelectMode((previous) => !previous)}
            chartRef={chartRef}
            chartBars={chartBars}
            analyzerChartMarkers={analyzerChartMarkers}
            onChartMarkerClick={onChartMarkerClick}
            onBarClick={handleAnalyzerBarClick}
            selectedMarker={selectedMarker}
            analyzerChartState={analyzerChartState}
            selectedRangeWindow={selectedRangeWindow}
            onChartStateChange={handleAnalyzerChartStateChange}
            onRangeSelected={handleRangeSelected}
            onSelectionClear={handleClearRange}
            rangeScrubMeta={rangeScrubMeta}
            focusSelectedRangeOffset={focusSelectedRangeOffset}
            moveSelectedRangeByStep={moveSelectedRangeByStep}
          />

          <StrategyAnalyzerRangeActions
            selectedRangeFrom={selectedRangeFrom}
            selectedRangeTo={selectedRangeTo}
            setSelectedRangeFrom={setSelectedRangeFrom}
            setSelectedRangeTo={setSelectedRangeTo}
            onClearRange={handleClearRange}
            onOpenStrategyEditor={() => setShowStrategyEditor(true)}
            onStartTest={handleStartAction}
            onRunWfo={handleRunWfo}
            runLoading={runLoading || wfoIsRunning}
            wfoEnabled={wfoEnabled}
            onWfoEnabledChange={setWfoEnabled}
            wfoGridConfig={wfoGridConfig}
            onWfoGridConfigChange={updateWfoGridConfig}
            wfoEstimatedCombinations={estimatedCombinationCount}
            wfoIsRunning={wfoIsRunning}
            wfoProgressLabel={wfoProgressLabel}
            rankedWfoResults={rankedWfoResults}
            selectedWfoVariantId={selectedWfoVariantId}
            bestWfoVariantId={bestWfoVariantId}
            onSelectWfoVariant={handleSelectWfoVariant}
          />
        </div>

        {isAnalyzerAttachedRun ? (
          <StrategyAnalyzerAttachedPanels
            ticker={ticker}
            analyzerDecisionEventsCount={analyzerDecisionEvents.length}
            hasConditionsPanelData={hasConditionsPanelData}
            conditionsPanelBadge={conditionsPanelBadge}
            detachedToggleButtonStyle={detachedToggleButtonStyle}
            isConditionsDetached={isConditionsDetached}
            isDecisionsDetached={isDecisionsDetached}
            setIsConditionsDetached={setIsConditionsDetached}
            setIsDecisionsDetached={setIsDecisionsDetached}
            entryConditionsContent={entryConditionsContent}
            decisionsContent={decisionsContent}
          />
        ) : null}
      </div>

      {/* ── Unified Strategy Configuration Dialog ────────────── */}
      {showStrategyEditor && (
        <StrategyAnalyzerUnifiedConfigWrapper
          ticker={ticker}
          strategyApiUrl={strategyApiUrl}
          onClose={() => setShowStrategyEditor(false)}
        />
      )}
      {selectedIntradayLevels && (
        <IntradayLevelsDialog
          bar={selectedIntradayLevels.bar}
          payload={selectedIntradayLevels.payload}
          sourcePath={selectedIntradayLevels.sourcePath}
          sourceMarker={selectedIntradayLevels.sourceMarker}
          relatedMarkers={selectedIntradayLevels.relatedMarkers}
          timeframeSeconds={selectedIntradayLevels.timeframeSeconds}
          onClose={closeIntradayLevelsDialog}
        />
      )}
    </div>
  );
}
