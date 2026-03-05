import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type {
  StrategyAnalyzerChartWindow,
  StrategyAnalyzerPreviewBar,
  StrategyAnalyzerRangePlaybackMeta,
} from "./types";
import { unixSecondsToDateTimeLocal } from "./utils";

type Params = {
  bars: StrategyAnalyzerPreviewBar[];
  selectedRangeFrom: string | null;
  selectedRangeTo: string | null;
  warmupBars: number;
};

const CHART_STATE_UPDATE_THROTTLE_MS = 120;

export function useStrategyAnalyzerRangePlayback({
  bars,
  selectedRangeFrom,
  selectedRangeTo,
  warmupBars,
}: Params) {
  const [analyzerChartState, setAnalyzerChartState] = useState<StrategyAnalyzerChartWindow | null>(null);
  const pendingChartStateRef = useRef<StrategyAnalyzerChartWindow | null>(null);
  const flushTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const applyChartState = useCallback((nextState: StrategyAnalyzerChartWindow | null) => {
    if (!nextState) return;
    const from = Number(nextState.from);
    const to = Number(nextState.to);
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

  const scheduleChartStateApply = useCallback((nextState: StrategyAnalyzerChartWindow | null) => {
    if (!nextState) return;
    pendingChartStateRef.current = nextState;
    if (flushTimerRef.current) return;
    flushTimerRef.current = setTimeout(() => {
      flushTimerRef.current = null;
      const pending = pendingChartStateRef.current;
      pendingChartStateRef.current = null;
      applyChartState(pending);
    }, CHART_STATE_UPDATE_THROTTLE_MS);
  }, [applyChartState]);

  const rangePlaybackMeta = useMemo<StrategyAnalyzerRangePlaybackMeta>(() => {
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
      const firstIdx = previewBars.findIndex((bar: StrategyAnalyzerPreviewBar) => {
        const t = Number(bar?.time);
        return Number.isFinite(t) && t >= rangeMin - 1;
      });
      const lastIdx = [...previewBars]
        .map((bar: StrategyAnalyzerPreviewBar, idx: number) => ({ idx, t: Number(bar?.time) }))
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

  const selectedRangeWindow: StrategyAnalyzerChartWindow | null = rangePlaybackMeta
    ? { from: rangePlaybackMeta.tradeStartTs, to: rangePlaybackMeta.tradeEndTs }
    : null;

  useEffect(() => {
    if (flushTimerRef.current) {
      clearTimeout(flushTimerRef.current);
      flushTimerRef.current = null;
    }
    pendingChartStateRef.current = null;

    if (!selectedRangeWindow) {
      setAnalyzerChartState(null);
      return;
    }
    applyChartState(selectedRangeWindow);
  }, [selectedRangeWindow?.from, selectedRangeWindow?.to, applyChartState]);

  const handleAnalyzerChartStateChange = useCallback((nextRange: StrategyAnalyzerChartWindow | null) => {
    if (!nextRange) return;
    const from = Number(nextRange.from);
    const to = Number(nextRange.to);
    if (!Number.isFinite(from) || !Number.isFinite(to)) return;
    scheduleChartStateApply({ from, to });
  }, [scheduleChartStateApply]);

  useEffect(() => {
    return () => {
      if (flushTimerRef.current) {
        clearTimeout(flushTimerRef.current);
        flushTimerRef.current = null;
      }
      pendingChartStateRef.current = null;
    };
  }, []);

  return {
    analyzerChartState,
    rangePlaybackMeta,
    selectedRangeWindow,
    handleAnalyzerChartStateChange,
  };
}
