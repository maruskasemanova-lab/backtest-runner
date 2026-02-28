import type {
  DecisionLogPayloadExtractResult,
  EntryQualityDiagnosticsExtractResult,
  IntradayLevelsExtractResult,
  L2DiagnosticsExtractResult,
  LevelContextExtractResult,
  MaybeObjectRecord,
  ObjectRecord,
} from "./decision-panel-diagnostic-types";
import {
  getBooleanMetricFromSource,
  getL2MetricFromSource,
  isObjectRecord,
  normalizeL2SourceSnapshot,
  resolveBreakEven,
  resolveContextRisk,
  resolveL2Source,
  resolveRiskControls,
} from "./decision-panel-diagnostic-resolvers";

const findFirstObjectRecord = (candidates: unknown[]): ObjectRecord | null => {
  const match = candidates.find(isObjectRecord);
  return match || null;
};

const toStringArray = (value: unknown): string[] =>
  Array.isArray(value) ? value.map((item) => String(item || "")).filter(Boolean) : [];

export const extractL2Diagnostics = (
  marker: MaybeObjectRecord,
  details: MaybeObjectRecord,
  metadata: MaybeObjectRecord,
): L2DiagnosticsExtractResult => {
  const { source, sourcePath, candidateDiagnostics } = resolveL2Source(marker, details, metadata);

  const flowScore = getL2MetricFromSource(source, "flow_score");
  const signedAggression = getL2MetricFromSource(source, "signed_aggression");
  const l2AggressionZ = getL2MetricFromSource(source, "l2_aggression_z");
  const l2BookPressureZ = getL2MetricFromSource(source, "l2_book_pressure_z");
  const absorptionRate = getL2MetricFromSource(source, "absorption_rate");
  const largeTraderActivity = getL2MetricFromSource(source, "large_trader_activity");
  const vwapExecutionFlow = getL2MetricFromSource(source, "vwap_execution_flow");
  const detailMetadata = isObjectRecord(details?.metadata) ? details.metadata : null;
  const signalMetadata = isObjectRecord(details?.signal_metadata) ? details.signal_metadata : null;
  const sweepDetected =
    getBooleanMetricFromSource(source, "sweep_detected") ??
    (typeof details?.sweep_detected === "boolean" ? details.sweep_detected : null) ??
    (typeof detailMetadata?.sweep_detected === "boolean" ? detailMetadata.sweep_detected : null) ??
    (typeof signalMetadata?.sweep_detected === "boolean" ? signalMetadata.sweep_detected : null) ??
    (typeof detailMetadata?.sweep_triggered === "boolean" ? detailMetadata.sweep_triggered : null);

  const hasAny =
    [
      flowScore,
      signedAggression,
      l2AggressionZ,
      l2BookPressureZ,
      absorptionRate,
      largeTraderActivity,
      vwapExecutionFlow,
    ].some((value) => value !== null) || sweepDetected !== null;

  return {
    hasAny,
    flowScore,
    signedAggression,
    l2AggressionZ,
    l2BookPressureZ,
    absorptionRate,
    largeTraderActivity,
    vwapExecutionFlow,
    sweepDetected,
    sourcePath,
    candidateDiagnostics,
  };
};

export const extractIntradayLevels = (
  marker: MaybeObjectRecord,
  details: MaybeObjectRecord,
  metadata: MaybeObjectRecord,
): IntradayLevelsExtractResult => {
  const payload = findFirstObjectRecord([
    details?.intraday_levels,
    details?.metadata?.intraday_levels,
    details?.indicators?.intraday_levels,
    metadata?.intraday_levels,
    marker?.intraday_levels,
  ]);

  if (!payload) {
    return { hasAny: false, enabled: true, stats: {}, volumeProfile: {}, latestEvent: null };
  }

  return {
    hasAny: true,
    enabled: payload.enabled !== false,
    stats: findFirstObjectRecord([payload.stats]) || {},
    volumeProfile: findFirstObjectRecord([payload.volume_profile]) || {},
    latestEvent: findFirstObjectRecord([payload.latest_event]),
  };
};

export const extractLevelContext = (
  marker: MaybeObjectRecord,
  details: MaybeObjectRecord,
  metadata: MaybeObjectRecord,
): LevelContextExtractResult => {
  const payload = findFirstObjectRecord([
    details?.level_context,
    details?.metadata?.level_context,
    details?.signal_metadata?.level_context,
    metadata?.level_context,
    marker?.level_context,
  ]);

  if (!payload) {
    return { hasAny: false, payload: {}, checks: {}, reasons: [] };
  }

  return {
    hasAny: true,
    payload,
    checks: findFirstObjectRecord([payload.checks]) || {},
    reasons: toStringArray(payload.reasons),
  };
};

export const extractEntryQualityDiagnostics = (
  marker: MaybeObjectRecord,
  details: MaybeObjectRecord,
  metadata: MaybeObjectRecord,
): EntryQualityDiagnosticsExtractResult => {
  const payload = findFirstObjectRecord([
    details?.entry_quality_diagnostics,
    details?.metadata?.entry_quality_diagnostics,
    metadata?.entry_quality_diagnostics,
    marker?.entry_quality_diagnostics,
  ]);

  if (!payload) {
    return { hasAny: false, payload: {}, tags: [] };
  }

  return {
    hasAny: true,
    payload,
    tags: toStringArray(payload.first_bar_stop_tags),
  };
};

export const extractDecisionLogPayload = (
  marker: MaybeObjectRecord,
  details: MaybeObjectRecord,
  metadata: MaybeObjectRecord,
): DecisionLogPayloadExtractResult => {
  const markerType = String(marker?.marker_type || "").trim();
  const marketContext = isObjectRecord(details?.market_context) ? details.market_context : null;
  const signalMetadata =
    markerType === "entry_executed"
      ? isObjectRecord(details?.metadata)
        ? details.metadata
        : null
      : isObjectRecord(details?.signal_metadata)
        ? details.signal_metadata
        : null;
  const levelContext = findFirstObjectRecord([details?.level_context, signalMetadata?.level_context]);
  const intradayLevels = findFirstObjectRecord([
    details?.intraday_levels,
    signalMetadata?.intraday_levels,
  ]);
  const flowSnapshot = normalizeL2SourceSnapshot(
    resolveL2Source(marker, details, signalMetadata).source,
  );
  const entryQualityDiagnostics = isObjectRecord(details?.entry_quality_diagnostics)
    ? details.entry_quality_diagnostics
    : null;
  const riskControlsResolution = resolveRiskControls({
    details,
    signalMetadata,
    marketContext,
  });
  const contextRiskResolution = resolveContextRisk({
    details,
    signalMetadata,
    marketContext,
    riskControls: riskControlsResolution.value,
  });
  const breakEvenResolution = resolveBreakEven({
    details,
    signalMetadata,
    marketContext,
  });
  const decisionState = isObjectRecord(marketContext?.decision_state) ? marketContext.decision_state : null;

  const payload = {
    marker_meta: {
      id: marker?.id ?? null,
      marker_type: marker?.marker_type ?? null,
      timestamp: marker?.timestamp ?? marker?.time ?? null,
      title: marker?.title ?? null,
      description: marker?.description ?? null,
      side: marker?.side ?? null,
      strategy: marker?.strategy ?? null,
      price: marker?.price ?? null,
      confidence: marker?.confidence ?? null,
    },
    decision_state: decisionState,
    signal_metadata: signalMetadata,
    level_context: levelContext,
    intraday_levels: intradayLevels,
    flow_snapshot: flowSnapshot,
    market_context: marketContext,
    entry_quality_diagnostics: entryQualityDiagnostics,
    risk_controls: riskControlsResolution.value,
    context_risk: contextRiskResolution.value,
    context_risk_source_path: contextRiskResolution.sourcePath,
    context_risk_candidates: contextRiskResolution.candidates,
    break_even: breakEvenResolution.value,
    break_even_source_path: breakEvenResolution.sourcePath,
    break_even_candidates: breakEvenResolution.candidates,
    risk_controls_source_path: riskControlsResolution.sourcePath,
    risk_controls_candidates: riskControlsResolution.candidates,
    metadata,
    details,
  };

  return {
    hasAny: Object.values(payload).some((value) => value != null),
    payload,
  };
};
