import { normalizeSleeveId, parseCsvTokens, toFiniteNumber } from "../../utils";

export interface MomentumSleeveDraft {
  sleeve_id?: string;
  enabled?: boolean;
  allocation_weight?: number;
  apply_to_strategies?: string;
  allowed_micro_regimes?: string;
  blocked_micro_regimes?: string;
  require_l2_coverage?: boolean;
  route_enabled?: boolean;
  route_require_l2_coverage?: boolean;
  min_flow_score?: number;
  min_directional_consistency?: number;
  min_signed_aggression?: number;
  min_imbalance?: number;
  min_cvd?: number;
  min_directional_price_change_pct?: number;
  min_price_trend_efficiency?: number;
  min_last_bar_body_ratio?: number;
  min_last_bar_close_location?: number;
  min_delta_acceleration?: number;
  min_delta_price_divergence?: number;
  route_flow_score_impulse?: number;
  fail_fast_exit_enabled?: boolean;
  fail_fast_max_bars?: number;
  fail_fast_signed_aggression_max?: number;
  fail_fast_book_pressure_max?: number;
  fail_fast_directional_consistency_max?: number;
}

export interface MomentumConfigSlice {
  momentum_diversification_override_enabled?: boolean;
  momentum_diversification_enabled?: boolean;
  momentum_require_l2_coverage?: boolean;
  momentum_route_enabled?: boolean;
  momentum_route_require_l2_coverage?: boolean;
  momentum_min_flow_score?: number;
  momentum_min_directional_consistency?: number;
  momentum_min_signed_aggression?: number;
  momentum_min_imbalance?: number;
  momentum_min_cvd?: number;
  momentum_min_directional_price_change_pct?: number;
  momentum_min_price_trend_efficiency?: number;
  momentum_min_last_bar_body_ratio?: number;
  momentum_min_last_bar_close_location?: number;
  momentum_min_delta_acceleration?: number;
  momentum_min_delta_price_divergence?: number;
  momentum_route_flow_score_impulse?: number;
  momentum_fail_fast_exit_enabled?: boolean;
  momentum_fail_fast_max_bars?: number;
  momentum_fail_fast_signed_aggression_max?: number;
  momentum_fail_fast_book_pressure_max?: number;
  momentum_fail_fast_directional_consistency_max?: number;
  momentum_apply_to_strategies?: string;
  momentum_allowed_micro_regimes?: string;
  momentum_blocked_micro_regimes?: string;
  momentum_sleeves?: MomentumSleeveDraft[];
}

const clamp = (value: unknown, fallback: number, min: number, max: number): number => {
  return Math.max(min, Math.min(max, toFiniteNumber(value, fallback)));
};

const clampInt = (value: unknown, fallback: number, min: number, max: number): number => {
  return Math.max(min, Math.min(max, Math.trunc(toFiniteNumber(value, fallback))));
};

export const createDefaultMomentumSleeveDraft = (index = 1): MomentumSleeveDraft => ({
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

export const buildMomentumSleevePayload = (
  sleeve: MomentumSleeveDraft | null | undefined,
  index: number,
): Record<string, unknown> => {
  const payload: Record<string, unknown> = {
    sleeve_id: normalizeSleeveId(sleeve?.sleeve_id, `sleeve_${index + 1}`),
    enabled: !!sleeve?.enabled,
    allocation_weight: clamp(sleeve?.allocation_weight, 0.5, 0, 1),
    require_l2_coverage: !!sleeve?.require_l2_coverage,
    route_enabled: !!sleeve?.route_enabled,
    route_require_l2_coverage: !!sleeve?.route_require_l2_coverage,
    min_flow_score: clamp(sleeve?.min_flow_score, 0, 0, 100),
    min_directional_consistency: clamp(sleeve?.min_directional_consistency, 0, 0, 1),
    min_signed_aggression: clamp(sleeve?.min_signed_aggression, 0, 0, 1),
    min_imbalance: clamp(sleeve?.min_imbalance, 0, 0, 1),
    min_cvd: clamp(sleeve?.min_cvd, 0, -1_000_000_000, 1_000_000_000),
    min_directional_price_change_pct: clamp(
      sleeve?.min_directional_price_change_pct,
      0,
      -100,
      100,
    ),
    min_price_trend_efficiency: clamp(sleeve?.min_price_trend_efficiency, 0, 0, 1),
    min_last_bar_body_ratio: clamp(sleeve?.min_last_bar_body_ratio, 0, 0, 1),
    min_last_bar_close_location: clamp(sleeve?.min_last_bar_close_location, 0, 0, 1),
    min_delta_acceleration: clamp(
      sleeve?.min_delta_acceleration,
      0,
      -1_000_000_000,
      1_000_000_000,
    ),
    min_delta_price_divergence: clamp(sleeve?.min_delta_price_divergence, 0, -10, 10),
    route_flow_score_impulse: clamp(sleeve?.route_flow_score_impulse, 0, 0, 100),
    fail_fast_exit_enabled: !!sleeve?.fail_fast_exit_enabled,
    fail_fast_max_bars: clampInt(sleeve?.fail_fast_max_bars, 3, 1, 30),
    fail_fast_signed_aggression_max: clamp(
      sleeve?.fail_fast_signed_aggression_max,
      -0.05,
      -1,
      0,
    ),
    fail_fast_book_pressure_max: clamp(sleeve?.fail_fast_book_pressure_max, -0.08, -1, 0),
    fail_fast_directional_consistency_max: clamp(
      sleeve?.fail_fast_directional_consistency_max,
      0.25,
      0,
      1,
    ),
  };

  const applyToStrategies = parseCsvTokens(sleeve?.apply_to_strategies, (token) =>
    token.toLowerCase(),
  );
  if (applyToStrategies.length) {
    payload.apply_to_strategies = applyToStrategies;
  }

  const allowedMicro = parseCsvTokens(sleeve?.allowed_micro_regimes, (token) =>
    token.toUpperCase(),
  );
  if (allowedMicro.length) {
    payload.allowed_micro_regimes = allowedMicro;
  }

  const blockedMicro = parseCsvTokens(sleeve?.blocked_micro_regimes, (token) =>
    token.toUpperCase(),
  );
  if (blockedMicro.length) {
    payload.blocked_micro_regimes = blockedMicro;
  }

  return payload;
};

export const buildMomentumDiversificationOverridePayload = (
  config: MomentumConfigSlice,
): Record<string, unknown> => {
  const payload: Record<string, unknown> = {
    enabled: !!config.momentum_diversification_enabled,
    require_l2_coverage: !!config.momentum_require_l2_coverage,
    route_enabled: !!config.momentum_route_enabled,
    route_require_l2_coverage: !!config.momentum_route_require_l2_coverage,
    min_flow_score: clamp(config.momentum_min_flow_score, 0, 0, 100),
    min_directional_consistency: clamp(config.momentum_min_directional_consistency, 0, 0, 1),
    min_signed_aggression: clamp(config.momentum_min_signed_aggression, 0, 0, 1),
    min_imbalance: clamp(config.momentum_min_imbalance, 0, 0, 1),
    min_cvd: clamp(config.momentum_min_cvd, 0, -1_000_000_000, 1_000_000_000),
    min_directional_price_change_pct: clamp(
      config.momentum_min_directional_price_change_pct,
      0,
      -100,
      100,
    ),
    min_price_trend_efficiency: clamp(config.momentum_min_price_trend_efficiency, 0, 0, 1),
    min_last_bar_body_ratio: clamp(config.momentum_min_last_bar_body_ratio, 0, 0, 1),
    min_last_bar_close_location: clamp(config.momentum_min_last_bar_close_location, 0, 0, 1),
    min_delta_acceleration: clamp(
      config.momentum_min_delta_acceleration,
      0,
      -1_000_000_000,
      1_000_000_000,
    ),
    min_delta_price_divergence: clamp(config.momentum_min_delta_price_divergence, 0, -10, 10),
    route_flow_score_impulse: clamp(config.momentum_route_flow_score_impulse, 0, 0, 100),
    fail_fast_exit_enabled: !!config.momentum_fail_fast_exit_enabled,
    fail_fast_max_bars: clampInt(config.momentum_fail_fast_max_bars, 3, 1, 30),
    fail_fast_signed_aggression_max: clamp(
      config.momentum_fail_fast_signed_aggression_max,
      -0.05,
      -1,
      0,
    ),
    fail_fast_book_pressure_max: clamp(config.momentum_fail_fast_book_pressure_max, -0.08, -1, 0),
    fail_fast_directional_consistency_max: clamp(
      config.momentum_fail_fast_directional_consistency_max,
      0.25,
      0,
      1,
    ),
  };

  const applyToStrategies = parseCsvTokens(config.momentum_apply_to_strategies, (token) =>
    token.toLowerCase(),
  );
  if (applyToStrategies.length) {
    payload.apply_to_strategies = applyToStrategies;
  }

  const allowedMicro = parseCsvTokens(config.momentum_allowed_micro_regimes, (token) =>
    token.toUpperCase(),
  );
  if (allowedMicro.length) {
    payload.allowed_micro_regimes = allowedMicro;
  }

  const blockedMicro = parseCsvTokens(config.momentum_blocked_micro_regimes, (token) =>
    token.toUpperCase(),
  );
  if (blockedMicro.length) {
    payload.blocked_micro_regimes = blockedMicro;
  }

  const sleeveRows = Array.isArray(config.momentum_sleeves) ? config.momentum_sleeves : [];
  const sleeves = sleeveRows
    .map((row, index) => buildMomentumSleevePayload(row, index))
    .filter((row) => row && typeof row === "object");
  if (sleeves.length) {
    payload.sleeves = sleeves;
  }

  return payload;
};
