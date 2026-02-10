import { useState, useEffect } from "react";

const MU_FLOW_PRESET = {
  // Keep FE defaults aligned with AOS tuning:
  // zeros/nulls below intentionally defer to AOS values in backend.
  regime_detection_minutes: 15,
  trailing_stop_pct: null,
  account_size_usd: 10000,
  risk_per_trade_pct: 1.0,
  max_position_notional_pct: 100.0,
  max_fill_participation_rate: 0.2,
  min_fill_ratio: 0.35,
  time_exit_bars: 40,
  adverse_flow_exit_enabled: true,
  adverse_flow_threshold: 0.12,
  adverse_flow_min_hold_bars: 3,
  stop_loss_mode: "capped",
  fixed_stop_loss_pct: 0.5,
  comparable_mode: true,
  cold_start_each_day: true,
  auto_save_checkpoint: false,
  l2_only: false,
  l2_confirm_enabled: true,
  l2_min_imbalance: 0.0,
  l2_min_directional_consistency: 0.0,
  l2_min_signed_aggression: 0.0,
  l2_lookback_bars: 3,
  strategy_selection_mode: "adaptive_top_n",
  max_active_strategies: 3,
};

const toFiniteNumberOrNull = (value) => {
  if (value === null || value === undefined || value === "") return null;
  const num = Number(value);
  return Number.isFinite(num) ? num : null;
};

const toHoursText = (hours) => {
  if (!Array.isArray(hours) || hours.length === 0) return "";
  return hours.join(",");
};

const parseTradingHoursText = (text) => {
  if (!text || !text.trim()) return [];
  const parts = text
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
  const hours = [];
  for (const part of parts) {
    const value = Number(part);
    if (!Number.isFinite(value) || !Number.isInteger(value) || value < 0 || value > 23) {
      throw new Error("Trading hours must be comma-separated integers in range 0-23.");
    }
    hours.push(value);
  }
  return Array.from(new Set(hours)).sort((a, b) => a - b);
};

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

const normalizeAosTickerConfig = (payload) => {
  const raw = payload && typeof payload === "object" && !Array.isArray(payload) ? payload : {};
  const params =
    raw.params && typeof raw.params === "object" && !Array.isArray(raw.params) ? raw.params : {};

  const tradingHours = Array.isArray(raw.trading_hours)
    ? raw.trading_hours
        .map((h) => Number(h))
        .filter((h) => Number.isFinite(h) && Number.isInteger(h) && h >= 0 && h <= 23)
    : [];

  const longOnly =
    typeof raw.long_only === "boolean"
      ? raw.long_only
      : (typeof params.long_only === "boolean" ? params.long_only : false);

  const trailingStopPct =
    toFiniteNumberOrNull(raw.trailing_stop_pct) ?? toFiniteNumberOrNull(params.trailing_stop_pct);

  const timeFilterEnabled =
    typeof raw.time_filter_enabled === "boolean"
      ? raw.time_filter_enabled
      : tradingHours.length > 0;
  const strategySelectionMode = normalizeStrategySelectionMode(raw.strategy_selection_mode);
  const maxActiveStrategies = parseMaxActiveStrategies(raw.max_active_strategies, 3);

  return {
    raw,
    form: {
      time_filter_enabled: timeFilterEnabled,
      trading_hours_text: toHoursText(tradingHours),
      long_only: longOnly,
      trailing_stop_pct: trailingStopPct === null ? "" : String(trailingStopPct),
      strategy_selection_mode: strategySelectionMode,
      max_active_strategies: String(maxActiveStrategies),
    },
  };
};

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
    time_exit_bars: 40,
    adverse_flow_exit_enabled: true,
    adverse_flow_threshold: 0.12,
    adverse_flow_min_hold_bars: 3,
    stop_loss_mode: "strategy",
    fixed_stop_loss_pct: 0.0,
    ...MU_FLOW_PRESET,
    checkpoint_path: null,
    auto_save_checkpoint: true,
    cold_start_each_day: false,
    comparable_mode: false,
    strategy_selection_mode: "adaptive_top_n",
    max_active_strategies: 3,
  });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [useWarmStart, setUseWarmStart] = useState(false);
  const [checkpointCatalog, setCheckpointCatalog] = useState([]);
  const [checkpointLoading, setCheckpointLoading] = useState(false);
  const [checkpointSaving, setCheckpointSaving] = useState(false);
  const [checkpointMessage, setCheckpointMessage] = useState(null);
  const [aosLoading, setAosLoading] = useState(false);
  const [aosSaving, setAosSaving] = useState(false);
  const [aosError, setAosError] = useState(null);
  const [aosTickerConfig, setAosTickerConfig] = useState({});
  const [aosControls, setAosControls] = useState({
    time_filter_enabled: false,
    trading_hours_text: "",
    long_only: false,
    trailing_stop_pct: "",
    strategy_selection_mode: "adaptive_top_n",
    max_active_strategies: "3",
  });
  const [adaptiveProfilesLoading, setAdaptiveProfilesLoading] = useState(false);
  const [adaptiveProfilesError, setAdaptiveProfilesError] = useState(null);
  const [adaptiveProfiles, setAdaptiveProfiles] = useState([]);
  const [activeAdaptiveProfileId, setActiveAdaptiveProfileId] = useState("");
  const [selectedAdaptiveProfileId, setSelectedAdaptiveProfileId] = useState(
    ACTIVE_PROFILE_SENTINEL
  );

  const strategyApiBase = (config.strategy_api_url || "").replace(/\/+$/, "");

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

  const fetchTickerAosConfig = async (ticker) => {
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
      setAosTickerConfig(normalized.raw);
      setAosControls(normalized.form);
      return normalized.raw;
    } catch (err) {
      console.error("Failed to fetch AOS config:", err);
      setAosError("Failed to load AOS settings for selected ticker.");
      setAosTickerConfig({});
      setAosControls({
        time_filter_enabled: false,
        trading_hours_text: "",
        long_only: false,
        trailing_stop_pct: "",
        strategy_selection_mode: "adaptive_top_n",
        max_active_strategies: "3",
      });
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

  const persistTickerAosConfig = async (ticker) => {
    if (!ticker) return null;

    const hours = aosControls.time_filter_enabled
      ? parseTradingHoursText(aosControls.trading_hours_text)
      : [];
    const trailingStopPct =
      toFiniteNumberOrNull(aosControls.trailing_stop_pct) ??
      toFiniteNumberOrNull(aosTickerConfig?.trailing_stop_pct) ??
      toFiniteNumberOrNull(aosTickerConfig?.params?.trailing_stop_pct);

    if (toFiniteNumberOrNull(aosControls.trailing_stop_pct) === null && aosControls.trailing_stop_pct !== "") {
      throw new Error("AOS trailing stop must be a valid number.");
    }
    const strategySelectionMode = normalizeStrategySelectionMode(aosControls.strategy_selection_mode);
    const maxActiveStrategies = parseMaxActiveStrategies(
      aosControls.max_active_strategies,
      parseMaxActiveStrategies(aosTickerConfig?.max_active_strategies, 3)
    );

    const current = aosTickerConfig && typeof aosTickerConfig === "object" ? aosTickerConfig : {};
    const currentParams =
      current.params && typeof current.params === "object" && !Array.isArray(current.params)
        ? current.params
        : {};

    const nextConfig = {
      ...current,
      time_filter_enabled: !!aosControls.time_filter_enabled,
      trading_hours: hours,
      long_only: !!aosControls.long_only,
      trailing_stop_pct: trailingStopPct,
      strategy_selection_mode: strategySelectionMode,
      max_active_strategies: maxActiveStrategies,
      params: {
        ...currentParams,
        long_only: !!aosControls.long_only,
        trailing_stop_pct: trailingStopPct,
      },
    };

    const resp = await fetch("/api/aos-config/update", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ticker,
        config: nextConfig,
      }),
    });
    if (!resp.ok) {
      throw new Error(`HTTP ${resp.status}`);
    }

    return nextConfig;
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

  const applyMuPreset = (date = "2026-02-03") => {
    setConfig((prev) => ({
      ...prev,
      ticker: "MU",
      date,
      date_from: date,
      date_to: date,
      ...MU_FLOW_PRESET,
    }));
    if (onTickerChange) {
      onTickerChange("MU");
    }
  };

  useEffect(() => {
    const fetchAvailableData = async () => {
      try {
        const resp = await fetch("/api/available-data");
        if (!resp.ok) {
          return;
        }

        const data = await resp.json();
        setAvailableData(data);

        if (!data.tickers || data.tickers.length === 0) {
          return;
        }

        const targetTicker = data.tickers.includes("MU") ? "MU" : data.tickers[0];
        const range = data.date_ranges[targetTicker];
        const defaultDate = targetTicker === "MU"
          ? "2026-02-03"
          : range?.end || new Date().toISOString().split("T")[0];

        setConfig((prev) => ({
          ...prev,
          ticker: targetTicker,
          date: defaultDate,
          date_from: defaultDate,
          date_to: defaultDate,
          ...(targetTicker === "MU" ? MU_FLOW_PRESET : {}),
        }));

        if (onTickerChange) {
          onTickerChange(targetTicker);
        }
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
      setAosControls({
        time_filter_enabled: false,
        trading_hours_text: "",
        long_only: false,
        trailing_stop_pct: "",
        strategy_selection_mode: "adaptive_top_n",
        max_active_strategies: "3",
      });
      setAosError(null);
      setAdaptiveProfiles([]);
      setActiveAdaptiveProfileId("");
      setSelectedAdaptiveProfileId(ACTIVE_PROFILE_SENTINEL);
      setAdaptiveProfilesError(null);
      return;
    }

    fetchTickerAosConfig(config.ticker);
    fetchAdaptiveProfiles(config.ticker);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [config.ticker]);

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
    setError(null);

    try {
      const comparableMode = !!config.comparable_mode;
      const stopLossMode = String(config.stop_loss_mode || "strategy").toLowerCase();
      const fixedStopLossPct = Math.max(0, Number(config.fixed_stop_loss_pct || 0));
      let runtimeAosConfig = null;
      if (stopLossMode !== "strategy" && fixedStopLossPct <= 0) {
        throw new Error("Fixed stop-loss % must be > 0 when stop mode is fixed or capped.");
      }

      if (config.ticker) {
        setAosSaving(true);
        setAosError(null);
        try {
          const savedAos = await persistTickerAosConfig(config.ticker);
          if (savedAos) {
            runtimeAosConfig = savedAos;
            setAosTickerConfig(savedAos);
          }
        } catch (aosErr) {
          throw new Error(`Failed to save AOS settings: ${aosErr.message}`);
        } finally {
          setAosSaving(false);
        }

        const selectedProfileId =
          selectedAdaptiveProfileId === ACTIVE_PROFILE_SENTINEL
            ? ""
            : String(selectedAdaptiveProfileId || "").trim();
        if (selectedProfileId) {
          try {
            await applyAdaptiveProfile(config.ticker, selectedProfileId);
            setActiveAdaptiveProfileId(selectedProfileId);
            const refreshedAos = await fetchTickerAosConfig(config.ticker);
            if (refreshedAos) {
              runtimeAosConfig = refreshedAos;
              setAosTickerConfig(refreshedAos);
            }
            await fetchAdaptiveProfiles(config.ticker);
          } catch (profileErr) {
            throw new Error(`Failed to apply adaptive profile: ${profileErr.message}`);
          }
        }
      }

      const effectiveStrategySelectionMode = normalizeStrategySelectionMode(
        runtimeAosConfig?.strategy_selection_mode || aosControls.strategy_selection_mode
      );
      const effectiveMaxActiveStrategies = parseMaxActiveStrategies(
        runtimeAosConfig?.max_active_strategies ?? aosControls.max_active_strategies,
        3
      );

      const payload = {
        ...config,
        stop_loss_mode: stopLossMode,
        fixed_stop_loss_pct: fixedStopLossPct,
        strategy_selection_mode: effectiveStrategySelectionMode,
        max_active_strategies: effectiveMaxActiveStrategies,
        comparable_mode: comparableMode,
        // Strategy overrides are used as FE defaults; do not re-apply them at run start.
        apply_ticker_overrides_on_start: false,
        cold_start_each_day: comparableMode ? true : !!config.cold_start_each_day,
        checkpoint_path: comparableMode
          ? null
          : (useWarmStart ? (config.checkpoint_path || "").trim() || null : null),
        auto_save_checkpoint: comparableMode ? false : !!config.auto_save_checkpoint,
      };
      if (!comparableMode && useWarmStart && !payload.checkpoint_path) {
        // No checkpoint available - proceed with cold start (no blocking)
        console.info("Warm start enabled but no checkpoint selected, proceeding with cold start.");
      }
      await onStart(payload);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (field, value) => {
    setConfig((prev) => ({ ...prev, [field]: value }));
  };

  const handleAosControlChange = (field, value) => {
    setAosControls((prev) => ({ ...prev, [field]: value }));
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
    const range = availableData?.date_ranges[ticker];
    const defaultDate = ticker === "MU" ? "2026-02-03" : range?.end;

    setConfig((prev) => ({
      ...prev,
      ticker,
      date: defaultDate || prev.date,
      date_from: defaultDate || range?.start || prev.date_from,
      date_to: defaultDate || range?.end || prev.date_to,
      ...(ticker === "MU" ? MU_FLOW_PRESET : {}),
    }));

    if (onTickerChange) {
      onTickerChange(ticker);
    }
  };

  const handleReloadAosAndProfiles = async () => {
    if (!config.ticker) return;
    await Promise.all([
      fetchTickerAosConfig(config.ticker),
      fetchAdaptiveProfiles(config.ticker),
    ]);
  };

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
  const activeColdStartEachDay = Boolean(
    effectiveConfig.cold_start_each_day ?? config.cold_start_each_day
  );
  const activeComparableMode = Boolean(
    effectiveConfig.comparable_mode ?? config.comparable_mode
  );
  const activeStrategySelectionMode = normalizeStrategySelectionMode(
    effectiveConfig.strategy_selection_mode ?? config.strategy_selection_mode
  );
  const activeMaxActiveStrategies = parseMaxActiveStrategies(
    effectiveConfig.max_active_strategies ?? config.max_active_strategies,
    3
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
            <label>Start Mode</label>
            <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
              {activeComparableMode
                ? "Comparable (day-isolated cold)"
                : (useWarmStart ? "Warm Start" : "Cold Start")}
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
          <div className="preset-box">
            <div className="preset-header">
              <span className="preset-title">MU Flow Preset</span>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => applyMuPreset()}
                style={{ padding: "6px 10px", fontSize: "0.78rem" }}
              >
                Apply
              </button>
            </div>
            <div className="preset-copy">
              Strategies: momentum_flow, absorption_reversal, exhaustion_fade. L2 confirm + depth thresholds are prefilled.
            </div>
          </div>

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
                onChange={(e) => handleChange("ticker", e.target.value.toUpperCase())}
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
            <label htmlFor="trailing_stop_pct">Global Trailing Stop (%)</label>
            <input
              id="trailing_stop_pct"
              type="number"
              min="0.1"
              max="5"
              step="0.1"
              value={config.trailing_stop_pct ?? ""}
              onChange={(e) =>
                handleChange(
                  "trailing_stop_pct",
                  e.target.value === "" ? null : Number(e.target.value)
                )
              }
            />
          </div>

          <div className="preset-box">
            <div className="preset-header">
              <span className="preset-title">AOS Runtime Settings ({config.ticker || "Ticker"})</span>
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
              Tieto hodnoty sa načítajú z API a ukladajú pred štartom runu.
            </div>

            <label className="field-row" htmlFor="aos_time_filter_enabled">
              <span>AOS Time Filter</span>
              <input
                id="aos_time_filter_enabled"
                type="checkbox"
                checked={!!aosControls.time_filter_enabled}
                onChange={(e) => handleAosControlChange("time_filter_enabled", e.target.checked)}
                disabled={aosLoading}
              />
            </label>

            <div className="form-group">
              <label htmlFor="aos_trading_hours">AOS Trading Hours (ET, comma-separated)</label>
              <input
                id="aos_trading_hours"
                type="text"
                value={aosControls.trading_hours_text}
                onChange={(e) => handleAosControlChange("trading_hours_text", e.target.value)}
                placeholder="15 or 9,10,15"
                disabled={aosLoading}
              />
            </div>

            <label className="field-row" htmlFor="aos_long_only">
              <span>AOS Long Only</span>
              <input
                id="aos_long_only"
                type="checkbox"
                checked={!!aosControls.long_only}
                onChange={(e) => handleAosControlChange("long_only", e.target.checked)}
                disabled={aosLoading}
              />
            </label>

            <div className="form-group">
              <label htmlFor="aos_trailing_stop_pct">AOS Trailing Stop (%)</label>
              <input
                id="aos_trailing_stop_pct"
                type="number"
                min="0.1"
                max="5"
                step="0.1"
                value={aosControls.trailing_stop_pct}
                onChange={(e) => handleAosControlChange("trailing_stop_pct", e.target.value)}
                disabled={aosLoading}
              />
            </div>

            <div className="form-group">
              <label htmlFor="aos_strategy_selection_mode">Strategy Selection Mode</label>
              <select
                id="aos_strategy_selection_mode"
                value={aosControls.strategy_selection_mode}
                onChange={(e) => handleAosControlChange("strategy_selection_mode", e.target.value)}
                disabled={aosLoading}
              >
                <option value="adaptive_top_n">Adaptive Top-N</option>
                <option value="all_enabled">All Enabled Strategies</option>
              </select>
            </div>

            <div className="form-group">
              <label htmlFor="aos_max_active_strategies">Max Active Strategies (adaptive mode)</label>
              <input
                id="aos_max_active_strategies"
                type="number"
                min="1"
                max="20"
                step="1"
                value={aosControls.max_active_strategies}
                onChange={(e) => handleAosControlChange("max_active_strategies", e.target.value)}
                disabled={aosLoading || aosControls.strategy_selection_mode === "all_enabled"}
              />
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
              Zvolený profil prepíše adaptive selection parametre pre ďalší run a nastaví sa ako aktívny v AOS.
            </div>
            {selectedAdaptiveProfile && (
              <div className="preset-copy">
                Candidate: {formatAdaptiveProfileCandidate(selectedAdaptiveProfile.candidate)}
              </div>
            )}

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

          <div className="form-group">
            <label className="field-row" htmlFor="l2_confirm_enabled">
              <span>L2 Confirmation Gate</span>
              <input
                id="l2_confirm_enabled"
                type="checkbox"
                checked={config.l2_confirm_enabled || false}
                onChange={(e) => handleChange("l2_confirm_enabled", e.target.checked)}
              />
            </label>
          </div>

          {config.l2_confirm_enabled && (
            <>
              <div className="form-group">
                <label htmlFor="l2_min_imbalance">L2 Min Imbalance</label>
                <input
                  id="l2_min_imbalance"
                  type="number"
                  step="0.01"
                  value={config.l2_min_imbalance}
                  onChange={(e) => handleChange("l2_min_imbalance", Number(e.target.value))}
                />
              </div>
              <div className="form-group">
                <label htmlFor="l2_min_signed_aggression">L2 Min Signed Aggression</label>
                <input
                  id="l2_min_signed_aggression"
                  type="number"
                  step="0.01"
                  value={config.l2_min_signed_aggression}
                  onChange={(e) => handleChange("l2_min_signed_aggression", Number(e.target.value))}
                />
              </div>
              <div className="form-group">
                <label htmlFor="l2_min_directional_consistency">L2 Min Directional Consistency</label>
                <input
                  id="l2_min_directional_consistency"
                  type="number"
                  step="0.01"
                  value={config.l2_min_directional_consistency}
                  onChange={(e) =>
                    handleChange("l2_min_directional_consistency", Number(e.target.value))
                  }
                />
              </div>
              <div className="form-group">
                <label htmlFor="l2_lookback_bars">L2 Lookback Bars</label>
                <input
                  id="l2_lookback_bars"
                  type="number"
                  min="1"
                  step="1"
                  value={config.l2_lookback_bars}
                  onChange={(e) => handleChange("l2_lookback_bars", Number(e.target.value))}
                />
              </div>
            </>
          )}

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
              aosSaving ||
              adaptiveProfilesLoading ||
              !config.ticker ||
              !config.date_from ||
              !config.date_to
            }
            style={{ width: "100%", marginTop: "var(--spacing-sm)" }}
          >
            {loading ? "Starting..." : (aosSaving ? "Saving AOS..." : "Start Backtest")}
          </button>
        </form>
      </div>
    </div>
  );
}

export default RunConfig;
