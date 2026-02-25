import { useEffect } from "react";
import type { CandlestickChartProps } from "../CandlestickChart";
import { normalizeVisibleRange, rangesEqual } from "./rangeUtils";
import type {
  CandlestickChartBooleanRef,
  CandlestickChartRef,
  CandlestickChartVisibleRangeRef,
} from "./types";

type Params = {
  chartRef: CandlestickChartRef;
  chartState?: CandlestickChartProps["chartState"];
  isUserInteracting: CandlestickChartBooleanRef;
  isSyncingRef: CandlestickChartBooleanRef;
  lastAppliedRangeRef: CandlestickChartVisibleRangeRef;
};

export default function useCandlestickChartExternalRangeSync({
  chartRef,
  chartState,
  isUserInteracting,
  isSyncingRef,
  lastAppliedRangeRef,
}: Params): void {
  useEffect(() => {
    if (!chartRef.current) return;
    const nextRange = normalizeVisibleRange(chartState);
    if (!nextRange) return;

    // If user is interacting, this chart is the leader. Ignore follower updates.
    if (isUserInteracting.current) return;
    if (rangesEqual(lastAppliedRangeRef.current, nextRange)) return;

    const api = chartRef.current.timeScale();
    const current = normalizeVisibleRange(api.getVisibleRange());
    if (rangesEqual(current, nextRange)) {
      lastAppliedRangeRef.current = nextRange;
      return;
    }

    isSyncingRef.current = true;
    try {
      api.setVisibleRange(nextRange);
      lastAppliedRangeRef.current = nextRange;
    } catch {
      // Ignore errors if data is not ready yet.
    } finally {
      isSyncingRef.current = false;
    }
  }, [chartRef, chartState, isSyncingRef, isUserInteracting, lastAppliedRangeRef]);
}
