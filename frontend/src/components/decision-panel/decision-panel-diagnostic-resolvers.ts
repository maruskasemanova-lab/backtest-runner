import { toFiniteNumber } from "./decision-panel-utils";
import type {
  BaseResolutionParams,
  ContextRiskResolutionParams,
  L2SourceCandidate,
  L2SourceResolution,
  MaybeObjectRecord,
  ObjectRecord,
  ResolutionCandidate,
  ResolutionResult,
} from "./decision-panel-diagnostic-types";

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

export const getL2MetricFromSource = (source: unknown, metricKey: string): number | null => {
  if (!isObjectRecord(source)) return null;
  const direct = toFiniteNumber(source[metricKey]);
  if (direct !== null) return direct;
  const prefixed = toFiniteNumber(source[`l2_${metricKey}`]);
  if (prefixed !== null) return prefixed;
  return null;
};

export const getBooleanMetricFromSource = (source: unknown, metricKey: string): boolean | null => {
  if (!isObjectRecord(source)) return null;
  const direct = source[metricKey];
  if (typeof direct === "boolean") return direct;
  const prefixed = source[`l2_${metricKey}`];
  if (typeof prefixed === "boolean") return prefixed;
  return null;
};

export const normalizeL2SourceSnapshot = (source: unknown): ObjectRecord | null => {
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
    { path: "risk_controls", value: details?.risk_controls ?? signalMetadata?.risk_controls ?? marketContext?.risk_controls }, // Fallback to details payload
  ];
};

const selectObjectCandidate = (
  candidates: ResolutionCandidate[],
): { path: string; value: ObjectRecord } | null => {
  const selected = candidates.find(
    (candidate): candidate is ResolutionCandidate & { value: ObjectRecord } =>
      isObjectRecord(candidate.value),
  );
  return selected ? { path: selected.path, value: selected.value } : null;
};

export const resolveRiskControls = (params: BaseResolutionParams): ResolutionResult => {
  const candidates = buildRiskControlsCandidates(params);
  const selected = selectObjectCandidate(candidates);
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
    { path: "signal_metadata.context_risk", value: signalMetadata?.context_risk },
    { path: "market_context.context_risk", value: marketContext?.context_risk },
  ];
};

export const resolveContextRisk = (params: ContextRiskResolutionParams): ResolutionResult => {
  const candidates = buildContextRiskCandidates(params);
  const selected = selectObjectCandidate(candidates);
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
  { path: "break_even", value: details?.break_even ?? signalMetadata?.break_even ?? marketContext?.break_even },
];

export const resolveBreakEven = (params: BaseResolutionParams): ResolutionResult => {
  const candidates = buildBreakEvenCandidates(params);
  const selected = selectObjectCandidate(candidates);
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

export const resolveL2Source = (
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
  let best: (L2SourceCandidate & { score: number }) | null = null;

  for (let idx = 0; idx < candidates.length; idx += 1) {
    const candidate = candidates[idx];
    const score = candidateDiagnostics[idx]?.score || 0;
    if (score <= 0) continue;
    if (!best || score > best.score) {
      best = { ...candidate, score };
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
