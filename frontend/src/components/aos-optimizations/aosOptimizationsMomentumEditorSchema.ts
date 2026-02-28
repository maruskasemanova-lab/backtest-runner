import {
  createDefaultMomentumDraft,
  createDefaultSleeveDraft,
} from "./aosOptimizationsMomentum";

type ToggleFieldConfig = {
  field: string;
  label: string;
};

type NumberFieldConfig = {
  field: string;
  label: string;
  min: string;
  max: string;
  step: string;
};

type TextFieldConfig = {
  field: string;
  label: string;
  placeholder: string;
};

export const MOMENTUM_EDITOR_CONTAINER_STYLE = {
  border: "1px solid var(--border-color)",
  borderRadius: "6px",
  padding: "12px",
  display: "flex",
  flexDirection: "column",
  gap: "10px",
  background: "var(--bg-secondary)",
} as const;

export const MOMENTUM_ACTIONS_STYLE = {
  display: "flex",
  flexWrap: "wrap",
  gap: "8px",
} as const;

export const MOMENTUM_TOGGLE_GRID_STYLE = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
  gap: "8px",
} as const;

export const MOMENTUM_NUMERIC_GRID_STYLE = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(185px, 1fr))",
  gap: "10px",
} as const;

export const MOMENTUM_TEXT_GRID_STYLE = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
  gap: "10px",
} as const;

export const MOMENTUM_SLEEVES_PANEL_STYLE = {
  border: "1px solid var(--border-color)",
  borderRadius: "6px",
  padding: "10px",
  background: "var(--bg-primary)",
} as const;

export const MOMENTUM_SLEEVE_CARD_STYLE = {
  border: "1px solid var(--border-color)",
  borderRadius: "6px",
  padding: "10px",
  background: "var(--bg-secondary)",
} as const;

export const MOMENTUM_SECTION_HEADER_STYLE = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  marginBottom: "8px",
} as const;

export const MOMENTUM_SLEEVE_META_GRID_STYLE = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))",
  gap: "8px",
} as const;

export const MOMENTUM_SLEEVE_TOGGLE_GRID_STYLE = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))",
  gap: "8px",
  marginBottom: "8px",
} as const;

export const MOMENTUM_SLEEVE_NUMERIC_GRID_STYLE = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(175px, 1fr))",
  gap: "8px",
} as const;

export const MOMENTUM_NOTICE_STYLE = {
  color: "var(--accent-green)",
  fontSize: "0.78rem",
} as const;

export const MOMENTUM_ERROR_STYLE = {
  color: "var(--accent-red)",
  fontSize: "0.78rem",
} as const;

export const MOMENTUM_DIRTY_STYLE = {
  color: "var(--accent-yellow)",
  fontSize: "0.76rem",
} as const;

export const MOMENTUM_EMPTY_SLEEVES_STYLE = {
  color: "var(--text-muted)",
  fontSize: "0.75rem",
} as const;

export const MOMENTUM_BOOLEAN_FIELDS: ToggleFieldConfig[] = [
  { field: "enabled", label: "Enabled" },
  { field: "require_l2_coverage", label: "Require L2 Coverage" },
  { field: "route_enabled", label: "Route Enabled" },
  { field: "route_require_l2_coverage", label: "Route Requires L2" },
  { field: "fail_fast_exit_enabled", label: "Fail-Fast Enabled" },
];

export const MOMENTUM_NUMERIC_FIELDS: NumberFieldConfig[] = [
  { field: "min_flow_score", label: "Min Flow Score", min: "0", max: "100", step: "0.5" },
  {
    field: "min_directional_consistency",
    label: "Min Directional Consistency",
    min: "0",
    max: "1",
    step: "0.01",
  },
  {
    field: "min_signed_aggression",
    label: "Min Signed Aggression",
    min: "0",
    max: "1",
    step: "0.01",
  },
  { field: "min_imbalance", label: "Min Imbalance", min: "0", max: "1", step: "0.01" },
  {
    field: "min_cvd",
    label: "Min CVD (Directional)",
    min: "-1000000000",
    max: "1000000000",
    step: "1",
  },
  {
    field: "min_directional_price_change_pct",
    label: "Min Directional Price Change %",
    min: "-100",
    max: "100",
    step: "0.01",
  },
  {
    field: "min_price_trend_efficiency",
    label: "Min Price Trend Efficiency",
    min: "0",
    max: "1",
    step: "0.01",
  },
  {
    field: "min_last_bar_body_ratio",
    label: "Min Last Bar Body Ratio",
    min: "0",
    max: "1",
    step: "0.01",
  },
  {
    field: "min_last_bar_close_location",
    label: "Min Last Bar Close Location",
    min: "0",
    max: "1",
    step: "0.01",
  },
  {
    field: "min_delta_acceleration",
    label: "Min Delta Acceleration",
    min: "-1000000000",
    max: "1000000000",
    step: "1",
  },
  {
    field: "min_delta_price_divergence",
    label: "Min Delta-Price Divergence",
    min: "-10",
    max: "10",
    step: "0.01",
  },
  {
    field: "route_flow_score_impulse",
    label: "Route Flow Score (Impulse)",
    min: "0",
    max: "100",
    step: "0.5",
  },
  {
    field: "fail_fast_max_bars",
    label: "Fail-Fast Max Bars",
    min: "1",
    max: "30",
    step: "1",
  },
  {
    field: "fail_fast_signed_aggression_max",
    label: "Fail-Fast Signed Aggression Max",
    min: "-1",
    max: "0",
    step: "0.01",
  },
  {
    field: "fail_fast_book_pressure_max",
    label: "Fail-Fast Book Pressure Max",
    min: "-1",
    max: "0",
    step: "0.01",
  },
  {
    field: "fail_fast_directional_consistency_max",
    label: "Fail-Fast Directional Consistency Max",
    min: "0",
    max: "1",
    step: "0.01",
  },
];

export const MOMENTUM_TEXT_FIELDS: TextFieldConfig[] = [
  {
    field: "apply_to_strategies",
    label: "Apply To Strategies (CSV)",
    placeholder: "momentum_flow,pullback",
  },
  {
    field: "allowed_micro_regimes",
    label: "Allowed Micro Regimes (CSV)",
    placeholder: "TRENDING_UP,BREAKOUT",
  },
  {
    field: "blocked_micro_regimes",
    label: "Blocked Micro Regimes (CSV)",
    placeholder: "CHOPPY,ABSORPTION",
  },
];

export const MOMENTUM_SLEEVE_DEFAULTS = createDefaultSleeveDraft();
export const MOMENTUM_DRAFT_DEFAULTS = createDefaultMomentumDraft();
