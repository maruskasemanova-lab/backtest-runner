import { formatTimestamp } from "../../utils";

export const normalizeStrategySelectionMode = (value) => {
  const normalized = String(value || "").trim().toLowerCase();
  return normalized === "all_enabled" ? "all_enabled" : "adaptive_top_n";
};

export const parseMaxActiveStrategies = (value, fallback = 3) => {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || !Number.isInteger(parsed)) {
    return fallback;
  }
  return Math.max(1, Math.min(20, parsed));
};

export const normalizeProfileRefToken = (value) => {
  const token = String(value || "").trim();
  if (!token) return "";
  const lowered = token.toLowerCase();
  if (lowered === "none" || lowered === "null" || lowered === "n/a" || lowered === "na") {
    return "";
  }
  return token;
};

export const ACTIVE_UNIFIED_PROFILE_SENTINEL = "__ACTIVE_UNIFIED__";
export const MU_TICKER = "MU";
export const MU_REPRO_PROFILE_ID = "c4bb2197e651";
export const MU_REPRO_DATE_FROM = "2026-01-13";
export const MU_REPRO_DATE_TO = "2026-01-30";
export const MU_SCALP_PROFILE_ID = "mu_scalp_intrabar_fee_v1";
export const MU_SCALP_DATE_FROM = "2026-02-10";
export const MU_SCALP_DATE_TO = "2026-02-11";
export const AUTO_PREWARM_TICKERS = new Set(
  String(import.meta.env.VITE_AUTO_PREWARM_TICKERS || MU_TICKER)
    .split(",")
    .map((value) => String(value || "").trim().toUpperCase())
    .filter(Boolean)
);
export const AUTO_PREWARM_CHUNK_DAYS = 5;
export const AUTO_PREWARM_CHUNK_MAX_RETRIES = 3;
export const AUTO_PREWARM_RETRY_BASE_MS = 900;
export const SHOW_RUN_CONFIG_ADVANCED_EXECUTION_CONTROLS = true;
export const SHOW_UNIFIED_PROFILE_ADVANCED_VIEW = false;
export const RUN_CONFIG_DRAFT_STORAGE_KEY = "backtest_runner.run_config_draft.v2";
export const RUN_CONFIG_DRAFT_VERSION = 9;
export const RUN_ID_COLLISION_PATTERN = /Run already exists:/i;

export const START_MODE_STANDARD = "standard";
export const START_MODE_FAST_RESTART = "fast_restart";
export const START_MODE_RESUME_WARM_START = "resume_warm_start";
export const START_MODE_DAY_ISOLATED_AUDIT = "day_isolated_audit";
export const START_MODE_VALUES = new Set([
  START_MODE_STANDARD,
  START_MODE_FAST_RESTART,
  START_MODE_RESUME_WARM_START,
  START_MODE_DAY_ISOLATED_AUDIT,
]);
export const START_MODE_OPTIONS = [
  {
    value: START_MODE_STANDARD,
    label: "Standard",
    hint: "Full cold reset with no checkpoint load.",
  },
  {
    value: START_MODE_FAST_RESTART,
    label: "Fast Restart",
    hint: "Session reset only, no checkpoint load.",
  },
  {
    value: START_MODE_RESUME_WARM_START,
    label: "Resume (Warm Start)",
    hint: "Session reset + checkpoint load.",
  },
  {
    value: START_MODE_DAY_ISOLATED_AUDIT,
    label: "Day-Isolated Audit",
    hint: "Comparable mode: full reset + per-day cold start.",
  },
];
export const START_MODE_LABELS = {
  [START_MODE_STANDARD]: "Standard",
  [START_MODE_FAST_RESTART]: "Fast Restart",
  [START_MODE_RESUME_WARM_START]: "Resume (Warm Start)",
  [START_MODE_DAY_ISOLATED_AUDIT]: "Day-Isolated Audit",
};

export const TRADE_EVAL_MODE_STANDARD = "standard";
export const TRADE_EVAL_MODE_INTRABAR_1S = "intrabar_1s";
export const TRADE_EVAL_MODE_INTRABAR_5S = "intrabar_5s";
export const TRADE_EVAL_MODE_VALUES = new Set([
  TRADE_EVAL_MODE_STANDARD,
  TRADE_EVAL_MODE_INTRABAR_1S,
  TRADE_EVAL_MODE_INTRABAR_5S,
]);
export const TRADE_EVAL_MODE_OPTIONS = [
  {
    value: TRADE_EVAL_MODE_STANDARD,
    label: "Fast (bar)",
    hint: "Minute-bar evaluation only.",
  },
  {
    value: TRADE_EVAL_MODE_INTRABAR_5S,
    label: "Intrabar 5s",
    hint: "Intrabar evaluation sampled each 5 seconds.",
  },
  {
    value: TRADE_EVAL_MODE_INTRABAR_1S,
    label: "Intrabar 1s",
    hint: "Full 1-second intrabar evaluation.",
  },
];

export const normalizeStartMode = (value, fallback = START_MODE_FAST_RESTART) => {
  const normalized = String(value || "").trim().toLowerCase();
  return START_MODE_VALUES.has(normalized) ? normalized : fallback;
};

export const normalizeTradeEvalMode = (
  value,
  fallback = TRADE_EVAL_MODE_STANDARD,
) => {
  const normalized = String(value || "").trim().toLowerCase();
  return TRADE_EVAL_MODE_VALUES.has(normalized) ? normalized : fallback;
};

export const deriveStartModeFromLegacyFlags = (draftConfig, fallback = START_MODE_FAST_RESTART) => {
  if (!draftConfig || typeof draftConfig !== "object") {
    return fallback;
  }

  const explicitStartMode = String(draftConfig.start_mode || "").trim();
  if (explicitStartMode) {
    return normalizeStartMode(explicitStartMode, fallback);
  }

  const comparableMode = Boolean(draftConfig.comparable_mode);
  const coldStartEachDay = Boolean(draftConfig.cold_start_each_day);
  if (comparableMode || coldStartEachDay) {
    return START_MODE_DAY_ISOLATED_AUDIT;
  }

  const checkpointPath = String(draftConfig.checkpoint_path || "").trim();
  if (checkpointPath) {
    return START_MODE_RESUME_WARM_START;
  }

  if (typeof draftConfig.fast_start_session_reset === "boolean") {
    return draftConfig.fast_start_session_reset ? START_MODE_FAST_RESTART : START_MODE_STANDARD;
  }

  return fallback;
};

export const resolveStartModeRuntime = (startMode) => {
  const normalizedMode = normalizeStartMode(startMode);
  if (normalizedMode === START_MODE_STANDARD) {
    return {
      startMode: normalizedMode,
      comparableMode: false,
      orchestratorResetScope: "all",
      coldStartEachDay: false,
    };
  }
  if (normalizedMode === START_MODE_FAST_RESTART) {
    return {
      startMode: normalizedMode,
      comparableMode: false,
      orchestratorResetScope: "session",
      coldStartEachDay: false,
    };
  }
  if (normalizedMode === START_MODE_RESUME_WARM_START) {
    return {
      startMode: normalizedMode,
      comparableMode: false,
      orchestratorResetScope: "session",
      coldStartEachDay: false,
    };
  }
  return {
    startMode: START_MODE_DAY_ISOLATED_AUDIT,
    comparableMode: true,
    orchestratorResetScope: "all",
    coldStartEachDay: true,
  };
};

export const formatStartModeLabel = (startMode) =>
  START_MODE_LABELS[normalizeStartMode(startMode)] || START_MODE_LABELS[START_MODE_FAST_RESTART];

export const MU_DEFAULT_MOMENTUM_APPLY_TO_STRATEGIES = [
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
].join(",");

export const MU_INTRADAY_NON_OVERFIT_BASELINE = {
  strategy_selection_mode: "all_enabled",
  max_active_strategies: 20,
  intraday_levels_enabled: true,
  intraday_levels_entry_quality_enabled: true,
  intraday_levels_memory_enabled: true,
  intraday_levels_spike_detection_enabled: true,
  intraday_levels_prior_day_anchors_enabled: true,
  intraday_levels_gap_analysis_enabled: true,
  intraday_levels_rvol_filter_enabled: true,
  intraday_levels_rvol_min_threshold: 0.75,
  intraday_levels_rvol_strong_threshold: 1.35,
  intraday_levels_adaptive_window_enabled: true,
  intraday_levels_adaptive_window_min_bars: 8,
  intraday_levels_adaptive_window_rvol_threshold: 0.5,
  intraday_levels_adaptive_window_atr_ratio_max: 1.6,
  intraday_levels_micro_confirmation_enabled: false,
  intraday_levels_micro_confirmation_bars: 1,
  intraday_levels_confluence_sizing_enabled: true,
  liquidity_sweep_detection_enabled: true,
  sweep_min_aggression_z: -2.0,
  sweep_min_book_pressure_z: 1.5,
  sweep_max_price_change_pct: 0.05,
  sweep_atr_buffer_multiplier: 0.5,
  context_aware_risk_enabled: true,
  context_risk_sl_buffer_pct: 0.10,
  context_risk_min_sl_pct: 0.50,
  context_risk_min_room_pct: 0.08,
  context_risk_min_effective_rr: 0.5,
  context_risk_max_anchor_search_pct: 2.5,
  stop_loss_mode: "strategy",
  fixed_stop_loss_pct: 0.0,
  trailing_activation_pct: 0.20,
  trailing_stop_pct: 0.8,
  break_even_buffer_pct: 0.03,
  break_even_min_hold_bars: 3,
  time_exit_bars: 20,
};

export const DEFAULT_FIXED_STOP_LOSS_PCT = 0.3;

export const formatProfileTimestamp = formatTimestamp;

export const formatAdaptiveProfileCandidate = (candidate) => {
  if (!candidate || typeof candidate !== "object") return "candidate unavailable";
  const mode = normalizeStrategySelectionMode(candidate.strategy_selection_mode);
  const topN = parseMaxActiveStrategies(candidate.max_active_strategies, 3);
  const hysteresis = Number.isFinite(Number(candidate.min_active_bars_before_switch))
    ? Math.max(0, Number(candidate.min_active_bars_before_switch))
    : 0;
  const cooldown = Number.isFinite(Number(candidate.switch_cooldown_bars))
    ? Math.max(0, Number(candidate.switch_cooldown_bars))
    : 0;
  const flowBias = candidate.flow_bias_enabled ? "flow-bias on" : "flow-bias off";
  return `${mode === "all_enabled" ? "all enabled" : `adaptive top-${topN}`} | hysteresis ${hysteresis} | cooldown ${cooldown} | ${flowBias}`;
};

export const formatUnifiedProfileLabel = (profile) => {
  const profileId = String(profile?.profile_id || "profile");
  const profileName = String(profile?.profile_name || profileId);
  const strategySection =
    profile?.strategy_profile && typeof profile.strategy_profile === "object"
      ? profile.strategy_profile
      : {};
  const executionSection =
    profile?.execution_profile && typeof profile.execution_profile === "object"
      ? profile.execution_profile
      : {};
  const strategyCount = Object.keys(strategySection?.strategy_params || {}).length;
  const hasExecution = Object.keys(executionSection || {}).length > 0;
  const stamp = formatProfileTimestamp(profile?.updated_at || profile?.created_at);
  return `${profileName} | ${strategyCount} strategies | execution ${hasExecution ? "yes" : "no"} | ${stamp}`;
};

export const START_TIMING_PHASE_LABELS = {
  reset_orchestrator: "Orchestrator reset",
  clear_remote_sessions: "Remote session cleanup",
  apply_strategy_overrides: "Strategy overrides",
  apply_aos_optimizations: "AOS apply",
  force_enable_all_strategies: "Enable all strategies",
  apply_global_trailing: "Global trailing apply",
  load_run_bars: "Load bars",
  resolve_execution_config: "Resolve execution config",
  enrich_bars_with_l2: "L2 enrich",
  configure_session: "Configure session",
  load_reference_bars: "Load reference bars",
  runner_setup: "Runner setup",
};

export const formatStartTimingMs = (value) => {
  const ms = Number(value);
  if (!Number.isFinite(ms) || ms < 0) return "-";
  if (ms >= 1000) return `${(ms / 1000).toFixed(2)}s`;
  return `${ms.toFixed(0)}ms`;
};

export const formatStartTimingPhaseLabel = (phaseKey) => {
  const key = String(phaseKey || "").trim();
  if (!key) return "unknown";
  if (START_TIMING_PHASE_LABELS[key]) return START_TIMING_PHASE_LABELS[key];
  return key
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
};

export const formatPrewarmReadyMessage = (payload) => {
  const barsCount = Number(payload?.bars || 0);
  const useL2 = !!payload?.use_l2;
  const cacheHit = !!payload?.cache_hit;
  const prewarmScope = String(payload?.prewarm_scope || "range").toLowerCase();
  const l2GuardReason = String(payload?.l2_guard_reason || "").trim();
  const coveredMinutes = Number(payload?.l2?.covered_minutes || 0);
  const readyPrefix = cacheHit ? "Prewarm ready (cached)" : "Prewarm ready";
  const scopeSuffix = prewarmScope === "ticker" ? " [ticker]" : "";
  const guardSuffix = l2GuardReason ? " | L2 guard active" : "";
  return useL2
    ? `${readyPrefix}${scopeSuffix}: ${barsCount} bars, L2 ${coveredMinutes}m${guardSuffix}`
    : `${readyPrefix}${scopeSuffix}: ${barsCount} bars${guardSuffix}`;
};

export const normalizeAosTickerConfig = (payload) => {
  return payload && typeof payload === "object" && !Array.isArray(payload) ? payload : {};
};

export const normalizePositioningConfig = (payload) => {
  const positioning = payload?.positioning;
  return positioning && typeof positioning === "object" && !Array.isArray(positioning)
    ? positioning
    : {};
};

export const normalizeStopLossMode = (value, fallback = "strategy") => {
  const normalized = String(value || "").trim().toLowerCase();
  if (normalized === "fixed" || normalized === "capped") return normalized;
  return fallback;
};

export const resolveFixedStopLossPct = (mode, value) => {
  const normalizedMode = normalizeStopLossMode(mode, "strategy");
  const parsed = Number(value);
  if (normalizedMode === "strategy") {
    return Number.isFinite(parsed) ? Math.max(0, parsed) : 0;
  }
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return DEFAULT_FIXED_STOP_LOSS_PCT;
  }
  return parsed;
};

export const l2GateFieldConfig = [
  {
    key: "l2_min_imbalance",
    label: "Min Imbalance",
    hint: "0 disables this filter; increase only if entries are too noisy.",
    min: "0",
    step: "0.01",
  },
  {
    key: "l2_min_signed_aggression",
    label: "Min Signed Aggression",
    hint: "Higher values require stronger aggressive flow in entry direction.",
    min: "0",
    step: "0.01",
  },
  {
    key: "l2_min_directional_consistency",
    label: "Min Directional Consistency",
    hint: "Controls how consistently flow must align before entry is allowed.",
    min: "0",
    step: "0.01",
  },
  {
    key: "l2_lookback_bars",
    label: "Lookback Bars",
    hint: "Recent bars used for gate evaluation.",
    min: "1",
    step: "1",
  },
];

export const tcbboGateFieldConfig = [
  {
    key: "tcbbo_min_net_premium",
    label: "Min Net Premium ($)",
    hint: "0 keeps the gate permissive while still forcing TCBBO enrichment + diagnostics.",
    min: "0",
    step: "1000",
  },
  {
    key: "tcbbo_sweep_boost",
    label: "Sweep Boost",
    hint: "Confidence boost applied when TCBBO sweep flow aligns with signal direction.",
    min: "0",
    step: "0.5",
  },
  {
    key: "tcbbo_lookback_bars",
    label: "Lookback Bars",
    hint: "Recent bars used for TCBBO confirmation/regime override checks.",
    min: "1",
    step: "1",
  },
];
