import { useState, useEffect, useCallback } from "react";
import {
  toFiniteNumber,
  clamp,
  clampInt,
  parseCsvTokens,
  toCsvString,
  normalizeSleeveId,
  resolveRunnerApiBaseUrl,
} from "../utils";

const resolveRunnerUrl = (apiUrl) => {
  const base = (apiUrl || "").trim();
  if (base) {
    return resolveRunnerApiBaseUrl(base);
  }
  return resolveRunnerApiBaseUrl("");
};

const safeObject = (value) => {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return {};
  }
  return value;
};

const safeArray = (value) => (Array.isArray(value) ? value : []);



const createDefaultSleeveDraft = (index = 1) => ({
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

const createDefaultMomentumDraft = () => ({
  enabled: true,
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
  apply_to_strategies: "momentum_flow",
  allowed_micro_regimes: "",
  blocked_micro_regimes: "",
  sleeves: [],
});

const normalizeSleeveDraft = (raw, index) => {
  const source = safeObject(raw);
  return {
    ...createDefaultSleeveDraft(index + 1),
    sleeve_id: normalizeSleeveId(source.sleeve_id, `sleeve_${index + 1}`),
    enabled: !!source.enabled,
    allocation_weight: clamp(source.allocation_weight, 0.5, 0, 1),
    apply_to_strategies: toCsvString(source.apply_to_strategies, (v) => v.toLowerCase()),
    allowed_micro_regimes: toCsvString(source.allowed_micro_regimes, (v) => v.toUpperCase()),
    blocked_micro_regimes: toCsvString(source.blocked_micro_regimes, (v) => v.toUpperCase()),
    require_l2_coverage: typeof source.require_l2_coverage === "boolean" ? source.require_l2_coverage : true,
    route_enabled: typeof source.route_enabled === "boolean" ? source.route_enabled : true,
    route_require_l2_coverage:
      typeof source.route_require_l2_coverage === "boolean" ? source.route_require_l2_coverage : true,
    min_flow_score: clamp(source.min_flow_score, 58, 0, 100),
    min_directional_consistency: clamp(source.min_directional_consistency, 0.45, 0, 1),
    min_signed_aggression: clamp(source.min_signed_aggression, 0.04, 0, 1),
    min_imbalance: clamp(source.min_imbalance, 0.02, 0, 1),
    min_cvd: clamp(source.min_cvd, 0, -1_000_000_000, 1_000_000_000),
    min_directional_price_change_pct: clamp(source.min_directional_price_change_pct, 0, -100, 100),
    min_price_trend_efficiency: clamp(source.min_price_trend_efficiency, 0, 0, 1),
    min_last_bar_body_ratio: clamp(source.min_last_bar_body_ratio, 0, 0, 1),
    min_last_bar_close_location: clamp(source.min_last_bar_close_location, 0, 0, 1),
    min_delta_acceleration: clamp(source.min_delta_acceleration, 0, -1_000_000_000, 1_000_000_000),
    min_delta_price_divergence: clamp(source.min_delta_price_divergence, 0, -10, 10),
    route_flow_score_impulse: clamp(source.route_flow_score_impulse, 64, 0, 100),
    fail_fast_exit_enabled:
      typeof source.fail_fast_exit_enabled === "boolean" ? source.fail_fast_exit_enabled : true,
    fail_fast_max_bars: clampInt(source.fail_fast_max_bars, 3, 1, 30),
    fail_fast_signed_aggression_max: clamp(source.fail_fast_signed_aggression_max, -0.08, -1, 0),
    fail_fast_book_pressure_max: clamp(source.fail_fast_book_pressure_max, -0.1, -1, 0),
    fail_fast_directional_consistency_max: clamp(
      source.fail_fast_directional_consistency_max,
      0.2,
      0,
      1
    ),
  };
};

const normalizeMomentumDraft = (raw) => {
  const source = safeObject(raw);
  const base = createDefaultMomentumDraft();
  return {
    ...base,
    enabled: typeof source.enabled === "boolean" ? source.enabled : base.enabled,
    require_l2_coverage:
      typeof source.require_l2_coverage === "boolean"
        ? source.require_l2_coverage
        : base.require_l2_coverage,
    route_enabled: typeof source.route_enabled === "boolean" ? source.route_enabled : base.route_enabled,
    route_require_l2_coverage:
      typeof source.route_require_l2_coverage === "boolean"
        ? source.route_require_l2_coverage
        : base.route_require_l2_coverage,
    min_flow_score: clamp(source.min_flow_score, base.min_flow_score, 0, 100),
    min_directional_consistency: clamp(
      source.min_directional_consistency,
      base.min_directional_consistency,
      0,
      1
    ),
    min_signed_aggression: clamp(source.min_signed_aggression, base.min_signed_aggression, 0, 1),
    min_imbalance: clamp(source.min_imbalance, base.min_imbalance, 0, 1),
    min_cvd: clamp(source.min_cvd, base.min_cvd, -1_000_000_000, 1_000_000_000),
    min_directional_price_change_pct: clamp(
      source.min_directional_price_change_pct,
      base.min_directional_price_change_pct,
      -100,
      100
    ),
    min_price_trend_efficiency: clamp(
      source.min_price_trend_efficiency,
      base.min_price_trend_efficiency,
      0,
      1
    ),
    min_last_bar_body_ratio: clamp(source.min_last_bar_body_ratio, base.min_last_bar_body_ratio, 0, 1),
    min_last_bar_close_location: clamp(
      source.min_last_bar_close_location,
      base.min_last_bar_close_location,
      0,
      1
    ),
    min_delta_acceleration: clamp(source.min_delta_acceleration, base.min_delta_acceleration, -1_000_000_000, 1_000_000_000),
    min_delta_price_divergence: clamp(source.min_delta_price_divergence, base.min_delta_price_divergence, -10, 10),
    route_flow_score_impulse: clamp(source.route_flow_score_impulse, base.route_flow_score_impulse, 0, 100),
    fail_fast_exit_enabled:
      typeof source.fail_fast_exit_enabled === "boolean"
        ? source.fail_fast_exit_enabled
        : base.fail_fast_exit_enabled,
    fail_fast_max_bars: clampInt(source.fail_fast_max_bars, base.fail_fast_max_bars, 1, 30),
    fail_fast_signed_aggression_max: clamp(
      source.fail_fast_signed_aggression_max,
      base.fail_fast_signed_aggression_max,
      -1,
      0
    ),
    fail_fast_book_pressure_max: clamp(
      source.fail_fast_book_pressure_max,
      base.fail_fast_book_pressure_max,
      -1,
      0
    ),
    fail_fast_directional_consistency_max: clamp(
      source.fail_fast_directional_consistency_max,
      base.fail_fast_directional_consistency_max,
      0,
      1
    ),
    apply_to_strategies: toCsvString(source.apply_to_strategies, (v) => v.toLowerCase()),
    allowed_micro_regimes: toCsvString(source.allowed_micro_regimes, (v) => v.toUpperCase()),
    blocked_micro_regimes: toCsvString(source.blocked_micro_regimes, (v) => v.toUpperCase()),
    sleeves: safeArray(source.sleeves).map((sleeve, index) => normalizeSleeveDraft(sleeve, index)),
  };
};

const buildMomentumSleeveConfig = (draft, index) => {
  const source = safeObject(draft);
  const payload: Record<string, any> = {
    sleeve_id: normalizeSleeveId(source.sleeve_id, `sleeve_${index + 1}`),
    enabled: !!source.enabled,
    allocation_weight: clamp(source.allocation_weight, 0.5, 0, 1),
    require_l2_coverage: !!source.require_l2_coverage,
    route_enabled: !!source.route_enabled,
    route_require_l2_coverage: !!source.route_require_l2_coverage,
    min_flow_score: clamp(source.min_flow_score, 58, 0, 100),
    min_directional_consistency: clamp(source.min_directional_consistency, 0.45, 0, 1),
    min_signed_aggression: clamp(source.min_signed_aggression, 0.04, 0, 1),
    min_imbalance: clamp(source.min_imbalance, 0.02, 0, 1),
    min_cvd: clamp(source.min_cvd, 0, -1_000_000_000, 1_000_000_000),
    min_directional_price_change_pct: clamp(source.min_directional_price_change_pct, 0, -100, 100),
    min_price_trend_efficiency: clamp(source.min_price_trend_efficiency, 0, 0, 1),
    min_last_bar_body_ratio: clamp(source.min_last_bar_body_ratio, 0, 0, 1),
    min_last_bar_close_location: clamp(source.min_last_bar_close_location, 0, 0, 1),
    min_delta_acceleration: clamp(source.min_delta_acceleration, 0, -1_000_000_000, 1_000_000_000),
    min_delta_price_divergence: clamp(source.min_delta_price_divergence, 0, -10, 10),
    route_flow_score_impulse: clamp(source.route_flow_score_impulse, 64, 0, 100),
    fail_fast_exit_enabled: !!source.fail_fast_exit_enabled,
    fail_fast_max_bars: clampInt(source.fail_fast_max_bars, 3, 1, 30),
    fail_fast_signed_aggression_max: clamp(source.fail_fast_signed_aggression_max, -0.08, -1, 0),
    fail_fast_book_pressure_max: clamp(source.fail_fast_book_pressure_max, -0.1, -1, 0),
    fail_fast_directional_consistency_max: clamp(
      source.fail_fast_directional_consistency_max,
      0.2,
      0,
      1
    ),
  };

  const applyTo = parseCsvTokens(source.apply_to_strategies, (v) => v.toLowerCase());
  if (applyTo.length) payload.apply_to_strategies = applyTo;
  const allowed = parseCsvTokens(source.allowed_micro_regimes, (v) => v.toUpperCase());
  if (allowed.length) payload.allowed_micro_regimes = allowed;
  const blocked = parseCsvTokens(source.blocked_micro_regimes, (v) => v.toUpperCase());
  if (blocked.length) payload.blocked_micro_regimes = blocked;
  return payload;
};

const buildMomentumConfigFromDraft = (draft) => {
  const source = safeObject(draft);
  const payload: Record<string, any> = {
    enabled: !!source.enabled,
    require_l2_coverage: !!source.require_l2_coverage,
    route_enabled: !!source.route_enabled,
    route_require_l2_coverage: !!source.route_require_l2_coverage,
    min_flow_score: clamp(source.min_flow_score, 58, 0, 100),
    min_directional_consistency: clamp(source.min_directional_consistency, 0.45, 0, 1),
    min_signed_aggression: clamp(source.min_signed_aggression, 0.04, 0, 1),
    min_imbalance: clamp(source.min_imbalance, 0.02, 0, 1),
    min_cvd: clamp(source.min_cvd, 0, -1_000_000_000, 1_000_000_000),
    min_directional_price_change_pct: clamp(source.min_directional_price_change_pct, 0, -100, 100),
    min_price_trend_efficiency: clamp(source.min_price_trend_efficiency, 0, 0, 1),
    min_last_bar_body_ratio: clamp(source.min_last_bar_body_ratio, 0, 0, 1),
    min_last_bar_close_location: clamp(source.min_last_bar_close_location, 0, 0, 1),
    min_delta_acceleration: clamp(source.min_delta_acceleration, 0, -1_000_000_000, 1_000_000_000),
    min_delta_price_divergence: clamp(source.min_delta_price_divergence, 0, -10, 10),
    route_flow_score_impulse: clamp(source.route_flow_score_impulse, 64, 0, 100),
    fail_fast_exit_enabled: !!source.fail_fast_exit_enabled,
    fail_fast_max_bars: clampInt(source.fail_fast_max_bars, 3, 1, 30),
    fail_fast_signed_aggression_max: clamp(source.fail_fast_signed_aggression_max, -0.08, -1, 0),
    fail_fast_book_pressure_max: clamp(source.fail_fast_book_pressure_max, -0.1, -1, 0),
    fail_fast_directional_consistency_max: clamp(
      source.fail_fast_directional_consistency_max,
      0.2,
      0,
      1
    ),
  };
  const applyTo = parseCsvTokens(source.apply_to_strategies, (v) => v.toLowerCase());
  if (applyTo.length) payload.apply_to_strategies = applyTo;
  const allowed = parseCsvTokens(source.allowed_micro_regimes, (v) => v.toUpperCase());
  if (allowed.length) payload.allowed_micro_regimes = allowed;
  const blocked = parseCsvTokens(source.blocked_micro_regimes, (v) => v.toUpperCase());
  if (blocked.length) payload.blocked_micro_regimes = blocked;

  const sleeves = safeArray(source.sleeves)
    .map((sleeve, index) => buildMomentumSleeveConfig(sleeve, index))
    .filter((item) => item && typeof item === "object");
  if (sleeves.length) payload.sleeves = sleeves;

  return payload;
};

const mergeMomentumIntoTickerConfig = (tickerConfig, momentumDraft) => {
  const next = { ...safeObject(tickerConfig) };
  const adaptive = { ...safeObject(next.adaptive) };
  adaptive.momentum_diversification = buildMomentumConfigFromDraft(momentumDraft);
  next.adaptive = adaptive;
  return next;
};

const parseTickerConfigText = (rawText) => {
  const text = String(rawText || "").trim();
  if (!text) return {};
  let parsed;
  try {
    parsed = JSON.parse(text);
  } catch (err) {
    throw new Error(`Invalid JSON: ${err.message}`);
  }
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("Ticker config JSON must be an object.");
  }
  return safeObject(parsed);
};

function AOSOptimizations({ apiUrl, selectedTicker, onOptimizationChange }) {
  const [aosConfig, setAosConfig] = useState({ tickers: {} });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [rawConfigText, setRawConfigText] = useState("");
  const [rawConfigError, setRawConfigError] = useState(null);
  const [rawConfigSaving, setRawConfigSaving] = useState(false);
  const [rawConfigDirty, setRawConfigDirty] = useState(false);
  const [momentumDraft, setMomentumDraft] = useState(createDefaultMomentumDraft);
  const [momentumDirty, setMomentumDirty] = useState(false);
  const [momentumSaving, setMomentumSaving] = useState(false);
  const [momentumError, setMomentumError] = useState(null);
  const [momentumNotice, setMomentumNotice] = useState(null);

  const selectedTickerKey = (selectedTicker || "").toUpperCase();

  const fetchAOSConfig = useCallback(async () => {
    setLoading(true);
    setError(null);
    const runnerUrl = resolveRunnerUrl(apiUrl);

    try {
      const resp = await fetch(`${runnerUrl}/api/aos-config`);
      if (!resp.ok) {
        throw new Error(`HTTP ${resp.status}`);
      }
      const payload = await resp.json();
      const normalized = safeObject(payload);
      normalized.tickers = safeObject(normalized.tickers);
      setAosConfig(normalized);
    } catch (err) {
      console.log("AOS config API unavailable", err);
      setError("AOS config API is unavailable.");
      setAosConfig({ tickers: {} });
    } finally {
      setLoading(false);
    }
  }, [apiUrl]);

  useEffect(() => {
    fetchAOSConfig();
  }, [fetchAOSConfig]);

  useEffect(() => {
    if (!selectedTickerKey) {
      setRawConfigText("");
      setRawConfigError(null);
      setRawConfigDirty(false);
      setMomentumDraft(createDefaultMomentumDraft());
      setMomentumDirty(false);
      setMomentumError(null);
      setMomentumNotice(null);
      return;
    }

    const tickerConfig = safeObject(aosConfig?.tickers?.[selectedTickerKey]);
    const momentumCfg = safeObject(safeObject(tickerConfig.adaptive).momentum_diversification);
    setRawConfigText(JSON.stringify(tickerConfig, null, 2));
    setRawConfigError(null);
    setRawConfigDirty(false);
    setMomentumDraft(normalizeMomentumDraft(momentumCfg));
    setMomentumDirty(false);
    setMomentumError(null);
    setMomentumNotice(null);
  }, [selectedTickerKey, aosConfig]);

  const persistConfig = useCallback(
    async (tickerKey, configValue) => {
      if (!tickerKey) return;
      const runnerUrl = resolveRunnerUrl(apiUrl);

      const resp = await fetch(`${runnerUrl}/api/aos-config/update`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ticker: tickerKey,
          config: configValue,
        }),
      });

      if (!resp.ok) {
        throw new Error(`HTTP ${resp.status}`);
      }
    },
    [apiUrl]
  );

  const applyRawConfig = async () => {
    if (!selectedTickerKey) return;

    let parsed;
    try {
      parsed = parseTickerConfigText(rawConfigText || "{}");
    } catch (err) {
      setRawConfigError(err.message);
      return;
    }

    const nextConfig = safeObject(parsed);
    setRawConfigSaving(true);
    setRawConfigError(null);

    try {
      await persistConfig(selectedTickerKey, nextConfig);

      setAosConfig((prev) => ({
        ...safeObject(prev),
        tickers: {
          ...safeObject(prev?.tickers),
          [selectedTickerKey]: nextConfig,
        },
      }));

      setRawConfigText(JSON.stringify(nextConfig, null, 2));
      setRawConfigDirty(false);
      const momentumCfg = safeObject(safeObject(nextConfig.adaptive).momentum_diversification);
      setMomentumDraft(normalizeMomentumDraft(momentumCfg));
      setMomentumDirty(false);
      setMomentumError(null);
      setMomentumNotice("Visual momentum editor synced from saved JSON.");
      setError(null);

      if (onOptimizationChange) {
        onOptimizationChange(selectedTickerKey, nextConfig);
      }
    } catch (err) {
      console.log("Could not save AOS config to server", err);
      setError("Could not save AOS config to server. Changes are local only.");
    } finally {
      setRawConfigSaving(false);
    }
  };

  const resetRawConfig = () => {
    if (!selectedTickerKey) return;
    const tickerConfig = safeObject(aosConfig?.tickers?.[selectedTickerKey]);
    const momentumCfg = safeObject(safeObject(tickerConfig.adaptive).momentum_diversification);
    setRawConfigText(JSON.stringify(tickerConfig, null, 2));
    setRawConfigError(null);
    setRawConfigDirty(false);
    setMomentumDraft(normalizeMomentumDraft(momentumCfg));
    setMomentumDirty(false);
    setMomentumError(null);
    setMomentumNotice("Reset to persisted ticker config.");
  };

  const handleMomentumChange = (field, value) => {
    setMomentumDraft((prev) => ({ ...safeObject(prev), [field]: value }));
    setMomentumDirty(true);
    setMomentumError(null);
    setMomentumNotice(null);
  };

  const handleSleeveChange = (index, field, value) => {
    setMomentumDraft((prev) => {
      const current = safeArray(prev?.sleeves);
      if (index < 0 || index >= current.length) return prev;
      return {
        ...safeObject(prev),
        sleeves: current.map((item, idx) =>
          idx === index ? { ...safeObject(item), [field]: value } : item
        ),
      };
    });
    setMomentumDirty(true);
    setMomentumError(null);
    setMomentumNotice(null);
  };

  const addSleeve = () => {
    setMomentumDraft((prev) => {
      const current = safeArray(prev?.sleeves);
      return {
        ...safeObject(prev),
        sleeves: [...current, createDefaultSleeveDraft(current.length + 1)],
      };
    });
    setMomentumDirty(true);
    setMomentumError(null);
    setMomentumNotice(null);
  };

  const removeSleeve = (index) => {
    setMomentumDraft((prev) => {
      const current = safeArray(prev?.sleeves);
      return {
        ...safeObject(prev),
        sleeves: current.filter((_, idx) => idx !== index),
      };
    });
    setMomentumDirty(true);
    setMomentumError(null);
    setMomentumNotice(null);
  };

  const loadMomentumFromEditor = () => {
    try {
      const parsed = parseTickerConfigText(rawConfigText || "{}");
      const momentumCfg = safeObject(safeObject(parsed.adaptive).momentum_diversification);
      setMomentumDraft(normalizeMomentumDraft(momentumCfg));
      setMomentumDirty(false);
      setMomentumError(null);
      setMomentumNotice("Loaded momentum settings from JSON editor.");
    } catch (err) {
      setMomentumError(err.message);
    }
  };

  const applyMomentumToEditor = () => {
    try {
      const base = parseTickerConfigText(rawConfigText || "{}");
      const nextConfig = mergeMomentumIntoTickerConfig(base, momentumDraft);
      setRawConfigText(JSON.stringify(nextConfig, null, 2));
      setRawConfigDirty(true);
      setRawConfigError(null);
      setMomentumDirty(false);
      setMomentumError(null);
      setMomentumNotice("Applied visual momentum settings to JSON editor.");
    } catch (err) {
      setMomentumError(err.message);
    }
  };

  const saveMomentumDirect = async () => {
    if (!selectedTickerKey) return;
    setMomentumSaving(true);
    setMomentumError(null);
    setMomentumNotice(null);
    try {
      let baseConfig = safeObject(aosConfig?.tickers?.[selectedTickerKey]);
      if (rawConfigDirty) {
        baseConfig = parseTickerConfigText(rawConfigText || "{}");
      }
      const nextConfig = mergeMomentumIntoTickerConfig(baseConfig, momentumDraft);
      await persistConfig(selectedTickerKey, nextConfig);

      setAosConfig((prev) => ({
        ...safeObject(prev),
        tickers: {
          ...safeObject(prev?.tickers),
          [selectedTickerKey]: nextConfig,
        },
      }));
      setRawConfigText(JSON.stringify(nextConfig, null, 2));
      setRawConfigDirty(false);
      setRawConfigError(null);
      setMomentumDraft(normalizeMomentumDraft(safeObject(safeObject(nextConfig.adaptive).momentum_diversification)));
      setMomentumDirty(false);
      setMomentumNotice("Saved visual momentum settings to server.");
      setError(null);

      if (onOptimizationChange) {
        onOptimizationChange(selectedTickerKey, nextConfig);
      }
    } catch (err) {
      setMomentumError(
        rawConfigDirty
          ? `Cannot save while JSON editor is invalid: ${err.message}`
          : `Could not save visual momentum settings: ${err.message}`
      );
    } finally {
      setMomentumSaving(false);
    }
  };

  const hasTickerConfig =
    !!selectedTickerKey &&
    Object.prototype.hasOwnProperty.call(safeObject(aosConfig?.tickers), selectedTickerKey);
  const sleeves = safeArray(momentumDraft?.sleeves);

  if (!selectedTickerKey) {
    return (
      <div className="card">
        <div className="card-header">
          <span className="card-title">AOS Config</span>
        </div>
        <div className="card-body" style={{ color: "var(--text-muted)" }}>
          Select a ticker to edit AOS configuration from file.
        </div>
      </div>
    );
  }

  return (
    <div className="card">
      <div className="card-header">
        <span className="card-title">AOS Config - {selectedTickerKey}</span>
        <button className="btn btn-secondary" onClick={fetchAOSConfig} disabled={loading || rawConfigSaving || momentumSaving}>
          Reload
        </button>
      </div>

      <div className="card-body" style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
        {loading && <div style={{ color: "var(--text-muted)" }}>Loading config...</div>}
        {error && <div style={{ color: "var(--accent-red)" }}>{error}</div>}

        <div
          style={{
            border: "1px solid var(--border-color)",
            borderRadius: "6px",
            padding: "12px",
            fontSize: "0.8rem",
            color: "var(--text-muted)",
          }}
        >
          Source of truth: <code>aos_optimization/aos_config.json</code> (adaptive/strategy)
          plus <code>aos_optimization/positioning_config.json</code> (execution/positioning) via{" "}
          <code>/api/aos-config</code>. Saved changes are applied on the next <code>/api/run/start</code>.
        </div>

        {!hasTickerConfig && (
          <div style={{ color: "var(--accent-yellow)", fontSize: "0.8rem" }}>
            No existing config for {selectedTickerKey} in file. Editing starts from an empty object.
          </div>
        )}

        <div
          style={{
            border: "1px solid var(--border-color)",
            borderRadius: "6px",
            padding: "12px",
            display: "flex",
            flexDirection: "column",
            gap: "10px",
            background: "var(--bg-secondary)",
          }}
        >
          <div style={{ fontWeight: 700, fontSize: "0.82rem" }}>
            Visual Momentum Diversification
          </div>
          <div style={{ color: "var(--text-muted)", fontSize: "0.76rem" }}>
            Structured editor for <code>adaptive.momentum_diversification</code> with multi-sleeve support.
          </div>

          <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
            <button className="btn btn-secondary" onClick={loadMomentumFromEditor} disabled={rawConfigSaving || momentumSaving}>
              Load From JSON
            </button>
            <button className="btn btn-secondary" onClick={applyMomentumToEditor} disabled={rawConfigSaving || momentumSaving}>
              Apply Visual To JSON
            </button>
            <button className="btn btn-primary" onClick={saveMomentumDirect} disabled={momentumSaving}>
              {momentumSaving ? "Saving visual..." : "Save Visual To Server"}
            </button>
          </div>

          {momentumNotice && (
            <div style={{ color: "var(--accent-green)", fontSize: "0.78rem" }}>
              {momentumNotice}
            </div>
          )}
          {momentumError && (
            <div style={{ color: "var(--accent-red)", fontSize: "0.78rem" }}>
              {momentumError}
            </div>
          )}

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
              gap: "8px",
            }}
          >
            <label className="field-row">
              <span>Enabled</span>
              <input
                type="checkbox"
                checked={!!momentumDraft.enabled}
                onChange={(e) => handleMomentumChange("enabled", e.target.checked)}
              />
            </label>
            <label className="field-row">
              <span>Require L2 Coverage</span>
              <input
                type="checkbox"
                checked={!!momentumDraft.require_l2_coverage}
                onChange={(e) => handleMomentumChange("require_l2_coverage", e.target.checked)}
              />
            </label>
            <label className="field-row">
              <span>Route Enabled</span>
              <input
                type="checkbox"
                checked={!!momentumDraft.route_enabled}
                onChange={(e) => handleMomentumChange("route_enabled", e.target.checked)}
              />
            </label>
            <label className="field-row">
              <span>Route Requires L2</span>
              <input
                type="checkbox"
                checked={!!momentumDraft.route_require_l2_coverage}
                onChange={(e) => handleMomentumChange("route_require_l2_coverage", e.target.checked)}
              />
            </label>
            <label className="field-row">
              <span>Fail-Fast Enabled</span>
              <input
                type="checkbox"
                checked={!!momentumDraft.fail_fast_exit_enabled}
                onChange={(e) => handleMomentumChange("fail_fast_exit_enabled", e.target.checked)}
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
                value={momentumDraft.min_flow_score}
                onChange={(e) => handleMomentumChange("min_flow_score", Number(e.target.value))}
              />
            </div>
            <div className="form-group">
              <label>Min Directional Consistency</label>
              <input
                type="number"
                min="0"
                max="1"
                step="0.01"
                value={momentumDraft.min_directional_consistency}
                onChange={(e) =>
                  handleMomentumChange("min_directional_consistency", Number(e.target.value))
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
                value={momentumDraft.min_signed_aggression}
                onChange={(e) => handleMomentumChange("min_signed_aggression", Number(e.target.value))}
              />
            </div>
            <div className="form-group">
              <label>Min Imbalance</label>
              <input
                type="number"
                min="0"
                max="1"
                step="0.01"
                value={momentumDraft.min_imbalance}
                onChange={(e) => handleMomentumChange("min_imbalance", Number(e.target.value))}
              />
            </div>
            <div className="form-group">
              <label>Min CVD (Directional)</label>
              <input
                type="number"
                min="-1000000000"
                max="1000000000"
                step="1"
                value={momentumDraft.min_cvd}
                onChange={(e) => handleMomentumChange("min_cvd", Number(e.target.value))}
              />
            </div>
            <div className="form-group">
              <label>Min Directional Price Change %</label>
              <input
                type="number"
                min="-100"
                max="100"
                step="0.01"
                value={momentumDraft.min_directional_price_change_pct}
                onChange={(e) =>
                  handleMomentumChange("min_directional_price_change_pct", Number(e.target.value))
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
                value={momentumDraft.min_price_trend_efficiency}
                onChange={(e) =>
                  handleMomentumChange("min_price_trend_efficiency", Number(e.target.value))
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
                value={momentumDraft.min_last_bar_body_ratio}
                onChange={(e) =>
                  handleMomentumChange("min_last_bar_body_ratio", Number(e.target.value))
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
                value={momentumDraft.min_last_bar_close_location}
                onChange={(e) =>
                  handleMomentumChange("min_last_bar_close_location", Number(e.target.value))
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
                value={momentumDraft.min_delta_acceleration}
                onChange={(e) => handleMomentumChange("min_delta_acceleration", Number(e.target.value))}
              />
            </div>
            <div className="form-group">
              <label>Min Delta-Price Divergence</label>
              <input
                type="number"
                min="-10"
                max="10"
                step="0.01"
                value={momentumDraft.min_delta_price_divergence}
                onChange={(e) =>
                  handleMomentumChange("min_delta_price_divergence", Number(e.target.value))
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
                value={momentumDraft.route_flow_score_impulse}
                onChange={(e) => handleMomentumChange("route_flow_score_impulse", Number(e.target.value))}
              />
            </div>
            <div className="form-group">
              <label>Fail-Fast Max Bars</label>
              <input
                type="number"
                min="1"
                max="30"
                step="1"
                value={momentumDraft.fail_fast_max_bars}
                onChange={(e) => handleMomentumChange("fail_fast_max_bars", Number(e.target.value))}
              />
            </div>
            <div className="form-group">
              <label>Fail-Fast Signed Aggression Max</label>
              <input
                type="number"
                min="-1"
                max="0"
                step="0.01"
                value={momentumDraft.fail_fast_signed_aggression_max}
                onChange={(e) =>
                  handleMomentumChange("fail_fast_signed_aggression_max", Number(e.target.value))
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
                value={momentumDraft.fail_fast_book_pressure_max}
                onChange={(e) =>
                  handleMomentumChange("fail_fast_book_pressure_max", Number(e.target.value))
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
                value={momentumDraft.fail_fast_directional_consistency_max}
                onChange={(e) =>
                  handleMomentumChange(
                    "fail_fast_directional_consistency_max",
                    Number(e.target.value)
                  )
                }
              />
            </div>
          </div>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
              gap: "10px",
            }}
          >
            <div className="form-group">
              <label>Apply To Strategies (CSV)</label>
              <input
                type="text"
                value={momentumDraft.apply_to_strategies}
                onChange={(e) => handleMomentumChange("apply_to_strategies", e.target.value)}
                placeholder="momentum_flow,pullback"
              />
            </div>
            <div className="form-group">
              <label>Allowed Micro Regimes (CSV)</label>
              <input
                type="text"
                value={momentumDraft.allowed_micro_regimes}
                onChange={(e) => handleMomentumChange("allowed_micro_regimes", e.target.value)}
                placeholder="TRENDING_UP,BREAKOUT"
              />
            </div>
            <div className="form-group">
              <label>Blocked Micro Regimes (CSV)</label>
              <input
                type="text"
                value={momentumDraft.blocked_micro_regimes}
                onChange={(e) => handleMomentumChange("blocked_micro_regimes", e.target.value)}
                placeholder="CHOPPY,ABSORPTION"
              />
            </div>
          </div>

          <div
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
              <div style={{ fontWeight: 700, fontSize: "0.78rem" }}>Momentum Sleeves</div>
              <button className="btn btn-secondary" type="button" onClick={addSleeve}>
                Add Sleeve
              </button>
            </div>

            {sleeves.length === 0 ? (
              <div style={{ color: "var(--text-muted)", fontSize: "0.75rem" }}>
                No sleeves defined. Add sleeve rows to enable multi-sleeve behavior.
              </div>
            ) : (
              <div style={{ display: "grid", gap: "10px" }}>
                {sleeves.map((sleeve, index) => (
                  <div
                    key={`${sleeve?.sleeve_id || "sleeve"}-${index}`}
                    style={{
                      border: "1px solid var(--border-color)",
                      borderRadius: "6px",
                      padding: "10px",
                      background: "var(--bg-secondary)",
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
                      <div style={{ fontWeight: 700, fontSize: "0.76rem" }}>Sleeve #{index + 1}</div>
                      <button className="btn btn-secondary" type="button" onClick={() => removeSleeve(index)}>
                        Remove
                      </button>
                    </div>

                    <div
                      style={{
                        display: "grid",
                        gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))",
                        gap: "8px",
                      }}
                    >
                      <div className="form-group">
                        <label>Sleeve ID</label>
                        <input
                          type="text"
                          value={sleeve?.sleeve_id || ""}
                          onChange={(e) => handleSleeveChange(index, "sleeve_id", e.target.value)}
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
                            handleSleeveChange(index, "allocation_weight", Number(e.target.value))
                          }
                        />
                      </div>
                      <div className="form-group">
                        <label>Apply To Strategies (CSV)</label>
                        <input
                          type="text"
                          value={sleeve?.apply_to_strategies || ""}
                          onChange={(e) => handleSleeveChange(index, "apply_to_strategies", e.target.value)}
                          placeholder="momentum_flow,pullback"
                        />
                      </div>
                      <div className="form-group">
                        <label>Allowed Micro Regimes (CSV)</label>
                        <input
                          type="text"
                          value={sleeve?.allowed_micro_regimes || ""}
                          onChange={(e) => handleSleeveChange(index, "allowed_micro_regimes", e.target.value)}
                          placeholder="TRENDING_UP,BREAKOUT"
                        />
                      </div>
                      <div className="form-group">
                        <label>Blocked Micro Regimes (CSV)</label>
                        <input
                          type="text"
                          value={sleeve?.blocked_micro_regimes || ""}
                          onChange={(e) => handleSleeveChange(index, "blocked_micro_regimes", e.target.value)}
                          placeholder="CHOPPY,ABSORPTION"
                        />
                      </div>
                    </div>

                    <div
                      style={{
                        display: "grid",
                        gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))",
                        gap: "8px",
                        marginBottom: "8px",
                      }}
                    >
                      <label className="field-row">
                        <span>Enabled</span>
                        <input
                          type="checkbox"
                          checked={!!sleeve?.enabled}
                          onChange={(e) => handleSleeveChange(index, "enabled", e.target.checked)}
                        />
                      </label>
                      <label className="field-row">
                        <span>Require L2 Coverage</span>
                        <input
                          type="checkbox"
                          checked={!!sleeve?.require_l2_coverage}
                          onChange={(e) =>
                            handleSleeveChange(index, "require_l2_coverage", e.target.checked)
                          }
                        />
                      </label>
                      <label className="field-row">
                        <span>Route Enabled</span>
                        <input
                          type="checkbox"
                          checked={!!sleeve?.route_enabled}
                          onChange={(e) => handleSleeveChange(index, "route_enabled", e.target.checked)}
                        />
                      </label>
                      <label className="field-row">
                        <span>Route Requires L2</span>
                        <input
                          type="checkbox"
                          checked={!!sleeve?.route_require_l2_coverage}
                          onChange={(e) =>
                            handleSleeveChange(index, "route_require_l2_coverage", e.target.checked)
                          }
                        />
                      </label>
                      <label className="field-row">
                        <span>Fail-Fast Enabled</span>
                        <input
                          type="checkbox"
                          checked={!!sleeve?.fail_fast_exit_enabled}
                          onChange={(e) =>
                            handleSleeveChange(index, "fail_fast_exit_enabled", e.target.checked)
                          }
                        />
                      </label>
                    </div>

                    <div
                      style={{
                        display: "grid",
                        gridTemplateColumns: "repeat(auto-fit, minmax(175px, 1fr))",
                        gap: "8px",
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
                          onChange={(e) => handleSleeveChange(index, "min_flow_score", Number(e.target.value))}
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
                            handleSleeveChange(index, "min_directional_consistency", Number(e.target.value))
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
                            handleSleeveChange(index, "min_signed_aggression", Number(e.target.value))
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
                          onChange={(e) => handleSleeveChange(index, "min_imbalance", Number(e.target.value))}
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
                          onChange={(e) => handleSleeveChange(index, "min_cvd", Number(e.target.value))}
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
                            handleSleeveChange(index, "min_directional_price_change_pct", Number(e.target.value))
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
                            handleSleeveChange(index, "min_price_trend_efficiency", Number(e.target.value))
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
                            handleSleeveChange(index, "min_last_bar_body_ratio", Number(e.target.value))
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
                            handleSleeveChange(index, "min_last_bar_close_location", Number(e.target.value))
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
                            handleSleeveChange(index, "min_delta_acceleration", Number(e.target.value))
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
                            handleSleeveChange(index, "min_delta_price_divergence", Number(e.target.value))
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
                            handleSleeveChange(index, "route_flow_score_impulse", Number(e.target.value))
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
                            handleSleeveChange(index, "fail_fast_max_bars", Number(e.target.value))
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
                            handleSleeveChange(index, "fail_fast_signed_aggression_max", Number(e.target.value))
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
                            handleSleeveChange(index, "fail_fast_book_pressure_max", Number(e.target.value))
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
                            handleSleeveChange(
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

          {momentumDirty && (
            <div style={{ color: "var(--accent-yellow)", fontSize: "0.76rem" }}>
              Visual momentum editor has unsaved changes.
            </div>
          )}
        </div>

        <textarea
          value={rawConfigText}
          onChange={(e) => {
            setRawConfigText(e.target.value);
            setRawConfigDirty(true);
            setRawConfigError(null);
          }}
          style={{
            width: "100%",
            minHeight: "260px",
            fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
            fontSize: "0.75rem",
            padding: "8px",
            borderRadius: "4px",
            border: "1px solid var(--border-color)",
            backgroundColor: "var(--bg-primary)",
            color: "var(--text-primary)",
          }}
        />

        {rawConfigError && (
          <div style={{ color: "var(--accent-red)", fontSize: "0.8rem" }}>
            {rawConfigError}
          </div>
        )}

        <div style={{ display: "flex", gap: "8px" }}>
          <button className="btn btn-primary" onClick={applyRawConfig} disabled={rawConfigSaving || !rawConfigDirty}>
            {rawConfigSaving ? "Saving..." : "Apply JSON"}
          </button>
          <button className="btn btn-secondary" onClick={resetRawConfig} disabled={rawConfigSaving || momentumSaving}>
            Reset
          </button>
        </div>
      </div>
    </div>
  );
}

export default AOSOptimizations;
