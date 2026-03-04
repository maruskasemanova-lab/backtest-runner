import { useCallback, useMemo } from "react";
import { toIsoTimestamp, toUnixSeconds } from "../../utils";
import type { CandlestickChartBar, CandlestickChartMarker } from "../CandlestickChart";

const MAX_SNAP_SECONDS = 120;

export type CandlestickChartNormalizedMarker = CandlestickChartMarker & {
  id: string | number;
  time: number;
  timestamp?: string | number | null;
};

type Params = {
  bars: CandlestickChartBar[];
  markers?: CandlestickChartMarker[];
  icebergs?: CandlestickChartMarker[];
};

type Result = {
  clickableMarkers: CandlestickChartNormalizedMarker[];
};

export default function useCandlestickChartMarkers({
  bars,
  markers,
  icebergs,
}: Params): Result {
  const avgVolume = useMemo(
    () => bars.reduce((acc, bar) => acc + (bar?.volume || 0), 0) / (bars.length || 1),
    [bars],
  );

  const sortedBarTimes = useMemo<number[]>(() => {
    if (!bars || bars.length === 0) return [];
    return bars
      .map((bar) => bar?.time)
      .filter((time): time is number | string => Number.isFinite(Number(time)))
      .map((time) => Number(time))
      .sort((a, b) => a - b);
  }, [bars]);

  const snapToleranceSeconds = useMemo(() => {
    if (sortedBarTimes.length < 2) return MAX_SNAP_SECONDS;
    let minSpacing = Number.POSITIVE_INFINITY;
    for (let i = 1; i < sortedBarTimes.length; i += 1) {
      const spacing = sortedBarTimes[i] - sortedBarTimes[i - 1];
      if (spacing > 0 && spacing < minSpacing) {
        minSpacing = spacing;
      }
    }
    if (!Number.isFinite(minSpacing)) return MAX_SNAP_SECONDS;
    return Math.max(MAX_SNAP_SECONDS, minSpacing);
  }, [sortedBarTimes]);

  const findClosestBarTime = useCallback(
    (targetTime: number): number | null => {
      if (!Number.isFinite(targetTime)) return null;
      if (!sortedBarTimes.length) return targetTime;

      let left = 0;
      let right = sortedBarTimes.length - 1;
      let closest = sortedBarTimes[0];
      let minDiff = Math.abs(targetTime - closest);

      while (left <= right) {
        const middle = Math.floor((left + right) / 2);
        const value = sortedBarTimes[middle];
        const diff = Math.abs(targetTime - value);
        if (diff < minDiff) {
          minDiff = diff;
          closest = value;
        }
        if (value < targetTime) {
          left = middle + 1;
        } else if (value > targetTime) {
          right = middle - 1;
        } else {
          return value;
        }
      }

      if (minDiff > snapToleranceSeconds) return null;
      return closest;
    },
    [sortedBarTimes, snapToleranceSeconds],
  );

  const normalizeDecisionMarker = useCallback(
    (
      marker: CandlestickChartMarker | null | undefined,
      index: number,
    ): CandlestickChartNormalizedMarker | null => {
      if (!marker) return null;

      const rawTime = toUnixSeconds(marker.time ?? marker.timestamp);
      if (!Number.isFinite(rawTime)) return null;

      const snappedTime = findClosestBarTime(rawTime);
      if (!Number.isFinite(snappedTime)) return null;

      return {
        ...marker,
        id: marker.id || `${marker.marker_type || "marker"}-${snappedTime}-${index}`,
        time: snappedTime,
        timestamp: marker.timestamp || toIsoTimestamp(rawTime) || toIsoTimestamp(snappedTime),
      };
    },
    [findClosestBarTime],
  );

  const normalizedIcebergs = useMemo<CandlestickChartNormalizedMarker[]>(() => {
    return (icebergs || [])
      .map((iceberg, index) => {
        const rawTime = toUnixSeconds(iceberg.time ?? iceberg.timestamp);
        if (!Number.isFinite(rawTime)) return null;

        const snappedTime = findClosestBarTime(rawTime);
        if (!Number.isFinite(snappedTime)) return null;

        const tradeSize = Number(iceberg.trade_size ?? 0);
        const hiddenSize = Number(iceberg.hidden_size ?? 0);
        const totalSize = tradeSize + hiddenSize;
        const price = Number(iceberg.price);
        const side = typeof iceberg.side === "string" ? iceberg.side.toLowerCase() : null;

        return {
          ...iceberg,
          id: iceberg.id || `iceberg-${snappedTime}-${index}`,
          marker_type: "iceberg_detected",
          time: snappedTime,
          timestamp: iceberg.timestamp || toIsoTimestamp(rawTime) || toIsoTimestamp(snappedTime),
          side,
          price: Number.isFinite(price) ? price : null,
          total_size: Number.isFinite(totalSize) ? totalSize : 0,
          details: {
            ...(iceberg.details || {}),
            iceberg_side: side,
            iceberg_price: Number.isFinite(price) ? price : null,
            trade_size: tradeSize,
            hidden_size: hiddenSize,
            total_size: Number.isFinite(totalSize) ? totalSize : 0,
          },
        };
      })
      .filter((marker): marker is CandlestickChartNormalizedMarker => Boolean(marker));
  }, [icebergs, findClosestBarTime]);

  const filteredIcebergMarkers = useMemo<CandlestickChartNormalizedMarker[]>(() => {
    if (!normalizedIcebergs.length) return [];
    const minSize = avgVolume * 0.05;
    const byTime = new Map<number, CandlestickChartNormalizedMarker>();

    normalizedIcebergs
      .filter((iceberg) => Number(iceberg.total_size || 0) > minSize)
      .forEach((iceberg) => {
        const current = byTime.get(iceberg.time);
        if (!current || Number(iceberg.total_size || 0) > Number(current.total_size || 0)) {
          byTime.set(iceberg.time, iceberg);
        }
      });

    return Array.from(byTime.values());
  }, [normalizedIcebergs, avgVolume]);

  const clickableMarkers = useMemo<CandlestickChartNormalizedMarker[]>(() => {
    const decisions = (markers || [])
      .map((marker, index) => normalizeDecisionMarker(marker, index))
      .filter((marker): marker is CandlestickChartNormalizedMarker => Boolean(marker));
    return [...decisions, ...filteredIcebergMarkers];
  }, [markers, normalizeDecisionMarker, filteredIcebergMarkers]);

  return {
    clickableMarkers,
  };
}
