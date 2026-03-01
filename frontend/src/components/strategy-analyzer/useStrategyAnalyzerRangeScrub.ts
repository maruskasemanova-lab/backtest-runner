import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  type Dispatch,
  type SetStateAction,
} from "react";
import type {
  StrategyAnalyzerRangePlaybackMeta,
  StrategyAnalyzerRangeScrubBase,
  StrategyAnalyzerRangeScrubMeta,
  StrategyAnalyzerTimelineCacheRef,
} from "./types";
import { unixSecondsToDateTimeLocal, unixSecondsToLabel } from "./utils";

type Params = {
  isAnalyzerAttachedRun: boolean;
  isPlayingRun: boolean;
  rangePlaybackMeta: StrategyAnalyzerRangePlaybackMeta;
  timelineCacheVersion: number;
  timelineCacheRef: StrategyAnalyzerTimelineCacheRef;
  rangeScrubOffset: number;
  setRangeScrubOffset: Dispatch<SetStateAction<number>>;
};

export function useStrategyAnalyzerRangeScrub({
  isAnalyzerAttachedRun,
  isPlayingRun,
  rangePlaybackMeta,
  timelineCacheVersion,
  timelineCacheRef,
  rangeScrubOffset,
  setRangeScrubOffset,
}: Params) {
  // Split into two useMemo calls to break the circular dependency:
  // rangeScrubBase does NOT depend on rangeScrubOffset -> no re-render loop.
  // rangeScrubMeta merges base + offset-derived values.
  const rangeScrubBase = useMemo<StrategyAnalyzerRangeScrubBase | null>(() => {
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
      Number.isFinite(medianSpacingSec) &&
      (medianSpacingSec as number) > 0 &&
      (medianSpacingSec as number) < 5
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
  }, [isAnalyzerAttachedRun, rangePlaybackMeta, timelineCacheVersion, timelineCacheRef]);

  // Offset-dependent values: depends on rangeScrubOffset but does NOT
  // trigger any useEffect that sets rangeScrubOffset -> no loop.
  const rangeScrubMeta = useMemo<StrategyAnalyzerRangeScrubMeta>(() => {
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
  // Depends on primitives from rangeScrubBase -> no object-identity loop.
  const progressedMaxOffset = rangeScrubBase?.progressedMaxOffset ?? 0;
  const previousProgressedMaxOffsetRef = useRef(0);
  const hasObservedProgressedMaxRef = useRef(false);

  // Keep tail-follow behavior even when playback has just stopped:
  // if user was already on the previous end and new bars arrive late
  // (poll sync after is_running=false), advance to the new end.
  useEffect(() => {
    if (!rangeScrubBase) {
      previousProgressedMaxOffsetRef.current = 0;
      hasObservedProgressedMaxRef.current = false;
      return;
    }
    const previousMax = previousProgressedMaxOffsetRef.current;
    if (!hasObservedProgressedMaxRef.current) {
      hasObservedProgressedMaxRef.current = true;
      previousProgressedMaxOffsetRef.current = progressedMaxOffset;
      return;
    }
    previousProgressedMaxOffsetRef.current = progressedMaxOffset;
    if (progressedMaxOffset <= previousMax) return;

    setRangeScrubOffset((prev) => {
      const prevClamped = Math.max(0, Math.min(prev, previousMax));
      const wasFollowingTail = prevClamped >= Math.max(0, previousMax - 1);
      if (!wasFollowingTail) return prev;
      return progressedMaxOffset;
    });
  }, [rangeScrubBase, progressedMaxOffset, setRangeScrubOffset]);

  useEffect(() => {
    if (!rangeScrubBase) {
      setRangeScrubOffset(0);
      return;
    }
    setRangeScrubOffset((prev) => {
      const clamped = Math.max(0, Math.min(prev, progressedMaxOffset));
      return clamped === prev ? prev : clamped;
    });
  }, [rangeScrubBase, progressedMaxOffset, setRangeScrubOffset]);

  // Auto-follow latest bar during playback.
  useEffect(() => {
    if (!isAnalyzerAttachedRun || !isPlayingRun || !rangeScrubBase) return;
    if (rangeScrubBase.progressedBars <= 0) return;
    setRangeScrubOffset((prev) => (prev === progressedMaxOffset ? prev : progressedMaxOffset));
  }, [
    isAnalyzerAttachedRun,
    isPlayingRun,
    progressedMaxOffset,
    rangeScrubBase,
    setRangeScrubOffset,
  ]);

  const focusSelectedRangeOffset = useCallback(
    (nextOffset: number) => {
      if (!rangeScrubMeta) return;
      const clampedOffset = Math.max(
        0,
        Math.min(Math.trunc(nextOffset), rangeScrubMeta.progressedMaxOffset)
      );
      setRangeScrubOffset(clampedOffset);
    },
    [rangeScrubMeta, setRangeScrubOffset]
  );

  const moveSelectedRangeByStep = useCallback(
    (direction: -1 | 1) => {
      if (!rangeScrubMeta) return;
      const stepBars = Math.max(1, Math.trunc(Number(rangeScrubMeta.sliderStepBars) || 1));
      focusSelectedRangeOffset(rangeScrubMeta.clampedOffset + direction * stepBars);
    },
    [focusSelectedRangeOffset, rangeScrubMeta]
  );

  return {
    rangeScrubBase,
    rangeScrubMeta,
    focusSelectedRangeOffset,
    moveSelectedRangeByStep,
  };
}
