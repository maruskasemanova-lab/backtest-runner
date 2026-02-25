import { useCallback, useEffect } from "react";
import type {
  CandlestickChartBar,
  CandlestickChartCandlePoint,
  CandlestickChartProps,
  CandlestickChartVolumePoint,
} from "../CandlestickChart";
import type {
  CandlestickChartAppliedBarsMetaRef,
  CandlestickChartCandleSeriesRef,
  CandlestickChartErrorSetter,
  CandlestickChartHistogramSeriesRef,
  CandlestickChartRef,
} from "./types";

type Params = {
  candleSeriesRef: CandlestickChartCandleSeriesRef;
  volumeSeriesRef: CandlestickChartHistogramSeriesRef;
  appliedBarsMetaRef: CandlestickChartAppliedBarsMetaRef;
  chartRef: CandlestickChartRef;
  bars: CandlestickChartBar[];
  chartState?: CandlestickChartProps["chartState"];
  setError: CandlestickChartErrorSetter;
};

export default function useCandlestickChartBarSeriesData({
  candleSeriesRef,
  volumeSeriesRef,
  appliedBarsMetaRef,
  chartRef,
  bars,
  chartState,
  setError,
}: Params): void {
  const toCandleDataPoint = useCallback((bar: CandlestickChartBar): CandlestickChartCandlePoint => {
    const time = Number(bar?.time) || 0;
    const open = Number(bar?.open);
    const high = Number(bar?.high);
    const low = Number(bar?.low);
    const close = Number(bar?.close);
    if (
      bar?.__wfPlaceholder ||
      !Number.isFinite(open) ||
      !Number.isFinite(high) ||
      !Number.isFinite(low) ||
      !Number.isFinite(close)
    ) {
      return { time };
    }
    return { time, open, high, low, close };
  }, []);

  const toVolumeDataPoint = useCallback((bar: CandlestickChartBar): CandlestickChartVolumePoint => {
    const time = Number(bar?.time) || 0;
    const open = Number(bar?.open);
    const close = Number(bar?.close);
    const volume = Number(bar?.volume);
    if (
      bar?.__wfPlaceholder ||
      !Number.isFinite(open) ||
      !Number.isFinite(close) ||
      !Number.isFinite(volume)
    ) {
      return { time };
    }
    return {
      time,
      value: volume,
      color: close >= open ? "rgba(34, 197, 94, 0.5)" : "rgba(239, 68, 68, 0.5)",
    };
  }, []);

  const applyFullBarDataset = useCallback(
    (sourceBars: CandlestickChartBar[]) => {
      if (!candleSeriesRef.current || !volumeSeriesRef.current) return;

      const seenTimes = new Set<number>();
      const validBars = (sourceBars || []).filter((bar) => {
        const time = Number(bar?.time);
        if (!Number.isFinite(time)) return false;
        if (seenTimes.has(time)) return false;
        seenTimes.add(time);
        return true;
      });

      validBars.sort((a, b) => Number(a.time) - Number(b.time));

      if (!validBars.length) {
        candleSeriesRef.current.setData([]);
        volumeSeriesRef.current.setData([]);
        appliedBarsMetaRef.current = { length: 0, lastTime: null };
        return;
      }

      candleSeriesRef.current.setData(validBars.map(toCandleDataPoint));
      volumeSeriesRef.current.setData(validBars.map(toVolumeDataPoint));
      appliedBarsMetaRef.current = {
        length: validBars.length,
        lastTime: Number(validBars[validBars.length - 1]?.time) || null,
      };
    },
    [appliedBarsMetaRef, candleSeriesRef, toCandleDataPoint, toVolumeDataPoint, volumeSeriesRef],
  );

  // Update bar series incrementally to avoid full chart reflows on every tick.
  useEffect(() => {
    if (!candleSeriesRef.current || !volumeSeriesRef.current) return;

    try {
      if (!Array.isArray(bars) || bars.length === 0) {
        applyFullBarDataset([]);
        return;
      }
      const containsWhitespaceBars = bars.some((bar) => Boolean(bar?.__wfPlaceholder));
      if (containsWhitespaceBars) {
        applyFullBarDataset(bars);
        return;
      }

      const nextLastBar = bars[bars.length - 1];
      const nextLastTime = Number(nextLastBar?.time);
      const prevMeta = appliedBarsMetaRef.current;

      const isAppend = prevMeta.length > 0 && bars.length === prevMeta.length + 1;
      const isInPlaceLastBarUpdate =
        prevMeta.length > 0 &&
        bars.length === prevMeta.length &&
        Number.isFinite(nextLastTime) &&
        nextLastTime === prevMeta.lastTime;
      const shouldFullRefresh =
        prevMeta.length === 0 ||
        bars.length < prevMeta.length ||
        bars.length > prevMeta.length + 1 ||
        !Number.isFinite(nextLastTime);

      if (shouldFullRefresh) {
        applyFullBarDataset(bars);
      } else if (isAppend || isInPlaceLastBarUpdate) {
        candleSeriesRef.current.update(toCandleDataPoint(nextLastBar));
        volumeSeriesRef.current.update(toVolumeDataPoint(nextLastBar));
        appliedBarsMetaRef.current = { length: bars.length, lastTime: nextLastTime };
      } else {
        applyFullBarDataset(bars);
      }

      if (chartRef.current && !chartState) {
        chartRef.current.timeScale().scrollToPosition(0, false);
      }
    } catch (err: unknown) {
      console.error("Chart data update error:", err);
      setError(err instanceof Error ? err.message : "Chart data update error");
      applyFullBarDataset(bars);
    }
  }, [
    appliedBarsMetaRef,
    applyFullBarDataset,
    bars,
    candleSeriesRef,
    chartRef,
    chartState,
    setError,
    toCandleDataPoint,
    toVolumeDataPoint,
    volumeSeriesRef,
  ]);
}
