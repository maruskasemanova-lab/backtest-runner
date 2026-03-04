import { renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { CandlestickChartTooltipState } from "../CandlestickChart";
import useCandlestickChartSelectedMarkerFocus from "./useCandlestickChartSelectedMarkerFocus";

type BuildParamsOverrides = {
  bars?: Array<{ time: number }>;
  selectedMarker?: { id?: string; time?: number; price?: number; __selectionSource?: string } | null;
  setVisibleRangeImpl?: () => void;
};

const createTooltipSetter = () =>
  vi.fn((next: CandlestickChartTooltipState | ((prev: CandlestickChartTooltipState) => CandlestickChartTooltipState)) => {
    const previous: CandlestickChartTooltipState = {
      visible: false,
      marker: null,
      x: 0,
      y: 0,
    };
    return typeof next === "function" ? next(previous) : next;
  });

const buildHookParams = (overrides: BuildParamsOverrides = {}) => {
  const setVisibleRange = vi.fn(overrides.setVisibleRangeImpl || (() => undefined));
  const setTooltip = createTooltipSetter();

  const bars = overrides.bars || [{ time: 100 }, { time: 160 }, { time: 220 }];
  const selectedMarker = overrides.selectedMarker ?? { id: "marker-1", time: 160, price: 101 };

  return {
    params: {
      chartRef: {
        current: {
          timeScale: () => ({
            setVisibleRange,
            timeToCoordinate: () => 8,
          }),
        },
      },
      candleSeriesRef: {
        current: {
          priceToCoordinate: () => 12,
        },
      },
      chartContainerRef: {
        current: {
          getBoundingClientRect: () => ({ left: 10, top: 20 }),
        },
      },
      selectedMarker,
      bars,
      lastFocusedMarkerKeyRef: { current: null },
      setTooltip,
    } as Parameters<typeof useCandlestickChartSelectedMarkerFocus>[0],
    setVisibleRange,
    setTooltip,
  };
};

describe("useCandlestickChartSelectedMarkerFocus", () => {
  it("swallows setVisibleRange errors when chart state is not ready", () => {
    const { params, setVisibleRange, setTooltip } = buildHookParams({
      setVisibleRangeImpl: () => {
        throw new Error("Value is null");
      },
    });

    expect(() => {
      renderHook(() => useCandlestickChartSelectedMarkerFocus(params));
    }).not.toThrow();

    expect(setVisibleRange).toHaveBeenCalledTimes(1);
    expect(setTooltip).toHaveBeenCalled();
  });

  it("skips visible-range focus for non-expanding ranges", () => {
    const { params, setVisibleRange } = buildHookParams({
      bars: [{ time: 100 }],
      selectedMarker: { id: "single-bar", time: 100, price: 99 },
    });

    renderHook(() => useCandlestickChartSelectedMarkerFocus(params));

    expect(setVisibleRange).not.toHaveBeenCalled();
  });
});
