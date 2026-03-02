import { renderHook } from "@testing-library/react";
import { useRef } from "react";
import { describe, expect, it } from "vitest";

import { useStrategyAnalyzerPlaybackProgress } from "./useStrategyAnalyzerPlaybackProgress";
import type {
  StrategyAnalyzerRangePlaybackMeta,
  StrategyAnalyzerTimelineCacheState,
} from "./types";

const BASE_META: StrategyAnalyzerRangePlaybackMeta = {
  rawFromSec: 1_706_600_000,
  rawToSec: 1_706_700_000,
  tradeStartTs: 1_706_601_000,
  tradeEndTs: 1_706_699_000,
  warmupStartTs: 1_706_600_000,
  tradeStartIdx: 40,
  tradeEndIdx: 487,
  warmupStartIdx: 0,
  tradeStartLocal: "2026-02-26T14:34",
  tradeEndLocal: "2026-02-27T09:04",
  warmupStartLocal: "2026-02-26T13:54",
  tradeTotalBars: 448,
  warmupTotalBars: 40,
};

const createEmptyTimelineCache = (): StrategyAnalyzerTimelineCacheState => ({
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

describe("useStrategyAnalyzerPlaybackProgress", () => {
  it("falls back to backend current_bar_index when timeline cache is empty", () => {
    const { result } = renderHook(() => {
      const timelineCacheRef = useRef<StrategyAnalyzerTimelineCacheState>(
        createEmptyTimelineCache(),
      );
      return useStrategyAnalyzerPlaybackProgress({
        isAnalyzerAttachedRun: true,
        rangePlaybackMeta: BASE_META,
        timelineCacheVersion: 0,
        attachedRunState: {
          is_running: true,
          phase: "PRE_MARKET",
          current_bar_index: 57,
          total_bars: 488,
        },
        timelineCacheRef,
      });
    });

    expect(result.current.analyzerPlaybackProgress).not.toBeNull();
    expect(result.current.analyzerPlaybackProgress?.warmupDone).toBe(40);
    expect(result.current.analyzerPlaybackProgress?.warmupTotal).toBe(40);
    expect(result.current.analyzerPlaybackProgress?.tradeDone).toBe(17);
    expect(result.current.analyzerPlaybackProgress?.tradeTotal).toBe(448);
    expect(result.current.analyzerPlaybackProgress?.isInitializing).toBe(false);
  });

  it("does not display warmup-initializing for terminal ERROR runs", () => {
    const { result } = renderHook(() => {
      const timelineCacheRef = useRef<StrategyAnalyzerTimelineCacheState>(
        createEmptyTimelineCache(),
      );
      return useStrategyAnalyzerPlaybackProgress({
        isAnalyzerAttachedRun: true,
        rangePlaybackMeta: BASE_META,
        timelineCacheVersion: 0,
        attachedRunState: {
          is_running: false,
          phase: "ERROR",
          current_bar_index: 0,
          total_bars: 488,
        },
        timelineCacheRef,
      });
    });

    expect(result.current.analyzerPlaybackProgress).not.toBeNull();
    expect(result.current.analyzerPlaybackProgress?.isInitializing).toBe(false);
    expect(result.current.analyzerPlaybackProgress?.warmupDone).toBe(0);
    expect(result.current.analyzerPlaybackProgress?.tradeDone).toBe(0);
  });
});
