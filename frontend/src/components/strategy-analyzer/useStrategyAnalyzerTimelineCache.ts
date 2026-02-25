import { useEffect, useMemo } from "react";
import { toUnixSeconds } from "../../utils";
import type {
  StrategyAnalyzerAnyObject,
  StrategyAnalyzerRangePlaybackMeta,
  StrategyAnalyzerRangeScrubTimelinePoint,
  StrategyAnalyzerRunBarLike,
  StrategyAnalyzerTimelineCacheRef,
} from "./types";

type Params = {
  isAnalyzerAttachedRun: boolean;
  rangePlaybackMeta: StrategyAnalyzerRangePlaybackMeta;
  analyzerRunKey: string | null;
  attachedRunBars: StrategyAnalyzerRunBarLike[];
  timelineCacheRef: StrategyAnalyzerTimelineCacheRef;
};

export function useStrategyAnalyzerTimelineCache({
  isAnalyzerAttachedRun,
  rangePlaybackMeta,
  analyzerRunKey,
  attachedRunBars,
  timelineCacheRef,
}: Params) {
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
  }, [rangeKey, timelineCacheRef]);

  const timelineCacheVersion = useMemo(() => {
    if (!isAnalyzerAttachedRun || !rangePlaybackMeta) return 0;
    const startTime = Number(rangePlaybackMeta.tradeStartTs);
    const endTime = Number(rangePlaybackMeta.tradeEndTs);
    if (!Number.isFinite(startTime) || !Number.isFinite(endTime)) return 0;

    const cache = timelineCacheRef.current;
    const runBars = Array.isArray(attachedRunBars) ? attachedRunBars : [];
    const prevCount = cache.processedRunBarCount;

    if (runBars.length > prevCount) {
      cache.startTime = startTime;
      cache.endTime = endTime;

      for (let i = prevCount; i < runBars.length; i += 1) {
        const runBar = runBars[i];
        const t = Number(runBar?.time);
        if (!Number.isFinite(t)) continue;

        if (runBar?.warmup_only === true) {
          cache.warmupDone += 1;
        } else {
          cache.tradeDone += 1;
        }

        if (t < startTime - 1 || t > endTime + 1) continue;
        cache.runBarsByTime.set(t, runBar);
        cache.progressedTradeBars.push(runBar);

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
        const checkpoints = Array.isArray(trace?.checkpoints)
          ? (trace.checkpoints as StrategyAnalyzerAnyObject[])
          : [];
        const normalizedCheckpoints: StrategyAnalyzerRangeScrubTimelinePoint[] = checkpoints
          .map((checkpoint: StrategyAnalyzerAnyObject, checkpointIndex: number) => {
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
          .filter(
            (point): point is StrategyAnalyzerRangeScrubTimelinePoint => Boolean(point)
          )
          .sort((left, right) => Number(left.time || 0) - Number(right.time || 0));

        if (normalizedCheckpoints.length > 0) {
          cache.observedCheckpointCounts.push(normalizedCheckpoints.length);
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

    return cache.processedRunBarCount;
  }, [isAnalyzerAttachedRun, rangePlaybackMeta, attachedRunBars, timelineCacheRef]);

  return {
    timelineCacheVersion,
  };
}
