import {
  clamp,
  clampInt,
  normalizeSleeveId,
  parseCsvTokens,
  resolveRunnerApiBaseUrl,
  toCsvString,
} from "../../utils";

export type AOSOptimizationsRecord = Record<string, unknown>;

export const resolveRunnerUrl = (apiUrl: unknown): string => {
  const base = String(apiUrl || "").trim();
  return resolveRunnerApiBaseUrl(base);
};

export const safeObject = (value: unknown): AOSOptimizationsRecord => {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return {};
  }
  return value as AOSOptimizationsRecord;
};

export const safeArray = <T = unknown>(value: unknown): T[] =>
  Array.isArray(value) ? (value as T[]) : [];

export const createDefaultSleeveDraft = (index = 1) => ({
  sleeve_id: `sleeve_${index}`,
  enabled: true,
  allocation_weight: 0.5,
  apply_to_strategies: "momentum_flow",
  allowed_micro_regimes: "",
  blocked_micro_regimes: "",
  require_l2_coverage: true,
  route_enabled: true,
  route_require_l2_coverage: true,
  min_flow_score: 58,
  min_directional_consistency: 0.45,
  min_signed_aggression: 0.04,
  min_imbalance: 0.02,
  min_cvd: 0,
  min_directional_price_change_pct: 0,
  min_price_trend_efficiency: 0,
  min_last_bar_body_ratio: 0,
  min_last_bar_close_location: 0,
  min_delta_acceleration: 0,
  min_delta_price_divergence: 0,
  route_flow_score_impulse: 64,
  fail_fast_exit_enabled: true,
  fail_fast_max_bars: 3,
  fail_fast_signed_aggression_max: -0.08,
  fail_fast_book_pressure_max: -0.1,
  fail_fast_directional_consistency_max: 0.2,
});

export type AOSMomentumSleeveDraft = ReturnType<typeof createDefaultSleeveDraft>;

export const createDefaultMomentumDraft = () => ({
  enabled: true,
  require_l2_coverage: true,
  route_enabled: true,
  route_require_l2_coverage: true,
  min_flow_score: 58,
  min_directional_consistency: 0.45,
  min_signed_aggression: 0.04,
  min_imbalance: 0.02,
  min_cvd: 0,
  min_directional_price_change_pct: 0,
  min_price_trend_efficiency: 0,
  min_last_bar_body_ratio: 0,
  min_last_bar_close_location: 0,
  min_delta_acceleration: 0,
  min_delta_price_divergence: 0,
  route_flow_score_impulse: 64,
  fail_fast_exit_enabled: true,
  fail_fast_max_bars: 3,
  fail_fast_signed_aggression_max: -0.08,
  fail_fast_book_pressure_max: -0.1,
  fail_fast_directional_consistency_max: 0.2,
  apply_to_strategies: "momentum_flow",
  allowed_micro_regimes: "",
  blocked_micro_regimes: "",
  sleeves: [] as AOSMomentumSleeveDraft[],
});

export type AOSMomentumDraft = ReturnType<typeof createDefaultMomentumDraft>;

export const normalizeSleeveDraft = (
  raw: unknown,
  index: number,
): AOSMomentumSleeveDraft => {
  const source = safeObject(raw);
  return {
    ...createDefaultSleeveDraft(index + 1),
    sleeve_id: normalizeSleeveId(source.sleeve_id, `sleeve_${index + 1}`),
    enabled: !!source.enabled,
    allocation_weight: clamp(source.allocation_weight, 0.5, 0, 1),
    apply_to_strategies: toCsvString(source.apply_to_strategies, (v) => v.toLowerCase()),
    allowed_micro_regimes: toCsvString(source.allowed_micro_regimes, (v) => v.toUpperCase()),
    blocked_micro_regimes: toCsvString(source.blocked_micro_regimes, (v) => v.toUpperCase()),
    require_l2_coverage:
      typeof source.require_l2_coverage === "boolean" ? source.require_l2_coverage : true,
    route_enabled: typeof source.route_enabled === "boolean" ? source.route_enabled : true,
    route_require_l2_coverage:
      typeof source.route_require_l2_coverage === "boolean"
        ? source.route_require_l2_coverage
        : true,
    min_flow_score: clamp(source.min_flow_score, 58, 0, 100),
    min_directional_consistency: clamp(source.min_directional_consistency, 0.45, 0, 1),
    min_signed_aggression: clamp(source.min_signed_aggression, 0.04, 0, 1),
    min_imbalance: clamp(source.min_imbalance, 0.02, 0, 1),
    min_cvd: clamp(source.min_cvd, 0, -1_000_000_000, 1_000_000_000),
    min_directional_price_change_pct: clamp(source.min_directional_price_change_pct, 0, -100, 100),
    min_price_trend_efficiency: clamp(source.min_price_trend_efficiency, 0, 0, 1),
    min_last_bar_body_ratio: clamp(source.min_last_bar_body_ratio, 0, 0, 1),
    min_last_bar_close_location: clamp(source.min_last_bar_close_location, 0, 0, 1),
    min_delta_acceleration: clamp(source.min_delta_acceleration, 0, -1_000_000_000, 1_000_000_000),
    min_delta_price_divergence: clamp(source.min_delta_price_divergence, 0, -10, 10),
    route_flow_score_impulse: clamp(source.route_flow_score_impulse, 64, 0, 100),
    fail_fast_exit_enabled:
      typeof source.fail_fast_exit_enabled === "boolean" ? source.fail_fast_exit_enabled : true,
    fail_fast_max_bars: clampInt(source.fail_fast_max_bars, 3, 1, 30),
    fail_fast_signed_aggression_max: clamp(source.fail_fast_signed_aggression_max, -0.08, -1, 0),
    fail_fast_book_pressure_max: clamp(source.fail_fast_book_pressure_max, -0.1, -1, 0),
    fail_fast_directional_consistency_max: clamp(
      source.fail_fast_directional_consistency_max,
      0.2,
      0,
      1,
    ),
  };
};

export const normalizeMomentumDraft = (raw: unknown): AOSMomentumDraft => {
  const source = safeObject(raw);
  const base = createDefaultMomentumDraft();
  return {
    ...base,
    enabled: typeof source.enabled === "boolean" ? source.enabled : base.enabled,
    require_l2_coverage:
      typeof source.require_l2_coverage === "boolean"
        ? source.require_l2_coverage
        : base.require_l2_coverage,
    route_enabled:
      typeof source.route_enabled === "boolean" ? source.route_enabled : base.route_enabled,
    route_require_l2_coverage:
      typeof source.route_require_l2_coverage === "boolean"
        ? source.route_require_l2_coverage
        : base.route_require_l2_coverage,
    min_flow_score: clamp(source.min_flow_score, base.min_flow_score, 0, 100),
    min_directional_consistency: clamp(
      source.min_directional_consistency,
      base.min_directional_consistency,
      0,
      1,
    ),
    min_signed_aggression: clamp(source.min_signed_aggression, base.min_signed_aggression, 0, 1),
    min_imbalance: clamp(source.min_imbalance, base.min_imbalance, 0, 1),
    min_cvd: clamp(source.min_cvd, base.min_cvd, -1_000_000_000, 1_000_000_000),
    min_directional_price_change_pct: clamp(
      source.min_directional_price_change_pct,
      base.min_directional_price_change_pct,
      -100,
      100,
    ),
    min_price_trend_efficiency: clamp(
      source.min_price_trend_efficiency,
      base.min_price_trend_efficiency,
      0,
      1,
    ),
    min_last_bar_body_ratio: clamp(source.min_last_bar_body_ratio, base.min_last_bar_body_ratio, 0, 1),
    min_last_bar_close_location: clamp(
      source.min_last_bar_close_location,
      base.min_last_bar_close_location,
      0,
      1,
    ),
    min_delta_acceleration: clamp(
      source.min_delta_acceleration,
      base.min_delta_acceleration,
      -1_000_000_000,
      1_000_000_000,
    ),
    min_delta_price_divergence: clamp(
      source.min_delta_price_divergence,
      base.min_delta_price_divergence,
      -10,
      10,
    ),
    route_flow_score_impulse: clamp(source.route_flow_score_impulse, base.route_flow_score_impulse, 0, 100),
    fail_fast_exit_enabled:
      typeof source.fail_fast_exit_enabled === "boolean"
        ? source.fail_fast_exit_enabled
        : base.fail_fast_exit_enabled,
    fail_fast_max_bars: clampInt(source.fail_fast_max_bars, base.fail_fast_max_bars, 1, 30),
    fail_fast_signed_aggression_max: clamp(
      source.fail_fast_signed_aggression_max,
      base.fail_fast_signed_aggression_max,
      -1,
      0,
    ),
    fail_fast_book_pressure_max: clamp(
      source.fail_fast_book_pressure_max,
      base.fail_fast_book_pressure_max,
      -1,
      0,
    ),
    fail_fast_directional_consistency_max: clamp(
      source.fail_fast_directional_consistency_max,
      base.fail_fast_directional_consistency_max,
      0,
      1,
    ),
    apply_to_strategies: toCsvString(source.apply_to_strategies, (v) => v.toLowerCase()),
    allowed_micro_regimes: toCsvString(source.allowed_micro_regimes, (v) => v.toUpperCase()),
    blocked_micro_regimes: toCsvString(source.blocked_micro_regimes, (v) => v.toUpperCase()),
    sleeves: safeArray(source.sleeves).map((sleeve, index) => normalizeSleeveDraft(sleeve, index)),
  };
};

export const buildMomentumSleeveConfig = (
  draft: unknown,
  index: number,
): AOSOptimizationsRecord => {
  const source = safeObject(draft);
  const payload: AOSOptimizationsRecord = {
    sleeve_id: normalizeSleeveId(source.sleeve_id, `sleeve_${index + 1}`),
    enabled: !!source.enabled,
    allocation_weight: clamp(source.allocation_weight, 0.5, 0, 1),
    require_l2_coverage: !!source.require_l2_coverage,
    route_enabled: !!source.route_enabled,
    route_require_l2_coverage: !!source.route_require_l2_coverage,
    min_flow_score: clamp(source.min_flow_score, 58, 0, 100),
    min_directional_consistency: clamp(source.min_directional_consistency, 0.45, 0, 1),
    min_signed_aggression: clamp(source.min_signed_aggression, 0.04, 0, 1),
    min_imbalance: clamp(source.min_imbalance, 0.02, 0, 1),
    min_cvd: clamp(source.min_cvd, 0, -1_000_000_000, 1_000_000_000),
    min_directional_price_change_pct: clamp(source.min_directional_price_change_pct, 0, -100, 100),
    min_price_trend_efficiency: clamp(source.min_price_trend_efficiency, 0, 0, 1),
    min_last_bar_body_ratio: clamp(source.min_last_bar_body_ratio, 0, 0, 1),
    min_last_bar_close_location: clamp(source.min_last_bar_close_location, 0, 0, 1),
    min_delta_acceleration: clamp(source.min_delta_acceleration, 0, -1_000_000_000, 1_000_000_000),
    min_delta_price_divergence: clamp(source.min_delta_price_divergence, 0, -10, 10),
    route_flow_score_impulse: clamp(source.route_flow_score_impulse, 64, 0, 100),
    fail_fast_exit_enabled: !!source.fail_fast_exit_enabled,
    fail_fast_max_bars: clampInt(source.fail_fast_max_bars, 3, 1, 30),
    fail_fast_signed_aggression_max: clamp(source.fail_fast_signed_aggression_max, -0.08, -1, 0),
    fail_fast_book_pressure_max: clamp(source.fail_fast_book_pressure_max, -0.1, -1, 0),
    fail_fast_directional_consistency_max: clamp(
      source.fail_fast_directional_consistency_max,
      0.2,
      0,
      1,
    ),
  };

  const applyTo = parseCsvTokens(source.apply_to_strategies, (v) => v.toLowerCase());
  if (applyTo.length) payload.apply_to_strategies = applyTo;
  const allowed = parseCsvTokens(source.allowed_micro_regimes, (v) => v.toUpperCase());
  if (allowed.length) payload.allowed_micro_regimes = allowed;
  const blocked = parseCsvTokens(source.blocked_micro_regimes, (v) => v.toUpperCase());
  if (blocked.length) payload.blocked_micro_regimes = blocked;
  return payload;
};

export const buildMomentumConfigFromDraft = (draft: unknown): AOSOptimizationsRecord => {
  const source = safeObject(draft);
  const payload: AOSOptimizationsRecord = {
    enabled: !!source.enabled,
    require_l2_coverage: !!source.require_l2_coverage,
    route_enabled: !!source.route_enabled,
    route_require_l2_coverage: !!source.route_require_l2_coverage,
    min_flow_score: clamp(source.min_flow_score, 58, 0, 100),
    min_directional_consistency: clamp(source.min_directional_consistency, 0.45, 0, 1),
    min_signed_aggression: clamp(source.min_signed_aggression, 0.04, 0, 1),
    min_imbalance: clamp(source.min_imbalance, 0.02, 0, 1),
    min_cvd: clamp(source.min_cvd, 0, -1_000_000_000, 1_000_000_000),
    min_directional_price_change_pct: clamp(source.min_directional_price_change_pct, 0, -100, 100),
    min_price_trend_efficiency: clamp(source.min_price_trend_efficiency, 0, 0, 1),
    min_last_bar_body_ratio: clamp(source.min_last_bar_body_ratio, 0, 0, 1),
    min_last_bar_close_location: clamp(source.min_last_bar_close_location, 0, 0, 1),
    min_delta_acceleration: clamp(source.min_delta_acceleration, 0, -1_000_000_000, 1_000_000_000),
    min_delta_price_divergence: clamp(source.min_delta_price_divergence, 0, -10, 10),
    route_flow_score_impulse: clamp(source.route_flow_score_impulse, 64, 0, 100),
    fail_fast_exit_enabled: !!source.fail_fast_exit_enabled,
    fail_fast_max_bars: clampInt(source.fail_fast_max_bars, 3, 1, 30),
    fail_fast_signed_aggression_max: clamp(source.fail_fast_signed_aggression_max, -0.08, -1, 0),
    fail_fast_book_pressure_max: clamp(source.fail_fast_book_pressure_max, -0.1, -1, 0),
    fail_fast_directional_consistency_max: clamp(
      source.fail_fast_directional_consistency_max,
      0.2,
      0,
      1,
    ),
  };
  const applyTo = parseCsvTokens(source.apply_to_strategies, (v) => v.toLowerCase());
  if (applyTo.length) payload.apply_to_strategies = applyTo;
  const allowed = parseCsvTokens(source.allowed_micro_regimes, (v) => v.toUpperCase());
  if (allowed.length) payload.allowed_micro_regimes = allowed;
  const blocked = parseCsvTokens(source.blocked_micro_regimes, (v) => v.toUpperCase());
  if (blocked.length) payload.blocked_micro_regimes = blocked;

  const sleeves = safeArray(source.sleeves)
    .map((sleeve, index) => buildMomentumSleeveConfig(sleeve, index))
    .filter((item) => item && typeof item === "object");
  if (sleeves.length) payload.sleeves = sleeves;

  return payload;
};

export const mergeMomentumIntoTickerConfig = (
  tickerConfig: unknown,
  momentumDraft: unknown,
): AOSOptimizationsRecord => {
  const next = { ...safeObject(tickerConfig) };
  const adaptive = { ...safeObject(next.adaptive) };
  adaptive.momentum_diversification = buildMomentumConfigFromDraft(momentumDraft);
  next.adaptive = adaptive;
  return next;
};

export const parseTickerConfigText = (rawText: unknown): AOSOptimizationsRecord => {
  const text = String(rawText || "").trim();
  if (!text) return {};
  let parsed: unknown;
  try {
    parsed = JSON.parse(text);
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    throw new Error(`Invalid JSON: ${message}`);
  }
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("Ticker config JSON must be an object.");
  }
  return safeObject(parsed);
};
