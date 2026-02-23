import { defaultStrategyApiUrl, normalizeIsoDay, formatTimestamp } from "../../utils";

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
export const RUN_CONFIG_DRAFT_VERSION = 8;
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
  context_risk_min_sl_pct: 0.30,
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

export const buildDefaultRunId = () => {
  const nonce = Math.random().toString(36).slice(2, 7);
  return `backtest-${Date.now()}-${nonce}`;
};

export const applyMuMomentumDefaults = (draft, ticker, previousTicker) => {
  const upperTicker = String(ticker || "").trim().toUpperCase();
  const priorTicker = String(previousTicker || "").trim().toUpperCase();
  if (upperTicker !== MU_TICKER || priorTicker === MU_TICKER) {
    return draft;
  }
  return {
    ...draft,
    // Favor fast first-start defaults; reproducibility presets remain available.
    momentum_diversification_override_enabled: false,
    momentum_apply_to_strategies: MU_DEFAULT_MOMENTUM_APPLY_TO_STRATEGIES,
    include_extended_hours: false,
    l2_confirm_enabled: false,
    apply_aos_optimizations_on_start: false,
    start_mode: START_MODE_FAST_RESTART,
    ...MU_INTRADAY_NON_OVERFIT_BASELINE,
  };
};

export const isPlainObject = (value) =>
  !!value && typeof value === "object" && !Array.isArray(value);

export const readPersistedRunConfigDraft = () => {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(RUN_CONFIG_DRAFT_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!isPlainObject(parsed)) return null;

    if (isPlainObject(parsed.config)) {
      return {
        version: Number(parsed.version || RUN_CONFIG_DRAFT_VERSION),
        saved_at: String(parsed.saved_at || ""),
        config: parsed.config,
        selected_unified_profile_id: String(parsed.selected_unified_profile_id || ""),
      };
    }

    // Backward compatibility for older draft format = plain config object.
    return {
      version: 0,
      saved_at: "",
      config: parsed,
      selected_unified_profile_id: "",
    };
  } catch (error) {
    console.warn("Failed to read persisted run config draft:", error);
    return null;
  }
};

export const normalizeDraftVersion = (value) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
};

export const applyRunConfigDraftMigrations = (mergedConfig, draftConfig, draftVersion) => {
  const version = normalizeDraftVersion(draftVersion);
  if (!isPlainObject(draftConfig)) {
    return mergedConfig;
  }
  const nextConfig = {
    ...mergedConfig,
    start_mode: deriveStartModeFromLegacyFlags(
      draftConfig,
      normalizeStartMode(mergedConfig.start_mode, START_MODE_FAST_RESTART),
    ),
  };

  if (version < 3 && !Object.prototype.hasOwnProperty.call(draftConfig, "start_mode")) {
    return nextConfig;
  }
  // v3 → v4: loosen context-risk & intraday-levels defaults
  if (version < 4) {
    nextConfig.context_risk_sl_buffer_pct = 0.05;
    nextConfig.context_risk_min_room_pct = 0.08;
    nextConfig.context_risk_min_effective_rr = 0.5;
    nextConfig.intraday_levels_min_levels_for_context = 1;
    nextConfig.intraday_levels_min_confluence_score = 1;
    nextConfig.intraday_levels_momentum_min_room_pct = 0.15;
  }
  // v4 → v5: loosen entry quality gates
  if (version < 5) {
    nextConfig.intraday_levels_micro_confirmation_enabled = false;
    nextConfig.intraday_levels_break_cooldown_bars = 3;
    nextConfig.intraday_levels_adaptive_window_rvol_threshold = 0.5;
    nextConfig.time_exit_bars = Math.max(nextConfig.time_exit_bars || 0, 15);
  }
  // v5 → v6: data-driven tuning — wider SL/TP, less noise exits
  if (version < 6) {
    nextConfig.trailing_activation_pct = 0.20;
    nextConfig.trailing_stop_pct = 0.80;
    nextConfig.break_even_buffer_pct = 0.03;
    nextConfig.break_even_min_hold_bars = 3;
    nextConfig.time_exit_bars = Math.max(nextConfig.time_exit_bars || 0, 20);
    nextConfig.context_risk_sl_buffer_pct = 0.10;
    nextConfig.context_risk_max_anchor_search_pct = 2.5;
    nextConfig.global_risk_min_stop_loss_pct = 0.15;
  }
  // v6 -> v7: default to all strategies enabled unless draft explicitly pins another mode.
  if (version < 7) {
    const hasExplicitMode = Object.prototype.hasOwnProperty.call(draftConfig, "strategy_selection_mode");
    if (!hasExplicitMode || !String(nextConfig.strategy_selection_mode || "").trim()) {
      nextConfig.strategy_selection_mode = "all_enabled";
    }
    const hasExplicitMax = Object.prototype.hasOwnProperty.call(draftConfig, "max_active_strategies");
    if (!hasExplicitMax || !Number.isFinite(Number(nextConfig.max_active_strategies))) {
      nextConfig.max_active_strategies = 20;
    }
  }
  // v7 -> v8: enable MU entry-quality gate by default for older drafts.
  if (version < 8) {
    const ticker = String(nextConfig.ticker || draftConfig.ticker || "").trim().toUpperCase();
    if (ticker === MU_TICKER) {
      nextConfig.intraday_levels_entry_quality_enabled = true;
    }
  }
  return nextConfig;
};

export const mergeRunConfigWithDefaults = (draftConfig, defaults, draftVersion = RUN_CONFIG_DRAFT_VERSION) => {
  if (!isPlainObject(draftConfig)) {
    return defaults;
  }
  const merged = { ...defaults };
  Object.keys(defaults).forEach((key) => {
    if (Object.prototype.hasOwnProperty.call(draftConfig, key)) {
      merged[key] = draftConfig[key];
    }
  });
  if (!Array.isArray(merged.momentum_sleeves)) {
    merged.momentum_sleeves = [];
  }
  if (!Array.isArray(merged.regime_filter)) {
    merged.regime_filter = [];
  }
  return applyRunConfigDraftMigrations(merged, draftConfig, draftVersion);
};

export const writePersistedRunConfigDraft = (config, selectedUnifiedProfileId) => {
  if (typeof window === "undefined") return null;
  try {
    const payload = {
      version: RUN_CONFIG_DRAFT_VERSION,
      saved_at: new Date().toISOString(),
      config,
      selected_unified_profile_id: String(selectedUnifiedProfileId || ""),
    };
    window.localStorage.setItem(RUN_CONFIG_DRAFT_STORAGE_KEY, JSON.stringify(payload));
    return payload;
  } catch (error) {
    console.warn("Failed to persist run config draft:", error);
    return null;
  }
};

export const parseRunKeyIdentity = (value) => {
  const raw = String(value || "").trim();
  if (!raw) return null;
  const parts = raw.split(":");
  if (parts.length < 3) return null;
  const date = String(parts.pop() || "").trim();
  const ticker = String(parts.pop() || "").trim().toUpperCase();
  const runId = String(parts.join(":") || "").trim();
  if (!runId || !ticker || !date) return null;
  return { run_id: runId, ticker, date };
};

export const RUN_RANGE_LABEL_PATTERN = /^(\d{4}-\d{2}-\d{2})_to_(\d{4}-\d{2}-\d{2})$/;

export const parseRunRangeLabel = (value) => {
  const token = String(value || "").trim();
  const match = token.match(RUN_RANGE_LABEL_PATTERN);
  if (!match) return null;
  const from = normalizeIsoDay(match[1]);
  const to = normalizeIsoDay(match[2]);
  if (!from || !to || from > to) return null;
  return { from, to };
};

export const resolveRunDateLabel = (payload) => {
  const rawDate = normalizeIsoDay(payload?.date);
  const rawDateFrom = normalizeIsoDay(payload?.date_from);
  const rawDateTo = normalizeIsoDay(payload?.date_to);
  const from = rawDateFrom || rawDate;
  const to = rawDateTo || rawDateFrom || rawDate;
  if (!from || !to) return "";
  // Keep parity with backend: explicit date_from/date_to always produces range label.
  if (rawDateFrom || rawDateTo || from !== to) {
    return `${from}_to_${to}`;
  }
  return from;
};

export const buildRunKeyFromStartPayload = (payload) => {
  const runId = String(payload?.run_id || "").trim();
  const ticker = String(payload?.ticker || "").trim().toUpperCase();
  const dateLabel = resolveRunDateLabel(payload);
  if (!runId || !ticker || !dateLabel) return "";
  return `${runId}:${ticker}:${dateLabel}`;
};

export const resolveAttachedRunDates = (runRow) => {
  const rawDate = String(runRow?.date || "").trim();
  const parsedRange = parseRunRangeLabel(rawDate);
  const from = normalizeIsoDay(runRow?.date_from) || parsedRange?.from || normalizeIsoDay(rawDate) || "";
  const to = normalizeIsoDay(runRow?.date_to) || parsedRange?.to || from || "";
  const singleDay = normalizeIsoDay(rawDate);
  return {
    date: singleDay || from || to || "",
    date_from: from,
    date_to: to,
  };
};


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

export const AVAILABLE_RANGE_HINT_PATTERN =
  /Available OHLCV range:\s*(\d{4}-\d{2}-\d{2})\s*to\s*(\d{4}-\d{2}-\d{2})/i;

export const parseIsoDayUtc = (value) => {
  const normalized = normalizeIsoDay(value);
  if (!normalized) return null;
  const parsed = new Date(`${normalized}T00:00:00Z`);
  if (Number.isNaN(parsed.getTime())) return null;
  return parsed;
};

export const formatIsoDayUtc = (date) => {
  if (!(date instanceof Date) || Number.isNaN(date.getTime())) return "";
  return date.toISOString().slice(0, 10);
};

export const buildIsoDayChunks = (rangeStart, rangeEnd, chunkDays = AUTO_PREWARM_CHUNK_DAYS) => {
  const startDate = parseIsoDayUtc(rangeStart);
  const endDate = parseIsoDayUtc(rangeEnd);
  if (!startDate || !endDate || startDate > endDate) {
    return [];
  }

  const daysPerChunk = Math.max(1, Math.trunc(Number(chunkDays) || 1));
  const chunks = [];
  let cursor = new Date(startDate.getTime());

  while (cursor <= endDate) {
    const chunkStart = new Date(cursor.getTime());
    const chunkEnd = new Date(cursor.getTime());
    chunkEnd.setUTCDate(chunkEnd.getUTCDate() + daysPerChunk - 1);
    if (chunkEnd > endDate) {
      chunkEnd.setTime(endDate.getTime());
    }
    chunks.push({
      date_from: formatIsoDayUtc(chunkStart),
      date_to: formatIsoDayUtc(chunkEnd),
    });
    cursor = new Date(chunkEnd.getTime());
    cursor.setUTCDate(cursor.getUTCDate() + 1);
  }

  return chunks;
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

export const clampIsoDayToRange = (day, range) => {
  const normalized = normalizeIsoDay(day);
  if (!normalized) return "";
  const min = normalizeIsoDay(range?.start);
  const max = normalizeIsoDay(range?.end);
  if (min && normalized < min) return min;
  if (max && normalized > max) return max;
  return normalized;
};

export const resolveDateRangeWithFallback = ({ range, from, to, fallbackDate }) => {
  const fallback = clampIsoDayToRange(fallbackDate, range) || normalizeIsoDay(fallbackDate);
  let nextFrom = clampIsoDayToRange(from, range) || fallback;
  let nextTo = clampIsoDayToRange(to, range) || fallback || nextFrom;
  if (nextFrom && nextTo && nextTo < nextFrom) {
    nextTo = nextFrom;
  }
  if (!nextFrom && nextTo) {
    nextFrom = nextTo;
  }
  if (!nextTo && nextFrom) {
    nextTo = nextFrom;
  }
  return {
    date_from: nextFrom || "",
    date_to: nextTo || "",
    date: nextFrom || nextTo || fallback || "",
  };
};

export const normalizeCoverageRange = (range) => {
  const start = normalizeIsoDay(range?.start);
  const end = normalizeIsoDay(range?.end);
  if (!start || !end || start > end) return null;
  return { start, end };
};

export const buildOverlapCoverageRange = (leftRange, rightRange) => {
  const left = normalizeCoverageRange(leftRange);
  const right = normalizeCoverageRange(rightRange);
  if (!left || !right) return null;
  const start = left.start > right.start ? left.start : right.start;
  const end = left.end < right.end ? left.end : right.end;
  if (!start || !end || start > end) return null;
  return { start, end };
};

export const resolveTickerCoverageRange = ({ availableData, ticker, l2Only = false }) => {
  const safeTicker = String(ticker || "").trim().toUpperCase();
  if (!availableData || !safeTicker) {
    return {
      effectiveRange: null,
      ohlcvRange: null,
      l2Range: null,
      overlapRange: null,
    };
  }

  const ohlcvRange = normalizeCoverageRange(availableData?.date_ranges?.[safeTicker]);
  const l2Range = normalizeCoverageRange(availableData?.l2_date_ranges?.[safeTicker]);
  const overlapRange =
    normalizeCoverageRange(availableData?.l2_overlap_date_ranges?.[safeTicker]) ||
    buildOverlapCoverageRange(ohlcvRange, l2Range);

  const effectiveRange = l2Only
    ? overlapRange || l2Range || ohlcvRange
    : ohlcvRange || overlapRange || l2Range;
  return {
    effectiveRange,
    ohlcvRange,
    l2Range,
    overlapRange,
  };
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

export const buildDefaultRunConfig = () => ({
  run_id: buildDefaultRunId(),
  ticker: "",
  date: "",
  date_from: "",
  date_to: "",
  trade_eval_mode: TRADE_EVAL_MODE_STANDARD,
  include_extended_hours: false,
  data_file: null,
  strategy_api_url: defaultStrategyApiUrl,
  risk_per_trade_pct: 1.0,
  max_position_notional_pct: 100.0,
  max_fill_participation_rate: 0.2,
  min_fill_ratio: 0.35,
  trailing_stop_pct: 0.8,
  global_exit_rr_ratio: 2.0,
  global_risk_atr_stop_multiplier: 1.0,
  global_risk_volume_stop_pct: 1.0,
  global_risk_min_stop_loss_pct: 0.15,
  trailing_activation_pct: 0.20,
  break_even_buffer_pct: 0.03,
  break_even_min_hold_bars: 3,
  break_even_activation_min_mfe_pct: 0.45,
  break_even_activation_min_r: 1.5,
  break_even_activation_min_r_trending_5m: 1.8,
  break_even_activation_min_r_choppy_5m: 1.2,
  break_even_activation_use_levels: true,
  break_even_activation_use_l2: true,
  enable_partial_take_profit: true,
  partial_take_profit_rr: 2.0,
  partial_take_profit_fraction: 0.4,
  partial_flow_deterioration_min_r: 0.5,
  partial_flow_deterioration_skip_be: true,
  trailing_enabled_in_choppy: false,
  time_exit_bars: 40,
  adverse_flow_exit_enabled: true,
  adverse_flow_threshold: 0.12,
  adverse_flow_min_hold_bars: 3,
  stop_loss_mode: "strategy",
  fixed_stop_loss_pct: 0.0,
  l2_only: false,
  l2_confirm_enabled: false,
  l2_min_imbalance: 0.0,
  l2_min_directional_consistency: 0.0,
  l2_min_signed_aggression: 0.0,
  l2_lookback_bars: 3,
  intraday_levels_enabled: true,
  intraday_levels_swing_left_bars: 2,
  intraday_levels_swing_right_bars: 2,
  intraday_levels_test_tolerance_pct: 0.08,
  intraday_levels_break_tolerance_pct: 0.05,
  intraday_levels_breakout_volume_lookback: 20,
  intraday_levels_breakout_volume_multiplier: 1.2,
  intraday_levels_volume_profile_bin_size_pct: 0.05,
  intraday_levels_value_area_pct: 0.7,
  intraday_levels_entry_quality_enabled: true,
  intraday_levels_min_levels_for_context: 1,
  intraday_levels_entry_tolerance_pct: 0.1,
  intraday_levels_break_cooldown_bars: 3,
  intraday_levels_rotation_max_tests: 2,
  intraday_levels_rotation_volume_max_ratio: 0.95,
  intraday_levels_recent_bounce_lookback_bars: 6,
  intraday_levels_require_recent_bounce_for_mean_reversion: true,
  intraday_levels_momentum_break_max_age_bars: 3,
  intraday_levels_momentum_min_room_pct: 0.15,
  intraday_levels_momentum_min_broken_ratio: 0.3,
  intraday_levels_min_confluence_score: 1,
  intraday_levels_memory_enabled: true,
  intraday_levels_memory_min_tests: 2,
  intraday_levels_memory_max_age_days: 5,
  intraday_levels_memory_decay_after_days: 2,
  intraday_levels_memory_decay_weight: 0.5,
  intraday_levels_memory_max_levels: 12,
  intraday_levels_opening_range_enabled: true,
  intraday_levels_opening_range_minutes: 30,
  intraday_levels_opening_range_break_tolerance_pct: 0.05,
  intraday_levels_poc_migration_enabled: true,
  intraday_levels_poc_migration_interval_bars: 30,
  intraday_levels_poc_migration_trend_threshold_pct: 0.2,
  intraday_levels_poc_migration_range_threshold_pct: 0.1,
  intraday_levels_composite_profile_enabled: true,
  intraday_levels_composite_profile_days: 3,
  intraday_levels_composite_profile_current_day_weight: 1.0,
  intraday_levels_spike_detection_enabled: true,
  intraday_levels_spike_min_wick_ratio: 0.6,
  intraday_levels_prior_day_anchors_enabled: true,
  intraday_levels_gap_analysis_enabled: true,
  intraday_levels_gap_min_pct: 0.3,
  intraday_levels_gap_momentum_threshold_pct: 2.0,
  intraday_levels_rvol_filter_enabled: true,
  intraday_levels_rvol_lookback_bars: 20,
  intraday_levels_rvol_min_threshold: 0.8,
  intraday_levels_rvol_strong_threshold: 1.5,
  intraday_levels_adaptive_window_enabled: true,
  intraday_levels_adaptive_window_min_bars: 6,
  intraday_levels_adaptive_window_rvol_threshold: 0.5,
  intraday_levels_adaptive_window_atr_ratio_max: 1.5,
  intraday_levels_micro_confirmation_enabled: false,
  intraday_levels_micro_confirmation_bars: 2,
  intraday_levels_confluence_sizing_enabled: false,
  liquidity_sweep_detection_enabled: true,
  sweep_min_aggression_z: -2.0,
  sweep_min_book_pressure_z: 1.5,
  sweep_max_price_change_pct: 0.05,
  sweep_atr_buffer_multiplier: 0.5,
  context_aware_risk_enabled: false,
  context_risk_sl_buffer_pct: 0.10,
  context_risk_min_sl_pct: 0.30,
  context_risk_min_room_pct: 0.08,
  context_risk_min_effective_rr: 0.5,
  context_risk_trailing_tighten_zone: 0.2,
  context_risk_trailing_tighten_factor: 0.5,
  context_risk_level_trail_enabled: true,
  context_risk_max_anchor_search_pct: 2.5,
  context_risk_min_level_tests_for_sl: 1,
  account_size_usd: 10000,
  regime_detection_minutes: 15,
  strategy_selection_mode: "all_enabled",
  max_active_strategies: 20,
  momentum_diversification_override_enabled: false,
  momentum_diversification_enabled: true,
  momentum_require_l2_coverage: true,
  momentum_route_enabled: true,
  momentum_route_require_l2_coverage: true,
  momentum_min_flow_score: 58,
  momentum_min_directional_consistency: 0.45,
  momentum_min_signed_aggression: 0.04,
  momentum_min_imbalance: 0.02,
  momentum_min_cvd: 0,
  momentum_min_directional_price_change_pct: 0,
  momentum_min_price_trend_efficiency: 0,
  momentum_min_last_bar_body_ratio: 0,
  momentum_min_last_bar_close_location: 0,
  momentum_min_delta_acceleration: 0,
  momentum_min_delta_price_divergence: 0,
  momentum_route_flow_score_impulse: 64,
  momentum_fail_fast_exit_enabled: true,
  momentum_fail_fast_max_bars: 3,
  momentum_fail_fast_signed_aggression_max: -0.08,
  momentum_fail_fast_book_pressure_max: -0.1,
  momentum_fail_fast_directional_consistency_max: 0.2,
  momentum_apply_to_strategies: "momentum_flow",
  momentum_allowed_micro_regimes: "",
  momentum_blocked_micro_regimes: "",
  momentum_sleeves: [],
  checkpoint_path: null,
  auto_save_checkpoint: true,
  start_mode: START_MODE_FAST_RESTART,
  apply_aos_optimizations_on_start: false,
});

export const buildNormalizedIntradayLevels = (config) => {
  const intradayLevelsEnabled = !!config.intraday_levels_enabled;
  const ticker = String(config.ticker || "").trim().toUpperCase();
  const forceMuEntryQualityGate = intradayLevelsEnabled && ticker === MU_TICKER;
  return {
    intraday_levels_enabled: intradayLevelsEnabled,
  intraday_levels_swing_left_bars: Math.max(
    1,
    Math.trunc(Number(config.intraday_levels_swing_left_bars || 2)),
  ),
  intraday_levels_swing_right_bars: Math.max(
    1,
    Math.trunc(Number(config.intraday_levels_swing_right_bars || 2)),
  ),
  intraday_levels_test_tolerance_pct: Math.max(
    0,
    Number(config.intraday_levels_test_tolerance_pct || 0),
  ),
  intraday_levels_break_tolerance_pct: Math.max(
    0,
    Number(config.intraday_levels_break_tolerance_pct || 0),
  ),
  intraday_levels_breakout_volume_lookback: Math.max(
    2,
    Math.trunc(Number(config.intraday_levels_breakout_volume_lookback || 20)),
  ),
  intraday_levels_breakout_volume_multiplier: Math.max(
    1,
    Number(config.intraday_levels_breakout_volume_multiplier || 1),
  ),
  intraday_levels_volume_profile_bin_size_pct: Math.max(
    0.01,
    Number(config.intraday_levels_volume_profile_bin_size_pct || 0.01),
  ),
  intraday_levels_value_area_pct: Math.min(
    0.95,
    Math.max(0.5, Number(config.intraday_levels_value_area_pct || 0.7)),
  ),
    intraday_levels_entry_quality_enabled: forceMuEntryQualityGate
      ? true
      : !!config.intraday_levels_entry_quality_enabled,
  intraday_levels_min_levels_for_context: Math.max(
    1,
    Math.trunc(Number(config.intraday_levels_min_levels_for_context || 2)),
  ),
  intraday_levels_entry_tolerance_pct: Math.max(
    0.01,
    Number(config.intraday_levels_entry_tolerance_pct || 0.1),
  ),
  intraday_levels_break_cooldown_bars: Math.max(
    1,
    Math.trunc(Number(config.intraday_levels_break_cooldown_bars || 6)),
  ),
  intraday_levels_rotation_max_tests: Math.max(
    1,
    Math.trunc(Number(config.intraday_levels_rotation_max_tests || 2)),
  ),
  intraday_levels_rotation_volume_max_ratio: Math.min(
    2.0,
    Math.max(0.1, Number(config.intraday_levels_rotation_volume_max_ratio || 0.95)),
  ),
  intraday_levels_recent_bounce_lookback_bars: Math.max(
    1,
    Math.trunc(Number(config.intraday_levels_recent_bounce_lookback_bars || 6)),
  ),
  intraday_levels_require_recent_bounce_for_mean_reversion:
    !!config.intraday_levels_require_recent_bounce_for_mean_reversion,
  intraday_levels_momentum_break_max_age_bars: Math.max(
    1,
    Math.trunc(Number(config.intraday_levels_momentum_break_max_age_bars || 3)),
  ),
  intraday_levels_momentum_min_room_pct: Math.max(
    0.01,
    Number(config.intraday_levels_momentum_min_room_pct || 0.3),
  ),
  intraday_levels_momentum_min_broken_ratio: Math.min(
    1.0,
    Math.max(0.0, Number(config.intraday_levels_momentum_min_broken_ratio || 0.3)),
  ),
  intraday_levels_min_confluence_score: Math.max(
    1,
    Math.trunc(Number(config.intraday_levels_min_confluence_score || 2)),
  ),
  intraday_levels_memory_enabled: !!config.intraday_levels_memory_enabled,
  intraday_levels_memory_min_tests: Math.max(
    1,
    Math.trunc(Number(config.intraday_levels_memory_min_tests || 2)),
  ),
  intraday_levels_memory_max_age_days: Math.max(
    1,
    Math.trunc(Number(config.intraday_levels_memory_max_age_days || 5)),
  ),
  intraday_levels_memory_decay_after_days: Math.max(
    1,
    Math.trunc(Number(config.intraday_levels_memory_decay_after_days || 2)),
  ),
  intraday_levels_memory_decay_weight: Math.min(
    1.0,
    Math.max(0.1, Number(config.intraday_levels_memory_decay_weight || 0.5)),
  ),
  intraday_levels_memory_max_levels: Math.max(
    1,
    Math.trunc(Number(config.intraday_levels_memory_max_levels || 12)),
  ),
  intraday_levels_opening_range_enabled: !!config.intraday_levels_opening_range_enabled,
  intraday_levels_opening_range_minutes: Math.max(
    5,
    Math.trunc(Number(config.intraday_levels_opening_range_minutes || 30)),
  ),
  intraday_levels_opening_range_break_tolerance_pct: Math.max(
    0.01,
    Number(config.intraday_levels_opening_range_break_tolerance_pct || 0.05),
  ),
  intraday_levels_poc_migration_enabled: !!config.intraday_levels_poc_migration_enabled,
  intraday_levels_poc_migration_interval_bars: Math.max(
    1,
    Math.trunc(Number(config.intraday_levels_poc_migration_interval_bars || 30)),
  ),
  intraday_levels_poc_migration_trend_threshold_pct: Math.max(
    0.01,
    Number(config.intraday_levels_poc_migration_trend_threshold_pct || 0.2),
  ),
  intraday_levels_poc_migration_range_threshold_pct: Math.max(
    0.01,
    Number(config.intraday_levels_poc_migration_range_threshold_pct || 0.1),
  ),
  intraday_levels_composite_profile_enabled: !!config.intraday_levels_composite_profile_enabled,
  intraday_levels_composite_profile_days: Math.max(
    1,
    Math.trunc(Number(config.intraday_levels_composite_profile_days || 3)),
  ),
  intraday_levels_composite_profile_current_day_weight: Math.max(
    0.1,
    Number(config.intraday_levels_composite_profile_current_day_weight || 1.0),
  ),
  intraday_levels_spike_detection_enabled: !!config.intraday_levels_spike_detection_enabled,
  intraday_levels_spike_min_wick_ratio: Math.min(
    0.95,
    Math.max(0.4, Number(config.intraday_levels_spike_min_wick_ratio || 0.6)),
  ),
  intraday_levels_prior_day_anchors_enabled: !!config.intraday_levels_prior_day_anchors_enabled,
  intraday_levels_gap_analysis_enabled: !!config.intraday_levels_gap_analysis_enabled,
  intraday_levels_gap_min_pct: Math.max(0, Number(config.intraday_levels_gap_min_pct || 0.3)),
  intraday_levels_gap_momentum_threshold_pct: Math.max(
    0.1,
    Number(config.intraday_levels_gap_momentum_threshold_pct || 2.0),
  ),
  intraday_levels_rvol_filter_enabled: !!config.intraday_levels_rvol_filter_enabled,
  intraday_levels_rvol_lookback_bars: Math.max(
    5,
    Math.trunc(Number(config.intraday_levels_rvol_lookback_bars || 20)),
  ),
  intraday_levels_rvol_min_threshold: Math.max(
    0,
    Number(config.intraday_levels_rvol_min_threshold || 0.8),
  ),
  intraday_levels_rvol_strong_threshold: Math.max(
    0.1,
    Number(config.intraday_levels_rvol_strong_threshold || 1.5),
  ),
  intraday_levels_adaptive_window_enabled: !!config.intraday_levels_adaptive_window_enabled,
  intraday_levels_adaptive_window_min_bars: Math.max(
    1,
    Math.trunc(Number(config.intraday_levels_adaptive_window_min_bars || 6)),
  ),
  intraday_levels_adaptive_window_rvol_threshold: Math.max(
    0,
    Number(config.intraday_levels_adaptive_window_rvol_threshold || 1.0),
  ),
  intraday_levels_adaptive_window_atr_ratio_max: Math.max(
    0.1,
    Number(config.intraday_levels_adaptive_window_atr_ratio_max || 1.5),
  ),
  intraday_levels_micro_confirmation_enabled: !!config.intraday_levels_micro_confirmation_enabled,
  intraday_levels_micro_confirmation_bars: Math.max(
    1,
    Math.trunc(Number(config.intraday_levels_micro_confirmation_bars || 2)),
  ),
    intraday_levels_confluence_sizing_enabled: !!config.intraday_levels_confluence_sizing_enabled,
    liquidity_sweep_detection_enabled: !!config.liquidity_sweep_detection_enabled,
    sweep_min_aggression_z: Number(config.sweep_min_aggression_z ?? -2.0),
    sweep_min_book_pressure_z: Number(config.sweep_min_book_pressure_z ?? 1.5),
    sweep_max_price_change_pct: Math.max(
      0,
      Number(config.sweep_max_price_change_pct ?? 0.05),
    ),
  };
};

export const buildNormalizedContextRisk = (config) => ({
  context_aware_risk_enabled: !!config.context_aware_risk_enabled,
  context_risk_sl_buffer_pct: Math.max(0, Number(config.context_risk_sl_buffer_pct || 0.05)),
  context_risk_min_sl_pct: Math.max(0, Number(config.context_risk_min_sl_pct || 0.30)),
  context_risk_min_room_pct: Math.max(0, Number(config.context_risk_min_room_pct || 0.08)),
  context_risk_min_effective_rr: Math.max(0, Number(config.context_risk_min_effective_rr || 0.5)),
  context_risk_trailing_tighten_zone: Math.max(
    0,
    Math.min(1, Number(config.context_risk_trailing_tighten_zone || 0.2)),
  ),
  context_risk_trailing_tighten_factor: Math.max(
    0,
    Math.min(1, Number(config.context_risk_trailing_tighten_factor || 0.5)),
  ),
  context_risk_level_trail_enabled: !!config.context_risk_level_trail_enabled,
  context_risk_max_anchor_search_pct: Math.max(
    0.1,
    Number(config.context_risk_max_anchor_search_pct || 1.5),
  ),
  context_risk_min_level_tests_for_sl: Math.max(
    0,
    Math.trunc(Number(config.context_risk_min_level_tests_for_sl || 1)),
  ),
  sweep_atr_buffer_multiplier: Math.max(
    0,
    Number(config.sweep_atr_buffer_multiplier ?? 0.5),
  ),
});
