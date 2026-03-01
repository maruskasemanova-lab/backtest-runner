import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { useMemo, useRef, useState } from "react";

import { useStrategyAnalyzerRangeScrub } from "./useStrategyAnalyzerRangeScrub";
import type {
  StrategyAnalyzerRangePlaybackMeta,
  StrategyAnalyzerRunBarLike,
  StrategyAnalyzerTimelineCacheState,
} from "./types";

const BASE_TIME = 1_707_000_000;
const INITIAL_POINTS = 10;

const createRunBar = (barIndex: number, time: number): StrategyAnalyzerRunBarLike => ({
  bar_index: barIndex,
  time,
  open: 100 + barIndex,
  high: 101 + barIndex,
  low: 99 + barIndex,
  close: 100 + barIndex,
  volume: 1_000 + barIndex,
});

const createTimelineCacheState = (points: number): StrategyAnalyzerTimelineCacheState => {
  const runBarsByTime = new Map<number, StrategyAnalyzerRunBarLike>();
  const progressedTradeBars: StrategyAnalyzerRunBarLike[] = [];
  const timelinePoints = [];
  for (let index = 0; index < points; index += 1) {
    const time = BASE_TIME + index * 60;
    const runBar = createRunBar(index, time);
    runBarsByTime.set(time, runBar);
    progressedTradeBars.push(runBar);
    timelinePoints.push({
      kind: "bar",
      time,
      barTime: time,
      checkpoint: null,
      checkpointIndex: 0,
      runBar,
    });
  }

  return {
    processedRunBarCount: progressedTradeBars.length,
    runBarsByTime,
    progressedTradeBars,
    timelinePoints,
    observedCheckpointCounts: [1],
    warmupDone: 40,
    tradeDone: progressedTradeBars.length,
    startTime: BASE_TIME,
    endTime: BASE_TIME + (points - 1) * 60,
    rangeKey: "MU:2026-02-13",
  };
};

function useRangeScrubHarness() {
  const timelineCacheRef = useRef<StrategyAnalyzerTimelineCacheState>(
    createTimelineCacheState(INITIAL_POINTS),
  );
  const [timelineCacheVersion, setTimelineCacheVersion] = useState(1);
  const [rangeScrubOffset, setRangeScrubOffset] = useState(0);
  const rangePlaybackMeta = useMemo<StrategyAnalyzerRangePlaybackMeta>(
    () => ({
      rawFromSec: BASE_TIME,
      rawToSec: BASE_TIME + 24 * 60 * 60,
      tradeStartTs: BASE_TIME + 40 * 60,
      tradeEndTs: BASE_TIME + 24 * 60 * 60,
      warmupStartTs: BASE_TIME,
      tradeStartIdx: 40,
      tradeEndIdx: 463,
      warmupStartIdx: 0,
      tradeStartLocal: "09:30",
      tradeEndLocal: "16:00",
      warmupStartLocal: "08:50",
      tradeTotalBars: 424,
      warmupTotalBars: 40,
    }),
    [],
  );

  const hook = useStrategyAnalyzerRangeScrub({
    isAnalyzerAttachedRun: true,
    isPlayingRun: false,
    rangePlaybackMeta,
    timelineCacheVersion,
    timelineCacheRef,
    rangeScrubOffset,
    setRangeScrubOffset,
  });

  const appendTradeBars = (count: number) => {
    const cache = timelineCacheRef.current;
    for (let idx = 0; idx < count; idx += 1) {
      const nextBarIndex = cache.progressedTradeBars.length;
      const nextTime = BASE_TIME + nextBarIndex * 60;
      const runBar = createRunBar(nextBarIndex, nextTime);
      cache.progressedTradeBars.push(runBar);
      cache.runBarsByTime.set(nextTime, runBar);
      cache.timelinePoints.push({
        kind: "bar",
        time: nextTime,
        barTime: nextTime,
        checkpoint: null,
        checkpointIndex: 0,
        runBar,
      });
    }
    cache.processedRunBarCount = cache.progressedTradeBars.length;
    cache.tradeDone = cache.progressedTradeBars.length;
    cache.endTime = Number(cache.timelinePoints[cache.timelinePoints.length - 1]?.time) || null;
    setTimelineCacheVersion((prev) => prev + 1);
  };

  return {
    ...hook,
    rangeScrubOffset,
    setRangeScrubOffset,
    appendTradeBars,
  };
}

describe("useStrategyAnalyzerRangeScrub", () => {
  it("keeps following the tail when late bars arrive after playback stops", async () => {
    const { result } = renderHook(() => useRangeScrubHarness());

    await waitFor(() => {
      expect(result.current.rangeScrubMeta?.progressedMaxOffset).toBe(9);
    });
    await waitFor(() => {
      expect(result.current.rangeScrubOffset).toBe(0);
    });

    act(() => {
      result.current.setRangeScrubOffset(9);
    });

    await waitFor(() => {
      expect(result.current.rangeScrubOffset).toBe(9);
    });

    act(() => {
      result.current.appendTradeBars(2);
    });

    await waitFor(() => {
      expect(result.current.rangeScrubMeta?.progressedMaxOffset).toBe(11);
    });
    await waitFor(() => {
      expect(result.current.rangeScrubOffset).toBe(11);
    });
  });

  it("does not force jump when user scrubbed away from tail", async () => {
    const { result } = renderHook(() => useRangeScrubHarness());

    await waitFor(() => {
      expect(result.current.rangeScrubOffset).toBe(0);
    });

    act(() => {
      result.current.setRangeScrubOffset(3);
    });

    await waitFor(() => {
      expect(result.current.rangeScrubOffset).toBe(3);
    });

    act(() => {
      result.current.appendTradeBars(2);
    });

    await waitFor(() => {
      expect(result.current.rangeScrubMeta?.progressedMaxOffset).toBe(11);
    });
    await waitFor(() => {
      expect(result.current.rangeScrubOffset).toBe(3);
    });
  });
});
