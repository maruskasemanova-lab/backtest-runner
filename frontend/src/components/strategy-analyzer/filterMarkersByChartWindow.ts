import { toUnixSeconds } from "../../utils";
import type {
  StrategyAnalyzerChartWindow,
  StrategyAnalyzerDecisionMarker,
} from "./types";

export function filterMarkersByChartWindow(
  markers: StrategyAnalyzerDecisionMarker[],
  chartWindow: StrategyAnalyzerChartWindow | null,
): StrategyAnalyzerDecisionMarker[] {
  const source = Array.isArray(markers) ? markers : [];
  if (!source.length || !chartWindow) return source;

  const minTime = Number(chartWindow.from);
  const maxTime = Number(chartWindow.to);
  if (!Number.isFinite(minTime) || !Number.isFinite(maxTime)) return source;

  return source.filter((marker) => {
    const markerTime = toUnixSeconds(marker?.time ?? marker?.timestamp);
    if (Number.isFinite(markerTime)) {
      return markerTime >= minTime - 1 && markerTime <= maxTime + 1;
    }
    return true;
  });
}
