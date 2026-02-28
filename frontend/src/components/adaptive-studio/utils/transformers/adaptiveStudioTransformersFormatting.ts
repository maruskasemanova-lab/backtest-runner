import {
  normalizeMaxActive,
  normalizeMode,
  normalizeNonNegativeInt,
  strategyLabel,
  toBoolean,
} from "./adaptiveStudioTransformersCore";

export const flowSummary = (strategies: unknown): string => {
  if (!Array.isArray(strategies) || strategies.length === 0) {
    return "none";
  }
  return strategies.slice(0, 3).map(strategyLabel).join(", ");
};

export const formatProfileTimestamp = (value: unknown): string => {
  if (!value) return "-";
  const parsed = Date.parse(String(value));
  if (Number.isNaN(parsed)) return String(value);
  return new Date(parsed).toLocaleString();
};

export const formatProfileCandidate = (candidate: unknown): string => {
  if (!candidate || typeof candidate !== "object") return "candidate unavailable";
  const candidateRow = candidate as Record<string, unknown>;
  const mode = normalizeMode(candidateRow.strategy_selection_mode);
  const maxActive = normalizeMaxActive(candidateRow.max_active_strategies, 3);
  const hysteresis = normalizeNonNegativeInt(candidateRow.min_active_bars_before_switch, 0);
  const cooldown = normalizeNonNegativeInt(candidateRow.switch_cooldown_bars, 0);
  const flowBias = toBoolean(candidateRow.flow_bias_enabled, true) ? "flow-bias on" : "flow-bias off";
  const fallback = toBoolean(candidateRow.use_ohlcv_fallbacks, true) ? "fallback on" : "fallback off";
  return `${mode === "all_enabled" ? "all enabled" : `adaptive top-${maxActive}`} | hysteresis ${hysteresis} | cooldown ${cooldown} | ${flowBias} | ${fallback}`;
};
export const formatV2VectorSummary = (candidate: unknown): string[] | null => {
  if (!candidate || typeof candidate !== "object") return null;
  const candidateRow = candidate as Record<string, unknown>;
  const parts: string[] = [];
  const strategies = candidateRow.enabled_strategies;
  if (Array.isArray(strategies) && strategies.length) {
    parts.push(`Strategies: ${strategies.join(", ")}`);
  }
  const regime = candidateRow.regime_filter;
  if (Array.isArray(regime) && regime.length) {
    parts.push(`Regime: ${regime.join(", ")}`);
  }
  if (candidateRow.l2_min_imbalance != null) {
    parts.push(`L2 imb: ${Number(candidateRow.l2_min_imbalance).toFixed(3)}`);
  }
  if (candidateRow.l2_min_delta != null) {
    parts.push(`L2 delta: ${candidateRow.l2_min_delta}`);
  }
  if (candidateRow.base_threshold != null) {
    parts.push(`Evidence thr: ${candidateRow.base_threshold}`);
  }
  if (candidateRow.min_confirming_sources != null) {
    parts.push(`Min sources: ${candidateRow.min_confirming_sources}`);
  }
  if (candidateRow.min_confidence != null) {
    parts.push(`Confidence: ${candidateRow.min_confidence}`);
  }
  if (candidateRow.atr_stop_multiplier != null) {
    parts.push(`ATR stop: ${candidateRow.atr_stop_multiplier}`);
  }
  if (candidateRow.rr_ratio != null) {
    parts.push(`R:R: ${candidateRow.rr_ratio}`);
  }
  const hours = candidateRow.trading_hours;
  if (Array.isArray(hours) && hours.length) {
    parts.push(`Hours: ${hours.join(",")}`);
  }
  if (candidateRow.adverse_flow_consistency != null) {
    parts.push(`FlowExitCons: ${candidateRow.adverse_flow_consistency}`);
  }
  if (candidateRow.adverse_book_pressure != null) {
    parts.push(`BookExitThr: ${candidateRow.adverse_book_pressure}`);
  }
  return parts.length ? parts : null;
};
