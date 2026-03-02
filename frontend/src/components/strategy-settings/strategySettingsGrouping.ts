export const FLOW_CORE_STRATEGIES = new Set([
  "momentum_flow",
  "absorption_reversal",
  "exhaustion_fade",
  "scalp_l2_intrabar",
]);

const STRATEGY_CATEGORY_MAP: Record<string, string> = {
  momentum_flow: "flow",
  absorption_reversal: "flow",
  exhaustion_fade: "flow",
  iceberg_defense: "flow",
  scalp_l2_intrabar: "scalp",
};

const STRATEGY_FIELD_EXCLUSIONS = new Set([
  "enabled",
  "display_name",
  "name",
  "open_positions",
  "total_signals",
  "last_signal",
  "trailing_stop_mode",
  "global_trailing_stop_pct",
  "effective_trailing_stop_pct",
  "global_rr_ratio",
  "effective_rr_ratio",
  "global_atr_stop_multiplier",
  "effective_atr_stop_multiplier",
  "global_volume_stop_pct",
  "effective_volume_stop_pct",
  "global_min_stop_loss_pct",
  "effective_min_stop_loss_pct",
  "custom_formula_supported_variables",
  "custom_formula_variable_docs",
  "custom_formula_examples",
]);

const SCALP_FIELD_ORDER = [
  "min_flow_score",
  "min_flow_score_trend_3bar",
  "min_signed_aggression",
  "min_directional_consistency",
  "min_imbalance",
  "min_book_pressure",
  "min_participation_ratio",
  "min_intrabar_move_pct",
  "min_intrabar_push_ratio",
  "min_intrabar_coverage_points",
  "min_intrabar_directional_consistency",
  "intrabar_eval_window_seconds",
  "min_intrabar_window_move_pct",
  "min_intrabar_window_push_ratio",
  "min_intrabar_window_directional_consistency",
  "max_intrabar_micro_volatility_bps",
  "max_intrabar_spread_bps",
  "spread_penalty_floor_bps",
  "spread_flow_score_penalty_per_bps",
  "min_round_trip_cost_bps",
  "spread_cost_multiplier",
  "min_reward_to_cost_ratio",
  "require_intrabar_confirmation",
  "no_intrabar_flow_buffer",
];

const FOCUS_FIELD_PRIORITY = [
  "allowed_regimes",
  "min_confidence",
  "risk_mode",
  "exit_mode",
  "atr_stop_multiplier",
  "stop_loss_pct",
  "rr_ratio",
  "take_profit_rr",
  "trailing_stop_pct",
  "time_exit_bars",
  "min_flow_score",
  "min_signed_aggression",
  "min_directional_consistency",
  "min_book_pressure",
  "min_imbalance",
  "min_absorption_rate",
  "min_divergence",
  "entry_threshold",
  "entry_deviation_pct",
  "breakout_threshold",
  "min_intrabar_move_pct",
  "min_intrabar_push_ratio",
  "max_intrabar_spread_bps",
];

const STRATEGY_SPECIFIC_FOCUS_FIELDS: Record<string, string[]> = {
  absorption_reversal: [
    "min_absorption_rate",
    "min_divergence",
    "min_signed_aggression",
    "min_book_pressure",
    "min_price_extension_pct",
  ],
  exhaustion_fade: [
    "min_flow_score",
    "min_signed_aggression",
    "min_directional_consistency",
    "entry_deviation_pct",
  ],
  scalp_l2_intrabar: [
    "min_flow_score",
    "min_intrabar_move_pct",
    "min_intrabar_push_ratio",
    "min_intrabar_directional_consistency",
    "max_intrabar_spread_bps",
  ],
  momentum_flow: [
    "min_flow_score",
    "min_signed_aggression",
    "min_directional_consistency",
    "entry_threshold",
  ],
};

const GROUP_FALLBACK_ORDER = [
  "Signal Setup",
  "Risk & Exit",
  "Scalp Intrabar",
  "Regime",
  "Other",
  "Custom Rules",
];

const MAX_FOCUS_FIELDS = 8;

export const formatFieldLabel = (field: string) => {
  const upperTokenMap = new Map([
    ["ma", "MA"],
    ["rr", "RR"],
    ["vwap", "VWAP"],
    ["l2", "L2"],
    ["pct", "%"],
  ]);

  return String(field || "")
    .split("_")
    .filter(Boolean)
    .map((token) => {
      const normalized = token.toLowerCase();
      if (upperTokenMap.has(normalized)) {
        return upperTokenMap.get(normalized);
      }
      return normalized.charAt(0).toUpperCase() + normalized.slice(1);
    })
    .join(" ");
};

export const resolveStrategyCategory = (name: string) =>
  STRATEGY_CATEGORY_MAP[name] || "other";

export const formatCategoryLabel = (categoryKey: string) => {
  if (categoryKey === "all") return "All";
  if (categoryKey === "flow") return "Flow";
  if (categoryKey === "scalp") return "Scalp";
  return "Other";
};

export const getStrategyWarning = (name: string, cfg: any) => {
  if (name !== "mean_reversion") return null;
  const deviation = cfg.entry_deviation_pct;
  if (typeof deviation === "number" && deviation > 2) {
    return "Deviation is very high; signals will likely never trigger.";
  }
  return null;
};

const classifyFieldGroup = (field: string) => {
  if (field === "allowed_regimes") return "Regime";
  if (/custom_.*formula/.test(field)) return "Custom Rules";
  if (
    /intrabar|spread_penalty|spread_cost|min_round_trip_cost|min_reward_to_cost|no_intrabar|require_intrabar/i.test(
      field,
    )
  )
    return "Scalp Intrabar";
  if (/stop|trailing|rr_ratio|risk|take_profit|time_exit/i.test(field))
    return "Risk & Exit";
  if (
    /entry|breakout|pullback|deviation|threshold|lookback|consolidation|rotation|distance|bars_since|ma_|volume|confidence|confirm/i.test(
      field,
    )
  )
    return "Signal Setup";
  return "Other";
};

const sortScalpFields = (grouped: Record<string, Array<[string, any]>>) => {
  const rank = new Map(SCALP_FIELD_ORDER.map((field, index) => [field, index]));
  Object.keys(grouped).forEach((groupKey) => {
    grouped[groupKey].sort((a, b) => {
      const rankA = rank.has(a[0]) ? rank.get(a[0]) : Number.MAX_SAFE_INTEGER;
      const rankB = rank.has(b[0]) ? rank.get(b[0]) : Number.MAX_SAFE_INTEGER;
      return rankA !== rankB ? rankA - rankB : String(a[0]).localeCompare(String(b[0]));
    });
  });
};

export const buildEditableFieldGroups = (name: string, cfg: any) => {
  const grouped: Record<string, Array<[string, any]>> = {
    Regime: [],
    "Scalp Intrabar": [],
    "Signal Setup": [],
    "Risk & Exit": [],
    "Custom Rules": [],
    Other: [],
  };

  Object.entries(cfg || {}).forEach(([field, value]) => {
    if (STRATEGY_FIELD_EXCLUSIONS.has(field)) return;
    if (
      !(
        typeof value === "number" ||
        typeof value === "boolean" ||
        (field === "allowed_regimes" && Array.isArray(value)) ||
        ([
          "trailing_stop_mode",
          "exit_mode",
          "risk_mode",
          "custom_entry_formula",
          "custom_exit_formula",
        ].includes(field) &&
          typeof value === "string")
      )
    ) {
      return;
    }

    const group = classifyFieldGroup(field);
    grouped[group].push([field, value]);
  });

  if (name === "scalp_l2_intrabar") {
    sortScalpFields(grouped);
  }

  return Object.entries(grouped).filter(([, entries]) => entries.length > 0);
};

export const buildFocusFieldLayout = (name: string, cfg: any) => {
  const grouped = buildEditableFieldGroups(name, cfg);
  const fieldMap = new Map<string, any>();

  grouped.forEach(([, entries]) => {
    entries.forEach(([field, value]) => {
      fieldMap.set(field, value);
    });
  });

  const orderedFields: string[] = [];
  const pushField = (field: string) => {
    if (!fieldMap.has(field) || orderedFields.includes(field)) return;
    orderedFields.push(field);
  };

  [
    ...(STRATEGY_SPECIFIC_FOCUS_FIELDS[name] || []),
    ...FOCUS_FIELD_PRIORITY,
  ].forEach(pushField);

  GROUP_FALLBACK_ORDER.forEach((groupName) => {
    const group = grouped.find(([label]) => label === groupName);
    if (!group) return;
    group[1].forEach(([field]) => {
      if (orderedFields.length >= MAX_FOCUS_FIELDS) return;
      pushField(field);
    });
  });

  const focusFields = orderedFields
    .slice(0, MAX_FOCUS_FIELDS)
    .map((field) => [field, fieldMap.get(field)] as [string, any]);
  const focusSet = new Set(focusFields.map(([field]) => field));
  const advancedGroups = grouped
    .map(
      ([label, entries]) =>
        [
          label,
          entries.filter(([field]) => !focusSet.has(field)),
        ] as [string, Array<[string, any]>],
    )
    .filter(([, entries]) => entries.length > 0);
  const totalEditableFields = grouped.reduce(
    (sum, [, entries]) => sum + entries.length,
    0,
  );

  return {
    focusFields,
    advancedGroups,
    totalEditableFields,
    focusFieldCount: focusFields.length,
    advancedFieldCount: Math.max(totalEditableFields - focusFields.length, 0),
  };
};
