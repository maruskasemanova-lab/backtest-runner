import type { StrategyConditionsPanelDataValue } from "./StrategyConditionsPanelData";
import { resolveContextRiskStrategyFloor } from "./strategyAnalyzerContextRiskFloors";
import type { ThresholdOverrides } from "./useStrategyAnalyzerThresholdOverrides";

type ActivationOverrideKey =
  | "base_threshold"
  | "min_margin_over_threshold"
  | "single_source_min_margin"
  | "min_confirming_sources"
  | "context_risk_min_room_pct"
  | "context_risk_min_effective_rr"
  | "intraday_levels_min_confluence_score"
  | "intraday_levels_rvol_min_threshold"
  | "intraday_levels_pullback_rvol_min_threshold"
  | "pullback_min_price_trend_efficiency"
  | "cost_aware_sweep_min_risk_pct";

export type ActivationMinimumUpdate = {
  key: ActivationOverrideKey;
  value: number;
};

function toFiniteNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return null;
}

function roundTo(value: number, decimals: number): number {
  const factor = 10 ** decimals;
  return Math.round(value * factor) / factor;
}

function normalizeOverrideValue(
  key: ActivationOverrideKey,
  value: number,
): number | null {
  if (!Number.isFinite(value)) return null;
  switch (key) {
    case "base_threshold":
      return roundTo(Math.max(0, value), 2);
    case "min_margin_over_threshold":
    case "single_source_min_margin":
      return roundTo(Math.max(0, Math.min(30, value)), 3);
    case "min_confirming_sources":
      return Math.max(0, Math.min(5, Math.round(value)));
    case "context_risk_min_room_pct":
    case "context_risk_min_effective_rr":
    case "intraday_levels_rvol_min_threshold":
    case "intraday_levels_pullback_rvol_min_threshold":
    case "cost_aware_sweep_min_risk_pct":
      return roundTo(Math.max(0, value), 4);
    case "intraday_levels_min_confluence_score":
      return Math.max(0, Math.min(10, Math.round(value)));
    case "pullback_min_price_trend_efficiency":
      return roundTo(Math.max(0, Math.min(1, value)), 4);
    default:
      return null;
  }
}

function pullLevelContext(data: StrategyConditionsPanelDataValue): Record<string, unknown> | null {
  const rejection = data.rejectionDetails;
  if (!rejection || typeof rejection !== "object") {
    const liveLevelContext = data.liveAnalysisSource?.level_context;
    return liveLevelContext && typeof liveLevelContext === "object"
      ? (liveLevelContext as Record<string, unknown>)
      : null;
  }
  const fromField = (rejection as Record<string, unknown>).level_context;
  if (fromField && typeof fromField === "object") return fromField as Record<string, unknown>;
  if ((rejection as Record<string, unknown>).gate === "intraday_levels_entry_quality") {
    return rejection as Record<string, unknown>;
  }
  const liveLevelContext = data.liveAnalysisSource?.level_context;
  if (liveLevelContext && typeof liveLevelContext === "object") {
    return liveLevelContext as Record<string, unknown>;
  }
  return null;
}

function maybeAssign(
  target: Partial<Record<ActivationOverrideKey, number>>,
  key: ActivationOverrideKey,
  value: number | null,
) {
  if (value == null || !Number.isFinite(value)) return;
  const normalized = normalizeOverrideValue(key, value);
  if (normalized == null) return;
  target[key] = normalized;
}

function extractConfirmingSourcesFromReasoning(reasoning: unknown): number | null {
  const text = typeof reasoning === "string" ? reasoning : "";
  if (!text) return null;

  const compactMatch = text.match(/confirming\s*=\s*(\d+)\s*\/\s*\d+/i);
  if (compactMatch) {
    const parsed = Number(compactMatch[1]);
    if (Number.isFinite(parsed)) return parsed;
  }

  const strictMatch = text.match(/confirming\s+sources\s+(\d+)\s*<\s*required\s+\d+/i);
  if (strictMatch) {
    const parsed = Number(strictMatch[1]);
    if (Number.isFinite(parsed)) return parsed;
  }

  const looseMatch = text.match(/confirming\s+sources\s*[:=]?\s*(\d+)/i);
  if (looseMatch) {
    const parsed = Number(looseMatch[1]);
    if (Number.isFinite(parsed)) return parsed;
  }

  return null;
}

export function resolveActivationMinimumUpdates({
  data,
  currentOverrides,
}: {
  data: StrategyConditionsPanelDataValue | null;
  currentOverrides?: ThresholdOverrides;
}): ActivationMinimumUpdate[] {
  if (!data) return [];

  const next: Partial<Record<ActivationOverrideKey, number>> = {};
  const combinedScore = toFiniteNumber(data.combinedScore);
  const rejection = data.rejectionDetails && typeof data.rejectionDetails === "object"
    ? (data.rejectionDetails as Record<string, unknown>)
    : null;
  const confirmingFromPayload = (
    toFiniteNumber(data.confirmingSources)
    ?? toFiniteNumber(rejection?.actual_confirming_sources)
    ?? extractConfirmingSourcesFromReasoning(rejection?.reasoning)
    ?? extractConfirmingSourcesFromReasoning(data.liveAnalysisSource?.signal_rejected?.reasoning)
  );
  maybeAssign(next, "min_confirming_sources", confirmingFromPayload);
  const rejectionDetails = rejection?.details && typeof rejection.details === "object"
    ? (rejection.details as Record<string, unknown>)
    : null;
  const levelContext = pullLevelContext(data);
  const levelStats = levelContext?.stats && typeof levelContext.stats === "object"
    ? (levelContext.stats as Record<string, unknown>)
    : null;
  const levelMarketActivity = levelContext?.market_activity && typeof levelContext.market_activity === "object"
    ? (levelContext.market_activity as Record<string, unknown>)
    : null;

  const modelGapRaw = toFiniteNumber(rejection?.score_minus_model_threshold)
    ?? toFiniteNumber(data.liveAnalysisSource?.layer_scores?.score_minus_model_threshold)
    ?? (
      combinedScore != null && toFiniteNumber(data.threshold) != null
        ? combinedScore - Number(data.threshold)
        : null
    );
  const minimumMarginForActivation = modelGapRaw == null ? null : Math.max(0, modelGapRaw);
  maybeAssign(next, "min_margin_over_threshold", minimumMarginForActivation);
  maybeAssign(next, "single_source_min_margin", minimumMarginForActivation);

  const derivedBaseThreshold = (
    combinedScore != null && minimumMarginForActivation != null
      ? combinedScore - minimumMarginForActivation
      : toFiniteNumber(data.threshold)
  );
  maybeAssign(next, "base_threshold", derivedBaseThreshold);

  const roomPct = toFiniteNumber((data.contextRisk as Record<string, unknown> | null)?.room_pct);
  const effectiveRr = toFiniteNumber((data.contextRisk as Record<string, unknown> | null)?.effective_rr);
  const contextRiskStrategyFloor = resolveContextRiskStrategyFloor(data.selectedStrategy);
  maybeAssign(
    next,
    "context_risk_min_room_pct",
    roomPct == null
      ? null
      : Math.max(contextRiskStrategyFloor?.minRoomPct ?? 0, roomPct),
  );
  maybeAssign(
    next,
    "context_risk_min_effective_rr",
    effectiveRr == null
      ? null
      : Math.max(contextRiskStrategyFloor?.minEffectiveRr ?? 0, effectiveRr),
  );

  const confluenceScore = toFiniteNumber(levelStats?.near_confluence_score);
  maybeAssign(next, "intraday_levels_min_confluence_score", confluenceScore);

  const currentRvol = toFiniteNumber(levelMarketActivity?.rvol);
  maybeAssign(next, "intraday_levels_rvol_min_threshold", currentRvol);
  maybeAssign(next, "intraday_levels_pullback_rvol_min_threshold", currentRvol);

  const trendEfficiency = toFiniteNumber(rejectionDetails?.trend_efficiency);
  maybeAssign(next, "pullback_min_price_trend_efficiency", trendEfficiency);

  const riskPct = toFiniteNumber(rejection?.risk_pct);
  maybeAssign(next, "cost_aware_sweep_min_risk_pct", riskPct);

  const updates: ActivationMinimumUpdate[] = [];
  for (const [key, value] of Object.entries(next) as Array<[ActivationOverrideKey, number]>) {
    const current = currentOverrides?.[key];
    if (typeof current === "number" && Math.abs(current - value) < 1e-6) {
      continue;
    }
    updates.push({ key, value });
  }
  return updates;
}
