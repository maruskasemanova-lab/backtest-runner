import { useState, useEffect, useCallback, useRef, useMemo } from "react";
import {
  toFiniteNumber,
  toBool,
  normalizeIsoDay,
  formatTimestamp,
  defaultStrategyApiUrl,
} from "../utils";
import MomentumDiversificationEditor from "./run-config/MomentumDiversificationEditor";
import { buildMomentumDiversificationOverridePayload } from "./run-config/momentumUtils";
import { useMomentumSleeves } from "./run-config/useMomentumSleeves";
import { useExecutionConfigBus } from "./run-config/useExecutionConfigBus";
import { useLoadingElapsedSeconds } from "./run-config/useLoadingElapsedSeconds";
import { useRunConfigProfiles } from "./run-config/useRunConfigProfiles";
import { useRunConfigEffectiveSnapshot } from "./run-config/useRunConfigEffectiveSnapshot";

const normalizeStrategySelectionMode = (value) => {
  const normalized = String(value || "").trim().toLowerCase();
  return normalized === "all_enabled" ? "all_enabled" : "adaptive_top_n";
};

const parseMaxActiveStrategies = (value, fallback = 3) => {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || !Number.isInteger(parsed)) {
    return fallback;
  }
  return Math.max(1, Math.min(20, parsed));
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

const ACTIVE_UNIFIED_PROFILE_SENTINEL = "__ACTIVE_UNIFIED__";
const MU_TICKER = "MU";
const MU_REPRO_PROFILE_ID = "c4bb2197e651";
const MU_REPRO_DATE_FROM = "2026-01-13";
const MU_REPRO_DATE_TO = "2026-01-30";
const MU_SCALP_PROFILE_ID = "mu_scalp_intrabar_fee_v1";
const MU_SCALP_DATE_FROM = "2026-02-10";
const MU_SCALP_DATE_TO = "2026-02-11";
const AUTO_PREWARM_TICKERS = new Set(
  String(import.meta.env.VITE_AUTO_PREWARM_TICKERS || MU_TICKER)
    .split(",")
    .map((value) => String(value || "").trim().toUpperCase())
    .filter(Boolean)
);
const AUTO_PREWARM_CHUNK_DAYS = 5;
const AUTO_PREWARM_CHUNK_MAX_RETRIES = 3;
const AUTO_PREWARM_RETRY_BASE_MS = 900;
const SHOW_RUN_CONFIG_ADVANCED_EXECUTION_CONTROLS = false;
const SHOW_UNIFIED_PROFILE_ADVANCED_VIEW = false;
const RUN_CONFIG_DRAFT_STORAGE_KEY = "backtest_runner.run_config_draft.v2";
const RUN_CONFIG_DRAFT_VERSION = 2;
const RUN_ID_COLLISION_PATTERN = /^Run already exists:/i;
const MU_DEFAULT_MOMENTUM_APPLY_TO_STRATEGIES = [
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

const buildDefaultRunId = () => {
  const nonce = Math.random().toString(36).slice(2, 7);
  return `backtest-${Date.now()}-${nonce}`;
};

const applyMuMomentumDefaults = (draft, ticker, previousTicker) => {
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
    fast_start_session_reset: true,
    comparable_mode: false,
  };
};

const isPlainObject = (value) =>
  !!value && typeof value === "object" && !Array.isArray(value);

const readPersistedRunConfigDraft = () => {
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

const normalizeDraftVersion = (value) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
};

const applyRunConfigDraftMigrations = (mergedConfig, draftConfig, draftVersion) => {
  const version = normalizeDraftVersion(draftVersion);
  if (version >= RUN_CONFIG_DRAFT_VERSION || !isPlainObject(draftConfig)) {
    return mergedConfig;
  }

  const legacyFastStartTuple =
    draftConfig.l2_confirm_enabled === true &&
    draftConfig.apply_aos_optimizations_on_start === true &&
    draftConfig.comparable_mode === true &&
    draftConfig.fast_start_session_reset === false;
  if (!legacyFastStartTuple) {
    return mergedConfig;
  }

  return {
    ...mergedConfig,
    l2_confirm_enabled: false,
    apply_aos_optimizations_on_start: false,
    comparable_mode: false,
    fast_start_session_reset: true,
    cold_start_each_day: false,
  };
};

const mergeRunConfigWithDefaults = (draftConfig, defaults, draftVersion = RUN_CONFIG_DRAFT_VERSION) => {
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
  return applyRunConfigDraftMigrations(merged, draftConfig, draftVersion);
};

const writePersistedRunConfigDraft = (config, selectedUnifiedProfileId) => {
  if (typeof window === "undefined") return;
  try {
    const payload = {
      version: RUN_CONFIG_DRAFT_VERSION,
      saved_at: new Date().toISOString(),
      config,
      selected_unified_profile_id: String(selectedUnifiedProfileId || ""),
    };
    window.localStorage.setItem(RUN_CONFIG_DRAFT_STORAGE_KEY, JSON.stringify(payload));
  } catch (error) {
    console.warn("Failed to persist run config draft:", error);
  }
};

const parseRunKeyIdentity = (value) => {
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

const RUN_RANGE_LABEL_PATTERN = /^(\d{4}-\d{2}-\d{2})_to_(\d{4}-\d{2}-\d{2})$/;

const parseRunRangeLabel = (value) => {
  const token = String(value || "").trim();
  const match = token.match(RUN_RANGE_LABEL_PATTERN);
  if (!match) return null;
  const from = normalizeIsoDay(match[1]);
  const to = normalizeIsoDay(match[2]);
  if (!from || !to || from > to) return null;
  return { from, to };
};

const resolveAttachedRunDates = (runRow) => {
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


const formatProfileTimestamp = formatTimestamp;

const formatAdaptiveProfileCandidate = (candidate) => {
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

const formatUnifiedProfileLabel = (profile) => {
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

const START_TIMING_PHASE_LABELS = {
  reset_orchestrator: "Orchestrator reset",
  clear_remote_sessions: "Remote session cleanup",
  apply_strategy_overrides: "Strategy overrides",
  apply_aos_optimizations: "AOS apply",
  apply_global_trailing: "Global trailing apply",
  load_run_bars: "Load bars",
  resolve_execution_config: "Resolve execution config",
  enrich_bars_with_l2: "L2 enrich",
  configure_session: "Configure session",
  load_reference_bars: "Load reference bars",
  runner_setup: "Runner setup",
};

const formatStartTimingMs = (value) => {
  const ms = Number(value);
  if (!Number.isFinite(ms) || ms < 0) return "-";
  if (ms >= 1000) return `${(ms / 1000).toFixed(2)}s`;
  return `${ms.toFixed(0)}ms`;
};

const formatStartTimingPhaseLabel = (phaseKey) => {
  const key = String(phaseKey || "").trim();
  if (!key) return "unknown";
  if (START_TIMING_PHASE_LABELS[key]) return START_TIMING_PHASE_LABELS[key];
  return key
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
};

const formatPrewarmReadyMessage = (payload) => {
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

const AVAILABLE_RANGE_HINT_PATTERN =
  /Available OHLCV range:\s*(\d{4}-\d{2}-\d{2})\s*to\s*(\d{4}-\d{2}-\d{2})/i;

const parseIsoDayUtc = (value) => {
  const normalized = normalizeIsoDay(value);
  if (!normalized) return null;
  const parsed = new Date(`${normalized}T00:00:00Z`);
  if (Number.isNaN(parsed.getTime())) return null;
  return parsed;
};

const formatIsoDayUtc = (date) => {
  if (!(date instanceof Date) || Number.isNaN(date.getTime())) return "";
  return date.toISOString().slice(0, 10);
};

const buildIsoDayChunks = (rangeStart, rangeEnd, chunkDays = AUTO_PREWARM_CHUNK_DAYS) => {
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

const normalizeAosTickerConfig = (payload) => {
  return payload && typeof payload === "object" && !Array.isArray(payload) ? payload : {};
};

const normalizePositioningConfig = (payload) => {
  const positioning = payload?.positioning;
  return positioning && typeof positioning === "object" && !Array.isArray(positioning)
    ? positioning
    : {};
};

const normalizeStopLossMode = (value, fallback = "strategy") => {
  const normalized = String(value || "").trim().toLowerCase();
  if (normalized === "fixed" || normalized === "capped") return normalized;
  return fallback;
};

const clampIsoDayToRange = (day, range) => {
  const normalized = normalizeIsoDay(day);
  if (!normalized) return "";
  const min = normalizeIsoDay(range?.start);
  const max = normalizeIsoDay(range?.end);
  if (min && normalized < min) return min;
  if (max && normalized > max) return max;
  return normalized;
};

const resolveDateRangeWithFallback = ({ range, from, to, fallbackDate }) => {
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

const normalizeCoverageRange = (range) => {
  const start = normalizeIsoDay(range?.start);
  const end = normalizeIsoDay(range?.end);
  if (!start || !end || start > end) return null;
  return { start, end };
};

const buildOverlapCoverageRange = (leftRange, rightRange) => {
  const left = normalizeCoverageRange(leftRange);
  const right = normalizeCoverageRange(rightRange);
  if (!left || !right) return null;
  const start = left.start > right.start ? left.start : right.start;
  const end = left.end < right.end ? left.end : right.end;
  if (!start || !end || start > end) return null;
  return { start, end };
};

const resolveTickerCoverageRange = ({ availableData, ticker, l2Only = false }) => {
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

const l2GateFieldConfig = [
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

function RunConfig({
  onStart,
  isRunning,
  onTickerChange,
  effectiveExecutionConfig,
  activeRuns = [],
  activeRunKey = "",
  onAttachRun,
  sidebarSubsection = "all",
  authToken = "",
  activeRunState = null,
}) {
  const persistedRunConfigDraftRef = useRef<Record<string, any> | null>(null);
  if (persistedRunConfigDraftRef.current === null) {
    persistedRunConfigDraftRef.current = readPersistedRunConfigDraft();
  }

  const [availableData, setAvailableData] = useState(null);
  const [availableDataError, setAvailableDataError] = useState(null);
  const [config, setConfig] = useState(() => {
    const defaults = {
      run_id: buildDefaultRunId(),
      ticker: "",
      date: "",
      date_from: "",
      date_to: "",
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
      global_risk_min_stop_loss_pct: 0.05,
      trailing_activation_pct: 0.45,
      break_even_buffer_pct: 0.0,
      break_even_min_hold_bars: 2,
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
      account_size_usd: 10000,
      regime_detection_minutes: 15,
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
      cold_start_each_day: false,
      comparable_mode: false,
      fast_start_session_reset: true,
      apply_aos_optimizations_on_start: false,
    };
    const persistedConfig =
      persistedRunConfigDraftRef.current && isPlainObject(persistedRunConfigDraftRef.current.config)
        ? persistedRunConfigDraftRef.current.config
        : null;
    const persistedVersion = normalizeDraftVersion(persistedRunConfigDraftRef.current?.version);
    return mergeRunConfigWithDefaults(persistedConfig, defaults, persistedVersion);
  });

  const [loading, setLoading] = useState(false);
  const [cacheFlushLoading, setCacheFlushLoading] = useState(false);
  const [cacheFlushMessage, setCacheFlushMessage] = useState(null);
  const [prewarmStatus, setPrewarmStatus] = useState({ state: "idle", message: "" });
  const [prewarmRevision, setPrewarmRevision] = useState(0);
  const [startTiming, setStartTiming] = useState(null);
  const [error, setError] = useState(null);
  const [useWarmStart, setUseWarmStart] = useState(false);
  const [checkpointCatalog, setCheckpointCatalog] = useState([]);
  const [checkpointLoading, setCheckpointLoading] = useState(false);
  const [checkpointSaving, setCheckpointSaving] = useState(false);
  const [checkpointMessage, setCheckpointMessage] = useState(null);
  const [checkpointApiUnavailable, setCheckpointApiUnavailable] = useState(false);
  const [remoteSettingsReady, setRemoteSettingsReady] = useState(false);
  const lastPrewarmKeyRef = useRef("");
  const activePrewarmRequestKeyRef = useRef("");
  const prewarmTimerRef = useRef(null);
  const prewarmAbortRef = useRef(null);
  const loadingElapsedSec = useLoadingElapsedSeconds(loading);
  const initialTickerSyncRef = useRef(false);
  const initialPersistedProfileAppliedRef = useRef(false);
  const remoteSettingsDebounceRef = useRef<number | null>(null);
  const lastHydratedAttachedRunKeyRef = useRef("");

  const strategyApiBase = (config.strategy_api_url || "").replace(/\/+$/, "");
  const runningRunOptions = useMemo(() => {
    const rows = Array.isArray(activeRuns) ? activeRuns : [];
    return rows.filter((row) => {
      if (!row || typeof row !== "object") return false;
      const running = !!row.is_running;
      const paused = !!row.is_paused;
      const phase = String(row.phase || "").trim().toUpperCase();
      return running || paused || phase === "INITIALIZED";
    });
  }, [activeRuns]);
  const showDateRangeControls = sidebarSubsection !== "profiles";
  const showProfileControls = sidebarSubsection !== "dates";

  const buildPrewarmPlan = useCallback(() => {
    const ticker = String(config.ticker || "").trim().toUpperCase();
    if (!ticker) return null;
    if (!AUTO_PREWARM_TICKERS.has(ticker)) return null;
    const basePayload = {
      ticker,
      allow_mock_data: false,
      l2_only: false,
      l2_confirm_enabled: !!config.l2_confirm_enabled,
      include_extended_hours: !!config.include_extended_hours,
      comparable_mode: false,
    };
    const coverage = resolveTickerCoverageRange({
      availableData,
      ticker,
      l2Only: !!config.l2_only,
    });
    const selectedDateFrom = normalizeIsoDay(config.date_from || config.date);
    const selectedDateTo = normalizeIsoDay(config.date_to || config.date_from || config.date);
    const selectedRangeReady = !!selectedDateFrom && !!selectedDateTo && selectedDateFrom <= selectedDateTo;
    const range = coverage.effectiveRange;
    const rangeStart = selectedRangeReady ? selectedDateFrom : normalizeIsoDay(range?.start);
    const rangeEnd = selectedRangeReady ? selectedDateTo : normalizeIsoDay(range?.end);
    const rangeChunks = buildIsoDayChunks(rangeStart, rangeEnd, AUTO_PREWARM_CHUNK_DAYS);

    if (rangeChunks.length > 0) {
      const chunkPayloads = rangeChunks.map((chunk) => ({
        ...basePayload,
        prewarm_scope: "range",
        date: chunk.date_from,
        date_from: chunk.date_from,
        date_to: chunk.date_to,
      }));
      return {
        keyPayload: {
          ...basePayload,
          prewarm_scope: "range",
          date_from: rangeStart,
          date_to: rangeEnd,
          chunk_days: AUTO_PREWARM_CHUNK_DAYS,
        },
        chunkPayloads,
      };
    }

    // Fallback for cases where coverage metadata is unavailable.
    return {
      keyPayload: {
        ...basePayload,
        prewarm_scope: "ticker",
      },
      chunkPayloads: [
        {
          ...basePayload,
          prewarm_scope: "ticker",
        },
      ],
    };
  }, [
    availableData,
    config.date,
    config.date_from,
    config.date_to,
    config.include_extended_hours,
    config.l2_confirm_enabled,
    config.l2_only,
    config.ticker,
  ]);

  const hydrateExecutionConfigFromPositioning = useCallback((payload) => {
    const positioning = normalizePositioningConfig(payload);
    if (!Object.keys(positioning).length) return;

    setConfig((prev) => ({
      ...prev,
      risk_per_trade_pct: toFiniteNumber(positioning.risk_per_trade_pct, prev.risk_per_trade_pct),
      max_position_notional_pct: toFiniteNumber(
        positioning.max_position_notional_pct,
        prev.max_position_notional_pct
      ),
      max_fill_participation_rate: toFiniteNumber(
        positioning.max_fill_participation_rate,
        prev.max_fill_participation_rate
      ),
      min_fill_ratio: toFiniteNumber(positioning.min_fill_ratio, prev.min_fill_ratio),
      trailing_stop_pct: Math.max(
        0,
        toFiniteNumber(positioning.trailing_stop_pct, prev.trailing_stop_pct)
      ),
      global_exit_rr_ratio: Math.max(
        0,
        toFiniteNumber(positioning.global_exit_rr_ratio, prev.global_exit_rr_ratio)
      ),
      global_risk_atr_stop_multiplier: Math.max(
        0,
        toFiniteNumber(
          positioning.global_risk_atr_stop_multiplier,
          prev.global_risk_atr_stop_multiplier
        )
      ),
      global_risk_volume_stop_pct: Math.max(
        0,
        toFiniteNumber(positioning.global_risk_volume_stop_pct, prev.global_risk_volume_stop_pct)
      ),
      global_risk_min_stop_loss_pct: Math.max(
        0,
        toFiniteNumber(
          positioning.global_risk_min_stop_loss_pct,
          prev.global_risk_min_stop_loss_pct
        )
      ),
      trailing_activation_pct: toFiniteNumber(
        positioning.trailing_activation_pct,
        prev.trailing_activation_pct
      ),
      break_even_buffer_pct: toFiniteNumber(
        positioning.break_even_buffer_pct,
        prev.break_even_buffer_pct
      ),
      break_even_min_hold_bars: Math.max(
        1,
        Math.trunc(
          toFiniteNumber(positioning.break_even_min_hold_bars, prev.break_even_min_hold_bars)
        )
      ),
      trailing_enabled_in_choppy: toBool(
        positioning.trailing_enabled_in_choppy,
        prev.trailing_enabled_in_choppy
      ),
      time_exit_bars: Math.max(
        1,
        Math.trunc(toFiniteNumber(positioning.time_exit_bars, prev.time_exit_bars))
      ),
      adverse_flow_exit_enabled: toBool(
        positioning.adverse_flow_exit_enabled,
        prev.adverse_flow_exit_enabled
      ),
      adverse_flow_threshold: toFiniteNumber(
        positioning.adverse_flow_threshold,
        prev.adverse_flow_threshold
      ),
      adverse_flow_min_hold_bars: Math.max(
        1,
        Math.trunc(
          toFiniteNumber(positioning.adverse_flow_min_hold_bars, prev.adverse_flow_min_hold_bars)
        )
      ),
      stop_loss_mode: normalizeStopLossMode(positioning.stop_loss_mode, prev.stop_loss_mode),
      fixed_stop_loss_pct: Math.max(
        0,
        toFiniteNumber(positioning.fixed_stop_loss_pct, prev.fixed_stop_loss_pct)
      ),
    }));
  }, []);

  const {
    aosLoading,
    aosError,
    aosTickerConfig,
    unifiedProfilesLoading,
    unifiedProfilesError,
    unifiedProfiles,
    activeUnifiedProfileId,
    setActiveUnifiedProfileId,
    selectedUnifiedProfileId,
    setSelectedUnifiedProfileId,
    fetchTickerAosConfig,
    fetchUnifiedProfiles,
    applyUnifiedProfile,
    reloadAosAndProfiles,
  } = useRunConfigProfiles({
    ticker: config.ticker,
    strategyApiUrl: config.strategy_api_url,
    activeProfileSentinel: ACTIVE_UNIFIED_PROFILE_SENTINEL,
    normalizeProfileRefToken,
    normalizeAosTickerConfig,
    hydrateExecutionConfigFromPositioning,
  });

  useEffect(() => {
    if (initialTickerSyncRef.current) return;
    const ticker = String(config.ticker || "").trim().toUpperCase();
    if (!ticker || typeof onTickerChange !== "function") return;
    initialTickerSyncRef.current = true;
    onTickerChange(ticker);
  }, [config.ticker, onTickerChange]);

  useEffect(() => {
    if (initialPersistedProfileAppliedRef.current) return;
    if (unifiedProfilesLoading) return;
    initialPersistedProfileAppliedRef.current = true;

    const persistedSelected = normalizeProfileRefToken(
      persistedRunConfigDraftRef.current?.selected_unified_profile_id,
    );
    if (!persistedSelected) return;
    if (persistedSelected === ACTIVE_UNIFIED_PROFILE_SENTINEL) {
      setSelectedUnifiedProfileId(ACTIVE_UNIFIED_PROFILE_SENTINEL);
      return;
    }
    const known = unifiedProfiles.some(
      (profile) => String(profile?.profile_id || "").trim() === persistedSelected,
    );
    if (known) {
      setSelectedUnifiedProfileId(persistedSelected);
    }
  }, [
    setSelectedUnifiedProfileId,
    unifiedProfiles,
    unifiedProfilesLoading,
  ]);

  useEffect(() => {
    setRemoteSettingsReady(false);
    if (!authToken || typeof window === "undefined") {
      setRemoteSettingsReady(true);
      return;
    }
    let cancelled = false;

    const hydrateFromRemoteSettings = async () => {
      try {
        const response = await fetch("/api/v2/user/settings", {
          headers: {
            Authorization: `Bearer ${authToken}`,
          },
        });
        if (!response.ok) {
          return;
        }
        const payload = await response.json().catch(() => ({}));
        const settings =
          payload && typeof payload.settings === "object" && !Array.isArray(payload.settings)
            ? payload.settings
            : {};
        const remoteRawDraft =
          settings && typeof settings.run_config_draft === "object" ? settings.run_config_draft : null;
        if (!remoteRawDraft) return;

        const normalizedRemoteDraft =
          isPlainObject(remoteRawDraft.config)
            ? {
                version: Number(remoteRawDraft.version || RUN_CONFIG_DRAFT_VERSION),
                saved_at: String(remoteRawDraft.saved_at || ""),
                config: remoteRawDraft.config,
                selected_unified_profile_id: String(remoteRawDraft.selected_unified_profile_id || ""),
              }
            : isPlainObject(remoteRawDraft)
              ? {
                  version: 0,
                  saved_at: String(remoteRawDraft.saved_at || ""),
                  config: remoteRawDraft,
                  selected_unified_profile_id: "",
                }
              : null;
        if (!normalizedRemoteDraft || !isPlainObject(normalizedRemoteDraft.config)) {
          return;
        }

        const localSavedAtRaw = String(persistedRunConfigDraftRef.current?.saved_at || "");
        const remoteSavedAtRaw = String(normalizedRemoteDraft.saved_at || "");
        const localSavedAtMs = Date.parse(localSavedAtRaw);
        const remoteSavedAtMs = Date.parse(remoteSavedAtRaw);
        const hasLocalConfig =
          !!persistedRunConfigDraftRef.current &&
          isPlainObject(persistedRunConfigDraftRef.current.config);
        const localIsNewer =
          hasLocalConfig &&
          Number.isFinite(localSavedAtMs) &&
          Number.isFinite(remoteSavedAtMs) &&
          localSavedAtMs > remoteSavedAtMs;
        if (localIsNewer) {
          return;
        }

        persistedRunConfigDraftRef.current = normalizedRemoteDraft;
        if (cancelled) return;

        setConfig((prev) =>
          mergeRunConfigWithDefaults(
            normalizedRemoteDraft.config,
            prev,
            normalizeDraftVersion(normalizedRemoteDraft.version),
          )
        );
        const remoteSelected = normalizeProfileRefToken(
          normalizedRemoteDraft.selected_unified_profile_id,
        );
        if (remoteSelected) {
          setSelectedUnifiedProfileId(remoteSelected);
        }
      } catch (error) {
        console.warn("Failed to hydrate run config draft from user settings:", error);
      } finally {
        if (!cancelled) {
          setRemoteSettingsReady(true);
        }
      }
    };

    hydrateFromRemoteSettings();
    return () => {
      cancelled = true;
    };
  }, [authToken, setSelectedUnifiedProfileId]);

  useEffect(() => {
    writePersistedRunConfigDraft(config, selectedUnifiedProfileId);
  }, [config, selectedUnifiedProfileId]);

  useEffect(() => {
    if (!authToken || typeof window === "undefined") return undefined;
    if (!remoteSettingsReady) return undefined;

    if (remoteSettingsDebounceRef.current !== null) {
      window.clearTimeout(remoteSettingsDebounceRef.current);
      remoteSettingsDebounceRef.current = null;
    }
    const timeoutId = window.setTimeout(async () => {
      const draftPayload = {
        version: RUN_CONFIG_DRAFT_VERSION,
        saved_at: new Date().toISOString(),
        config,
        selected_unified_profile_id: String(selectedUnifiedProfileId || ""),
      };
      persistedRunConfigDraftRef.current = draftPayload;
      try {
        await fetch("/api/v2/user/settings", {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${authToken}`,
          },
          body: JSON.stringify({
            settings: {
              run_config_draft: draftPayload,
            },
          }),
        });
      } catch (error) {
        console.warn("Failed to persist run config draft to user settings:", error);
      }
    }, 650);
    remoteSettingsDebounceRef.current = timeoutId;

    return () => {
      if (remoteSettingsDebounceRef.current !== null) {
        window.clearTimeout(remoteSettingsDebounceRef.current);
        remoteSettingsDebounceRef.current = null;
      }
    };
  }, [authToken, config, remoteSettingsReady, selectedUnifiedProfileId]);

  const formatCheckpointLabel = (item) => {
    const path = item?.path || "";
    const file = path.split(/[\\/]/).pop() || path || "(unknown)";
    const created = item?.created_at ? new Date(item.created_at).toLocaleString() : "unknown time";
    const trades = Number(item?.source?.total_trades || 0);
    const wr = item?.source?.win_rate;
    const wrText = typeof wr === "number" ? `${(wr * 100).toFixed(1)}%` : "n/a";
    return `${file} | ${trades} trades | WR ${wrText} | ${created}`;
  };

  const fetchCheckpoints = async (preferredPath = null) => {
    if (!strategyApiBase || checkpointApiUnavailable) {
      return;
    }

    setCheckpointLoading(true);
    setCheckpointMessage(null);
    try {
      const resp = await fetch(`${strategyApiBase}/api/orchestrator/checkpoints`);
      if (!resp.ok) {
        if (resp.status === 401 || resp.status === 403 || resp.status === 404) {
          setCheckpointApiUnavailable(true);
          setCheckpointCatalog([]);
          setCheckpointMessage("Checkpoint catalog is not available in this environment.");
          return;
        }
        throw new Error(`HTTP ${resp.status}`);
      }

      const payload = await resp.json();
      const catalog = Array.isArray(payload) ? payload : [];
      setCheckpointCatalog(catalog);

      if (preferredPath) {
        setConfig((prev) => ({ ...prev, checkpoint_path: preferredPath }));
      } else if (useWarmStart && !config.checkpoint_path && catalog.length > 0) {
        setConfig((prev) => ({ ...prev, checkpoint_path: catalog[0].path || null }));
      }
    } catch (err) {
      setCheckpointApiUnavailable(true);
      console.warn("Checkpoint catalog load disabled:", err);
      setCheckpointMessage("Checkpoint API is not reachable right now.");
    } finally {
      setCheckpointLoading(false);
    }
  };

  const handleSaveCheckpointNow = async () => {
    if (!strategyApiBase) {
      setCheckpointMessage("Strategy API URL is missing.");
      return;
    }

    setCheckpointSaving(true);
    setCheckpointMessage(null);
    try {
      const params = new URLSearchParams();
      if (config.run_id) params.set("run_id", config.run_id);
      if (config.ticker) params.set("ticker", config.ticker);
      if (config.date_from) params.set("date_from", config.date_from);
      if (config.date_to) params.set("date_to", config.date_to);
      const query = params.toString();
      const saveUrl = `${strategyApiBase}/api/orchestrator/checkpoint/save${query ? `?${query}` : ""}`;

      const resp = await fetch(saveUrl, { method: "POST" });
      if (!resp.ok) {
        throw new Error(`HTTP ${resp.status}`);
      }

      const payload = await resp.json();
      const savedPath = payload?.path || null;
      if (savedPath) {
        setUseWarmStart(true);
        setConfig((prev) => ({ ...prev, checkpoint_path: savedPath }));
        await fetchCheckpoints(savedPath);
      }
      setCheckpointMessage(savedPath ? `Checkpoint saved: ${savedPath}` : "Checkpoint saved.");
    } catch (err) {
      console.error("Checkpoint save failed:", err);
      setCheckpointMessage("Checkpoint save failed.");
    } finally {
      setCheckpointSaving(false);
    }
  };

  useEffect(() => {
    const applyAvailableData = (data) => {
      setAvailableData(data);

      if (!data?.tickers || data.tickers.length === 0) {
        setAvailableDataError("No tickers available from R2 manifest catalog.");
        return;
      }
      setAvailableDataError(null);

      let changedTickerToNotify = "";
      setConfig((prev) => {
        const prevTicker = String(prev.ticker || "").trim().toUpperCase();
        const hasPrevTicker = !!prevTicker;
        const hasPrevTickerInCatalog = hasPrevTicker && data.tickers.includes(prevTicker);
        const targetTicker = hasPrevTicker ? prevTicker : data.tickers[0];
        if (!hasPrevTicker && targetTicker && targetTicker !== prevTicker) {
          changedTickerToNotify = targetTicker;
        }
        const coverage = resolveTickerCoverageRange({
          availableData: data,
          ticker: targetTicker,
          l2Only: !!prev.l2_only,
        });
        const range = coverage.effectiveRange;
        const defaultDate = normalizeIsoDay(range?.end) || new Date().toISOString().split("T")[0];
        const dateSeed = hasPrevTicker
          ? resolveDateRangeWithFallback({
              range,
              from: prev.date_from,
              to: prev.date_to,
              fallbackDate: defaultDate,
            })
          : resolveDateRangeWithFallback({
              range,
              from: defaultDate,
              to: defaultDate,
              fallbackDate: defaultDate,
            });
        if (hasPrevTicker && !hasPrevTickerInCatalog) {
          dateSeed.date = normalizeIsoDay(prev.date) || dateSeed.date;
          dateSeed.date_from = normalizeIsoDay(prev.date_from) || dateSeed.date_from;
          dateSeed.date_to = normalizeIsoDay(prev.date_to) || dateSeed.date_to;
        }
        const next = applyMuMomentumDefaults(
          {
            ...prev,
            ticker: targetTicker,
            ...dateSeed,
          },
          targetTicker,
          prev.ticker
        );
        return next;
      });

      if (onTickerChange && changedTickerToNotify) {
        onTickerChange(changedTickerToNotify);
      }
    };

    const fetchAvailableData = async () => {
      const retryDelaysMs = [0, 400, 1200];
      let lastErrorMessage = "";

      for (let attempt = 0; attempt < retryDelaysMs.length; attempt += 1) {
        const delayMs = retryDelaysMs[attempt];
        if (delayMs > 0) {
          // Strict R2 mode: retry transient backend/edge failures, no local fallback.
          await new Promise((resolve) => setTimeout(resolve, delayMs));
        }

        try {
          const resp = await fetch("/api/available-data?refresh=1");
          if (!resp.ok) {
            const payload = await resp.json().catch(() => ({}));
            const detail = String(payload?.detail || "").trim();
            lastErrorMessage = detail
              ? `Failed to load available data: ${detail}`
              : `Failed to load available data (HTTP ${resp.status}).`;
            if (attempt < retryDelaysMs.length - 1) {
              continue;
            }
            setAvailableData(null);
            setAvailableDataError(lastErrorMessage);
            return;
          }

          const data = await resp.json();
          applyAvailableData(data);
          return;
        } catch (err) {
          console.error("Failed to fetch available data:", err);
          lastErrorMessage = "Failed to load available data from backend.";
          if (attempt < retryDelaysMs.length - 1) {
            continue;
          }
          setAvailableData(null);
          setAvailableDataError(lastErrorMessage);
          return;
        }
      }

      setAvailableData(null);
      setAvailableDataError(lastErrorMessage || "Failed to load available data from backend.");
    };

    fetchAvailableData();
  }, [onTickerChange]);

  useEffect(() => {
    setCheckpointApiUnavailable(false);
    fetchCheckpoints();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [strategyApiBase]);

  useExecutionConfigBus(config, setConfig);

  useEffect(() => {
    const plan = buildPrewarmPlan();
    if (!plan) {
      activePrewarmRequestKeyRef.current = "";
      setPrewarmStatus({ state: "idle", message: "" });
      return;
    }

    const prewarmKey = JSON.stringify(plan.keyPayload);
    if (prewarmKey === lastPrewarmKeyRef.current) {
      return;
    }
    activePrewarmRequestKeyRef.current = prewarmKey;

    if (prewarmTimerRef.current) {
      clearTimeout(prewarmTimerRef.current);
      prewarmTimerRef.current = null;
    }
    if (prewarmAbortRef.current) {
      prewarmAbortRef.current.abort();
      prewarmAbortRef.current = null;
    }

    prewarmTimerRef.current = setTimeout(async () => {
      const controller = new AbortController();
      prewarmAbortRef.current = controller;
      const totalChunks = Array.isArray(plan.chunkPayloads) ? plan.chunkPayloads.length : 0;
      const sleep = (ms) =>
        new Promise((resolve) => {
          setTimeout(resolve, ms);
        });
      const isCurrentRequest = () =>
        !controller.signal.aborted && activePrewarmRequestKeyRef.current === prewarmKey;
      const chunkLabel = (chunkPayload, index) => {
        if (chunkPayload?.prewarm_scope === "range") {
          const from = String(chunkPayload?.date_from || "").trim();
          const to = String(chunkPayload?.date_to || "").trim();
          return `${index + 1}/${totalChunks} ${from}..${to}`;
        }
        return `${index + 1}/${totalChunks} ticker scope`;
      };

      let totalBars = 0;
      let totalReferenceBars = 0;
      let l2CoveredMinutes = 0;
      let anyL2 = false;
      let anyL2Guard = false;
      let finalScope = "range";
      try {
        for (let index = 0; index < totalChunks; index += 1) {
          const chunkPayload = plan.chunkPayloads[index];
          const statusPrefix = `Prewarming cache chunk ${chunkLabel(chunkPayload, index)}...`;
          if (!isCurrentRequest()) return;
          setPrewarmStatus({ state: "warming", message: statusPrefix });

          let statusResp = await fetch("/api/run/prewarm/status", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(chunkPayload),
            signal: controller.signal,
          });
          let statusData = await statusResp.json().catch(() => ({}));
          if (!isCurrentRequest()) return;

          if (statusResp.ok && statusData?.in_progress && !statusData?.ready) {
            // Another worker/request is already warming this chunk - poll briefly.
            for (let poll = 0; poll < 18; poll += 1) {
              await sleep(1000);
              if (!isCurrentRequest()) return;
              statusResp = await fetch("/api/run/prewarm/status", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(chunkPayload),
                signal: controller.signal,
              });
              statusData = await statusResp.json().catch(() => ({}));
              if (statusResp.ok && statusData?.ready) break;
              if (!(statusResp.ok && statusData?.in_progress)) break;
            }
          }

          let result = null;
          if (statusResp.ok && statusData?.ready) {
            result = { ...statusData, cache_hit: true };
          } else {
            let lastError = null;
            for (let attempt = 1; attempt <= AUTO_PREWARM_CHUNK_MAX_RETRIES; attempt += 1) {
              if (!isCurrentRequest()) return;
              try {
                const resp = await fetch("/api/run/prewarm", {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify(chunkPayload),
                  signal: controller.signal,
                });
                const data = await resp.json().catch(() => ({}));
                if (!resp.ok) {
                  throw new Error(data?.detail || `HTTP ${resp.status}`);
                }
                result = data;
                break;
              } catch (err) {
                lastError = err;
                if (attempt >= AUTO_PREWARM_CHUNK_MAX_RETRIES) break;
                setPrewarmStatus({
                  state: "warming",
                  message: `${statusPrefix} retry ${attempt}/${AUTO_PREWARM_CHUNK_MAX_RETRIES - 1}`,
                });
                await sleep(AUTO_PREWARM_RETRY_BASE_MS * attempt);
              }
            }
            if (!result) {
              throw lastError || new Error("Prewarm request failed");
            }
          }

          totalBars += Number(result?.bars || 0);
          totalReferenceBars += Number(result?.reference_bars || 0);
          l2CoveredMinutes += Number(result?.l2?.covered_minutes || 0);
          anyL2 = anyL2 || !!result?.use_l2;
          anyL2Guard = anyL2Guard || !!result?.l2_guard_reason;
          finalScope = String(result?.prewarm_scope || finalScope || "range").toLowerCase();
        }

        if (!isCurrentRequest()) return;
        lastPrewarmKeyRef.current = prewarmKey;

        if (totalChunks > 1) {
          const summary = {
            bars: totalBars,
            reference_bars: totalReferenceBars,
            use_l2: anyL2,
            l2_guard_reason: anyL2Guard ? "active" : "",
            l2: { covered_minutes: l2CoveredMinutes },
            prewarm_scope: finalScope,
            cache_hit: false,
          };
          setPrewarmStatus({
            state: "ready",
            message: `${formatPrewarmReadyMessage(summary)} | chunks ${totalChunks}`,
          });
          return;
        }

        setPrewarmStatus({
          state: "ready",
          message: formatPrewarmReadyMessage({
            bars: totalBars,
            reference_bars: totalReferenceBars,
            use_l2: anyL2,
            l2_guard_reason: anyL2Guard ? "active" : "",
            l2: { covered_minutes: l2CoveredMinutes },
            prewarm_scope: finalScope,
            cache_hit: false,
          }),
        });
      } catch (err) {
        if (!isCurrentRequest()) return;
        setPrewarmStatus({
          state: "warming",
          message:
            "Prewarm unavailable (network timeout). Run can start now; remaining data will load in background.",
        });
        setTimeout(() => {
          if (activePrewarmRequestKeyRef.current !== prewarmKey) return;
          setPrewarmRevision((prev) => prev + 1);
        }, 1800);
      } finally {
        if (prewarmAbortRef.current === controller) {
          prewarmAbortRef.current = null;
        }
      }
    }, 250);

    return () => {
      if (prewarmTimerRef.current) {
        clearTimeout(prewarmTimerRef.current);
        prewarmTimerRef.current = null;
      }
      if (activePrewarmRequestKeyRef.current === prewarmKey) {
        activePrewarmRequestKeyRef.current = "";
      }
    };
  }, [buildPrewarmPlan, prewarmRevision]);

  useEffect(() => {
    return () => {
      if (prewarmTimerRef.current) {
        clearTimeout(prewarmTimerRef.current);
        prewarmTimerRef.current = null;
      }
      if (prewarmAbortRef.current) {
        prewarmAbortRef.current.abort();
        prewarmAbortRef.current = null;
      }
      activePrewarmRequestKeyRef.current = "";
    };
  }, []);

  const getDateRange = () => {
    const coverage = resolveTickerCoverageRange({
      availableData,
      ticker: config.ticker,
      l2Only: !!config.l2_only,
    });
    const range = coverage.effectiveRange;
    return {
      min: range?.start || null,
      max: range?.end || null,
      l2_min: coverage.l2Range?.start || null,
      l2_max: coverage.l2Range?.end || null,
      ohlcv_min: coverage.ohlcvRange?.start || null,
      ohlcv_max: coverage.ohlcvRange?.end || null,
    };
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setStartTiming(null);
    setError(null);
    setCacheFlushMessage(null);

    try {
      const comparableMode = !!config.comparable_mode;
      const stopLossMode = String(config.stop_loss_mode || "strategy").toLowerCase();
      const fixedStopLossPct = Math.max(0, Number(config.fixed_stop_loss_pct || 0));
      if (stopLossMode !== "strategy" && fixedStopLossPct <= 0) {
        throw new Error("Fixed stop-loss % must be > 0 when stop mode is fixed or capped.");
      }

      let unifiedProfileChanged = false;
      let unifiedAppliedProfileId = "";
      if (config.ticker) {
        const selectedProfileId =
          selectedUnifiedProfileId === ACTIVE_UNIFIED_PROFILE_SENTINEL
            ? ""
            : String(selectedUnifiedProfileId || "").trim();
        const activeProfileId = String(activeUnifiedProfileId || "").trim();
        const profileToApplyId = selectedProfileId || activeProfileId;
        if (profileToApplyId) {
          try {
            await applyUnifiedProfile(config.ticker, profileToApplyId, {
              applyNow: true,
              // Keep unified profile immutable; run-time edits from this form
              // are sent via run payload and should not persist to positioning store.
              applyExecution: false,
            });
            unifiedAppliedProfileId = profileToApplyId;
            if (profileToApplyId !== activeProfileId) {
              setActiveUnifiedProfileId(profileToApplyId);
              unifiedProfileChanged = true;
            }
          } catch (profileErr) {
            throw new Error(`Failed to apply unified profile: ${profileErr.message}`);
          }
        }
      }

      const payload: Record<string, any> = {
        run_id: String(config.run_id || "").trim(),
        ticker: String(config.ticker || "").trim().toUpperCase(),
        date_from: config.date_from,
        date_to: config.date_to,
        include_extended_hours: !!config.include_extended_hours,
        strategy_api_url: config.strategy_api_url,
        regime_detection_minutes: Number(config.regime_detection_minutes),
        account_size_usd: Number(config.account_size_usd),
        risk_per_trade_pct: Number(config.risk_per_trade_pct),
        max_position_notional_pct: Number(config.max_position_notional_pct),
        max_fill_participation_rate: Number(config.max_fill_participation_rate),
        min_fill_ratio: Number(config.min_fill_ratio),
        trailing_stop_pct: Math.max(0, Number(config.trailing_stop_pct || 0)),
        global_exit_rr_ratio: Math.max(0, Number(config.global_exit_rr_ratio || 0)),
        global_risk_atr_stop_multiplier: Math.max(
          0,
          Number(config.global_risk_atr_stop_multiplier || 0)
        ),
        global_risk_volume_stop_pct: Math.max(0, Number(config.global_risk_volume_stop_pct || 0)),
        global_risk_min_stop_loss_pct: Math.max(
          0,
          Number(config.global_risk_min_stop_loss_pct || 0)
        ),
        trailing_activation_pct: Number(config.trailing_activation_pct),
        break_even_buffer_pct: Number(config.break_even_buffer_pct),
        break_even_min_hold_bars: Number(config.break_even_min_hold_bars),
        trailing_enabled_in_choppy: !!config.trailing_enabled_in_choppy,
        time_exit_bars: Number(config.time_exit_bars),
        adverse_flow_exit_enabled: !!config.adverse_flow_exit_enabled,
        adverse_flow_threshold: Number(config.adverse_flow_threshold),
        adverse_flow_min_hold_bars: Number(config.adverse_flow_min_hold_bars),
        stop_loss_mode: stopLossMode,
        fixed_stop_loss_pct: fixedStopLossPct,
        l2_only: !!config.l2_only,
        l2_confirm_enabled: !!config.l2_confirm_enabled,
        l2_min_imbalance: Number(config.l2_min_imbalance),
        l2_min_directional_consistency: Number(config.l2_min_directional_consistency),
        l2_min_signed_aggression: Number(config.l2_min_signed_aggression),
        l2_lookback_bars: Number(config.l2_lookback_bars),
        comparable_mode: comparableMode,
        orchestrator_reset_scope: comparableMode
          ? "all"
          : (config.fast_start_session_reset ? "session" : "all"),
        apply_aos_optimizations_on_start: !!config.apply_aos_optimizations_on_start,
        // Strategy overrides are used as FE defaults; do not re-apply them at run start.
        apply_ticker_overrides_on_start: false,
        cold_start_each_day: comparableMode ? true : !!config.cold_start_each_day,
        checkpoint_path: comparableMode
          ? null
          : (useWarmStart ? (config.checkpoint_path || "").trim() || null : null),
        auto_save_checkpoint: comparableMode ? false : !!config.auto_save_checkpoint,
      };

      if (config.momentum_diversification_override_enabled) {
        payload.momentum_diversification_override = buildMomentumDiversificationOverridePayload(config);
      }

      if (config.data_file) {
        payload.data_file = config.data_file;
      }
      if (unifiedAppliedProfileId === MU_SCALP_PROFILE_ID) {
        payload.strategy_selection_mode = "all_enabled";
        payload.max_active_strategies = 1;
        payload.intrabar_execution_recalc_1s = true;
      }
      if (!comparableMode && useWarmStart && !payload.checkpoint_path) {
        // No checkpoint available - proceed with cold start (no blocking)
        console.info("Warm start enabled but no checkpoint selected, proceeding with cold start.");
      }
      let startResult;
      try {
        startResult = await onStart(payload);
      } catch (startErr) {
        const startMessage = String(startErr?.message || "");
        if (!RUN_ID_COLLISION_PATTERN.test(startMessage)) {
          throw startErr;
        }
        const retryRunId = buildDefaultRunId();
        const retryPayload = {
          ...payload,
          run_id: retryRunId,
        };
        setConfig((prev) => ({
          ...prev,
          run_id: retryRunId,
        }));
        startResult = await onStart(retryPayload);
      }
      const timingPayload = startResult?.start_timing;
      if (timingPayload && typeof timingPayload === "object") {
        setStartTiming(timingPayload);
      }
      const progressiveInfo = startResult?.progressive_loading;
      if (progressiveInfo?.enabled) {
        const pendingChunks = Number(progressiveInfo?.pending_chunks || 0);
        const loadedUntil = String(progressiveInfo?.loaded_until || "").trim();
        const targetEnd = String(progressiveInfo?.target_end || "").trim();
        setPrewarmStatus({
          state: "warming",
          message: `Run started immediately (loaded until ${loadedUntil || "n/a"}). Remaining chunks: ${pendingChunks} (target ${targetEnd || "n/a"}).`,
        });
      }
      if (unifiedProfileChanged && config.ticker) {
        Promise.allSettled([
          fetchTickerAosConfig(config.ticker, { hydrateExecution: true }),
          fetchUnifiedProfiles(config.ticker),
        ]).catch(() => null);
      }
    } catch (err) {
      setStartTiming(null);
      const message = String(err?.message || "Failed to start run.");
      const rangeHintMatch = message.match(AVAILABLE_RANGE_HINT_PATTERN);
      if (rangeHintMatch) {
        const hintedFrom = String(rangeHintMatch[1] || "").trim();
        const hintedTo = String(rangeHintMatch[2] || "").trim();
        if (hintedFrom && hintedTo) {
          setConfig((prev) => ({
            ...prev,
            date: hintedFrom,
            date_from: hintedFrom,
            date_to: hintedTo,
          }));
          setError(
            `${message} Date range was auto-adjusted to ${hintedFrom} -> ${hintedTo}. Start the run again.`
          );
          return;
        }
      }
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (field, value) => {
    setConfig((prev) => ({ ...prev, [field]: value }));
  };
  const {
    handleMomentumSleeveChange,
    handleAddMomentumSleeve,
    handleRemoveMomentumSleeve,
  } = useMomentumSleeves(setConfig);

  const hydrateConfigFromAttachedRun = useCallback(
    (runRow) => {
      if (!runRow || typeof runRow !== "object") return;

      const runId = String(runRow.run_id || "").trim();
      const ticker = String(runRow.ticker || "").trim().toUpperCase();
      const normalizedDates = resolveAttachedRunDates(runRow);
      const date = normalizedDates.date;
      const dateFrom = normalizedDates.date_from;
      const dateTo = normalizedDates.date_to;
      const executionConfig =
        runRow.execution_config && typeof runRow.execution_config === "object"
          ? runRow.execution_config
          : effectiveExecutionConfig && typeof effectiveExecutionConfig === "object"
            ? effectiveExecutionConfig
            : {};
      const includeExtendedHours =
        typeof executionConfig.include_extended_hours === "boolean"
          ? executionConfig.include_extended_hours
          : typeof runRow.include_extended_hours === "boolean"
            ? runRow.include_extended_hours
            : null;

      setConfig((prev) => {
        const patch: Record<string, any> = {};
        const prevTicker = String(prev.ticker || "").trim().toUpperCase();

        if (runId && runId !== String(prev.run_id || "")) patch.run_id = runId;
        if (ticker && ticker !== prevTicker) patch.ticker = ticker;
        if (date && date !== String(prev.date || "")) patch.date = date;
        if (dateFrom && dateFrom !== String(prev.date_from || "")) patch.date_from = dateFrom;
        if (dateTo && dateTo !== String(prev.date_to || "")) patch.date_to = dateTo;
        if (
          typeof includeExtendedHours === "boolean" &&
          includeExtendedHours !== Boolean(prev.include_extended_hours)
        ) {
          patch.include_extended_hours = includeExtendedHours;
        }

        if (!Object.keys(patch).length) return prev;
        return {
          ...prev,
          ...patch,
        };
      });

      if (ticker && onTickerChange && ticker !== String(config.ticker || "").trim().toUpperCase()) {
        onTickerChange(ticker);
      }

      const reportMeta =
        runRow.report_metadata && typeof runRow.report_metadata === "object"
          ? runRow.report_metadata
          : {};
      const aosApplied =
        runRow.aos_applied && typeof runRow.aos_applied === "object" ? runRow.aos_applied : {};
      const unifiedMeta =
        aosApplied.unified_profile && typeof aosApplied.unified_profile === "object"
          ? aosApplied.unified_profile
          : {};
      const runProfileId = normalizeProfileRefToken(
        reportMeta.unified_profile_id ||
          runRow.unified_profile_id ||
          executionConfig.unified_profile_id ||
          unifiedMeta.active_profile_id ||
          unifiedMeta.profile_id,
      );
      if (runProfileId) {
        setSelectedUnifiedProfileId(runProfileId);
      }
    },
    [config.ticker, effectiveExecutionConfig, onTickerChange, setSelectedUnifiedProfileId],
  );

  useEffect(() => {
    const targetRunKey = String(activeRunKey || "").trim();
    if (!targetRunKey) {
      lastHydratedAttachedRunKeyRef.current = "";
      return;
    }
    if (lastHydratedAttachedRunKeyRef.current === targetRunKey) {
      return;
    }
    const selected = runningRunOptions.find(
      (row) => String(row?.run_key || "").trim() === targetRunKey
    );
    if (selected) {
      hydrateConfigFromAttachedRun(selected);
      lastHydratedAttachedRunKeyRef.current = targetRunKey;
      return;
    }

    const parsedFromKey = parseRunKeyIdentity(targetRunKey) || {};
    if (activeRunState && typeof activeRunState === "object") {
      hydrateConfigFromAttachedRun({
        ...activeRunState,
        ...parsedFromKey,
      });
      lastHydratedAttachedRunKeyRef.current = targetRunKey;
      return;
    }
    if (parsedFromKey && parsedFromKey.run_id) {
      hydrateConfigFromAttachedRun(parsedFromKey);
      lastHydratedAttachedRunKeyRef.current = targetRunKey;
    }
  }, [
    activeRunKey,
    activeRunState,
    hydrateConfigFromAttachedRun,
    runningRunOptions,
  ]);

  const handleFlushRunCache = async () => {
    setCacheFlushLoading(true);
    setError(null);
    setCacheFlushMessage(null);
    try {
      const resp = await fetch("/api/run/cache/flush?include_disk=true", { method: "POST" });
      const payload = await resp.json().catch(() => ({}));
      if (!resp.ok) {
        throw new Error(payload?.detail || `HTTP ${resp.status}`);
      }
      const beforeMem = Number(payload?.before?.memory?.base_bars_entries || 0);
      const afterMem = Number(payload?.after?.memory?.base_bars_entries || 0);
      setCacheFlushMessage(`Run cache flushed (memory bars ${beforeMem} -> ${afterMem}).`);
      lastPrewarmKeyRef.current = "";
      setPrewarmRevision((prev) => prev + 1);
    } catch (err) {
      setError(`Cache flush failed: ${err.message}`);
    } finally {
      setCacheFlushLoading(false);
    }
  };

  const handleDateFromChange = (value) => {
    setConfig((prev) => {
      const nextTo = prev.date_to && value > prev.date_to ? value : prev.date_to;
      return {
        ...prev,
        date_from: value,
        date: value,
        date_to: nextTo,
      };
    });
  };

  const handleDateToChange = (value) => {
    setConfig((prev) => {
      const nextFrom = prev.date_from && value < prev.date_from ? value : prev.date_from;
      return {
        ...prev,
        date_to: value,
        date: nextFrom || prev.date,
        date_from: nextFrom,
      };
    });
  };

  const handleTickerChange = (ticker) => {
    const upperTicker = String(ticker || "").trim().toUpperCase();
    const coverage = resolveTickerCoverageRange({
      availableData,
      ticker: upperTicker,
      l2Only: !!config.l2_only,
    });
    const range = coverage.effectiveRange;
    const defaultDate = normalizeIsoDay(range?.end);

    setConfig((prev) => {
      const prevTicker = String(prev.ticker || "").trim().toUpperCase();
      const tickerChanged = upperTicker !== prevTicker;
      const dateSeed = tickerChanged
        ? resolveDateRangeWithFallback({
            range,
            from: defaultDate || range?.start,
            to: defaultDate || range?.end,
            fallbackDate: defaultDate || range?.start || prev.date_from || prev.date_to || prev.date,
          })
        : resolveDateRangeWithFallback({
            range,
            from: prev.date_from,
            to: prev.date_to,
            fallbackDate: defaultDate || prev.date_from || prev.date_to || prev.date,
          });
      const nextDraft = {
        ...prev,
        ticker: upperTicker,
        ...dateSeed,
      };
      return applyMuMomentumDefaults(nextDraft, upperTicker, prev.ticker);
    });

    if (onTickerChange) {
      onTickerChange(upperTicker);
    }
  };

  const handleReloadAosAndProfiles = useCallback(async () => {
    await reloadAosAndProfiles();
  }, [reloadAosAndProfiles]);

  const handleApplyMuReproPreset = () => {
    setConfig((prev) => {
      if (String(prev.ticker || "").trim().toUpperCase() !== MU_TICKER) {
        return prev;
      }
      return {
        ...prev,
        date: MU_REPRO_DATE_TO,
        date_from: MU_REPRO_DATE_FROM,
        date_to: MU_REPRO_DATE_TO,
        include_extended_hours: false,
        apply_aos_optimizations_on_start: true,
        fast_start_session_reset: false,
        momentum_diversification_override_enabled: false,
        comparable_mode: true,
        cold_start_each_day: false,
      };
    });
    setSelectedUnifiedProfileId(MU_REPRO_PROFILE_ID);
  };

  const handleApplyMuScalpPreset = () => {
    setConfig((prev) => {
      if (String(prev.ticker || "").trim().toUpperCase() !== MU_TICKER) {
        return prev;
      }
      return {
        ...prev,
        date: MU_SCALP_DATE_TO,
        date_from: MU_SCALP_DATE_FROM,
        date_to: MU_SCALP_DATE_TO,
        include_extended_hours: false,
        l2_only: true,
        l2_confirm_enabled: true,
        l2_min_imbalance: 0.02,
        l2_min_directional_consistency: 0.25,
        l2_min_signed_aggression: 0.02,
        l2_lookback_bars: 3,
        comparable_mode: true,
        cold_start_each_day: true,
        fast_start_session_reset: false,
        apply_aos_optimizations_on_start: false,
        momentum_diversification_override_enabled: false,
      };
    });
    setSelectedUnifiedProfileId(MU_SCALP_PROFILE_ID);
  };

  const momentumSleeves = Array.isArray(config.momentum_sleeves) ? config.momentum_sleeves : [];
  const dateRange = useMemo(
    () => getDateRange(),
    [availableData, config.ticker, config.l2_only],
  );
  const {
    hasEffectiveConfig,
    activeRiskPerTradePct,
    activeMaxPositionNotionalPct,
    activeMaxFillParticipationRate,
    activeMinFillRatio,
    activeTimeExitBars,
    activeAdverseFlowEnabled,
    activeAdverseFlowThreshold,
    activeAdverseFlowMinHoldBars,
    activeStopLossMode,
    activeFixedStopLossPct,
    activeTrailingActivationPct,
    activeTrailingStopPct,
    activeGlobalExitRrRatio,
    activeGlobalRiskAtrStopMultiplier,
    activeGlobalRiskVolumeStopPct,
    activeGlobalRiskMinStopLossPct,
    activeBreakEvenBufferPct,
    activeBreakEvenMinHoldBars,
    activeTrailingInChoppy,
    activeColdStartEachDay,
    activeComparableMode,
    activeAosOptimizationsOnStart,
    activeOrchestratorResetScope,
    activeStrategySelectionMode,
    activeMaxActiveStrategies,
    activeMomentumDiversificationRaw,
    activeMomentumDiversificationApplied,
    activeMomentumDiversificationSource,
    effectiveUnifiedProfileId,
  } = useRunConfigEffectiveSnapshot({
    config,
    effectiveExecutionConfig,
    aosTickerConfig,
    selectedUnifiedProfileId,
    activeUnifiedProfileId,
    activeProfileSentinel: ACTIVE_UNIFIED_PROFILE_SENTINEL,
    normalizeStrategySelectionMode,
    parseMaxActiveStrategies,
  });

  if (isRunning) {
    return (
      <div className="card">
        <div className="card-header">
          <span className="card-title">Run Info</span>
        </div>
        <div className="card-body">
          <div className="form-group">
            <label>Run ID</label>
            <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>{config.run_id}</div>
          </div>
          <div className="form-group">
            <label>Ticker</label>
            <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>{config.ticker}</div>
          </div>
          <div className="form-group">
            <label>Date Range</label>
            <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
              {config.date_from && config.date_to
                ? `${config.date_from} → ${config.date_to}`
                : config.date}
            </div>
          </div>
          <div className="form-group">
            <label className="field-row" htmlFor="run_info_include_extended_hours">
              <span>Include Pre/Post-Market Bars</span>
              <input
                id="run_info_include_extended_hours"
                type="checkbox"
                checked={!!config.include_extended_hours}
                disabled
                readOnly
              />
            </label>
            <div style={{ color: "var(--text-muted)", fontSize: "0.78rem", marginTop: "4px" }}>
              This value is set before run start in Run Config.
            </div>
          </div>
          <div className="form-group">
            <label>Account Size</label>
            <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
              ${Number(config.account_size_usd || 0).toLocaleString()}
            </div>
          </div>
          <div className="form-group">
            <label>Risk / Trade</label>
            <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
              {activeRiskPerTradePct.toFixed(2)}%
            </div>
          </div>
          <div className="form-group">
            <label>Max Position Notional</label>
            <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
              {activeMaxPositionNotionalPct.toFixed(2)}%
            </div>
          </div>
          <div className="form-group">
            <label>Max Fill Participation</label>
            <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
              {activeMaxFillParticipationRate.toFixed(2)}
            </div>
          </div>
          <div className="form-group">
            <label>Min Fill Ratio</label>
            <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
              {activeMinFillRatio.toFixed(2)}
            </div>
          </div>
          <div className="form-group">
            <label>Global Trailing Stop (%)</label>
            <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
              {activeTrailingStopPct.toFixed(2)}%
            </div>
          </div>
          <div className="form-group">
            <label>Global Exit RR</label>
            <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
              {activeGlobalExitRrRatio.toFixed(2)}
            </div>
          </div>
          <div className="form-group">
            <label>Global Risk ATR Multiplier</label>
            <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
              {activeGlobalRiskAtrStopMultiplier.toFixed(2)}
            </div>
          </div>
          <div className="form-group">
            <label>Global Risk Volume Stop (%)</label>
            <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
              {activeGlobalRiskVolumeStopPct.toFixed(2)}%
            </div>
          </div>
          <div className="form-group">
            <label>Global Risk Min Stop (%)</label>
            <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
              {activeGlobalRiskMinStopLossPct.toFixed(2)}%
            </div>
          </div>
          <div className="form-group">
            <label>Stop-Loss Mode</label>
            <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
              {activeStopLossMode}
              {(activeStopLossMode === "fixed" || activeStopLossMode === "capped") && (
                <> ({activeFixedStopLossPct.toFixed(2)}%)</>
              )}
            </div>
          </div>
          <div className="form-group">
            <label>Break-even Activation</label>
            <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
              {activeTrailingActivationPct.toFixed(2)}% MFE, hold {Math.max(1, Math.trunc(activeBreakEvenMinHoldBars || 1))} bars
            </div>
          </div>
          <div className="form-group">
            <label>Break-even Buffer</label>
            <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
              {activeBreakEvenBufferPct.toFixed(2)}%
            </div>
          </div>
          <div className="form-group">
            <label>Trailing In Choppy</label>
            <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
              {activeTrailingInChoppy ? "Enabled" : "Disabled"}
            </div>
          </div>
          <div className="form-group">
            <label>Time Exit</label>
            <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
              {activeTimeExitBars} bars
            </div>
          </div>
          <div className="form-group">
            <label>Adverse Flow Exit</label>
            <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
              {activeAdverseFlowEnabled ? "Enabled" : "Disabled"}
            </div>
          </div>
          {activeAdverseFlowEnabled && (
            <>
              <div className="form-group">
                <label>Adverse Flow Threshold</label>
                <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
                  {activeAdverseFlowThreshold.toFixed(2)}
                </div>
              </div>
              <div className="form-group">
                <label>Adverse Flow Min Hold</label>
                <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
                  {activeAdverseFlowMinHoldBars} bars
                </div>
              </div>
            </>
          )}
          <div className="form-group">
            <label>L2 Confirmation</label>
            <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
              {config.l2_confirm_enabled ? "Enabled" : "Disabled"}
            </div>
          </div>
          <div className="form-group">
            <label>Strategy Selection</label>
            <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
              {activeStrategySelectionMode === "all_enabled" ? "all enabled strategies" : "adaptive top-N"}
              {activeStrategySelectionMode !== "all_enabled" && <> ({activeMaxActiveStrategies})</>}
            </div>
          </div>
          <div className="form-group">
            <label>Unified Profile</label>
            <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
              {effectiveUnifiedProfileId || "none (using direct AOS settings)"}
            </div>
          </div>
          <div className="form-group">
            <label>Momentum Diversification</label>
            <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
              {activeMomentumDiversificationApplied
                ? `Applied (${activeMomentumDiversificationSource})`
                : "Not applied"}
            </div>
          </div>
          {activeMomentumDiversificationApplied && (
            <>
              <div className="form-group">
                <label>Momentum Flow Filter</label>
                <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
                  min_flow_score {Number(activeMomentumDiversificationRaw.min_flow_score ?? 0).toFixed(2)}, directional
                  {" "}
                  {Number(activeMomentumDiversificationRaw.min_directional_consistency ?? 0).toFixed(2)}, signed_aggr
                  {" "}
                  {Number(activeMomentumDiversificationRaw.min_signed_aggression ?? 0).toFixed(2)}
                </div>
              </div>
              <div className="form-group">
                <label>Momentum Route + Fail-Fast</label>
                <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
                  route {activeMomentumDiversificationRaw.route_enabled ? "on" : "off"}, fail-fast
                  {" "}
                  {activeMomentumDiversificationRaw.fail_fast_exit_enabled ? "on" : "off"}
                  {activeMomentumDiversificationRaw.fail_fast_exit_enabled && (
                    <> ({Math.max(1, Math.trunc(Number(activeMomentumDiversificationRaw.fail_fast_max_bars ?? 1)))} bars)</>
                  )}
                </div>
              </div>
            </>
          )}
          <div className="form-group">
            <label>Start Mode</label>
            <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
              {activeComparableMode
                ? "Comparable (day-isolated cold)"
                : (useWarmStart ? "Warm Start" : "Cold Start")}
            </div>
          </div>
          <div className="form-group">
            <label>Reset Scope</label>
            <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
              {activeOrchestratorResetScope === "session"
                ? "Session-only (fast)"
                : (activeOrchestratorResetScope === "learning" ? "Learning-only" : "All (cold)")}
            </div>
          </div>
          <div className="form-group">
            <label>AOS Sync On Start</label>
            <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
              {activeAosOptimizationsOnStart ? "Enabled" : "Disabled (fast)"}
            </div>
          </div>
          <div className="form-group">
            <label>Checkpoint Auto-save</label>
            <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
              {config.auto_save_checkpoint ? "Enabled" : "Disabled"}
            </div>
          </div>
          <div className="form-group">
            <label>Cold Start Each Day</label>
            <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
              {(activeColdStartEachDay || activeComparableMode) ? "Enabled" : "Disabled"}
            </div>
          </div>
          <div className="form-group">
            <label>Comparable Mode</label>
            <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
              {activeComparableMode ? "Enabled" : "Disabled"}
            </div>
          </div>
          <div style={{ color: "var(--text-muted)", fontSize: "0.78rem", marginTop: "4px" }}>
            {hasEffectiveConfig
              ? "Values shown are effective execution settings returned by backend."
              : "Values shown are requested settings (backend effective settings unavailable)."}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="card">
      <div className="card-header">
        <span className="card-title">New Backtest Run</span>
      </div>
      <div className="card-body">
        <form
          className="run-config-form"
          onSubmit={showDateRangeControls ? handleSubmit : (e) => e.preventDefault()}
        >
          {showDateRangeControls && (
          <div className="form-group">
            <label htmlFor="run_id">Run ID</label>
            <input
              id="run_id"
              type="text"
              value={config.run_id}
              onChange={(e) => handleChange("run_id", e.target.value)}
              required
            />
          </div>
          )}
          {showDateRangeControls && (
          <div className="form-group">
            <label htmlFor="active_run_select">
              Running Processes
              <span style={{ color: "var(--text-muted)", fontWeight: "normal", fontSize: "0.75rem" }}>
                {` (${runningRunOptions.length})`}
              </span>
            </label>
            <select
              id="active_run_select"
              value={String(activeRunKey || "")}
              onChange={(e) => {
                const targetRunKey = String(e.target.value || "");
                if (!targetRunKey) return;
                const selected = runningRunOptions.find(
                  (row) => String(row.run_key || "") === targetRunKey
                );
                if (selected) {
                  hydrateConfigFromAttachedRun(selected);
                  lastHydratedAttachedRunKeyRef.current = targetRunKey;
                }
                if (typeof onAttachRun === "function") {
                  onAttachRun(targetRunKey);
                }
              }}
            >
              <option value="">Select running run...</option>
              {runningRunOptions.map((row) => {
                const runKey = String(row.run_key || "");
                const runId = String(row.run_id || "");
                const ticker = String(row.ticker || "").toUpperCase();
                const date = String(row.date || "");
                const phase = String(row.phase || "UNKNOWN");
                const bars = Number(row.current_bar_index || 0);
                const total = Number(row.total_bars || 0);
                const progress = Number(row.progress_pct || 0);
                const statusLabel = row.is_running ? "RUNNING" : (row.is_paused ? "PAUSED" : phase);
                return (
                  <option key={runKey} value={runKey}>
                    {`${runId} | ${ticker} | ${date} | ${statusLabel} | ${bars}/${total} (${progress.toFixed(1)}%)`}
                  </option>
                );
              })}
            </select>
            <div style={{ color: "var(--text-muted)", fontSize: "0.78rem", marginTop: "4px" }}>
              Pick a running/paused run to attach the UI to it.
            </div>
          </div>
          )}
          {showDateRangeControls && (
          <div className="form-group">
            <label htmlFor="ticker">
              Ticker
              <div className="inline-toggle">
                <span>L2 Only</span>
                <input
                  type="checkbox"
                  checked={config.l2_only || false}
                  onChange={(e) => {
                    const checked = e.target.checked;
                    if (checked && availableData?.l2_tickers) {
                      const isCurrentTickerL2 = availableData.l2_tickers.includes(config.ticker);
                      if (!isCurrentTickerL2 && availableData.l2_tickers.length > 0) {
                        handleTickerChange(availableData.l2_tickers[0]);
                      }
                    }
                    handleChange("l2_only", checked);
                  }}
                />
              </div>
            </label>
            {availableData?.tickers ? (
              <select
                id="ticker"
                value={config.ticker}
                onChange={(e) => handleTickerChange(e.target.value)}
                required
              >
                {(() => {
                  const filteredTickers = availableData.tickers.filter(
                    (t) => !config.l2_only || availableData.l2_tickers?.includes(t),
                  );
                  const currentTicker = String(config.ticker || "").trim().toUpperCase();
                  const tickerOptions =
                    currentTicker && !filteredTickers.includes(currentTicker)
                      ? [currentTicker, ...filteredTickers]
                      : filteredTickers;
                  return tickerOptions.map((t, idx) => (
                    <option key={`${t}-${idx}`} value={t}>
                      {t}
                    </option>
                  ));
                })()}
              </select>
            ) : (
              <input
                id="ticker"
                type="text"
                value={config.ticker}
                onChange={(e) => handleTickerChange(e.target.value.toUpperCase())}
                placeholder="Loading..."
                required
              />
            )}
            {availableDataError ? (
              <div className="tw-message-error">{availableDataError}</div>
            ) : null}
          </div>
          )}

          {showDateRangeControls && (
          <>
          <div className="form-group">
            <label htmlFor="date_from">
              Date From
              {dateRange.min && dateRange.max && (
                <span style={{ color: "var(--text-muted)", fontWeight: "normal", fontSize: "0.75rem" }}>
                  {` (${dateRange.min} to ${dateRange.max})`}
                </span>
              )}
            </label>
            <input
              id="date_from"
              type="date"
              value={config.date_from}
              min={dateRange.min || undefined}
              max={dateRange.max || undefined}
              onChange={(e) => handleDateFromChange(e.target.value)}
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="date_to">Date To</label>
            <input
              id="date_to"
              type="date"
              value={config.date_to}
              min={dateRange.min || undefined}
              max={dateRange.max || undefined}
              onChange={(e) => handleDateToChange(e.target.value)}
              required
            />
            {config.l2_only && dateRange.l2_min && dateRange.l2_max && (
              <div style={{ color: "var(--text-muted)", fontSize: "0.75rem", marginTop: "4px" }}>
                {`L2 coverage: ${dateRange.l2_min} to ${dateRange.l2_max}`}
              </div>
            )}
          </div>

          <div className="form-group">
            <label className="field-row" htmlFor="include_extended_hours">
              <span>Include Pre/Post-Market Bars</span>
              <input
                id="include_extended_hours"
                type="checkbox"
                checked={!!config.include_extended_hours}
                onChange={(e) => handleChange("include_extended_hours", e.target.checked)}
              />
            </label>
            <div style={{ color: "var(--text-muted)", fontSize: "0.78rem", marginTop: "4px" }}>
              Off = regular session only (ET 09:30-16:00), faster runs. On = include pre/post market.
            </div>
          </div>

          <div className="form-group">
            <label htmlFor="regime_minutes">Regime Detection (min)</label>
            <input
              id="regime_minutes"
              type="number"
              min="5"
              value={config.regime_detection_minutes}
              onChange={(e) => handleChange("regime_detection_minutes", Number(e.target.value))}
            />
          </div>

          <div className="form-group">
            <label htmlFor="account_size_usd">Account Size (USD)</label>
            <input
              id="account_size_usd"
              type="number"
              min="100"
              step="100"
              value={config.account_size_usd}
              onChange={(e) => handleChange("account_size_usd", Number(e.target.value))}
            />
          </div>

          {SHOW_RUN_CONFIG_ADVANCED_EXECUTION_CONTROLS && (
          <div className="tw-panel">
            <div className="tw-panel-title">Execution Sizing</div>
            <div className="tw-panel-hint">
              Tieto nastavenia riadia veľkosť pozície, fill realizmus a maximálnu dĺžku držania.
            </div>
            <div className="form-group">
              <label htmlFor="risk_per_trade_pct">Risk Per Trade (%)</label>
              <input
                id="risk_per_trade_pct"
                type="number"
                min="0.1"
                max="10"
                step="0.1"
                value={config.risk_per_trade_pct}
                onChange={(e) => handleChange("risk_per_trade_pct", Number(e.target.value))}
              />
            </div>

            <div className="form-group">
              <label htmlFor="max_position_notional_pct">Max Position Notional (%)</label>
              <input
                id="max_position_notional_pct"
                type="number"
                min="1"
                max="100"
                step="1"
                value={config.max_position_notional_pct}
                onChange={(e) => handleChange("max_position_notional_pct", Number(e.target.value))}
              />
            </div>

            <div className="form-group">
              <label htmlFor="max_fill_participation_rate">Max Fill Participation (0-1)</label>
              <input
                id="max_fill_participation_rate"
                type="number"
                min="0.01"
                max="1"
                step="0.01"
                value={config.max_fill_participation_rate}
                onChange={(e) => handleChange("max_fill_participation_rate", Number(e.target.value))}
              />
            </div>

            <div className="form-group">
              <label htmlFor="min_fill_ratio">Min Fill Ratio (0-1)</label>
              <input
                id="min_fill_ratio"
                type="number"
                min="0.01"
                max="1"
                step="0.01"
                value={config.min_fill_ratio}
                onChange={(e) => handleChange("min_fill_ratio", Number(e.target.value))}
              />
            </div>

            <div className="form-group">
              <label htmlFor="time_exit_bars">Time Exit (bars)</label>
              <input
                id="time_exit_bars"
                type="number"
                min="1"
                step="1"
                value={config.time_exit_bars}
                onChange={(e) => handleChange("time_exit_bars", Number(e.target.value))}
              />
            </div>
          </div>
          )}

          {SHOW_RUN_CONFIG_ADVANCED_EXECUTION_CONTROLS && (
          <div className="tw-panel">
            <div className="tw-panel-title">Stop-Loss And Break-Even</div>
            <div className="tw-panel-hint">
              `strategy` = stop zo stratégie, `fixed` = vždy fixné %, `capped` = prísnejší zo strategy/fixed.
            </div>
            <div className="form-group">
              <label htmlFor="stop_loss_mode">Stop-Loss Mode</label>
              <select
                id="stop_loss_mode"
                value={config.stop_loss_mode}
                onChange={(e) => handleChange("stop_loss_mode", e.target.value)}
              >
                <option value="strategy">strategy (use strategy stop)</option>
                <option value="fixed">fixed (always fixed % stop)</option>
                <option value="capped">capped (cap only wide stops)</option>
              </select>
            </div>

            <div className="form-group">
              <label htmlFor="fixed_stop_loss_pct">Fixed Stop-Loss (%)</label>
              <input
                id="fixed_stop_loss_pct"
                type="number"
                min="0"
                max="5"
                step="0.05"
                value={config.fixed_stop_loss_pct}
                onChange={(e) => handleChange("fixed_stop_loss_pct", Number(e.target.value))}
                disabled={config.stop_loss_mode === "strategy"}
              />
            </div>
            <div className="form-group">
              <label htmlFor="trailing_stop_pct">Global Trailing Stop (%)</label>
              <input
                id="trailing_stop_pct"
                type="number"
                min="0"
                max="5"
                step="0.01"
                value={config.trailing_stop_pct}
                onChange={(e) => handleChange("trailing_stop_pct", Number(e.target.value))}
              />
            </div>
            <div className="form-group">
              <label htmlFor="global_exit_rr_ratio">Global Exit RR Ratio</label>
              <input
                id="global_exit_rr_ratio"
                type="number"
                min="0"
                max="10"
                step="0.05"
                value={config.global_exit_rr_ratio}
                onChange={(e) => handleChange("global_exit_rr_ratio", Number(e.target.value))}
              />
            </div>
            <div className="form-group">
              <label htmlFor="global_risk_atr_stop_multiplier">Global Risk ATR Stop Multiplier</label>
              <input
                id="global_risk_atr_stop_multiplier"
                type="number"
                min="0"
                max="10"
                step="0.05"
                value={config.global_risk_atr_stop_multiplier}
                onChange={(e) =>
                  handleChange("global_risk_atr_stop_multiplier", Number(e.target.value))
                }
              />
            </div>
            <div className="form-group">
              <label htmlFor="global_risk_volume_stop_pct">Global Risk Volume Stop (%)</label>
              <input
                id="global_risk_volume_stop_pct"
                type="number"
                min="0"
                max="10"
                step="0.05"
                value={config.global_risk_volume_stop_pct}
                onChange={(e) => handleChange("global_risk_volume_stop_pct", Number(e.target.value))}
              />
            </div>
            <div className="form-group">
              <label htmlFor="global_risk_min_stop_loss_pct">Global Risk Min Stop-Loss (%)</label>
              <input
                id="global_risk_min_stop_loss_pct"
                type="number"
                min="0"
                max="5"
                step="0.01"
                value={config.global_risk_min_stop_loss_pct}
                onChange={(e) =>
                  handleChange("global_risk_min_stop_loss_pct", Number(e.target.value))
                }
              />
            </div>

            <div className="form-group">
              <label htmlFor="trailing_activation_pct">Break-even Activation (% MFE)</label>
              <input
                id="trailing_activation_pct"
                type="number"
                min="0"
                max="5"
                step="0.01"
                value={config.trailing_activation_pct}
                onChange={(e) => handleChange("trailing_activation_pct", Number(e.target.value))}
              />
            </div>

            <div className="form-group">
              <label htmlFor="break_even_buffer_pct">Break-even Buffer (%)</label>
              <input
                id="break_even_buffer_pct"
                type="number"
                min="0"
                max="2"
                step="0.01"
                value={config.break_even_buffer_pct}
                onChange={(e) => handleChange("break_even_buffer_pct", Number(e.target.value))}
              />
            </div>

            <div className="form-group">
              <label htmlFor="break_even_min_hold_bars">Break-even Min Hold (bars)</label>
              <input
                id="break_even_min_hold_bars"
                type="number"
                min="1"
                step="1"
                value={config.break_even_min_hold_bars}
                onChange={(e) => handleChange("break_even_min_hold_bars", Number(e.target.value))}
              />
            </div>

            <div className="form-group">
              <label className="field-row" htmlFor="trailing_enabled_in_choppy">
                <span>Enable Trailing In CHOPPY</span>
                <input
                  id="trailing_enabled_in_choppy"
                  type="checkbox"
                  checked={!!config.trailing_enabled_in_choppy}
                  onChange={(e) => handleChange("trailing_enabled_in_choppy", e.target.checked)}
                />
              </label>
            </div>
          </div>
          )}

          {SHOW_RUN_CONFIG_ADVANCED_EXECUTION_CONTROLS && (
          <div className="tw-panel">
            <div className="tw-panel-title">Adverse Flow Exit</div>
            <div className="tw-panel-hint">
              Ochranný exit pri zhoršení order-flow podmienok po vstupe.
            </div>
            <div className="form-group">
              <label className="field-row" htmlFor="adverse_flow_exit_enabled">
                <span>Adverse Flow Exit Enabled</span>
                <input
                  id="adverse_flow_exit_enabled"
                  type="checkbox"
                  checked={!!config.adverse_flow_exit_enabled}
                  onChange={(e) => handleChange("adverse_flow_exit_enabled", e.target.checked)}
                />
              </label>
            </div>

            <div className="form-group">
              <label htmlFor="adverse_flow_threshold">Adverse Flow Threshold</label>
              <input
                id="adverse_flow_threshold"
                type="number"
                min="0.02"
                max="1"
                step="0.01"
                value={config.adverse_flow_threshold}
                onChange={(e) => handleChange("adverse_flow_threshold", Number(e.target.value))}
              />
            </div>

          <div className="form-group">
            <label htmlFor="adverse_flow_min_hold_bars">Adverse Flow Min Hold (bars)</label>
            <input
              id="adverse_flow_min_hold_bars"
                type="number"
                min="1"
                step="1"
                value={config.adverse_flow_min_hold_bars}
                onChange={(e) => handleChange("adverse_flow_min_hold_bars", Number(e.target.value))}
              />
            </div>
          </div>
          )}
          </>
          )}

          {showProfileControls && (
          <div id="unified_profile_section" className="form-group">
            <label htmlFor="aos_unified_profile">Available Profiles</label>
            <select
              id="aos_unified_profile"
              value={selectedUnifiedProfileId}
              onChange={(e) => setSelectedUnifiedProfileId(e.target.value)}
              disabled={unifiedProfilesLoading || !config.ticker}
            >
              <option value={ACTIVE_UNIFIED_PROFILE_SENTINEL}>
                {unifiedProfilesLoading
                  ? "Loading available profiles..."
                  : `Use active unified profile${activeUnifiedProfileId ? ` (${activeUnifiedProfileId})` : " (none)"}`}
              </option>
              {unifiedProfiles
                .filter((profile) => String(profile?.profile_id || "").trim())
                .map((profile, idx) => {
                  const profileId = String(profile?.profile_id || "").trim();
                  return (
                    <option key={profileId || `unified-${idx}`} value={profileId}>
                      {formatUnifiedProfileLabel(profile)}
                    </option>
                  );
                })}
            </select>
          </div>
          )}

          {showDateRangeControls && (
          <>
          {SHOW_RUN_CONFIG_ADVANCED_EXECUTION_CONTROLS ? (
            <MomentumDiversificationEditor
              config={config}
              momentumSleeves={momentumSleeves}
              onChange={handleChange}
              onMomentumSleeveChange={handleMomentumSleeveChange}
              onAddMomentumSleeve={handleAddMomentumSleeve}
              onRemoveMomentumSleeve={handleRemoveMomentumSleeve}
            />
          ) : (
            <div className="preset-copy">
              Exit/risk moduly a ich detaily sa nastavujú v `Global Modules` a cez unified profile.
            </div>
          )}

          <div className="preset-box">
            <div className="preset-header">
              <span className="preset-title">Warm Start Checkpoints</span>
              <button
                type="button"
                className="btn btn-secondary tw-btn-compact"
                onClick={() => fetchCheckpoints()}
                disabled={checkpointLoading}
              >
                {checkpointLoading ? "Refreshing..." : "Refresh"}
              </button>
            </div>
            <div className="preset-copy">
              Choose how each run should initialize learning state.
            </div>

            <label className="field-row">
              <span>Comparable Mode (day-isolated parity)</span>
              <input
                type="checkbox"
                checked={!!config.comparable_mode}
                onChange={(e) => {
                  const enabled = e.target.checked;
                  handleChange("comparable_mode", enabled);
                  if (enabled) {
                    setUseWarmStart(false);
                    handleChange("cold_start_each_day", true);
                    handleChange("auto_save_checkpoint", false);
                    handleChange("checkpoint_path", null);
                  }
                }}
              />
            </label>
            <div className="preset-copy">
              Isolates each market day (including L2 feature build) so range runs match day-by-day audit behavior.
            </div>

            <label className="field-row">
              <span>Fast Session Reset (skip full cold reset)</span>
              <input
                type="checkbox"
                checked={!!config.fast_start_session_reset && !config.comparable_mode}
                disabled={!!config.comparable_mode}
                onChange={(e) => handleChange("fast_start_session_reset", e.target.checked)}
              />
            </label>
            <div className="preset-copy">
              Uses orchestrator reset scope `session` for faster run start while preserving broader learning state.
            </div>

            <label className="field-row">
              <span>Apply AOS/Adaptive Sync On Start (slower)</span>
              <input
                type="checkbox"
                checked={!!config.apply_aos_optimizations_on_start}
                onChange={(e) => handleChange("apply_aos_optimizations_on_start", e.target.checked)}
              />
            </label>
            <div className="preset-copy">
              Keeps startup deterministic by pushing AOS/adaptive strategy params to strategy API at run start.
            </div>

            <div className="form-group tw-mb-sm">
              <label className="tw-mb-sm">Start Mode</label>
              <div className="tw-grid-gap-sm">
                <label className="field-row">
                  <span>Cold Start (reset learning state)</span>
                  <input
                    type="radio"
                    name="start_mode"
                    checked={!useWarmStart}
                    onChange={() => {
                      setUseWarmStart(false);
                    }}
                  />
                </label>
                <label className="field-row">
                  <span>Warm Start (load checkpoint)</span>
                  <input
                    type="radio"
                    name="start_mode"
                    checked={useWarmStart}
                    disabled={!!config.comparable_mode}
                    onChange={() => {
                      setUseWarmStart(true);
                      handleChange("comparable_mode", false);
                      handleChange("cold_start_each_day", false);
                      if (!config.checkpoint_path && checkpointCatalog.length > 0) {
                        handleChange("checkpoint_path", checkpointCatalog[0].path || null);
                      }
                    }}
                  />
                </label>
              </div>
            </div>

            <label className="field-row">
              <span>Cold Start Each Day (range runs)</span>
              <input
                type="checkbox"
                checked={!!config.cold_start_each_day || !!config.comparable_mode}
                disabled={useWarmStart || !!config.comparable_mode}
                onChange={(e) => handleChange("cold_start_each_day", e.target.checked)}
              />
            </label>
            <div className="preset-copy">
              Re-initializes learning state at each new trading day. Use this to match day-by-day audit behavior.
            </div>

            <label className="field-row">
              <span>Auto-save Checkpoint After Run</span>
              <input
                type="checkbox"
                checked={!!config.auto_save_checkpoint && !config.comparable_mode}
                disabled={!!config.comparable_mode}
                onChange={(e) => handleChange("auto_save_checkpoint", e.target.checked)}
              />
            </label>

            {useWarmStart && !config.comparable_mode && (
              <div className="form-group">
                <label htmlFor="checkpoint_path">Checkpoint</label>
                <select
                  id="checkpoint_path"
                  value={config.checkpoint_path || ""}
                  onChange={(e) => handleChange("checkpoint_path", e.target.value || null)}
                >
                  <option value="">Select checkpoint...</option>
                  {checkpointCatalog.map((cp) => (
                    <option key={cp.path} value={cp.path}>
                      {formatCheckpointLabel(cp)}
                    </option>
                  ))}
                </select>
              </div>
            )}

            {useWarmStart && !config.comparable_mode && (
              <div className="form-group">
                <label htmlFor="checkpoint_path_custom">Custom Checkpoint Path</label>
                <input
                  id="checkpoint_path_custom"
                  type="text"
                  value={config.checkpoint_path || ""}
                  onChange={(e) => handleChange("checkpoint_path", e.target.value || null)}
                  placeholder="data/checkpoints/checkpoint_YYYYMMDD_HHMMSS.json"
                />
              </div>
            )}

            <button
              type="button"
              className="btn btn-secondary tw-full-btn"
              onClick={handleSaveCheckpointNow}
              disabled={checkpointSaving || !!config.comparable_mode}
            >
              {checkpointSaving ? "Saving checkpoint..." : "Save Checkpoint Now"}
            </button>

            {checkpointMessage && (
              <div className="text-[0.8rem] leading-[1.4] text-app-text-secondary">
                {checkpointMessage}
              </div>
            )}
          </div>

          {SHOW_RUN_CONFIG_ADVANCED_EXECUTION_CONTROLS && (
          <div className="tw-panel">
            <div className="tw-panel-title">L2 Confirmation Gate</div>
            <div className="tw-panel-hint">
              Applies an order-flow quality check before entry. Keep filters light to avoid overfitting.
            </div>
            <div className="form-group">
              <label className="field-row" htmlFor="l2_confirm_enabled">
                <span>Enable L2 Confirmation Gate</span>
                <input
                  id="l2_confirm_enabled"
                  type="checkbox"
                  checked={config.l2_confirm_enabled || false}
                  onChange={(e) => handleChange("l2_confirm_enabled", e.target.checked)}
                />
              </label>
            </div>

            {config.l2_confirm_enabled && (
              <div className="tw-grid-fit-190">
                {l2GateFieldConfig.map((field) => {
                  const isLookback = field.key === "l2_lookback_bars";
                  return (
                    <div key={field.key} className="form-group">
                      <label htmlFor={field.key}>{field.label}</label>
                      <input
                        id={field.key}
                        type="number"
                        min={field.min}
                        step={field.step}
                        value={config[field.key]}
                        onChange={(e) =>
                          handleChange(
                            field.key,
                            isLookback ? Math.max(1, Math.trunc(Number(e.target.value))) : Number(e.target.value)
                          )
                        }
                      />
                      <div className="tw-inline-note">
                        {field.hint}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
          )}

          {error && (
            <div className="rounded-app-sm bg-red-500/10 p-2 text-[0.85rem] text-app-accent-red">{error}</div>
          )}

          <button
            type="submit"
            className="btn btn-primary tw-full-btn mt-2"
            disabled={
              loading ||
              aosLoading ||
              unifiedProfilesLoading ||
              !config.ticker ||
              !config.date_from ||
              !config.date_to
            }
          >
            {loading ? `Starting... ${loadingElapsedSec.toFixed(1)}s` : "Start Backtest"}
          </button>

          <button
            type="button"
            className="btn btn-secondary tw-full-btn mt-2"
            onClick={handleFlushRunCache}
            disabled={loading || cacheFlushLoading}
          >
            {cacheFlushLoading ? "Flushing Cache..." : "Flush Run Cache"}
          </button>

          {cacheFlushMessage && (
            <div className="tw-message-success">
              {cacheFlushMessage}
            </div>
          )}

          {prewarmStatus.message && (
            <div
              className={
                prewarmStatus.state === "error"
                  ? "tw-message-error"
                  : prewarmStatus.state === "ready"
                    ? "tw-message-success"
                    : "tw-message-muted"
              }
            >
              {prewarmStatus.message}
            </div>
          )}

          {startTiming && (
            <div className="tw-timing-wrap">
              <div className="tw-timing-head">
                Start timing: total {formatStartTimingMs(startTiming?.total_ms)}
                {startTiming?.slowest_phase && (
                  <>
                    {" "} | slowest {formatStartTimingPhaseLabel(startTiming.slowest_phase)}{" "}
                    {formatStartTimingMs(startTiming?.slowest_phase_ms)}
                  </>
                )}
              </div>
              {startTiming?.context && (
                <div className="mb-1">
                  {String(startTiming.context.ticker || "")}{" "}
                  {String(startTiming.context.range_start || "")} → {String(startTiming.context.range_end || "")}{" "}
                  | bars {Number(startTiming.context.bars_loaded || 0)} | ref{" "}
                  {Number(startTiming.context.reference_bars_loaded || 0)} | aos-sync{" "}
                  {startTiming.context.apply_aos_optimizations_on_start ? "on" : "off"}
                </div>
              )}
              {Object.entries(startTiming?.phases_ms || {}).map(([phaseKey, ms]) => (
                <div key={phaseKey}>
                  {formatStartTimingPhaseLabel(phaseKey)}: {formatStartTimingMs(ms)}
                </div>
              ))}
            </div>
          )}
          </>
          )}
        </form>
      </div>
    </div>
  );
}

export default RunConfig;
