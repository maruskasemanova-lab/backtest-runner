import { useCallback, useEffect, useState } from "react";
import { defaultStrategyApiUrl } from "../utils";
import StrategySettings from "./StrategySettings";
import { useExecutionModulesEditor } from "./adaptive-studio/useExecutionModulesEditor";

const MACRO_REGIMES = ["TRENDING", "CHOPPY", "MIXED"];
const MICRO_REGIMES = [
  "TRENDING_UP",
  "TRENDING_DOWN",
  "CHOPPY",
  "ABSORPTION",
  "BREAKOUT",
  "MIXED",
];

const DEFAULT_STRATEGIES = [
  "mean_reversion",
  "momentum",
  "pullback",
  "rotation",
  "vwap_magnet",
  "volume_profile",
  "gap_liquidity",
  "absorption_reversal",
  "momentum_flow",
  "scalp_l2_intrabar",
  "exhaustion_fade",
];

const DEFAULT_FLOW_BIAS_STRATEGIES = [
  "momentum_flow",
  "absorption_reversal",
  "exhaustion_fade",
  "scalp_l2_intrabar",
];

const DEFAULT_REGIME_PREFERENCES = {
  TRENDING: [
    "momentum_flow",
    "momentum",
    "pullback",
    "gap_liquidity",
    "scalp_l2_intrabar",
    "volume_profile",
    "vwap_magnet",
  ],
  CHOPPY: [
    "absorption_reversal",
    "exhaustion_fade",
    "mean_reversion",
    "vwap_magnet",
    "scalp_l2_intrabar",
    "volume_profile",
  ],
  MIXED: [
    "exhaustion_fade",
    "absorption_reversal",
    "volume_profile",
    "gap_liquidity",
    "scalp_l2_intrabar",
    "mean_reversion",
    "vwap_magnet",
    "rotation",
  ],
};

const DEFAULT_MICRO_PREFERENCES = {
  TRENDING_UP: ["momentum_flow", "momentum", "pullback", "gap_liquidity", "scalp_l2_intrabar"],
  TRENDING_DOWN: ["momentum_flow", "momentum", "gap_liquidity", "pullback", "scalp_l2_intrabar"],
  CHOPPY: ["absorption_reversal", "exhaustion_fade", "mean_reversion", "vwap_magnet"],
  ABSORPTION: ["absorption_reversal", "exhaustion_fade", "vwap_magnet"],
  BREAKOUT: ["momentum_flow", "momentum", "gap_liquidity", "scalp_l2_intrabar"],
  MIXED: ["exhaustion_fade", "volume_profile", "rotation"],
};

const STUDIO_PROFILE_LIST_KEY = "adaptive_studio_profiles";
const STUDIO_PROFILE_ACTIVE_KEY = "active_adaptive_studio_profile_id";
const STUDIO_PROFILE_MAX_ITEMS = 30;
const EXECUTION_MODULES = [
  {
    key: "adverse_flow_exit",
    label: "Adverse Flow Exit",
    category: "exit",
    description: "Protective exit when post-entry flow turns against the position.",
    configKey: "adverse_flow_exit_enabled",
  },
  {
    key: "l2_confirmation_gate",
    label: "L2 Confirmation Gate",
    category: "flow",
    description: "Requires L2 microstructure confirmation before entry.",
    configKey: "l2_confirm_enabled",
  },
  {
    key: "trailing_stop",
    label: "Trailing Stop",
    category: "risk",
    description: "Break-even and trailing controls for in-trade risk management.",
    configKey: "trailing_enabled_in_choppy",
  },
  {
    key: "momentum_route",
    label: "Momentum Route",
    category: "flow",
    description: "Flow-based routing constraints for momentum entries.",
    configKey: "momentum_route_enabled",
  },
  {
    key: "momentum_fail_fast",
    label: "Momentum Fail-Fast",
    category: "exit",
    description: "Early-exit guardrails when momentum flow deteriorates.",
    configKey: "momentum_fail_fast_exit_enabled",
  },
  {
    key: "momentum_diversification",
    label: "Momentum Diversification",
    category: "risk",
    description: "Optional run-level override for momentum diversification behavior.",
    configKey: "momentum_diversification_enabled",
  },
  {
    key: "aos_auto_apply",
    label: "AOS Auto-Apply",
    category: "engine",
    description: "Applies active AOS/adaptive optimizations during run start.",
    configKey: "apply_aos_optimizations_on_start",
  },
];
const EXECUTION_MODULE_CATEGORY_LABELS = {
  flow: "Flow",
  exit: "Exit",
  risk: "Risk",
  engine: "Engine",
};
const EXECUTION_MODULE_PROFILE_KEYS = EXECUTION_MODULES.map((module) => module.configKey);
const EXECUTION_MODULE_PARAM_FIELDS = [
  {
    moduleKey: "trailing_stop",
    key: "trailing_stop_pct",
    label: "Global Trailing Stop %",
    type: "number",
    min: 0,
    max: 5,
    step: 0.01,
    fallback: 0.8,
    integer: false,
  },
  {
    moduleKey: "trailing_stop",
    key: "global_exit_rr_ratio",
    label: "Global Exit RR Ratio",
    type: "number",
    min: 0,
    max: 10,
    step: 0.05,
    fallback: 2.0,
    integer: false,
  },
  {
    moduleKey: "trailing_stop",
    key: "global_risk_atr_stop_multiplier",
    label: "Global Risk ATR Stop Multiplier",
    type: "number",
    min: 0,
    max: 10,
    step: 0.05,
    fallback: 1.0,
    integer: false,
  },
  {
    moduleKey: "trailing_stop",
    key: "global_risk_volume_stop_pct",
    label: "Global Risk Volume Stop %",
    type: "number",
    min: 0,
    max: 10,
    step: 0.05,
    fallback: 1.0,
    integer: false,
  },
  {
    moduleKey: "trailing_stop",
    key: "global_risk_min_stop_loss_pct",
    label: "Global Risk Min Stop %",
    type: "number",
    min: 0,
    max: 5,
    step: 0.01,
    fallback: 0.05,
    integer: false,
  },
  {
    moduleKey: "trailing_stop",
    key: "trailing_activation_pct",
    label: "Trailing Activation %",
    type: "number",
    min: 0,
    max: 5,
    step: 0.01,
    fallback: 0.45,
    integer: false,
  },
  {
    moduleKey: "trailing_stop",
    key: "break_even_buffer_pct",
    label: "Break-even Buffer %",
    type: "number",
    min: 0,
    max: 2,
    step: 0.01,
    fallback: 0,
    integer: false,
  },
  {
    moduleKey: "trailing_stop",
    key: "break_even_min_hold_bars",
    label: "Break-even Min Hold Bars",
    type: "number",
    min: 1,
    max: 50,
    step: 1,
    fallback: 2,
    integer: true,
  },
  {
    moduleKey: "trailing_stop",
    key: "time_exit_bars",
    label: "Time Exit Bars",
    type: "number",
    min: 1,
    max: 300,
    step: 1,
    fallback: 40,
    integer: true,
  },
  {
    moduleKey: "trailing_stop",
    key: "stop_loss_mode",
    label: "Stop-Loss Mode",
    type: "select",
    options: [
      { value: "strategy", label: "strategy (use strategy stop)" },
      { value: "fixed", label: "fixed (always fixed % stop)" },
      { value: "capped", label: "capped (cap wide strategy stops)" },
    ],
    fallback: "strategy",
  },
  {
    moduleKey: "trailing_stop",
    key: "fixed_stop_loss_pct",
    label: "Fixed Stop-Loss %",
    type: "number",
    min: 0,
    max: 5,
    step: 0.05,
    fallback: 0,
    integer: false,
    disabledWhen: (configSnapshot) =>
      String(configSnapshot?.stop_loss_mode || "strategy").toLowerCase() === "strategy",
  },
  {
    moduleKey: "adverse_flow_exit",
    key: "adverse_flow_threshold",
    label: "Adverse Flow Threshold",
    type: "number",
    min: 0,
    max: 1,
    step: 0.01,
    fallback: 0.12,
    integer: false,
  },
  {
    moduleKey: "adverse_flow_exit",
    key: "adverse_flow_min_hold_bars",
    label: "Adverse Flow Min Hold Bars",
    type: "number",
    min: 1,
    max: 50,
    step: 1,
    fallback: 3,
    integer: true,
  },
  {
    moduleKey: "l2_confirmation_gate",
    key: "l2_min_imbalance",
    label: "L2 Min Imbalance",
    type: "number",
    min: 0,
    max: 1,
    step: 0.01,
    fallback: 0,
    integer: false,
  },
  {
    moduleKey: "l2_confirmation_gate",
    key: "l2_min_directional_consistency",
    label: "L2 Min Directional Consistency",
    type: "number",
    min: 0,
    max: 1,
    step: 0.01,
    fallback: 0,
    integer: false,
  },
  {
    moduleKey: "l2_confirmation_gate",
    key: "l2_min_signed_aggression",
    label: "L2 Min Signed Aggression",
    type: "number",
    min: 0,
    max: 1,
    step: 0.01,
    fallback: 0,
    integer: false,
  },
  {
    moduleKey: "l2_confirmation_gate",
    key: "l2_lookback_bars",
    label: "L2 Lookback Bars",
    type: "number",
    min: 1,
    max: 50,
    step: 1,
    fallback: 3,
    integer: true,
  },
  {
    moduleKey: "momentum_route",
    key: "momentum_min_flow_score",
    label: "Momentum Min Flow Score",
    type: "number",
    min: 0,
    max: 100,
    step: 0.5,
    fallback: 58,
    integer: false,
  },
  {
    moduleKey: "momentum_route",
    key: "momentum_route_flow_score_impulse",
    label: "Momentum Route Flow Impulse",
    type: "number",
    min: 0,
    max: 100,
    step: 0.5,
    fallback: 64,
    integer: false,
  },
  {
    moduleKey: "momentum_route",
    key: "momentum_min_directional_consistency",
    label: "Momentum Min Directional Consistency",
    type: "number",
    min: 0,
    max: 1,
    step: 0.01,
    fallback: 0.45,
    integer: false,
  },
  {
    moduleKey: "momentum_route",
    key: "momentum_min_signed_aggression",
    label: "Momentum Min Signed Aggression",
    type: "number",
    min: 0,
    max: 1,
    step: 0.01,
    fallback: 0.04,
    integer: false,
  },
  {
    moduleKey: "momentum_route",
    key: "momentum_min_imbalance",
    label: "Momentum Min Imbalance",
    type: "number",
    min: 0,
    max: 1,
    step: 0.01,
    fallback: 0.02,
    integer: false,
  },
  {
    moduleKey: "momentum_route",
    key: "momentum_min_cvd",
    label: "Momentum Min CVD",
    type: "number",
    min: -1000000000,
    max: 1000000000,
    step: 1,
    fallback: 0,
    integer: false,
  },
  {
    moduleKey: "momentum_route",
    key: "momentum_min_directional_price_change_pct",
    label: "Momentum Min Directional Price Change %",
    type: "number",
    min: -100,
    max: 100,
    step: 0.01,
    fallback: 0,
    integer: false,
  },
  {
    moduleKey: "momentum_route",
    key: "momentum_min_price_trend_efficiency",
    label: "Momentum Min Price Trend Efficiency",
    type: "number",
    min: 0,
    max: 1,
    step: 0.01,
    fallback: 0,
    integer: false,
  },
  {
    moduleKey: "momentum_route",
    key: "momentum_min_last_bar_body_ratio",
    label: "Momentum Min Last Bar Body Ratio",
    type: "number",
    min: 0,
    max: 1,
    step: 0.01,
    fallback: 0,
    integer: false,
  },
  {
    moduleKey: "momentum_route",
    key: "momentum_min_last_bar_close_location",
    label: "Momentum Min Last Bar Close Location",
    type: "number",
    min: 0,
    max: 1,
    step: 0.01,
    fallback: 0,
    integer: false,
  },
  {
    moduleKey: "momentum_route",
    key: "momentum_min_delta_acceleration",
    label: "Momentum Min Delta Acceleration",
    type: "number",
    min: -1000000000,
    max: 1000000000,
    step: 1,
    fallback: 0,
    integer: false,
  },
  {
    moduleKey: "momentum_route",
    key: "momentum_min_delta_price_divergence",
    label: "Momentum Min Delta-Price Divergence",
    type: "number",
    min: -10,
    max: 10,
    step: 0.01,
    fallback: 0,
    integer: false,
  },
  {
    moduleKey: "momentum_route",
    key: "momentum_route_require_l2_coverage",
    label: "Momentum Route Requires L2 Coverage",
    type: "boolean",
    fallback: true,
  },
  {
    moduleKey: "momentum_fail_fast",
    key: "momentum_fail_fast_max_bars",
    label: "Momentum Fail-fast Max Bars",
    type: "number",
    min: 1,
    max: 30,
    step: 1,
    fallback: 3,
    integer: true,
  },
  {
    moduleKey: "momentum_fail_fast",
    key: "momentum_fail_fast_signed_aggression_max",
    label: "Momentum Fail-fast Signed Aggression Max",
    type: "number",
    min: -1,
    max: 0,
    step: 0.01,
    fallback: -0.08,
    integer: false,
  },
  {
    moduleKey: "momentum_fail_fast",
    key: "momentum_fail_fast_book_pressure_max",
    label: "Momentum Fail-fast Book Pressure Max",
    type: "number",
    min: -1,
    max: 0,
    step: 0.01,
    fallback: -0.1,
    integer: false,
  },
  {
    moduleKey: "momentum_fail_fast",
    key: "momentum_fail_fast_directional_consistency_max",
    label: "Momentum Fail-fast Directional Consistency Max",
    type: "number",
    min: 0,
    max: 1,
    step: 0.01,
    fallback: 0.2,
    integer: false,
  },
  {
    moduleKey: "momentum_diversification",
    key: "momentum_diversification_override_enabled",
    label: "Use Run-level Diversification Override",
    type: "boolean",
    fallback: false,
  },
  {
    moduleKey: "momentum_diversification",
    key: "momentum_require_l2_coverage",
    label: "Momentum Diversification Requires L2 Coverage",
    type: "boolean",
    fallback: true,
  },
];
const EXECUTION_MODULE_PARAM_FIELDS_BY_MODULE = EXECUTION_MODULE_PARAM_FIELDS.reduce(
  (acc, field) => {
    const moduleKey = String(field?.moduleKey || "");
    if (!moduleKey) return acc;
    if (!Array.isArray(acc[moduleKey])) {
      acc[moduleKey] = [];
    }
    acc[moduleKey].push(field);
    return acc;
  },
  {}
);
const normalizeMode = (value) => {
  const normalized = String(value || "").trim().toLowerCase();
  return normalized === "all_enabled" ? "all_enabled" : "adaptive_top_n";
};

const normalizeMaxActive = (value, fallback = 3) => {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || !Number.isInteger(parsed)) {
    return fallback;
  }
  return Math.max(1, Math.min(20, parsed));
};

const normalizeNonNegativeInt = (value, fallback = 0, max = 10000) => {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || !Number.isInteger(parsed)) {
    return fallback;
  }
  return Math.max(0, Math.min(max, parsed));
};

const toBoolean = (value, fallback = false) => {
  if (typeof value === "boolean") return value;
  if (typeof value === "number") return value !== 0;
  if (typeof value === "string") {
    const normalized = value.trim().toLowerCase();
    if (["1", "true", "yes", "on"].includes(normalized)) return true;
    if (["0", "false", "no", "off"].includes(normalized)) return false;
  }
  return fallback;
};

const normalizeProfileRefToken = (value) => {
  const token = String(value || "").trim();
  if (!token) return "";
  const lowered = token.toLowerCase();
  if (lowered === "none" || lowered === "null" || lowered === "n/a" || lowered === "na") {
    return "";
  }
  return token;
};

const canonicalizeStrategyName = (value, strategyUniverse) => {
  const raw = String(value || "").trim();
  if (!raw) return "";

  const normalized = raw
    .replace(/-/g, "_")
    .replace(/\s+/g, "_")
    .replace(/__+/g, "_")
    .toLowerCase();

  if (strategyUniverse.includes(normalized)) return normalized;

  const compact = normalized.replace(/_/g, "");
  const compactMatch = strategyUniverse.find((item) => item.replace(/_/g, "") === compact);
  if (compactMatch) return compactMatch;

  return normalized;
};

const normalizeStrategyList = (value, fallback, strategyUniverse) => {
  const source = Array.isArray(value) ? value : fallback;
  const normalized = [];
  const seen = new Set();

  source.forEach((item) => {
    const key = canonicalizeStrategyName(item, strategyUniverse);
    if (!key || seen.has(key)) return;
    seen.add(key);
    normalized.push(key);
  });

  return normalized;
};

const normalizePreferenceMap = (value, keys, fallbackMap, strategyUniverse) => {
  const source = value && typeof value === "object" && !Array.isArray(value) ? value : {};
  const normalized = {};

  keys.forEach((key) => {
    normalized[key] = normalizeStrategyList(
      source[key],
      fallbackMap[key] || [],
      strategyUniverse
    );
  });

  return normalized;
};

const cloneMap = (input) => {
  const out = {};
  Object.entries(input || {}).forEach(([key, list]) => {
    out[key] = Array.isArray(list) ? [...list] : [];
  });
  return out;
};

const strategyLabel = (name) =>
  String(name || "")
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");

const normalizeTickerAdaptiveForm = (tickerConfig, strategyUniverse) => {
  const safeTickerConfig =
    tickerConfig && typeof tickerConfig === "object" && !Array.isArray(tickerConfig)
      ? tickerConfig
      : {};
  const adaptiveRaw =
    safeTickerConfig.adaptive && typeof safeTickerConfig.adaptive === "object" && !Array.isArray(safeTickerConfig.adaptive)
      ? safeTickerConfig.adaptive
      : {};

  return {
    strategy_selection_mode: normalizeMode(safeTickerConfig.strategy_selection_mode),
    max_active_strategies: normalizeMaxActive(safeTickerConfig.max_active_strategies, 3),
    flow_bias_enabled: toBoolean(adaptiveRaw.flow_bias_enabled, true),
    use_ohlcv_fallbacks: toBoolean(adaptiveRaw.use_ohlcv_fallbacks, true),
    min_active_bars_before_switch: normalizeNonNegativeInt(
      adaptiveRaw.min_active_bars_before_switch,
      0
    ),
    switch_cooldown_bars: normalizeNonNegativeInt(adaptiveRaw.switch_cooldown_bars, 0),
    flow_bias_strategies: normalizeStrategyList(
      adaptiveRaw.flow_bias_strategies,
      DEFAULT_FLOW_BIAS_STRATEGIES,
      strategyUniverse
    ),
    regime_preferences: normalizePreferenceMap(
      adaptiveRaw.regime_preferences,
      MACRO_REGIMES,
      DEFAULT_REGIME_PREFERENCES,
      strategyUniverse
    ),
    micro_regime_preferences: normalizePreferenceMap(
      adaptiveRaw.micro_regime_preferences,
      MICRO_REGIMES,
      DEFAULT_MICRO_PREFERENCES,
      strategyUniverse
    ),
  };
};

const normalizeAdaptiveFormSnapshot = (value, strategyUniverse) => {
  const source = value && typeof value === "object" && !Array.isArray(value) ? value : {};
  return {
    strategy_selection_mode: normalizeMode(source.strategy_selection_mode),
    max_active_strategies: normalizeMaxActive(source.max_active_strategies, 3),
    flow_bias_enabled: toBoolean(source.flow_bias_enabled, true),
    use_ohlcv_fallbacks: toBoolean(source.use_ohlcv_fallbacks, true),
    min_active_bars_before_switch: normalizeNonNegativeInt(source.min_active_bars_before_switch, 0),
    switch_cooldown_bars: normalizeNonNegativeInt(source.switch_cooldown_bars, 0),
    flow_bias_strategies: normalizeStrategyList(
      source.flow_bias_strategies,
      DEFAULT_FLOW_BIAS_STRATEGIES,
      strategyUniverse
    ),
    regime_preferences: normalizePreferenceMap(
      source.regime_preferences,
      MACRO_REGIMES,
      DEFAULT_REGIME_PREFERENCES,
      strategyUniverse
    ),
    micro_regime_preferences: normalizePreferenceMap(
      source.micro_regime_preferences,
      MICRO_REGIMES,
      DEFAULT_MICRO_PREFERENCES,
      strategyUniverse
    ),
  };
};

const normalizeExecutionModulesSnapshot = (value) => {
  const source = value && typeof value === "object" && !Array.isArray(value) ? value : {};
  const normalized = {};
  EXECUTION_MODULE_PROFILE_KEYS.forEach((key) => {
    normalized[key] = toBoolean(source[key], false);
  });
  return normalized;
};

const normalizeExecutionParamValue = (value, field) => {
  if (field?.type === "boolean") {
    return toBoolean(value, !!field?.fallback);
  }
  if (field?.type === "select") {
    if (field?.key === "stop_loss_mode") {
      const raw = String(value ?? field?.fallback ?? "strategy")
        .trim()
        .toLowerCase();
      if (raw === "fixed" || raw === "capped") return raw;
      return "strategy";
    }
    const options = Array.isArray(field?.options) ? field.options : [];
    const allowed = options
      .map((item) => String(item?.value || "").trim())
      .filter(Boolean);
    const fallback = String(field?.fallback ?? allowed[0] ?? "").trim();
    const candidate = String(value ?? fallback).trim();
    return allowed.includes(candidate) ? candidate : fallback;
  }
  const parsed = Number(value);
  const fallback = Number(field?.fallback || 0);
  const min = Number(field?.min ?? Number.NEGATIVE_INFINITY);
  const max = Number(field?.max ?? Number.POSITIVE_INFINITY);
  const safe = Number.isFinite(parsed) ? parsed : fallback;
  const clamped = Math.max(min, Math.min(max, safe));
  if (field?.integer) {
    return Math.trunc(clamped);
  }
  return clamped;
};

const normalizeExecutionParamsSnapshot = (value) => {
  const source = value && typeof value === "object" && !Array.isArray(value) ? value : {};
  const normalized = {};
  EXECUTION_MODULE_PARAM_FIELDS.forEach((field) => {
    normalized[field.key] = normalizeExecutionParamValue(source[field.key], field);
  });
  return normalized;
};

const readExecutionConfigSnapshot = () => {
  if (typeof window === "undefined") return {};
  const raw = (window as any).__executionConfig;
  return raw && typeof raw === "object" && !Array.isArray(raw) ? raw : {};
};

const readExecutionModuleSnapshot = () => {
  return normalizeExecutionModulesSnapshot(readExecutionConfigSnapshot());
};

const readExecutionParamsSnapshot = () => {
  return normalizeExecutionParamsSnapshot(readExecutionConfigSnapshot());
};

const applyExecutionModuleSnapshot = (value) => {
  if (typeof window === "undefined") return;
  const normalized = normalizeExecutionModulesSnapshot(value);
  Object.entries(normalized).forEach(([configKey, enabled]) => {
    window.dispatchEvent(
      new CustomEvent("execution-module-toggle", {
        detail: { configKey, value: !!enabled },
      })
    );
  });
};

const applyExecutionParamsSnapshot = (value) => {
  if (typeof window === "undefined") return;
  const normalized = normalizeExecutionParamsSnapshot(value);
  Object.entries(normalized).forEach(([configKey, nextValue]) => {
    window.dispatchEvent(
      new CustomEvent("execution-module-toggle", {
        detail: { configKey, value: nextValue },
      })
    );
  });
};

const parseIsoMs = (value) => {
  const parsed = Date.parse(String(value || ""));
  return Number.isFinite(parsed) ? parsed : 0;
};

const normalizeStudioProfiles = (value, strategyUniverse) => {
  if (!Array.isArray(value)) return [];
  const seen = new Set();
  const rows = [];
  value.forEach((item) => {
    if (!item || typeof item !== "object" || Array.isArray(item)) return;
    const profileId = String(item.profile_id || "").trim();
    if (!profileId || seen.has(profileId)) return;
    seen.add(profileId);
    const profileName = String(item.profile_name || profileId).trim() || profileId;
    const createdAt = String(item.created_at || "").trim() || new Date().toISOString();
    const updatedAt = String(item.updated_at || "").trim() || createdAt;
    rows.push({
      profile_id: profileId,
      profile_name: profileName,
      created_at: createdAt,
      updated_at: updatedAt,
      adaptive_form: normalizeAdaptiveFormSnapshot(item.adaptive_form, strategyUniverse),
      execution_modules: normalizeExecutionModulesSnapshot(item.execution_modules),
      execution_params: normalizeExecutionParamsSnapshot(item.execution_params),
      strategy_combo_profile_id: String(item.strategy_combo_profile_id || "").trim(),
      strategy_combo_profile_name: String(item.strategy_combo_profile_name || "").trim(),
    });
  });
  rows.sort((a, b) => parseIsoMs(b.updated_at) - parseIsoMs(a.updated_at));
  return rows.slice(0, STUDIO_PROFILE_MAX_ITEMS);
};

const asObject = (value) =>
  value && typeof value === "object" && !Array.isArray(value) ? value : {};

const extractAdaptiveCandidate = (profile) => {
  const row = asObject(profile);
  const candidate = asObject(row.candidate);
  if (Object.keys(candidate).length) return candidate;
  const bestTrial = asObject(row.best_trial);
  const bestCandidate = asObject(bestTrial.candidate);
  return bestCandidate;
};

const normalizeUnifiedProfiles = (value) => {
  if (!Array.isArray(value)) return [];
  const out = [];
  const seen = new Set();
  value.forEach((item) => {
    const row = asObject(item);
    const profileId = String(row.profile_id || "").trim();
    if (!profileId || seen.has(profileId)) return;
    seen.add(profileId);
    out.push({
      profile_id: profileId,
      profile_name: String(row.profile_name || profileId).trim() || profileId,
      created_at: String(row.created_at || "").trim() || new Date().toISOString(),
      updated_at: String(row.updated_at || "").trim() || String(row.created_at || "").trim() || new Date().toISOString(),
      strategy_profile: asObject(row.strategy_profile),
      execution_profile: asObject(row.execution_profile),
      source_strategy_combo_profile_id: String(row.source_strategy_combo_profile_id || "").trim(),
      source_adaptive_tuner_profile_id: String(row.source_adaptive_tuner_profile_id || "").trim(),
    });
  });
  out.sort((a, b) => parseIsoMs(b.updated_at) - parseIsoMs(a.updated_at));
  return out.slice(0, STUDIO_PROFILE_MAX_ITEMS);
};

const buildLegacyUnifiedProfiles = ({
  ticker,
  tickerConfig,
  comboPayload,
  tunedPayload,
}) => {
  const safeTicker = asObject(tickerConfig);
  const comboProfiles = Array.isArray(comboPayload?.profiles) ? comboPayload.profiles : [];
  const comboActiveId = normalizeProfileRefToken(comboPayload?.active_profile_id);
  const tunedProfiles = Array.isArray(tunedPayload?.profiles) ? tunedPayload.profiles : [];
  const tunedActiveId = normalizeProfileRefToken(tunedPayload?.active_profile_id);
  const nowIso = new Date().toISOString();
  const baseExecutionProfile = {
    positioning: asObject(safeTicker?.positioning),
  };
  const parseMs = (value) => {
    const parsed = Date.parse(String(value || "").trim());
    return Number.isFinite(parsed) ? parsed : 0;
  };
  const orderWithActive = (rows, activeId) => {
    const activeRows = [];
    const restRows = [];
    rows.forEach((row) => {
      if (String(row?.profile_id || "").trim() === activeId) {
        activeRows.push(row);
      } else {
        restRows.push(row);
      }
    });
    restRows.sort(
      (a, b) =>
        parseMs(b?.updated_at || b?.created_at) - parseMs(a?.updated_at || a?.created_at)
    );
    return [...activeRows, ...restRows];
  };
  const comboCandidates = orderWithActive(comboProfiles, comboActiveId);
  const tunedCandidates = orderWithActive(tunedProfiles, tunedActiveId);
  const limitedCombos = comboCandidates.length ? comboCandidates.slice(0, 12) : [null];
  const limitedTuned = tunedCandidates.length ? tunedCandidates.slice(0, 12) : [null];

  const makeProfile = ({
    comboProfile,
    tunedProfile,
  }) => {
    const comboId = String(comboProfile?.profile_id || "").trim();
    const profileTunedId = String(tunedProfile?.profile_id || "").trim();
    const comboName = String(comboProfile?.profile_name || comboId || "").trim();
    const tunedName = String(tunedProfile?.profile_name || profileTunedId || "").trim();
    const profileName = comboName && tunedName
      ? `legacy: ${comboName} + ${tunedName}`
      : `legacy: ${comboName || tunedName || "profile"}`;
    const strategyProfile = {
      strategy_params: asObject(comboProfile?.strategy_params),
      strategy_selection_mode: normalizeMode(safeTicker?.strategy_selection_mode),
      max_active_strategies: normalizeMaxActive(safeTicker?.max_active_strategies, 3),
      trading_hours: Array.isArray(safeTicker?.trading_hours) ? safeTicker.trading_hours : [],
      time_filter_enabled: toBoolean(safeTicker?.time_filter_enabled, false),
      long_only: toBoolean(safeTicker?.long_only, false),
      l2: asObject(safeTicker?.l2),
      adaptive: asObject(safeTicker?.adaptive),
      active_strategy_combo_profile_id: comboId,
      active_adaptive_tuner_profile_id: profileTunedId,
    };
    const candidate = extractAdaptiveCandidate(tunedProfile);
    if (Object.keys(candidate).length) {
      strategyProfile.adaptive_candidate = candidate;
    }
    return {
      profile_id: `legacy-unified-${String(ticker || "").toUpperCase()}-${comboId || "none"}-${profileTunedId || "none"}`,
      profile_name: profileName,
      created_at: String(comboProfile?.created_at || tunedProfile?.created_at || nowIso),
      updated_at: String(
        comboProfile?.updated_at ||
          comboProfile?.created_at ||
          tunedProfile?.updated_at ||
          tunedProfile?.created_at ||
          nowIso
      ),
      strategy_profile: strategyProfile,
      execution_profile: baseExecutionProfile,
      source_strategy_combo_profile_id: comboId || undefined,
      source_adaptive_tuner_profile_id: profileTunedId || undefined,
    };
  };

  const rows = [];
  limitedCombos.forEach((combo) => {
    limitedTuned.forEach((tuned) => {
      if (!combo && !tuned) return;
      rows.push(
        makeProfile({
          comboProfile: combo,
          tunedProfile: tuned,
        })
      );
    });
  });
  const uniqueRows = [];
  const seen = new Set();
  rows.forEach((row) => {
    const rowId = String(row?.profile_id || "").trim();
    if (!rowId || seen.has(rowId)) return;
    seen.add(rowId);
    uniqueRows.push(row);
  });
  uniqueRows.sort(
    (a, b) =>
      parseMs(b?.updated_at || b?.created_at) - parseMs(a?.updated_at || a?.created_at)
  );
  const derivedActiveProfileId = `legacy-unified-${String(ticker || "").toUpperCase()}-${comboActiveId || "none"}-${tunedActiveId || "none"}`;
  const activeProfileId = seen.has(derivedActiveProfileId)
    ? derivedActiveProfileId
    : String(uniqueRows[0]?.profile_id || "").trim();
  return {
    profiles: uniqueRows.slice(0, STUDIO_PROFILE_MAX_ITEMS),
    active_profile_id: activeProfileId || null,
    legacy_fallback: true,
  };
};

const toProfileSlug = (value) =>
  String(value || "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 48);

const buildStudioProfileId = (ticker, profileName, existingIds) => {
  const baseTicker = String(ticker || "ticker").trim().toLowerCase() || "ticker";
  const slug = toProfileSlug(profileName) || "profile";
  const stamp = Date.now().toString(36);
  let candidate = `${baseTicker}-${slug}-${stamp}`;
  let suffix = 1;
  while (existingIds.has(candidate)) {
    candidate = `${baseTicker}-${slug}-${stamp}-${suffix}`;
    suffix += 1;
  }
  return candidate;
};

const countEnabledExecutionModules = (modules) =>
  EXECUTION_MODULE_PROFILE_KEYS.reduce((acc, key) => acc + (modules?.[key] ? 1 : 0), 0);

const flowSummary = (strategies) => {
  if (!Array.isArray(strategies) || strategies.length === 0) {
    return "none";
  }
  return strategies.slice(0, 3).map(strategyLabel).join(", ");
};

const formatProfileTimestamp = (value) => {
  if (!value) return "-";
  const parsed = Date.parse(value);
  if (Number.isNaN(parsed)) return String(value);
  return new Date(parsed).toLocaleString();
};

const formatProfileCandidate = (candidate) => {
  if (!candidate || typeof candidate !== "object") return "candidate unavailable";
  const mode = normalizeMode(candidate.strategy_selection_mode);
  const maxActive = normalizeMaxActive(candidate.max_active_strategies, 3);
  const hysteresis = normalizeNonNegativeInt(candidate.min_active_bars_before_switch, 0);
  const cooldown = normalizeNonNegativeInt(candidate.switch_cooldown_bars, 0);
  const flowBias = toBoolean(candidate.flow_bias_enabled, true) ? "flow-bias on" : "flow-bias off";
  const fallback = toBoolean(candidate.use_ohlcv_fallbacks, true) ? "fallback on" : "fallback off";
  return `${mode === "all_enabled" ? "all enabled" : `adaptive top-${maxActive}`} | hysteresis ${hysteresis} | cooldown ${cooldown} | ${flowBias} | ${fallback}`;
};

const applyTunedCandidateToForm = (formState, candidate, strategyUniverse) => {
  const source = candidate && typeof candidate === "object" ? candidate : {};
  const base = {
    ...formState,
    strategy_selection_mode: normalizeMode(source.strategy_selection_mode),
    max_active_strategies: normalizeMaxActive(
      source.max_active_strategies,
      normalizeMaxActive(formState.max_active_strategies, 3)
    ),
    flow_bias_enabled: toBoolean(source.flow_bias_enabled, formState.flow_bias_enabled),
    use_ohlcv_fallbacks: toBoolean(source.use_ohlcv_fallbacks, formState.use_ohlcv_fallbacks),
    min_active_bars_before_switch: normalizeNonNegativeInt(
      source.min_active_bars_before_switch,
      normalizeNonNegativeInt(formState.min_active_bars_before_switch, 0)
    ),
    switch_cooldown_bars: normalizeNonNegativeInt(
      source.switch_cooldown_bars,
      normalizeNonNegativeInt(formState.switch_cooldown_bars, 0)
    ),
  };

  // V2 recomposition: if candidate has enabled_strategies, recompose regime preferences
  const enabled = source.enabled_strategies;
  if (Array.isArray(enabled) && enabled.length > 0 && Array.isArray(strategyUniverse)) {
    const enabledSet = new Set(
      enabled.map((s) => canonicalizeStrategyName(s, strategyUniverse)).filter(Boolean)
    );
    const nextRegime = {};
    MACRO_REGIMES.forEach((key) => {
      nextRegime[key] = buildRecomposedList(
        base.regime_preferences?.[key],
        DEFAULT_REGIME_PREFERENCES[key],
        enabledSet
      );
    });
    const nextMicro = {};
    MICRO_REGIMES.forEach((key) => {
      nextMicro[key] = buildRecomposedList(
        base.micro_regime_preferences?.[key],
        DEFAULT_MICRO_PREFERENCES[key],
        enabledSet
      );
    });
    const nextFlowBias = buildRecomposedList(
      base.flow_bias_strategies,
      DEFAULT_FLOW_BIAS_STRATEGIES,
      enabledSet
    );
    base.regime_preferences = nextRegime;
    base.micro_regime_preferences = nextMicro;
    base.flow_bias_strategies = nextFlowBias;
    base.max_active_strategies = Math.max(1, Math.min(base.max_active_strategies, enabledSet.size));
  }

  return base;
};

/** Summarize a v2 candidate's vector config for display. */
const formatV2VectorSummary = (candidate) => {
  if (!candidate || typeof candidate !== "object") return null;
  const parts = [];
  const strategies = candidate.enabled_strategies;
  if (Array.isArray(strategies) && strategies.length) {
    parts.push(`Strategies: ${strategies.join(", ")}`);
  }
  const regime = candidate.regime_filter;
  if (Array.isArray(regime) && regime.length) {
    parts.push(`Regime: ${regime.join(", ")}`);
  }
  if (candidate.l2_min_imbalance != null) {
    parts.push(`L2 imb: ${Number(candidate.l2_min_imbalance).toFixed(3)}`);
  }
  if (candidate.l2_min_delta != null) {
    parts.push(`L2 delta: ${candidate.l2_min_delta}`);
  }
  if (candidate.base_threshold != null) {
    parts.push(`Evidence thr: ${candidate.base_threshold}`);
  }
  if (candidate.min_confirming_sources != null) {
    parts.push(`Min sources: ${candidate.min_confirming_sources}`);
  }
  if (candidate.min_confidence != null) {
    parts.push(`Confidence: ${candidate.min_confidence}`);
  }
  if (candidate.atr_stop_multiplier != null) {
    parts.push(`ATR stop: ${candidate.atr_stop_multiplier}`);
  }
  if (candidate.rr_ratio != null) {
    parts.push(`R:R: ${candidate.rr_ratio}`);
  }
  const hours = candidate.trading_hours;
  if (Array.isArray(hours) && hours.length) {
    parts.push(`Hours: ${hours.join(",")}`);
  }
  if (candidate.adverse_flow_consistency != null) {
    parts.push(`FlowExitCons: ${candidate.adverse_flow_consistency}`);
  }
  if (candidate.adverse_book_pressure != null) {
    parts.push(`BookExitThr: ${candidate.adverse_book_pressure}`);
  }
  return parts.length ? parts : null;
};

const extractEnabledStrategiesFromCombo = (profile, strategyUniverse) => {
  const strategyParams =
    profile && typeof profile === "object" && typeof profile.strategy_params === "object"
      ? profile.strategy_params
      : {};
  const enabled = [];
  Object.entries(strategyParams || {}).forEach(([name, params]: [string, any]) => {
    const canonical = canonicalizeStrategyName(name, strategyUniverse);
    if (!canonical) return;
    const isEnabled = !(params && typeof params === "object" && params.enabled === false);
    if (isEnabled) {
      enabled.push(canonical);
    }
  });
  return Array.from(new Set(enabled));
};

const buildRecomposedList = (currentList, fallbackList, enabledSet) => {
  const filteredCurrent = (Array.isArray(currentList) ? currentList : []).filter((name) =>
    enabledSet.has(name)
  );
  if (filteredCurrent.length > 0) return filteredCurrent;
  const filteredFallback = (Array.isArray(fallbackList) ? fallbackList : []).filter((name) =>
    enabledSet.has(name)
  );
  if (filteredFallback.length > 0) return filteredFallback;
  return [];
};

function AdaptiveStrategyStudio({ selectedTicker, onTickerChange, strategyApiUrl }) {
  const [availableTickers, setAvailableTickers] = useState([]);
  const [strategyUniverse, setStrategyUniverse] = useState(DEFAULT_STRATEGIES);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [isDirty, setIsDirty] = useState(false);
  const [rawTickerConfig, setRawTickerConfig] = useState<Record<string, any>>({});
  const [form, setForm] = useState<Record<string, any>>(() =>
    normalizeTickerAdaptiveForm({}, DEFAULT_STRATEGIES)
  );
  const [profileLoading, setProfileLoading] = useState(false);
  const [profileError, setProfileError] = useState(null);
  const [profileActionLoading, setProfileActionLoading] = useState(null);
  const [profileList, setProfileList] = useState([]);
  const [activeProfileId, setActiveProfileId] = useState("");
  const [unifiedLoading, setUnifiedLoading] = useState(false);
  const [unifiedError, setUnifiedError] = useState(null);
  const [unifiedActionLoading, setUnifiedActionLoading] = useState(null);
  const [unifiedList, setUnifiedList] = useState([]);
  const [activeUnifiedId, setActiveUnifiedId] = useState("");
  const [unifiedDraftName, setUnifiedDraftName] = useState("");
  const [unifiedViewTab, setUnifiedViewTab] = useState<"strategy" | "execution">("strategy");
  const [comboLoading, setComboLoading] = useState(false);
  const [comboError, setComboError] = useState(null);
  const [comboActionLoading, setComboActionLoading] = useState(null);
  const [comboList, setComboList] = useState([]);
  const [activeComboId, setActiveComboId] = useState("");
  const [studioProfileBusy, setStudioProfileBusy] = useState(false);
  const [studioProfileActionLoading, setStudioProfileActionLoading] = useState(null);
  const [studioProfileList, setStudioProfileList] = useState([]);
  const [activeStudioProfileId, setActiveStudioProfileId] = useState("");
  const [studioProfileDraftName, setStudioProfileDraftName] = useState("");
  const [captureComboOnStudioSave, setCaptureComboOnStudioSave] = useState(true);
  const [activeTab, setActiveTab] = useState<"profiles" | "strategies" | "modules" | "adaptive" | "flow">("profiles");

  const {
    executionConfigSnapshot,
    expandedExecutionModules,
    toggleExecutionModuleExpanded,
    expandAllExecutionModules,
    collapseAllExecutionModules,
    refreshExecutionConfigSnapshot,
    updateExecutionConfigField,
    mergeExecutionConfigSnapshot,
    getExecutionParamValue,
  } = useExecutionModulesEditor({
    modules: EXECUTION_MODULES,
    normalizeExecutionParamValue,
    readExecutionConfigSnapshot,
  });

  const activeTicker = String(selectedTicker || "").toUpperCase();
  const strategyApiBase = (strategyApiUrl || defaultStrategyApiUrl).replace(/\/+$/, "");

  const loadAvailableTickers = useCallback(async () => {
    try {
      const resp = await fetch("/api/available-data?refresh=1");
      if (!resp.ok) return;
      const payload = await resp.json();
      const tickers = Array.isArray(payload?.tickers)
        ? payload.tickers.map((ticker) => String(ticker).toUpperCase())
        : [];
      if (!tickers.length) return;

      setAvailableTickers(tickers);
      if (!activeTicker && onTickerChange) {
        const fallback = tickers.includes("MU") ? "MU" : tickers[0];
        onTickerChange(fallback);
      }
    } catch (err) {
      console.error("Failed to load available tickers:", err);
    }
  }, [activeTicker, onTickerChange]);

  const loadStrategyUniverse = useCallback(async () => {
    try {
      const resp = await fetch(`${strategyApiBase}/api/strategies`);
      if (!resp.ok) return;
      const payload = await resp.json();
      const names = Object.keys(payload || {})
        .map((name) => canonicalizeStrategyName(name, DEFAULT_STRATEGIES))
        .filter(Boolean);
      if (names.length) {
        const merged = Array.from(new Set([...DEFAULT_STRATEGIES, ...names]));
        setStrategyUniverse(merged);
      }
    } catch (err) {
      console.error("Failed to load strategy universe:", err);
    }
  }, [strategyApiBase]);

  const loadProfileOptions = useCallback(async (ticker) => {
    if (!ticker) return null;
    const upperTicker = String(ticker).toUpperCase();
    setProfileLoading(true);
    setProfileError(null);
    try {
      const resp = await fetch(`/api/adaptive-tuner/options/${upperTicker}`);
      if (!resp.ok) {
        throw new Error(`HTTP ${resp.status}`);
      }
      const payload = await resp.json();
      const profiles = Array.isArray(payload?.profiles) ? payload.profiles : [];
      setProfileList(profiles);
      setActiveProfileId(normalizeProfileRefToken(payload?.active_profile_id));
      return payload;
    } catch (err) {
      console.error("Failed to load adaptive tuner profiles:", err);
      setProfileError("Failed to load adaptive tuned profiles for this ticker.");
      setProfileList([]);
      setActiveProfileId("");
      return null;
    } finally {
      setProfileLoading(false);
    }
  }, []);

  const loadComboOptions = useCallback(async (ticker) => {
    if (!ticker) return null;
    const upperTicker = String(ticker).toUpperCase();
    setComboLoading(true);
    setComboError(null);
    try {
      const resp = await fetch(`/api/strategy-combos/${upperTicker}`);
      if (!resp.ok) {
        throw new Error(`HTTP ${resp.status}`);
      }
      const payload = await resp.json();
      const combos = Array.isArray(payload?.profiles) ? payload.profiles : [];
      setComboList(combos);
      setActiveComboId(normalizeProfileRefToken(payload?.active_profile_id));
      return payload;
    } catch (err) {
      console.error("Failed to load strategy combinations:", err);
      setComboError("Failed to load strategy combinations for this ticker.");
      setComboList([]);
      setActiveComboId("");
      return null;
    } finally {
      setComboLoading(false);
    }
  }, []);

  const loadUnifiedOptions = useCallback(
    async (ticker, options: Record<string, any> = {}) => {
      if (!ticker) return null;
      const upperTicker = String(ticker).toUpperCase();
      setUnifiedLoading(true);
      setUnifiedError(null);
      try {
        const resp = await fetch(`/api/profiles/${upperTicker}`);
        if (resp.ok) {
          const payload = await resp.json();
          const profiles = normalizeUnifiedProfiles(payload?.profiles);
          const activeProfileId = normalizeProfileRefToken(payload?.active_profile_id);
          setUnifiedList(profiles);
          setActiveUnifiedId(activeProfileId);
          return { ...payload, profiles, active_profile_id: activeProfileId };
        }

        const fallbackPayload = buildLegacyUnifiedProfiles({
          ticker: upperTicker,
          tickerConfig: options?.tickerConfig,
          comboPayload: options?.comboPayload,
          tunedPayload: options?.tunedPayload,
        });
        const profiles = normalizeUnifiedProfiles(fallbackPayload?.profiles);
        const activeProfileId = normalizeProfileRefToken(fallbackPayload?.active_profile_id);
        setUnifiedList(profiles);
        setActiveUnifiedId(activeProfileId);
        setUnifiedError(null);
        return { ...fallbackPayload, profiles, active_profile_id: activeProfileId };
      } catch (err) {
        console.error("Failed to load unified profiles:", err);
        setUnifiedError("Failed to load unified profiles for this ticker.");
        setUnifiedList([]);
        setActiveUnifiedId("");
        return null;
      } finally {
        setUnifiedLoading(false);
      }
    },
    []
  );

  const loadTickerConfig = useCallback(
    async (ticker) => {
      if (!ticker) return;
      setLoading(true);
      setError(null);
      setNotice(null);
      setProfileError(null);

      try {
        const resp = await fetch(`/api/aos-config/${ticker}`);
        if (!resp.ok) {
          throw new Error(`HTTP ${resp.status}`);
        }
        const payload = await resp.json();
        const safePayload =
          payload && typeof payload === "object" && !Array.isArray(payload) ? payload : {};

        setRawTickerConfig(safePayload);
        const studioProfiles = normalizeStudioProfiles(
          safePayload?.[STUDIO_PROFILE_LIST_KEY],
          strategyUniverse
        );
        const requestedActiveStudioId = String(
          safePayload?.[STUDIO_PROFILE_ACTIVE_KEY] || ""
        ).trim();
        const resolvedStudioId = studioProfiles.some(
          (profile) => String(profile?.profile_id || "").trim() === requestedActiveStudioId
        )
          ? requestedActiveStudioId
          : "";
        setStudioProfileList(studioProfiles);
        setActiveStudioProfileId(resolvedStudioId);
        setStudioProfileDraftName(`${String(ticker || "").toUpperCase()}-studio`);
        setUnifiedDraftName(`${String(ticker || "").toUpperCase()}-profile`);
        refreshExecutionConfigSnapshot();
        const executionFromTickerConfig = asObject(safePayload?.positioning);
        if (Object.keys(executionFromTickerConfig).length) {
          mergeExecutionConfigSnapshot(executionFromTickerConfig);
          applyExecutionModuleSnapshot(executionFromTickerConfig);
          applyExecutionParamsSnapshot(executionFromTickerConfig);
        }
        const baseForm = normalizeTickerAdaptiveForm(safePayload, strategyUniverse);
        let nextForm = baseForm;
        const [profilePayload, comboPayload] = await Promise.all([
          loadProfileOptions(ticker),
          loadComboOptions(ticker),
        ]);
        const unifiedPayload = await loadUnifiedOptions(ticker, {
          tickerConfig: safePayload,
          comboPayload,
          tunedPayload: profilePayload,
        });
        const unifiedActiveId = normalizeProfileRefToken(unifiedPayload?.active_profile_id);
        const unifiedActiveProfile = Array.isArray(unifiedPayload?.profiles)
          ? unifiedPayload.profiles.find(
              (profile) => String(profile?.profile_id || "").trim() === unifiedActiveId
            )
          : null;
        const unifiedStrategyProfile = asObject(unifiedActiveProfile?.strategy_profile);
        if (Object.keys(unifiedStrategyProfile).length) {
          const mergedAdaptive = {
            ...asObject(safePayload?.adaptive),
            ...asObject(unifiedStrategyProfile?.adaptive),
          };
          const mergedTickerConfig = {
            ...safePayload,
            ...unifiedStrategyProfile,
            adaptive: mergedAdaptive,
          };
          nextForm = normalizeTickerAdaptiveForm(mergedTickerConfig, strategyUniverse);
          const unifiedCandidate = asObject(unifiedStrategyProfile?.adaptive_candidate);
          if (Object.keys(unifiedCandidate).length) {
            nextForm = applyTunedCandidateToForm(nextForm, unifiedCandidate, strategyUniverse);
          }
          const executionFromUnified = asObject(asObject(unifiedActiveProfile?.execution_profile)?.positioning);
          if (Object.keys(executionFromUnified).length) {
            mergeExecutionConfigSnapshot(executionFromUnified);
            applyExecutionModuleSnapshot(executionFromUnified);
            applyExecutionParamsSnapshot(executionFromUnified);
          }
        }
        const activeProfileId = normalizeProfileRefToken(
          profilePayload?.active_profile_id || safePayload?.active_adaptive_tuner_profile_id || ""
        );
        const activeProfile = Array.isArray(profilePayload?.profiles)
          ? profilePayload.profiles.find(
              (profile) => String(profile?.profile_id || "").trim() === activeProfileId
            )
          : null;
        if (
          !Object.keys(unifiedStrategyProfile).length &&
          activeProfile &&
          activeProfile.candidate &&
          typeof activeProfile.candidate === "object" &&
          !Array.isArray(activeProfile.candidate)
        ) {
          nextForm = applyTunedCandidateToForm(baseForm, activeProfile.candidate, strategyUniverse);
        }
        setForm(nextForm);
        setIsDirty(false);
      } catch (err) {
        console.error("Failed to load adaptive ticker config:", err);
        setError("Failed to load adaptive configuration for selected ticker.");
        setRawTickerConfig({});
        setForm(normalizeTickerAdaptiveForm({}, strategyUniverse));
        setIsDirty(false);
        setProfileList([]);
        setActiveProfileId("");
        setUnifiedList([]);
        setActiveUnifiedId("");
        setUnifiedError(null);
        setUnifiedDraftName("");
        setComboList([]);
        setActiveComboId("");
        setStudioProfileList([]);
        setActiveStudioProfileId("");
        setStudioProfileDraftName("");
      } finally {
        setLoading(false);
      }
    },
    [
      applyExecutionModuleSnapshot,
      applyExecutionParamsSnapshot,
      loadComboOptions,
      loadProfileOptions,
      loadUnifiedOptions,
      mergeExecutionConfigSnapshot,
      refreshExecutionConfigSnapshot,
      strategyUniverse,
    ]
  );

  useEffect(() => {
    loadAvailableTickers();
  }, [loadAvailableTickers]);

  useEffect(() => {
    loadStrategyUniverse();
  }, [loadStrategyUniverse]);

  useEffect(() => {
    if (!activeTicker) return;
    loadTickerConfig(activeTicker);
  }, [activeTicker, loadTickerConfig]);

  useEffect(() => {
    const handleComboUpdated = (event) => {
      const ticker = String(event?.detail?.ticker || "").toUpperCase();
      if (!ticker || ticker !== activeTicker) return;
      loadTickerConfig(activeTicker);
    };
    window.addEventListener("strategy-combo-updated", handleComboUpdated);
    return () => {
      window.removeEventListener("strategy-combo-updated", handleComboUpdated);
    };
  }, [activeTicker, loadTickerConfig]);

  const updateForm = (updater) => {
    setForm((prev) => {
      const next = typeof updater === "function" ? updater(prev) : updater;
      return next;
    });
    setIsDirty(true);
    setNotice(null);
  };

  const applyExecutionFieldChange = (configKey: string, value: unknown, options: Record<string, any> = {}) => {
    updateExecutionConfigField(configKey, value, options);
    setIsDirty(true);
    setNotice(null);
  };

  const updatePriorityList = (scope, key, nextList) => {
    const normalized = normalizeStrategyList(nextList, [], strategyUniverse);
    updateForm((prev) => {
      const nextScope = cloneMap(prev[scope]);
      nextScope[key] = normalized;
      return {
        ...prev,
        [scope]: nextScope,
      };
    });
  };

  const toggleStrategyInList = (scope, key, strategy) => {
    const current = form?.[scope]?.[key] || [];
    const exists = current.includes(strategy);
    const next = exists ? current.filter((item) => item !== strategy) : [...current, strategy];
    updatePriorityList(scope, key, next);
  };

  const movePriorityItem = (scope, key, index, direction) => {
    const current = form?.[scope]?.[key] || [];
    const target = index + direction;
    if (target < 0 || target >= current.length) return;
    const next = [...current];
    const [item] = next.splice(index, 1);
    next.splice(target, 0, item);
    updatePriorityList(scope, key, next);
  };

  const updateFlowBiasStrategies = (nextList) => {
    updateForm((prev) => ({
      ...prev,
      flow_bias_strategies: normalizeStrategyList(nextList, DEFAULT_FLOW_BIAS_STRATEGIES, strategyUniverse),
    }));
  };

  const toggleFlowBiasStrategy = (strategy) => {
    const current = form.flow_bias_strategies || [];
    const exists = current.includes(strategy);
    updateFlowBiasStrategies(exists ? current.filter((item) => item !== strategy) : [...current, strategy]);
  };

  const moveFlowBiasStrategy = (index, direction) => {
    const current = [...(form.flow_bias_strategies || [])];
    const target = index + direction;
    if (target < 0 || target >= current.length) return;
    const [item] = current.splice(index, 1);
    current.splice(target, 0, item);
    updateFlowBiasStrategies(current);
  };

  const handleSave = async () => {
    if (!activeTicker) return;
    setSaving(true);
    setError(null);
    setNotice(null);

    try {
      const normalizedForm = normalizeAdaptiveFormSnapshot(form, strategyUniverse);

      const currentConfig: Record<string, any> =
        rawTickerConfig && typeof rawTickerConfig === "object" && !Array.isArray(rawTickerConfig)
          ? (rawTickerConfig as Record<string, any>)
          : {};
      const currentAdaptive: Record<string, any> =
        currentConfig.adaptive && typeof currentConfig.adaptive === "object" && !Array.isArray(currentConfig.adaptive)
          ? (currentConfig.adaptive as Record<string, any>)
          : {};
      const currentPositioning = asObject(currentConfig.positioning);
      const executionSnapshot = readExecutionConfigSnapshot();
      const executionModulesSnapshot = normalizeExecutionModulesSnapshot(executionSnapshot);
      const executionParamsSnapshot = normalizeExecutionParamsSnapshot(executionSnapshot);

      const nextConfig = {
        ...currentConfig,
        strategy_selection_mode: normalizedForm.strategy_selection_mode,
        max_active_strategies: normalizedForm.max_active_strategies,
        positioning: {
          ...currentPositioning,
          ...executionModulesSnapshot,
          ...executionParamsSnapshot,
        },
        adaptive: {
          ...currentAdaptive,
          flow_bias_enabled: normalizedForm.flow_bias_enabled,
          use_ohlcv_fallbacks: normalizedForm.use_ohlcv_fallbacks,
          min_active_bars_before_switch: normalizedForm.min_active_bars_before_switch,
          switch_cooldown_bars: normalizedForm.switch_cooldown_bars,
          flow_bias_strategies: normalizedForm.flow_bias_strategies,
          regime_preferences: normalizedForm.regime_preferences,
          micro_regime_preferences: normalizedForm.micro_regime_preferences,
        },
      };

      const resp = await fetch("/api/aos-config/update", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ticker: activeTicker,
          config: nextConfig,
        }),
      });

      if (!resp.ok) {
        throw new Error(`HTTP ${resp.status}`);
      }

      setRawTickerConfig(nextConfig);
      setForm(normalizeTickerAdaptiveForm(nextConfig, strategyUniverse));
      setIsDirty(false);
      setNotice("Adaptive + execution configuration saved. Changes are applied on the next run start.");
    } catch (err) {
      console.error("Failed to save adaptive config:", err);
      setError("Failed to save adaptive configuration.");
    } finally {
      setSaving(false);
    }
  };

  const handleReload = async () => {
    if (!activeTicker) return;
    await loadTickerConfig(activeTicker);
  };

  const persistTickerConfig = async (nextConfig) => {
    const resp = await fetch("/api/aos-config/update", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ticker: activeTicker,
        config: nextConfig,
      }),
    });
    if (!resp.ok) {
      const data = await resp.json().catch(() => ({}));
      throw new Error(data?.detail || `HTTP ${resp.status}`);
    }
    setRawTickerConfig(nextConfig);
  };

  const handleLoadStudioProfileToEditor = (profile, options: Record<string, any> = {}) => {
    const profileId = String(profile?.profile_id || "").trim();
    if (!profileId) {
      setError("Cannot load Studio profile: missing profile ID.");
      return false;
    }
    const profileName = String(profile?.profile_name || profileId).trim() || profileId;
    const adaptiveSnapshot = normalizeAdaptiveFormSnapshot(profile?.adaptive_form, strategyUniverse);
    const executionSnapshot = normalizeExecutionModulesSnapshot(profile?.execution_modules);
    const executionParamsSnapshot = normalizeExecutionParamsSnapshot(profile?.execution_params);
    const comboProfileId = String(profile?.strategy_combo_profile_id || "").trim();

    setError(null);
    setForm(adaptiveSnapshot);
    setIsDirty(true);
    mergeExecutionConfigSnapshot({
      ...executionSnapshot,
      ...executionParamsSnapshot,
    });
    applyExecutionModuleSnapshot(executionSnapshot);
    applyExecutionParamsSnapshot(executionParamsSnapshot);

    if (!options.silent) {
      const comboNote = comboProfileId
        ? ` Linked combo profile: ${comboProfileId}.`
        : "";
      setNotice(`Loaded Studio profile ${profileName} into editor.${comboNote}`);
    }
    return true;
  };

  const handleSaveStudioProfile = async () => {
    if (!activeTicker) return;
    const profileName = String(studioProfileDraftName || "").trim();
    if (!profileName) {
      setError("Studio profile name is required.");
      return;
    }
    setStudioProfileBusy(true);
    setError(null);
    setNotice(null);
    try {
      const currentConfig =
        rawTickerConfig && typeof rawTickerConfig === "object" && !Array.isArray(rawTickerConfig)
          ? (rawTickerConfig as Record<string, any>)
          : {};
      const normalizedProfiles = normalizeStudioProfiles(
        currentConfig?.[STUDIO_PROFILE_LIST_KEY],
        strategyUniverse
      );
      const existingIds = new Set(
        normalizedProfiles
          .map((profile) => String(profile?.profile_id || "").trim())
          .filter(Boolean)
      );
      const existingByName = normalizedProfiles.find(
        (profile) =>
          String(profile?.profile_name || "")
            .trim()
            .toLowerCase() === profileName.toLowerCase()
      );

      let comboProfileId = String(activeComboId || "").trim();
      let comboProfileName = "";
      if (comboProfileId) {
        const linkedCombo = comboList.find(
          (profile) => String(profile?.profile_id || "").trim() === comboProfileId
        );
        comboProfileName = String(linkedCombo?.profile_name || comboProfileId).trim();
      }

      if (captureComboOnStudioSave) {
        const comboCaptureResp = await fetch("/api/strategy-combos/capture", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            ticker: activeTicker,
            profile_name: `${profileName}-combo`,
            strategy_api_url: strategyApiBase,
            set_active: false,
          }),
        });
        if (!comboCaptureResp.ok) {
          const data = await comboCaptureResp.json().catch(() => ({}));
          throw new Error(data?.detail || `HTTP ${comboCaptureResp.status}`);
        }
        const capturePayload = await comboCaptureResp.json();
        comboProfileId = String(capturePayload?.profile?.profile_id || "").trim();
        comboProfileName = String(capturePayload?.profile?.profile_name || comboProfileId).trim();
        await loadComboOptions(activeTicker);
      }

      const nowIso = new Date().toISOString();
      const profileId = existingByName
        ? String(existingByName.profile_id || "").trim()
        : buildStudioProfileId(activeTicker, profileName, existingIds);
      const createdAt = existingByName
        ? String(existingByName.created_at || nowIso)
        : nowIso;
      const nextProfile = {
        profile_id: profileId,
        profile_name: profileName,
        created_at: createdAt,
        updated_at: nowIso,
        adaptive_form: normalizeAdaptiveFormSnapshot(form, strategyUniverse),
        execution_modules: readExecutionModuleSnapshot(),
        execution_params: readExecutionParamsSnapshot(),
        strategy_combo_profile_id: comboProfileId,
        strategy_combo_profile_name: comboProfileName,
      };

      const nextProfiles = [
        nextProfile,
        ...normalizedProfiles.filter(
          (profile) => String(profile?.profile_id || "").trim() !== profileId
        ),
      ].slice(0, STUDIO_PROFILE_MAX_ITEMS);

      const nextConfig = {
        ...currentConfig,
        [STUDIO_PROFILE_LIST_KEY]: nextProfiles,
        [STUDIO_PROFILE_ACTIVE_KEY]: profileId,
      };

      await persistTickerConfig(nextConfig);
      setStudioProfileList(normalizeStudioProfiles(nextProfiles, strategyUniverse));
      setActiveStudioProfileId(profileId);
      setStudioProfileDraftName(profileName);
      const comboMessage = comboProfileId
        ? captureComboOnStudioSave
          ? ` Strategy combo ${comboProfileId} captured for this profile.`
          : ` Linked strategy combo: ${comboProfileId}.`
        : "";
      setNotice(`Studio profile ${profileName} saved.${comboMessage}`);
    } catch (err) {
      console.error("Failed to save Studio profile:", err);
      setError(err.message || "Failed to save Studio profile.");
    } finally {
      setStudioProfileBusy(false);
    }
  };

  const handleSetActiveStudioProfile = async (profileId) => {
    const targetProfileId = String(profileId || "").trim();
    if (!activeTicker || !targetProfileId) return;
    const targetProfile =
      studioProfileList.find(
        (profile) => String(profile?.profile_id || "").trim() === targetProfileId
      ) || null;
    if (!targetProfile) {
      setError(`Studio profile not found: ${targetProfileId}`);
      return;
    }
    setStudioProfileActionLoading(`active:${targetProfileId}`);
    setError(null);
    setNotice(null);
    try {
      const currentConfig =
        rawTickerConfig && typeof rawTickerConfig === "object" && !Array.isArray(rawTickerConfig)
          ? (rawTickerConfig as Record<string, any>)
          : {};
      const nextProfiles = normalizeStudioProfiles(
        currentConfig?.[STUDIO_PROFILE_LIST_KEY],
        strategyUniverse
      );
      const nextConfig = {
        ...currentConfig,
        [STUDIO_PROFILE_LIST_KEY]: nextProfiles,
        [STUDIO_PROFILE_ACTIVE_KEY]: targetProfileId,
      };
      await persistTickerConfig(nextConfig);
      setStudioProfileList(nextProfiles);
      setActiveStudioProfileId(targetProfileId);
      handleLoadStudioProfileToEditor(targetProfile, { silent: true });
      setNotice(
        `Studio profile ${targetProfile.profile_name || targetProfileId} is active and loaded into editor.`
      );
    } catch (err) {
      console.error("Failed to set active Studio profile:", err);
      setError(err.message || "Failed to set active Studio profile.");
    } finally {
      setStudioProfileActionLoading(null);
    }
  };

  const handleDeleteStudioProfile = async (profileId) => {
    const targetProfileId = String(profileId || "").trim();
    if (!activeTicker || !targetProfileId) return;
    const targetProfile =
      studioProfileList.find(
        (profile) => String(profile?.profile_id || "").trim() === targetProfileId
      ) || null;
    if (!targetProfile) return;
    if (typeof window !== "undefined") {
      const ok = window.confirm(
        `Delete Studio profile ${targetProfile.profile_name || targetProfileId}?`
      );
      if (!ok) return;
    }
    setStudioProfileActionLoading(`delete:${targetProfileId}`);
    setError(null);
    setNotice(null);
    try {
      const currentConfig =
        rawTickerConfig && typeof rawTickerConfig === "object" && !Array.isArray(rawTickerConfig)
          ? (rawTickerConfig as Record<string, any>)
          : {};
      const nextProfiles = normalizeStudioProfiles(
        currentConfig?.[STUDIO_PROFILE_LIST_KEY],
        strategyUniverse
      ).filter((profile) => String(profile?.profile_id || "").trim() !== targetProfileId);
      const currentActiveProfileId = String(activeStudioProfileId || "").trim();
      const nextActiveProfileId =
        currentActiveProfileId === targetProfileId
          ? String(nextProfiles[0]?.profile_id || "").trim()
          : currentActiveProfileId;
      const nextConfig = {
        ...currentConfig,
        [STUDIO_PROFILE_LIST_KEY]: nextProfiles,
        [STUDIO_PROFILE_ACTIVE_KEY]: nextActiveProfileId,
      };
      await persistTickerConfig(nextConfig);
      setStudioProfileList(nextProfiles);
      setActiveStudioProfileId(nextActiveProfileId);
      setNotice(`Studio profile ${targetProfile.profile_name || targetProfileId} deleted.`);
    } catch (err) {
      console.error("Failed to delete Studio profile:", err);
      setError(err.message || "Failed to delete Studio profile.");
    } finally {
      setStudioProfileActionLoading(null);
    }
  };

  const handleLoadProfileToEditor = (profile) => {
    const profileId = String(profile?.profile_id || "").trim();
    const candidate = profile?.candidate;
    if (!profileId || !candidate || typeof candidate !== "object") {
      setError("Cannot load profile: candidate payload is missing.");
      return;
    }
    const profileVersion = Number(profile?.adaptive_version || 1);
    setError(null);
    const versionLabel = profileVersion >= 2 ? ` (v2 vector)` : "";
    setNotice(`Loaded profile ${profileId}${versionLabel} into editor. Save if you want to persist these values.`);
    setForm((prev) => applyTunedCandidateToForm(prev, candidate, strategyUniverse));
    setIsDirty(true);
  };

  const handleSetActiveProfile = async (profileId) => {
    const targetProfileId = String(profileId || "").trim();
    if (!activeTicker || !targetProfileId) return;
    setProfileActionLoading(targetProfileId);
    setError(null);
    setNotice(null);
    try {
      const resp = await fetch("/api/adaptive-tuner/profiles/apply", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ticker: activeTicker, profile_id: targetProfileId }),
      });
      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        throw new Error(data?.detail || `HTTP ${resp.status}`);
      }
      await loadTickerConfig(activeTicker);
      setNotice(
        `Profile ${targetProfileId} is now active for ${activeTicker}. Next backtest run uses this adaptive setup.`
      );
    } catch (err) {
      console.error("Failed to set active adaptive profile:", err);
      setError(err.message || "Failed to apply adaptive profile.");
    } finally {
      setProfileActionLoading(null);
    }
  };

  const handleSetActiveCombo = async (comboId) => {
    const targetComboId = String(comboId || "").trim();
    if (!activeTicker || !targetComboId) return;
    setComboActionLoading(targetComboId);
    setError(null);
    setNotice(null);
    try {
      const resp = await fetch("/api/strategy-combos/apply", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ticker: activeTicker,
          profile_id: targetComboId,
          strategy_api_url: strategyApiBase,
          apply_now: false,
        }),
      });
      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        throw new Error(data?.detail || `HTTP ${resp.status}`);
      }
      await loadTickerConfig(activeTicker);
      window.dispatchEvent(
        new CustomEvent("strategy-combo-updated", {
          detail: { ticker: activeTicker, active_profile_id: targetComboId },
        })
      );
      setNotice(
        `Strategy combination ${targetComboId} is now active for ${activeTicker}.`
      );
    } catch (err) {
      console.error("Failed to set active strategy combination:", err);
      setError(err.message || "Failed to set active strategy combination.");
    } finally {
      setComboActionLoading(null);
    }
  };

  const handleLoadUnifiedProfileToEditor = (profile) => {
    const profileId = String(profile?.profile_id || "").trim();
    if (!profileId) {
      setError("Cannot load unified profile: missing profile ID.");
      return;
    }
    const strategyProfile = asObject(profile?.strategy_profile);
    const executionProfile = asObject(profile?.execution_profile);
    const mergedAdaptive = {
      ...asObject(rawTickerConfig?.adaptive),
      ...asObject(strategyProfile?.adaptive),
    };
    const mergedTickerConfig = {
      ...asObject(rawTickerConfig),
      ...strategyProfile,
      adaptive: mergedAdaptive,
    };
    let nextForm = normalizeTickerAdaptiveForm(mergedTickerConfig, strategyUniverse);
    const adaptiveCandidate = asObject(strategyProfile?.adaptive_candidate);
    if (Object.keys(adaptiveCandidate).length) {
      nextForm = applyTunedCandidateToForm(nextForm, adaptiveCandidate, strategyUniverse);
    }
    setForm(nextForm);
    setIsDirty(true);

    const executionPositioning = asObject(executionProfile?.positioning);
    if (Object.keys(executionPositioning).length) {
      mergeExecutionConfigSnapshot(executionPositioning);
      applyExecutionParamsSnapshot(executionPositioning);
    }

    const sourceCombo = String(
      profile?.source_strategy_combo_profile_id ||
        strategyProfile?.active_strategy_combo_profile_id ||
        ""
    ).trim();
    const sourceAdaptive = String(
      profile?.source_adaptive_tuner_profile_id ||
        strategyProfile?.active_adaptive_tuner_profile_id ||
        ""
    ).trim();
    if (sourceCombo) {
      setActiveComboId(sourceCombo);
    }
    if (sourceAdaptive) {
      setActiveProfileId(sourceAdaptive);
    }
    setNotice(
      `Unified profile ${profile?.profile_name || profileId} loaded into editor (Strategy + Execution).`
    );
  };

  const handleCaptureUnifiedProfile = async () => {
    if (!activeTicker) return;
    const profileName = String(unifiedDraftName || "").trim();
    if (!profileName) {
      setError("Unified profile name is required.");
      return;
    }
    setUnifiedActionLoading("capture");
    setError(null);
    setNotice(null);
    try {
      const resp = await fetch("/api/profiles/capture", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ticker: activeTicker,
          profile_name: profileName,
          strategy_api_url: strategyApiBase,
          set_active: true,
        }),
      });
      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        throw new Error(data?.detail || `HTTP ${resp.status}`);
      }
      await loadTickerConfig(activeTicker);
      setNotice(`Unified profile ${profileName} captured and set active.`);
    } catch (err) {
      console.error("Failed to capture unified profile:", err);
      setError(err.message || "Failed to capture unified profile.");
    } finally {
      setUnifiedActionLoading(null);
    }
  };

  const handleSetActiveUnifiedProfile = async (profile) => {
    const profileId = String(profile?.profile_id || "").trim();
    if (!activeTicker || !profileId) return;
    setUnifiedActionLoading(`active:${profileId}`);
    setError(null);
    setNotice(null);
    try {
      const resp = await fetch("/api/profiles/apply", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ticker: activeTicker,
          profile_id: profileId,
          strategy_api_url: strategyApiBase,
          apply_now: false,
          apply_execution: true,
        }),
      });
      if (!resp.ok) {
        const sourceCombo = String(
          profile?.source_strategy_combo_profile_id ||
            profile?.strategy_profile?.active_strategy_combo_profile_id ||
            ""
        ).trim();
        const sourceAdaptive = String(
          profile?.source_adaptive_tuner_profile_id ||
            profile?.strategy_profile?.active_adaptive_tuner_profile_id ||
            ""
        ).trim();
        if (!sourceCombo && !sourceAdaptive) {
          const data = await resp.json().catch(() => ({}));
          throw new Error(data?.detail || `HTTP ${resp.status}`);
        }
        if (sourceCombo) {
          const comboResp = await fetch("/api/strategy-combos/apply", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              ticker: activeTicker,
              profile_id: sourceCombo,
              strategy_api_url: strategyApiBase,
              apply_now: false,
            }),
          });
          if (!comboResp.ok) {
            const data = await comboResp.json().catch(() => ({}));
            throw new Error(data?.detail || `Legacy combo apply failed (HTTP ${comboResp.status})`);
          }
        }
        if (sourceAdaptive) {
          const adaptiveResp = await fetch("/api/adaptive-tuner/profiles/apply", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              ticker: activeTicker,
              profile_id: sourceAdaptive,
            }),
          });
          if (!adaptiveResp.ok) {
            const data = await adaptiveResp.json().catch(() => ({}));
            throw new Error(
              data?.detail || `Legacy adaptive apply failed (HTTP ${adaptiveResp.status})`
            );
          }
        }
      }
      await loadTickerConfig(activeTicker);
      setNotice(`Unified profile ${profile?.profile_name || profileId} is now active for ${activeTicker}.`);
    } catch (err) {
      console.error("Failed to set active unified profile:", err);
      setError(err.message || "Failed to apply unified profile.");
    } finally {
      setUnifiedActionLoading(null);
    }
  };

  const handleRecomposeFromCombo = (comboProfile) => {
    const enabledStrategies = extractEnabledStrategiesFromCombo(
      comboProfile,
      strategyUniverse
    );
    if (!enabledStrategies.length) {
      setError("Selected strategy combination has no enabled strategies to recompose.");
      return;
    }
    const enabledSet = new Set(enabledStrategies);
    updateForm((prev) => {
      const nextRegime = {};
      MACRO_REGIMES.forEach((key) => {
        nextRegime[key] = buildRecomposedList(
          prev?.regime_preferences?.[key],
          DEFAULT_REGIME_PREFERENCES[key],
          enabledSet
        );
      });
      const nextMicro = {};
      MICRO_REGIMES.forEach((key) => {
        nextMicro[key] = buildRecomposedList(
          prev?.micro_regime_preferences?.[key],
          DEFAULT_MICRO_PREFERENCES[key],
          enabledSet
        );
      });
      const nextFlowBias = buildRecomposedList(
        prev?.flow_bias_strategies,
        DEFAULT_FLOW_BIAS_STRATEGIES,
        enabledSet
      );
      const currentMaxActive = normalizeMaxActive(prev?.max_active_strategies, 3);
      const clampedMaxActive = Math.max(
        1,
        Math.min(currentMaxActive, enabledStrategies.length)
      );
      return {
        ...prev,
        max_active_strategies: clampedMaxActive,
        flow_bias_strategies: nextFlowBias,
        regime_preferences: nextRegime,
        micro_regime_preferences: nextMicro,
      };
    });
    setNotice(
      `Adaptive preferences recomposed from strategy combination (${enabledStrategies.length} enabled strategies).`
    );
  };

  const renderPriorityEditor = (scope, regimeKey, title) => {
    const selected = form?.[scope]?.[regimeKey] || [];

    return (
      <div className="adaptive-priority-editor" key={`${scope}-${regimeKey}`}>
        <div className="adaptive-priority-header">
          <span>{title}</span>
          <span className="adaptive-priority-count">{selected.length} selected</span>
        </div>

        <div className="adaptive-priority-list">
          {selected.length === 0 && (
            <div className="adaptive-empty">No strategies selected.</div>
          )}
          {selected.map((name, index) => (
            <div className="adaptive-priority-item" key={`${regimeKey}-${name}`}>
              <div className="adaptive-priority-item-title">
                <span className="adaptive-priority-rank">#{index + 1}</span>
                <span>{strategyLabel(name)}</span>
              </div>
              <div className="adaptive-priority-item-actions">
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={() => movePriorityItem(scope, regimeKey, index, -1)}
                  disabled={index === 0}
                >
                  Up
                </button>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={() => movePriorityItem(scope, regimeKey, index, 1)}
                  disabled={index === selected.length - 1}
                >
                  Down
                </button>
                <button
                  type="button"
                  className="btn btn-danger btn-sm"
                  onClick={() => toggleStrategyInList(scope, regimeKey, name)}
                >
                  Remove
                </button>
              </div>
            </div>
          ))}
        </div>

        <div className="adaptive-chip-grid">
          {strategyUniverse.map((name) => {
            const active = selected.includes(name);
            return (
              <button
                type="button"
                key={`${regimeKey}-chip-${name}`}
                className={`adaptive-chip ${active ? "active" : ""}`}
                onClick={() => toggleStrategyInList(scope, regimeKey, name)}
              >
                {strategyLabel(name)}
              </button>
            );
          })}
        </div>
      </div>
    );
  };

  const strategyModeLabel =
    form.strategy_selection_mode === "all_enabled" ? "All enabled strategies" : `Adaptive top-${normalizeMaxActive(form.max_active_strategies, 3)}`;
  const activeUnifiedProfile =
    unifiedList.find(
      (profile) => String(profile?.profile_id || "").trim() === String(activeUnifiedId || "").trim()
    ) || null;
  const activeComboProfile = comboList.find(
    (profile) => String(profile?.profile_id || "").trim() === activeComboId
  ) || null;
  const activeComboEnabledStrategies = extractEnabledStrategiesFromCombo(
    activeComboProfile,
    strategyUniverse
  );
  const activeStudioProfile =
    studioProfileList.find(
      (profile) => String(profile?.profile_id || "").trim() === activeStudioProfileId
    ) || null;
  const hasTickers = availableTickers.length > 0;

  const TABS = [
    { id: "profiles" as const, label: "Unified Profiles", icon: "📋" },
    { id: "strategies" as const, label: "Strategies", icon: "🎯" },
    { id: "modules" as const, label: "Global Modules", icon: "🔧" },
    { id: "adaptive" as const, label: "Adaptive", icon: "⚙" },
    { id: "flow" as const, label: "Flow", icon: "🔀" },
  ];

  return (
    <main className="adaptive-studio-page">
      <section className="card adaptive-studio-controls">
        <div className="card-header">
          <span className="card-title">Adaptive Strategy Studio</span>
          <div className="adaptive-toolbar">
            <select
              className="studio-header-ticker"
              value={activeTicker}
              onChange={(e) => {
                if (onTickerChange) onTickerChange(e.target.value);
              }}
              disabled={!hasTickers}
              title="Active ticker"
            >
              {!hasTickers && <option value="">No ticker</option>}
              {availableTickers.map((ticker) => (
                <option key={ticker} value={ticker}>
                  {ticker}
                </option>
              ))}
            </select>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={handleReload}
              disabled={
                loading ||
                saving ||
                studioProfileBusy ||
                unifiedLoading ||
                profileLoading ||
                comboLoading ||
                !!unifiedActionLoading ||
                !!profileActionLoading ||
                !!comboActionLoading ||
                !!studioProfileActionLoading ||
                !activeTicker
              }
            >
              {loading || unifiedLoading || profileLoading || comboLoading ? "Loading..." : "Reload"}
            </button>
            <button
              type="button"
              className="btn btn-primary"
              onClick={handleSave}
              disabled={
                saving ||
                studioProfileBusy ||
                loading ||
                !!unifiedActionLoading ||
                !!profileActionLoading ||
                !!comboActionLoading ||
                !!studioProfileActionLoading ||
                !activeTicker ||
                !isDirty
              }
            >
              {saving ? "Saving..." : "Save"}
            </button>
          </div>
        </div>

        {/* Tab bar */}
        <div className="studio-tabs">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              className={`studio-tab ${activeTab === tab.id ? "active" : ""}`}
              onClick={() => setActiveTab(tab.id)}
            >
              <span className="studio-tab-icon">{tab.icon}</span>
              <span>{tab.label}</span>
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div className="studio-tab-content">
          {/* Notices — always visible */}
          {(error || notice || unifiedError || profileError || comboError) && (
            <div className="adaptive-column" style={{ gap: 6 }}>
              {error && <div className="adaptive-error">{error}</div>}
              {notice && <div className="adaptive-notice">{notice}</div>}
              {unifiedError && <div className="adaptive-error">{unifiedError}</div>}
              {profileError && <div className="adaptive-error">{profileError}</div>}
              {comboError && <div className="adaptive-error">{comboError}</div>}
            </div>
          )}

          {/* ── Tab: Profiles ── */}
          {activeTab === "profiles" && (
            <div className="adaptive-column">
              <div className="adaptive-section">
                <h3>Unified Profiles</h3>
                <div style={{ display: "flex", gap: 8, alignItems: "end" }}>
                  <div className="form-group" style={{ flex: 1 }}>
                    <label htmlFor="unified_profile_name">Profile name</label>
                    <input
                      id="unified_profile_name"
                      type="text"
                      value={unifiedDraftName}
                      onChange={(e) => setUnifiedDraftName(e.target.value)}
                      placeholder={`${activeTicker || "TICKER"}-profile`}
                    />
                  </div>
                  <button
                    type="button"
                    className="btn btn-primary btn-sm"
                    onClick={handleCaptureUnifiedProfile}
                    disabled={
                      !activeTicker ||
                      loading ||
                      saving ||
                      unifiedLoading ||
                      !!unifiedActionLoading
                    }
                  >
                    {unifiedActionLoading === "capture" ? "Saving..." : "Capture"}
                  </button>
                </div>
                <div className="adaptive-empty" style={{ marginTop: 6 }}>
                  Jeden profil obsahuje sekcie Strategy profile + Execution profile.
                </div>
              </div>

              <div className="adaptive-section">
                <details open>
                  <summary>
                    <span>Unified Profile List</span>
                    <span className={`profile-badge ${activeUnifiedId ? "active-badge" : "inactive-badge"}`}>
                      {activeUnifiedId ? `Active: ${activeUnifiedId.slice(0, 12)}…` : "None active"}
                    </span>
                  </summary>
                  <div>
                    {unifiedLoading ? (
                      <div className="adaptive-empty">Loading…</div>
                    ) : !unifiedList.length ? (
                      <div className="adaptive-empty">No unified profiles saved yet.</div>
                    ) : (
                      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                        {unifiedList.map((profile, idx) => {
                          const profileId = String(profile?.profile_id || "").trim();
                          const isActive = !!profileId && profileId === activeUnifiedId;
                          const strategyCount = Object.keys(profile?.strategy_profile?.strategy_params || {}).length;
                          const hasExecution =
                            Object.keys(asObject(profile?.execution_profile?.positioning)).length > 0;
                          const isSettingActive =
                            unifiedActionLoading === `active:${profileId}`;
                          return (
                            <div className={`profile-table-row ${isActive ? "active" : ""}`} key={profileId || `up-${idx}`}>
                              <span className={`profile-badge ${isActive ? "active-badge" : "inactive-badge"}`}>
                                {isActive ? "●" : "○"}
                              </span>
                              <span className="profile-name">{profile?.profile_name || profileId || "profile"}</span>
                              <span className="profile-meta">{strategyCount} strategies</span>
                              <span className="profile-meta">{hasExecution ? "execution yes" : "execution no"}</span>
                              <span className="profile-meta">{formatProfileTimestamp(profile?.updated_at || profile?.created_at)}</span>
                              <div className="profile-table-actions">
                                <button
                                  className="btn btn-secondary btn-sm"
                                  onClick={() => handleLoadUnifiedProfileToEditor(profile)}
                                  disabled={!profileId || !!unifiedActionLoading}
                                >
                                  Load
                                </button>
                                <button
                                  className="btn btn-secondary btn-sm"
                                  onClick={() => handleSetActiveUnifiedProfile(profile)}
                                  disabled={!profileId || isActive || !!unifiedActionLoading || saving || loading}
                                >
                                  {isSettingActive ? "…" : isActive ? "Active" : "Set Active"}
                                </button>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                </details>
              </div>

              {activeUnifiedProfile && (
                <div className="adaptive-section">
                  <div style={{ display: "flex", gap: 8, marginBottom: 8 }}>
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      onClick={() => setUnifiedViewTab("strategy")}
                      style={{
                        opacity: unifiedViewTab === "strategy" ? 1 : 0.75,
                        borderColor:
                          unifiedViewTab === "strategy" ? "var(--accent-primary)" : undefined,
                      }}
                    >
                      Strategy profile
                    </button>
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      onClick={() => setUnifiedViewTab("execution")}
                      style={{
                        opacity: unifiedViewTab === "execution" ? 1 : 0.75,
                        borderColor:
                          unifiedViewTab === "execution" ? "var(--accent-primary)" : undefined,
                      }}
                    >
                      Execution profile
                    </button>
                  </div>
                  <pre
                    style={{
                      margin: 0,
                      padding: "10px",
                      borderRadius: "8px",
                      border: "1px solid var(--border-default)",
                      background: "var(--surface-2)",
                      color: "var(--text-primary)",
                      fontSize: "0.75rem",
                      overflowX: "auto",
                      maxHeight: "280px",
                    }}
                  >
{JSON.stringify(
  unifiedViewTab === "strategy"
    ? asObject(activeUnifiedProfile?.strategy_profile)
    : asObject(activeUnifiedProfile?.execution_profile),
  null,
  2
)}
                  </pre>
                </div>
              )}
            </div>
          )}

          {/* ── Tab: Strategies ── */}
          {activeTab === "strategies" && (
            <div className="adaptive-column">
              <StrategySettings
                apiUrl={strategyApiBase}
                selectedTicker={activeTicker}
                initialExpandAll
              />
            </div>
          )}

          {/* ── Tab: Global Modules ── */}
          {activeTab === "modules" && (
            <div className="adaptive-column">
              <div className="sc-panel">
                <div className="sc-toolbar">
                  <div className="sc-toolbar-left">
                    <span className="sc-counter">
                      {countEnabledExecutionModules(executionConfigSnapshot)}/{EXECUTION_MODULES.length}
                    </span>
                    <span className="sc-msg">
                      Global defaults synced with RunConfig execution snapshot.
                    </span>
                  </div>
                  <div className="sc-toolbar-right">
                    <button
                      className="sc-icon-btn"
                      onClick={refreshExecutionConfigSnapshot}
                      title="Refresh snapshot"
                    >
                      ↻
                    </button>
                    <button
                      className="sc-icon-btn"
                      onClick={expandAllExecutionModules}
                      title="Expand all"
                    >
                      ⬇
                    </button>
                    <button
                      className="sc-icon-btn"
                      onClick={collapseAllExecutionModules}
                      title="Collapse all"
                    >
                      ⬆
                    </button>
                  </div>
                </div>

                <div className="sc-list">
                  {EXECUTION_MODULES.map((module) => {
                    const enabled = !!toBoolean(executionConfigSnapshot?.[module.configKey], false);
                    const moduleFields = EXECUTION_MODULE_PARAM_FIELDS_BY_MODULE[module.key] || [];
                    const isExpanded = !!expandedExecutionModules[module.key];
                    const categoryLabel = EXECUTION_MODULE_CATEGORY_LABELS[module.category] || "Other";
                    return (
                      <div
                        key={module.key}
                        className={`sc-item ${enabled ? "on" : "off"} ${isExpanded ? "open" : ""}`}
                      >
                        <div
                          className="sc-item-head"
                          onClick={() => toggleExecutionModuleExpanded(module.key)}
                        >
                          <div className="sc-item-info">
                            <span className="sc-item-name">{module.label}</span>
                            <span className={`sc-cat ${module.category}`}>{categoryLabel}</span>
                            <span className="sc-regimes">{module.description}</span>
                          </div>
                          <div className="sc-item-controls" onClick={(e) => e.stopPropagation()}>
                            <label className="switch" htmlFor={`studio_module_${module.key}`}>
                              <input
                                id={`studio_module_${module.key}`}
                                type="checkbox"
                                checked={enabled}
                                onChange={(e) =>
                                  applyExecutionFieldChange(module.configKey, e.target.checked, {
                                    raw: true,
                                  })
                                }
                              />
                              <span className="slider" />
                            </label>
                          </div>
                          <span className={`sc-expand-arrow ${isExpanded ? "open" : ""}`}>›</span>
                        </div>

                        {isExpanded && (
                          <div className="sc-item-body">
                            <div className="sc-section">
                              <div className="sc-section-label">Configuration</div>
                              {moduleFields.length === 0 ? (
                                <div className="sc-msg">No additional configuration fields.</div>
                              ) : (
                                <div className="sc-grid">
                                  {moduleFields.map((field) => {
                                    const fieldId = `studio_${module.key}_${field.key}`;
                                    const fieldDisabled =
                                      typeof field?.disabledWhen === "function"
                                        ? !!field.disabledWhen(executionConfigSnapshot || {})
                                        : false;
                                    if (field.type === "boolean") {
                                      return (
                                        <div key={field.key} className="sc-field sc-field-bool">
                                          <label className="sc-field-label" htmlFor={fieldId}>
                                            {field.label}
                                          </label>
                                          <input
                                            id={fieldId}
                                            type="checkbox"
                                            className="sc-field-check"
                                            checked={!!getExecutionParamValue(field)}
                                            disabled={fieldDisabled}
                                            onChange={(e) =>
                                              applyExecutionFieldChange(
                                                field.key,
                                                normalizeExecutionParamValue(e.target.checked, field),
                                                { raw: true }
                                              )
                                            }
                                          />
                                        </div>
                                      );
                                    }
                                    if (field.type === "select") {
                                      const selectedValue = String(
                                        getExecutionParamValue(field) ?? field.fallback ?? ""
                                      );
                                      return (
                                        <div key={field.key} className="sc-field">
                                          <label className="sc-field-label" htmlFor={fieldId}>
                                            {field.label}
                                          </label>
                                          <select
                                            id={fieldId}
                                            className="sc-field-input"
                                            value={selectedValue}
                                            disabled={fieldDisabled}
                                            onChange={(e) =>
                                              applyExecutionFieldChange(
                                                field.key,
                                                normalizeExecutionParamValue(e.target.value, field),
                                                { raw: true }
                                              )
                                            }
                                          >
                                            {(Array.isArray(field.options) ? field.options : []).map((option) => {
                                              const optionValue = String(option?.value || "");
                                              const optionLabel = String(option?.label || optionValue);
                                              return (
                                                <option key={optionValue} value={optionValue}>
                                                  {optionLabel}
                                                </option>
                                              );
                                            })}
                                          </select>
                                        </div>
                                      );
                                    }
                                    return (
                                      <div key={field.key} className="sc-field">
                                        <label className="sc-field-label" htmlFor={fieldId}>
                                          {field.label}
                                        </label>
                                        <input
                                          id={fieldId}
                                          type="number"
                                          min={field.min}
                                          max={field.max}
                                          step={field.step}
                                          className="sc-field-input"
                                          value={getExecutionParamValue(field)}
                                          disabled={fieldDisabled}
                                          onChange={(e) =>
                                            applyExecutionFieldChange(
                                              field.key,
                                              normalizeExecutionParamValue(e.target.value, field),
                                              { raw: true }
                                            )
                                          }
                                        />
                                      </div>
                                    );
                                  })}
                                </div>
                              )}
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          )}

          {/* ── Tab: Adaptive ── */}
          {activeTab === "adaptive" && (
            <div className="adaptive-column">
              {/* Row 1: Selection Mode + Flow Gate side-by-side */}
              <div className="adaptive-grid-2col">
                <div className="adaptive-section">
                  <h3>Selection Mode</h3>
                  <div className="form-group">
                    <label htmlFor="adaptive_mode">Strategy selection mode</label>
                    <select
                      id="adaptive_mode"
                      value={form.strategy_selection_mode}
                      onChange={(e) =>
                        updateForm((prev) => ({
                          ...prev,
                          strategy_selection_mode: normalizeMode(e.target.value),
                        }))
                      }
                    >
                      <option value="adaptive_top_n">Adaptive Top-N</option>
                      <option value="all_enabled">All Enabled</option>
                    </select>
                  </div>
                  <div className="form-group">
                    <label htmlFor="adaptive_max_active">Max active strategies</label>
                    <input
                      id="adaptive_max_active"
                      type="number"
                      min="1"
                      max="20"
                      step="1"
                      value={normalizeMaxActive(form.max_active_strategies, 3)}
                      onChange={(e) =>
                        updateForm((prev) => ({
                          ...prev,
                          max_active_strategies: normalizeMaxActive(e.target.value, 3),
                        }))
                      }
                      disabled={form.strategy_selection_mode === "all_enabled"}
                    />
                  </div>
                </div>

                <div className="adaptive-section">
                  <h3>Flow Gate</h3>
                  <label className="field-row" htmlFor="adaptive_flow_bias_enabled">
                    <span>Prefer flow strategies when L2 exists</span>
                    <input
                      id="adaptive_flow_bias_enabled"
                      type="checkbox"
                      checked={!!form.flow_bias_enabled}
                      onChange={(e) =>
                        updateForm((prev) => ({
                          ...prev,
                          flow_bias_enabled: e.target.checked,
                        }))
                      }
                    />
                  </label>
                  <label className="field-row" htmlFor="adaptive_ohlcv_fallbacks">
                    <span>OHLCV fallback when no L2</span>
                    <input
                      id="adaptive_ohlcv_fallbacks"
                      type="checkbox"
                      checked={!!form.use_ohlcv_fallbacks}
                      onChange={(e) =>
                        updateForm((prev) => ({
                          ...prev,
                          use_ohlcv_fallbacks: e.target.checked,
                        }))
                      }
                    />
                  </label>
                  <div className="form-group">
                    <label htmlFor="adaptive_min_active_bars">Hysteresis (bars)</label>
                    <input
                      id="adaptive_min_active_bars"
                      type="number"
                      min="0"
                      step="1"
                      value={normalizeNonNegativeInt(form.min_active_bars_before_switch, 0)}
                      onChange={(e) =>
                        updateForm((prev) => ({
                          ...prev,
                          min_active_bars_before_switch: normalizeNonNegativeInt(e.target.value, 0),
                        }))
                      }
                    />
                  </div>
                  <div className="form-group">
                    <label htmlFor="adaptive_switch_cooldown_bars">Cooldown (bars)</label>
                    <input
                      id="adaptive_switch_cooldown_bars"
                      type="number"
                      min="0"
                      step="1"
                      value={normalizeNonNegativeInt(form.switch_cooldown_bars, 0)}
                      onChange={(e) =>
                        updateForm((prev) => ({
                          ...prev,
                          switch_cooldown_bars: normalizeNonNegativeInt(e.target.value, 0),
                        }))
                      }
                    />
                  </div>
                </div>
              </div> {/* end adaptive-grid-2col */}

              <div className="adaptive-section">
                <div className="adaptive-priority-editor">
                  <div className="adaptive-priority-header">
                    <span>Flow bias strategy order</span>
                    <span className="adaptive-priority-count">{(form.flow_bias_strategies || []).length} selected</span>
                  </div>

                  <div className="adaptive-priority-list">
                    {(form.flow_bias_strategies || []).length === 0 && (
                      <div className="adaptive-empty">No flow-bias strategies selected.</div>
                    )}
                    {(form.flow_bias_strategies || []).map((name, index) => (
                      <div className="adaptive-priority-item" key={`flow-bias-${name}`}>
                        <div className="adaptive-priority-item-title">
                          <span className="adaptive-priority-rank">#{index + 1}</span>
                          <span>{strategyLabel(name)}</span>
                        </div>
                        <div className="adaptive-priority-item-actions">
                          <button
                            type="button"
                            className="btn btn-secondary btn-sm"
                            onClick={() => moveFlowBiasStrategy(index, -1)}
                            disabled={index === 0}
                          >
                            Up
                          </button>
                          <button
                            type="button"
                            className="btn btn-secondary btn-sm"
                            onClick={() => moveFlowBiasStrategy(index, 1)}
                            disabled={index === (form.flow_bias_strategies || []).length - 1}
                          >
                            Down
                          </button>
                          <button
                            type="button"
                            className="btn btn-danger btn-sm"
                            onClick={() => toggleFlowBiasStrategy(name)}
                          >
                            Remove
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>

                  <div className="adaptive-chip-grid">
                    {strategyUniverse.map((name) => {
                      const active = (form.flow_bias_strategies || []).includes(name);
                      return (
                        <button
                          type="button"
                          key={`flow-chip-${name}`}
                          className={`adaptive-chip ${active ? "active" : ""}`}
                          onClick={() => toggleFlowBiasStrategy(name)}
                        >
                          {strategyLabel(name)}
                        </button>
                      );
                    })}
                  </div>
                </div>
              </div>

              {/* Regime Preferences - collapsible */}
              <div className="adaptive-grid-2col">
                <div className="adaptive-section">
                  <details>
                    <summary>Macro Regime Preferences</summary>
                    <div>
                      <div className="adaptive-editor-grid">
                        {MACRO_REGIMES.map((regime) =>
                          renderPriorityEditor("regime_preferences", regime, regime)
                        )}
                      </div>
                    </div>
                  </details>
                </div>
                <div className="adaptive-section">
                  <details>
                    <summary>Micro Regime Preferences</summary>
                    <div>
                      <div className="adaptive-editor-grid">
                        {MICRO_REGIMES.map((regime) =>
                          renderPriorityEditor("micro_regime_preferences", regime, regime)
                        )}
                      </div>
                    </div>
                  </details>
                </div>
              </div>
            </div>
          )}

          {/* ── Tab: Flow ── */}
          {activeTab === "flow" && (
            <div className="adaptive-column">
              <div className="adaptive-section">
                <h3>Decision Flow Diagram</h3>
                <div className="adaptive-flow-diagram">
                  <div className="adaptive-flow-node">
                    <strong>1) Regime detection</strong>
                    <div>Macro + micro regime are refreshed from current bars only.</div>
                  </div>
                  <div className="adaptive-flow-arrow">↓</div>
                  <div className="adaptive-flow-branch-row">
                    <div className="adaptive-flow-node">
                      <strong>2A) L2 branch</strong>
                      <div>
                        {form.flow_bias_enabled
                          ? `Flow bias ON: ${flowSummary(form.flow_bias_strategies)}`
                          : "Flow bias OFF: no forced L2-first priority"}
                      </div>
                    </div>
                    <div className="adaptive-flow-node">
                      <strong>2B) No-L2 branch</strong>
                      <div>
                        {form.use_ohlcv_fallbacks
                          ? "OHLCV fallback ON"
                          : "OHLCV fallback OFF"}
                      </div>
                    </div>
                  </div>
                  <div className="adaptive-flow-arrow">↓</div>
                  <div className="adaptive-flow-node">
                    <strong>3) Preference merge</strong>
                    <div>
                      Micro preference + macro regime preference + ticker/default candidates.
                    </div>
                    <div>
                      Unified profile: {activeUnifiedId || "none"}.
                      {activeUnifiedProfile &&
                        (String(activeUnifiedProfile?.source_strategy_combo_profile_id || "").trim() ||
                          String(activeUnifiedProfile?.source_adaptive_tuner_profile_id || "").trim()) && (
                          <>
                            {" "}
                            Legacy sources:
                            {" "}
                            {String(activeUnifiedProfile?.source_strategy_combo_profile_id || "").trim() || "combo:none"}
                            {" / "}
                            {String(activeUnifiedProfile?.source_adaptive_tuner_profile_id || "").trim() || "tuned:none"}
                            .
                          </>
                        )}
                    </div>
                  </div>
                  <div className="adaptive-flow-arrow">↓</div>
                  <div className="adaptive-flow-node">
                    <strong>3.5) Switch guard</strong>
                    <div>
                      Hysteresis: {normalizeNonNegativeInt(form.min_active_bars_before_switch, 0)} bars.
                      Cooldown: {normalizeNonNegativeInt(form.switch_cooldown_bars, 0)} bars.
                    </div>
                  </div>
                  <div className="adaptive-flow-arrow">↓</div>
                  <div className="adaptive-flow-node highlight">
                    <strong>4) Final selection</strong>
                    <div>{strategyModeLabel}</div>
                  </div>
                </div>
              </div>

            </div>
          )}
        </div>
      </section>
    </main>
  );
}

export default AdaptiveStrategyStudio;
