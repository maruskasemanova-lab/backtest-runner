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
  return payload && typeof payload === "object" && !Array.isArray(payload) ? payload : {};
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
    l2_only: false,
    l2_confirm_enabled: true,
    l2_min_imbalance: 0.0,
    l2_min_directional_consistency: 0.0,
    l2_min_signed_aggression: 0.0,
    l2_lookback_bars: 3,
    account_size_usd: 10000,
    regime_detection_minutes: 15,
    checkpoint_path: null,
    auto_save_checkpoint: true,
    cold_start_each_day: false,
    comparable_mode: false,
  });

  const [loading, setLoading] = useState(false);
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
      setAosTickerConfig(normalized);
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

        const targetTicker = data.tickers[0];
        const range = data.date_ranges[targetTicker];
        const defaultDate = range?.end || new Date().toISOString().split("T")[0];

        setConfig((prev) => ({
          ...prev,
          ticker: targetTicker,
          date: defaultDate,
          date_from: defaultDate,
          date_to: defaultDate,
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
      if (stopLossMode !== "strategy" && fixedStopLossPct <= 0) {
        throw new Error("Fixed stop-loss % must be > 0 when stop mode is fixed or capped.");
      }

      if (config.ticker) {
        const selectedProfileId =
          selectedAdaptiveProfileId === ACTIVE_PROFILE_SENTINEL
            ? ""
            : String(selectedAdaptiveProfileId || "").trim();
        if (selectedProfileId) {
          try {
            await applyAdaptiveProfile(config.ticker, selectedProfileId);
            setActiveAdaptiveProfileId(selectedProfileId);
            await fetchTickerAosConfig(config.ticker);
            await fetchAdaptiveProfiles(config.ticker);
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
        // Strategy overrides are used as FE defaults; do not re-apply them at run start.
        apply_ticker_overrides_on_start: false,
        cold_start_each_day: comparableMode ? true : !!config.cold_start_each_day,
        checkpoint_path: comparableMode
          ? null
          : (useWarmStart ? (config.checkpoint_path || "").trim() || null : null),
        auto_save_checkpoint: comparableMode ? false : !!config.auto_save_checkpoint,
      };

      if (config.data_file) {
        payload.data_file = config.data_file;
      }
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
    const defaultDate = range?.end;

    setConfig((prev) => ({
      ...prev,
      ticker,
      date: defaultDate || prev.date,
      date_from: defaultDate || range?.start || prev.date_from,
      date_to: defaultDate || range?.end || prev.date_to,
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
    effectiveConfig.strategy_selection_mode ?? aosTickerConfig?.strategy_selection_mode ?? "adaptive_top_n"
  );
  const activeMaxActiveStrategies = parseMaxActiveStrategies(
    effectiveConfig.max_active_strategies ?? aosTickerConfig?.max_active_strategies ?? 3,
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
              adaptiveProfilesLoading ||
              !config.ticker ||
              !config.date_from ||
              !config.date_to
            }
            style={{ width: "100%", marginTop: "var(--spacing-sm)" }}
          >
            {loading ? "Starting..." : "Start Backtest"}
          </button>
        </form>
      </div>
    </div>
  );
}

export default RunConfig;
