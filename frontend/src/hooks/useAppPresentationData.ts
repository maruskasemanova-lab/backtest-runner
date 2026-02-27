import { useMemo } from 'react';
import type { CandlestickChartBar } from '../components/CandlestickChart';
import type { StrategyAnalyzerDecisionMarker } from '../components/strategy-analyzer/types';
import { toIsoTimestamp, toUnixSeconds } from '../utils';

type MarkerVisibility = {
  entries: boolean;
  exits: boolean;
  regime: boolean;
  strategy: boolean;
  icebergs: boolean;
};

type UseAppPresentationDataArgs = {
  bars: CandlestickChartBar[];
  timeframe: string;
  markers: StrategyAnalyzerDecisionMarker[];
  markerVisibility: MarkerVisibility;
  icebergs: Array<Record<string, any>>;
  icebergRenderLimit: number;
  featureFlags: Record<string, any> | null;
  planTier: string | null;
  activeView: string;
};

const toFiniteNumber = (value: unknown, fallback = 0): number => {
  const next = Number(value);
  return Number.isFinite(next) ? next : fallback;
};

export const useAppPresentationData = ({
  bars,
  timeframe,
  markers,
  markerVisibility,
  icebergs,
  icebergRenderLimit,
  featureFlags,
  planTier,
  activeView,
}: UseAppPresentationDataArgs) => {
  const displayedBars = useMemo(() => {
    if (timeframe === '1min') return bars;
    if (!bars.length) return [];

    const tfMinutes = Number.parseInt(timeframe, 10);
    if (!Number.isFinite(tfMinutes) || tfMinutes <= 0) return bars;

    const interval = tfMinutes * 60;
    const groups = new Map<number, CandlestickChartBar & { count: number }>();
    bars.forEach((bar) => {
      const time = toFiniteNumber(bar?.time, Number.NaN);
      if (!Number.isFinite(time)) return;
      const bucket = Math.floor(time / interval) * interval;

      if (!groups.has(bucket)) {
        groups.set(bucket, {
          time: bucket,
          open: toFiniteNumber(bar?.open),
          high: toFiniteNumber(bar?.high),
          low: toFiniteNumber(bar?.low),
          close: toFiniteNumber(bar?.close),
          volume: toFiniteNumber(bar?.volume),
          count: 1,
        });
        return;
      }

      const existing = groups.get(bucket);
      if (!existing) return;
      existing.high = Math.max(toFiniteNumber(existing.high), toFiniteNumber(bar?.high));
      existing.low = Math.min(toFiniteNumber(existing.low), toFiniteNumber(bar?.low));
      existing.close = toFiniteNumber(bar?.close, toFiniteNumber(existing.close));
      existing.volume =
        toFiniteNumber(existing.volume) + toFiniteNumber(bar?.volume);
      existing.count += 1;
    });

    if (!groups.size) return bars;
    return Array.from(groups.values()).sort((left, right) => {
      return toFiniteNumber(left.time) - toFiniteNumber(right.time);
    });
  }, [bars, timeframe]);

  const filteredMarkers = useMemo(() => {
    if (!markers.length) return [];
    return markers.filter((marker) => {
      const type = marker.marker_type;
      if (type === 'entry_executed' && !markerVisibility.entries) return false;
      if (
        (type === 'exit_executed' || type === 'stop_loss_hit' || type === 'take_profit_hit') &&
        !markerVisibility.exits
      ) {
        return false;
      }
      if (type === 'regime_detected' && !markerVisibility.regime) return false;
      if (type === 'strategy_selected' && !markerVisibility.strategy) return false;
      return true;
    });
  }, [markerVisibility, markers]);

  const filteredIcebergs = useMemo(() => {
    if (!markerVisibility.icebergs) return [];
    return icebergs.slice(0, icebergRenderLimit);
  }, [icebergs, icebergRenderLimit, markerVisibility.icebergs]);

  const showAdSlot = useMemo(() => {
    if (!featureFlags || !featureFlags.ads_enabled) return false;
    if (String(planTier || '').toLowerCase() !== 'free') return false;
    return ['data-manager', 'adaptive-studio', 'diagnostics'].includes(activeView);
  }, [activeView, featureFlags, planTier]);

  const icebergDecisionMarkers = useMemo<StrategyAnalyzerDecisionMarker[]>(() => {
    if (!icebergs.length) return [];

    return icebergs
      .map((iceberg, index) => {
        const rawTime = toUnixSeconds(iceberg?.time ?? iceberg?.timestamp);
        const timestamp = iceberg?.timestamp || toIsoTimestamp(rawTime);
        if (!timestamp) return null;

        const tradeSize = toFiniteNumber(iceberg?.trade_size);
        const hiddenSize = toFiniteNumber(iceberg?.hidden_size);
        const totalSize = tradeSize + hiddenSize;
        const side = typeof iceberg?.side === 'string' ? iceberg.side.toLowerCase() : null;
        const price = Number(iceberg?.price);
        const normalizedPrice = Number.isFinite(price) ? price : null;
        const sideLabel = side ? side.toUpperCase() : 'UNKNOWN';
        const readableSide =
          side === 'buy' ? 'BUY support' : side === 'sell' ? 'SELL resistance' : 'unknown side';

        return {
          ...iceberg,
          id: iceberg.id || `iceberg-${timestamp}-${normalizedPrice ?? 'na'}-${index}`,
          marker_type: 'iceberg_detected',
          title: iceberg.title || `Iceberg ${sideLabel}`,
          description: iceberg.description || `Detected ${readableSide} iceberg`,
          timestamp,
          time: rawTime,
          side,
          price: normalizedPrice,
          details: {
            ...(iceberg.details || {}),
            iceberg_side: side,
            iceberg_price: normalizedPrice,
            trade_size: tradeSize,
            hidden_size: hiddenSize,
            total_size: totalSize,
          },
        };
      })
      .filter((marker): marker is StrategyAnalyzerDecisionMarker => Boolean(marker))
      .sort((left, right) => toFiniteNumber(left.time) - toFiniteNumber(right.time))
      .slice(-icebergRenderLimit);
  }, [icebergRenderLimit, icebergs]);

  const decisionEvents = useMemo<StrategyAnalyzerDecisionMarker[]>(
    () => (markerVisibility.icebergs ? [...markers, ...icebergDecisionMarkers] : markers),
    [icebergDecisionMarkers, markerVisibility.icebergs, markers],
  );

  return {
    displayedBars,
    filteredMarkers,
    filteredIcebergs,
    showAdSlot,
    decisionEvents,
  };
};
