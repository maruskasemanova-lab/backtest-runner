// ─── Event names for bidirectional sync with RunConfig ───
export const EXEC_MODULE_TOGGLE_EVENT = "execution-module-toggle";
export const EXEC_CONFIG_SNAPSHOT_EVENT = "execution-config-snapshot";
export const EXEC_CONFIG_SNAPSHOT_REQUEST_EVENT = "execution-config-snapshot-request";

/** Metadata for each execution module. */
export const EXEC_MODULE_META: Record<
  string,
  {
    label: string;
    description: string;
    category: "risk" | "exit" | "flow" | "engine";
    configKey: string; // boolean key in RunConfig state
  }
> = {
  adverse_flow_exit: {
    label: "Adverse Flow Exit",
    description:
      "Monitors real-time order flow and exits the trade when aggressive flow turns against your position. Protects from sudden institutional selling/buying pressure.",
    category: "exit",
    configKey: "adverse_flow_exit_enabled",
  },
  l2_confirmation_gate: {
    label: "L2 Confirmation Gate",
    description:
      "Requires Level 2 microstructure confirmation before any trade entry — checks imbalance, signed aggression, directional consistency across a lookback window.",
    category: "flow",
    configKey: "l2_confirm_enabled",
  },
  trailing_stop: {
    label: "Trailing Stop",
    description:
      "Activates a trailing stop-loss after the trade reaches a profit threshold. Includes break-even protection and optional activation during choppy regimes.",
    category: "risk",
    configKey: "trailing_enabled_in_choppy",
  },
  momentum_route: {
    label: "Momentum Route",
    description:
      "Routes momentum strategy signals through an L2 flow scoring filter. Only lets high-flow-score momentum trades through, reducing false breakouts.",
    category: "flow",
    configKey: "momentum_route_enabled",
  },
  momentum_fail_fast: {
    label: "Momentum Fail-Fast",
    description:
      "Exits momentum trades early when post-entry flow metrics deteriorate — aggression reverses, book pressure drops, or directional consistency collapses.",
    category: "exit",
    configKey: "momentum_fail_fast_exit_enabled",
  },
  momentum_diversification: {
    label: "Momentum Diversification",
    description:
      "Distributes momentum exposure across multiple strategy sleeves with per-sleeve flow scoring, preventing concentration risk in a single momentum signal.",
    category: "flow",
    configKey: "momentum_diversification_enabled",
  },
  aos_auto_apply: {
    label: "AOS Auto-Apply",
    description:
      "Automatically applies Adaptive Orchestration System optimizations when a backtest run starts — adjusts strategy weights and parameters based on recent regime analysis.",
    category: "engine",
    configKey: "apply_aos_optimizations_on_start",
  },
};

export type ModuleSettingField =
  | {
      type: "number";
      configKey: string;
      label: string;
      min?: number;
      max?: number;
      step?: number;
      integer?: boolean;
      hint?: string;
      disabledWhen?: (config: Record<string, any>) => boolean;
    }
  | {
      type: "checkbox";
      configKey: string;
      label: string;
      hint?: string;
      disabledWhen?: (config: Record<string, any>) => boolean;
    }
  | {
      type: "select";
      configKey: string;
      label: string;
      options: Array<{ value: string; label: string }>;
      hint?: string;
      disabledWhen?: (config: Record<string, any>) => boolean;
    }
  | {
      type: "text";
      configKey: string;
      label: string;
      placeholder?: string;
      hint?: string;
      disabledWhen?: (config: Record<string, any>) => boolean;
    };

export const MODULE_SETTING_FIELDS: Record<string, ModuleSettingField[]> = {
  trailing_stop: [
    { type: "number", configKey: "risk_per_trade_pct", label: "Risk Per Trade (%)", min: 0.1, max: 10, step: 0.1 },
    {
      type: "number",
      configKey: "max_position_notional_pct",
      label: "Max Position Notional (%)",
      min: 1,
      max: 100,
      step: 1,
    },
    {
      type: "number",
      configKey: "max_fill_participation_rate",
      label: "Max Fill Participation (0-1)",
      min: 0.01,
      max: 1,
      step: 0.01,
    },
    { type: "number", configKey: "min_fill_ratio", label: "Min Fill Ratio (0-1)", min: 0.01, max: 1, step: 0.01 },
    { type: "number", configKey: "time_exit_bars", label: "Time Exit (bars)", min: 1, step: 1, integer: true },
    { type: "number", configKey: "trailing_stop_pct", label: "Global Trailing Stop (%)", min: 0, max: 5, step: 0.01 },
    {
      type: "select",
      configKey: "stop_loss_mode",
      label: "Stop-Loss Mode",
      options: [
        { value: "strategy", label: "strategy" },
        { value: "fixed", label: "fixed" },
        { value: "capped", label: "capped" },
      ],
    },
    {
      type: "number",
      configKey: "fixed_stop_loss_pct",
      label: "Fixed Stop-Loss (%)",
      min: 0.01,
      max: 5,
      step: 0.05,
      disabledWhen: (config) => String(config.stop_loss_mode || "strategy") === "strategy",
    },
    { type: "number", configKey: "global_exit_rr_ratio", label: "Global Exit RR Ratio", min: 0, max: 10, step: 0.05 },
    {
      type: "number",
      configKey: "global_risk_atr_stop_multiplier",
      label: "Global Risk ATR Stop Multiplier",
      min: 0,
      max: 10,
      step: 0.05,
    },
    {
      type: "number",
      configKey: "global_risk_volume_stop_pct",
      label: "Global Risk Volume Stop (%)",
      min: 0,
      max: 10,
      step: 0.05,
    },
    {
      type: "number",
      configKey: "global_risk_min_stop_loss_pct",
      label: "Global Risk Min Stop-Loss (%)",
      min: 0,
      max: 5,
      step: 0.01,
    },
    {
      type: "number",
      configKey: "trailing_activation_pct",
      label: "Break-even Activation (% MFE)",
      min: 0,
      max: 5,
      step: 0.01,
    },
    {
      type: "number",
      configKey: "break_even_buffer_pct",
      label: "Break-even Buffer (%)",
      min: 0,
      max: 2,
      step: 0.01,
    },
    {
      type: "number",
      configKey: "break_even_min_hold_bars",
      label: "Break-even Min Hold (bars)",
      min: 1,
      step: 1,
      integer: true,
    },
  ],
  adverse_flow_exit: [
    {
      type: "number",
      configKey: "adverse_flow_threshold",
      label: "Adverse Flow Threshold",
      min: 0.02,
      max: 1,
      step: 0.01,
    },
    {
      type: "number",
      configKey: "adverse_flow_min_hold_bars",
      label: "Adverse Flow Min Hold (bars)",
      min: 1,
      step: 1,
      integer: true,
    },
  ],
  l2_confirmation_gate: [
    { type: "number", configKey: "l2_min_imbalance", label: "Min Imbalance", min: 0, step: 0.01 },
    {
      type: "number",
      configKey: "l2_min_signed_aggression",
      label: "Min Signed Aggression",
      min: 0,
      step: 0.01,
    },
    {
      type: "number",
      configKey: "l2_min_directional_consistency",
      label: "Min Directional Consistency",
      min: 0,
      step: 0.01,
    },
    { type: "number", configKey: "l2_lookback_bars", label: "Lookback Bars", min: 1, step: 1, integer: true },
  ],
  momentum_route: [
    {
      type: "number",
      configKey: "momentum_min_flow_score",
      label: "Min Flow Score",
      min: 0,
      max: 100,
      step: 1,
    },
    {
      type: "number",
      configKey: "momentum_route_flow_score_impulse",
      label: "Flow Score Impulse",
      min: 0,
      max: 200,
      step: 1,
    },
    {
      type: "number",
      configKey: "momentum_min_directional_consistency",
      label: "Min Directional Consistency",
      min: 0,
      max: 1,
      step: 0.01,
    },
    {
      type: "number",
      configKey: "momentum_min_signed_aggression",
      label: "Min Signed Aggression",
      min: 0,
      max: 1,
      step: 0.01,
    },
    { type: "number", configKey: "momentum_min_imbalance", label: "Min Imbalance", min: 0, max: 1, step: 0.01 },
    {
      type: "checkbox",
      configKey: "momentum_route_require_l2_coverage",
      label: "Require L2 Coverage",
    },
  ],
  momentum_fail_fast: [
    {
      type: "number",
      configKey: "momentum_fail_fast_max_bars",
      label: "Fail-Fast Max Bars",
      min: 1,
      step: 1,
      integer: true,
    },
    {
      type: "number",
      configKey: "momentum_fail_fast_signed_aggression_max",
      label: "Signed Aggression Max",
      min: -1,
      max: 1,
      step: 0.01,
    },
    {
      type: "number",
      configKey: "momentum_fail_fast_book_pressure_max",
      label: "Book Pressure Max",
      min: -1,
      max: 1,
      step: 0.01,
    },
    {
      type: "number",
      configKey: "momentum_fail_fast_directional_consistency_max",
      label: "Directional Consistency Max",
      min: 0,
      max: 1,
      step: 0.01,
    },
  ],
  momentum_diversification: [
    {
      type: "checkbox",
      configKey: "momentum_diversification_override_enabled",
      label: "Override Momentum Defaults",
    },
    {
      type: "checkbox",
      configKey: "momentum_require_l2_coverage",
      label: "Require L2 Coverage",
    },
    {
      type: "text",
      configKey: "momentum_apply_to_strategies",
      label: "Apply To Strategies (csv)",
      placeholder: "momentum_flow,mean_reversion",
    },
    {
      type: "text",
      configKey: "momentum_allowed_micro_regimes",
      label: "Allowed Micro Regimes (csv)",
      placeholder: "trend_up,trend_down",
    },
    {
      type: "text",
      configKey: "momentum_blocked_micro_regimes",
      label: "Blocked Micro Regimes (csv)",
      placeholder: "noise,rotation",
    },
  ],
};

/** Canonical ordered list of all execution module keys. */
export const ALL_MODULE_KEYS = Object.keys(EXEC_MODULE_META);

export const EXEC_CATEGORY_LABELS: Record<string, string> = {
  exit: "Exit Protection",
  flow: "Flow Routing",
  risk: "Risk Management",
  engine: "Engine",
};
export const EXEC_CATEGORY_ORDER = ["exit", "flow", "risk", "engine"] as const;
