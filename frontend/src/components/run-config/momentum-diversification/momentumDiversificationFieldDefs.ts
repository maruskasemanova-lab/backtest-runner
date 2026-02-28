import type { MomentumConfigSlice, MomentumSleeveDraft } from "../momentumUtils";

type NumericParser = (value: number) => number;

export interface ToggleFieldDef<T extends object> {
  label: string;
  field: keyof T;
}

export interface TextFieldDef<T extends object> {
  label: string;
  field: keyof T;
  placeholder?: string;
  id?: string;
}

export interface NumericFieldDef<T extends object> {
  label: string;
  field: keyof T;
  min: number;
  max: number;
  step: number;
  id?: string;
  fallback?: number;
  parseValue?: NumericParser;
}

const asMinOneInteger = (value: number) => Math.max(1, Math.trunc(value));

export const MOMENTUM_OVERRIDE_TOGGLE_FIELDS: ToggleFieldDef<MomentumConfigSlice>[] = [
  { label: "Momentum Diversification Enabled", field: "momentum_diversification_enabled" },
  { label: "Require L2 Coverage", field: "momentum_require_l2_coverage" },
  { label: "Route Enabled", field: "momentum_route_enabled" },
  { label: "Route Requires L2 Coverage", field: "momentum_route_require_l2_coverage" },
  { label: "Fail-Fast Exit Enabled", field: "momentum_fail_fast_exit_enabled" },
];

export const MOMENTUM_OVERRIDE_NUMERIC_FIELDS: NumericFieldDef<MomentumConfigSlice>[] = [
  { id: "momentum_min_flow_score", label: "Min Flow Score", field: "momentum_min_flow_score", min: 0, max: 100, step: 0.5 },
  {
    id: "momentum_min_directional_consistency",
    label: "Min Directional Consistency",
    field: "momentum_min_directional_consistency",
    min: 0,
    max: 1,
    step: 0.01,
  },
  {
    id: "momentum_min_signed_aggression",
    label: "Min Signed Aggression",
    field: "momentum_min_signed_aggression",
    min: 0,
    max: 1,
    step: 0.01,
  },
  { id: "momentum_min_imbalance", label: "Min Imbalance", field: "momentum_min_imbalance", min: 0, max: 1, step: 0.01 },
  {
    id: "momentum_min_cvd",
    label: "Min CVD (Directional)",
    field: "momentum_min_cvd",
    min: -1_000_000_000,
    max: 1_000_000_000,
    step: 1,
  },
  {
    id: "momentum_min_directional_price_change_pct",
    label: "Min Directional Price Change %",
    field: "momentum_min_directional_price_change_pct",
    min: -100,
    max: 100,
    step: 0.01,
  },
  {
    id: "momentum_min_price_trend_efficiency",
    label: "Min Price Trend Efficiency",
    field: "momentum_min_price_trend_efficiency",
    min: 0,
    max: 1,
    step: 0.01,
  },
  {
    id: "momentum_min_last_bar_body_ratio",
    label: "Min Last Bar Body Ratio",
    field: "momentum_min_last_bar_body_ratio",
    min: 0,
    max: 1,
    step: 0.01,
  },
  {
    id: "momentum_min_last_bar_close_location",
    label: "Min Last Bar Close Location",
    field: "momentum_min_last_bar_close_location",
    min: 0,
    max: 1,
    step: 0.01,
  },
  {
    id: "momentum_min_delta_acceleration",
    label: "Min Delta Acceleration",
    field: "momentum_min_delta_acceleration",
    min: -1_000_000_000,
    max: 1_000_000_000,
    step: 1,
  },
  {
    id: "momentum_min_delta_price_divergence",
    label: "Min Delta-Price Divergence",
    field: "momentum_min_delta_price_divergence",
    min: -10,
    max: 10,
    step: 0.01,
  },
  {
    id: "momentum_route_flow_score_impulse",
    label: "Route Flow Score (Impulse)",
    field: "momentum_route_flow_score_impulse",
    min: 0,
    max: 100,
    step: 0.5,
  },
  {
    id: "momentum_fail_fast_max_bars",
    label: "Fail-Fast Max Bars",
    field: "momentum_fail_fast_max_bars",
    min: 1,
    max: 30,
    step: 1,
    parseValue: asMinOneInteger,
  },
  {
    id: "momentum_fail_fast_signed_aggression_max",
    label: "Fail-Fast Signed Aggression Max",
    field: "momentum_fail_fast_signed_aggression_max",
    min: -1,
    max: 0,
    step: 0.01,
  },
  {
    id: "momentum_fail_fast_book_pressure_max",
    label: "Fail-Fast Book Pressure Max",
    field: "momentum_fail_fast_book_pressure_max",
    min: -1,
    max: 0,
    step: 0.01,
  },
  {
    id: "momentum_fail_fast_directional_consistency_max",
    label: "Fail-Fast Directional Consistency Max",
    field: "momentum_fail_fast_directional_consistency_max",
    min: 0,
    max: 1,
    step: 0.01,
  },
];

export const MOMENTUM_OVERRIDE_PRIMARY_TEXT_FIELD: TextFieldDef<MomentumConfigSlice> = {
  id: "momentum_apply_to_strategies",
  label: "Apply To Strategies (CSV, optional)",
  field: "momentum_apply_to_strategies",
  placeholder: "momentum_flow,momentum",
};

export const MOMENTUM_OVERRIDE_MICRO_REGIME_TEXT_FIELDS: TextFieldDef<MomentumConfigSlice>[] = [
  {
    id: "momentum_allowed_micro_regimes",
    label: "Allowed Micro Regimes (CSV)",
    field: "momentum_allowed_micro_regimes",
    placeholder: "TRENDING_UP,BREAKOUT",
  },
  {
    id: "momentum_blocked_micro_regimes",
    label: "Blocked Micro Regimes (CSV)",
    field: "momentum_blocked_micro_regimes",
    placeholder: "CHOPPY,ABSORPTION",
  },
];

export const MOMENTUM_SLEEVE_TEXT_FIELDS: TextFieldDef<MomentumSleeveDraft>[] = [
  { label: "Sleeve ID", field: "sleeve_id", placeholder: "impulse" },
  {
    label: "Apply To Strategies (CSV)",
    field: "apply_to_strategies",
    placeholder: "momentum_flow,pullback",
  },
  {
    label: "Allowed Micro Regimes (CSV)",
    field: "allowed_micro_regimes",
    placeholder: "TRENDING_UP,BREAKOUT",
  },
  {
    label: "Blocked Micro Regimes (CSV)",
    field: "blocked_micro_regimes",
    placeholder: "CHOPPY,ABSORPTION",
  },
];

export const MOMENTUM_SLEEVE_ALLOCATION_FIELD: NumericFieldDef<MomentumSleeveDraft> = {
  label: "Allocation Weight (0-1)",
  field: "allocation_weight",
  min: 0,
  max: 1,
  step: 0.05,
  fallback: 0.5,
};

export const MOMENTUM_SLEEVE_TOGGLE_FIELDS: ToggleFieldDef<MomentumSleeveDraft>[] = [
  { label: "Enabled", field: "enabled" },
  { label: "Require L2 Coverage", field: "require_l2_coverage" },
  { label: "Route Enabled", field: "route_enabled" },
  { label: "Route Requires L2", field: "route_require_l2_coverage" },
  { label: "Fail-Fast Exit Enabled", field: "fail_fast_exit_enabled" },
];

export const MOMENTUM_SLEEVE_NUMERIC_FIELDS: NumericFieldDef<MomentumSleeveDraft>[] = [
  { label: "Min Flow Score", field: "min_flow_score", min: 0, max: 100, step: 0.5, fallback: 58 },
  {
    label: "Min Directional Consistency",
    field: "min_directional_consistency",
    min: 0,
    max: 1,
    step: 0.01,
    fallback: 0.45,
  },
  {
    label: "Min Signed Aggression",
    field: "min_signed_aggression",
    min: 0,
    max: 1,
    step: 0.01,
    fallback: 0.04,
  },
  { label: "Min Imbalance", field: "min_imbalance", min: 0, max: 1, step: 0.01, fallback: 0.02 },
  {
    label: "Min CVD (Directional)",
    field: "min_cvd",
    min: -1_000_000_000,
    max: 1_000_000_000,
    step: 1,
    fallback: 0,
  },
  {
    label: "Min Directional Price Change %",
    field: "min_directional_price_change_pct",
    min: -100,
    max: 100,
    step: 0.01,
    fallback: 0,
  },
  {
    label: "Min Price Trend Efficiency",
    field: "min_price_trend_efficiency",
    min: 0,
    max: 1,
    step: 0.01,
    fallback: 0,
  },
  {
    label: "Min Last Bar Body Ratio",
    field: "min_last_bar_body_ratio",
    min: 0,
    max: 1,
    step: 0.01,
    fallback: 0,
  },
  {
    label: "Min Last Bar Close Location",
    field: "min_last_bar_close_location",
    min: 0,
    max: 1,
    step: 0.01,
    fallback: 0,
  },
  {
    label: "Min Delta Acceleration",
    field: "min_delta_acceleration",
    min: -1_000_000_000,
    max: 1_000_000_000,
    step: 1,
    fallback: 0,
  },
  {
    label: "Min Delta-Price Divergence",
    field: "min_delta_price_divergence",
    min: -10,
    max: 10,
    step: 0.01,
    fallback: 0,
  },
  {
    label: "Route Flow Score (Impulse)",
    field: "route_flow_score_impulse",
    min: 0,
    max: 100,
    step: 0.5,
    fallback: 64,
  },
  {
    label: "Fail-Fast Max Bars",
    field: "fail_fast_max_bars",
    min: 1,
    max: 30,
    step: 1,
    fallback: 3,
    parseValue: asMinOneInteger,
  },
  {
    label: "Fail-Fast Signed Aggression Max",
    field: "fail_fast_signed_aggression_max",
    min: -1,
    max: 0,
    step: 0.01,
    fallback: -0.08,
  },
  {
    label: "Fail-Fast Book Pressure Max",
    field: "fail_fast_book_pressure_max",
    min: -1,
    max: 0,
    step: 0.01,
    fallback: -0.1,
  },
  {
    label: "Fail-Fast Directional Consistency Max",
    field: "fail_fast_directional_consistency_max",
    min: 0,
    max: 1,
    step: 0.01,
    fallback: 0.2,
  },
];
