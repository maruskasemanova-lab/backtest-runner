import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import StrategyAnalyzerScrubSlider from "./StrategyAnalyzerScrubSlider";
import type { StrategyAnalyzerRangeScrubMeta } from "./types";

const buildTimeline = (bars: number, checkpointsPerBar = 1) => {
  const progressedTradeBars = [];
  const timelinePoints = [];
  const start = 1_707_000_000;

  for (let barOffset = 0; barOffset < bars; barOffset += 1) {
    const barTime = start + barOffset * 60;
    const runBar = {
      bar_index: barOffset,
      time: barTime,
      open: 100 + barOffset,
      high: 101 + barOffset,
      low: 99 + barOffset,
      close: 100 + barOffset,
      volume: 1_000 + barOffset,
    };
    progressedTradeBars.push(runBar);
    for (let checkpointIdx = 0; checkpointIdx < checkpointsPerBar; checkpointIdx += 1) {
      timelinePoints.push({
        kind: "checkpoint",
        time: barTime + checkpointIdx,
        barTime,
        checkpoint: { checkpointIdx },
        checkpointIndex: checkpointIdx,
        runBar,
      });
    }
  }

  return { progressedTradeBars, timelinePoints };
};

const buildRangeScrubMeta = (
  overrides: Partial<NonNullable<StrategyAnalyzerRangeScrubMeta>> = {},
): NonNullable<StrategyAnalyzerRangeScrubMeta> => ({
  ...(() => {
    const { progressedTradeBars, timelinePoints } = buildTimeline(10, 2);
    return {
      progressedTradeBars,
      timelinePoints,
      progressedBars: progressedTradeBars.length,
      progressedPoints: timelinePoints.length,
      progressedMaxOffset: timelinePoints.length - 1,
    };
  })(),
  tradeStartIdx: 0,
  tradeEndIdx: 19,
  startTime: 1_707_000_000,
  endTime: 1_707_001_140,
  tradeTotalBars: 20,
  progressPct: 50,
  fullMaxOffset: 19,
  progressedMaxOffset: 19,
  enabledTrackPct: 50,
  estimatedPointsPerBar: 2,
  sliderStepBars: 1,
  sliderStepSeconds: 5,
  startLocal: "2026-02-13T09:30",
  endLocal: "2026-02-13T09:49",
  clampedOffset: 7,
  targetPoint: null,
  targetBar: {
    bar_index: 3,
    time: 1_707_000_180,
    open: 103,
    high: 104,
    low: 102,
    close: 103,
    volume: 1_003,
  },
  targetCheckpoint: null,
  targetTime: 1_707_000_180,
  targetLocal: "2026-02-13T09:33",
  ...overrides,
});

describe("StrategyAnalyzerScrubSlider", () => {
  it("scales slider to total bars and shows one scrub track", () => {
    const focusSelectedRangeOffset = vi.fn();

    render(
      <StrategyAnalyzerScrubSlider
        rangeScrubMeta={buildRangeScrubMeta({
          progressedBars: 8,
          tradeTotalBars: 20,
          targetBar: {
            bar_index: 6,
            time: 1_707_000_360,
            open: 106,
            high: 107,
            low: 105,
            close: 106,
            volume: 1_006,
          },
        })}
        focusSelectedRangeOffset={focusSelectedRangeOffset}
        moveSelectedRangeByStep={vi.fn()}
      />,
    );

    const slider = screen.getByRole("slider", {
      name: "Navigate walking-forward progress in selected range",
    });
    expect(slider).toHaveAttribute("aria-valuemin", "0");
    expect(slider).toHaveAttribute("aria-valuemax", "19");
    expect(slider).toHaveAttribute("aria-valuenow", "6");
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();

    const hiddenInput = document.querySelector(
      'input[data-webmcp="strategy-analyzer-scrub-range"]',
    ) as HTMLInputElement | null;
    expect(hiddenInput).not.toBeNull();
    expect(hiddenInput?.max).toBe("19");
    expect(hiddenInput?.step).toBe("1");
    expect(hiddenInput?.value).toBe("6");
    expect(hiddenInput?.disabled).toBe(false);
  });

  it("maps bar offset input to latest checkpoint timeline offset", () => {
    const onInputOffset = vi.fn();

    const { rerender } = render(
      <StrategyAnalyzerScrubSlider
        rangeScrubMeta={buildRangeScrubMeta()}
        focusSelectedRangeOffset={onInputOffset}
        moveSelectedRangeByStep={vi.fn()}
      />,
    );

    const hiddenInput = document.querySelector(
      'input[data-webmcp="strategy-analyzer-scrub-range"]',
    ) as HTMLInputElement;
    fireEvent.input(hiddenInput, { target: { value: "6" } });
    expect(onInputOffset).toHaveBeenCalledWith(13);

    const onChangeOffset = vi.fn();
    rerender(
      <StrategyAnalyzerScrubSlider
        rangeScrubMeta={buildRangeScrubMeta({ clampedOffset: 6 })}
        focusSelectedRangeOffset={onChangeOffset}
        moveSelectedRangeByStep={vi.fn()}
      />,
    );
    const hiddenInputAfterRerender = document.querySelector(
      'input[data-webmcp="strategy-analyzer-scrub-range"]',
    ) as HTMLInputElement;
    fireEvent.change(hiddenInputAfterRerender, { target: { value: "15" } });
    expect(onChangeOffset).toHaveBeenCalledWith(19);
  });
});
