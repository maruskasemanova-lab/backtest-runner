import { renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { useStrategyAnalyzerChartData } from "./useStrategyAnalyzerChartData";
import type {
  StrategyAnalyzerChartBarLike,
  StrategyAnalyzerTimelineCacheRef,
} from "./types";

const buildPreviewBar = (time: number): StrategyAnalyzerChartBarLike => ({
  time,
  open: 100,
  high: 101,
  low: 99,
  close: 100,
  volume: 1_000,
});

const buildTimelineCacheRef = (
  runBarsByTime: Map<number, StrategyAnalyzerChartBarLike>,
): StrategyAnalyzerTimelineCacheRef =>
  ({
    current: {
      processedRunBarCount: runBarsByTime.size,
      runBarsByTime: runBarsByTime as Map<number, any>,
      progressedTradeBars: [],
      timelinePoints: [],
      observedCheckpointCounts: [],
      warmupDone: 0,
      tradeDone: 0,
      startTime: null,
      endTime: null,
      rangeKey: "test",
    },
  }) as StrategyAnalyzerTimelineCacheRef;

describe("useStrategyAnalyzerChartData", () => {
  it("keeps placeholders for missing bars while run is still active", () => {
    const previewBars = [buildPreviewBar(100), buildPreviewBar(160), buildPreviewBar(220)];
    const timelineCacheRef = buildTimelineCacheRef(
      new Map([[160, { ...buildPreviewBar(160), bar_index: 1 }]]),
    );

    const { result } = renderHook(() =>
      useStrategyAnalyzerChartData({
        bars: previewBars,
        attachedRunBars: [],
        isAnalyzerAttachedRun: true,
        analyzerRunTerminal: false,
        selectedRangeWindow: { from: 100, to: 220 },
        rangeScrubMeta: null,
        analyzerDecisionEvents: [],
        timelineCacheVersion: 1,
        timelineCacheRef,
      }),
    );

    expect(result.current.chartBars[0]?.__wfPlaceholder).toBe(true);
    expect(result.current.chartBars[1]?.bar_index).toBe(1);
    expect(result.current.chartBars[2]?.__wfPlaceholder).toBe(true);
  });

  it("falls back to preview bars after run reaches terminal state", () => {
    const previewBars = [buildPreviewBar(100), buildPreviewBar(160), buildPreviewBar(220)];
    const timelineCacheRef = buildTimelineCacheRef(
      new Map([[160, { ...buildPreviewBar(160), bar_index: 1 }]]),
    );

    const { result } = renderHook(() =>
      useStrategyAnalyzerChartData({
        bars: previewBars,
        attachedRunBars: [],
        isAnalyzerAttachedRun: true,
        analyzerRunTerminal: true,
        selectedRangeWindow: { from: 100, to: 220 },
        rangeScrubMeta: null,
        analyzerDecisionEvents: [],
        timelineCacheVersion: 1,
        timelineCacheRef,
      }),
    );

    expect(result.current.chartBars[0]?.__wfPlaceholder).toBeUndefined();
    expect(result.current.chartBars[0]?.open).toBe(100);
    expect(result.current.chartBars[1]?.bar_index).toBe(1);
    expect(result.current.chartBars[2]?.__wfPlaceholder).toBeUndefined();
  });

  it("uses attached run bars when preview bars are missing", () => {
    const attachedRunBars = [buildPreviewBar(100), buildPreviewBar(160), buildPreviewBar(220)];
    const timelineCacheRef = buildTimelineCacheRef(new Map());

    const { result } = renderHook(() =>
      useStrategyAnalyzerChartData({
        bars: [],
        attachedRunBars,
        isAnalyzerAttachedRun: true,
        analyzerRunTerminal: false,
        selectedRangeWindow: { from: 100, to: 220 },
        rangeScrubMeta: null,
        analyzerDecisionEvents: [],
        timelineCacheVersion: 1,
        timelineCacheRef,
      }),
    );

    expect(result.current.chartBars).toHaveLength(3);
    expect(result.current.chartBars[0]?.time).toBe(100);
    expect(result.current.chartBars[2]?.time).toBe(220);
  });

  it("filters attached run bars to selected range when preview bars are missing", () => {
    const attachedRunBars = [
      buildPreviewBar(40),
      buildPreviewBar(100),
      buildPreviewBar(160),
      buildPreviewBar(220),
      buildPreviewBar(280),
    ];
    const timelineCacheRef = buildTimelineCacheRef(new Map());

    const { result } = renderHook(() =>
      useStrategyAnalyzerChartData({
        bars: [],
        attachedRunBars,
        isAnalyzerAttachedRun: true,
        analyzerRunTerminal: false,
        selectedRangeWindow: { from: 100, to: 220 },
        rangeScrubMeta: null,
        analyzerDecisionEvents: [],
        timelineCacheVersion: 1,
        timelineCacheRef,
      }),
    );

    expect(result.current.chartBars.map((bar) => Number(bar?.time))).toEqual([100, 160, 220]);
  });
});
