import { toIsoTimestamp, toUnixSeconds } from "../utils";

const VALID_MARKER_TYPES = [
  "entry_executed",
  "exit_executed",
  "stop_loss_hit",
  "take_profit_hit",
  "regime_detected",
  "strategy_selected",
  "iceberg_detected",
];

const DEFAULT_MARKER_PALETTE = {
  long: "#0f766e",
  short: "#dc2626",
  neutral: "#475569",
  blue: "#1d4ed8",
  amber: "#f59e0b",
  ice: "#00dbe3",
};

const readCssVar = (name: string, fallback: string): string => {
  if (typeof window === "undefined" || typeof document === "undefined") {
    return fallback;
  }
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return value || fallback;
};

const buildMarkerPalette = () => ({
  long: readCssVar("--accent-green", DEFAULT_MARKER_PALETTE.long),
  short: readCssVar("--accent-red", DEFAULT_MARKER_PALETTE.short),
  neutral: DEFAULT_MARKER_PALETTE.neutral,
  blue: readCssVar("--accent-blue", DEFAULT_MARKER_PALETTE.blue),
  amber: readCssVar("--accent-amber", DEFAULT_MARKER_PALETTE.amber),
  ice: DEFAULT_MARKER_PALETTE.ice,
});

export const findFirstBarIndex = (bars: any[], targetTime: number): number => {
  let lo = 0;
  let hi = bars.length;
  while (lo < hi) {
    const mid = (lo + hi) >>> 1;
    if (bars[mid].time < targetTime) lo = mid + 1;
    else hi = mid;
  }
  return lo;
};

export const normalizeDecisionMarkers = (markers: any[] = []) =>
  markers
    .map((marker, index) => {
      const time = toUnixSeconds(marker?.time ?? marker?.timestamp);
      if (!Number.isFinite(time)) return null;
      return {
        ...marker,
        id: marker.id || `${marker.marker_type || "marker"}-${Math.floor(time)}-${index}`,
        time: Math.floor(time),
        timestamp: marker.timestamp || toIsoTimestamp(time),
      };
    })
    .filter(Boolean);

export const normalizeIcebergMarkers = (icebergs: any[] = []) =>
  icebergs
    .map((iceberg, index) => {
      const time = toUnixSeconds(iceberg?.time ?? iceberg?.timestamp);
      if (!Number.isFinite(time)) return null;

      const side = typeof iceberg.side === "string" ? iceberg.side.toLowerCase() : null;
      const price = Number(iceberg.price);
      const tradeSize = Number(iceberg.trade_size ?? 0);
      const hiddenSize = Number(iceberg.hidden_size ?? 0);
      const totalSize = tradeSize + hiddenSize;

      return {
        ...iceberg,
        id: iceberg.id || `iceberg-${Math.floor(time)}-${index}`,
        marker_type: "iceberg_detected",
        time: Math.floor(time),
        timestamp: iceberg.timestamp || toIsoTimestamp(time),
        side,
        price: Number.isFinite(price) ? price : null,
        title: iceberg.title || `Iceberg ${side ? side.toUpperCase() : "UNKNOWN"}`,
        description: iceberg.description || `Detected ${side || "unknown"} iceberg`,
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
    .filter(Boolean);

export const buildCvdData = (l2Data: any) => {
  if (!l2Data || !Array.isArray(l2Data.bars)) return [];
  let cumDelta = 0;
  const sortedL2 = [...l2Data.bars].sort((a, b) => a.time - b.time);
  return sortedL2.map((bar) => {
    cumDelta += bar.delta || 0;
    return {
      time: bar.time,
      value: cumDelta,
      color: cumDelta >= 0 ? "rgba(38, 166, 154, 0.4)" : "rgba(239, 83, 80, 0.4)",
    };
  });
};

export const buildValidChartBars = (bars: any[] = []) => {
  const seenTimes = new Set<number>();
  return bars
    .filter((bar) => {
      if (!bar || typeof bar.time !== "number" || Number.isNaN(bar.time)) return false;
      if (seenTimes.has(bar.time)) return false;
      seenTimes.add(bar.time);
      return true;
    })
    .sort((left, right) => left.time - right.time);
};

export const buildMarkersByTime = (markers: any[]) => {
  const markersByTime = new Map<number, any[]>();
  markers.forEach((marker) => {
    const key = Math.floor(Number(marker?.time));
    if (!Number.isFinite(key)) return;
    const existing = markersByTime.get(key) || [];
    existing.push(marker);
    markersByTime.set(key, existing);
  });
  return markersByTime;
};

export const resolveClickedMarkerCandidate = (candidates: any[], clickedPrice: number | null) => {
  if (!Array.isArray(candidates) || candidates.length === 0) return null;
  if (candidates.length === 1 || !Number.isFinite(clickedPrice)) return candidates[0];

  const pricedCandidates = candidates.filter((candidate) => Number.isFinite(Number(candidate.price)));
  if (!pricedCandidates.length) return candidates[0];

  return pricedCandidates.reduce((best, candidate) => {
    const bestDiff = Math.abs(Number(best.price) - Number(clickedPrice));
    const candidateDiff = Math.abs(Number(candidate.price) - Number(clickedPrice));
    return candidateDiff < bestDiff ? candidate : best;
  }, pricedCandidates[0]);
};

export const buildChartMarkers = (clickableMarkers: any[]) => {
  const palette = buildMarkerPalette();

  return clickableMarkers
    .filter((marker) => marker && VALID_MARKER_TYPES.includes(marker.marker_type))
    .map((marker) => {
      const time = Math.floor(Number(marker.time));
      if (!Number.isFinite(time)) return null;

      let position = "aboveBar";
      let color = "#3b82f6";
      let shape = "circle";
      let text = "";

      switch (marker.marker_type) {
        case "entry_executed":
          if (marker.side === "long") {
            position = "belowBar";
            color = palette.long;
            shape = "arrowUp";
            text = "BUY";
          } else {
            position = "aboveBar";
            color = palette.short;
            shape = "arrowDown";
            text = "SELL";
          }
          break;
        case "exit_executed":
        case "stop_loss_hit":
          if (marker.side === "long") {
            position = "aboveBar";
            color = marker.marker_type === "stop_loss_hit" ? palette.short : palette.neutral;
            shape = "arrowDown";
            text = marker.marker_type === "stop_loss_hit" ? "SL" : "SELL";
          } else {
            position = "belowBar";
            color = marker.marker_type === "stop_loss_hit" ? palette.short : palette.neutral;
            shape = "arrowUp";
            text = marker.marker_type === "stop_loss_hit" ? "SL" : "BUY";
          }
          break;
        case "take_profit_hit":
          position = marker.side === "long" ? "aboveBar" : "belowBar";
          color = palette.long;
          shape = marker.side === "long" ? "arrowDown" : "arrowUp";
          text = "TP";
          break;
        case "regime_detected":
          position = "aboveBar";
          color = palette.blue;
          shape = "circle";
          text = marker.regime || "R";
          break;
        case "strategy_selected": {
          position = "belowBar";
          shape = "square";
          text = (marker.strategy || "UNK").substring(0, 3).toUpperCase();
          const hash = (marker.strategy || "").split("").reduce((acc, char) => acc + char.charCodeAt(0), 0);
          color = `hsl(${hash % 360}, 70%, 50%)`;
          break;
        }
        case "iceberg_detected":
          if (marker.side === "buy") {
            position = "aboveBar";
            color = palette.ice;
            shape = "arrowDown";
            text = "❄️";
          } else {
            position = "belowBar";
            color = palette.ice;
            shape = "arrowUp";
            text = "❄️";
          }
          break;
      }

      return { time, position, color, shape, text, id: marker.id || `${marker.time}-${marker.price}` };
    })
    .filter((marker) => marker && Number.isFinite(marker.time))
    .sort((left, right) => left.time - right.time);
};

export const resolveMarkerFocusedVisibleRange = (
  bars: any[],
  marker: any,
  windowSize = 40,
): { from: number; to: number } | null => {
  if (!Array.isArray(bars) || !bars.length || !marker) return null;
  const targetTime = toUnixSeconds(marker.time ?? marker.timestamp);
  if (!Number.isFinite(targetTime)) return null;

  let closestIndex = -1;
  let closestDiff = Number.POSITIVE_INFINITY;
  for (let i = 0; i < bars.length; i += 1) {
    const barTime = bars[i]?.time;
    if (!Number.isFinite(barTime)) continue;
    const diff = Math.abs(barTime - targetTime);
    if (diff < closestDiff) {
      closestDiff = diff;
      closestIndex = i;
    }
  }

  if (closestIndex === -1) return null;

  const fromIndex = Math.max(0, closestIndex - windowSize);
  const toIndex = Math.min(bars.length - 1, closestIndex + windowSize);
  const fromTime = bars[fromIndex]?.time;
  const toTime = bars[toIndex]?.time;
  if (!Number.isFinite(fromTime) || !Number.isFinite(toTime)) return null;
  return {
    from: fromTime,
    to: toTime,
  };
};
