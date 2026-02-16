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
  const [strategyCategory, setStrategyCategory] = useState("all");
  const [comboProfiles, setComboProfiles] = useState([]);
  const [comboActiveProfileId, setComboActiveProfileId] = useState("");
  const [comboSelectedProfileId, setComboSelectedProfileId] = useState("");
  const [comboProfileName, setComboProfileName] = useState("");
  const [comboLoading, setComboLoading] = useState(false);
  const [comboBusy, setComboBusy] = useState(false);
  const [comboError, setComboError] = useState(null);
  const [comboNotice, setComboNotice] = useState(null);

  const resolvedUrl =
    apiUrl ||
    `http://${window.location.hostname}:8001`;
  const MU_TICKER = "MU";

  const formatTimestamp = (value) => {
    if (!value) return "-";
    const parsed = Date.parse(value);
    if (Number.isNaN(parsed)) return String(value);
    return new Date(parsed).toLocaleString();
  };

  const formatFieldLabel = (field) => {
    const upperTokenMap = new Map([
      ["ma", "MA"],
      ["rr", "RR"],
      ["vwap", "VWAP"],
      ["l2", "L2"],
      ["pct", "%"],
    ]);
    return String(field || "")
      .split("_")
      .filter(Boolean)
      .map((token) => {
        const normalized = token.toLowerCase();
        if (upperTokenMap.has(normalized)) {
          return upperTokenMap.get(normalized);
        }
        return normalized.charAt(0).toUpperCase() + normalized.slice(1);
      })
      .join(" ");
  };

  const fetchStrategies = useCallback(async () => {
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
  }, [resolvedUrl]);

  const fetchStrategyCombos = useCallback(
    async (ticker) => {
      const upperTicker = String(ticker || "").toUpperCase().trim();
      if (!upperTicker) {
        setComboProfiles([]);
        setComboActiveProfileId("");
        setComboSelectedProfileId("");
        setComboError(null);
        return null;
      }
      setComboLoading(true);
      setComboError(null);
      try {
        const resp = await fetch(`/api/strategy-combos/${upperTicker}`);
        if (!resp.ok) {
          throw new Error(`HTTP ${resp.status}`);
        }
        const payload = await resp.json();
        const profiles = Array.isArray(payload?.profiles) ? payload.profiles : [];
        const activeId = String(payload?.active_profile_id || "").trim();
        setComboProfiles(profiles);
        setComboActiveProfileId(activeId);
        setComboSelectedProfileId((prev) => {
          const prevId = String(prev || "").trim();
          if (prevId && profiles.some((profile) => String(profile?.profile_id || "") === prevId)) {
            return prevId;
          }
          if (activeId) return activeId;
          const firstId = String(profiles[0]?.profile_id || "").trim();
          return firstId;
        });
        return payload;
      } catch (err) {
        console.error("Failed to load strategy combos:", err);
        setComboError(`Failed to load strategy combinations: ${err.message}`);
        setComboProfiles([]);
        setComboActiveProfileId("");
        setComboSelectedProfileId("");
        return null;
      } finally {
        setComboLoading(false);
      }
    },
    []
  );

  const captureCurrentCombo = async () => {
    const upperTicker = String(selectedTicker || "").toUpperCase().trim();
    if (!upperTicker) return;
    setComboBusy(true);
    setComboError(null);
    setComboNotice(null);
    try {
      const resp = await fetch("/api/strategy-combos/capture", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ticker: upperTicker,
          profile_name: comboProfileName || null,
          strategy_api_url: resolvedUrl,
          set_active: true,
        }),
      });
      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        throw new Error(data?.detail || `HTTP ${resp.status}`);
      }
      const payload = await resp.json();
      const capturedId = String(payload?.profile?.profile_id || "").trim();
      setComboNotice(
        capturedId
          ? `Captured combo ${capturedId} for ${upperTicker}.`
          : `Captured strategy combination for ${upperTicker}.`
      );
      if (capturedId) {
        setComboSelectedProfileId(capturedId);
      }
      await fetchStrategyCombos(upperTicker);
      window.dispatchEvent(
        new CustomEvent("strategy-combo-updated", {
          detail: { ticker: upperTicker, active_profile_id: capturedId || null },
        })
      );
    } catch (err) {
      setComboError(`Failed to capture strategy combination: ${err.message}`);
    } finally {
      setComboBusy(false);
    }
  };

  const applySelectedCombo = async () => {
    const upperTicker = String(selectedTicker || "").toUpperCase().trim();
    const profileId = String(comboSelectedProfileId || "").trim();
    if (!upperTicker || !profileId) return;
    setComboBusy(true);
    setComboError(null);
    setComboNotice(null);
    try {
      const resp = await fetch("/api/strategy-combos/apply", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ticker: upperTicker,
          profile_id: profileId,
          strategy_api_url: resolvedUrl,
          apply_now: true,
        }),
      });
      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        throw new Error(data?.detail || `HTTP ${resp.status}`);
      }
      const payload = await resp.json();
      const appliedCount = Number(payload?.apply_result?.applied_count || 0);
      const failedCount = Number(payload?.apply_result?.failed_count || 0);
      setComboNotice(
        `Applied combo ${profileId} (${appliedCount} strategies updated${failedCount ? `, ${failedCount} failed` : ""}).`
      );
      await Promise.all([fetchStrategyCombos(upperTicker), fetchStrategies()]);
      window.dispatchEvent(
        new CustomEvent("strategy-combo-updated", {
          detail: { ticker: upperTicker, active_profile_id: profileId },
        })
      );
    } catch (err) {
      setComboError(`Failed to apply strategy combination: ${err.message}`);
    } finally {
      setComboBusy(false);
    }
  };

  const toggleExpanded = (name) => {
    setExpanded((prev) => ({ ...prev, [name]: !prev[name] }));
    // initialise draft when opening
    setDrafts((prev) => ({ ...prev, [name]: prev[name] || strategies?.[name] || {} }));
  };

  const regimeOptions = useMemo(() => ["TRENDING", "CHOPPY", "MIXED"], []);
  const flowCoreSet = useMemo(
    () => new Set(["momentum_flow", "absorption_reversal", "exhaustion_fade", "scalp_l2_intrabar"]),
    []
  );
  const strategyCategoryMap = useMemo(
    () => ({
      momentum_flow: "flow",
      absorption_reversal: "flow",
      exhaustion_fade: "flow",
      iceberg_defense: "flow",
      scalp_l2_intrabar: "scalp",
    }),
    []
  );
  const resolveStrategyCategory = useCallback(
    (name) => strategyCategoryMap[name] || "other",
    [strategyCategoryMap]
  );
  const formatCategoryLabel = useCallback((categoryKey) => {
    if (categoryKey === "all") return "All";
    if (categoryKey === "flow") return "Flow";
    if (categoryKey === "scalp") return "Scalp";
    return "Other";
  }, []);

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
      scalp_l2_intrabar: {
        enabled: true,
        allowed_regimes: ["TRENDING", "CHOPPY", "MIXED"],
        min_flow_score: 48.0,
        min_signed_aggression: 0.045,
        min_directional_consistency: 0.58,
        min_imbalance: 0.03,
        min_book_pressure: 0.02,
        min_participation_ratio: 0.05,
        min_flow_score_trend_3bar: -2.0,
        min_intrabar_move_pct: 0.035,
        min_intrabar_push_ratio: 0.12,
        min_intrabar_coverage_points: 4,
        min_intrabar_directional_consistency: 0.12,
        intrabar_eval_window_seconds: 5,
        min_intrabar_window_move_pct: 0.015,
        min_intrabar_window_push_ratio: 0.08,
        min_intrabar_window_directional_consistency: 0.08,
        max_intrabar_micro_volatility_bps: 18.0,
        max_intrabar_spread_bps: 8.0,
        spread_penalty_floor_bps: 4.0,
        spread_flow_score_penalty_per_bps: 0.45,
        min_round_trip_cost_bps: 6.5,
        spread_cost_multiplier: 1.1,
        min_reward_to_cost_ratio: 1.7,
        min_flow_signal_margin: 0.01,
        max_abs_price_extension_pct: 1.8,
        require_intrabar_confirmation: false,
        no_intrabar_flow_buffer: 10.0,
        min_confidence: 55.0,
        atr_stop_multiplier: 0.66,
        min_stop_loss_pct: 0.05,
        rr_ratio: 1.35,
        trailing_stop_pct: 0.28,
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

  const enableAllStrategies = useCallback(async () => {
    if (!resolvedUrl) return;
    try {
      const resp = await fetch(`${resolvedUrl}/api/strategies`);
      if (!resp.ok) return;
      const data = await resp.json();
      const strategyNames = Object.keys(data || {});
      if (!strategyNames.length) return;

      await Promise.all(
        strategyNames.map((strategyName) =>
          fetch(`${resolvedUrl}/api/strategies/update`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              strategy_name: strategyName,
              params: { enabled: true },
            }),
          }).catch(() => null)
        )
      );
      await fetchStrategies();
    } catch (err) {
      console.error("Failed to enable all strategies:", err);
    }
  }, [resolvedUrl, fetchStrategies]);

  // Watch for ticker changes and apply presets
  useEffect(() => {
    if (!selectedTicker || !presetsLoaded) return;
    const upperTicker = String(selectedTicker || "").trim().toUpperCase();
    (async () => {
      await applyTickerPresets(upperTicker);
      if (upperTicker === MU_TICKER) {
        await enableAllStrategies();
      }
    })();
  }, [selectedTicker, presetsLoaded, applyTickerPresets, enableAllStrategies]);

  useEffect(() => {
    if (selectedTicker === "MU") {
      setShowCoreOnly(true);
    } else {
      setShowCoreOnly(false);
    }
  }, [selectedTicker]);

  useEffect(() => {
    const upperTicker = String(selectedTicker || "").toUpperCase().trim();
    if (!upperTicker) {
      setComboProfiles([]);
      setComboActiveProfileId("");
      setComboSelectedProfileId("");
      setComboProfileName("");
      setComboNotice(null);
      setComboError(null);
      return;
    }
    setComboProfileName((prev) => prev || `${upperTicker}-combo`);
    fetchStrategyCombos(upperTicker);
  }, [fetchStrategyCombos, selectedTicker]);

  useEffect(() => {
    fetchStrategies();
  }, [fetchStrategies]);

  useEffect(() => {
    const handleAdaptiveProfileUpdated = (event) => {
      const ticker = String(event?.detail?.ticker || "").toUpperCase().trim();
      const selected = String(selectedTicker || "").toUpperCase().trim();
      if (!ticker || !selected || ticker !== selected) return;
      fetchStrategies();
    };
    window.addEventListener("adaptive-profile-updated", handleAdaptiveProfileUpdated);
    return () => {
      window.removeEventListener("adaptive-profile-updated", handleAdaptiveProfileUpdated);
    };
  }, [fetchStrategies, selectedTicker]);

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
        <div key={field} style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <span className="field-label" style={{ fontWeight: 600 }}>
            Allowed Regimes
          </span>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {regimeOptions.map((opt) => {
              const checked = (drafts[name]?.allowed_regimes || value || []).includes(opt);
              return (
                <label
                  key={opt}
                  style={{ fontSize: "0.8rem", color: "var(--text-secondary)", cursor: "pointer" }}
                >
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
          <span className="field-label">{formatFieldLabel(field)}</span>
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
          <span className="field-label">{formatFieldLabel(field)}</span>
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

  const strategyFieldExclusions = useMemo(
    () =>
      new Set(["enabled", "display_name", "name", "open_positions", "total_signals", "last_signal"]),
    []
  );

  const classifyFieldGroup = (field) => {
    if (field === "allowed_regimes") return "Regime";
    if (
      /intrabar|spread_penalty|spread_cost|min_round_trip_cost|min_reward_to_cost|no_intrabar|require_intrabar/i.test(
        field
      )
    ) {
      return "Scalp Intrabar";
    }
    if (/stop|trailing|rr_ratio|risk|take_profit|time_exit/i.test(field)) {
      return "Risk And Exit";
    }
    if (
      /entry|breakout|pullback|deviation|threshold|lookback|consolidation|rotation|distance|bars_since|ma_|volume|confidence|confirm/i.test(
        field
      )
    ) {
      return "Signal Setup";
    }
    return "Other";
  };

  const groupFieldsForEdit = (name, cfg) => {
    const grouped = {
      Regime: [],
      "Scalp Intrabar": [],
      "Signal Setup": [],
      "Risk And Exit": [],
      Other: [],
    };
    Object.entries(cfg || {}).forEach(([field, value]) => {
      if (strategyFieldExclusions.has(field)) return;
      if (
        !(typeof value === "number" || typeof value === "boolean" || (field === "allowed_regimes" && Array.isArray(value)))
      ) {
        return;
      }
      const group = classifyFieldGroup(field);
      grouped[group].push([field, value]);
    });
    if (name === "scalp_l2_intrabar") {
      const scalpOrder = [
        "min_flow_score",
        "min_flow_score_trend_3bar",
        "min_signed_aggression",
        "min_directional_consistency",
        "min_imbalance",
        "min_book_pressure",
        "min_participation_ratio",
        "min_intrabar_move_pct",
        "min_intrabar_push_ratio",
        "min_intrabar_coverage_points",
        "min_intrabar_directional_consistency",
        "intrabar_eval_window_seconds",
        "min_intrabar_window_move_pct",
        "min_intrabar_window_push_ratio",
        "min_intrabar_window_directional_consistency",
        "max_intrabar_micro_volatility_bps",
        "max_intrabar_spread_bps",
        "spread_penalty_floor_bps",
        "spread_flow_score_penalty_per_bps",
        "min_round_trip_cost_bps",
        "spread_cost_multiplier",
        "min_reward_to_cost_ratio",
        "require_intrabar_confirmation",
        "no_intrabar_flow_buffer",
      ];
      const rank = new Map(scalpOrder.map((field, idx) => [field, idx]));
      Object.keys(grouped).forEach((groupKey) => {
        grouped[groupKey].sort((a, b) => {
          const rankA = rank.has(a[0]) ? rank.get(a[0]) : Number.MAX_SAFE_INTEGER;
          const rankB = rank.has(b[0]) ? rank.get(b[0]) : Number.MAX_SAFE_INTEGER;
          if (rankA !== rankB) return rankA - rankB;
          return String(a[0]).localeCompare(String(b[0]));
        });
      });
    }
    return Object.entries(grouped).filter(([, entries]) => entries.length > 0);
  };

  const strategyEntries = useMemo(() => {
    if (!strategies) {
      return [];
    }
    const sorted = Object.entries(strategies).sort((a, b) => {
      const aEnabled = a[1]?.enabled ? 1 : 0;
      const bEnabled = b[1]?.enabled ? 1 : 0;
      if (aEnabled !== bEnabled) return bEnabled - aEnabled;
      const aLabel = String(a[1]?.display_name || a[1]?.name || a[0] || "");
      const bLabel = String(b[1]?.display_name || b[1]?.name || b[0] || "");
      return aLabel.localeCompare(bLabel);
    });
    const withCoreFilter =
      selectedTicker === "MU" && showCoreOnly
        ? sorted.filter(([name]) => flowCoreSet.has(name))
        : sorted;
    if (strategyCategory === "all") {
      return withCoreFilter;
    }
    return withCoreFilter.filter(
      ([name]) => resolveStrategyCategory(name) === strategyCategory
    );
  }, [strategies, selectedTicker, showCoreOnly, flowCoreSet, strategyCategory, resolveStrategyCategory]);

  const strategySummary = useMemo(() => {
    const total = strategyEntries.length;
    const enabled = strategyEntries.filter(([, cfg]) => !!cfg?.enabled).length;
    const expandedCount = strategyEntries.filter(([name]) => !!expanded[name]).length;
    return {
      total,
      enabled,
      disabled: Math.max(0, total - enabled),
      expanded: expandedCount,
    };
  }, [strategyEntries, expanded]);

  const selectedComboProfile = useMemo(() => {
    const selectedId = String(comboSelectedProfileId || "").trim();
    if (!selectedId) return null;
    return (
      comboProfiles.find(
        (profile) => String(profile?.profile_id || "").trim() === selectedId
      ) || null
    );
  }, [comboProfiles, comboSelectedProfileId]);

  return (
    <div className="card">
      <div className="card-header">
        <span className="card-title">Strategies</span>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <select
            value={strategyCategory}
            onChange={(e) => setStrategyCategory(e.target.value)}
            style={{ minWidth: 110 }}
            title="Filter strategy category"
          >
            <option value="all">All</option>
            <option value="flow">Flow</option>
            <option value="scalp">Scalp</option>
            <option value="other">Other</option>
          </select>
          {selectedTicker === "MU" && (
            <button
              className="btn btn-secondary"
              onClick={() => setShowCoreOnly((prev) => !prev)}
              title="Show only MU flow strategies used in backtest profile"
            >
              {showCoreOnly ? "Core Only" : "Show All"}
            </button>
          )}
          <button className="btn btn-secondary" onClick={fetchStrategies} disabled={loading}>
            Refresh
          </button>
          {loading && <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>Loading...</span>}
        </div>
      </div>
      <div className="card-body" style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
        {!!selectedTicker && (
          <div className="preset-box">
            <div className="preset-header">
              <span className="preset-title">Strategy Combination Profiles ({selectedTicker})</span>
              <button
                className="btn btn-secondary"
                onClick={() => fetchStrategyCombos(selectedTicker)}
                disabled={comboLoading || comboBusy}
              >
                {comboLoading ? "Loading..." : "Reload"}
              </button>
            </div>
            <div className="preset-copy">
              Ulož aktuálne nastavenia stratégií ako kombináciu parametrov, potom ju aktivuj a použi aj v Adaptive Studiu/backteste.
            </div>

            <div className="form-group">
              <label htmlFor="combo_profile_name">New Combination Name</label>
              <input
                id="combo_profile_name"
                type="text"
                value={comboProfileName}
                onChange={(e) => setComboProfileName(e.target.value)}
                placeholder={`${selectedTicker}-combo`}
                disabled={comboBusy}
              />
            </div>

            <button
              className="btn btn-primary"
              onClick={captureCurrentCombo}
              disabled={comboBusy || comboLoading || !selectedTicker}
              style={{ width: "100%" }}
            >
              {comboBusy ? "Working..." : "Capture Current Strategy Settings"}
            </button>

            <div className="form-group">
              <label htmlFor="combo_profile_select">Saved Combinations</label>
              <select
                id="combo_profile_select"
                value={comboSelectedProfileId}
                onChange={(e) => setComboSelectedProfileId(e.target.value)}
                disabled={comboBusy || comboLoading || !comboProfiles.length}
              >
                {!comboProfiles.length && <option value="">No combinations yet</option>}
                {comboProfiles.map((profile, idx) => {
                  const profileId = String(profile?.profile_id || "");
                  const strategyCount = Object.keys(profile?.strategy_params || {}).length;
                  const activeSuffix =
                    profileId && profileId === comboActiveProfileId ? " (active)" : "";
                  return (
                    <option key={profileId || `combo-${idx}`} value={profileId}>
                      {`${profile?.profile_name || profileId} | ${strategyCount} strategies | ${formatTimestamp(profile?.updated_at || profile?.created_at)}${activeSuffix}`}
                    </option>
                  );
                })}
              </select>
            </div>

            <button
              className="btn btn-secondary"
              onClick={applySelectedCombo}
              disabled={
                comboBusy ||
                comboLoading ||
                !comboSelectedProfileId ||
                comboSelectedProfileId === comboActiveProfileId
              }
              style={{ width: "100%" }}
            >
              {comboBusy ? "Working..." : "Apply Selected Combination"}
            </button>

            <div className="preset-copy">
              Active combination: {comboActiveProfileId || "none"}
            </div>
            {selectedComboProfile && (
              <div className="preset-copy">
                Selected contains {Object.keys(selectedComboProfile.strategy_params || {}).length} strategies.
              </div>
            )}
            {comboError && (
              <div style={{ color: "var(--accent-red)", fontSize: "0.8rem" }}>
                {comboError}
              </div>
            )}
            {comboNotice && (
              <div style={{ color: "var(--accent-blue)", fontSize: "0.8rem" }}>
                {comboNotice}
              </div>
            )}
          </div>
        )}
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
        {strategySummary.total > 0 && (
          <div
            style={{
              border: "1px solid var(--border-color)",
              borderRadius: 6,
              padding: "8px 10px",
              background: "rgba(255, 255, 255, 0.65)",
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(110px, 1fr))",
              gap: 8,
              fontSize: "0.8rem",
              color: "var(--text-secondary)",
            }}
          >
            <div>
              <strong style={{ color: "var(--text-primary)" }}>{strategySummary.total}</strong> visible
            </div>
            <div>
              <strong style={{ color: "var(--text-primary)" }}>{strategySummary.enabled}</strong> enabled
            </div>
            <div>
              <strong style={{ color: "var(--text-primary)" }}>{strategySummary.disabled}</strong> disabled
            </div>
            <div>
              <strong style={{ color: "var(--text-primary)" }}>{strategySummary.expanded}</strong> open
            </div>
          </div>
        )}
        {strategies && strategyEntries.length === 0 && (
          <div style={{ color: "var(--text-muted)", fontSize: "0.85rem" }}>
            No strategies match the current filter.
          </div>
        )}
        {strategies &&
          strategyEntries.map(([name, cfg]) => {
            const displayName = cfg.display_name || cfg.name || name;
            const regimes = (cfg.allowed_regimes || cfg.regimes || []).join(", ") || "all";
            const categoryKey = resolveStrategyCategory(name);
            const warning = getStrategyWarning(name, cfg);
            const editableGroups = groupFieldsForEdit(name, cfg);
            const isExpanded = !!expanded[name];
            return (
              <div
                key={name}
                style={{
                  border: "1px solid var(--border-color)",
                  borderLeft: cfg.enabled
                    ? "3px solid var(--accent-blue)"
                    : "3px solid rgba(148, 163, 184, 0.45)",
                  borderRadius: "6px",
                  padding: "10px",
                  background: cfg.enabled ? "rgba(255, 255, 255, 0.75)" : "rgba(248, 250, 252, 0.68)",
                  display: "flex",
                  flexDirection: "column",
                  gap: 8,
                }}
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "flex-start",
                    gap: 10,
                  }}
                >
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                      <div style={{ fontWeight: 700 }}>{displayName}</div>
                      <span
                        style={{
                          fontSize: "0.72rem",
                          lineHeight: 1,
                          padding: "4px 6px",
                          borderRadius: 999,
                          background: cfg.enabled ? "rgba(37, 99, 235, 0.12)" : "rgba(148, 163, 184, 0.16)",
                          color: cfg.enabled ? "var(--accent-blue)" : "var(--text-muted)",
                          fontWeight: 600,
                        }}
                      >
                        {cfg.enabled ? "enabled" : "disabled"}
                      </span>
                      <span style={{ color: "var(--text-muted)", fontSize: "0.75rem" }}>{name}</span>
                      <span
                        style={{
                          fontSize: "0.72rem",
                          lineHeight: 1,
                          padding: "4px 6px",
                          borderRadius: 999,
                          background:
                            categoryKey === "scalp"
                              ? "rgba(14, 116, 144, 0.12)"
                              : categoryKey === "flow"
                              ? "rgba(16, 185, 129, 0.14)"
                              : "rgba(148, 163, 184, 0.18)",
                          color:
                            categoryKey === "scalp"
                              ? "#0e7490"
                              : categoryKey === "flow"
                              ? "#047857"
                              : "var(--text-muted)",
                          fontWeight: 600,
                          textTransform: "uppercase",
                        }}
                      >
                        {formatCategoryLabel(categoryKey)}
                      </span>
                    </div>
                    <div style={{ color: "var(--text-muted)", fontSize: "0.78rem", marginTop: 4 }}>
                      Regimes: {regimes}
                    </div>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <label className="switch">
                      <input
                        type="checkbox"
                        checked={cfg.enabled}
                        onChange={(e) => toggleStrategy(name, e.target.checked)}
                      />
                      <span className="slider" />
                    </label>
                    <button className="btn btn-secondary" onClick={() => toggleExpanded(name)}>
                      {isExpanded ? "Hide" : "Edit"}
                    </button>
                  </div>
                </div>

                {isExpanded && (
                  <div
                    style={{
                      borderTop: "1px solid var(--border-color)",
                      paddingTop: 10,
                      display: "flex",
                      flexDirection: "column",
                      gap: 8,
                      color: "var(--text-secondary)",
                      fontSize: "0.85rem",
                      lineHeight: 1.4,
                    }}
                  >
                    {warning && (
                      <div
                        style={{
                          color: "var(--accent-red)",
                          fontSize: "0.8rem",
                          background: "rgba(239, 68, 68, 0.08)",
                          padding: "6px 8px",
                          borderRadius: 6,
                        }}
                      >
                        Warning: {warning}
                      </div>
                    )}
                    {editableGroups.map(([groupLabel, groupFields]) => (
                      <div
                        key={groupLabel}
                        style={{
                          border: "1px solid rgba(148, 163, 184, 0.22)",
                          borderRadius: 6,
                          padding: "8px",
                          display: "flex",
                          flexDirection: "column",
                          gap: 6,
                        }}
                      >
                        <div style={{ fontSize: "0.74rem", fontWeight: 700, color: "var(--text-muted)" }}>
                          {groupLabel}
                        </div>
                        {groupFields.map(([field, value]) => renderField(name, field, value))}
                      </div>
                    ))}
                    <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 2 }}>
                      <button className="btn btn-secondary" onClick={() => handleReset(name)}>
                        Reset
                      </button>
                      {recommendedParams[name] && (
                        <button className="btn btn-secondary" onClick={() => applyRecommended(name)}>
                          Recommended
                        </button>
                      )}
                      <button className="btn btn-primary" onClick={() => saveDraft(name)}>
                        Save
                      </button>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
      </div>
    </div>
  );
}

export default StrategySettings;
