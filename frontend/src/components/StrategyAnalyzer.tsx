import { useState, useEffect, useCallback, useRef, useMemo } from "react";
import CandlestickChart from "./CandlestickChart";
import DecisionPanel from "./DecisionPanel";
import IntradayLevelsDialog from "./IntradayLevelsDialog";
import ChartRangeSelector from "./strategy-analyzer/ChartRangeSelector";
import StrategyEditorModal from "./strategy-analyzer/StrategyEditorModal";
import StrategyConditionsPanel from "./strategy-analyzer/StrategyConditionsPanel";
import ExternalWindowPortal from "./ExternalWindowPortal";
import { toUnixSeconds, defaultStrategyApiUrl } from "../utils";

/* ── bar conversion (mirrors App.tsx toChartBar) ─────────────────── */
const toChartBar = (bar: any) => {
  if (!bar || typeof bar !== "object") return null;
  const time = toUnixSeconds(bar.timestamp ?? bar.time);
  const open = Number(bar.open);
  const high = Number(bar.high);
  const low = Number(bar.low);
  const close = Number(bar.close);
  const volume = Number(bar.volume);
  if (!Number.isFinite(time)) return null;
  if (
    !Number.isFinite(open) ||
    !Number.isFinite(high) ||
    !Number.isFinite(low) ||
    !Number.isFinite(close)
  )
    return null;
  return { time, open, high, low, close, volume: Number.isFinite(volume) ? volume : 0 };
};

const dateTimeLocalToUtcIso = (value: string | null | undefined): string | null => {
  const raw = String(value || "").trim();
  if (!raw) return null;
  const ms = Date.parse(raw);
  if (!Number.isFinite(ms)) return null;
  return new Date(ms).toISOString();
};

const unixSecondsToDateTimeLocal = (ts: number): string => {
  const d = new Date(ts * 1000);
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  const hh = String(d.getHours()).padStart(2, "0");
  const min = String(d.getMinutes()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}T${hh}:${min}`;
};

const unixSecondsToLabel = (ts: number, includeSeconds = false): string => {
  const d = new Date(ts * 1000);
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  const hh = String(d.getHours()).padStart(2, "0");
  const min = String(d.getMinutes()).padStart(2, "0");
  const ss = String(d.getSeconds()).padStart(2, "0");
  return includeSeconds ? `${yyyy}-${mm}-${dd}T${hh}:${min}:${ss}` : `${yyyy}-${mm}-${dd}T${hh}:${min}`;
};

const isObjectRecord = (value: any) =>
  Boolean(value) && typeof value === "object" && !Array.isArray(value);

const pickIntradayLevelsPayload = (sources: Array<{ payload: any; sourcePath: string } | null>) => {
  if (!Array.isArray(sources)) return { payload: null, sourcePath: null };
  for (const source of sources) {
    if (!source || !isObjectRecord(source.payload)) continue;
    const sourcePath = String(source.sourcePath || "").trim();
    return { payload: source.payload, sourcePath: sourcePath || null };
  }
  return { payload: null, sourcePath: null };
};

const extractIntradayLevelsFromAnalysisObject = (analysis: any, sourcePrefix: string) => {
  if (!isObjectRecord(analysis)) return { payload: null, sourcePath: null };
  return pickIntradayLevelsPayload([
    { sourcePath: `${sourcePrefix}.intraday_levels`, payload: analysis.intraday_levels },
    {
      sourcePath: `${sourcePrefix}.metadata.intraday_levels`,
      payload: analysis.metadata?.intraday_levels,
    },
    {
      sourcePath: `${sourcePrefix}.indicators.intraday_levels`,
      payload: analysis.indicators?.intraday_levels,
    },
    {
      sourcePath: `${sourcePrefix}.signal_metadata.intraday_levels`,
      payload: analysis.signal_metadata?.intraday_levels,
    },
    {
      sourcePath: `${sourcePrefix}.signal.intraday_levels`,
      payload: analysis.signal?.intraday_levels,
    },
    {
      sourcePath: `${sourcePrefix}.signal.metadata.intraday_levels`,
      payload: analysis.signal?.metadata?.intraday_levels,
    },
  ]);
};

const extractIntradayLevelsFromBarPayload = (bar: any) => {
  if (!isObjectRecord(bar)) return { payload: null, sourcePath: null };
  const barAnalysis = extractIntradayLevelsFromAnalysisObject(bar.analysis, "bar.analysis");
  const strategyAnalysis = extractIntradayLevelsFromAnalysisObject(
    bar.strategy_analysis,
    "bar.strategy_analysis"
  );
  return pickIntradayLevelsPayload([
    { sourcePath: "bar.intraday_levels", payload: bar.intraday_levels },
    barAnalysis,
    strategyAnalysis,
  ]);
};

const extractIntradayLevelsFromMarkerPayload = (marker: any) => {
  if (!isObjectRecord(marker)) return { payload: null, sourcePath: null };
  const details = isObjectRecord(marker.details) ? marker.details : {};
  const detailMetadata = isObjectRecord(details.metadata) ? details.metadata : {};
  return pickIntradayLevelsPayload([
    { sourcePath: "marker.details.intraday_levels", payload: details.intraday_levels },
    {
      sourcePath: "marker.details.metadata.intraday_levels",
      payload: details.metadata?.intraday_levels,
    },
    {
      sourcePath: "marker.details.indicators.intraday_levels",
      payload: details.indicators?.intraday_levels,
    },
    {
      sourcePath: "marker.details.signal_metadata.intraday_levels",
      payload: details.signal_metadata?.intraday_levels,
    },
    { sourcePath: "marker.metadata.intraday_levels", payload: detailMetadata.intraday_levels },
    { sourcePath: "marker.intraday_levels", payload: marker.intraday_levels },
  ]);
};

const resolveMarkersInBarWindow = (allMarkers: any[], barTime: number, windowSeconds = 60) => {
  if (!Array.isArray(allMarkers) || !Number.isFinite(barTime)) return [];
  const startTime = Math.floor(barTime);
  const endTime = startTime + Math.max(1, Math.trunc(windowSeconds));
  return allMarkers
    .map((marker) => {
      const markerTime = toUnixSeconds(marker?.time ?? marker?.timestamp);
      return Number.isFinite(markerTime) ? { marker, markerTime } : null;
    })
    .filter(Boolean)
    .filter((row: any) => row.markerTime >= startTime && row.markerTime < endTime)
    .sort((left: any, right: any) => left.markerTime - right.markerTime)
    .map((row: any) => row.marker);
};

const resolveNearestMarkerWithIntradayLevels = (allMarkers: any[], barTime: number) => {
  if (!Array.isArray(allMarkers) || !Number.isFinite(barTime)) return null;
  let nearest: any = null;
  allMarkers.forEach((marker) => {
    const markerTime = toUnixSeconds(marker?.time ?? marker?.timestamp);
    if (!Number.isFinite(markerTime)) return;
    const markerLevels = extractIntradayLevelsFromMarkerPayload(marker);
    if (!markerLevels.payload) return;
    const diff = Math.abs(markerTime - barTime);
    if (!nearest || diff < nearest.diff) {
      nearest = { marker, levels: markerLevels, diff, markerTime };
      return;
    }
    if (diff === nearest.diff) {
      const nearestIsFuture = nearest.markerTime > barTime;
      const currentIsPastOrNow = markerTime <= barTime;
      if (nearestIsFuture && currentIsPastOrNow) {
        nearest = { marker, levels: markerLevels, diff, markerTime };
      }
    }
  });
  return nearest;
};

/* ── types ───────────────────────────────────────────────────────── */
interface StrategyAnalyzerProps {
  selectedTicker: string | null;
  onTickerChange: (ticker: string) => void;
  strategyApiUrl: string;
  onStartRun?: (config: any) => Promise<any>;
  onPlayRun?: (options?: { trade_eval_mode?: string }) => Promise<any> | void;
  onPauseRun?: () => Promise<any> | void;
  onStepRun?: (options?: { trade_eval_mode?: string }) => Promise<any> | void;
  onEvaluateIntrabarSlice?: (ts: number) => Promise<any>;
  onClearRun?: () => Promise<any> | void;
  isPlayingRun?: boolean;
  attachedRunKey?: string | null;
  attachedRunState?: any;
  attachedRunBars?: any[];
  decisionEvents?: any[];
  selectedMarker?: any;
  latestBarAnalysis?: any;
  onDecisionSelectMarker?: (marker: any) => void;
  onChartMarkerClick?: (markerOrId: any) => void;
  onSwitchToBacktest?: () => void;
}

interface AvailableTicker {
  ticker: string;
  start_date: string;
  end_date: string;
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
}: StrategyAnalyzerProps) {
  // available data
  const [tickers, setTickers] = useState<AvailableTicker[]>([]);
  const [loadingTickers, setLoadingTickers] = useState(false);

  // chart load
  const [ticker, setTicker] = useState(selectedTicker || "MU");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [bars, setBars] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [barCount, setBarCount] = useState(0);
  const [warmupBars, setWarmupBars] = useState(240);

  // range selection
  const [rangeSelectMode, setRangeSelectMode] = useState(false);
  const [selectedRangeFrom, setSelectedRangeFrom] = useState<string | null>(null);
  const [selectedRangeTo, setSelectedRangeTo] = useState<string | null>(null);
  const chartRef = useRef<any>(null);
  const [analyzerChartState, setAnalyzerChartState] = useState<{ from: number; to: number } | null>(null);
  const [rangeScrubOffset, setRangeScrubOffset] = useState(0);
  const [analyzerTradeEvalMode, setAnalyzerTradeEvalMode] = useState<"standard" | "intrabar_1s" | "intrabar_5s">("intrabar_5s");
  const [isScrubbingLiveEval, setIsScrubbingLiveEval] = useState(false);
  const [scrubLiveAnalysis, setScrubLiveAnalysis] = useState<any>(null);
  const [selectedIntradayLevels, setSelectedIntradayLevels] = useState<any>(null);
  const scrubEvalSeqRef = useRef(0);
  const lastStableScrubAnalysisRef = useRef<any>(null);

  // ── incremental caching refs for performance ─────────────────────
  // These refs hold pre-computed data structures that are incrementally
  // updated when new bars arrive, avoiding O(n) recomputation each time.
  const timelineCacheRef = useRef<{
    processedRunBarCount: number;
    runBarsByTime: Map<number, any>;
    progressedTradeBars: any[];
    timelinePoints: any[];
    observedCheckpointCounts: number[];
    warmupDone: number;
    tradeDone: number;
    // Track the range boundaries used to build this cache
    startTime: number | null;
    endTime: number | null;
    rangeKey: string | null; // composite key to detect range changes
  }>({
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
  const [runLoading, setRunLoading] = useState(false);
  const [analyzerRunKey, setAnalyzerRunKey] = useState<string | null>(null);

  const isAnalyzerAttachedRun = useMemo(
    () =>
      Boolean(
        analyzerRunKey &&
          attachedRunKey &&
          String(analyzerRunKey).trim() === String(attachedRunKey).trim()
      ),
    [analyzerRunKey, attachedRunKey]
  );
  const analyzerDecisionEvents = isAnalyzerAttachedRun ? decisionEvents : [];
  const analyzerRunPhase = isAnalyzerAttachedRun ? String(attachedRunState?.phase || "").trim() : "";
  const analyzerRunFinished = isAnalyzerAttachedRun && !attachedRunState?.is_running && analyzerRunPhase === "COMPLETED";
  const rangePlaybackMeta = useMemo(() => {
    const rawFromSec = Date.parse(String(selectedRangeFrom || "")) / 1000;
    const rawToSec = Date.parse(String(selectedRangeTo || "")) / 1000;
    if (!Number.isFinite(rawFromSec) || !Number.isFinite(rawToSec)) return null;

    const previewBars = Array.isArray(bars) ? bars : [];
    const rangeMin = Math.min(rawFromSec, rawToSec);
    const rangeMax = Math.max(rawFromSec, rawToSec);

    let tradeStartTs = rangeMin;
    let tradeEndTs = rangeMax;
    let tradeStartIdx: number | null = null;
    let tradeEndIdx: number | null = null;

    if (previewBars.length > 0) {
      const firstIdx = previewBars.findIndex((bar: any) => {
        const t = Number(bar?.time);
        return Number.isFinite(t) && t >= rangeMin - 1;
      });
      const lastIdx = [...previewBars]
        .map((bar: any, idx: number) => ({ idx, t: Number(bar?.time) }))
        .reverse()
        .find((row) => Number.isFinite(row.t) && row.t <= rangeMax + 1)?.idx;

      if (firstIdx >= 0 && typeof lastIdx === "number" && lastIdx >= firstIdx) {
        const firstTs = Number(previewBars[firstIdx]?.time);
        const lastTs = Number(previewBars[lastIdx]?.time);
        if (Number.isFinite(firstTs) && Number.isFinite(lastTs)) {
          tradeStartTs = firstTs;
          tradeEndTs = lastTs;
          tradeStartIdx = firstIdx;
          tradeEndIdx = lastIdx;
        }
      }
    }

    let warmupStartTs = tradeStartTs;
    let warmupStartIdx: number | null = tradeStartIdx;
    if (
      previewBars.length > 0 &&
      typeof tradeStartIdx === "number" &&
      Number.isFinite(tradeStartIdx) &&
      warmupBars > 0
    ) {
      const idx = Math.max(0, tradeStartIdx - Math.trunc(Math.max(0, warmupBars)));
      const ts = Number(previewBars[idx]?.time);
      if (Number.isFinite(ts)) {
        warmupStartTs = ts;
        warmupStartIdx = idx;
      }
    }

    const tradeTotalBars =
      typeof tradeStartIdx === "number" && typeof tradeEndIdx === "number"
        ? Math.max(0, tradeEndIdx - tradeStartIdx + 1)
        : 0;
    const warmupTotalBars =
      typeof tradeStartIdx === "number" && typeof warmupStartIdx === "number"
        ? Math.max(0, tradeStartIdx - warmupStartIdx)
        : 0;

    return {
      rawFromSec,
      rawToSec,
      tradeStartTs,
      tradeEndTs,
      warmupStartTs,
      tradeStartIdx,
      tradeEndIdx,
      warmupStartIdx,
      tradeStartLocal: unixSecondsToDateTimeLocal(tradeStartTs),
      tradeEndLocal: unixSecondsToDateTimeLocal(tradeEndTs),
      warmupStartLocal: unixSecondsToDateTimeLocal(warmupStartTs),
      tradeTotalBars,
      warmupTotalBars,
    };
  }, [bars, selectedRangeFrom, selectedRangeTo, warmupBars]);
  const selectedRangeWindow = rangePlaybackMeta
    ? { from: rangePlaybackMeta.tradeStartTs, to: rangePlaybackMeta.tradeEndTs }
    : null;
  useEffect(() => {
    if (!selectedRangeWindow) {
      setAnalyzerChartState(null);
      return;
    }
    setAnalyzerChartState((prev) => {
      const prevFrom = Number(prev?.from);
      const prevTo = Number(prev?.to);
      const nextFrom = Number(selectedRangeWindow.from);
      const nextTo = Number(selectedRangeWindow.to);
      if (
        Number.isFinite(prevFrom) &&
        Number.isFinite(prevTo) &&
        Math.abs(prevFrom - nextFrom) < 0.001 &&
        Math.abs(prevTo - nextTo) < 0.001
      ) {
        return prev;
      }
      return { from: nextFrom, to: nextTo };
    });
  }, [selectedRangeWindow?.from, selectedRangeWindow?.to]);
  // ── Invalidate timeline cache when range/run changes ──────────
  const rangeKey = useMemo(() => {
    if (!isAnalyzerAttachedRun || !rangePlaybackMeta) return null;
    return `${rangePlaybackMeta.tradeStartTs}|${rangePlaybackMeta.tradeEndTs}|${analyzerRunKey}`;
  }, [isAnalyzerAttachedRun, rangePlaybackMeta, analyzerRunKey]);

  useEffect(() => {
    const cache = timelineCacheRef.current;
    if (cache.rangeKey !== rangeKey) {
      cache.processedRunBarCount = 0;
      cache.runBarsByTime = new Map();
      cache.progressedTradeBars = [];
      cache.timelinePoints = [];
      cache.observedCheckpointCounts = [];
      cache.warmupDone = 0;
      cache.tradeDone = 0;
      cache.startTime = null;
      cache.endTime = null;
      cache.rangeKey = rangeKey;
    }
  }, [rangeKey]);

  // ── Incrementally process new bars into timeline cache ────────
  const timelineCacheVersion = useMemo(() => {
    if (!isAnalyzerAttachedRun || !rangePlaybackMeta) return 0;
    const startTime = Number(rangePlaybackMeta.tradeStartTs);
    const endTime = Number(rangePlaybackMeta.tradeEndTs);
    if (!Number.isFinite(startTime) || !Number.isFinite(endTime)) return 0;

    const cache = timelineCacheRef.current;
    const runBars = Array.isArray(attachedRunBars) ? attachedRunBars : [];
    const prevCount = cache.processedRunBarCount;

    // Process only newly arrived bars
    if (runBars.length > prevCount) {
      cache.startTime = startTime;
      cache.endTime = endTime;

      for (let i = prevCount; i < runBars.length; i++) {
        const runBar = runBars[i];
        const t = Number(runBar?.time);
        if (!Number.isFinite(t)) continue;

        // Incremental warmup/trade counting
        if ((runBar as any)?.warmup_only === true) {
          cache.warmupDone += 1;
        } else {
          cache.tradeDone += 1;
        }

        if (t < startTime - 1 || t > endTime + 1) continue;
        cache.runBarsByTime.set(t, runBar);

        // Maintain sorted insertion for progressedTradeBars
        // (bars arrive in order, so push is correct)
        cache.progressedTradeBars.push(runBar);

        // Build timeline points for this new bar
        const barTime = t;
        const trace =
          (runBar?.intrabar_eval_trace && typeof runBar.intrabar_eval_trace === "object"
            ? runBar.intrabar_eval_trace
            : runBar?.analysis?.intrabar_eval_trace && typeof runBar.analysis.intrabar_eval_trace === "object"
              ? runBar.analysis.intrabar_eval_trace
              : runBar?.strategy_analysis?.intrabar_eval_trace &&
                  typeof runBar.strategy_analysis.intrabar_eval_trace === "object"
                ? runBar.strategy_analysis.intrabar_eval_trace
                : null) || null;
        const checkpoints = Array.isArray(trace?.checkpoints) ? trace.checkpoints : [];
        const normalizedCheckpoints = checkpoints
          .map((checkpoint: any, checkpointIndex: number) => {
            const checkpointTime =
              toUnixSeconds(checkpoint?.timestamp) ??
              (Number.isFinite(Number(checkpoint?.offset_sec))
                ? barTime + Number(checkpoint.offset_sec)
                : barTime);
            if (!Number.isFinite(Number(checkpointTime))) return null;
            return {
              kind: "checkpoint",
              time: Number(checkpointTime),
              barTime,
              checkpoint,
              checkpointIndex,
              runBar,
            };
          })
          .filter(Boolean)
          .sort((left: any, right: any) => Number(left.time || 0) - Number(right.time || 0));

        if (normalizedCheckpoints.length > 0) {
          cache.observedCheckpointCounts.push(normalizedCheckpoints.length);
          // Append in order (bars arrive chronologically)
          cache.timelinePoints.push(...normalizedCheckpoints);
        } else {
          cache.timelinePoints.push({
            kind: "bar",
            time: barTime,
            barTime,
            checkpoint: null,
            checkpointIndex: -1,
            runBar,
          });
        }
      }

      cache.processedRunBarCount = runBars.length;
    }

    // Return a version counter to trigger downstream useMemo recompute
    return cache.processedRunBarCount;
  }, [isAnalyzerAttachedRun, rangePlaybackMeta, attachedRunBars]);

  // ── rangeScrubMeta: derives from cached timeline (cheap read) ─
  // Split into two useMemo calls to break the circular dependency:
  // rangeScrubBase does NOT depend on rangeScrubOffset → no re-render loop.
  // rangeScrubMeta merges base + offset-derived values.
  const rangeScrubBase = useMemo(() => {
    if (!isAnalyzerAttachedRun || !rangePlaybackMeta || timelineCacheVersion === 0) {
      return null;
    }
    const cache = timelineCacheRef.current;
    const startTime = cache.startTime!;
    const endTime = cache.endTime!;
    const tradeStartIdx = Number(rangePlaybackMeta.tradeStartIdx);
    const tradeEndIdx = Number(rangePlaybackMeta.tradeEndIdx);

    const { progressedTradeBars, timelinePoints, observedCheckpointCounts } = cache;
    const progressedBars = progressedTradeBars.length;
    const progressedPoints = timelinePoints.length;
    const progressedMaxOffset = Math.max(0, progressedPoints - 1);

    let estimatedPointsPerBar = 1;
    if (observedCheckpointCounts.length > 0) {
      const sortedCounts = [...observedCheckpointCounts].sort((a, b) => a - b);
      estimatedPointsPerBar = Math.max(
        1,
        Math.round(sortedCounts[Math.floor(sortedCounts.length / 2)])
      );
    }

    const tradeTotalBars = Number(rangePlaybackMeta.tradeTotalBars || 0);
    const allBarsProcessed = tradeTotalBars > 0 && progressedBars >= tradeTotalBars;
    const fullEstimatedPoints = allBarsProcessed
      ? progressedPoints
      : tradeTotalBars > 0
        ? Math.max(tradeTotalBars, tradeTotalBars * estimatedPointsPerBar)
        : progressedPoints;
    const fullMaxOffset = Math.max(0, fullEstimatedPoints - 1);

    const progressPct =
      tradeTotalBars > 0 ? (Math.min(tradeTotalBars, progressedBars) / tradeTotalBars) * 100 : 0;
    const enabledTrackPct =
      fullMaxOffset > 0 && progressedPoints > 0
        ? Math.min(100, Math.max(0, (progressedMaxOffset / fullMaxOffset) * 100))
        : progressedPoints > 0
          ? 100
          : 0;

    let medianSpacingSec: number | null = null;
    if (timelinePoints.length >= 2) {
      const diffs: number[] = [];
      const sampleStart = Math.max(0, timelinePoints.length - 200);
      for (let i = Math.max(1, sampleStart); i < timelinePoints.length; i += 1) {
        const prevT = Number(timelinePoints[i - 1]?.time);
        const nextT = Number(timelinePoints[i]?.time);
        const diff = nextT - prevT;
        if (Number.isFinite(diff) && diff > 0) diffs.push(diff);
      }
      if (diffs.length) {
        diffs.sort((a, b) => a - b);
        medianSpacingSec = diffs[Math.floor(diffs.length / 2)];
      }
    }
    const sliderStepBars =
      Number.isFinite(medianSpacingSec) && (medianSpacingSec as number) > 0 && (medianSpacingSec as number) < 5
        ? Math.max(1, Math.round(5 / (medianSpacingSec as number)))
        : 1;
    const sliderStepSeconds =
      Number.isFinite(medianSpacingSec) && (medianSpacingSec as number) > 0
        ? sliderStepBars * (medianSpacingSec as number)
        : null;

    return {
      tradeStartIdx: Number.isInteger(tradeStartIdx) ? tradeStartIdx : null,
      tradeEndIdx: Number.isInteger(tradeEndIdx) ? tradeEndIdx : null,
      startTime,
      endTime,
      progressedTradeBars,
      progressedBars,
      progressedPoints,
      timelinePoints,
      tradeTotalBars,
      progressPct,
      fullMaxOffset,
      progressedMaxOffset,
      enabledTrackPct,
      estimatedPointsPerBar,
      sliderStepBars,
      sliderStepSeconds,
      startLocal: unixSecondsToDateTimeLocal(startTime),
      endLocal: unixSecondsToDateTimeLocal(endTime),
    };
  }, [isAnalyzerAttachedRun, rangePlaybackMeta, timelineCacheVersion]);

  // Offset-dependent values: depends on rangeScrubOffset but does NOT
  // trigger any useEffect that sets rangeScrubOffset → no loop.
  const rangeScrubMeta = useMemo(() => {
    if (!rangeScrubBase) return null;
    const { progressedPoints, timelinePoints, progressedMaxOffset } = rangeScrubBase;
    const clampedOffset =
      progressedPoints > 0 ? Math.max(0, Math.min(rangeScrubOffset, progressedMaxOffset)) : 0;
    const targetPoint = progressedPoints > 0 ? timelinePoints[clampedOffset] : null;
    const targetBar = targetPoint?.runBar || null;
    const targetCheckpoint = targetPoint?.checkpoint || null;
    const targetTime = Number(targetPoint?.time);
    return {
      ...rangeScrubBase,
      clampedOffset,
      targetPoint,
      targetBar,
      targetCheckpoint,
      targetTime: Number.isFinite(targetTime) ? targetTime : null,
      targetLocal: Number.isFinite(targetTime) ? unixSecondsToLabel(targetTime, true) : null,
    };
  }, [rangeScrubBase, rangeScrubOffset]);

  // Clamp offset when progressedMaxOffset shrinks (e.g. range change).
  // Depends on primitives from rangeScrubBase → no object-identity loop.
  const _progressedMaxOffset = rangeScrubBase?.progressedMaxOffset ?? 0;
  useEffect(() => {
    if (!rangeScrubBase) {
      setRangeScrubOffset(0);
      return;
    }
    setRangeScrubOffset((prev) => {
      const clamped = Math.max(0, Math.min(prev, _progressedMaxOffset));
      return clamped === prev ? prev : clamped;
    });
  }, [rangeScrubBase, _progressedMaxOffset]);

  // Auto-follow latest bar during playback.
  useEffect(() => {
    if (!isAnalyzerAttachedRun || !isPlayingRun || !rangeScrubBase) return;
    if (rangeScrubBase.progressedBars <= 0) return;
    setRangeScrubOffset((prev) =>
      prev === _progressedMaxOffset ? prev : _progressedMaxOffset
    );
  }, [isAnalyzerAttachedRun, isPlayingRun, rangeScrubBase, _progressedMaxOffset]);

  const focusSelectedRangeOffset = useCallback(
    (nextOffset: number) => {
      if (!rangeScrubMeta) return;
      const clampedOffset = Math.max(0, Math.min(Math.trunc(nextOffset), rangeScrubMeta.progressedMaxOffset));
      setRangeScrubOffset(clampedOffset);
    },
    [rangeScrubMeta]
  );
  const moveSelectedRangeByStep = useCallback(
    (direction: -1 | 1) => {
      if (!rangeScrubMeta) return;
      const stepBars = Math.max(1, Math.trunc(Number(rangeScrubMeta.sliderStepBars) || 1));
      focusSelectedRangeOffset(rangeScrubMeta.clampedOffset + direction * stepBars);
    },
    [rangeScrubMeta, focusSelectedRangeOffset]
  );

  // ── analyzerPlaybackProgress: reads from incremental cache ────
  const analyzerPlaybackProgress = useMemo(() => {
    if (!isAnalyzerAttachedRun || !rangePlaybackMeta) return null;

    const cache = timelineCacheRef.current;
    const warmupDone = cache.warmupDone;
    const tradeDone = cache.tradeDone;

    const backendTotalBars = Number(attachedRunState?.total_bars || 0);
    const estimatedWarmup = Number(rangePlaybackMeta.warmupTotalBars || 0);

    const warmupTotal = backendTotalBars > 0
      ? Math.min(estimatedWarmup, backendTotalBars)
      : estimatedWarmup;
    const tradeTotal = backendTotalBars > 0
      ? Math.max(0, backendTotalBars - warmupTotal)
      : Number(rangePlaybackMeta.tradeTotalBars || 0);

    const warmupClamped = warmupTotal > 0 ? Math.min(warmupTotal, warmupDone) : 0;
    const tradeClamped = tradeTotal > 0 ? Math.min(tradeTotal, tradeDone) : tradeDone;
    const isInitializing = warmupTotal > 0 && warmupClamped < warmupTotal;
    const tradeProgressPct = tradeTotal > 0 ? (tradeClamped / tradeTotal) * 100 : 0;
    return {
      warmupDone: warmupClamped,
      warmupTotal,
      tradeDone: tradeClamped,
      tradeTotal,
      tradeProgressPct,
      isInitializing,
    };
  }, [isAnalyzerAttachedRun, rangePlaybackMeta, timelineCacheVersion, attachedRunState]);
  const analyzerDisplayPhase = analyzerPlaybackProgress?.isInitializing
    ? "INITIALIZING"
    : analyzerRunPhase;
  const analyzerChartMarkers = useMemo(() => {
    const sourceMarkers = Array.isArray(analyzerDecisionEvents) ? analyzerDecisionEvents : [];
    if (!sourceMarkers.length) return [];

    const minTime = Number(selectedRangeWindow?.from);
    const maxTime = Number(selectedRangeWindow?.to);
    const scrubCutoffTime = Number(rangeScrubMeta?.targetTime);
    const hasScrubCutoff = Number.isFinite(scrubCutoffTime);
    const scrubCutoffBarIndex = Number(rangeScrubMeta?.targetBar?.bar_index);
    const dedupeKeys = new Set<string>();

    return sourceMarkers.filter((marker: any) => {
      const markerTime = toUnixSeconds(marker?.time ?? marker?.timestamp);
      if (Number.isFinite(markerTime)) {
        if (Number.isFinite(minTime) && markerTime < minTime - 1) return false;
        if (Number.isFinite(maxTime) && markerTime > maxTime + 1) return false;
        if (hasScrubCutoff && markerTime > scrubCutoffTime + 1) return false;
      } else if (hasScrubCutoff && Number.isFinite(scrubCutoffBarIndex)) {
        const markerBarIndex = Number(marker?.bar_index);
        if (Number.isFinite(markerBarIndex) && markerBarIndex > scrubCutoffBarIndex) {
          return false;
        }
      }

      const markerType = String(marker?.marker_type || "").trim();
      if (markerType === "regime_detected" || markerType === "strategy_selected") {
        const timeKey = Number.isFinite(markerTime)
          ? `ts:${Math.floor(markerTime)}`
          : Number.isFinite(Number(marker?.bar_index))
            ? `bar:${Number(marker.bar_index)}`
            : "";
        const valueKey =
          markerType === "regime_detected"
            ? String(marker?.regime || "").trim().toUpperCase()
            : String(marker?.strategy || "").trim().toUpperCase();
        const dedupeKey = `${markerType}|${timeKey}|${valueKey}`;
        if (dedupeKeys.has(dedupeKey)) return false;
        dedupeKeys.add(dedupeKey);
      }

      return true;
    });
  }, [analyzerDecisionEvents, selectedRangeWindow, rangeScrubMeta]);
  // ── chartBars: uses cached runBarsByTime Map from timeline cache ─
  const chartBars = useMemo(() => {
    const previewBars = Array.isArray(bars) ? bars : [];
    if (!previewBars.length) return previewBars;
    if (!isAnalyzerAttachedRun || !selectedRangeWindow) return previewBars;

    const minTime = selectedRangeWindow.from - 1;
    const maxTime = selectedRangeWindow.to + 1;
    const scrubCutoffTime = Number(rangeScrubMeta?.targetTime);
    const hasScrubCutoff = Number.isFinite(scrubCutoffTime);
    // Reuse the incrementally-built Map from the timeline cache
    const runBarsByTime = timelineCacheRef.current.runBarsByTime;

    let touchedSegment = false;
    const composedBars = previewBars.map((previewBar: any) => {
      const t = Number(previewBar?.time);
      if (!Number.isFinite(t) || t < minTime || t > maxTime) return previewBar;
      touchedSegment = true;
      if (hasScrubCutoff && t > scrubCutoffTime + 1) {
        return { time: t, __wfPlaceholder: true };
      }
      const runBar = runBarsByTime.get(t);
      if (runBar) return runBar;
      return { time: t, __wfPlaceholder: true };
    });
    return touchedSegment ? composedBars : previewBars;
  }, [bars, isAnalyzerAttachedRun, selectedRangeWindow, timelineCacheVersion, rangeScrubMeta]);

  const extractRunBarAnalysis = useCallback((bar: any) => {
    if (!bar || typeof bar !== "object") return null;
    const hasLayerScoresOnBar = Boolean(
      (bar.layer_scores && typeof bar.layer_scores === "object") ||
      (bar.analysis?.layer_scores && typeof bar.analysis.layer_scores === "object") ||
      (bar.strategy_analysis?.layer_scores && typeof bar.strategy_analysis.layer_scores === "object")
    );
    const checkpointIntrabar =
      bar.intrabar_1s && typeof bar.intrabar_1s === "object" ? bar.intrabar_1s : null;
    const checkpointLayerScores =
      bar.layer_scores && typeof bar.layer_scores === "object" ? bar.layer_scores : null;
    const checkpointSignalRejected =
      bar.signal_rejected && typeof bar.signal_rejected === "object" ? bar.signal_rejected : null;
    const checkpointCandidateDiagnostics =
      bar.candidate_diagnostics && typeof bar.candidate_diagnostics === "object" ? bar.candidate_diagnostics : null;
    const checkpointLike =
      !hasLayerScoresOnBar &&
      (checkpointIntrabar || Number.isFinite(Number(bar?.offset_sec)) || typeof bar?.provisional === "boolean");
    if (checkpointLike) {
      const hasCheckpointScores = Boolean(checkpointLayerScores);
      return {
        layer_scores: checkpointLayerScores,
        signal_rejected: checkpointSignalRejected,
        candidate_diagnostics: checkpointCandidateDiagnostics,
        intrabar_1s: checkpointIntrabar,
        intrabar_confirmation:
          bar.intrabar_confirmation && typeof bar.intrabar_confirmation === "object"
            ? bar.intrabar_confirmation
            : null,
        micro_confirmation:
          bar.micro_confirmation && typeof bar.micro_confirmation === "object"
            ? bar.micro_confirmation
            : null,
        level_context:
          bar.level_context && typeof bar.level_context === "object" ? bar.level_context : null,
        context_risk:
          bar.context_risk && typeof bar.context_risk === "object" ? bar.context_risk : null,
        warmup_only: false,
        bar_index: null,
        checkpoint_mode: true,
        intrabar_only_checkpoint: !hasCheckpointScores,
        checkpoint_offset_sec: Number.isFinite(Number(bar?.offset_sec)) ? Number(bar.offset_sec) : null,
        provisional: typeof bar?.provisional === "boolean" ? Boolean(bar.provisional) : null,
        timestamp: typeof bar?.timestamp === "string" ? bar.timestamp : null,
      };
    }

    const layerScores =
      (bar.layer_scores && typeof bar.layer_scores === "object" && bar.layer_scores) ||
      (bar.analysis?.layer_scores && typeof bar.analysis.layer_scores === "object" && bar.analysis.layer_scores) ||
      (bar.strategy_analysis?.layer_scores &&
        typeof bar.strategy_analysis.layer_scores === "object" &&
        bar.strategy_analysis.layer_scores) ||
      null;
    const intradayLevels =
      (bar.intraday_levels && typeof bar.intraday_levels === "object" ? bar.intraday_levels : null) ||
      (bar.analysis?.intraday_levels && typeof bar.analysis.intraday_levels === "object"
        ? bar.analysis.intraday_levels
        : null) ||
      (bar.analysis?.metadata?.intraday_levels && typeof bar.analysis.metadata.intraday_levels === "object"
        ? bar.analysis.metadata.intraday_levels
        : null) ||
      (bar.analysis?.signal_metadata?.intraday_levels &&
      typeof bar.analysis.signal_metadata.intraday_levels === "object"
        ? bar.analysis.signal_metadata.intraday_levels
        : null) ||
      (bar.analysis?.signal?.metadata?.intraday_levels &&
      typeof bar.analysis.signal.metadata.intraday_levels === "object"
        ? bar.analysis.signal.metadata.intraday_levels
        : null) ||
      (bar.strategy_analysis?.intraday_levels && typeof bar.strategy_analysis.intraday_levels === "object"
        ? bar.strategy_analysis.intraday_levels
        : null) ||
      (bar.strategy_analysis?.metadata?.intraday_levels &&
      typeof bar.strategy_analysis.metadata.intraday_levels === "object"
        ? bar.strategy_analysis.metadata.intraday_levels
        : null) ||
      (bar.strategy_analysis?.signal_metadata?.intraday_levels &&
      typeof bar.strategy_analysis.signal_metadata.intraday_levels === "object"
        ? bar.strategy_analysis.signal_metadata.intraday_levels
        : null) ||
      null;
    if (!layerScores && !intradayLevels) return null;

    const signalRejected =
      bar.signal_rejected ??
      bar.analysis?.signal_rejected ??
      bar.strategy_analysis?.signal_rejected ??
      null;
    const candidateDiagnostics =
      bar.candidate_diagnostics ??
      bar.analysis?.candidate_diagnostics ??
      bar.strategy_analysis?.candidate_diagnostics ??
      null;
    const warmupOnly =
      typeof bar.warmup_only === "boolean"
        ? bar.warmup_only
        : typeof bar.analysis?.warmup_only === "boolean"
          ? bar.analysis.warmup_only
          : typeof bar.strategy_analysis?.warmup_only === "boolean"
            ? bar.strategy_analysis.warmup_only
            : false;
    const barIndexCandidate =
      bar.bar_index ??
      bar.analysis?.bar_index ??
      bar.strategy_analysis?.bar_index ??
      null;

    return {
      layer_scores: layerScores,
      signal_rejected: signalRejected,
      candidate_diagnostics: candidateDiagnostics,
      intrabar_1s:
        (bar.intrabar_1s && typeof bar.intrabar_1s === "object" ? bar.intrabar_1s : null) ||
        (bar.analysis?.intrabar_1s && typeof bar.analysis.intrabar_1s === "object"
          ? bar.analysis.intrabar_1s
          : null) ||
        (bar.strategy_analysis?.intrabar_1s && typeof bar.strategy_analysis.intrabar_1s === "object"
          ? bar.strategy_analysis.intrabar_1s
          : null),
      intrabar_eval_trace:
        (bar.intrabar_eval_trace && typeof bar.intrabar_eval_trace === "object" ? bar.intrabar_eval_trace : null) ||
        (bar.analysis?.intrabar_eval_trace && typeof bar.analysis.intrabar_eval_trace === "object"
          ? bar.analysis.intrabar_eval_trace
          : null) ||
        (bar.strategy_analysis?.intrabar_eval_trace &&
        typeof bar.strategy_analysis.intrabar_eval_trace === "object"
          ? bar.strategy_analysis.intrabar_eval_trace
          : null),
      intraday_levels: intradayLevels,
      bar_index: Number.isFinite(Number(barIndexCandidate)) ? Number(barIndexCandidate) : null,
      warmup_only: warmupOnly,
      timestamp: bar.timestamp || bar.analysis?.timestamp || bar.strategy_analysis?.timestamp || null,
    };
  }, []);

  const scrubbedLiveAnalysis = useMemo(() => {
    const checkpointSnapshot = extractRunBarAnalysis(rangeScrubMeta?.targetCheckpoint);
    const targetBar = rangeScrubMeta?.targetBar;
    const direct = extractRunBarAnalysis(targetBar);
    if (checkpointSnapshot && direct) {
      const hasCheckpointScores = Boolean(checkpointSnapshot.layer_scores);
      const hasParentScores = Boolean(direct.layer_scores);
      return {
        ...direct,
        ...checkpointSnapshot,
        layer_scores: hasCheckpointScores ? checkpointSnapshot.layer_scores : direct.layer_scores,
        signal_rejected: hasCheckpointScores ? (checkpointSnapshot.signal_rejected ?? direct.signal_rejected) : direct.signal_rejected,
        candidate_diagnostics: hasCheckpointScores ? (checkpointSnapshot.candidate_diagnostics ?? direct.candidate_diagnostics) : direct.candidate_diagnostics,
        intrabar_only_checkpoint: (hasCheckpointScores || hasParentScores) ? false : checkpointSnapshot.intrabar_only_checkpoint,
        checkpoint_mode: hasCheckpointScores ? true : (hasParentScores ? false : checkpointSnapshot.checkpoint_mode),
      };
    }
    if (checkpointSnapshot) return checkpointSnapshot;
    if (direct) return direct;

    const progressed = Array.isArray(rangeScrubMeta?.progressedTradeBars)
      ? rangeScrubMeta.progressedTradeBars
      : [];
    const targetTime = Number(rangeScrubMeta?.targetTime);
    if (!progressed.length || !Number.isFinite(targetTime)) return null;

    // Prefer the most recent executed bar at or before the scrubbed bar.
    for (let i = progressed.length - 1; i >= 0; i -= 1) {
      const bar = progressed[i];
      const t = Number(bar?.time);
      if (!Number.isFinite(t) || t > targetTime + 1) continue;
      const snapshot = extractRunBarAnalysis(bar);
      if (snapshot) return snapshot;
    }

    // Fallback: nearest future bar snapshot in case only sparse snapshots exist.
    for (let i = 0; i < progressed.length; i += 1) {
      const bar = progressed[i];
      const t = Number(bar?.time);
      if (!Number.isFinite(t) || t < targetTime - 1) continue;
      const snapshot = extractRunBarAnalysis(bar);
      if (snapshot) return snapshot;
    }

    return null;
  }, [rangeScrubMeta, extractRunBarAnalysis]);
  const scrubbedCheckpointHasDecisionPayload = useMemo(() => {
    if (!scrubbedLiveAnalysis || typeof scrubbedLiveAnalysis !== "object") return false;
    return Boolean(
      (scrubbedLiveAnalysis.layer_scores &&
        typeof scrubbedLiveAnalysis.layer_scores === "object") ||
        (scrubbedLiveAnalysis.signal_rejected &&
          typeof scrubbedLiveAnalysis.signal_rejected === "object") ||
        (scrubbedLiveAnalysis.candidate_diagnostics &&
          typeof scrubbedLiveAnalysis.candidate_diagnostics === "object")
    );
  }, [scrubbedLiveAnalysis]);

  const scrubbedConditionsActive = Boolean(rangeScrubMeta && Number(rangeScrubMeta.progressedPoints || 0) > 0);
  // During slider scrub, always drive Entry Conditions from scrubbed checkpoint snapshots.
  const effectiveConditionsMarker = scrubbedConditionsActive ? null : selectedMarker;
  const effectiveConditionsLiveAnalysis = effectiveConditionsMarker
    ? null
    : scrubbedConditionsActive
      ? (() => {
          const base = scrubbedCheckpointHasDecisionPayload
            ? scrubbedLiveAnalysis
            : (
                scrubLiveAnalysis
                  ? {
                      ...scrubbedLiveAnalysis,
                      ...scrubLiveAnalysis,
                      candidate_diagnostics:
                        scrubLiveAnalysis.candidate_diagnostics ||
                        scrubLiveAnalysis.signal?.metadata?.candidate_diagnostics ||
                        scrubbedLiveAnalysis?.candidate_diagnostics,
                      signal_rejected:
                        scrubLiveAnalysis.signal_rejected || scrubbedLiveAnalysis?.signal_rejected,
                      checkpoint_mode: false,
                      intrabar_only_checkpoint: false,
                    }
                  : scrubbedLiveAnalysis ||
                    ((rangeScrubMeta?.clampedOffset ?? -1) ===
                    (rangeScrubMeta?.progressedMaxOffset ?? -2)
                      ? latestBarAnalysis
                      : null)
              );
          // Ensure timestamp is present for panel header display during scrubbing
          if (base && !base.timestamp && rangeScrubMeta?.targetTime) {
            return { ...base, timestamp: rangeScrubMeta.targetTime };
          }
          return base;
        })()
      : (!selectedMarker ? latestBarAnalysis : null);
  useEffect(() => {
    if (!scrubbedConditionsActive) {
      lastStableScrubAnalysisRef.current = null;
      return;
    }
    if (effectiveConditionsLiveAnalysis && typeof effectiveConditionsLiveAnalysis === "object") {
      lastStableScrubAnalysisRef.current = effectiveConditionsLiveAnalysis;
    }
  }, [scrubbedConditionsActive, effectiveConditionsLiveAnalysis]);
  const stableConditionsLiveAnalysis =
    scrubbedConditionsActive
      ? (effectiveConditionsLiveAnalysis || lastStableScrubAnalysisRef.current)
      : effectiveConditionsLiveAnalysis;
  const hasConditionsPanelData = Boolean(
    effectiveConditionsMarker || stableConditionsLiveAnalysis || scrubbedConditionsActive
  );

  const conditionsPanelBadge = useMemo(() => {
    if (scrubbedConditionsActive) {
      if (rangeScrubMeta?.targetLocal) {
        return {
          label: `scrub ${rangeScrubMeta.targetLocal.replace("T", " ")}`,
          tone: "muted" as const,
        };
      }
      return { label: "scrub", tone: "muted" as const };
    }
    if (selectedMarker) {
      return {
        label: selectedMarker.strategy || selectedMarker.marker_type?.replace(/_/g, " "),
        tone: "accent" as const,
      };
    }
    if (latestBarAnalysis) {
      return { label: "live", tone: "muted" as const };
    }
    return null;
  }, [scrubbedConditionsActive, rangeScrubMeta, selectedMarker, latestBarAnalysis]);

  const handleAnalyzerBarClick = useCallback((bar: any) => {
    if (!bar || typeof bar !== "object" || bar.__wfPlaceholder) return;

    const barTime = Number(bar.time);
    const markersInWindow = resolveMarkersInBarWindow(analyzerDecisionEvents, barTime, 60);

    let resolved = extractIntradayLevelsFromBarPayload(bar);
    let sourceMarker = null;

    if (!resolved.payload) {
      resolved = extractIntradayLevelsFromAnalysisObject(
        stableConditionsLiveAnalysis,
        "effective_conditions_live_analysis"
      );
    }

    if (!resolved.payload) {
      for (const marker of markersInWindow) {
        const markerLevels = extractIntradayLevelsFromMarkerPayload(marker);
        if (!markerLevels.payload) continue;
        resolved = markerLevels;
        sourceMarker = marker;
        break;
      }
    }

    if (!resolved.payload) {
      const nearestMarkerMatch = resolveNearestMarkerWithIntradayLevels(analyzerDecisionEvents, barTime);
      if (nearestMarkerMatch) {
        resolved = nearestMarkerMatch.levels;
        sourceMarker = nearestMarkerMatch.marker;
      }
    }

    const relatedMarkers =
      sourceMarker && !markersInWindow.some((candidate) => candidate?.id === sourceMarker?.id)
        ? [...markersInWindow, sourceMarker]
        : markersInWindow;

    setSelectedIntradayLevels({
      bar,
      payload: resolved.payload,
      sourcePath: resolved.sourcePath,
      sourceMarker,
      relatedMarkers,
      timeframeSeconds: 60,
    });
  }, [analyzerDecisionEvents, stableConditionsLiveAnalysis]);

  const closeIntradayLevelsDialog = useCallback(() => {
    setSelectedIntradayLevels(null);
  }, []);

  useEffect(() => {
    setSelectedIntradayLevels(null);
  }, [analyzerRunKey, selectedRangeFrom, selectedRangeTo]);

  useEffect(() => {
    if (isAnalyzerAttachedRun) return;
    setIsConditionsDetached(false);
    setIsDecisionsDetached(false);
  }, [isAnalyzerAttachedRun]);

  /* ── fetch available tickers on mount ──────────────────────────── */
  useEffect(() => {
    let cancelled = false;
    setLoadingTickers(true);
    fetch("/api/available-data")
      .then((r) => r.json())
      .then((data) => {
        if (cancelled) return;
        const ranges = data?.date_ranges || {};
        const list: AvailableTicker[] = Object.entries(ranges).map(
          ([t, r]: [string, any]) => ({
            ticker: t,
            start_date: r?.ohlcv_start || r?.start || "",
            end_date: r?.ohlcv_end || r?.end || "",
          })
        );
        list.sort((a, b) => a.ticker.localeCompare(b.ticker));
        setTickers(list);

        // auto-populate dates for selected ticker
        const match = list.find((t) => t.ticker === (selectedTicker || "MU"));
        if (match) {
          setDateFrom(match.start_date);
          setDateTo(match.end_date);
        }
      })
      .catch(() => {})
      .finally(() => !cancelled && setLoadingTickers(false));
    return () => {
      cancelled = true;
    };
  }, []);

  /* ── ticker change → update dates ──────────────────────────────── */
  const handleTickerChange = useCallback(
    (newTicker: string) => {
      setTicker(newTicker);
      onTickerChange(newTicker);
      const match = tickers.find((t) => t.ticker === newTicker);
      if (match) {
        setDateFrom(match.start_date);
        setDateTo(match.end_date);
      }
      // clear old data
      setBars([]);
      setBarCount(0);
      setSelectedRangeFrom(null);
      setSelectedRangeTo(null);
      setRangeScrubOffset(0);
      setAnalyzerRunKey(null);
    },
    [tickers, onTickerChange]
  );

  /* ── load bars ─────────────────────────────────────────────────── */
  const loadBars = useCallback(async () => {
    if (!ticker || !dateFrom || !dateTo) return;
    setLoading(true);
    setError(null);
    setBars([]);
    setBarCount(0);
    setSelectedRangeFrom(null);
    setSelectedRangeTo(null);
    setRangeScrubOffset(0);
    setAnalyzerRunKey(null);
    try {
      const url = `/api/chart-preview/bars?ticker=${encodeURIComponent(ticker)}&date_from=${dateFrom}&date_to=${dateTo}`;
      const resp = await fetch(url);
      if (!resp.ok) {
        const detail = await resp.json().catch(() => ({}));
        throw new Error(detail?.detail || `HTTP ${resp.status}`);
      }
      const data = await resp.json();
      const converted = (data.bars || []).map(toChartBar).filter(Boolean);
      setBars(converted);
      setBarCount(data.bar_count || converted.length);
    } catch (e: any) {
      setError(e.message || "Failed to load bars");
    } finally {
      setLoading(false);
    }
  }, [ticker, dateFrom, dateTo]);

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

  const handleEvaluateIntrabarSlice = useCallback(async (ts: number) => {
    if (typeof onEvaluateIntrabarSlice === "function") {
      const requestSeq = ++scrubEvalSeqRef.current;
      setIsScrubbingLiveEval(true);
      try {
        const result = await onEvaluateIntrabarSlice(ts);
        if (scrubEvalSeqRef.current !== requestSeq) return;
        setScrubLiveAnalysis(result);
      } catch (err) {
        if (scrubEvalSeqRef.current !== requestSeq) return;
        console.error("Intrabar slice evaluation failed:", err);
        setScrubLiveAnalysis(null);
      } finally {
        if (scrubEvalSeqRef.current === requestSeq) {
          setIsScrubbingLiveEval(false);
        }
      }
    }
  }, [onEvaluateIntrabarSlice]);

  useEffect(() => {
    // Attempt to evaluate only when scrubbed checkpoint itself has no decision payload.
    if (
      rangeScrubMeta?.targetTime &&
      !scrubbedCheckpointHasDecisionPayload &&
      typeof onEvaluateIntrabarSlice === "function"
    ) {
      const delay = setTimeout(() => {
        handleEvaluateIntrabarSlice(rangeScrubMeta.targetTime!);
      }, 300); // debounce
      return () => clearTimeout(delay);
    }
    // Invalidate stale async eval responses when checkpoint payload is available.
    scrubEvalSeqRef.current += 1;
    setIsScrubbingLiveEval(false);
    setScrubLiveAnalysis(null);
  }, [
    rangeScrubMeta?.targetTime,
    scrubbedCheckpointHasDecisionPayload,
    handleEvaluateIntrabarSlice,
    onEvaluateIntrabarSlice,
  ]);

  /* ── start test ────────────────────────────────────────────────── */
  const handleStartTest = useCallback(async () => {
    if (!selectedRangeFrom || !selectedRangeTo || !ticker) return;
    setRunLoading(true);
    setError(null);
    try {
      const effectiveStartLocal = rangePlaybackMeta?.warmupStartLocal || selectedRangeFrom;
      const effectiveEndLocal = rangePlaybackMeta?.tradeEndLocal || selectedRangeTo;
      const effectiveTradeStartLocal = rangePlaybackMeta?.tradeStartLocal || selectedRangeFrom;
      const effectiveTradeEndLocal = rangePlaybackMeta?.tradeEndLocal || selectedRangeTo;

      // Extract date part (YYYY-MM-DD) for the run API; datetime-local values are "YYYY-MM-DDTHH:mm"
      const payload = {
        run_id: `analyzer-${Date.now()}`,
        ticker,
        date_from: effectiveStartLocal.slice(0, 10),
        date_to: effectiveEndLocal.slice(0, 10),
        start_time: dateTimeLocalToUtcIso(effectiveStartLocal),
        end_time: dateTimeLocalToUtcIso(effectiveEndLocal),
        trade_start_time: dateTimeLocalToUtcIso(effectiveTradeStartLocal),
        trade_end_time: dateTimeLocalToUtcIso(effectiveTradeEndLocal),
        strategy_api_url: strategyApiUrl || defaultStrategyApiUrl,
        include_extended_hours: true,
        trade_eval_mode: analyzerTradeEvalMode,
      };
      if (typeof onStartRun === "function") {
        const result = await onStartRun(payload);
        const nextRunKey = String(result?.run_key || "").trim();
        setRangeScrubOffset(0);
        setAnalyzerRunKey(nextRunKey || null);
      } else {
        const resp = await fetch("/api/run/start", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        if (!resp.ok) {
          const detail = await resp.json().catch(() => ({}));
          throw new Error(detail?.detail || `HTTP ${resp.status}`);
        }
        const data = await resp.json().catch(() => ({}));
        const nextRunKey = String(data?.run_key || "").trim();
        setRangeScrubOffset(0);
        setAnalyzerRunKey(nextRunKey || null);
        // Legacy fallback behavior for standalone usage.
        onSwitchToBacktest?.();
      }
    } catch (e: any) {
      setError(e.message || "Failed to start test");
    } finally {
      setRunLoading(false);
    }
  }, [selectedRangeFrom, selectedRangeTo, ticker, strategyApiUrl, onStartRun, onSwitchToBacktest, rangePlaybackMeta, analyzerTradeEvalMode]);

  const handleClearAnalyzerRun = useCallback(async () => {
    if (!isAnalyzerAttachedRun) return;
    setError(null);
    try {
      await onClearRun?.();
      setAnalyzerRunKey(null);
    } catch (e: any) {
      setError(e?.message || "Failed to clear run");
    }
  }, [isAnalyzerAttachedRun, onClearRun]);

  const handleAnalyzerChartStateChange = useCallback((nextRange: any) => {
    if (!nextRange) return;
    const from = Number(nextRange.from);
    const to = Number(nextRange.to);
    if (!Number.isFinite(from) || !Number.isFinite(to)) return;
    setAnalyzerChartState((prev) => {
      const prevFrom = Number(prev?.from);
      const prevTo = Number(prev?.to);
      if (
        Number.isFinite(prevFrom) &&
        Number.isFinite(prevTo) &&
        Math.abs(prevFrom - from) < 0.001 &&
        Math.abs(prevTo - to) < 0.001
      ) {
        return prev;
      }
      return { from, to };
    });
  }, []);

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

  const decisionSelectHandler = onDecisionSelectMarker || (() => {});

  const entryConditionsContent = (
    <div style={{ flex: 1, minHeight: 0, overflowY: "auto", overflowX: "hidden", position: "relative" }}>
      <StrategyConditionsPanel
        marker={effectiveConditionsMarker}
        liveAnalysis={stableConditionsLiveAnalysis}
      />
      {isScrubbingLiveEval && (
        <div style={{ position: "absolute", top: 0, left: 0, width: "100%", height: "100%", background: "rgba(0,0,0,0.2)", display: "flex", alignItems: "center", justifyContent: "center" }}>
          <span style={{ color: "var(--text-muted)", fontSize: "0.8rem" }}>evaluating...</span>
        </div>
      )}
    </div>
  );

  const decisionsContent = (
    <div
      className="card-body"
      style={{
        flex: 1,
        minHeight: 0,
        overflow: "hidden",
        display: "flex",
        flexDirection: "column",
      }}
    >
      <DecisionPanel
        markers={analyzerDecisionEvents}
        selectedMarker={selectedMarker}
        onSelectMarker={decisionSelectHandler}
      />
    </div>
  );

  /* ── render ────────────────────────────────────────────────────── */
  return (
    <div className="strategy-analyzer" style={{ display: "flex", flexDirection: "column", gap: "0.75rem", height: "100%", padding: "0.75rem" }}>
      {/* ── Header: Ticker + Date Range + Load ─────────────────── */}
      <div className="card" style={{ padding: "0.75rem 1rem" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", flexWrap: "wrap" }}>
          <label style={{ fontWeight: 600, fontSize: "0.85rem", color: "var(--text-secondary)" }}>Ticker</label>
          <select
            className="chart-timeframe"
            value={ticker}
            onChange={(e) => handleTickerChange(e.target.value)}
            style={{ minWidth: 90 }}
          >
            {tickers.map((t) => (
              <option key={t.ticker} value={t.ticker}>
                {t.ticker}
              </option>
            ))}
            {tickers.length === 0 && <option value={ticker}>{ticker}</option>}
          </select>

          <label style={{ fontWeight: 600, fontSize: "0.85rem", color: "var(--text-secondary)" }}>From</label>
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            style={{ padding: "4px 8px", borderRadius: "var(--radius-sm)", border: "1px solid var(--border-color)", background: "var(--bg-secondary)", color: "var(--text-primary)", fontSize: "0.85rem" }}
          />

          <label style={{ fontWeight: 600, fontSize: "0.85rem", color: "var(--text-secondary)" }}>To</label>
          <input
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            style={{ padding: "4px 8px", borderRadius: "var(--radius-sm)", border: "1px solid var(--border-color)", background: "var(--bg-secondary)", color: "var(--text-primary)", fontSize: "0.85rem" }}
          />

          <button
            className="btn btn-primary"
            onClick={loadBars}
            disabled={loading || !ticker || !dateFrom || !dateTo}
            style={{ padding: "6px 16px", fontSize: "0.85rem", fontWeight: 600 }}
          >
            {loading ? "Loading..." : "Load Chart"}
          </button>

          {barCount > 0 && (
            <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
              {barCount.toLocaleString()} bars
            </span>
          )}

          <label style={{ fontWeight: 600, fontSize: "0.8rem", color: "var(--text-secondary)" }}>
            Warmup bars
          </label>
          <input
            type="number"
            min={0}
            step={1}
            value={warmupBars}
            onChange={(e) => {
              const raw = Number(e.target.value);
              setWarmupBars(Number.isFinite(raw) ? Math.max(0, Math.trunc(raw)) : 0);
            }}
            style={{
              width: 84,
              padding: "4px 8px",
              borderRadius: "var(--radius-sm)",
              border: "1px solid var(--border-color)",
              background: "var(--bg-secondary)",
              color: "var(--text-primary)",
              fontSize: "0.8rem",
            }}
            title="How many bars before the selected range to preload for warmup"
          />

          {isAnalyzerAttachedRun ? (
            <>
              <div style={{ width: 1, alignSelf: "stretch", background: "var(--border-color)" }} />
              <label style={{ fontWeight: 600, fontSize: "0.78rem", color: "var(--text-secondary)" }}>
                Eval
              </label>
              <select
                className="chart-timeframe"
                value={analyzerTradeEvalMode}
                onChange={(e) => setAnalyzerTradeEvalMode(e.target.value as any)}
                disabled={runLoading || isPlayingRun}
                style={{ minWidth: 118, fontSize: "0.78rem", padding: "4px 8px" }}
                title="Walking-forward evaluation mode for Play"
              >
                <option value="standard">1m (standard)</option>
                <option value="intrabar_1s">Intrabar 1s</option>
                <option value="intrabar_5s">Intrabar 5s</option>
              </select>
              <button
                className="btn btn-primary"
                onClick={() => void onPlayRun?.({ trade_eval_mode: analyzerTradeEvalMode })}
                disabled={runLoading || isPlayingRun || analyzerRunFinished}
                style={{ padding: "6px 12px", fontSize: "0.8rem", fontWeight: 700 }}
                title="Play analyzer run"
              >
                ▶ Play
              </button>
              <button
                className="btn btn-secondary"
                onClick={() => void onPauseRun?.()}
                disabled={runLoading || !isPlayingRun}
                style={{ padding: "6px 12px", fontSize: "0.8rem", fontWeight: 700 }}
                title="Pause analyzer run"
              >
                ⏸ Pause
              </button>
              <button
                className="btn btn-secondary"
                onClick={() => void onStepRun?.({ trade_eval_mode: analyzerTradeEvalMode })}
                disabled={runLoading || isPlayingRun || analyzerRunFinished}
                style={{ padding: "6px 12px", fontSize: "0.8rem", fontWeight: 700 }}
                title="Step one bar"
              >
                Step
              </button>
              <button
                className="btn btn-secondary"
                onClick={() => void handleClearAnalyzerRun()}
                disabled={runLoading}
                style={{ padding: "6px 12px", fontSize: "0.8rem", fontWeight: 700 }}
                title="Clear analyzer run"
              >
                Clear
              </button>
              {analyzerPlaybackProgress ? (
                <span style={{ fontSize: "0.78rem", color: "var(--text-muted)", display: "inline-flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                  {analyzerPlaybackProgress.isInitializing ? (
                    <span>
                      Initializing warmup {analyzerPlaybackProgress.warmupDone}/{analyzerPlaybackProgress.warmupTotal}
                    </span>
                  ) : analyzerPlaybackProgress.warmupTotal > 0 ? (
                    <span>
                      Warmup done {analyzerPlaybackProgress.warmupTotal}/{analyzerPlaybackProgress.warmupTotal}
                    </span>
                  ) : null}
                  <span>
                    Trade {analyzerPlaybackProgress.tradeDone}/{analyzerPlaybackProgress.tradeTotal} ({Number(analyzerPlaybackProgress.tradeProgressPct || 0).toFixed(1)}%)
                  </span>
                </span>
              ) : attachedRunState ? (
                <span style={{ fontSize: "0.78rem", color: "var(--text-muted)" }}>
                  {Number(attachedRunState.current_bar_index || 0)}/{Number(attachedRunState.total_bars || 0)} ({Number(attachedRunState.progress_pct || 0).toFixed(1)}%)
                </span>
              ) : null}
            </>
          ) : null}
        </div>
      </div>

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
          {/* ── Chart ──────────────────────────────────────────────── */}
          <div className="card chart-container" style={{ flex: 1, minHeight: 0, display: "flex", flexDirection: "column" }}>
            <div className="card-header" style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <span className="card-title">
                {bars.length > 0 ? `${ticker} - ${dateFrom} \u2192 ${dateTo}` : "Strategy Analyzer"}
              </span>
              <div className="chart-toolbar" style={{ display: "flex", gap: "0.5rem", alignItems: "center", flexWrap: "wrap" }}>
                {isAnalyzerAttachedRun && analyzerDisplayPhase ? (
                  <span className={`phase-badge ${String(analyzerDisplayPhase || "").toLowerCase()}`}>
                    {analyzerDisplayPhase}
                  </span>
                ) : null}
                {selectedRangeFrom && selectedRangeTo && (
                  <span style={{ fontSize: "0.8rem", color: "var(--accent-blue)", fontWeight: 600, display: "flex", alignItems: "center" }}>
                    {selectedRangeFrom.replace("T", " ")} &rarr; {selectedRangeTo.replace("T", " ")}
                  </span>
                )}
                <button
                  className={rangeSelectMode ? "btn btn-primary" : "btn btn-secondary"}
                  onClick={() => setRangeSelectMode(!rangeSelectMode)}
                  title={rangeSelectMode ? "Cancel range selection" : "Select range on chart"}
                  style={{ padding: "4px 14px", fontSize: "0.8rem", fontWeight: 600 }}
                >
                  {rangeSelectMode ? "Cancel Selection" : "Select Range"}
                </button>
              </div>
            </div>

            <div style={{ position: "relative", flex: 1, minHeight: 0 }}>
              {bars.length > 0 ? (
                <>
                  <CandlestickChart
                    ref={chartRef}
                    bars={chartBars}
                    markers={analyzerChartMarkers}
                    icebergs={[]}
                    onMarkerClick={onChartMarkerClick}
                    onBarClick={handleAnalyzerBarClick}
                    selectedMarker={selectedMarker}
                    chartState={analyzerChartState || selectedRangeWindow || null}
                    onChartStateChange={handleAnalyzerChartStateChange}
                  />
                  <ChartRangeSelector
                    enabled={rangeSelectMode}
                    chartRef={chartRef}
                    bars={bars}
                    onRangeSelected={handleRangeSelected}
                    onSelectionClear={handleClearRange}
                    selectedFrom={selectedRangeFrom}
                    selectedTo={selectedRangeTo}
                  />
                </>
              ) : (
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    height: "100%",
                    color: "var(--text-muted)",
                    fontSize: "0.9rem",
                  }}
                >
                  {loading ? "Loading bars..." : "Select a ticker and date range, then click Load Chart"}
                </div>
              )}
            </div>

            {rangeScrubMeta && Number(rangeScrubMeta.progressedPoints || 0) > 0 ? (
              <div
                style={{
                  borderTop: "1px solid var(--border-color)",
                  padding: "0.65rem 0.85rem 0.75rem",
                  display: "flex",
                  flexDirection: "column",
                  gap: "0.5rem",
                  background: "linear-gradient(180deg, color-mix(in srgb, var(--bg-card) 92%, var(--accent-blue) 8%), var(--bg-card))",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    gap: "0.75rem",
                    flexWrap: "wrap",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", flexWrap: "wrap" }}>
                    <span style={{ fontSize: "0.78rem", fontWeight: 700, color: "var(--text-secondary)" }}>
                      WF progress slider
                    </span>
                    <span style={{ fontSize: "0.76rem", color: "var(--text-muted)" }}>
                      {rangeScrubMeta.startLocal.replace("T", " ")} → {rangeScrubMeta.endLocal.replace("T", " ")}
                    </span>
                  </div>
                  <div style={{ display: "inline-flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                    <span style={{ fontSize: "0.76rem", color: "var(--text-muted)" }}>
                      {rangeScrubMeta.targetLocal
                        ? `${rangeScrubMeta.targetLocal.replace("T", " ")} (${Number(rangeScrubMeta.progressedPoints || 0) > 0 ? rangeScrubMeta.clampedOffset + 1 : 0}/${rangeScrubMeta.progressedPoints || 0} pts)`
                        : `${rangeScrubMeta.progressedPoints || 0}/${rangeScrubMeta.progressedPoints || 0} pts`}
                    </span>
                    <span style={{ fontSize: "0.76rem", color: "var(--text-muted)" }}>
                      Progress {Math.min(rangeScrubMeta.tradeTotalBars || 0, rangeScrubMeta.progressedBars)}/{rangeScrubMeta.tradeTotalBars || 0} ({Number(rangeScrubMeta.progressPct || 0).toFixed(1)}%)
                    </span>
                    {Number(rangeScrubMeta.estimatedPointsPerBar || 1) > 1 ? (
                      <span style={{ fontSize: "0.76rem", color: "var(--text-muted)" }}>
                        ~{Number(rangeScrubMeta.estimatedPointsPerBar || 1)} pts/bar
                      </span>
                    ) : null}
                    {Number(rangeScrubMeta.sliderStepSeconds || 0) > 0 &&
                    Number(rangeScrubMeta.sliderStepSeconds || 0) <= 6 ? (
                      <span style={{ fontSize: "0.76rem", color: "var(--text-muted)" }}>
                        Step ~{Number(rangeScrubMeta.sliderStepSeconds || 5).toFixed(0)}s
                      </span>
                    ) : null}
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={() => focusSelectedRangeOffset(rangeScrubMeta.progressedMaxOffset)}
                      disabled={rangeScrubMeta.clampedOffset >= rangeScrubMeta.progressedMaxOffset}
                      style={{ padding: "2px 8px", fontSize: "0.72rem", fontWeight: 700 }}
                      title="Jump slider to latest processed walking-forward bar"
                    >
                      Latest
                    </button>
                  </div>
                </div>

                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => moveSelectedRangeByStep(-1)}
                    disabled={rangeScrubMeta.clampedOffset <= 0}
                    style={{ padding: "4px 10px", fontSize: "0.78rem", fontWeight: 700 }}
                    title={`Previous executed ${Number(rangeScrubMeta.sliderStepSeconds || 0) > 0 ? `~${Number(rangeScrubMeta.sliderStepSeconds).toFixed(0)}s` : "bar"} in selected range`}
                  >
                    ◀
                  </button>
                  <input
                    type="range"
                    min={0}
                    max={rangeScrubMeta.fullMaxOffset}
                    step={Math.max(1, Math.trunc(Number(rangeScrubMeta.sliderStepBars) || 1))}
                    value={rangeScrubMeta.clampedOffset}
                    onChange={(e) => focusSelectedRangeOffset(Number(e.target.value))}
                    style={{
                      flex: 1,
                      minWidth: 120,
                      accentColor: "var(--accent-blue, #3b82f6)",
                      borderRadius: 999,
                      background: `linear-gradient(to right,
                        color-mix(in srgb, var(--accent-blue, #3b82f6) 88%, white 12%) 0%,
                        color-mix(in srgb, var(--accent-blue, #3b82f6) 88%, white 12%) ${Number(rangeScrubMeta.enabledTrackPct || 0).toFixed(2)}%,
                        color-mix(in srgb, var(--text-muted, #94a3b8) 24%, transparent) ${Number(rangeScrubMeta.enabledTrackPct || 0).toFixed(2)}%,
                        color-mix(in srgb, var(--text-muted, #94a3b8) 24%, transparent) 100%)`,
                    }}
                    aria-label="Navigate walking-forward progress in selected range"
                  />
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => moveSelectedRangeByStep(1)}
                    disabled={rangeScrubMeta.clampedOffset >= rangeScrubMeta.progressedMaxOffset}
                    style={{ padding: "4px 10px", fontSize: "0.78rem", fontWeight: 700 }}
                    title={`Next executed ${Number(rangeScrubMeta.sliderStepSeconds || 0) > 0 ? `~${Number(rangeScrubMeta.sliderStepSeconds).toFixed(0)}s` : "bar"} in selected range`}
                  >
                    ▶
                  </button>
                </div>
              </div>
            ) : null}
          </div>

          {/* ── Selected Range + Actions ───────────────────────────── */}
          <div className="card" style={{ padding: "0.75rem 1rem" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", flexWrap: "wrap" }}>
              <label style={{ fontWeight: 600, fontSize: "0.85rem", color: "var(--text-secondary)" }}>Test Range</label>

              <input
                type="datetime-local"
                value={selectedRangeFrom || ""}
                onChange={(e) => setSelectedRangeFrom(e.target.value)}
                step="60"
                style={{ padding: "4px 8px", borderRadius: "var(--radius-sm)", border: "1px solid var(--border-color)", background: "var(--bg-secondary)", color: "var(--text-primary)", fontSize: "0.85rem" }}
              />
              <span style={{ color: "var(--text-muted)" }}>&rarr;</span>
              <input
                type="datetime-local"
                value={selectedRangeTo || ""}
                onChange={(e) => setSelectedRangeTo(e.target.value)}
                step="60"
                style={{ padding: "4px 8px", borderRadius: "var(--radius-sm)", border: "1px solid var(--border-color)", background: "var(--bg-secondary)", color: "var(--text-primary)", fontSize: "0.85rem" }}
              />

              {selectedRangeFrom && selectedRangeTo && (
                <button
                  onClick={handleClearRange}
                  style={{ background: "none", border: "none", color: "var(--text-muted)", cursor: "pointer", fontSize: "0.8rem" }}
                >
                  clear
                </button>
              )}

              <div style={{ flex: 1 }} />

              <button
                className="btn"
                onClick={() => setShowStrategyEditor(true)}
                style={{ padding: "6px 16px", fontSize: "0.85rem", fontWeight: 600 }}
              >
                Edit Strategy
              </button>

              <button
                className="btn btn-primary"
                onClick={handleStartTest}
                disabled={!selectedRangeFrom || !selectedRangeTo || runLoading}
                style={{ padding: "6px 16px", fontSize: "0.85rem", fontWeight: 600 }}
              >
                {runLoading ? "Starting..." : "Start Test"}
              </button>
            </div>
          </div>
        </div>

        {isAnalyzerAttachedRun ? (
          <aside
            style={{
              flex: "0 0 380px",
              width: "380px",
              maxWidth: "100%",
              minHeight: 0,
              display: "flex",
              flexDirection: "column",
              gap: "0.75rem",
              overflow: "hidden",
            }}
          >
            {/* ── Strategy Conditions ── */}
            <div
              className="card"
              style={{
                flex: hasConditionsPanelData ? "1 1 0" : "0 0 auto",
                minHeight: hasConditionsPanelData ? 120 : 0,
                display: "flex",
                flexDirection: "column",
                overflow: "hidden",
                position: "relative",
              }}
            >
              <div className="card-header" style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <span className="card-title">Entry Conditions</span>
                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                  <span style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>
                    {conditionsPanelBadge ? (
                      <span
                        style={{
                          color:
                            conditionsPanelBadge.tone === "accent"
                              ? "var(--accent-blue, #3b82f6)"
                              : "var(--text-muted)",
                          fontWeight: conditionsPanelBadge.tone === "accent" ? 600 : 500,
                          fontSize: "0.78rem",
                        }}
                      >
                        {conditionsPanelBadge.label}
                      </span>
                    ) : null}
                  </span>
                  <button
                    type="button"
                    style={detachedToggleButtonStyle}
                    onClick={() => setIsConditionsDetached((previous) => !previous)}
                  >
                    {isConditionsDetached ? "Dock" : "Open window"}
                  </button>
                </div>
              </div>
              {isConditionsDetached ? (
                <div style={{ padding: "0.75rem 1rem", color: "var(--text-muted)", fontSize: "0.8rem" }}>
                  Opened in separate window.
                </div>
              ) : (
                entryConditionsContent
              )}
            </div>

            {/* ── Decision List ── */}
            <div
              className="card decision-panel"
              style={{
                flex: selectedMarker ? "1 1 0" : "1 1 0",
                minHeight: 120,
                display: "flex",
                flexDirection: "column",
                overflow: "hidden",
              }}
            >
              <div className="card-header" style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <span className="card-title">Decisions</span>
                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                  <span style={{ color: "var(--text-muted)", fontSize: "0.8rem" }}>
                    {analyzerDecisionEvents.length} total
                  </span>
                  <button
                    type="button"
                    style={detachedToggleButtonStyle}
                    onClick={() => setIsDecisionsDetached((previous) => !previous)}
                  >
                    {isDecisionsDetached ? "Dock" : "Open window"}
                  </button>
                </div>
              </div>
              {isDecisionsDetached ? (
                <div style={{ padding: "0.75rem 1rem", color: "var(--text-muted)", fontSize: "0.8rem" }}>
                  Opened in separate window.
                </div>
              ) : (
                decisionsContent
              )}
            </div>
          </aside>
        ) : null}
      </div>

      <ExternalWindowPortal
        isOpen={Boolean(isAnalyzerAttachedRun && isConditionsDetached)}
        title={`Entry Conditions - ${ticker}`}
        windowName="strategy-analyzer-conditions"
        width={560}
        height={780}
        onClose={() => setIsConditionsDetached(false)}
      >
        <div
          className="card"
          style={{
            margin: 0,
            borderRadius: 0,
            height: "100%",
            display: "flex",
            flexDirection: "column",
            overflow: "hidden",
            position: "relative",
          }}
        >
          <div className="card-header" style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <span className="card-title">Entry Conditions</span>
            <button type="button" style={detachedToggleButtonStyle} onClick={() => setIsConditionsDetached(false)}>
              Dock
            </button>
          </div>
          {entryConditionsContent}
        </div>
      </ExternalWindowPortal>

      <ExternalWindowPortal
        isOpen={Boolean(isAnalyzerAttachedRun && isDecisionsDetached)}
        title={`Decisions - ${ticker}`}
        windowName="strategy-analyzer-decisions"
        width={760}
        height={860}
        onClose={() => setIsDecisionsDetached(false)}
      >
        <div
          className="card decision-panel"
          style={{
            margin: 0,
            borderRadius: 0,
            height: "100%",
            display: "flex",
            flexDirection: "column",
            overflow: "hidden",
          }}
        >
          <div className="card-header" style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <span className="card-title">Decisions</span>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <span style={{ color: "var(--text-muted)", fontSize: "0.8rem" }}>
                {analyzerDecisionEvents.length} total
              </span>
              <button type="button" style={detachedToggleButtonStyle} onClick={() => setIsDecisionsDetached(false)}>
                Dock
              </button>
            </div>
          </div>
          {decisionsContent}
        </div>
      </ExternalWindowPortal>

      {/* ── Strategy Editor Modal ──────────────────────────────── */}
      {showStrategyEditor && (
        <StrategyEditorModal
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
