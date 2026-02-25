import { useMemo } from "react";
import type {
  StrategyAnalyzerAttachedRunState,
  StrategyAnalyzerPlaybackProgress,
  StrategyAnalyzerRangePlaybackMeta,
  StrategyAnalyzerTimelineCacheRef,
} from "./types";

type Params = {
  isAnalyzerAttachedRun: boolean;
  rangePlaybackMeta: StrategyAnalyzerRangePlaybackMeta;
  timelineCacheVersion: number;
  attachedRunState: StrategyAnalyzerAttachedRunState | null | undefined;
  timelineCacheRef: StrategyAnalyzerTimelineCacheRef;
};

export function useStrategyAnalyzerPlaybackProgress({
  isAnalyzerAttachedRun,
  rangePlaybackMeta,
  timelineCacheVersion,
  attachedRunState,
  timelineCacheRef,
}: Params) {
  const analyzerPlaybackProgress = useMemo<StrategyAnalyzerPlaybackProgress>(() => {
    if (!isAnalyzerAttachedRun || !rangePlaybackMeta) return null;

    const cache = timelineCacheRef.current;
    const warmupDone = cache.warmupDone;
    const tradeDone = cache.tradeDone;

    const backendTotalBars = Number(attachedRunState?.total_bars || 0);
    const estimatedWarmup = Number(rangePlaybackMeta.warmupTotalBars || 0);

    const warmupTotal =
      backendTotalBars > 0 ? Math.min(estimatedWarmup, backendTotalBars) : estimatedWarmup;
    const tradeTotal =
      backendTotalBars > 0
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
  }, [isAnalyzerAttachedRun, rangePlaybackMeta, timelineCacheVersion, attachedRunState, timelineCacheRef]);

  return { analyzerPlaybackProgress };
}
