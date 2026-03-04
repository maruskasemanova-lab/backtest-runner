import { useEffect } from "react";
import { createChart, ColorType } from "lightweight-charts";
import type {
  CandlestickChartProps,
} from "../CandlestickChart";
import { normalizeVisibleRange, rangesEqual } from "./rangeUtils";
import { getCandlestickChartThemeColors } from "./themeUtils";
import type {
  CandlestickChartAppliedBarsMetaRef,
  CandlestickChartBooleanRef,
  CandlestickChartCandleSeriesRef,
  CandlestickChartContainerRef,
  CandlestickChartErrorSetter,
  CandlestickChartHistogramSeriesRef,
  CandlestickChartInteractionTimeoutRef,
  CandlestickChartOnChartStateChangeRef,
  CandlestickChartRef,
  CandlestickChartVisibleRangeRef,
} from "./types";

type Params = {
  chartContainerRef: CandlestickChartContainerRef;
  chartRef: CandlestickChartRef;
  candleSeriesRef: CandlestickChartCandleSeriesRef;
  volumeSeriesRef: CandlestickChartHistogramSeriesRef;
  appliedBarsMetaRef: CandlestickChartAppliedBarsMetaRef;
  lastAppliedRangeRef: CandlestickChartVisibleRangeRef;
  lastBroadcastRangeRef: CandlestickChartVisibleRangeRef;
  isSyncingRef: CandlestickChartBooleanRef;
  isUserInteracting: CandlestickChartBooleanRef;
  interactionTimeoutRef: CandlestickChartInteractionTimeoutRef;
  onChartStateChangeRef: CandlestickChartOnChartStateChangeRef;
  onPriceRangeChange?: CandlestickChartProps["onPriceRangeChange"];
  setError: CandlestickChartErrorSetter;
};

export default function useCandlestickChartLifecycle({
  chartContainerRef,
  chartRef,
  candleSeriesRef,
  volumeSeriesRef,
  appliedBarsMetaRef,
  lastAppliedRangeRef,
  lastBroadcastRangeRef,
  isSyncingRef,
  isUserInteracting,
  interactionTimeoutRef,
  onChartStateChangeRef,
  onPriceRangeChange,
  setError,
}: Params): void {
  useEffect(() => {
    if (!chartContainerRef.current) return;

    try {
      const colors = getCandlestickChartThemeColors();

      const chart = createChart(chartContainerRef.current, {
        width: chartContainerRef.current.clientWidth,
        height: chartContainerRef.current.clientHeight,
        layout: {
          background: { type: ColorType.Solid, color: colors.bg },
          textColor: colors.text,
        },
        grid: {
          vertLines: { color: colors.grid },
          horzLines: { color: colors.grid },
        },
        crosshair: {
          mode: 1,
          vertLine: {
            color: colors.text,
            width: 1,
            style: 2,
            labelBackgroundColor: colors.accent,
          },
          horzLine: {
            color: colors.text,
            width: 1,
            style: 2,
            labelBackgroundColor: colors.accent,
          },
        },
        rightPriceScale: {
          borderColor: colors.grid,
          scaleMargins: {
            top: 0.1,
            bottom: 0.2,
          },
        },
        timeScale: {
          borderColor: colors.grid,
          timeVisible: true,
          secondsVisible: false,
        },
      });

      chart.timeScale().subscribeVisibleTimeRangeChange((range) => {
        const normalizedRange = normalizeVisibleRange(range);
        if (!normalizedRange) return;

        lastAppliedRangeRef.current = normalizedRange;
        if (isSyncingRef.current) return;
        if (rangesEqual(lastBroadcastRangeRef.current, normalizedRange)) return;

        lastBroadcastRangeRef.current = normalizedRange;
        onChartStateChangeRef.current?.(normalizedRange);
      });

      const candleSeries = chart.addCandlestickSeries({
        upColor: colors.up,
        downColor: colors.down,
        borderUpColor: colors.up,
        borderDownColor: colors.down,
        wickUpColor: colors.up,
        wickDownColor: colors.down,
      });

      const volumeSeries = chart.addHistogramSeries({
        color: colors.accent,
        priceFormat: {
          type: "volume",
        },
        priceScaleId: "volume",
      });

      chart.priceScale("volume").applyOptions({
        scaleMargins: {
          top: 0.85,
          bottom: 0,
        },
        borderVisible: false,
      });

      chartRef.current = chart;
      candleSeriesRef.current = candleSeries;
      volumeSeriesRef.current = volumeSeries;

      const syncChartSize = () => {
        if (chartContainerRef.current && chartRef.current) {
          chartRef.current.applyOptions({
            width: chartContainerRef.current.clientWidth,
            height: chartContainerRef.current.clientHeight,
          });
        }
      };

      syncChartSize();
      window.addEventListener("resize", syncChartSize);
      const resizeObserver =
        typeof ResizeObserver === "undefined"
          ? null
          : new ResizeObserver(() => {
              syncChartSize();
            });
      if (resizeObserver && chartContainerRef.current) {
        resizeObserver.observe(chartContainerRef.current);
      }

      const handleWheel = (e: WheelEvent) => {
        isUserInteracting.current = true;
        if (interactionTimeoutRef.current) clearTimeout(interactionTimeoutRef.current);
        interactionTimeoutRef.current = setTimeout(() => {
          isUserInteracting.current = false;
        }, 200);

        if (e.metaKey || e.ctrlKey) {
          e.preventDefault();
          const priceScale = chart.priceScale("right");
          const currentMargins = priceScale.options().scaleMargins || { top: 0.1, bottom: 0.2 };
          const delta = e.deltaY > 0 ? 0.02 : -0.02;
          const newTop = Math.max(0.02, Math.min(0.45, (currentMargins.top ?? 0.1) + delta));
          const newBottom = Math.max(0.02, Math.min(0.45, (currentMargins.bottom ?? 0.2) + delta));
          priceScale.applyOptions({
            scaleMargins: { top: newTop, bottom: newBottom },
          });
          onPriceRangeChange?.({ top: newTop, bottom: newBottom });
        }
      };

      const handleMouseDown = () => {
        isUserInteracting.current = true;
      };
      const handleMouseUp = () => {
        isUserInteracting.current = false;
      };
      const handleTouchStart = () => {
        isUserInteracting.current = true;
      };
      const handleTouchEnd = () => {
        isUserInteracting.current = false;
      };

      chartContainerRef.current.addEventListener("mousedown", handleMouseDown);
      chartContainerRef.current.addEventListener("mouseup", handleMouseUp);
      chartContainerRef.current.addEventListener("mouseleave", handleMouseUp);
      chartContainerRef.current.addEventListener("touchstart", handleTouchStart, { passive: true });
      chartContainerRef.current.addEventListener("touchend", handleTouchEnd);
      chartContainerRef.current.addEventListener("wheel", handleWheel, { passive: false });

      return () => {
        window.removeEventListener("resize", syncChartSize);
        resizeObserver?.disconnect();
        if (chartContainerRef.current) {
          chartContainerRef.current.removeEventListener("wheel", handleWheel);
          chartContainerRef.current.removeEventListener("mousedown", handleMouseDown);
          chartContainerRef.current.removeEventListener("mouseup", handleMouseUp);
          chartContainerRef.current.removeEventListener("mouseleave", handleMouseUp);
          chartContainerRef.current.removeEventListener("touchstart", handleTouchStart);
          chartContainerRef.current.removeEventListener("touchend", handleTouchEnd);
        }
        if (chartRef.current) {
          chartRef.current.remove();
          chartRef.current = null;
        }
        appliedBarsMetaRef.current = { length: 0, lastTime: null };
        lastAppliedRangeRef.current = null;
        lastBroadcastRangeRef.current = null;
      };
    } catch (err: unknown) {
      console.error("Chart initialization error:", err);
      setError(err instanceof Error ? err.message : "Chart initialization error");
    }
  }, []);
}
