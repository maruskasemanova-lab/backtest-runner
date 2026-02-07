import { useEffect, useMemo, useState, useCallback } from "react";

function StrategySettings({ apiUrl, selectedTicker }) {
  const [strategies, setStrategies] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [expanded, setExpanded] = useState({});
  const [drafts, setDrafts] = useState({});
  const [tickerPresets, setTickerPresets] = useState({});
  const [presetsLoaded, setPresetsLoaded] = useState(false);
  const [showCoreOnly, setShowCoreOnly] = useState(true);

  const resolvedUrl =
    apiUrl ||
    `http://${window.location.hostname}:8001`;

  const fetchStrategies = async () => {
    if (!resolvedUrl) return null;
    setLoading(true);
    setError(null);
    try {
      const resp = await fetch(`${resolvedUrl}/api/strategies`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      setStrategies(data);
      return data;
    } catch (err) {
      setError(`Failed to load strategies: ${err.message}`);
      return null;
    } finally {
      setLoading(false);
    }
  };

  const toggleExpanded = (name) => {
    setExpanded((prev) => ({ ...prev, [name]: !prev[name] }));
    // initialise draft when opening
    setDrafts((prev) => ({ ...prev, [name]: prev[name] || strategies?.[name] || {} }));
  };

  const regimeOptions = useMemo(() => ["TRENDING", "CHOPPY", "MIXED"], []);
  const flowCoreSet = useMemo(
    () => new Set(["momentum_flow", "absorption_reversal", "exhaustion_fade"]),
    []
  );

  const recommendedParams = useMemo(
    () => ({
      mean_reversion: {
        entry_deviation_pct: 0.3,
        min_confidence: 60.0,
        volume_confirmation: true,
        volume_lookback: 20,
        volume_exhaustion_ratio: 0.9,
        volume_stop_pct: 0.6,
        trailing_stop_pct: 0.3,
        allowed_regimes: ["CHOPPY", "MIXED"],
      },
      momentum: {
        consolidation_bars: 10,
        volume_threshold: 1.5,
        volume_lookback: 20,
        consolidation_range_pct: 0.6,
        breakout_pct: 0.15,
        volume_stop_pct: 0.8,
        rr_ratio: 2.5,
        trailing_stop_pct: 1.5,
        allowed_regimes: ["TRENDING"],
      },
      pullback: {
        pullback_threshold_pct: 0.5,
        ma_fast_period: 50,
        ma_slow_period: 100,
        volume_lookback: 20,
        volume_surge_ratio: 1.2,
        volume_stop_pct: 1.0,
        rr_ratio: 1.5,
        trailing_stop_pct: 1.0,
        allowed_regimes: ["TRENDING"],
      },
      rotation: {
        lookback_period: 10,
        rotation_threshold: 0.5,
        volume_lookback: 10,
        volume_increase_ratio: 1.05,
        volume_stop_pct: 0.9,
        trailing_stop_pct: 1.0,
        allowed_regimes: ["MIXED", "CHOPPY"],
      },
      vwap_magnet: {
        min_distance_pct: 0.4,
        max_distance_pct: 3.0,
        bars_since_vwap_threshold: 5,
        volume_confirm: true,
        volume_lookback: 20,
        volume_stop_pct: 0.7,
        trailing_stop_pct: 0.4,
        allowed_regimes: ["TRENDING", "CHOPPY", "MIXED"],
      },
    }),
    []
  );

  // Fetch all ticker presets on mount
  useEffect(() => {
    const fetchPresets = async () => {
      try {
        const resp = await fetch(`http://${window.location.hostname}:8002/api/strategy-overrides`);
        if (resp.ok) {
          const data = await resp.json();
          setTickerPresets(data);
          setPresetsLoaded(true);
        }
      } catch (err) {
        console.error("Failed to load ticker presets:", err);
      }
    };
    fetchPresets();
  }, []);

  // Apply ticker-specific presets when ticker changes
  const applyTickerPresets = useCallback(async (ticker) => {
    if (!ticker || !presetsLoaded) return;
    
    const presets = tickerPresets[ticker];
    if (!presets) return;
    
    console.log(`Applying presets for ${ticker}:`, presets);
    
    for (const [stratName, params] of Object.entries(presets)) {
      try {
        const resp = await fetch(`${resolvedUrl}/api/strategies/update`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ strategy_name: stratName, params }),
        });
        if (resp.ok) {
          const data = await resp.json();
          setStrategies((prev) =>
            prev ? { ...prev, [stratName]: data.current } : prev
          );
          setDrafts((prev) => ({ ...prev, [stratName]: data.current }));
        }
      } catch (err) {
        console.error(`Failed to apply preset for ${stratName}:`, err);
      }
    }
  }, [resolvedUrl, presetsLoaded, tickerPresets]);

  // Watch for ticker changes and apply presets
  useEffect(() => {
    if (selectedTicker && presetsLoaded) {
      applyTickerPresets(selectedTicker);
    }
  }, [selectedTicker, presetsLoaded, applyTickerPresets]);

  useEffect(() => {
    if (selectedTicker === "MU") {
      setShowCoreOnly(true);
    } else {
      setShowCoreOnly(false);
    }
  }, [selectedTicker]);

  useEffect(() => {
    fetchStrategies();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resolvedUrl]);

  const toggleStrategy = async (name, enabled) => {
    try {
      setStrategies((prev) =>
        prev
          ? {
              ...prev,
              [name]: { ...prev[name], enabled },
            }
          : prev
      );
      const resp = await fetch(`${resolvedUrl}/api/strategies/toggle`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ strategy_name: name, enabled }),
      });
      if (!resp.ok) {
        throw new Error(`Toggle failed: ${resp.status}`);
      }
    } catch (err) {
      setError(err.message);
      fetchStrategies();
    }
  };

  const saveDraft = async (name) => {
    const draft = drafts[name];
    if (!draft) return;
    try {
      const params = { ...draft };
      delete params.enabled;
      delete params.name;
      delete params.display_name;
      const resp = await fetch(`${resolvedUrl}/api/strategies/update`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ strategy_name: name, params }),
      });
      if (!resp.ok) throw new Error(`Update failed: ${resp.status}`);
      const data = await resp.json();
      setStrategies((prev) =>
        prev ? { ...prev, [name]: data.current } : prev
      );
      setDrafts((prev) => ({ ...prev, [name]: data.current }));
    } catch (err) {
      setError(err.message);
      fetchStrategies();
    }
  };

  const updateDraftField = (name, field, value) => {
    setDrafts((prev) => ({
      ...prev,
      [name]: { ...(prev[name] || {}), [field]: value },
    }));
  };

  const renderField = (name, field, value) => {
    // Editable numeric or boolean fields; allowed_regimes multi-select
    if (field === "allowed_regimes" && Array.isArray(value)) {
      return (
        <div className="field-row" key={field}>
          <span className="field-label">Allowed Regimes</span>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            {regimeOptions.map((opt) => {
              const checked = (drafts[name]?.allowed_regimes || value || []).includes(opt);
              return (
                <label key={opt} style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={(e) => {
                      const current = new Set(drafts[name]?.allowed_regimes || value || []);
                      e.target.checked ? current.add(opt) : current.delete(opt);
                      updateDraftField(name, "allowed_regimes", Array.from(current));
                    }}
                    style={{ marginRight: 4 }}
                  />
                  {opt}
                </label>
              );
            })}
          </div>
        </div>
      );
    }

    if (typeof value === "number") {
      return (
        <div className="field-row" key={field}>
          <span className="field-label">{field.replace(/_/g, " ")}</span>
          <input
            type="number"
            step="0.01"
            value={drafts[name]?.[field] ?? value}
            onChange={(e) => updateDraftField(name, field, Number(e.target.value))}
            className="field-input"
          />
        </div>
      );
    }

    if (typeof value === "boolean") {
      return (
        <div className="field-row" key={field}>
          <span className="field-label">{field.replace(/_/g, " ")}</span>
          <input
            type="checkbox"
            checked={drafts[name]?.[field] ?? value}
            onChange={(e) => updateDraftField(name, field, e.target.checked)}
          />
        </div>
      );
    }

    return null;
  };

  const handleReset = async (name) => {
    // Re-fetch to ensure we pull the latest values from the server, then reset draft.
    const fresh = await fetchStrategies();
    const latest = fresh?.[name] || strategies?.[name] || {};
    setDrafts((prev) => ({
      ...prev,
      [name]: latest,
    }));
  };

  const applyRecommended = async (name) => {
    const recommended = recommendedParams[name];
    if (!recommended) return;
    try {
      const resp = await fetch(`${resolvedUrl}/api/strategies/update`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ strategy_name: name, params: recommended }),
      });
      if (!resp.ok) throw new Error(`Update failed: ${resp.status}`);
      const data = await resp.json();
      setStrategies((prev) =>
        prev ? { ...prev, [name]: data.current } : prev
      );
      setDrafts((prev) => ({ ...prev, [name]: data.current }));
    } catch (err) {
      setError(err.message);
      fetchStrategies();
    }
  };

  const getStrategyWarning = (name, cfg) => {
    if (name !== "mean_reversion") return null;
    const deviation = cfg.entry_deviation_pct;
    if (typeof deviation === "number" && deviation > 2) {
      return "Deviation is very high; signals will likely never trigger.";
    }
    return null;
  };

  const strategyEntries = useMemo(() => {
    if (!strategies) {
      return [];
    }
    const entries = Object.entries(strategies);
    if (selectedTicker === "MU" && showCoreOnly) {
      return entries.filter(([name]) => flowCoreSet.has(name));
    }
    return entries;
  }, [strategies, selectedTicker, showCoreOnly, flowCoreSet]);

  return (
    <div className="card">
      <div className="card-header">
        <span className="card-title">Strategies</span>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          {selectedTicker === "MU" && (
            <button
              className="btn btn-secondary"
              onClick={() => setShowCoreOnly((prev) => !prev)}
              title="Show only MU flow strategies used in backtest profile"
            >
              {showCoreOnly ? "Core Flow" : "All"}
            </button>
          )}
          <button className="btn btn-secondary" onClick={fetchStrategies} disabled={loading}>
            ↻
          </button>
          {loading && <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>Loading…</span>}
        </div>
      </div>
      <div className="card-body" style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
        {error && (
          <div style={{ color: "var(--accent-red)", fontSize: "0.85rem" }}>{error}</div>
        )}
        {!strategies && !error && !loading && (
          <div style={{ color: "var(--text-muted)", fontSize: "0.9rem" }}>No data</div>
        )}
        {selectedTicker === "MU" && showCoreOnly && (
          <div style={{ color: "var(--text-muted)", fontSize: "0.8rem" }}>
            Showing only MU flow strategies used by current backtest profile.
          </div>
        )}
        {strategies &&
          strategyEntries.map(([name, cfg]) => (
            <div
              key={name}
              style={{
                border: "1px solid var(--border-color)",
                borderRadius: "6px",
                padding: "8px",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
              }}
            >
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 600 }}>{cfg.display_name || cfg.name || name}</div>
                <div style={{ color: "var(--text-muted)", fontSize: "0.8rem" }}>
                  Regimes: {(cfg.allowed_regimes || cfg.regimes || []).join(", ") || "all"}
                </div>
                {expanded[name] && (
                  <div style={{ marginTop: 8, color: "var(--text-secondary)", fontSize: "0.85rem", lineHeight: 1.4, display: "flex", flexDirection: "column", gap: 6 }}>
                    {getStrategyWarning(name, cfg) && (
                      <div style={{ color: "var(--accent-red)", fontSize: "0.8rem", background: "rgba(239, 68, 68, 0.08)", padding: "6px 8px", borderRadius: 6 }}>
                        ⚠ {getStrategyWarning(name, cfg)}
                      </div>
                    )}
                    {Object.entries(cfg)
                      .filter(([k, v]) => !["enabled", "display_name", "name", "open_positions", "total_signals", "last_signal"].includes(k))
                      .map(([k, v]) => renderField(name, k, v))}
                    <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 8 }}>
                      <button className="btn btn-secondary" onClick={() => handleReset(name)}>Reset (server)</button>
                      {recommendedParams[name] && (
                        <button className="btn btn-secondary" onClick={() => applyRecommended(name)}>
                          Recommended
                        </button>
                      )}
                      <button className="btn btn-primary" onClick={() => saveDraft(name)}>Save</button>
                    </div>
                  </div>
                )}
              </div>
              <label className="switch">
                <input
                  type="checkbox"
                  checked={cfg.enabled}
                  onChange={(e) => toggleStrategy(name, e.target.checked)}
                />
                <span className="slider" />
              </label>
              <button
                className="btn btn-secondary"
                style={{ marginLeft: 8 }}
                onClick={() => toggleExpanded(name)}
              >
                {expanded[name] ? "▲" : "▼"}
              </button>
            </div>
          ))}
      </div>
    </div>
  );
}

export default StrategySettings;
