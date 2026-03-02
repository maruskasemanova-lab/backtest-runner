import { useMemo } from "react";
import type {
  StrategyAnalyzerAttachedRunState,
  StrategyAnalyzerPlaybackProgress,
  StrategyAnalyzerRangePlaybackMeta,
  StrategyAnalyzerTimelineCacheRef,
} from "./types";

const TERMINAL_RUN_PHASES = new Set([
  "COMPLETED",
  "END_OF_DAY",
  "ERROR",
  "FAILED",
  "STOPPED",
]);

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
    const cacheWarmupDone = Number(cache.warmupDone || 0);
    const cacheTradeDone = Number(cache.tradeDone || 0);

    const backendTotalBars = Number(attachedRunState?.total_bars || 0);
    const backendProcessedRaw = Number(attachedRunState?.current_bar_index || 0);
    const backendProcessed = Number.isFinite(backendProcessedRaw)
      ? Math.max(0, Math.trunc(backendProcessedRaw))
      : 0;
    const estimatedWarmup = Number(rangePlaybackMeta.warmupTotalBars || 0);

    const warmupTotal =
      backendTotalBars > 0 ? Math.min(estimatedWarmup, backendTotalBars) : estimatedWarmup;
    const tradeTotal =
      backendTotalBars > 0
        ? Math.max(0, backendTotalBars - warmupTotal)
        : Number(rangePlaybackMeta.tradeTotalBars || 0);

    const backendWarmupDone = warmupTotal > 0 ? Math.min(warmupTotal, backendProcessed) : 0;
    const backendTradeDone = Math.max(0, backendProcessed - warmupTotal);

    const observedWarmupDone = Math.max(cacheWarmupDone, backendWarmupDone);
    const observedTradeDone = Math.max(cacheTradeDone, backendTradeDone);

    const warmupClamped = warmupTotal > 0 ? Math.min(warmupTotal, observedWarmupDone) : 0;
    const tradeClamped = tradeTotal > 0 ? Math.min(tradeTotal, observedTradeDone) : observedTradeDone;

    const runPhase = String(attachedRunState?.phase || "").trim().toUpperCase();
    const isTerminalRunState =
      !Boolean(attachedRunState?.is_running) && TERMINAL_RUN_PHASES.has(runPhase);
    const isInitializing =
      !isTerminalRunState && warmupTotal > 0 && warmupClamped < warmupTotal;
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
