import { useEffect } from "react";
import { toUnixSeconds } from "../../utils";
import type {
  CandlestickChartBar,
  CandlestickChartClickHandler,
  CandlestickChartClickParam,
  CandlestickChartProps,
} from "../CandlestickChart";
import type {
  CandlestickChartCandleSeriesRef,
  CandlestickChartContainerRef,
  CandlestickChartRef,
  CandlestickChartTooltipSetter,
} from "./types";
import type { CandlestickChartNormalizedMarker } from "./useCandlestickChartMarkers";

type Params = {
  chartRef: CandlestickChartRef;
  candleSeriesRef: CandlestickChartCandleSeriesRef;
  chartContainerRef: CandlestickChartContainerRef;
  clickableMarkers: CandlestickChartNormalizedMarker[];
  onMarkerClick?: CandlestickChartProps["onMarkerClick"];
  onBarClick?: CandlestickChartProps["onBarClick"];
  bars: CandlestickChartBar[];
  setTooltip: CandlestickChartTooltipSetter;
};

export default function useCandlestickChartClickSelection({
  chartRef,
  candleSeriesRef,
  chartContainerRef,
  clickableMarkers,
  onMarkerClick,
  onBarClick,
  bars,
  setTooltip,
}: Params): void {
  useEffect(() => {
    if (!chartRef.current) return;

    const markerTimeMap = new Map<number, CandlestickChartNormalizedMarker[]>();
    clickableMarkers.forEach((marker) => {
      const key = Math.floor(Number(marker.time));
      if (!Number.isFinite(key)) return;
      const existing = markerTimeMap.get(key) || [];
      existing.push(marker);
      markerTimeMap.set(key, existing);
    });

    const resolveMarkerForClick = (
      param: CandlestickChartClickParam,
    ): CandlestickChartNormalizedMarker | null => {
      const clickedTime = toUnixSeconds(param?.time);
      if (!Number.isFinite(clickedTime)) return null;

      const candidates = markerTimeMap.get(Math.floor(clickedTime));
      if (!candidates || candidates.length === 0) return null;
      if (candidates.length === 1) return candidates[0];

      const clickedPrice =
        param?.point && candleSeriesRef.current?.coordinateToPrice
          ? candleSeriesRef.current.coordinateToPrice(param.point.y)
          : null;

      if (!Number.isFinite(clickedPrice)) return candidates[0];

      const pricedCandidates = candidates.filter((candidate) =>
        Number.isFinite(Number(candidate.price)),
      );
      if (!pricedCandidates.length) return candidates[0];

      return pricedCandidates.reduce((best, candidate) => {
        const bestDiff = Math.abs(Number(best.price) - clickedPrice);
        const candidateDiff = Math.abs(Number(candidate.price) - clickedPrice);
        return candidateDiff < bestDiff ? candidate : best;
      }, pricedCandidates[0]);
    };

    const handleClick: CandlestickChartClickHandler = (param) => {
      setTooltip((prev) => ({ ...prev, visible: false }));

      // Always call onBarClick if we have a valid time (for intrabar panel)
      if (param?.time && onBarClick) {
        const barTime = toUnixSeconds(param.time);
        if (Number.isFinite(barTime)) {
          const bar = bars?.find((b) => Math.floor(Number(b?.time)) === Math.floor(barTime));
          if (bar) {
            onBarClick(bar);
          }
        }
      }

      if (!param?.time || markerTimeMap.size === 0) return;

      const marker = resolveMarkerForClick(param);
      if (!marker) return;

      if (onMarkerClick) {
        onMarkerClick(marker);
      }

      const point = param.point;
      if (point && chartContainerRef.current) {
        const rect = chartContainerRef.current.getBoundingClientRect();
        setTooltip({
          visible: true,
          marker,
          x: point.x + rect.left,
          y: point.y + rect.top,
        });
      }
    };

    chartRef.current.subscribeClick(handleClick);

    return () => {
      try {
        if (chartRef.current) {
          chartRef.current.unsubscribeClick(handleClick);
        }
      } catch {
        // Ignore cleanup errors
      }
    };
  }, [bars, candleSeriesRef, chartContainerRef, chartRef, clickableMarkers, onBarClick, onMarkerClick, setTooltip]);
}
