import { useCallback, useEffect, useState } from "react";

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
  "exhaustion_fade",
];

const DEFAULT_FLOW_BIAS_STRATEGIES = [
  "momentum_flow",
  "absorption_reversal",
  "exhaustion_fade",
];

const DEFAULT_REGIME_PREFERENCES = {
  TRENDING: [
    "momentum_flow",
    "momentum",
    "pullback",
    "gap_liquidity",
    "volume_profile",
    "vwap_magnet",
  ],
  CHOPPY: [
    "absorption_reversal",
    "exhaustion_fade",
    "mean_reversion",
    "vwap_magnet",
    "volume_profile",
  ],
  MIXED: [
    "exhaustion_fade",
    "absorption_reversal",
    "volume_profile",
    "gap_liquidity",
    "mean_reversion",
    "vwap_magnet",
    "rotation",
  ],
};

const DEFAULT_MICRO_PREFERENCES = {
  TRENDING_UP: ["momentum_flow", "momentum", "pullback", "gap_liquidity"],
  TRENDING_DOWN: ["momentum_flow", "momentum", "gap_liquidity", "pullback"],
  CHOPPY: ["absorption_reversal", "exhaustion_fade", "mean_reversion", "vwap_magnet"],
  ABSORPTION: ["absorption_reversal", "exhaustion_fade", "vwap_magnet"],
  BREAKOUT: ["momentum_flow", "momentum", "gap_liquidity"],
  MIXED: ["exhaustion_fade", "volume_profile", "rotation"],
};

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

const applyTunedCandidateToForm = (formState, candidate) => {
  const source = candidate && typeof candidate === "object" ? candidate : {};
  return {
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
};

const extractEnabledStrategiesFromCombo = (profile, strategyUniverse) => {
  const strategyParams =
    profile && typeof profile === "object" && typeof profile.strategy_params === "object"
      ? profile.strategy_params
      : {};
  const enabled = [];
  Object.entries(strategyParams || {}).forEach(([name, params]) => {
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
  const [rawTickerConfig, setRawTickerConfig] = useState({});
  const [form, setForm] = useState(() =>
    normalizeTickerAdaptiveForm({}, DEFAULT_STRATEGIES)
  );
  const [profileLoading, setProfileLoading] = useState(false);
  const [profileError, setProfileError] = useState(null);
  const [profileActionLoading, setProfileActionLoading] = useState(null);
  const [profileList, setProfileList] = useState([]);
  const [activeProfileId, setActiveProfileId] = useState("");
  const [comboLoading, setComboLoading] = useState(false);
  const [comboError, setComboError] = useState(null);
  const [comboActionLoading, setComboActionLoading] = useState(null);
  const [comboList, setComboList] = useState([]);
  const [activeComboId, setActiveComboId] = useState("");

  const activeTicker = String(selectedTicker || "").toUpperCase();
  const strategyApiBase = (strategyApiUrl || `http://${window.location.hostname}:8001`).replace(/\/+$/, "");

  const loadAvailableTickers = useCallback(async () => {
    try {
      const resp = await fetch("/api/available-data");
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
      setActiveProfileId(String(payload?.active_profile_id || "").trim());
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
      setActiveComboId(String(payload?.active_profile_id || "").trim());
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
        setForm(normalizeTickerAdaptiveForm(safePayload, strategyUniverse));
        setIsDirty(false);
        await Promise.all([loadProfileOptions(ticker), loadComboOptions(ticker)]);
      } catch (err) {
        console.error("Failed to load adaptive ticker config:", err);
        setError("Failed to load adaptive configuration for selected ticker.");
        setRawTickerConfig({});
        setForm(normalizeTickerAdaptiveForm({}, strategyUniverse));
        setIsDirty(false);
        setProfileList([]);
        setActiveProfileId("");
        setComboList([]);
        setActiveComboId("");
      } finally {
        setLoading(false);
      }
    },
    [loadComboOptions, loadProfileOptions, strategyUniverse]
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
      loadComboOptions(activeTicker);
    };
    window.addEventListener("strategy-combo-updated", handleComboUpdated);
    return () => {
      window.removeEventListener("strategy-combo-updated", handleComboUpdated);
    };
  }, [activeTicker, loadComboOptions]);

  const updateForm = (updater) => {
    setForm((prev) => {
      const next = typeof updater === "function" ? updater(prev) : updater;
      return next;
    });
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
      const normalizedForm = {
        ...form,
        strategy_selection_mode: normalizeMode(form.strategy_selection_mode),
        max_active_strategies: normalizeMaxActive(form.max_active_strategies, 3),
        flow_bias_enabled: !!form.flow_bias_enabled,
        use_ohlcv_fallbacks: !!form.use_ohlcv_fallbacks,
        min_active_bars_before_switch: normalizeNonNegativeInt(
          form.min_active_bars_before_switch,
          0
        ),
        switch_cooldown_bars: normalizeNonNegativeInt(form.switch_cooldown_bars, 0),
        flow_bias_strategies: normalizeStrategyList(
          form.flow_bias_strategies,
          DEFAULT_FLOW_BIAS_STRATEGIES,
          strategyUniverse
        ),
        regime_preferences: normalizePreferenceMap(
          form.regime_preferences,
          MACRO_REGIMES,
          DEFAULT_REGIME_PREFERENCES,
          strategyUniverse
        ),
        micro_regime_preferences: normalizePreferenceMap(
          form.micro_regime_preferences,
          MICRO_REGIMES,
          DEFAULT_MICRO_PREFERENCES,
          strategyUniverse
        ),
      };

      const currentConfig =
        rawTickerConfig && typeof rawTickerConfig === "object" && !Array.isArray(rawTickerConfig)
          ? rawTickerConfig
          : {};
      const currentAdaptive =
        currentConfig.adaptive && typeof currentConfig.adaptive === "object" && !Array.isArray(currentConfig.adaptive)
          ? currentConfig.adaptive
          : {};

      const nextConfig = {
        ...currentConfig,
        strategy_selection_mode: normalizedForm.strategy_selection_mode,
        max_active_strategies: normalizedForm.max_active_strategies,
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
      setNotice("Adaptive configuration saved. Changes are applied on the next run start.");
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

  const handleLoadProfileToEditor = (profile) => {
    const profileId = String(profile?.profile_id || "").trim();
    const candidate = profile?.candidate;
    if (!profileId || !candidate || typeof candidate !== "object") {
      setError("Cannot load profile: candidate payload is missing.");
      return;
    }
    setError(null);
    setNotice(`Loaded profile ${profileId} into editor. Save if you want to persist these values.`);
    setForm((prev) => applyTunedCandidateToForm(prev, candidate));
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
  const activeComboProfile = comboList.find(
    (profile) => String(profile?.profile_id || "").trim() === activeComboId
  ) || null;
  const activeComboEnabledStrategies = extractEnabledStrategiesFromCombo(
    activeComboProfile,
    strategyUniverse
  );

  const hasTickers = availableTickers.length > 0;

  return (
    <main className="adaptive-studio-page">
      <section className="card adaptive-studio-controls">
        <div className="card-header">
          <span className="card-title">Adaptive Strategy Studio</span>
          <div className="adaptive-toolbar">
            <button
              type="button"
              className="btn btn-secondary"
              onClick={handleReload}
              disabled={
                loading ||
                saving ||
                profileLoading ||
                comboLoading ||
                !!profileActionLoading ||
                !!comboActionLoading ||
                !activeTicker
              }
            >
              {loading || profileLoading || comboLoading ? "Loading..." : "Reload"}
            </button>
            <button
              type="button"
              className="btn btn-primary"
              onClick={handleSave}
              disabled={
                saving ||
                loading ||
                !!profileActionLoading ||
                !!comboActionLoading ||
                !activeTicker ||
                !isDirty
              }
            >
              {saving ? "Saving..." : "Save Adaptive Config"}
            </button>
          </div>
        </div>

        <div className="card-body adaptive-studio-grid">
          <div className="adaptive-column">
            <div className="form-group">
              <label htmlFor="adaptive_ticker">Ticker</label>
              <select
                id="adaptive_ticker"
                value={activeTicker}
                onChange={(e) => {
                  if (onTickerChange) onTickerChange(e.target.value);
                }}
                disabled={!hasTickers}
              >
                {!hasTickers && <option value="">No ticker data</option>}
                {availableTickers.map((ticker) => (
                  <option key={ticker} value={ticker}>
                    {ticker}
                  </option>
                ))}
              </select>
            </div>

            <div className="adaptive-info-box">
              Source of truth: <code>aos_optimization/aos_config.json</code> via <code>/api/aos-config</code>. Saved changes are applied on the next <code>/api/run/start</code>.
            </div>

            {error && <div className="adaptive-error">{error}</div>}
            {notice && <div className="adaptive-notice">{notice}</div>}
            {profileError && <div className="adaptive-error">{profileError}</div>}
            {comboError && <div className="adaptive-error">{comboError}</div>}

            <div className="adaptive-section">
              <h3>Strategy Parameter Combinations</h3>
              <div className="adaptive-preview-item">
                <span>Active combination profile</span>
                <strong>{activeComboId || "none"}</strong>
              </div>
              {activeComboProfile && (
                <div className="adaptive-preview-item">
                  <span>Enabled strategies in active combo</span>
                  <strong>{activeComboEnabledStrategies.length || 0}</strong>
                </div>
              )}
              {comboLoading ? (
                <div className="adaptive-empty">Loading strategy combinations...</div>
              ) : !comboList.length ? (
                <div className="adaptive-empty">
                  No saved strategy combinations for this ticker yet. Create one in the Strategies panel.
                </div>
              ) : (
                <div className="tuner-profile-list">
                  {comboList.map((combo, idx) => {
                    const comboId = String(combo?.profile_id || "").trim();
                    const isActive = !!comboId && comboId === activeComboId;
                    const enabledCount = extractEnabledStrategiesFromCombo(
                      combo,
                      strategyUniverse
                    ).length;
                    const totalStrategies = Object.keys(combo?.strategy_params || {}).length;
                    return (
                      <div
                        className={`tuner-profile-item ${isActive ? "active" : ""}`}
                        key={comboId || `combo-profile-${idx}`}
                      >
                        <div className="tuner-profile-head">
                          <strong>{combo?.profile_name || comboId || "combo"}</strong>
                          <span>{formatProfileTimestamp(combo?.updated_at || combo?.created_at)}</span>
                        </div>
                        <div className="tuner-profile-body">
                          <div>{comboId || "profile-id-missing"}</div>
                          <div>
                            {enabledCount} enabled / {totalStrategies} total strategies
                          </div>
                        </div>
                        <div className="tuner-profile-actions">
                          <button
                            type="button"
                            className="btn btn-secondary btn-sm"
                            onClick={() => handleSetActiveCombo(comboId)}
                            disabled={
                              !comboId ||
                              isActive ||
                              comboActionLoading === comboId ||
                              saving ||
                              loading
                            }
                          >
                            {comboActionLoading === comboId ? "Applying..." : (isActive ? "Active" : "Set Active")}
                          </button>
                          <button
                            type="button"
                            className="btn btn-secondary btn-sm"
                            onClick={() => handleRecomposeFromCombo(combo)}
                            disabled={!enabledCount}
                          >
                            Recompose Adaptive
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            <div className="adaptive-section">
              <h3>Adaptive Tuned Profiles (v1)</h3>
              <div className="adaptive-preview-item">
                <span>Active profile for backtest</span>
                <strong>{activeProfileId || "none"}</strong>
              </div>
              {profileLoading ? (
                <div className="adaptive-empty">Loading tuned profiles...</div>
              ) : !profileList.length ? (
                <div className="adaptive-empty">No saved tuned profiles for this ticker yet.</div>
              ) : (
                <div className="tuner-profile-list">
                  {profileList.map((profile, idx) => {
                    const profileId = String(profile?.profile_id || "").trim();
                    const isActive = !!profileId && profileId === activeProfileId;
                    return (
                      <div
                        className={`tuner-profile-item ${isActive ? "active" : ""}`}
                        key={profileId || `studio-profile-${idx}`}
                      >
                        <div className="tuner-profile-head">
                          <strong>{profileId || "profile"}</strong>
                          <span>{formatProfileTimestamp(profile?.created_at)}</span>
                        </div>
                        <div className="tuner-profile-body">
                          <div>{formatProfileCandidate(profile?.candidate)}</div>
                          <div>
                            score {Number(profile?.score || 0).toFixed(4)} | {profile?.date_from || "?"}
                            {" -> "}
                            {profile?.date_to || "?"}
                          </div>
                        </div>
                        <div className="tuner-profile-actions">
                          <button
                            type="button"
                            className="btn btn-secondary btn-sm"
                            onClick={() => handleLoadProfileToEditor(profile)}
                            disabled={!profileId || !!profileActionLoading}
                          >
                            Load To Editor
                          </button>
                          <button
                            type="button"
                            className="btn btn-secondary btn-sm"
                            onClick={() => handleSetActiveProfile(profileId)}
                            disabled={
                              !profileId ||
                              isActive ||
                              profileActionLoading === profileId ||
                              saving ||
                              loading
                            }
                          >
                            {profileActionLoading === profileId ? "Applying..." : (isActive ? "Active" : "Set Active")}
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

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
                <span>Prefer flow strategies when L2 coverage exists</span>
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
                <span>Use OHLCV fallback strategies when L2 is unavailable</span>
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
                <label htmlFor="adaptive_min_active_bars">
                  Strategy hysteresis (min active bars before switch)
                </label>
                <input
                  id="adaptive_min_active_bars"
                  type="number"
                  min="0"
                  step="1"
                  value={normalizeNonNegativeInt(form.min_active_bars_before_switch, 0)}
                  onChange={(e) =>
                    updateForm((prev) => ({
                      ...prev,
                      min_active_bars_before_switch: normalizeNonNegativeInt(
                        e.target.value,
                        0
                      ),
                    }))
                  }
                />
              </div>

              <div className="form-group">
                <label htmlFor="adaptive_switch_cooldown_bars">
                  Cooldown after switch (bars)
                </label>
                <input
                  id="adaptive_switch_cooldown_bars"
                  type="number"
                  min="0"
                  step="1"
                  value={normalizeNonNegativeInt(form.switch_cooldown_bars, 0)}
                  onChange={(e) =>
                    updateForm((prev) => ({
                      ...prev,
                      switch_cooldown_bars: normalizeNonNegativeInt(
                        e.target.value,
                        0
                      ),
                    }))
                  }
                />
              </div>

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
          </div>

          <div className="adaptive-column">
            <div className="adaptive-section">
              <h3>Macro Regime Preferences</h3>
              <div className="adaptive-editor-grid">
                {MACRO_REGIMES.map((regime) =>
                  renderPriorityEditor("regime_preferences", regime, regime)
                )}
              </div>
            </div>

            <div className="adaptive-section">
              <h3>Micro Regime Preferences</h3>
              <div className="adaptive-editor-grid">
                {MICRO_REGIMES.map((regime) =>
                  renderPriorityEditor("micro_regime_preferences", regime, regime)
                )}
              </div>
            </div>
          </div>

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
                    Strategy combo profile: {activeComboId || "none"}.
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

            <div className="adaptive-section">
              <h3>Runtime Preview</h3>
              <div className="adaptive-preview-list">
                <div className="adaptive-preview-item">
                  <span>Active strategy combination</span>
                  <strong>{activeComboId || "none"}</strong>
                </div>
                <div className="adaptive-preview-item">
                  <span>Active tuned profile</span>
                  <strong>{activeProfileId || "none"}</strong>
                </div>
                <div className="adaptive-preview-item">
                  <span>Mode</span>
                  <strong>{strategyModeLabel}</strong>
                </div>
                <div className="adaptive-preview-item">
                  <span>Flow bias list</span>
                  <strong>{flowSummary(form.flow_bias_strategies)}</strong>
                </div>
                <div className="adaptive-preview-item">
                  <span>Switch guard</span>
                  <strong>
                    min-active {normalizeNonNegativeInt(form.min_active_bars_before_switch, 0)} bars, cooldown {normalizeNonNegativeInt(form.switch_cooldown_bars, 0)} bars
                  </strong>
                </div>
                <div className="adaptive-preview-item">
                  <span>TRENDING macro top-3</span>
                  <strong>
                    {(form.regime_preferences.TRENDING || []).slice(0, 3).map(strategyLabel).join(", ") || "none"}
                  </strong>
                </div>
                <div className="adaptive-preview-item">
                  <span>TRENDING_UP micro top-3</span>
                  <strong>
                    {(form.micro_regime_preferences.TRENDING_UP || []).slice(0, 3).map(strategyLabel).join(", ") || "none"}
                  </strong>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}

export default AdaptiveStrategyStudio;
