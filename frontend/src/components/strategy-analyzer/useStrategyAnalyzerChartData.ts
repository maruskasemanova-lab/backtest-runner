import { useMemo } from "react";
import { toUnixSeconds } from "../../utils";
import type {
  StrategyAnalyzerChartBarLike,
  StrategyAnalyzerChartWindow,
  StrategyAnalyzerDecisionMarker,
  StrategyAnalyzerRangeScrubMeta,
  StrategyAnalyzerTimelineCacheRef,
} from "./types";

type Params = {
  bars: StrategyAnalyzerChartBarLike[];
  isAnalyzerAttachedRun: boolean;
  analyzerRunFinished: boolean;
  selectedRangeWindow: StrategyAnalyzerChartWindow | null;
  rangeScrubMeta: StrategyAnalyzerRangeScrubMeta;
  analyzerDecisionEvents: StrategyAnalyzerDecisionMarker[];
  timelineCacheVersion: number;
  timelineCacheRef: StrategyAnalyzerTimelineCacheRef;
};

export function useStrategyAnalyzerChartData({
  bars,
  isAnalyzerAttachedRun,
  analyzerRunFinished,
  selectedRangeWindow,
  rangeScrubMeta,
  analyzerDecisionEvents,
  timelineCacheVersion,
  timelineCacheRef,
}: Params) {
  const analyzerChartMarkers = useMemo<StrategyAnalyzerDecisionMarker[]>(() => {
    const sourceMarkers = Array.isArray(analyzerDecisionEvents) ? analyzerDecisionEvents : [];
    if (!sourceMarkers.length) return [];

    const minTime = Number(selectedRangeWindow?.from);
    const maxTime = Number(selectedRangeWindow?.to);
    const scrubCutoffTime = Number(rangeScrubMeta?.targetTime);
    const hasScrubCutoff = Number.isFinite(scrubCutoffTime);
    const scrubCutoffBarIndex = Number(rangeScrubMeta?.targetBar?.bar_index);
    const dedupeKeys = new Set<string>();

    return sourceMarkers.filter((marker: StrategyAnalyzerDecisionMarker) => {
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

  // Uses cached runBarsByTime Map from timeline cache.
  const chartBars = useMemo<StrategyAnalyzerChartBarLike[]>(() => {
    const previewBars = Array.isArray(bars) ? bars : [];
    if (!previewBars.length) return previewBars;
    if (!isAnalyzerAttachedRun || !selectedRangeWindow) return previewBars;

    const minTime = selectedRangeWindow.from - 1;
    const maxTime = selectedRangeWindow.to + 1;
    const scrubCutoffTime = Number(rangeScrubMeta?.targetTime);
    const hasScrubCutoff = Number.isFinite(scrubCutoffTime);
    const runBarsByTime = timelineCacheRef.current.runBarsByTime;

    let touchedSegment = false;
    const composedBars = previewBars.map((previewBar: StrategyAnalyzerChartBarLike) => {
      const t = Number(previewBar?.time);
      if (!Number.isFinite(t) || t < minTime || t > maxTime) return previewBar;
      touchedSegment = true;
      if (hasScrubCutoff && t > scrubCutoffTime + 1) {
        return { time: t, __wfPlaceholder: true };
      }
      const runBar = runBarsByTime.get(t);
      if (runBar) return runBar;
      // After run completes, bars not emitted via WS throttle should fall
      // back to the preview bar (same OHLCV) instead of an empty placeholder.
      if (analyzerRunFinished) return previewBar;
      return { time: t, __wfPlaceholder: true };
    });
    return touchedSegment ? composedBars : previewBars;
  }, [
    bars,
    isAnalyzerAttachedRun,
    analyzerRunFinished,
    selectedRangeWindow,
    timelineCacheVersion,
    rangeScrubMeta,
    timelineCacheRef,
  ]);

  return {
    analyzerChartMarkers,
    chartBars,
  };
}
