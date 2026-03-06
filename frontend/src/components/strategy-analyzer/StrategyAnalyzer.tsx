import { useState, useEffect, useCallback, useRef, useMemo } from "react";
import { parseRunKey, buildRunApiBase } from "../../app/appRunStateStateHelpers";
import IntradayLevelsDialog from "../IntradayLevelsDialog";
import StrategyAnalyzerAttachedPanels from "./StrategyAnalyzerAttachedPanels";
import StrategyAnalyzerChartPanel from "./StrategyAnalyzerChartPanel";
import StrategyAnalyzerDecisionsContent from "./StrategyAnalyzerDecisionsContent";
import StrategyAnalyzerEntryConditionsContent from "./StrategyAnalyzerEntryConditionsContent";
import StrategyAnalyzerPriceHeatmap from "./StrategyAnalyzerPriceHeatmap";
import StrategyAnalyzerUnifiedConfigWrapper from "./StrategyAnalyzerUnifiedConfigWrapper";
import StrategyAnalyzerHeaderControls from "./StrategyAnalyzerHeaderControls";
import StrategyAnalyzerRangeActions from "./StrategyAnalyzerRangeActions";
import { filterMarkersByChartWindow } from "./filterMarkersByChartWindow";
import { extractStrategyConditionsPanelData } from "./StrategyConditionsPanelData";
import {
  clampContextRiskThresholdOverrides,
  resolveContextRiskStrategyFloor,
} from "./strategyAnalyzerContextRiskFloors";
import {
  BOOLEAN_THRESHOLD_OVERRIDE_KEYS,
  SUPPORTED_THRESHOLD_OVERRIDE_KEYS,
  useStrategyAnalyzerThresholdOverrides,
} from "./useStrategyAnalyzerThresholdOverrides";
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
  StrategyAnalyzerContextRiskPresetKey,
  StrategyAnalyzerTradeEvalMode,
  StrategyAnalyzerRunBarLike,
} from "./types";
import type {
  ThresholdOverrideKey,
  ThresholdOverrides,
} from "./useStrategyAnalyzerThresholdOverrides";
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
import { DEFAULT_STRATEGY_ANALYZER_CONTEXT_RISK_PRESET } from "./strategyAnalyzerContextRiskPresets";

const TERMINAL_RUN_PHASES = new Set(["COMPLETED", "END_OF_DAY", "ERROR", "FAILED", "STOPPED"]);
const STRATEGY_ANALYZER_THRESHOLD_KEY_SET = new Set<string>(SUPPORTED_THRESHOLD_OVERRIDE_KEYS);
const STRATEGY_ANALYZER_BOOLEAN_THRESHOLD_KEY_SET = new Set<string>(BOOLEAN_THRESHOLD_OVERRIDE_KEYS);

const waitForStrategyAnalyzerBridgeTick = async (delayMs = 0): Promise<void> =>
  new Promise((resolve) => window.setTimeout(resolve, delayMs));

type StrategyAnalyzerWebMcpBridge = {
  getState: () => Record<string, unknown>;
  openDay: (args?: Record<string, unknown>) => Promise<Record<string, unknown>>;
  startReplay: () => Promise<Record<string, unknown>>;
  playReplay: (options?: Record<string, unknown>) => Promise<Record<string, unknown>>;
  pauseReplay: () => Promise<Record<string, unknown>>;
  stepReplay: (steps?: number) => Promise<Record<string, unknown>>;
  clearReplay: () => Promise<Record<string, unknown>>;
  setThresholdOverride: (
    key: string,
    value: unknown,
  ) => Promise<Record<string, unknown>>;
  bulkSetThresholdOverrides: (
    overrides: Record<string, unknown>,
  ) => Promise<Record<string, unknown>>;
  clearThresholdOverrides: (key?: string) => Promise<Record<string, unknown>>;
};

const setThresholdOverrideValue = (
  target: ThresholdOverrides,
  key: ThresholdOverrideKey,
  value: number | boolean | null,
) => {
  (target as Record<string, number | boolean | null | undefined>)[key] = value;
};

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
  const [includeExtendedHours, setIncludeExtendedHours] = useState(true);
  const [comparableMode, setComparableMode] = useState(false);
  const [coldStartEachDay, setColdStartEachDay] = useState(false);
  const [contextRiskPresetKey, setContextRiskPresetKey] = useState<StrategyAnalyzerContextRiskPresetKey>(
    DEFAULT_STRATEGY_ANALYZER_CONTEXT_RISK_PRESET,
  );

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

  const { bars, loading, barCount, loadBars, loadBarsFor, resetBarsState } = useStrategyAnalyzerBarsLoader({
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
    ticker,
    dateFrom,
    dateTo,
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
  const analyzerProcessedBars = isAnalyzerAttachedRun
    ? Math.max(0, Math.trunc(Number(attachedRunState?.current_bar_index || 0)))
    : 0;
  const analyzerTotalBars = isAnalyzerAttachedRun
    ? Math.max(0, Math.trunc(Number(attachedRunState?.total_bars || 0)))
    : 0;
  const analyzerProgressLooksComplete =
    isAnalyzerAttachedRun &&
    !attachedRunState?.is_running &&
    analyzerTotalBars > 0 &&
    analyzerProcessedBars >= analyzerTotalBars;
  const analyzerRunTerminal =
    isAnalyzerAttachedRun &&
    !attachedRunState?.is_running &&
    (TERMINAL_RUN_PHASES.has(analyzerRunPhase) || analyzerProgressLooksComplete);

  const thresholdPayloadContextData = useMemo(
    () => extractStrategyConditionsPanelData(selectedMarker, latestBarAnalysis),
    [selectedMarker, latestBarAnalysis],
  );

  // ── threshold overrides (interactive sliders when paused) ─────
  const activeRunApiBase = useMemo(
    () => buildRunApiBase(parseRunKey(attachedRunKey)),
    [attachedRunKey],
  );
  const {
    thresholdOverrides,
    isThresholdInteractive,
    hasPendingOverrides,
    updateThresholdOverride,
    replaceThresholdOverrides,
    resetThresholdOverrides,
    buildThresholdPayload,
  } = useStrategyAnalyzerThresholdOverrides({
    isAnalyzerAttachedRun,
    isPlayingRun,
    analyzerRunTerminal,
    activeRunApiBase,
    contextRiskStrategyKey: thresholdPayloadContextData?.selectedStrategy ?? null,
  });

  const { timelineCacheVersion } = useStrategyAnalyzerTimelineCache({
    isAnalyzerAttachedRun,
    rangePlaybackMeta,
    analyzerRunKey,
    attachedRunBars,
    timelineCacheRef,
  });
  const scrubIdentityKey = useMemo(() => {
    if (!isAnalyzerAttachedRun || !rangePlaybackMeta) return null;
    return `${String(analyzerRunKey || "").trim()}|${Number(rangePlaybackMeta.tradeStartTs)}|${Number(
      rangePlaybackMeta.tradeEndTs,
    )}`;
  }, [isAnalyzerAttachedRun, rangePlaybackMeta, analyzerRunKey]);
  const {
    rangeScrubBase,
    rangeScrubMeta,
    focusSelectedRangeOffset,
    moveSelectedRangeByStep,
  } = useStrategyAnalyzerRangeScrub({
    isAnalyzerAttachedRun,
    isPlayingRun,
    scrubIdentityKey,
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
    : analyzerRunTerminal && !TERMINAL_RUN_PHASES.has(analyzerRunPhase)
      ? "COMPLETED"
      : analyzerRunPhase;
  const { analyzerChartMarkers, chartBars } = useStrategyAnalyzerChartData({
    bars,
    attachedRunBars,
    isAnalyzerAttachedRun,
    analyzerRunTerminal,
    selectedRangeWindow,
    rangeScrubMeta,
    analyzerDecisionEvents,
    timelineCacheVersion,
    timelineCacheRef,
  });
  const analyzerDecisionEventsForDisplay = useMemo(
    () => filterMarkersByChartWindow(analyzerDecisionEvents, selectedRangeWindow),
    [analyzerDecisionEvents, selectedRangeWindow],
  );
  const { runLoading, handleStartTest, handleClearAnalyzerRun } = useStrategyAnalyzerRunOrchestration({
    selectedRangeFrom,
    selectedRangeTo,
    ticker,
    strategyApiUrl,
    analyzerTradeEvalMode,
    includeExtendedHours,
    comparableMode,
    coldStartEachDay,
    contextRiskPresetKey,
    rangePlaybackMeta,
    onStartRun,
    onSwitchToBacktest,
    onClearRun,
    isAnalyzerAttachedRun,
    setError,
    setRangeScrubOffset,
    setAnalyzerRunKey,
    thresholdOverridesPayload: hasPendingOverrides ? buildThresholdPayload(thresholdOverrides) : undefined,
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
    includeExtendedHours,
    comparableMode,
    coldStartEachDay,
    contextRiskPresetKey,
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
    scrubMarkers: analyzerChartMarkers,
    selectedMarker,
    latestBarAnalysis,
    onEvaluateIntrabarSlice,
  });
  const effectiveThresholdContextData = useMemo(
    () =>
      extractStrategyConditionsPanelData(
        effectiveConditionsMarker,
        stableConditionsLiveAnalysis,
      ),
    [effectiveConditionsMarker, stableConditionsLiveAnalysis],
  );
  const effectiveThresholdStrategyFloor = useMemo(
    () =>
      resolveContextRiskStrategyFloor(
        effectiveThresholdContextData?.selectedStrategy ?? null,
      ),
    [effectiveThresholdContextData],
  );
  const thresholdStatusSelectedStrategy =
    effectiveThresholdContextData?.selectedStrategy ??
    thresholdPayloadContextData?.selectedStrategy ??
    null;
  const thresholdStatusStrategyFloor =
    effectiveThresholdStrategyFloor ??
    resolveContextRiskStrategyFloor(thresholdPayloadContextData?.selectedStrategy ?? null);
  const effectiveThresholdOverridesForDisplay = useMemo(
    () =>
      clampContextRiskThresholdOverrides(
        thresholdOverrides,
        thresholdStatusSelectedStrategy,
      ),
    [thresholdOverrides, thresholdStatusSelectedStrategy],
  );
  const effectiveThresholdPayloadForDisplay = useMemo(
    () => buildThresholdPayload(effectiveThresholdOverridesForDisplay),
    [buildThresholdPayload, effectiveThresholdOverridesForDisplay],
  );
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

  useEffect(() => {
    if (!comparableMode) return;
    setColdStartEachDay(true);
  }, [comparableMode]);

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
    setContextRiskPresetKey,
    setComparableMode,
    setAnalyzerTradeEvalMode,
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

  const currentBarForBridge = useMemo(() => {
    if (rangeScrubMeta?.targetBar && typeof rangeScrubMeta.targetBar === "object") {
      return rangeScrubMeta.targetBar;
    }
    if (isAnalyzerAttachedRun && attachedRunBars.length > 0) {
      return attachedRunBars[attachedRunBars.length - 1];
    }
    if (chartBars.length > 0) {
      return chartBars[chartBars.length - 1];
    }
    if (bars.length > 0) {
      return bars[bars.length - 1];
    }
    return null;
  }, [rangeScrubMeta, isAnalyzerAttachedRun, attachedRunBars, chartBars, bars]);

  const strategyAnalyzerBridgeState = useMemo<Record<string, unknown>>(
    () => ({
      active: true,
      ticker,
      date_from: dateFrom || null,
      date_to: dateTo || null,
      loading,
      error,
      bar_count: barCount,
      preview_bars: Array.isArray(bars) ? bars : [],
      run_bars: isAnalyzerAttachedRun && Array.isArray(attachedRunBars) ? attachedRunBars : [],
      chart_bars: Array.isArray(chartBars) ? chartBars : [],
      current_bar: currentBarForBridge,
      selected_range: {
        from: selectedRangeFrom,
        to: selectedRangeTo,
      },
      chart_state:
        analyzerChartState &&
        Number.isFinite(Number(analyzerChartState.from)) &&
        Number.isFinite(Number(analyzerChartState.to))
          ? {
              from: Number(analyzerChartState.from),
              to: Number(analyzerChartState.to),
            }
          : null,
      attached_run: isAnalyzerAttachedRun,
      run_key:
        (isAnalyzerAttachedRun
          ? String(attachedRunKey || analyzerRunKey || "").trim()
          : String(analyzerRunKey || "").trim()) || null,
      run_phase: analyzerDisplayPhase || null,
      is_playing: isPlayingRun,
      comparable_mode: comparableMode,
      cold_start_each_day: comparableMode ? true : coldStartEachDay,
      include_extended_hours: includeExtendedHours,
      trade_eval_mode: analyzerTradeEvalMode,
      context_risk_preset: contextRiskPresetKey,
      decision_events: Array.isArray(analyzerDecisionEvents) ? analyzerDecisionEvents : [],
      visible_decision_events: Array.isArray(analyzerDecisionEventsForDisplay)
        ? analyzerDecisionEventsForDisplay
        : [],
      selected_marker:
        (effectiveConditionsMarker ?? selectedMarker) &&
        typeof (effectiveConditionsMarker ?? selectedMarker) === "object"
          ? (effectiveConditionsMarker ?? selectedMarker)
          : null,
      latest_bar_analysis:
        stableConditionsLiveAnalysis && typeof stableConditionsLiveAnalysis === "object"
          ? stableConditionsLiveAnalysis
          : null,
      scrub: rangeScrubMeta
        ? {
            current_offset: rangeScrubMeta.clampedOffset,
            min_offset: 0,
            max_offset: rangeScrubMeta.progressedMaxOffset,
            target_time: rangeScrubMeta.targetTime ?? null,
            target_local: rangeScrubMeta.targetLocal ?? null,
            target_bar_index:
              rangeScrubMeta.targetBar?.bar_index != null
                ? Number(rangeScrubMeta.targetBar.bar_index)
                : null,
            progress_pct: rangeScrubBase?.progressPct ?? null,
            step_bars: rangeScrubBase?.sliderStepBars ?? null,
          }
        : null,
      has_conditions_panel_data: hasConditionsPanelData,
      conditions_panel_badge: conditionsPanelBadge,
      thresholds: {
        overrides: thresholdOverrides,
        effective_overrides: effectiveThresholdOverridesForDisplay,
        payload: buildThresholdPayload(thresholdOverrides),
        effective_payload: effectiveThresholdPayloadForDisplay,
        has_pending_overrides: hasPendingOverrides,
        is_interactive: isThresholdInteractive,
        selected_strategy: thresholdStatusSelectedStrategy,
        context_risk_strategy_floor: thresholdStatusStrategyFloor,
        supported_keys: [...SUPPORTED_THRESHOLD_OVERRIDE_KEYS],
        boolean_keys: [...BOOLEAN_THRESHOLD_OVERRIDE_KEYS],
      },
      snapshot_updated_at_utc: new Date().toISOString(),
    }),
    [
      ticker,
      dateFrom,
      dateTo,
      loading,
      error,
      barCount,
      bars,
      isAnalyzerAttachedRun,
      attachedRunBars,
      chartBars,
      currentBarForBridge,
      selectedRangeFrom,
      selectedRangeTo,
      analyzerChartState,
      attachedRunKey,
      analyzerRunKey,
      analyzerDisplayPhase,
      isPlayingRun,
      comparableMode,
      coldStartEachDay,
      includeExtendedHours,
      analyzerTradeEvalMode,
      contextRiskPresetKey,
      analyzerDecisionEvents,
      analyzerDecisionEventsForDisplay,
      effectiveConditionsMarker,
      selectedMarker,
      stableConditionsLiveAnalysis,
      rangeScrubMeta,
      rangeScrubBase,
      hasConditionsPanelData,
      conditionsPanelBadge,
      thresholdOverrides,
      effectiveThresholdOverridesForDisplay,
      hasPendingOverrides,
      isThresholdInteractive,
      buildThresholdPayload,
      effectiveThresholdPayloadForDisplay,
      thresholdStatusSelectedStrategy,
      thresholdStatusStrategyFloor,
    ],
  );

  const setBridgeThresholdOverride = useCallback(
    async (rawKey: string, rawValue: unknown) => {
      const key = String(rawKey || "").trim() as ThresholdOverrideKey;
      if (!STRATEGY_ANALYZER_THRESHOLD_KEY_SET.has(key)) {
        return {
          ok: false,
          error: "Unknown threshold override key.",
          key: rawKey,
          supported_keys: [...SUPPORTED_THRESHOLD_OVERRIDE_KEYS],
        };
      }

      let normalizedValue: number | boolean | null = null;
      if (rawValue != null) {
        if (STRATEGY_ANALYZER_BOOLEAN_THRESHOLD_KEY_SET.has(key)) {
          normalizedValue = Boolean(rawValue);
        } else {
          const numericValue = Number(rawValue);
          if (!Number.isFinite(numericValue)) {
            return {
              ok: false,
              error: "Threshold override value must be numeric.",
              key,
              value: rawValue,
            };
          }
          normalizedValue = numericValue;
        }
      }

      const nextOverrides: ThresholdOverrides = { ...thresholdOverrides };
      if (normalizedValue == null) {
        delete nextOverrides[key];
      } else {
        setThresholdOverrideValue(nextOverrides, key, normalizedValue);
      }
      replaceThresholdOverrides(nextOverrides);
      await waitForStrategyAnalyzerBridgeTick();

      return {
        ok: true,
        key,
        value: normalizedValue,
        overrides: nextOverrides,
        effective_overrides: clampContextRiskThresholdOverrides(
          nextOverrides,
          thresholdStatusSelectedStrategy,
        ),
        payload: buildThresholdPayload(nextOverrides),
        effective_payload: buildThresholdPayload(
          clampContextRiskThresholdOverrides(
            nextOverrides,
            thresholdStatusSelectedStrategy,
          ),
        ),
      };
    },
    [
      thresholdOverrides,
      replaceThresholdOverrides,
      buildThresholdPayload,
      thresholdStatusSelectedStrategy,
    ],
  );

  const bulkSetBridgeThresholdOverrides = useCallback(
    async (overrides: Record<string, unknown>) => {
      const nextOverrides: ThresholdOverrides = { ...thresholdOverrides };
      const ignoredKeys: string[] = [];

      for (const [rawKey, rawValue] of Object.entries(overrides || {})) {
        const key = String(rawKey || "").trim() as ThresholdOverrideKey;
        if (!STRATEGY_ANALYZER_THRESHOLD_KEY_SET.has(key)) {
          ignoredKeys.push(rawKey);
          continue;
        }
        if (rawValue == null) {
          delete nextOverrides[key];
          continue;
        }
        if (STRATEGY_ANALYZER_BOOLEAN_THRESHOLD_KEY_SET.has(key)) {
          setThresholdOverrideValue(nextOverrides, key, Boolean(rawValue));
          continue;
        }
        const numericValue = Number(rawValue);
        if (!Number.isFinite(numericValue)) {
          ignoredKeys.push(rawKey);
          continue;
        }
        setThresholdOverrideValue(nextOverrides, key, numericValue);
      }

      replaceThresholdOverrides(nextOverrides);
      await waitForStrategyAnalyzerBridgeTick();

      return {
        ok: true,
        overrides: nextOverrides,
        effective_overrides: clampContextRiskThresholdOverrides(
          nextOverrides,
          thresholdStatusSelectedStrategy,
        ),
        payload: buildThresholdPayload(nextOverrides),
        effective_payload: buildThresholdPayload(
          clampContextRiskThresholdOverrides(
            nextOverrides,
            thresholdStatusSelectedStrategy,
          ),
        ),
        ignored_keys: ignoredKeys,
      };
    },
    [thresholdOverrides, replaceThresholdOverrides, buildThresholdPayload, thresholdStatusSelectedStrategy],
  );

  const clearBridgeThresholdOverrides = useCallback(
    async (rawKey?: string) => {
      const key = typeof rawKey === "string" ? rawKey.trim() : "";
      if (!key) {
        resetThresholdOverrides();
        await waitForStrategyAnalyzerBridgeTick();
        return {
          ok: true,
          cleared_all: true,
          overrides: {},
          effective_overrides: {},
          payload: {},
          effective_payload: {},
        };
      }
      if (!STRATEGY_ANALYZER_THRESHOLD_KEY_SET.has(key)) {
        return {
          ok: false,
          error: "Unknown threshold override key.",
          key,
          supported_keys: [...SUPPORTED_THRESHOLD_OVERRIDE_KEYS],
        };
      }

      const nextOverrides: ThresholdOverrides = { ...thresholdOverrides };
      delete nextOverrides[key as ThresholdOverrideKey];
      replaceThresholdOverrides(nextOverrides);
      await waitForStrategyAnalyzerBridgeTick();

      return {
        ok: true,
        cleared_all: false,
        key,
        overrides: nextOverrides,
        effective_overrides: clampContextRiskThresholdOverrides(
          nextOverrides,
          thresholdStatusSelectedStrategy,
        ),
        payload: buildThresholdPayload(nextOverrides),
        effective_payload: buildThresholdPayload(
          clampContextRiskThresholdOverrides(
            nextOverrides,
            thresholdStatusSelectedStrategy,
          ),
        ),
      };
    },
    [
      thresholdOverrides,
      resetThresholdOverrides,
      replaceThresholdOverrides,
      buildThresholdPayload,
      thresholdStatusSelectedStrategy,
    ],
  );

  const openDayForBridge = useCallback(
    async (args?: Record<string, unknown>) => {
      const targetTicker = String(args?.ticker || args?.symbol || ticker || "MU")
        .trim()
        .toUpperCase();
      const targetDate = String(args?.iso_date || args?.date || "").trim();
      if (!/^\d{4}-\d{2}-\d{2}$/.test(targetDate)) {
        return {
          ok: false,
          error: "Invalid or missing iso_date. Expected YYYY-MM-DD.",
          iso_date: targetDate || null,
        };
      }

      const rawWarmupBars = Number(args?.warmup_bars);
      if (Number.isFinite(rawWarmupBars) && rawWarmupBars >= 0) {
        setWarmupBars(Math.trunc(rawWarmupBars));
      }

      if (typeof args?.include_extended_hours === "boolean") {
        setIncludeExtendedHours(args.include_extended_hours);
      }
      if (typeof args?.comparable_mode === "boolean") {
        setComparableMode(args.comparable_mode);
      }
      if (typeof args?.cold_start_each_day === "boolean") {
        setColdStartEachDay(args.cold_start_each_day);
      }
      if (
        args?.trade_eval_mode === "standard" ||
        args?.trade_eval_mode === "intrabar_1s" ||
        args?.trade_eval_mode === "intrabar_5s"
      ) {
        setAnalyzerTradeEvalMode(args.trade_eval_mode);
      }
      if (typeof args?.context_risk_preset === "string" && args.context_risk_preset.trim()) {
        setContextRiskPresetKey(args.context_risk_preset.trim() as StrategyAnalyzerContextRiskPresetKey);
      }

      setError(null);
      setRangeSelectMode(false);
      setSelectedRangeFrom(null);
      setSelectedRangeTo(null);
      setRangeScrubOffset(0);
      setAnalyzerRunKey(null);
      if (targetTicker !== ticker) {
        setTicker(targetTicker);
      }
      setDateFrom(targetDate);
      setDateTo(targetDate);

      await loadBarsFor({
        ticker: targetTicker,
        dateFrom: targetDate,
        dateTo: targetDate,
      });

      setSelectedRangeFrom(`${targetDate}T00:00`);
      setSelectedRangeTo(`${targetDate}T23:59`);
      setRangeScrubOffset(0);
      await waitForStrategyAnalyzerBridgeTick();

      return {
        ok: true,
        ticker: targetTicker,
        iso_date: targetDate,
      };
    },
    [ticker, loadBarsFor],
  );

  const startReplayForBridge = useCallback(async () => {
    await handleStartTest();
    await waitForStrategyAnalyzerBridgeTick(40);
    return { ok: true };
  }, [handleStartTest]);

  // Wrap play/step requests so replay controls and bridge calls share identical overrides behavior.
  const handlePlayWithOverrides: typeof onPlayRun = useCallback(
    async (options?: any) => {
      const merged: any = hasPendingOverrides
        ? { ...options, threshold_overrides: buildThresholdPayload(thresholdOverrides) }
        : { ...options };
      merged.keep_in_memory_after_completion = true;
      if (
        rangeScrubMeta &&
        rangeScrubMeta.clampedOffset < rangeScrubMeta.progressedMaxOffset &&
        rangeScrubMeta.targetBar?.bar_index != null
      ) {
        merged.seek_to_bar_index = rangeScrubMeta.targetBar.bar_index;
      }
      return onPlayRun?.(merged);
    },
    [hasPendingOverrides, onPlayRun, thresholdOverrides, rangeScrubMeta, buildThresholdPayload],
  );

  const handleStepWithOverrides: typeof onStepRun = useCallback(
    async (options?: any) => {
      const merged: any = hasPendingOverrides
        ? { ...options, threshold_overrides: buildThresholdPayload(thresholdOverrides) }
        : { ...options };
      if (
        rangeScrubMeta &&
        rangeScrubMeta.clampedOffset < rangeScrubMeta.progressedMaxOffset &&
        rangeScrubMeta.targetBar?.bar_index != null
      ) {
        merged.seek_to_bar_index = rangeScrubMeta.targetBar.bar_index;
      }
      return onStepRun?.(merged);
    },
    [hasPendingOverrides, onStepRun, thresholdOverrides, rangeScrubMeta, buildThresholdPayload],
  );

  const playReplayForBridge = useCallback(
    async (options?: Record<string, unknown>) => {
      await handlePlayWithOverrides(options);
      await waitForStrategyAnalyzerBridgeTick(40);
      return { ok: true };
    },
    [handlePlayWithOverrides],
  );

  const pauseReplayForBridge = useCallback(async () => {
    await onPauseRun?.();
    await waitForStrategyAnalyzerBridgeTick();
    return { ok: true };
  }, [onPauseRun]);

  const stepReplayForBridge = useCallback(
    async (steps = 1) => {
      const boundedSteps = Math.max(1, Math.min(500, Math.trunc(Number(steps) || 1)));
      for (let idx = 0; idx < boundedSteps; idx += 1) {
        await handleStepWithOverrides();
      }
      await waitForStrategyAnalyzerBridgeTick();
      return { ok: true, steps: boundedSteps };
    },
    [handleStepWithOverrides],
  );

  const clearReplayForBridge = useCallback(async () => {
    await handleClearAnalyzerRun();
    await waitForStrategyAnalyzerBridgeTick();
    return { ok: true };
  }, [handleClearAnalyzerRun]);

  const strategyAnalyzerWebMcpBridge = useMemo<StrategyAnalyzerWebMcpBridge>(
    () => ({
      getState: () => strategyAnalyzerBridgeState,
      openDay: openDayForBridge,
      startReplay: startReplayForBridge,
      playReplay: playReplayForBridge,
      pauseReplay: pauseReplayForBridge,
      stepReplay: stepReplayForBridge,
      clearReplay: clearReplayForBridge,
      setThresholdOverride: setBridgeThresholdOverride,
      bulkSetThresholdOverrides: bulkSetBridgeThresholdOverrides,
      clearThresholdOverrides: clearBridgeThresholdOverrides,
    }),
    [
      strategyAnalyzerBridgeState,
      openDayForBridge,
      startReplayForBridge,
      playReplayForBridge,
      pauseReplayForBridge,
      stepReplayForBridge,
      clearReplayForBridge,
      setBridgeThresholdOverride,
      bulkSetBridgeThresholdOverrides,
      clearBridgeThresholdOverrides,
    ],
  );

  useEffect(() => {
    if (typeof window === "undefined") return;
    const runtimeWindow = window as Window & {
      __backtestStrategyAnalyzerWebMcpBridge?: StrategyAnalyzerWebMcpBridge | null;
    };
    runtimeWindow.__backtestStrategyAnalyzerWebMcpBridge = strategyAnalyzerWebMcpBridge;
    return () => {
      if (runtimeWindow.__backtestStrategyAnalyzerWebMcpBridge === strategyAnalyzerWebMcpBridge) {
        runtimeWindow.__backtestStrategyAnalyzerWebMcpBridge = null;
      }
    };
  }, [strategyAnalyzerWebMcpBridge]);

  const handleStartAction = useCallback(() => {
    if (wfoEnabled) {
      void handleRunWfo();
      return;
    }
    void handleStartTest();
  }, [wfoEnabled, handleRunWfo, handleStartTest]);

  const entryConditionsContent = (
    <StrategyAnalyzerEntryConditionsContent
      effectiveConditionsMarker={effectiveConditionsMarker}
      stableConditionsLiveAnalysis={stableConditionsLiveAnalysis}
      isScrubbingLiveEval={isScrubbingLiveEval}
      isThresholdInteractive={isThresholdInteractive}
      thresholdOverrides={effectiveThresholdOverridesForDisplay}
      onThresholdOverrideChange={updateThresholdOverride}
      hasPendingOverrides={hasPendingOverrides}
    />
  );

  const decisionsContent = (
    <StrategyAnalyzerDecisionsContent
      analyzerDecisionEvents={analyzerDecisionEventsForDisplay}
      selectedMarker={selectedMarker}
      onDecisionSelectMarker={onDecisionSelectMarker}
    />
  );

  /* ── render ────────────────────────────────────────────────────── */
  return (
    <div className="strategy-analyzer sa-shell">
      {/* ── Error ──────────────────────────────────────────────── */}
      {error && (
        <div className="card sa-alert-card">
          {error}
          <button
            type="button"
            className="sa-alert-dismiss"
            onClick={() => setError(null)}
          >
            dismiss
          </button>
        </div>
      )}

      <div className={`sa-workspace ${isAnalyzerAttachedRun ? "is-attached" : ""}`}>
        <div className="sa-chart-column">
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
        </div>

        <aside className="sa-utility-rail">
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
            includeExtendedHours={includeExtendedHours}
            onIncludeExtendedHoursChange={setIncludeExtendedHours}
            comparableMode={comparableMode}
            onComparableModeChange={setComparableMode}
            coldStartEachDay={coldStartEachDay}
            onColdStartEachDayChange={setColdStartEachDay}
            contextRiskPresetKey={contextRiskPresetKey}
            onContextRiskPresetChange={setContextRiskPresetKey}
            isAnalyzerAttachedRun={isAnalyzerAttachedRun}
            analyzerTradeEvalMode={analyzerTradeEvalMode}
            onAnalyzerTradeEvalModeChange={setAnalyzerTradeEvalMode}
            runLoading={runLoading || wfoIsRunning}
            isPlayingRun={isPlayingRun}
            analyzerRunTerminal={analyzerRunTerminal}
            onPlayRun={handlePlayWithOverrides}
            onPauseRun={onPauseRun}
            onStepRun={handleStepWithOverrides}
            onClearAnalyzerRun={handleClearAnalyzerRun}
            analyzerPlaybackProgress={analyzerPlaybackProgress}
            attachedRunState={attachedRunState}
            layout="rail"
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

          {isAnalyzerAttachedRun ? (
            <StrategyAnalyzerAttachedPanels
              ticker={ticker}
              analyzerDecisionEventsCount={analyzerDecisionEventsForDisplay.length}
              hasConditionsPanelData={hasConditionsPanelData}
              conditionsPanelBadge={conditionsPanelBadge}
              isConditionsDetached={isConditionsDetached}
              isDecisionsDetached={isDecisionsDetached}
              setIsConditionsDetached={setIsConditionsDetached}
              setIsDecisionsDetached={setIsDecisionsDetached}
              entryConditionsContent={entryConditionsContent}
              decisionsContent={decisionsContent}
            />
          ) : null}

          {bars.length > 0 ? (
            <StrategyAnalyzerPriceHeatmap ticker={ticker} dateFrom={dateFrom} dateTo={dateTo} />
          ) : null}
        </aside>
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
