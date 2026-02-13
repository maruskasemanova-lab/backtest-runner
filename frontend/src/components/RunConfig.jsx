import { useState, useEffect, useCallback, useRef } from "react";

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

const ACTIVE_PROFILE_SENTINEL = "__ACTIVE__";
const AVAILABLE_DATA_CACHE_KEY = "backtest_runner_available_data_v1";
const MU_TICKER = "MU";
const MAX_RANGE_L2_PREWARM_DAYS = 10;
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
  "exhaustion_fade",
].join(",");

const applyMuMomentumDefaults = (draft, ticker, previousTicker) => {
  const upperTicker = String(ticker || "").trim().toUpperCase();
  const priorTicker = String(previousTicker || "").trim().toUpperCase();
  if (upperTicker !== MU_TICKER || priorTicker === MU_TICKER) {
    return draft;
  }
  return {
    ...draft,
    momentum_diversification_override_enabled: true,
    momentum_apply_to_strategies: MU_DEFAULT_MOMENTUM_APPLY_TO_STRATEGIES,
  };
};

const inclusiveDaySpan = (startIso, endIso) => {
  const start = String(startIso || "").trim();
  const end = String(endIso || "").trim();
  if (!start || !end) return NaN;
  const startDate = new Date(`${start}T00:00:00Z`);
  const endDate = new Date(`${end}T00:00:00Z`);
  const startMs = Number(startDate.getTime());
  const endMs = Number(endDate.getTime());
  if (!Number.isFinite(startMs) || !Number.isFinite(endMs) || endMs < startMs) return NaN;
  return Math.floor((endMs - startMs) / 86400000) + 1;
};

const formatProfileTimestamp = (value) => {
  if (!value) return "-";
  const parsed = Date.parse(value);
  if (Number.isNaN(parsed)) return String(value);
  return new Date(parsed).toLocaleString();
};

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

const formatAdaptiveProfileLabel = (profile) => {
  const profileId = String(profile?.profile_id || "profile");
  const score = Number(profile?.score || 0).toFixed(4);
  const stamp = formatProfileTimestamp(profile?.created_at);
  return `${profileId} | score ${score} | ${stamp}`;
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

const normalizeAosTickerConfig = (payload) => {
  return payload && typeof payload === "object" && !Array.isArray(payload) ? payload : {};
};

const normalizePositioningConfig = (payload) => {
  const positioning = payload?.positioning;
  return positioning && typeof positioning === "object" && !Array.isArray(positioning)
    ? positioning
    : {};
};

const toFiniteNumber = (value, fallback) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
};

const toBool = (value, fallback) => {
  if (typeof value === "boolean") return value;
  if (typeof value === "number") return value !== 0;
  if (typeof value === "string") {
    const normalized = value.trim().toLowerCase();
    if (["1", "true", "yes", "y", "on"].includes(normalized)) return true;
    if (["0", "false", "no", "n", "off"].includes(normalized)) return false;
  }
  return fallback;
};

const normalizeStopLossMode = (value, fallback = "strategy") => {
  const normalized = String(value || "").trim().toLowerCase();
  if (normalized === "fixed" || normalized === "capped") return normalized;
  return fallback;
};

const parseCsvTokens = (value, normalizeToken) => {
  const tokens = String(value || "").split(",");
  const seen = new Set();
  const normalized = [];
  tokens.forEach((token) => {
    const raw = String(token || "").trim();
    if (!raw) return;
    const next = typeof normalizeToken === "function" ? normalizeToken(raw) : raw;
    if (!next || seen.has(next)) return;
    seen.add(next);
    normalized.push(next);
  });
  return normalized;
};

const normalizeSleeveId = (value, fallback = "sleeve_1") => {
  const raw = String(value || "").trim().toLowerCase();
  const cleaned = raw
    .replace(/[^a-z0-9_]+/g, "_")
    .replace(/_+/g, "_")
    .replace(/^_+|_+$/g, "");
  return cleaned || fallback;
};

const createDefaultMomentumSleeveDraft = (index = 1) => ({
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

const buildMomentumSleevePayload = (sleeve, index) => {
  const clamp = (value, fallback, min, max) =>
    Math.max(min, Math.min(max, toFiniteNumber(value, fallback)));
  const clampInt = (value, fallback, min, max) =>
    Math.max(min, Math.min(max, Math.trunc(toFiniteNumber(value, fallback))));

  const payload = {
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
      100
    ),
    min_price_trend_efficiency: clamp(sleeve?.min_price_trend_efficiency, 0, 0, 1),
    min_last_bar_body_ratio: clamp(sleeve?.min_last_bar_body_ratio, 0, 0, 1),
    min_last_bar_close_location: clamp(sleeve?.min_last_bar_close_location, 0, 0, 1),
    min_delta_acceleration: clamp(sleeve?.min_delta_acceleration, 0, -1_000_000_000, 1_000_000_000),
    min_delta_price_divergence: clamp(sleeve?.min_delta_price_divergence, 0, -10, 10),
    route_flow_score_impulse: clamp(sleeve?.route_flow_score_impulse, 0, 0, 100),
    fail_fast_exit_enabled: !!sleeve?.fail_fast_exit_enabled,
    fail_fast_max_bars: clampInt(sleeve?.fail_fast_max_bars, 3, 1, 30),
    fail_fast_signed_aggression_max: clamp(
      sleeve?.fail_fast_signed_aggression_max,
      -0.05,
      -1,
      0
    ),
    fail_fast_book_pressure_max: clamp(sleeve?.fail_fast_book_pressure_max, -0.08, -1, 0),
    fail_fast_directional_consistency_max: clamp(
      sleeve?.fail_fast_directional_consistency_max,
      0.25,
      0,
      1
    ),
  };

  const applyToStrategies = parseCsvTokens(sleeve?.apply_to_strategies, (token) =>
    token.toLowerCase()
  );
  if (applyToStrategies.length) {
    payload.apply_to_strategies = applyToStrategies;
  }

  const allowedMicro = parseCsvTokens(sleeve?.allowed_micro_regimes, (token) =>
    token.toUpperCase()
  );
  if (allowedMicro.length) {
    payload.allowed_micro_regimes = allowedMicro;
  }

  const blockedMicro = parseCsvTokens(sleeve?.blocked_micro_regimes, (token) =>
    token.toUpperCase()
  );
  if (blockedMicro.length) {
    payload.blocked_micro_regimes = blockedMicro;
  }

  return payload;
};

const buildMomentumDiversificationOverridePayload = (config) => {
  const clamp = (value, fallback, min, max) =>
    Math.max(min, Math.min(max, toFiniteNumber(value, fallback)));
  const clampInt = (value, fallback, min, max) =>
    Math.max(min, Math.min(max, Math.trunc(toFiniteNumber(value, fallback))));

  const payload = {
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
      100
    ),
    min_price_trend_efficiency: clamp(config.momentum_min_price_trend_efficiency, 0, 0, 1),
    min_last_bar_body_ratio: clamp(config.momentum_min_last_bar_body_ratio, 0, 0, 1),
    min_last_bar_close_location: clamp(config.momentum_min_last_bar_close_location, 0, 0, 1),
    min_delta_acceleration: clamp(config.momentum_min_delta_acceleration, 0, -1_000_000_000, 1_000_000_000),
    min_delta_price_divergence: clamp(config.momentum_min_delta_price_divergence, 0, -10, 10),
    route_flow_score_impulse: clamp(config.momentum_route_flow_score_impulse, 0, 0, 100),
    fail_fast_exit_enabled: !!config.momentum_fail_fast_exit_enabled,
    fail_fast_max_bars: clampInt(config.momentum_fail_fast_max_bars, 3, 1, 30),
    fail_fast_signed_aggression_max: clamp(
      config.momentum_fail_fast_signed_aggression_max,
      -0.05,
      -1,
      0
    ),
    fail_fast_book_pressure_max: clamp(config.momentum_fail_fast_book_pressure_max, -0.08, -1, 0),
    fail_fast_directional_consistency_max: clamp(
      config.momentum_fail_fast_directional_consistency_max,
      0.25,
      0,
      1
    ),
  };

  const applyToStrategies = parseCsvTokens(config.momentum_apply_to_strategies, (token) =>
    token.toLowerCase()
  );
  if (applyToStrategies.length) {
    payload.apply_to_strategies = applyToStrategies;
  }

  const allowedMicro = parseCsvTokens(config.momentum_allowed_micro_regimes, (token) =>
    token.toUpperCase()
  );
  if (allowedMicro.length) {
    payload.allowed_micro_regimes = allowedMicro;
  }

  const blockedMicro = parseCsvTokens(config.momentum_blocked_micro_regimes, (token) =>
    token.toUpperCase()
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

const executionSectionStyle = {
  border: "1px solid var(--border-color)",
  borderRadius: "8px",
  padding: "12px",
  marginBottom: "12px",
  background: "var(--bg-secondary)",
};

const executionSectionTitleStyle = {
  fontSize: "0.86rem",
  fontWeight: 700,
  color: "var(--text-primary)",
  marginBottom: "4px",
};

const executionSectionHintStyle = {
  color: "var(--text-muted)",
  fontSize: "0.78rem",
  marginBottom: "10px",
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

function RunConfig({ onStart, isRunning, onTickerChange, effectiveExecutionConfig }) {
  const [availableData, setAvailableData] = useState(null);
  const [config, setConfig] = useState({
    run_id: `backtest-${Date.now()}`,
    ticker: "",
    date: "",
    date_from: "",
    date_to: "",
    data_file: null,
    strategy_api_url: `http://${window.location.hostname}:8001`,
    risk_per_trade_pct: 1.0,
    max_position_notional_pct: 100.0,
    max_fill_participation_rate: 0.2,
    min_fill_ratio: 0.35,
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
    l2_confirm_enabled: true,
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
  });

  const [loading, setLoading] = useState(false);
  const [cacheFlushLoading, setCacheFlushLoading] = useState(false);
  const [cacheFlushMessage, setCacheFlushMessage] = useState(null);
  const [prewarmStatus, setPrewarmStatus] = useState({ state: "idle", message: "" });
  const [prewarmRevision, setPrewarmRevision] = useState(0);
  const [startTiming, setStartTiming] = useState(null);
  const [loadingElapsedSec, setLoadingElapsedSec] = useState(0);
  const [error, setError] = useState(null);
  const [useWarmStart, setUseWarmStart] = useState(false);
  const [checkpointCatalog, setCheckpointCatalog] = useState([]);
  const [checkpointLoading, setCheckpointLoading] = useState(false);
  const [checkpointSaving, setCheckpointSaving] = useState(false);
  const [checkpointMessage, setCheckpointMessage] = useState(null);
  const [aosLoading, setAosLoading] = useState(false);
  const [aosError, setAosError] = useState(null);
  const [aosTickerConfig, setAosTickerConfig] = useState({});
  const [adaptiveProfilesLoading, setAdaptiveProfilesLoading] = useState(false);
  const [adaptiveProfilesError, setAdaptiveProfilesError] = useState(null);
  const [adaptiveProfiles, setAdaptiveProfiles] = useState([]);
  const [activeAdaptiveProfileId, setActiveAdaptiveProfileId] = useState("");
  const [selectedAdaptiveProfileId, setSelectedAdaptiveProfileId] = useState(
    ACTIVE_PROFILE_SENTINEL
  );
  const lastSyncedAdaptiveProfileRef = useRef("");
  const lastPrewarmKeyRef = useRef("");
  const prewarmTimerRef = useRef(null);
  const prewarmAbortRef = useRef(null);

  const strategyApiBase = (config.strategy_api_url || "").replace(/\/+$/, "");

  const buildPrewarmPayload = useCallback(() => {
    const ticker = String(config.ticker || "").trim().toUpperCase();
    if (!ticker) return null;
    const hasRange = Boolean(config.date_from && config.date_to);
    const wantsL2Prewarm = Boolean(config.l2_only || config.l2_confirm_enabled);
    const rangeSpanDays = hasRange ? inclusiveDaySpan(config.date_from, config.date_to) : NaN;
    const canRangeL2Prewarm = (
      hasRange
      && wantsL2Prewarm
      && Number.isFinite(rangeSpanDays)
      && rangeSpanDays <= MAX_RANGE_L2_PREWARM_DAYS
    );
    const prewarmScope = canRangeL2Prewarm ? "range" : "ticker";
    const enableL2Prewarm = canRangeL2Prewarm && wantsL2Prewarm;
    const payload = {
      ticker,
      prewarm_scope: prewarmScope,
      data_file: config.data_file || null,
      allow_mock_data: false,
      l2_only: enableL2Prewarm ? !!config.l2_only : false,
      l2_confirm_enabled: enableL2Prewarm ? !!config.l2_confirm_enabled : false,
      comparable_mode: !!config.comparable_mode,
    };
    if (canRangeL2Prewarm) {
      payload.date_from = config.date_from;
      payload.date_to = config.date_to;
    }
    return payload;
  }, [
    config.ticker,
    config.date_from,
    config.date_to,
    config.data_file,
    config.l2_only,
    config.l2_confirm_enabled,
    config.comparable_mode,
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
    if (!strategyApiBase) {
      return;
    }

    setCheckpointLoading(true);
    setCheckpointMessage(null);
    try {
      const resp = await fetch(`${strategyApiBase}/api/orchestrator/checkpoints`);
      if (!resp.ok) {
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
      console.error("Checkpoint catalog load failed:", err);
      setCheckpointMessage("Checkpoint API is not reachable right now.");
    } finally {
      setCheckpointLoading(false);
    }
  };

  const fetchTickerAosConfig = async (ticker, options = {}) => {
    const { hydrateExecution = false } = options;
    if (!ticker) return;
    setAosLoading(true);
    setAosError(null);

    try {
      const resp = await fetch(`/api/aos-config/${ticker}`);
      if (!resp.ok) {
        throw new Error(`HTTP ${resp.status}`);
      }
      const payload = await resp.json();
      const normalized = normalizeAosTickerConfig(payload);
      setAosTickerConfig(normalized);
      if (hydrateExecution) {
        hydrateExecutionConfigFromPositioning(normalized);
      }
      return normalized;
    } catch (err) {
      console.error("Failed to fetch AOS config:", err);
      setAosError("Failed to load AOS settings for selected ticker/profile.");
      setAosTickerConfig({});
      return null;
    } finally {
      setAosLoading(false);
    }
  };

  const fetchAdaptiveProfiles = async (ticker) => {
    const upperTicker = String(ticker || "").trim().toUpperCase();
    if (!upperTicker) return null;
    setAdaptiveProfilesLoading(true);
    setAdaptiveProfilesError(null);
    try {
      const resp = await fetch(`/api/adaptive-tuner/options/${upperTicker}`);
      if (!resp.ok) {
        throw new Error(`HTTP ${resp.status}`);
      }
      const payload = await resp.json();
      const profiles = Array.isArray(payload?.profiles) ? payload.profiles : [];
      const activeProfileId = String(payload?.active_profile_id || "").trim();
      const knownIds = new Set(
        profiles
          .map((profile) => String(profile?.profile_id || "").trim())
          .filter(Boolean)
      );

      setAdaptiveProfiles(profiles);
      setActiveAdaptiveProfileId(activeProfileId);
      setSelectedAdaptiveProfileId((prev) => {
        const prevId = String(prev || "").trim();
        if (prevId && prevId !== ACTIVE_PROFILE_SENTINEL && knownIds.has(prevId)) {
          return prevId;
        }
        return ACTIVE_PROFILE_SENTINEL;
      });
      return payload;
    } catch (err) {
      console.error("Failed to fetch adaptive profiles:", err);
      setAdaptiveProfilesError("Failed to load adaptive tuned profiles.");
      setAdaptiveProfiles([]);
      setActiveAdaptiveProfileId("");
      setSelectedAdaptiveProfileId(ACTIVE_PROFILE_SENTINEL);
      return null;
    } finally {
      setAdaptiveProfilesLoading(false);
    }
  };

  const normalizeStrategyKey = (value) =>
    String(value || "")
      .trim()
      .toLowerCase()
      .replace(/-/g, "_")
      .replace(/\s+/g, "_");

  const syncAdaptiveCandidateToStrategyApi = useCallback(
    async (candidate) => {
      if (!strategyApiBase) return;
      if (!candidate || typeof candidate !== "object") return;
      const enabledRaw = Array.isArray(candidate.enabled_strategies)
        ? candidate.enabled_strategies
        : [];
      const enabledSet = new Set(
        enabledRaw.map((name) => normalizeStrategyKey(name)).filter(Boolean)
      );
      if (!enabledSet.size) return;

      const strategyResp = await fetch(`${strategyApiBase}/api/strategies`);
      if (!strategyResp.ok) {
        throw new Error(`Failed to fetch strategies: HTTP ${strategyResp.status}`);
      }
      const strategyMap = await strategyResp.json();
      const strategyNames = Object.keys(strategyMap || {});
      if (!strategyNames.length) return;

      await Promise.all(
        strategyNames.map((strategyName) =>
          fetch(`${strategyApiBase}/api/strategies/update`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              strategy_name: strategyName,
              params: { enabled: enabledSet.has(normalizeStrategyKey(strategyName)) },
            }),
          }).catch(() => null)
        )
      );

      const v2Params = {};
      ["min_confidence", "atr_stop_multiplier", "rr_ratio", "trailing_stop_pct"].forEach((key) => {
        const raw = candidate[key];
        const parsed = Number(raw);
        if (Number.isFinite(parsed)) {
          v2Params[key] = parsed;
        }
      });

      if (Object.keys(v2Params).length > 0) {
        await Promise.all(
          strategyNames
            .filter((name) => enabledSet.has(normalizeStrategyKey(name)))
            .map((strategyName) =>
              fetch(`${strategyApiBase}/api/strategies/update`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                  strategy_name: strategyName,
                  params: v2Params,
                }),
              }).catch(() => null)
            )
        );
      }
    },
    [strategyApiBase]
  );

  const applyAdaptiveProfile = async (ticker, profileId) => {
    const upperTicker = String(ticker || "").trim().toUpperCase();
    const targetProfileId = String(profileId || "").trim();
    if (!upperTicker || !targetProfileId) return null;
    const resp = await fetch("/api/adaptive-tuner/profiles/apply", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ticker: upperTicker, profile_id: targetProfileId }),
    });
    if (!resp.ok) {
      const data = await resp.json().catch(() => ({}));
      throw new Error(data?.detail || `HTTP ${resp.status}`);
    }
    return await resp.json();
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
        return;
      }

      const targetTicker = data.tickers[0];
      const range = data.date_ranges?.[targetTicker];
      const defaultDate = range?.end || new Date().toISOString().split("T")[0];

      setConfig((prev) => ({
        ...applyMuMomentumDefaults(
          {
            ...prev,
            ticker: targetTicker,
            date: defaultDate,
            date_from: defaultDate,
            date_to: defaultDate,
          },
          targetTicker,
          prev.ticker
        ),
      }));

      if (onTickerChange) {
        onTickerChange(targetTicker);
      }
    };

    const readCachedAvailableData = () => {
      if (typeof window === "undefined") return null;
      try {
        const raw = window.localStorage.getItem(AVAILABLE_DATA_CACHE_KEY);
        if (!raw) return null;
        const parsed = JSON.parse(raw);
        if (!parsed || typeof parsed !== "object" || !Array.isArray(parsed.tickers)) {
          return null;
        }
        return parsed;
      } catch {
        return null;
      }
    };

    const writeCachedAvailableData = (data) => {
      if (typeof window === "undefined") return;
      try {
        window.localStorage.setItem(AVAILABLE_DATA_CACHE_KEY, JSON.stringify(data));
      } catch {
        // Ignore quota/storage errors and continue with fresh fetch-only behavior.
      }
    };

    const cachedData = readCachedAvailableData();
    if (cachedData) {
      applyAvailableData(cachedData);
    }

    const fetchAvailableData = async () => {
      try {
        const resp = await fetch("/api/available-data");
        if (!resp.ok) {
          return;
        }

        const data = await resp.json();
        applyAvailableData(data);
        writeCachedAvailableData(data);
      } catch (err) {
        console.error("Failed to fetch available data:", err);
      }
    };

    fetchAvailableData();
  }, [onTickerChange]);

  useEffect(() => {
    fetchCheckpoints();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [strategyApiBase]);

  useEffect(() => {
    if (!config.ticker) {
      setAosTickerConfig({});
      setAosError(null);
      setAdaptiveProfiles([]);
      setActiveAdaptiveProfileId("");
      setSelectedAdaptiveProfileId(ACTIVE_PROFILE_SENTINEL);
      setAdaptiveProfilesError(null);
      return;
    }

    fetchTickerAosConfig(config.ticker, { hydrateExecution: true });
    fetchAdaptiveProfiles(config.ticker);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [config.ticker]);

  useEffect(() => {
    const upperTicker = String(config.ticker || "").trim().toUpperCase();
    if (!upperTicker) return;

    const requestedProfileId =
      selectedAdaptiveProfileId === ACTIVE_PROFILE_SENTINEL
        ? String(activeAdaptiveProfileId || "").trim()
        : String(selectedAdaptiveProfileId || "").trim();
    if (!requestedProfileId) return;

    const profile = adaptiveProfiles.find(
      (item) => String(item?.profile_id || "").trim() === requestedProfileId
    );
    const candidate =
      profile && typeof profile.candidate === "object" && !Array.isArray(profile.candidate)
        ? profile.candidate
        : null;
    if (!candidate) return;

    const syncKey = `${upperTicker}:${requestedProfileId}`;
    if (lastSyncedAdaptiveProfileRef.current === syncKey) {
      return;
    }
    lastSyncedAdaptiveProfileRef.current = syncKey;

    syncAdaptiveCandidateToStrategyApi(candidate)
      .then(() => {
        window.dispatchEvent(
          new CustomEvent("adaptive-profile-updated", {
            detail: {
              ticker: upperTicker,
              profile_id: requestedProfileId,
            },
          })
        );
      })
      .catch((err) => {
        console.warn("Failed to sync adaptive profile to strategy API:", err);
      });
  }, [
    activeAdaptiveProfileId,
    adaptiveProfiles,
    config.ticker,
    selectedAdaptiveProfileId,
    syncAdaptiveCandidateToStrategyApi,
  ]);

  useEffect(() => {
    const payload = buildPrewarmPayload();
    if (!payload) {
      setPrewarmStatus({ state: "idle", message: "" });
      return;
    }

    const prewarmKey = JSON.stringify(payload);
    if (prewarmKey === lastPrewarmKeyRef.current) {
      return;
    }

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
      let done = false;
      const warmingIndicator = setTimeout(() => {
        if (!done) {
          setPrewarmStatus({ state: "warming", message: "Prewarming cache..." });
        }
      }, 120);
      try {
        const resp = await fetch("/api/run/prewarm", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
          signal: controller.signal,
        });
        const data = await resp.json().catch(() => ({}));
        if (!resp.ok) {
          throw new Error(data?.detail || `HTTP ${resp.status}`);
        }
        lastPrewarmKeyRef.current = prewarmKey;
        const barsCount = Number(data?.bars || 0);
        const useL2 = !!data?.use_l2;
        const cacheHit = !!data?.cache_hit;
        const prewarmScope = String(data?.prewarm_scope || "range").toLowerCase();
        const l2GuardReason = String(data?.l2_guard_reason || "").trim();
        const coveredMinutes = Number(data?.l2?.covered_minutes || 0);
        const readyPrefix = cacheHit ? "Prewarm ready (cached)" : "Prewarm ready";
        const scopeSuffix = prewarmScope === "ticker" ? " [ticker]" : "";
        const guardSuffix = l2GuardReason ? " | L2 guard active" : "";
        setPrewarmStatus({
          state: "ready",
          message: useL2
            ? `${readyPrefix}${scopeSuffix}: ${barsCount} bars, L2 ${coveredMinutes}m${guardSuffix}`
            : `${readyPrefix}${scopeSuffix}: ${barsCount} bars${guardSuffix}`,
        });
      } catch (err) {
        if (controller.signal.aborted) return;
        setPrewarmStatus({
          state: "error",
          message: `Prewarm failed: ${err.message}`,
        });
      } finally {
        done = true;
        clearTimeout(warmingIndicator);
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
    };
  }, [buildPrewarmPayload, prewarmRevision]);

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
    };
  }, []);

  useEffect(() => {
    if (!loading) {
      setLoadingElapsedSec(0);
      return undefined;
    }
    const startedAtMs = Date.now();
    setLoadingElapsedSec(0);
    const timer = setInterval(() => {
      setLoadingElapsedSec((Date.now() - startedAtMs) / 1000);
    }, 100);
    return () => clearInterval(timer);
  }, [loading]);

  const getDateRange = () => {
    if (!availableData || !config.ticker) {
      return { min: null, max: null };
    }
    const range = availableData.date_ranges[config.ticker];
    return {
      min: range?.start || null,
      max: range?.end || null,
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

      let profileChanged = false;
      if (config.ticker) {
        const selectedProfileId =
          selectedAdaptiveProfileId === ACTIVE_PROFILE_SENTINEL
            ? ""
            : String(selectedAdaptiveProfileId || "").trim();
        const activeProfileId = String(activeAdaptiveProfileId || "").trim();
        if (selectedProfileId && selectedProfileId !== activeProfileId) {
          try {
            await applyAdaptiveProfile(config.ticker, selectedProfileId);
            setActiveAdaptiveProfileId(selectedProfileId);
            profileChanged = true;
          } catch (profileErr) {
            throw new Error(`Failed to apply adaptive profile: ${profileErr.message}`);
          }
        }
      }

      const payload = {
        run_id: String(config.run_id || "").trim(),
        ticker: String(config.ticker || "").trim().toUpperCase(),
        date_from: config.date_from,
        date_to: config.date_to,
        strategy_api_url: config.strategy_api_url,
        regime_detection_minutes: Number(config.regime_detection_minutes),
        account_size_usd: Number(config.account_size_usd),
        risk_per_trade_pct: Number(config.risk_per_trade_pct),
        max_position_notional_pct: Number(config.max_position_notional_pct),
        max_fill_participation_rate: Number(config.max_fill_participation_rate),
        min_fill_ratio: Number(config.min_fill_ratio),
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
      if (!comparableMode && useWarmStart && !payload.checkpoint_path) {
        // No checkpoint available - proceed with cold start (no blocking)
        console.info("Warm start enabled but no checkpoint selected, proceeding with cold start.");
      }
      const startResult = await onStart(payload);
      const timingPayload = startResult?.start_timing;
      if (timingPayload && typeof timingPayload === "object") {
        setStartTiming(timingPayload);
      }
      if (profileChanged && config.ticker) {
        Promise.allSettled([
          fetchTickerAosConfig(config.ticker, { hydrateExecution: true }),
          fetchAdaptiveProfiles(config.ticker),
        ]).catch(() => null);
      }
    } catch (err) {
      setStartTiming(null);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (field, value) => {
    setConfig((prev) => ({ ...prev, [field]: value }));
  };

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

  const handleMomentumSleeveChange = (index, field, value) => {
    setConfig((prev) => {
      const current = Array.isArray(prev.momentum_sleeves) ? prev.momentum_sleeves : [];
      if (index < 0 || index >= current.length) return prev;
      const next = current.map((item, idx) =>
        idx === index ? { ...(item || {}), [field]: value } : item
      );
      return { ...prev, momentum_sleeves: next };
    });
  };

  const handleAddMomentumSleeve = () => {
    setConfig((prev) => {
      const current = Array.isArray(prev.momentum_sleeves) ? prev.momentum_sleeves : [];
      const draft = createDefaultMomentumSleeveDraft(current.length + 1);
      return { ...prev, momentum_sleeves: [...current, draft] };
    });
  };

  const handleRemoveMomentumSleeve = (index) => {
    setConfig((prev) => {
      const current = Array.isArray(prev.momentum_sleeves) ? prev.momentum_sleeves : [];
      if (index < 0 || index >= current.length) return prev;
      return {
        ...prev,
        momentum_sleeves: current.filter((_, idx) => idx !== index),
      };
    });
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
    const range = availableData?.date_ranges[upperTicker];
    const defaultDate = range?.end;

    setConfig((prev) => {
      const nextDraft = {
        ...prev,
        ticker: upperTicker,
        date: defaultDate || prev.date,
        date_from: defaultDate || range?.start || prev.date_from,
        date_to: defaultDate || range?.end || prev.date_to,
      };
      return applyMuMomentumDefaults(nextDraft, upperTicker, prev.ticker);
    });

    if (onTickerChange) {
      onTickerChange(upperTicker);
    }
  };

  const handleReloadAosAndProfiles = async () => {
    if (!config.ticker) return;
    await Promise.all([
      fetchTickerAosConfig(config.ticker, { hydrateExecution: true }),
      fetchAdaptiveProfiles(config.ticker),
    ]);
  };

  const momentumSleeves = Array.isArray(config.momentum_sleeves) ? config.momentum_sleeves : [];
  const dateRange = getDateRange();
  const effectiveConfig = effectiveExecutionConfig || {};
  const hasEffectiveConfig = !!effectiveExecutionConfig;
  const activeRiskPerTradePct = Number(
    effectiveConfig.risk_per_trade_pct ?? config.risk_per_trade_pct ?? 0
  );
  const activeMaxPositionNotionalPct = Number(
    effectiveConfig.max_position_notional_pct ?? config.max_position_notional_pct ?? 0
  );
  const activeMaxFillParticipationRate = Number(
    effectiveConfig.max_fill_participation_rate ?? config.max_fill_participation_rate ?? 0
  );
  const activeMinFillRatio = Number(
    effectiveConfig.min_fill_ratio ?? config.min_fill_ratio ?? 0
  );
  const activeTimeExitBars = Number(
    effectiveConfig.time_exit_bars ?? config.time_exit_bars ?? 0
  );
  const activeAdverseFlowEnabled = Boolean(
    effectiveConfig.adverse_flow_exit_enabled ?? config.adverse_flow_exit_enabled
  );
  const activeAdverseFlowThreshold = Number(
    effectiveConfig.adverse_flow_threshold ?? config.adverse_flow_threshold ?? 0
  );
  const activeAdverseFlowMinHoldBars = Number(
    effectiveConfig.adverse_flow_min_hold_bars ?? config.adverse_flow_min_hold_bars ?? 0
  );
  const activeStopLossMode = String(
    effectiveConfig.stop_loss_mode ?? config.stop_loss_mode ?? "strategy"
  );
  const activeFixedStopLossPct = Number(
    effectiveConfig.fixed_stop_loss_pct ?? config.fixed_stop_loss_pct ?? 0
  );
  const activeTrailingActivationPct = Number(
    effectiveConfig.trailing_activation_pct ?? config.trailing_activation_pct ?? 0
  );
  const activeBreakEvenBufferPct = Number(
    effectiveConfig.break_even_buffer_pct ?? config.break_even_buffer_pct ?? 0
  );
  const activeBreakEvenMinHoldBars = Number(
    effectiveConfig.break_even_min_hold_bars ?? config.break_even_min_hold_bars ?? 0
  );
  const activeTrailingInChoppy = Boolean(
    effectiveConfig.trailing_enabled_in_choppy ?? config.trailing_enabled_in_choppy
  );
  const activeColdStartEachDay = Boolean(
    effectiveConfig.cold_start_each_day ?? config.cold_start_each_day
  );
  const activeComparableMode = Boolean(
    effectiveConfig.comparable_mode ?? config.comparable_mode
  );
  const activeAosOptimizationsOnStart = Boolean(
    effectiveConfig.apply_aos_optimizations_on_start ?? config.apply_aos_optimizations_on_start
  );
  const activeOrchestratorResetScope = String(
    effectiveConfig.orchestrator_reset_scope
      || (activeComparableMode
        ? "all"
        : (config.fast_start_session_reset ? "session" : "all"))
  ).toLowerCase();
  const activeStrategySelectionMode = normalizeStrategySelectionMode(
    effectiveConfig.strategy_selection_mode ?? aosTickerConfig?.strategy_selection_mode ?? "adaptive_top_n"
  );
  const activeMaxActiveStrategies = parseMaxActiveStrategies(
    effectiveConfig.max_active_strategies ?? aosTickerConfig?.max_active_strategies ?? 3,
    3
  );
  const activeMomentumDiversificationRaw =
    effectiveConfig?.momentum_diversification &&
    typeof effectiveConfig.momentum_diversification === "object" &&
    !Array.isArray(effectiveConfig.momentum_diversification)
      ? effectiveConfig.momentum_diversification
      : {};
  const activeMomentumDiversificationApplied = Boolean(
    effectiveConfig?.momentum_diversification_applied
  );
  const activeMomentumDiversificationSource = String(
    effectiveConfig?.momentum_diversification_source || "none"
  );
  const requestedAdaptiveProfileId =
    selectedAdaptiveProfileId === ACTIVE_PROFILE_SENTINEL
      ? ""
      : String(selectedAdaptiveProfileId || "").trim();
  const selectedAdaptiveProfile =
    requestedAdaptiveProfileId
      ? adaptiveProfiles.find(
          (profile) => String(profile?.profile_id || "").trim() === requestedAdaptiveProfileId
        ) || null
      : null;
  const effectiveAdaptiveProfileId = requestedAdaptiveProfileId || String(activeAdaptiveProfileId || "").trim();

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
            <label>Adaptive Tuner Profile</label>
            <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
              {effectiveAdaptiveProfileId || "none (using direct AOS settings)"}
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
        <form className="run-config-form" onSubmit={handleSubmit}>
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
                {availableData.tickers
                  .filter((t) => !config.l2_only || availableData.l2_tickers?.includes(t))
                  .map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
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
          </div>

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

          <div style={executionSectionStyle}>
            <div style={executionSectionTitleStyle}>Execution Sizing</div>
            <div style={executionSectionHintStyle}>
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

          <div style={executionSectionStyle}>
            <div style={executionSectionTitleStyle}>Stop-Loss And Break-Even</div>
            <div style={executionSectionHintStyle}>
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

          <div style={executionSectionStyle}>
            <div style={executionSectionTitleStyle}>Adverse Flow Exit</div>
            <div style={executionSectionHintStyle}>
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

          <div className="preset-box">
            <div className="preset-header">
              <span className="preset-title">Adaptive Profile ({config.ticker || "Ticker"})</span>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={handleReloadAosAndProfiles}
                disabled={aosLoading || adaptiveProfilesLoading || !config.ticker}
                style={{ padding: "6px 10px", fontSize: "0.78rem" }}
              >
                {aosLoading || adaptiveProfilesLoading ? "Loading..." : "Reload"}
              </button>
            </div>
            <div className="preset-copy">
              Runtime adaptive/AOS hodnoty sa berú priamo z API (Adaptive Studio/Tuner). Tu vyberieš len profil,
              ktorý sa má aktivovať pred štartom runu.
            </div>

            <div className="form-group">
              <label htmlFor="aos_adaptive_profile">Adaptive Tuned Profile (for this run)</label>
              <select
                id="aos_adaptive_profile"
                value={selectedAdaptiveProfileId}
                onChange={(e) => setSelectedAdaptiveProfileId(e.target.value)}
                disabled={aosLoading || adaptiveProfilesLoading || !config.ticker}
              >
                <option value={ACTIVE_PROFILE_SENTINEL}>
                  Use active profile from AOS
                  {activeAdaptiveProfileId ? ` (${activeAdaptiveProfileId})` : " (none)"}
                </option>
                {adaptiveProfiles
                  .filter((profile) => String(profile?.profile_id || "").trim())
                  .map((profile, idx) => {
                  const profileId = String(profile?.profile_id || "").trim();
                  return (
                    <option key={profileId || `profile-${idx}`} value={profileId}>
                      {formatAdaptiveProfileLabel(profile)}
                    </option>
                  );
                })}
              </select>
            </div>
            <div className="preset-copy">
              Zvolený profil nastaví active adaptive profil v AOS pred štartom runu.
            </div>
            {selectedAdaptiveProfile && (
              <div className="preset-copy">
                Candidate: {formatAdaptiveProfileCandidate(selectedAdaptiveProfile.candidate)}
              </div>
            )}
            <div className="preset-copy">
              Aktívny AOS režim:{" "}
              {normalizeStrategySelectionMode(aosTickerConfig?.strategy_selection_mode) === "all_enabled"
                ? "all enabled strategies"
                : `adaptive top-${parseMaxActiveStrategies(aosTickerConfig?.max_active_strategies, 3)}`}
            </div>

            {aosError && (
              <div
                style={{
                  color: "var(--accent-red)",
                  fontSize: "0.8rem",
                  background: "rgba(239, 68, 68, 0.1)",
                  padding: "var(--spacing-xs)",
                  borderRadius: "var(--border-radius-sm)",
                }}
              >
                {aosError}
              </div>
            )}
            {adaptiveProfilesError && (
              <div
                style={{
                  color: "var(--accent-red)",
                  fontSize: "0.8rem",
                  background: "rgba(239, 68, 68, 0.1)",
                  padding: "var(--spacing-xs)",
                  borderRadius: "var(--border-radius-sm)",
                }}
              >
                {adaptiveProfilesError}
              </div>
            )}
          </div>

          <div style={executionSectionStyle}>
            <div style={executionSectionTitleStyle}>Momentum Diversification Override</div>
            <div style={executionSectionHintStyle}>
              Voliteľný run-level override pre adaptive momentum routing (L2/CVD + price-action prahy, route a fail-fast).
              Keď je vypnutý, použije sa aktívny Adaptive Profile/AOS config.
            </div>

            <div className="form-group">
              <label className="field-row" htmlFor="momentum_diversification_override_enabled">
                <span>Enable per-run momentum diversification override</span>
                <input
                  id="momentum_diversification_override_enabled"
                  type="checkbox"
                  checked={!!config.momentum_diversification_override_enabled}
                  onChange={(e) =>
                    handleChange("momentum_diversification_override_enabled", e.target.checked)
                  }
                />
              </label>
            </div>

            {config.momentum_diversification_override_enabled ? (
              <>
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
                    gap: "8px",
                    marginBottom: "8px",
                  }}
                >
                  <label className="field-row">
                    <span>Momentum Diversification Enabled</span>
                    <input
                      type="checkbox"
                      checked={!!config.momentum_diversification_enabled}
                      onChange={(e) => handleChange("momentum_diversification_enabled", e.target.checked)}
                    />
                  </label>
                  <label className="field-row">
                    <span>Require L2 Coverage</span>
                    <input
                      type="checkbox"
                      checked={!!config.momentum_require_l2_coverage}
                      onChange={(e) => handleChange("momentum_require_l2_coverage", e.target.checked)}
                    />
                  </label>
                  <label className="field-row">
                    <span>Route Enabled</span>
                    <input
                      type="checkbox"
                      checked={!!config.momentum_route_enabled}
                      onChange={(e) => handleChange("momentum_route_enabled", e.target.checked)}
                    />
                  </label>
                  <label className="field-row">
                    <span>Route Requires L2 Coverage</span>
                    <input
                      type="checkbox"
                      checked={!!config.momentum_route_require_l2_coverage}
                      onChange={(e) =>
                        handleChange("momentum_route_require_l2_coverage", e.target.checked)
                      }
                    />
                  </label>
                  <label className="field-row">
                    <span>Fail-Fast Exit Enabled</span>
                    <input
                      type="checkbox"
                      checked={!!config.momentum_fail_fast_exit_enabled}
                      onChange={(e) => handleChange("momentum_fail_fast_exit_enabled", e.target.checked)}
                    />
                  </label>
                </div>

                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))",
                    gap: "10px",
                  }}
                >
                  <div className="form-group">
                    <label htmlFor="momentum_min_flow_score">Min Flow Score</label>
                    <input
                      id="momentum_min_flow_score"
                      type="number"
                      min="0"
                      max="100"
                      step="0.5"
                      value={config.momentum_min_flow_score}
                      onChange={(e) => handleChange("momentum_min_flow_score", Number(e.target.value))}
                    />
                  </div>
                  <div className="form-group">
                    <label htmlFor="momentum_min_directional_consistency">Min Directional Consistency</label>
                    <input
                      id="momentum_min_directional_consistency"
                      type="number"
                      min="0"
                      max="1"
                      step="0.01"
                      value={config.momentum_min_directional_consistency}
                      onChange={(e) =>
                        handleChange("momentum_min_directional_consistency", Number(e.target.value))
                      }
                    />
                  </div>
                  <div className="form-group">
                    <label htmlFor="momentum_min_signed_aggression">Min Signed Aggression</label>
                    <input
                      id="momentum_min_signed_aggression"
                      type="number"
                      min="0"
                      max="1"
                      step="0.01"
                      value={config.momentum_min_signed_aggression}
                      onChange={(e) =>
                        handleChange("momentum_min_signed_aggression", Number(e.target.value))
                      }
                    />
                  </div>
                  <div className="form-group">
                    <label htmlFor="momentum_min_imbalance">Min Imbalance</label>
                    <input
                      id="momentum_min_imbalance"
                      type="number"
                      min="0"
                      max="1"
                      step="0.01"
                      value={config.momentum_min_imbalance}
                      onChange={(e) => handleChange("momentum_min_imbalance", Number(e.target.value))}
                    />
                  </div>
                  <div className="form-group">
                    <label htmlFor="momentum_min_cvd">Min CVD (Directional)</label>
                    <input
                      id="momentum_min_cvd"
                      type="number"
                      min="-1000000000"
                      max="1000000000"
                      step="1"
                      value={config.momentum_min_cvd}
                      onChange={(e) => handleChange("momentum_min_cvd", Number(e.target.value))}
                    />
                  </div>
                  <div className="form-group">
                    <label htmlFor="momentum_min_directional_price_change_pct">
                      Min Directional Price Change %
                    </label>
                    <input
                      id="momentum_min_directional_price_change_pct"
                      type="number"
                      min="-100"
                      max="100"
                      step="0.01"
                      value={config.momentum_min_directional_price_change_pct}
                      onChange={(e) =>
                        handleChange("momentum_min_directional_price_change_pct", Number(e.target.value))
                      }
                    />
                  </div>
                  <div className="form-group">
                    <label htmlFor="momentum_min_price_trend_efficiency">Min Price Trend Efficiency</label>
                    <input
                      id="momentum_min_price_trend_efficiency"
                      type="number"
                      min="0"
                      max="1"
                      step="0.01"
                      value={config.momentum_min_price_trend_efficiency}
                      onChange={(e) =>
                        handleChange("momentum_min_price_trend_efficiency", Number(e.target.value))
                      }
                    />
                  </div>
                  <div className="form-group">
                    <label htmlFor="momentum_min_last_bar_body_ratio">Min Last Bar Body Ratio</label>
                    <input
                      id="momentum_min_last_bar_body_ratio"
                      type="number"
                      min="0"
                      max="1"
                      step="0.01"
                      value={config.momentum_min_last_bar_body_ratio}
                      onChange={(e) =>
                        handleChange("momentum_min_last_bar_body_ratio", Number(e.target.value))
                      }
                    />
                  </div>
                  <div className="form-group">
                    <label htmlFor="momentum_min_last_bar_close_location">
                      Min Last Bar Close Location
                    </label>
                    <input
                      id="momentum_min_last_bar_close_location"
                      type="number"
                      min="0"
                      max="1"
                      step="0.01"
                      value={config.momentum_min_last_bar_close_location}
                      onChange={(e) =>
                        handleChange("momentum_min_last_bar_close_location", Number(e.target.value))
                      }
                    />
                  </div>
                  <div className="form-group">
                    <label htmlFor="momentum_min_delta_acceleration">Min Delta Acceleration</label>
                    <input
                      id="momentum_min_delta_acceleration"
                      type="number"
                      min="-1000000000"
                      max="1000000000"
                      step="1"
                      value={config.momentum_min_delta_acceleration}
                      onChange={(e) =>
                        handleChange("momentum_min_delta_acceleration", Number(e.target.value))
                      }
                    />
                  </div>
                  <div className="form-group">
                    <label htmlFor="momentum_min_delta_price_divergence">Min Delta-Price Divergence</label>
                    <input
                      id="momentum_min_delta_price_divergence"
                      type="number"
                      min="-10"
                      max="10"
                      step="0.01"
                      value={config.momentum_min_delta_price_divergence}
                      onChange={(e) =>
                        handleChange("momentum_min_delta_price_divergence", Number(e.target.value))
                      }
                    />
                  </div>
                  <div className="form-group">
                    <label htmlFor="momentum_route_flow_score_impulse">Route Flow Score (Impulse)</label>
                    <input
                      id="momentum_route_flow_score_impulse"
                      type="number"
                      min="0"
                      max="100"
                      step="0.5"
                      value={config.momentum_route_flow_score_impulse}
                      onChange={(e) =>
                        handleChange("momentum_route_flow_score_impulse", Number(e.target.value))
                      }
                    />
                  </div>
                  <div className="form-group">
                    <label htmlFor="momentum_fail_fast_max_bars">Fail-Fast Max Bars</label>
                    <input
                      id="momentum_fail_fast_max_bars"
                      type="number"
                      min="1"
                      max="30"
                      step="1"
                      value={config.momentum_fail_fast_max_bars}
                      onChange={(e) =>
                        handleChange("momentum_fail_fast_max_bars", Math.max(1, Math.trunc(Number(e.target.value))))
                      }
                    />
                  </div>
                  <div className="form-group">
                    <label htmlFor="momentum_fail_fast_signed_aggression_max">Fail-Fast Signed Aggression Max</label>
                    <input
                      id="momentum_fail_fast_signed_aggression_max"
                      type="number"
                      min="-1"
                      max="0"
                      step="0.01"
                      value={config.momentum_fail_fast_signed_aggression_max}
                      onChange={(e) =>
                        handleChange("momentum_fail_fast_signed_aggression_max", Number(e.target.value))
                      }
                    />
                  </div>
                  <div className="form-group">
                    <label htmlFor="momentum_fail_fast_book_pressure_max">Fail-Fast Book Pressure Max</label>
                    <input
                      id="momentum_fail_fast_book_pressure_max"
                      type="number"
                      min="-1"
                      max="0"
                      step="0.01"
                      value={config.momentum_fail_fast_book_pressure_max}
                      onChange={(e) =>
                        handleChange("momentum_fail_fast_book_pressure_max", Number(e.target.value))
                      }
                    />
                  </div>
                  <div className="form-group">
                    <label htmlFor="momentum_fail_fast_directional_consistency_max">
                      Fail-Fast Directional Consistency Max
                    </label>
                    <input
                      id="momentum_fail_fast_directional_consistency_max"
                      type="number"
                      min="0"
                      max="1"
                      step="0.01"
                      value={config.momentum_fail_fast_directional_consistency_max}
                      onChange={(e) =>
                        handleChange(
                          "momentum_fail_fast_directional_consistency_max",
                          Number(e.target.value)
                        )
                      }
                    />
                  </div>
                </div>

                <div className="form-group">
                  <label htmlFor="momentum_apply_to_strategies">
                    Apply To Strategies (CSV, optional)
                  </label>
                  <input
                    id="momentum_apply_to_strategies"
                    type="text"
                    value={config.momentum_apply_to_strategies}
                    onChange={(e) => handleChange("momentum_apply_to_strategies", e.target.value)}
                    placeholder="momentum_flow,momentum"
                  />
                </div>

                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
                    gap: "10px",
                  }}
                >
                  <div className="form-group">
                    <label htmlFor="momentum_allowed_micro_regimes">Allowed Micro Regimes (CSV)</label>
                    <input
                      id="momentum_allowed_micro_regimes"
                      type="text"
                      value={config.momentum_allowed_micro_regimes}
                      onChange={(e) => handleChange("momentum_allowed_micro_regimes", e.target.value)}
                      placeholder="TRENDING_UP,BREAKOUT"
                    />
                  </div>
                  <div className="form-group">
                    <label htmlFor="momentum_blocked_micro_regimes">Blocked Micro Regimes (CSV)</label>
                    <input
                      id="momentum_blocked_micro_regimes"
                      type="text"
                      value={config.momentum_blocked_micro_regimes}
                      onChange={(e) => handleChange("momentum_blocked_micro_regimes", e.target.value)}
                      placeholder="CHOPPY,ABSORPTION"
                    />
                  </div>
                </div>

                <div
                  style={{
                    border: "1px solid var(--border-color)",
                    borderRadius: "6px",
                    padding: "10px",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      marginBottom: "8px",
                    }}
                  >
                    <div style={{ fontWeight: 700, fontSize: "0.8rem" }}>
                      Multi-Sleeve Diversification
                    </div>
                    <button
                      type="button"
                      className="btn btn-secondary"
                      style={{ padding: "6px 10px", fontSize: "0.74rem" }}
                      onClick={handleAddMomentumSleeve}
                    >
                      Add Sleeve
                    </button>
                  </div>
                  <div style={{ color: "var(--text-muted)", fontSize: "0.74rem", marginBottom: "8px" }}>
                    Vizualny editor pre `sleeves[]`. Ak pridáš aspoň jeden sleeve, backend použije multi-sleeve režim.
                  </div>

                  {momentumSleeves.length === 0 ? (
                    <div style={{ color: "var(--text-muted)", fontSize: "0.75rem" }}>
                      Zatial nie je definovany ziadny sleeve.
                    </div>
                  ) : (
                    <div style={{ display: "grid", gap: "10px" }}>
                      {momentumSleeves.map((sleeve, index) => (
                        <div
                          key={`${sleeve?.sleeve_id || "sleeve"}-${index}`}
                          style={{
                            border: "1px solid var(--border-color)",
                            borderRadius: "6px",
                            padding: "10px",
                            background: "var(--bg-primary)",
                          }}
                        >
                          <div
                            style={{
                              display: "flex",
                              justifyContent: "space-between",
                              alignItems: "center",
                              marginBottom: "8px",
                            }}
                          >
                            <div style={{ fontWeight: 700, fontSize: "0.78rem" }}>
                              Sleeve #{index + 1}
                            </div>
                            <button
                              type="button"
                              className="btn btn-secondary"
                              style={{ padding: "4px 8px", fontSize: "0.72rem" }}
                              onClick={() => handleRemoveMomentumSleeve(index)}
                            >
                              Remove
                            </button>
                          </div>

                          <div
                            style={{
                              display: "grid",
                              gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
                              gap: "8px",
                            }}
                          >
                            <div className="form-group">
                              <label>Sleeve ID</label>
                              <input
                                type="text"
                                value={sleeve?.sleeve_id || ""}
                                onChange={(e) =>
                                  handleMomentumSleeveChange(index, "sleeve_id", e.target.value)
                                }
                                placeholder="impulse"
                              />
                            </div>
                            <div className="form-group">
                              <label>Allocation Weight (0-1)</label>
                              <input
                                type="number"
                                min="0"
                                max="1"
                                step="0.05"
                                value={sleeve?.allocation_weight ?? 0.5}
                                onChange={(e) =>
                                  handleMomentumSleeveChange(index, "allocation_weight", Number(e.target.value))
                                }
                              />
                            </div>
                            <div className="form-group">
                              <label>Apply To Strategies (CSV)</label>
                              <input
                                type="text"
                                value={sleeve?.apply_to_strategies || ""}
                                onChange={(e) =>
                                  handleMomentumSleeveChange(index, "apply_to_strategies", e.target.value)
                                }
                                placeholder="momentum_flow,pullback"
                              />
                            </div>
                            <div className="form-group">
                              <label>Allowed Micro Regimes (CSV)</label>
                              <input
                                type="text"
                                value={sleeve?.allowed_micro_regimes || ""}
                                onChange={(e) =>
                                  handleMomentumSleeveChange(index, "allowed_micro_regimes", e.target.value)
                                }
                                placeholder="TRENDING_UP,BREAKOUT"
                              />
                            </div>
                            <div className="form-group">
                              <label>Blocked Micro Regimes (CSV)</label>
                              <input
                                type="text"
                                value={sleeve?.blocked_micro_regimes || ""}
                                onChange={(e) =>
                                  handleMomentumSleeveChange(index, "blocked_micro_regimes", e.target.value)
                                }
                                placeholder="CHOPPY,ABSORPTION"
                              />
                            </div>
                          </div>

                          <div
                            style={{
                              display: "grid",
                              gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
                              gap: "8px",
                              marginBottom: "8px",
                            }}
                          >
                            <label className="field-row">
                              <span>Enabled</span>
                              <input
                                type="checkbox"
                                checked={!!sleeve?.enabled}
                                onChange={(e) =>
                                  handleMomentumSleeveChange(index, "enabled", e.target.checked)
                                }
                              />
                            </label>
                            <label className="field-row">
                              <span>Require L2 Coverage</span>
                              <input
                                type="checkbox"
                                checked={!!sleeve?.require_l2_coverage}
                                onChange={(e) =>
                                  handleMomentumSleeveChange(index, "require_l2_coverage", e.target.checked)
                                }
                              />
                            </label>
                            <label className="field-row">
                              <span>Route Enabled</span>
                              <input
                                type="checkbox"
                                checked={!!sleeve?.route_enabled}
                                onChange={(e) =>
                                  handleMomentumSleeveChange(index, "route_enabled", e.target.checked)
                                }
                              />
                            </label>
                            <label className="field-row">
                              <span>Route Requires L2</span>
                              <input
                                type="checkbox"
                                checked={!!sleeve?.route_require_l2_coverage}
                                onChange={(e) =>
                                  handleMomentumSleeveChange(index, "route_require_l2_coverage", e.target.checked)
                                }
                              />
                            </label>
                            <label className="field-row">
                              <span>Fail-Fast Exit Enabled</span>
                              <input
                                type="checkbox"
                                checked={!!sleeve?.fail_fast_exit_enabled}
                                onChange={(e) =>
                                  handleMomentumSleeveChange(index, "fail_fast_exit_enabled", e.target.checked)
                                }
                              />
                            </label>
                          </div>

                          <div
                            style={{
                              display: "grid",
                              gridTemplateColumns: "repeat(auto-fit, minmax(185px, 1fr))",
                              gap: "10px",
                            }}
                          >
                            <div className="form-group">
                              <label>Min Flow Score</label>
                              <input
                                type="number"
                                min="0"
                                max="100"
                                step="0.5"
                                value={sleeve?.min_flow_score ?? 58}
                                onChange={(e) =>
                                  handleMomentumSleeveChange(index, "min_flow_score", Number(e.target.value))
                                }
                              />
                            </div>
                            <div className="form-group">
                              <label>Min Directional Consistency</label>
                              <input
                                type="number"
                                min="0"
                                max="1"
                                step="0.01"
                                value={sleeve?.min_directional_consistency ?? 0.45}
                                onChange={(e) =>
                                  handleMomentumSleeveChange(
                                    index,
                                    "min_directional_consistency",
                                    Number(e.target.value)
                                  )
                                }
                              />
                            </div>
                            <div className="form-group">
                              <label>Min Signed Aggression</label>
                              <input
                                type="number"
                                min="0"
                                max="1"
                                step="0.01"
                                value={sleeve?.min_signed_aggression ?? 0.04}
                                onChange={(e) =>
                                  handleMomentumSleeveChange(
                                    index,
                                    "min_signed_aggression",
                                    Number(e.target.value)
                                  )
                                }
                              />
                            </div>
                            <div className="form-group">
                              <label>Min Imbalance</label>
                              <input
                                type="number"
                                min="0"
                                max="1"
                                step="0.01"
                                value={sleeve?.min_imbalance ?? 0.02}
                                onChange={(e) =>
                                  handleMomentumSleeveChange(index, "min_imbalance", Number(e.target.value))
                                }
                              />
                            </div>
                            <div className="form-group">
                              <label>Min CVD (Directional)</label>
                              <input
                                type="number"
                                min="-1000000000"
                                max="1000000000"
                                step="1"
                                value={sleeve?.min_cvd ?? 0}
                                onChange={(e) =>
                                  handleMomentumSleeveChange(index, "min_cvd", Number(e.target.value))
                                }
                              />
                            </div>
                            <div className="form-group">
                              <label>Min Directional Price Change %</label>
                              <input
                                type="number"
                                min="-100"
                                max="100"
                                step="0.01"
                                value={sleeve?.min_directional_price_change_pct ?? 0}
                                onChange={(e) =>
                                  handleMomentumSleeveChange(
                                    index,
                                    "min_directional_price_change_pct",
                                    Number(e.target.value)
                                  )
                                }
                              />
                            </div>
                            <div className="form-group">
                              <label>Min Price Trend Efficiency</label>
                              <input
                                type="number"
                                min="0"
                                max="1"
                                step="0.01"
                                value={sleeve?.min_price_trend_efficiency ?? 0}
                                onChange={(e) =>
                                  handleMomentumSleeveChange(
                                    index,
                                    "min_price_trend_efficiency",
                                    Number(e.target.value)
                                  )
                                }
                              />
                            </div>
                            <div className="form-group">
                              <label>Min Last Bar Body Ratio</label>
                              <input
                                type="number"
                                min="0"
                                max="1"
                                step="0.01"
                                value={sleeve?.min_last_bar_body_ratio ?? 0}
                                onChange={(e) =>
                                  handleMomentumSleeveChange(
                                    index,
                                    "min_last_bar_body_ratio",
                                    Number(e.target.value)
                                  )
                                }
                              />
                            </div>
                            <div className="form-group">
                              <label>Min Last Bar Close Location</label>
                              <input
                                type="number"
                                min="0"
                                max="1"
                                step="0.01"
                                value={sleeve?.min_last_bar_close_location ?? 0}
                                onChange={(e) =>
                                  handleMomentumSleeveChange(
                                    index,
                                    "min_last_bar_close_location",
                                    Number(e.target.value)
                                  )
                                }
                              />
                            </div>
                            <div className="form-group">
                              <label>Min Delta Acceleration</label>
                              <input
                                type="number"
                                min="-1000000000"
                                max="1000000000"
                                step="1"
                                value={sleeve?.min_delta_acceleration ?? 0}
                                onChange={(e) =>
                                  handleMomentumSleeveChange(
                                    index,
                                    "min_delta_acceleration",
                                    Number(e.target.value)
                                  )
                                }
                              />
                            </div>
                            <div className="form-group">
                              <label>Min Delta-Price Divergence</label>
                              <input
                                type="number"
                                min="-10"
                                max="10"
                                step="0.01"
                                value={sleeve?.min_delta_price_divergence ?? 0}
                                onChange={(e) =>
                                  handleMomentumSleeveChange(
                                    index,
                                    "min_delta_price_divergence",
                                    Number(e.target.value)
                                  )
                                }
                              />
                            </div>
                            <div className="form-group">
                              <label>Route Flow Score (Impulse)</label>
                              <input
                                type="number"
                                min="0"
                                max="100"
                                step="0.5"
                                value={sleeve?.route_flow_score_impulse ?? 64}
                                onChange={(e) =>
                                  handleMomentumSleeveChange(
                                    index,
                                    "route_flow_score_impulse",
                                    Number(e.target.value)
                                  )
                                }
                              />
                            </div>
                            <div className="form-group">
                              <label>Fail-Fast Max Bars</label>
                              <input
                                type="number"
                                min="1"
                                max="30"
                                step="1"
                                value={sleeve?.fail_fast_max_bars ?? 3}
                                onChange={(e) =>
                                  handleMomentumSleeveChange(
                                    index,
                                    "fail_fast_max_bars",
                                    Math.max(1, Math.trunc(Number(e.target.value)))
                                  )
                                }
                              />
                            </div>
                            <div className="form-group">
                              <label>Fail-Fast Signed Aggression Max</label>
                              <input
                                type="number"
                                min="-1"
                                max="0"
                                step="0.01"
                                value={sleeve?.fail_fast_signed_aggression_max ?? -0.08}
                                onChange={(e) =>
                                  handleMomentumSleeveChange(
                                    index,
                                    "fail_fast_signed_aggression_max",
                                    Number(e.target.value)
                                  )
                                }
                              />
                            </div>
                            <div className="form-group">
                              <label>Fail-Fast Book Pressure Max</label>
                              <input
                                type="number"
                                min="-1"
                                max="0"
                                step="0.01"
                                value={sleeve?.fail_fast_book_pressure_max ?? -0.1}
                                onChange={(e) =>
                                  handleMomentumSleeveChange(
                                    index,
                                    "fail_fast_book_pressure_max",
                                    Number(e.target.value)
                                  )
                                }
                              />
                            </div>
                            <div className="form-group">
                              <label>Fail-Fast Directional Consistency Max</label>
                              <input
                                type="number"
                                min="0"
                                max="1"
                                step="0.01"
                                value={sleeve?.fail_fast_directional_consistency_max ?? 0.2}
                                onChange={(e) =>
                                  handleMomentumSleeveChange(
                                    index,
                                    "fail_fast_directional_consistency_max",
                                    Number(e.target.value)
                                  )
                                }
                              />
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </>
            ) : (
              <div style={{ color: "var(--text-muted)", fontSize: "0.78rem" }}>
                Override je vypnutý, použije sa profil z Adaptive Tuner/AOS.
              </div>
            )}
          </div>

          <div className="preset-box">
            <div className="preset-header">
              <span className="preset-title">Warm Start Checkpoints</span>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => fetchCheckpoints()}
                disabled={checkpointLoading}
                style={{ padding: "6px 10px", fontSize: "0.78rem" }}
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

            <div className="form-group" style={{ marginBottom: "var(--spacing-sm)" }}>
              <label style={{ marginBottom: "8px" }}>Start Mode</label>
              <div style={{ display: "grid", gap: "8px" }}>
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
              className="btn btn-secondary"
              onClick={handleSaveCheckpointNow}
              disabled={checkpointSaving || !!config.comparable_mode}
              style={{ width: "100%" }}
            >
              {checkpointSaving ? "Saving checkpoint..." : "Save Checkpoint Now"}
            </button>

            {checkpointMessage && (
              <div
                style={{
                  fontSize: "0.8rem",
                  color: "var(--text-secondary)",
                  lineHeight: 1.4,
                }}
              >
                {checkpointMessage}
              </div>
            )}
          </div>

          <div style={executionSectionStyle}>
            <div style={executionSectionTitleStyle}>L2 Confirmation Gate</div>
            <div style={executionSectionHintStyle}>
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
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))",
                  gap: "10px",
                }}
              >
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
                      <div
                        style={{
                          fontSize: "0.74rem",
                          color: "var(--text-muted)",
                          lineHeight: 1.35,
                        }}
                      >
                        {field.hint}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {error && (
            <div
              style={{
                color: "var(--accent-red)",
                fontSize: "0.85rem",
                padding: "var(--spacing-sm)",
                background: "rgba(239, 68, 68, 0.1)",
                borderRadius: "var(--border-radius-sm)",
              }}
            >
              {error}
            </div>
          )}

          <button
            type="submit"
            className="btn btn-primary"
            disabled={
              loading ||
              aosLoading ||
              adaptiveProfilesLoading ||
              !config.ticker ||
              !config.date_from ||
              !config.date_to
            }
            style={{ width: "100%", marginTop: "var(--spacing-sm)" }}
          >
            {loading ? `Starting... ${loadingElapsedSec.toFixed(1)}s` : "Start Backtest"}
          </button>

          <button
            type="button"
            className="btn btn-secondary"
            onClick={handleFlushRunCache}
            disabled={loading || cacheFlushLoading}
            style={{ width: "100%", marginTop: "8px" }}
          >
            {cacheFlushLoading ? "Flushing Cache..." : "Flush Run Cache"}
          </button>

          {cacheFlushMessage && (
            <div
              style={{
                color: "var(--accent-green)",
                fontSize: "0.8rem",
                marginTop: "6px",
              }}
            >
              {cacheFlushMessage}
            </div>
          )}

          {prewarmStatus.message && (
            <div
              style={{
                color:
                  prewarmStatus.state === "error"
                    ? "var(--accent-red)"
                    : prewarmStatus.state === "ready"
                      ? "var(--accent-green)"
                      : "var(--text-muted)",
                fontSize: "0.78rem",
                marginTop: "6px",
              }}
            >
              {prewarmStatus.message}
            </div>
          )}

          {startTiming && (
            <div
              style={{
                color: "var(--text-muted)",
                fontSize: "0.78rem",
                marginTop: "8px",
                borderTop: "1px solid var(--border-color)",
                paddingTop: "8px",
              }}
            >
              <div style={{ color: "var(--text-primary)", marginBottom: "4px" }}>
                Start timing: total {formatStartTimingMs(startTiming?.total_ms)}
                {startTiming?.slowest_phase && (
                  <>
                    {" "} | slowest {formatStartTimingPhaseLabel(startTiming.slowest_phase)}{" "}
                    {formatStartTimingMs(startTiming?.slowest_phase_ms)}
                  </>
                )}
              </div>
              {startTiming?.context && (
                <div style={{ marginBottom: "4px" }}>
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
        </form>
      </div>
    </div>
  );
}

export default RunConfig;
