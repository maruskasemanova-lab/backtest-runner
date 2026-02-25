import { toUnixSeconds } from "./utils";

export type IntradayLevelsObject = Record<string, unknown>;
export type IntradayLevelsBarLike = IntradayLevelsObject;
export type IntradayLevelsMarkerLike = IntradayLevelsObject;

type IntradayLevelsSource = { payload: IntradayLevelsObject; sourcePath: string } | null;

type IntradayLevelsMarkerTimeRow = {
  marker: IntradayLevelsMarkerLike;
  markerTime: number;
};

type IntradayLevelsNearestMarkerMatch = {
  marker: IntradayLevelsMarkerLike;
  levels: IntradayLevelsPayloadMatch;
  diff: number;
  markerTime: number;
};

export type IntradayLevelsDialogSelection = {
  bar: IntradayLevelsBarLike;
  payload: IntradayLevelsObject | null;
  sourcePath: string | null;
  sourceMarker: IntradayLevelsMarkerLike | null;
  relatedMarkers: IntradayLevelsMarkerLike[];
  timeframeSeconds: number;
};

export type IntradayLevelsPayloadMatch = {
  payload: IntradayLevelsObject | null;
  sourcePath: string | null;
};

type BuildIntradayLevelsDialogSelectionParams = {
  bar: IntradayLevelsBarLike | null | undefined;
  allMarkers: IntradayLevelsMarkerLike[];
  timeframeSeconds: number;
  fallbackAnalysis?: IntradayLevelsObject | null;
  fallbackAnalysisSourcePath?: string;
};

const isObjectRecord = (value: unknown): value is IntradayLevelsObject =>
  Boolean(value) && typeof value === "object" && !Array.isArray(value);

const emptyMatch = (): IntradayLevelsPayloadMatch => ({ payload: null, sourcePath: null });

const pickIntradayLevelsPayload = (sources: IntradayLevelsSource[]): IntradayLevelsPayloadMatch => {
  if (!Array.isArray(sources)) return emptyMatch();
  for (const source of sources) {
    if (!source || !isObjectRecord(source.payload)) continue;
    const sourcePath = String(source.sourcePath || "").trim();
    return { payload: source.payload, sourcePath: sourcePath || null };
  }
  return emptyMatch();
};

export const extractIntradayLevelsFromAnalysisObject = (
  analysis: unknown,
  sourcePrefix: string
): IntradayLevelsPayloadMatch => {
  if (!isObjectRecord(analysis)) return emptyMatch();
  const metadata = isObjectRecord(analysis.metadata) ? analysis.metadata : null;
  const indicators = isObjectRecord(analysis.indicators) ? analysis.indicators : null;
  const signalMetadata = isObjectRecord(analysis.signal_metadata) ? analysis.signal_metadata : null;
  const signal = isObjectRecord(analysis.signal) ? analysis.signal : null;
  const signalMetadataNested = isObjectRecord(signal?.metadata) ? signal.metadata : null;
  return pickIntradayLevelsPayload([
    { sourcePath: `${sourcePrefix}.intraday_levels`, payload: analysis.intraday_levels },
    {
      sourcePath: `${sourcePrefix}.metadata.intraday_levels`,
      payload: metadata?.intraday_levels,
    },
    {
      sourcePath: `${sourcePrefix}.indicators.intraday_levels`,
      payload: indicators?.intraday_levels,
    },
    {
      sourcePath: `${sourcePrefix}.signal_metadata.intraday_levels`,
      payload: signalMetadata?.intraday_levels,
    },
    {
      sourcePath: `${sourcePrefix}.signal.intraday_levels`,
      payload: signal?.intraday_levels,
    },
    {
      sourcePath: `${sourcePrefix}.signal.metadata.intraday_levels`,
      payload: signalMetadataNested?.intraday_levels,
    },
  ]);
};

export const extractIntradayLevelsFromBarPayload = (
  bar: IntradayLevelsBarLike | null | undefined
): IntradayLevelsPayloadMatch => {
  if (!isObjectRecord(bar)) return emptyMatch();
  const barAnalysis = extractIntradayLevelsFromAnalysisObject(bar.analysis, "bar.analysis");
  const strategyAnalysis = extractIntradayLevelsFromAnalysisObject(
    bar.strategy_analysis,
    "bar.strategy_analysis"
  );
  return pickIntradayLevelsPayload([
    { sourcePath: "bar.intraday_levels", payload: bar.intraday_levels },
    barAnalysis,
    strategyAnalysis,
  ]);
};

export const extractIntradayLevelsFromMarkerPayload = (
  marker: IntradayLevelsMarkerLike | null | undefined
): IntradayLevelsPayloadMatch => {
  if (!isObjectRecord(marker)) return emptyMatch();
  const details = isObjectRecord(marker.details) ? marker.details : {};
  const detailMetadata = isObjectRecord(details.metadata) ? details.metadata : {};
  const detailIndicators = isObjectRecord(details.indicators) ? details.indicators : {};
  const detailSignalMetadata = isObjectRecord(details.signal_metadata) ? details.signal_metadata : {};
  return pickIntradayLevelsPayload([
    { sourcePath: "marker.details.intraday_levels", payload: details.intraday_levels },
    {
      sourcePath: "marker.details.metadata.intraday_levels",
      payload: detailMetadata.intraday_levels,
    },
    {
      sourcePath: "marker.details.indicators.intraday_levels",
      payload: detailIndicators.intraday_levels,
    },
    {
      sourcePath: "marker.details.signal_metadata.intraday_levels",
      payload: detailSignalMetadata.intraday_levels,
    },
    { sourcePath: "marker.metadata.intraday_levels", payload: detailMetadata.intraday_levels },
    { sourcePath: "marker.intraday_levels", payload: marker.intraday_levels },
  ]);
};

export const resolveNearestMarkerWithIntradayLevels = (
  allMarkers: IntradayLevelsMarkerLike[],
  barTime: number
): IntradayLevelsNearestMarkerMatch | null => {
  if (!Array.isArray(allMarkers) || !Number.isFinite(barTime)) return null;
  let nearest: IntradayLevelsNearestMarkerMatch | null = null;
  allMarkers.forEach((marker: IntradayLevelsMarkerLike) => {
    const markerTime = toUnixSeconds(marker?.time ?? marker?.timestamp);
    if (!Number.isFinite(markerTime)) return;
    const markerLevels = extractIntradayLevelsFromMarkerPayload(marker);
    if (!markerLevels.payload) return;
    const diff = Math.abs(markerTime - barTime);
    if (!nearest || diff < nearest.diff) {
      nearest = { marker, levels: markerLevels, diff, markerTime };
      return;
    }
    if (diff === nearest.diff) {
      const nearestIsFuture = nearest.markerTime > barTime;
      const currentIsPastOrNow = markerTime <= barTime;
      if (nearestIsFuture && currentIsPastOrNow) {
        nearest = { marker, levels: markerLevels, diff, markerTime };
      }
    }
  });
  return nearest;
};

export const resolveMarkersInBarWindow = (
  allMarkers: IntradayLevelsMarkerLike[],
  barTime: number,
  timeframeSeconds?: number
): IntradayLevelsMarkerLike[] => {
  if (!Array.isArray(allMarkers) || !Number.isFinite(barTime)) return [];
  const windowSize =
    Number.isFinite(timeframeSeconds) && Number(timeframeSeconds) > 0 ? Number(timeframeSeconds) : 60;
  const startTime = Math.floor(barTime);
  const endTime = startTime + windowSize;
  return allMarkers
    .map((marker: IntradayLevelsMarkerLike): IntradayLevelsMarkerTimeRow | null => {
      const markerTime = toUnixSeconds(marker?.time ?? marker?.timestamp);
      return Number.isFinite(markerTime) ? { marker, markerTime } : null;
    })
    .filter((row): row is IntradayLevelsMarkerTimeRow => Boolean(row))
    .filter((row) => row.markerTime >= startTime && row.markerTime < endTime)
    .sort((left, right) => left.markerTime - right.markerTime)
    .map((row) => row.marker);
};

export const buildIntradayLevelsDialogSelection = ({
  bar,
  allMarkers,
  timeframeSeconds,
  fallbackAnalysis,
  fallbackAnalysisSourcePath,
}: BuildIntradayLevelsDialogSelectionParams): IntradayLevelsDialogSelection | null => {
  if (!isObjectRecord(bar)) return null;

  const barTime = Number(bar.time);
  const markersInWindow = resolveMarkersInBarWindow(allMarkers, barTime, timeframeSeconds);

  let resolved = extractIntradayLevelsFromBarPayload(bar);
  let sourceMarker: IntradayLevelsMarkerLike | null = null;

  if (!resolved.payload && fallbackAnalysis && fallbackAnalysisSourcePath) {
    resolved = extractIntradayLevelsFromAnalysisObject(fallbackAnalysis, fallbackAnalysisSourcePath);
  }

  if (!resolved.payload) {
    for (const marker of markersInWindow) {
      const markerLevels = extractIntradayLevelsFromMarkerPayload(marker);
      if (!markerLevels.payload) continue;
      resolved = markerLevels;
      sourceMarker = marker;
      break;
    }
  }

  if (!resolved.payload) {
    const nearestMarkerMatch = resolveNearestMarkerWithIntradayLevels(allMarkers, barTime);
    if (nearestMarkerMatch) {
      resolved = nearestMarkerMatch.levels;
      sourceMarker = nearestMarkerMatch.marker;
    }
  }

  const relatedMarkers =
    sourceMarker && !markersInWindow.some((candidate) => candidate?.id === sourceMarker?.id)
      ? [...markersInWindow, sourceMarker]
      : markersInWindow;

  return {
    bar,
    payload: resolved.payload,
    sourcePath: resolved.sourcePath,
    sourceMarker,
    relatedMarkers,
    timeframeSeconds,
  };
};
