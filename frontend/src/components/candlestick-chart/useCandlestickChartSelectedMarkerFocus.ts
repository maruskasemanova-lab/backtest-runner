import { useEffect } from "react";
import { toUnixSeconds } from "../../utils";
import type {
  CandlestickChartBar,
  CandlestickChartMarker,
} from "../CandlestickChart";
import type {
  CandlestickChartCandleSeriesRef,
  CandlestickChartContainerRef,
  CandlestickChartMarkerFocusKeyRef,
  CandlestickChartRef,
  CandlestickChartTooltipSetter,
} from "./types";

type Params = {
  chartRef: CandlestickChartRef;
  candleSeriesRef: CandlestickChartCandleSeriesRef;
  chartContainerRef: CandlestickChartContainerRef;
  selectedMarker?: CandlestickChartMarker | null;
  bars: CandlestickChartBar[];
  lastFocusedMarkerKeyRef: CandlestickChartMarkerFocusKeyRef;
  setTooltip: CandlestickChartTooltipSetter;
};

export default function useCandlestickChartSelectedMarkerFocus({
  chartRef,
  candleSeriesRef,
  chartContainerRef,
  selectedMarker,
  bars,
  lastFocusedMarkerKeyRef,
  setTooltip,
}: Params): void {
  useEffect(() => {
    if (!chartRef.current || !selectedMarker || !bars || bars.length === 0) {
      if (!selectedMarker) {
        lastFocusedMarkerKeyRef.current = null;
        setTooltip((prev) => ({ ...prev, visible: false }));
      }
      return;
    }

    const selectedFromDecisionPanel =
      String(selectedMarker?.__selectionSource || "") === "decision_panel";

    const markerFocusKey = String(selectedMarker.id || selectedMarker.time || selectedMarker.timestamp || "");
    if (markerFocusKey && lastFocusedMarkerKeyRef.current === markerFocusKey) {
      return;
    }

    const targetTime = toUnixSeconds(selectedMarker.time ?? selectedMarker.timestamp);
    if (!Number.isFinite(targetTime)) return;

    let closestIndex = -1;
    let closestDiff = Number.POSITIVE_INFINITY;
    for (let i = 0; i < bars.length; i += 1) {
      const barTime = bars[i]?.time;
      if (typeof barTime !== "number" || Number.isNaN(barTime)) continue;
      const diff = Math.abs(barTime - targetTime);
      if (diff < closestDiff) {
        closestDiff = diff;
        closestIndex = i;
      }
    }

    if (closestIndex === -1) return;

    const windowSize = 40;
    const fromIndex = Math.max(0, closestIndex - windowSize);
    const toIndex = Math.min(bars.length - 1, closestIndex + windowSize);
    const fromTime = bars[fromIndex]?.time;
    const toTime = bars[toIndex]?.time;

    if (fromTime && toTime && chartRef.current) {
      chartRef.current.timeScale().setVisibleRange({
        from: fromTime,
        to: toTime,
      });
      lastFocusedMarkerKeyRef.current = markerFocusKey || `${fromTime}-${toTime}`;
    }

    // Show tooltip for chart-driven selection only. Decision-panel selection opens detail dialog.
    if (selectedFromDecisionPanel) {
      setTooltip((prev) => ({ ...prev, visible: false }));
      return;
    }

    try {
      const timeScale = chartRef.current.timeScale();
      const x = timeScale.timeToCoordinate ? timeScale.timeToCoordinate(targetTime) : null;
      const price = Number(selectedMarker.price);
      const y = candleSeriesRef.current?.priceToCoordinate
        ? candleSeriesRef.current.priceToCoordinate(price)
        : null;
      if (
        x !== null &&
        y !== null &&
        chartContainerRef.current &&
        Number.isFinite(x) &&
        Number.isFinite(y)
      ) {
        const rect = chartContainerRef.current.getBoundingClientRect();
        setTooltip({
          visible: true,
          marker: selectedMarker,
          x: x + rect.left,
          y: y + rect.top,
        });
      }
    } catch {
      // Ignore tooltip errors, focus is the priority
    }
  }, [bars, candleSeriesRef, chartContainerRef, chartRef, lastFocusedMarkerKeyRef, selectedMarker, setTooltip]);
}
