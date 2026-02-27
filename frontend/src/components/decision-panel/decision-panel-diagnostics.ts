import { toFiniteNumber } from "./decision-panel-utils";

type ObjectRecord = Record<string, unknown>;
type MaybeObjectRecord = ObjectRecord | null | undefined;

type ResolutionCandidate = {
  path: string;
  value: unknown;
};

type BaseResolutionParams = {
  details: MaybeObjectRecord;
  signalMetadata: MaybeObjectRecord;
  marketContext: MaybeObjectRecord;
};

type ContextRiskResolutionParams = BaseResolutionParams & {
  riskControls: MaybeObjectRecord;
};

type ResolutionResult = {
  value: ObjectRecord | null;
  sourcePath: string;
  candidates: ResolutionCandidate[];
};

type L2SourceCandidate = {
  sourcePath: string;
  source: ObjectRecord;
};

type L2CandidateDiagnostic = {
  sourcePath: string;
  score: number;
  availableMetrics: string[];
};

type L2SourceResolution = {
  source: ObjectRecord | null;
  sourcePath: string;
  candidateDiagnostics: L2CandidateDiagnostic[];
};

type L2DiagnosticsExtractResult = {
  hasAny: boolean;
  flowScore: number | null;
  signedAggression: number | null;
  l2AggressionZ: number | null;
  l2BookPressureZ: number | null;
  absorptionRate: number | null;
  largeTraderActivity: number | null;
  vwapExecutionFlow: number | null;
  sweepDetected: boolean | null;
  sourcePath: string;
  candidateDiagnostics: L2CandidateDiagnostic[];
};

type IntradayLevelsExtractResult = {
  hasAny: boolean;
  enabled: boolean;
  stats: ObjectRecord;
  volumeProfile: ObjectRecord;
  latestEvent: ObjectRecord | null;
};

type LevelContextExtractResult = {
  hasAny: boolean;
  payload: ObjectRecord;
  checks: ObjectRecord;
  reasons: string[];
};

type EntryQualityDiagnosticsExtractResult = {
  hasAny: boolean;
  payload: ObjectRecord;
  tags: string[];
};

type DecisionLogPayloadExtractResult = {
  hasAny: boolean;
  payload: ObjectRecord;
};

const EXIT_MARKER_TYPES = new Set([
  "exit_executed",
  "stop_loss_hit",
  "take_profit_hit",
  "time_exit",
]);

export const L2_DIAGNOSTIC_KEYS = [
  "flow_score",
  "signed_aggression",
  "l2_aggression_z",
  "l2_book_pressure_z",
  "absorption_rate",
  "large_trader_activity",
  "vwap_execution_flow",
];

export const isObjectRecord = (value: unknown): value is ObjectRecord =>
  Boolean(value) && typeof value === "object" && !Array.isArray(value);

const getL2MetricFromSource = (source: unknown, metricKey: string): number | null => {
  if (!isObjectRecord(source)) return null;
  const direct = toFiniteNumber(source[metricKey]);
  if (direct !== null) return direct;
  const prefixed = toFiniteNumber(source[`l2_${metricKey}`]);
  if (prefixed !== null) return prefixed;
  return null;
};

const getBooleanMetricFromSource = (source: unknown, metricKey: string): boolean | null => {
  if (!isObjectRecord(source)) return null;
  const direct = source[metricKey];
  if (typeof direct === "boolean") return direct;
  const prefixed = source[`l2_${metricKey}`];
  if (typeof prefixed === "boolean") return prefixed;
  return null;
};

const normalizeL2SourceSnapshot = (source: unknown): ObjectRecord | null => {
  if (!isObjectRecord(source)) return null;
  const normalized: ObjectRecord = { ...source };
  L2_DIAGNOSTIC_KEYS.forEach((metricKey) => {
    if (normalized[metricKey] == null) {
      const resolved = getL2MetricFromSource(source, metricKey);
      if (resolved !== null) {
        normalized[metricKey] = resolved;
      }
    }
  });
  if (normalized.sweep_detected == null) {
    const sweepDetected = getBooleanMetricFromSource(source, "sweep_detected");
    if (sweepDetected !== null) {
      normalized.sweep_detected = sweepDetected;
    }
  }
  return normalized;
};

const buildRiskControlsCandidates = ({
  details,
  signalMetadata,
  marketContext,
}: BaseResolutionParams): ResolutionCandidate[] => {
  const detailMetadata = isObjectRecord(details?.metadata) ? details.metadata : null;
  return [
    { path: "details.metadata.risk_controls", value: detailMetadata?.risk_controls },
    { path: "details.risk_controls", value: details?.risk_controls },
    {
      path: "details.entry_quality_diagnostics.risk_controls",
      value: details?.entry_quality_diagnostics?.risk_controls,
    },
    { path: "details.signal_metadata.risk_controls", value: details?.signal_metadata?.risk_controls },
    { path: "signal_metadata.risk_controls", value: signalMetadata?.risk_controls },
    { path: "market_context.risk_controls", value: marketContext?.risk_controls },
  ];
};

export const resolveRiskControls = (params: BaseResolutionParams): ResolutionResult => {
  const candidates = buildRiskControlsCandidates(params);
  const selected = candidates.find((candidate) => isObjectRecord(candidate.value));
  return {
    value: selected?.value || null,
    sourcePath: selected?.path || "n/a",
    candidates,
  };
};

const buildContextRiskCandidates = ({
  details,
  signalMetadata,
  marketContext,
  riskControls,
}: ContextRiskResolutionParams): ResolutionCandidate[] => {
  const detailMetadata = isObjectRecord(details?.metadata) ? details.metadata : null;
  return [
    { path: "details.context_risk", value: details?.context_risk },
    { path: "details.metadata.context_risk", value: detailMetadata?.context_risk },
    {
      path: "details.metadata.risk_controls.context_risk",
      value: detailMetadata?.risk_controls?.context_risk,
    },
    { path: "details.risk_controls.context_risk", value: details?.risk_controls?.context_risk },
    {
      path: "details.entry_quality_diagnostics.risk_controls.context_risk",
      value: details?.entry_quality_diagnostics?.risk_controls?.context_risk,
    },
    {
      path: "details.signal_metadata.risk_controls.context_risk",
      value: details?.signal_metadata?.risk_controls?.context_risk,
    },
    { path: "signal_metadata.risk_controls.context_risk", value: signalMetadata?.risk_controls?.context_risk },
    { path: "market_context.risk_controls.context_risk", value: marketContext?.risk_controls?.context_risk },
    { path: "resolved_risk_controls.context_risk", value: riskControls?.context_risk },
  ];
};

export const resolveContextRisk = (params: ContextRiskResolutionParams): ResolutionResult => {
  const candidates = buildContextRiskCandidates(params);
  const selected = candidates.find((candidate) => isObjectRecord(candidate.value));
  return {
    value: selected?.value || null,
    sourcePath: selected?.path || "n/a",
    candidates,
  };
};

const buildBreakEvenCandidates = ({
  details,
  signalMetadata,
  marketContext,
}: BaseResolutionParams): ResolutionCandidate[] => [
  { path: "details.break_even", value: details?.break_even },
  {
    path: "details.signal_metadata.break_even",
    value: details?.signal_metadata?.break_even,
  },
  {
    path: "details.entry_quality_diagnostics.break_even",
    value: details?.entry_quality_diagnostics?.break_even,
  },
  { path: "details.market_context.break_even", value: details?.market_context?.break_even },
  { path: "signal_metadata.break_even", value: signalMetadata?.break_even },
  { path: "market_context.break_even", value: marketContext?.break_even },
];

export const resolveBreakEven = (params: BaseResolutionParams): ResolutionResult => {
  const candidates = buildBreakEvenCandidates(params);
  const selected = candidates.find((candidate) => isObjectRecord(candidate.value));
  return {
    value: selected?.value || null,
    sourcePath: selected?.path || "n/a",
    candidates,
  };
};

const buildL2CandidateSources = (
  marker: MaybeObjectRecord,
  details: MaybeObjectRecord,
  metadata: MaybeObjectRecord,
): L2SourceCandidate[] => {
  const markerType = String(marker?.marker_type || "").trim();
  const detailMetadata = isObjectRecord(details?.metadata) ? details.metadata : null;
  const signalMetadata = isObjectRecord(details?.signal_metadata) ? details.signal_metadata : null;
  const metadataContext = isObjectRecord(metadata) ? metadata : null;
  const marketL2 = isObjectRecord(details?.market_context?.l2) ? details.market_context.l2 : null;

  const candidates: L2SourceCandidate[] = [];
  const pushCandidate = (sourcePath: string, source: unknown) => {
    if (!isObjectRecord(source)) return;
    candidates.push({ sourcePath, source });
  };

  if (markerType === "entry_executed") {
    pushCandidate("details.metadata.order_flow", detailMetadata?.order_flow ?? metadataContext?.order_flow);
    pushCandidate("details.signal_metadata.order_flow", signalMetadata?.order_flow);
    pushCandidate("details.flow_snapshot", details?.flow_snapshot);
  } else if (markerType === "signal_generated") {
    pushCandidate("details.flow_snapshot", details?.flow_snapshot);
    pushCandidate("details.signal_metadata.order_flow", signalMetadata?.order_flow);
    pushCandidate("details.metadata.order_flow", detailMetadata?.order_flow ?? metadataContext?.order_flow);
  } else if (EXIT_MARKER_TYPES.has(markerType)) {
    pushCandidate("details.signal_metadata.order_flow", signalMetadata?.order_flow);
    pushCandidate("details.flow_snapshot", details?.flow_snapshot);
    pushCandidate("details.metadata.order_flow", detailMetadata?.order_flow ?? metadataContext?.order_flow);
  } else {
    pushCandidate("details.flow_snapshot", details?.flow_snapshot);
    pushCandidate("details.signal_metadata.order_flow", signalMetadata?.order_flow);
    pushCandidate("details.metadata.order_flow", detailMetadata?.order_flow ?? metadataContext?.order_flow);
  }

  pushCandidate("details.order_flow", details?.order_flow);
  pushCandidate("marker.order_flow", marker?.order_flow);
  pushCandidate("details.market_context.l2", marketL2);

  return candidates;
};

const resolveL2Source = (
  marker: MaybeObjectRecord,
  details: MaybeObjectRecord,
  metadata: MaybeObjectRecord,
): L2SourceResolution => {
  const candidates = buildL2CandidateSources(marker, details, metadata);
  const candidateDiagnostics = candidates.map(({ sourcePath, source }) => {
    const availableMetrics = L2_DIAGNOSTIC_KEYS.filter(
      (metricKey) => getL2MetricFromSource(source, metricKey) !== null,
    );
    return {
      sourcePath,
      score: availableMetrics.length,
      availableMetrics,
    };
  });
  let best: (L2SourceCandidate & { score: number; candidateIndex: number }) | null = null;

  for (let idx = 0; idx < candidates.length; idx += 1) {
    const candidate = candidates[idx];
    const score = candidateDiagnostics[idx]?.score || 0;
    if (score <= 0) continue;
    if (!best || score > best.score) {
      best = { ...candidate, score, candidateIndex: idx };
    }
  }

  if (!best) {
    return {
      source: null,
      sourcePath: "n/a",
      candidateDiagnostics,
    };
  }

  return {
    source: best.source,
    sourcePath: best.sourcePath,
    candidateDiagnostics,
  };
};

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
  const candidates = [
    details?.intraday_levels,
    details?.metadata?.intraday_levels,
    details?.indicators?.intraday_levels,
    metadata?.intraday_levels,
    marker?.intraday_levels,
  ];
  const payload = candidates.find(
    (candidate) => candidate && typeof candidate === "object" && !Array.isArray(candidate),
  );
  if (!payload) {
    return { hasAny: false, enabled: true, stats: {}, volumeProfile: {}, latestEvent: null };
  }
  const stats =
    payload.stats && typeof payload.stats === "object" && !Array.isArray(payload.stats)
      ? payload.stats
      : {};
  const volumeProfile =
    payload.volume_profile &&
    typeof payload.volume_profile === "object" &&
    !Array.isArray(payload.volume_profile)
      ? payload.volume_profile
      : {};
  const latestEvent =
    payload.latest_event && typeof payload.latest_event === "object" ? payload.latest_event : null;
  return {
    hasAny: true,
    enabled: payload.enabled !== false,
    stats,
    volumeProfile,
    latestEvent,
  };
};

export const extractLevelContext = (
  marker: MaybeObjectRecord,
  details: MaybeObjectRecord,
  metadata: MaybeObjectRecord,
): LevelContextExtractResult => {
  const candidates = [
    details?.level_context,
    details?.metadata?.level_context,
    details?.signal_metadata?.level_context,
    metadata?.level_context,
    marker?.level_context,
  ];
  const payload = candidates.find(
    (candidate) => candidate && typeof candidate === "object" && !Array.isArray(candidate),
  );
  if (!payload) {
    return { hasAny: false, payload: {}, checks: {}, reasons: [] };
  }
  const checks =
    payload.checks && typeof payload.checks === "object" && !Array.isArray(payload.checks)
      ? payload.checks
      : {};
  const reasons = Array.isArray(payload.reasons)
    ? payload.reasons.map((item) => String(item || "")).filter(Boolean)
    : [];
  return {
    hasAny: true,
    payload,
    checks,
    reasons,
  };
};

export const extractEntryQualityDiagnostics = (
  marker: MaybeObjectRecord,
  details: MaybeObjectRecord,
  metadata: MaybeObjectRecord,
): EntryQualityDiagnosticsExtractResult => {
  const candidates = [
    details?.entry_quality_diagnostics,
    details?.metadata?.entry_quality_diagnostics,
    metadata?.entry_quality_diagnostics,
    marker?.entry_quality_diagnostics,
  ];
  const payload = candidates.find(
    (candidate) => candidate && typeof candidate === "object" && !Array.isArray(candidate),
  );
  if (!payload) {
    return { hasAny: false, payload: {}, tags: [] };
  }
  const tags = Array.isArray(payload.first_bar_stop_tags)
    ? payload.first_bar_stop_tags.map((item) => String(item || "")).filter(Boolean)
    : [];
  return {
    hasAny: true,
    payload,
    tags,
  };
};

export const extractDecisionLogPayload = (
  marker: MaybeObjectRecord,
  details: MaybeObjectRecord,
  metadata: MaybeObjectRecord,
): DecisionLogPayloadExtractResult => {
  const markerType = String(marker?.marker_type || "").trim();
  const marketContext =
    details?.market_context && typeof details.market_context === "object" ? details.market_context : null;
  const signalMetadata =
    markerType === "entry_executed"
      ? details?.metadata && typeof details.metadata === "object"
        ? details.metadata
        : null
      : details?.signal_metadata && typeof details.signal_metadata === "object"
        ? details.signal_metadata
        : null;
  const levelContext =
    details?.level_context && typeof details.level_context === "object"
      ? details.level_context
      : signalMetadata?.level_context && typeof signalMetadata.level_context === "object"
        ? signalMetadata.level_context
        : null;
  const intradayLevels =
    details?.intraday_levels && typeof details.intraday_levels === "object"
      ? details.intraday_levels
      : signalMetadata?.intraday_levels && typeof signalMetadata.intraday_levels === "object"
        ? signalMetadata.intraday_levels
        : null;
  const flowSnapshot = normalizeL2SourceSnapshot(
    resolveL2Source(marker, details, signalMetadata).source,
  );
  const entryQualityDiagnostics =
    details?.entry_quality_diagnostics && typeof details.entry_quality_diagnostics === "object"
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
  const decisionState =
    marketContext?.decision_state && typeof marketContext.decision_state === "object"
      ? marketContext.decision_state
      : null;

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

  const hasAny = Object.values(payload).some((value) => value != null);
  return {
    hasAny,
    payload,
  };
};

export type DecisionPanelRiskControlsResolution = ReturnType<typeof resolveRiskControls>;
export type DecisionPanelContextRiskResolution = ReturnType<typeof resolveContextRisk>;
export type DecisionPanelBreakEvenResolution = ReturnType<typeof resolveBreakEven>;
export type DecisionPanelL2DiagnosticsResult = ReturnType<typeof extractL2Diagnostics>;
export type DecisionPanelIntradayLevelsResult = ReturnType<typeof extractIntradayLevels>;
export type DecisionPanelLevelContextResult = ReturnType<typeof extractLevelContext>;
export type DecisionPanelEntryQualityDiagnosticsResult = ReturnType<
  typeof extractEntryQualityDiagnostics
>;
export type DecisionPanelDecisionLogResult = ReturnType<typeof extractDecisionLogPayload>;
