import { useCallback, useEffect, useMemo, useState } from "react";

const DEFAULT_FORM = {
  ticker: "",
  date_from: "",
  date_to: "",
  method: "grid",
  adaptive_version: 1,
  n_trials: 16,
  score_metric: "pnl_pct",
  seed: 42,
  persist_best: false,
  l2_required: true,
  l2_only: false,
  quick_mode: false,
  quick_max_days: 2,
  quick_trial_boost: 3,
  selection_modes: "adaptive_top_n,all_enabled",
  max_active_options: "1,2,3,4,5",
  min_active_bars_options: "0,2,4,8,12",
  switch_cooldown_bars_options: "0,1,2,4,8",
  flow_bias_options: "true,false",
  ohlcv_fallback_options: "true,false",
  // V2 fields
  v2_strategy_sets: "",
  v2_l2_min_imbalance: "0.05,0.12,0.25",
  v2_l2_min_delta: "",
  v2_regime_filter_sets: "",
  v2_base_threshold: "45,55,65",
  v2_min_confirming_sources: "2,3",
  // Per-strategy param tuning (v2)
  v2_min_confidence: "50,55,60,65",
  v2_atr_stop_multiplier: "0.7,1.0,1.3,1.8",
  v2_rr_ratio: "1.5,2.0,2.5,3.0",
  // Time-of-day window (v2)
  v2_time_windows: "9,10;9,10,11,12;9,10,11,12,13,14,15",
  // Flow exit thresholds (v2)
  v2_adverse_flow_consistency: "0.35,0.45,0.55",
  v2_adverse_book_pressure: "0.10,0.15,0.22",
  // Exit params (v2)
  v2_time_exit_bars: "15,25,35,50",
  v2_trailing_stop_pct: "0.4,0.6,0.8,1.0,1.3",
  neighborhood_search: true,
};

const parseIntCsv = (value, { min = 0, max = 1000 } = {}) => {
  const source = String(value || "").trim();
  if (!source) return null;
  const out = [];
  const seen = new Set();
  source
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
    .forEach((token) => {
      const parsed = Number(token);
      if (!Number.isFinite(parsed) || !Number.isInteger(parsed)) {
        throw new Error(`Invalid integer list value: ${token}`);
      }
      const clamped = Math.max(min, Math.min(max, parsed));
      if (seen.has(clamped)) return;
      seen.add(clamped);
      out.push(clamped);
    });
  return out.length ? out : null;
};

const parseFloatCsv = (value, { min = 0, max = 1000 } = {}) => {
  const source = String(value || "").trim();
  if (!source) return null;
  const out = [];
  const seen = new Set();
  source
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
    .forEach((token) => {
      const parsed = Number(token);
      if (!Number.isFinite(parsed)) {
        throw new Error(`Invalid float list value: ${token}`);
      }
      const clamped = Math.max(min, Math.min(max, parsed));
      const rounded = Math.round(clamped * 10000) / 10000;
      if (seen.has(rounded)) return;
      seen.add(rounded);
      out.push(rounded);
    });
  return out.length ? out : null;
};

const parseBoolCsv = (value) => {
  const source = String(value || "").trim();
  if (!source) return null;
  const out = [];
  const seen = new Set();
  source
    .split(",")
    .map((item) => item.trim().toLowerCase())
    .filter(Boolean)
    .forEach((token) => {
      let current;
      if (["true", "1", "yes", "on"].includes(token)) {
        current = true;
      } else if (["false", "0", "no", "off"].includes(token)) {
        current = false;
      } else {
        throw new Error(`Invalid boolean list value: ${token}`);
      }
      if (seen.has(current)) return;
      seen.add(current);
      out.push(current);
    });
  return out.length ? out : null;
};

const parseModeCsv = (value) => {
  const source = String(value || "").trim();
  if (!source) return null;
  const out = [];
  const seen = new Set();
  source
    .split(",")
    .map((item) => item.trim().toLowerCase())
    .filter(Boolean)
    .forEach((token) => {
      const current = token === "all_enabled" ? "all_enabled" : "adaptive_top_n";
      if (seen.has(current)) return;
      seen.add(current);
      out.push(current);
    });
  return out.length ? out : null;
};

/**
 * Parse strategy sets from semicolon-delimited groups where each group is
 * comma-delimited strategies. E.g.: "momentum_flow,absorption_reversal;pullback"
 * → [["momentum_flow","absorption_reversal"], ["pullback"]]
 */
const parseStrategySets = (value) => {
  const source = String(value || "").trim();
  if (!source) return null;
  const sets = source
    .split(";")
    .map((group) =>
      group
        .split(",")
        .map((s) => s.trim().toLowerCase())
        .filter(Boolean)
    )
    .filter((group) => group.length > 0);
  return sets.length > 0 ? sets : null;
};

/**
 * Parse regime filter sets from semicolon-delimited groups. E.g.:
 * "TRENDING;TRENDING,MIXED;TRENDING,MIXED,CHOPPY"
 * → [["TRENDING"], ["TRENDING","MIXED"], ["TRENDING","MIXED","CHOPPY"]]
 */
const parseRegimeFilterSets = (value) => {
  const source = String(value || "").trim();
  if (!source) return null;
  const valid = new Set(["TRENDING", "CHOPPY", "MIXED"]);
  const sets = source
    .split(";")
    .map((group) =>
      group
        .split(",")
        .map((s) => s.trim().toUpperCase())
        .filter((s) => valid.has(s))
    )
    .filter((group) => group.length > 0);
  return sets.length > 0 ? sets : null;
};

const formatCandidate = (candidate) => {
  if (!candidate || typeof candidate !== "object") return "-";
  const mode = candidate.strategy_selection_mode || "adaptive_top_n";
  return `${mode} | top=${candidate.max_active_strategies} | hysteresis=${candidate.min_active_bars_before_switch} | cooldown=${candidate.switch_cooldown_bars} | flowBias=${candidate.flow_bias_enabled ? "on" : "off"} | fallback=${candidate.use_ohlcv_fallbacks ? "on" : "off"}`;
};

const formatV2Candidate = (candidate) => {
  if (!candidate || typeof candidate !== "object") return "-";
  const parts = [];
  const strategies = candidate.enabled_strategies;
  if (Array.isArray(strategies) && strategies.length) {
    parts.push(strategies.join("+"));
  }
  const regime = candidate.regime_filter;
  if (Array.isArray(regime) && regime.length) {
    parts.push(`regime:${regime.join(",")}`);
  }
  if (candidate.l2_min_imbalance != null) {
    parts.push(`imb:${Number(candidate.l2_min_imbalance).toFixed(3)}`);
  }
  if (candidate.base_threshold != null) {
    parts.push(`thr:${candidate.base_threshold}`);
  }
  if (candidate.min_confirming_sources != null) {
    parts.push(`src:${candidate.min_confirming_sources}`);
  }
  return parts.length ? parts.join(" | ") : formatCandidate(candidate);
};

const formatRange = (range) => {
  if (!range || !range.start || !range.end) return "-";
  return `${range.start} -> ${range.end} (${Number(range.total_days || 0)} days)`;
};

const formatTimestamp = (value) => {
  if (!value) return "-";
  const parsed = Date.parse(value);
  if (Number.isNaN(parsed)) return String(value);
  return new Date(parsed).toLocaleString();
};

// ------- Vector Analysis Visualization Helpers -------

function DimensionImportanceBars({ importance }) {
  if (!importance || typeof importance !== "object") return null;
  const entries = Object.entries(importance).sort((a, b) => b[1] - a[1]);
  if (!entries.length) return null;
  const maxVal = Math.max(...entries.map(([, v]) => v), 0.01);

  return (
    <div className="vector-importance-bars">
      {entries.map(([dim, val]) => (
        <div className="vector-bar-row" key={dim}>
          <span className="vector-bar-label">{dim}</span>
          <div className="vector-bar-track">
            <div
              className="vector-bar-fill"
              style={{ width: `${Math.min(100, (val / maxVal) * 100)}%` }}
            />
          </div>
          <span className="vector-bar-value">{(val * 100).toFixed(1)}%</span>
        </div>
      ))}
    </div>
  );
}

function InteractionsList({ interactions }) {
  if (!Array.isArray(interactions) || !interactions.length) return null;
  return (
    <div className="vector-interactions-list">
      {interactions.slice(0, 8).map((ix, idx) => (
        <div className="vector-interaction-item" key={idx}>
          <span className="interaction-dims">{ix.dimensions || ix.pair || "?"}</span>
          <span className="interaction-effect">
            Δ={Number(ix.effect ?? ix.delta ?? 0).toFixed(4)}
          </span>
          {ix.count != null && (
            <span className="interaction-count">n={ix.count}</span>
          )}
        </div>
      ))}
    </div>
  );
}

function SurprisingVectorsTable({ vectors }) {
  if (!Array.isArray(vectors) || !vectors.length) return null;
  return (
    <div className="vector-surprising-table-wrap">
      <table className="vector-surprising-table">
        <thead>
          <tr>
            <th>Vector</th>
            <th>Score</th>
            <th>z-score</th>
            <th>Trades</th>
          </tr>
        </thead>
        <tbody>
          {vectors.slice(0, 10).map((v, idx) => (
            <tr key={idx}>
              <td>{v.label || v.key || JSON.stringify(v.candidate || {})}</td>
              <td>{Number(v.score ?? 0).toFixed(4)}</td>
              <td className={Number(v.z_score ?? 0) > 1.5 ? "z-high" : ""}>
                {Number(v.z_score ?? 0).toFixed(2)}σ
              </td>
              <td>{Number(v.trades ?? v.trade_count ?? 0)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ------- Main Component -------

function AdaptiveTuner({ selectedTicker, onTickerChange, strategyApiUrl }) {
  const [availableData, setAvailableData] = useState(null);
  const [form, setForm] = useState(DEFAULT_FORM);
  const [tickerOptions, setTickerOptions] = useState(null);
  const [loadingTickerOptions, setLoadingTickerOptions] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [applyingProfileId, setApplyingProfileId] = useState(null);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [activeJobId, setActiveJobId] = useState(null);
  const [job, setJob] = useState(null);
  const [selectedTrialIndex, setSelectedTrialIndex] = useState(null);

  const isV2 = Number(form.adaptive_version) === 2;

  const refreshTickerOptions = useCallback(async (ticker, { forceDates = false } = {}) => {
    const upper = String(ticker || "").toUpperCase().trim();
    if (!upper) return;

    setLoadingTickerOptions(true);
    try {
      const resp = await fetch(`/api/adaptive-tuner/options/${upper}`);
      if (!resp.ok) {
        throw new Error(`Failed to load tuner options for ${upper}`);
      }
      const payload = await resp.json();
      setTickerOptions(payload);

      setForm((prev) => {
        const hasDates = !!prev.date_from && !!prev.date_to;
        const nextFrom = payload?.default_date_from || prev.date_from;
        const nextTo = payload?.default_date_to || prev.date_to;
        return {
          ...prev,
          ticker: upper,
          date_from: forceDates || !hasDates ? nextFrom : prev.date_from,
          date_to: forceDates || !hasDates ? nextTo : prev.date_to,
        };
      });
    } catch (err) {
      setError(err.message || String(err));
    } finally {
      setLoadingTickerOptions(false);
    }
  }, []);

  useEffect(() => {
    const loadAvailableData = async () => {
      try {
        const resp = await fetch("/api/available-data");
        if (!resp.ok) return;
        const payload = await resp.json();
        setAvailableData(payload);

        const tickers = Array.isArray(payload?.tickers)
          ? payload.tickers.map((ticker) => String(ticker).toUpperCase())
          : [];
        if (!tickers.length) return;

        const fallbackTicker = selectedTicker || (tickers.includes("MU") ? "MU" : tickers[0]);
        setForm((prev) => ({ ...prev, ticker: fallbackTicker }));
        await refreshTickerOptions(fallbackTicker, { forceDates: true });

        if (!selectedTicker && onTickerChange) {
          onTickerChange(fallbackTicker);
        }
      } catch (err) {
        console.error("Failed to load available data for tuner:", err);
      }
    };

    loadAvailableData();
  }, [onTickerChange, refreshTickerOptions, selectedTicker]);

  useEffect(() => {
    if (!selectedTicker) return;
    const upper = String(selectedTicker).toUpperCase();
    if (upper === String(form.ticker || "").toUpperCase()) return;
    setForm((prev) => ({ ...prev, ticker: upper }));
    refreshTickerOptions(upper, { forceDates: true });
  }, [form.ticker, refreshTickerOptions, selectedTicker]);

  useEffect(() => {
    if (!activeJobId) return undefined;

    let cancelled = false;
    const poll = async () => {
      try {
        const resp = await fetch(`/api/adaptive-tuner/${activeJobId}`);
        if (!resp.ok) {
          if (!cancelled) {
            setError(`Failed to fetch tuner job ${activeJobId}`);
          }
          return;
        }
        const payload = await resp.json();
        if (cancelled) return;
        setJob(payload);

        const status = String(payload?.status || "").toLowerCase();
        if (status === "completed") {
          setNotice("Adaptive tuning finished.");
          setSubmitting(false);
          setActiveJobId(null);
          const bestIndex = payload?.best_trial?.trial_index;
          if (Number.isFinite(bestIndex)) {
            setSelectedTrialIndex(bestIndex);
          }
          await refreshTickerOptions(form.ticker, { forceDates: false });
        } else if (status === "failed") {
          setSubmitting(false);
          setActiveJobId(null);
          setError(payload?.error || "Adaptive tuning failed.");
        }
      } catch (err) {
        if (!cancelled) {
          setError(`Tuner poll error: ${err.message}`);
          setSubmitting(false);
          setActiveJobId(null);
        }
      }
    };

    poll();
    const interval = setInterval(poll, 1000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [activeJobId, form.ticker, refreshTickerOptions]);

  const sortedTrials = useMemo(() => {
    const trials = Array.isArray(job?.trials) ? [...job.trials] : [];
    trials.sort((a, b) => Number(b?.score || 0) - Number(a?.score || 0));
    return trials;
  }, [job]);

  const selectedTrial = useMemo(() => {
    if (!Array.isArray(job?.trials) || !job.trials.length) return null;
    if (selectedTrialIndex === null || selectedTrialIndex === undefined) {
      return job?.best_trial || job.trials[0];
    }
    return job.trials.find((trial) => trial?.trial_index === selectedTrialIndex) || null;
  }, [job, selectedTrialIndex]);

  const progressPct = useMemo(() => {
    const completed = Number(job?.progress?.completed_trials || 0);
    const total = Number(job?.progress?.total_trials || 0);
    if (total <= 0) return 0;
    return Math.max(0, Math.min(100, (completed / total) * 100));
  }, [job]);

  const effectiveTrialBudgetPreview = useMemo(() => {
    const requested = Math.max(1, Number(form.n_trials || (isV2 ? 32 : 16)));
    const boost = form.quick_mode
      ? Math.max(1, Number(form.quick_trial_boost || 3))
      : 1;
    return {
      requested,
      boost,
      effective: Math.min(400, requested * boost),
    };
  }, [form.n_trials, form.quick_mode, form.quick_trial_boost, isV2]);

  const profileList = useMemo(() => {
    return Array.isArray(tickerOptions?.profiles) ? tickerOptions.profiles : [];
  }, [tickerOptions]);

  const jobVersion = Number(job?.adaptive_version || job?.request?.adaptive_version || form.adaptive_version || 1);
  const jobQuickMode = Boolean(job?.quick_mode || job?.summary?.quick_mode);
  const jobTrialBudget = job?.trial_budget;
  const vectorAnalysis = job?.vector_analysis || null;

  const handleStart = async () => {
    setSubmitting(true);
    setError(null);
    setNotice(null);
    setJob(null);
    setSelectedTrialIndex(null);

    try {
      if (!form.ticker) {
        throw new Error("Ticker is required.");
      }
      if (!form.date_from || !form.date_to) {
        throw new Error("Date range is required.");
      }

      const version = Number(form.adaptive_version || 1);

      const payload = {
        ticker: form.ticker,
        date_from: form.date_from,
        date_to: form.date_to,
        strategy_api_url: strategyApiUrl || `http://${window.location.hostname}:8001`,
        method: version === 2 ? (form.method === "grid" ? "random" : form.method) : form.method,
        adaptive_version: version,
        n_trials: Number(form.n_trials || (version === 2 ? 32 : 16)),
        score_metric: form.score_metric,
        seed: Number(form.seed || 42),
        persist_best: !!form.persist_best,
        l2_required: !!form.l2_required,
        l2_confirm_enabled: true,
        l2_only: !!form.l2_only,
        quick_mode: !!form.quick_mode,
        quick_max_days: Math.max(1, Math.min(30, Number(form.quick_max_days || 2))),
        quick_trial_boost: Math.max(1, Math.min(10, Number(form.quick_trial_boost || 3))),
      };

      if (version === 1) {
        // V1 fields
        payload.selection_modes = parseModeCsv(form.selection_modes);
        payload.max_active_options = parseIntCsv(form.max_active_options, { min: 1, max: 20 });
        payload.min_active_bars_options = parseIntCsv(form.min_active_bars_options, { min: 0, max: 500 });
        payload.switch_cooldown_bars_options = parseIntCsv(form.switch_cooldown_bars_options, { min: 0, max: 500 });
        payload.flow_bias_options = parseBoolCsv(form.flow_bias_options);
        payload.ohlcv_fallback_options = parseBoolCsv(form.ohlcv_fallback_options);
      } else {
        // V2 fields
        const strategySets = parseStrategySets(form.v2_strategy_sets);
        if (strategySets) payload.strategy_sets = strategySets;

        const l2Imb = parseFloatCsv(form.v2_l2_min_imbalance, { min: 0, max: 1 });
        if (l2Imb) payload.l2_min_imbalance_options = l2Imb;

        const l2Delta = parseFloatCsv(form.v2_l2_min_delta, { min: 0, max: 10000 });
        if (l2Delta) payload.l2_min_delta_options = l2Delta;

        const regimeSets = parseRegimeFilterSets(form.v2_regime_filter_sets);
        if (regimeSets) payload.regime_filter_sets = regimeSets;

        const baseThr = parseIntCsv(form.v2_base_threshold, { min: 0, max: 100 });
        if (baseThr) payload.base_threshold_options = baseThr;

        const minSrc = parseIntCsv(form.v2_min_confirming_sources, { min: 1, max: 10 });
        if (minSrc) payload.min_confirming_sources_options = minSrc;

        const minConf = parseFloatCsv(form.v2_min_confidence, { min: 30, max: 90 });
        if (minConf) payload.min_confidence_options = minConf;

        const atrStop = parseFloatCsv(form.v2_atr_stop_multiplier, { min: 0.3, max: 4 });
        if (atrStop) payload.atr_stop_multiplier_options = atrStop;

        const rrRatio = parseFloatCsv(form.v2_rr_ratio, { min: 1, max: 5 });
        if (rrRatio) payload.rr_ratio_options = rrRatio;

        // Time-of-day windows (semicolon-separated sets of hour ints)
        const rawTW = String(form.v2_time_windows || "").trim();
        if (rawTW) {
          const twSets = rawTW.split(";").map((s) => {
            const hours = s.split(",").map((h) => parseInt(h.trim(), 10)).filter((h) => !isNaN(h) && h >= 0 && h <= 23);
            return hours;
          }).filter((h) => h.length > 0);
          if (twSets.length) payload.time_window_sets = twSets;
        }

        // Flow exit thresholds
        const afConsistency = parseFloatCsv(form.v2_adverse_flow_consistency, { min: 0.1, max: 0.9 });
        if (afConsistency) payload.adverse_flow_consistency_options = afConsistency;
        const abPressure = parseFloatCsv(form.v2_adverse_book_pressure, { min: 0.05, max: 0.5 });
        if (abPressure) payload.adverse_book_pressure_options = abPressure;

        // Exit param dims
        const teBarsParsed = parseIntCsv(form.v2_time_exit_bars, { min: 5, max: 120 });
        if (teBarsParsed) payload.time_exit_bars_options = teBarsParsed;
        const tsPctParsed = parseFloatCsv(form.v2_trailing_stop_pct, { min: 0.1, max: 3.0 });
        if (tsPctParsed) payload.trailing_stop_pct_options = tsPctParsed;

        // Neighborhood search toggle
        if (form.neighborhood_search) {
          payload.neighborhood_search = true;
        }

        // Also include v1 fields as base
        payload.selection_modes = parseModeCsv(form.selection_modes);
        payload.max_active_options = parseIntCsv(form.max_active_options, { min: 1, max: 20 });
      }

      const resp = await fetch("/api/adaptive-tuner/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        throw new Error(data?.detail || `HTTP ${resp.status}`);
      }
      const data = await resp.json();
      setActiveJobId(data.job_id);
      setNotice(
        `Adaptive tuner v${version} job queued: ${data.job_id} (${data.effective_days || 0} effective days)`
      );
    } catch (err) {
      setSubmitting(false);
      setError(err.message || String(err));
    }
  };

  const handleApplyProfile = async (profileId) => {
    if (!form.ticker || !profileId) return;
    setApplyingProfileId(profileId);
    setError(null);
    setNotice(null);
    try {
      const resp = await fetch("/api/adaptive-tuner/profiles/apply", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ticker: form.ticker, profile_id: profileId }),
      });
      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        throw new Error(data?.detail || `HTTP ${resp.status}`);
      }
      setNotice(
        `Applied adaptive profile ${profileId} for ${form.ticker}. It will be used on next Backtest run start.`
      );
      await refreshTickerOptions(form.ticker, { forceDates: false });
    } catch (err) {
      setError(err.message || String(err));
    } finally {
      setApplyingProfileId(null);
    }
  };

  const handleTickerChange = async (ticker) => {
    const upper = String(ticker || "").toUpperCase();
    setForm((prev) => ({ ...prev, ticker: upper }));
    await refreshTickerOptions(upper, { forceDates: true });
    if (onTickerChange) {
      onTickerChange(upper);
    }
  };

  const tickerOptionsList = Array.isArray(availableData?.tickers)
    ? availableData.tickers.map((ticker) => String(ticker).toUpperCase())
    : [];

  const bestTrial = job?.best_trial;

  return (
    <main className="adaptive-tuner-page">
      <section className="card adaptive-tuner-card">
        <div className="card-header">
          <span className="card-title">
            Adaptive Tuner {isV2 ? "(v2 Vector Discovery)" : "(L2-Aware)"}
          </span>
          <button className="btn btn-primary" onClick={handleStart} disabled={submitting}>
            {submitting ? "Running..." : "Start Tuning"}
          </button>
        </div>

        <div className="card-body adaptive-tuner-layout">
          <div className="adaptive-tuner-form-col">
            <div className="adaptive-info-box">
              {isV2 ? (
                <>
                  Vector Discovery mode <strong>v2</strong>: searches across strategy×L2×regime×evidence dimensions.
                  Grid search is not available — use Random or Optuna.
                </>
              ) : (
                <>
                  Tuning targets Adaptive Studio <strong>Version 1</strong>. Ticker options are based on
                  real data coverage from your catalog, including OHLCV and L2 overlap.
                </>
              )}
            </div>

            {error && <div className="adaptive-error">{error}</div>}
            {notice && <div className="adaptive-notice">{notice}</div>}

            <div className="adaptive-section">
              <h3>Real Data Coverage</h3>
              <div className="adaptive-preview-list">
                <div className="adaptive-preview-item">
                  <span>OHLCV coverage</span>
                  <strong>{formatRange(tickerOptions?.ohlcv_range)}</strong>
                </div>
                <div className="adaptive-preview-item">
                  <span>L2 coverage (mbp-10)</span>
                  <strong>{formatRange(tickerOptions?.l2_range)}</strong>
                </div>
                <div className="adaptive-preview-item">
                  <span>OHLCV -&gt; L2 overlap (tunable)</span>
                  <strong>{formatRange(tickerOptions?.l2_overlap_range)}</strong>
                </div>
              </div>
              {loadingTickerOptions && <div className="adaptive-empty">Loading ticker coverage...</div>}
            </div>

            <div className="adaptive-section">
              <h3>Run Setup</h3>
              <div className="form-group">
                <label htmlFor="tuner_ticker">Ticker</label>
                <select
                  id="tuner_ticker"
                  value={form.ticker}
                  onChange={(e) => handleTickerChange(e.target.value)}
                >
                  {tickerOptionsList.map((ticker) => (
                    <option key={ticker} value={ticker}>
                      {ticker}
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label htmlFor="tuner_version">Adaptive Version</label>
                <select
                  id="tuner_version"
                  value={form.adaptive_version}
                  onChange={(e) => {
                    const ver = Number(e.target.value);
                    setForm((prev) => ({
                      ...prev,
                      adaptive_version: ver,
                      method: ver === 2 && prev.method === "grid" ? "random" : prev.method,
                      n_trials: ver === 2 ? Math.max(prev.n_trials, 32) : prev.n_trials,
                    }));
                  }}
                >
                  <option value={1}>v1 — Flat Parameter Tuning</option>
                  <option value={2}>v2 — Multi-Dimensional Vector Discovery</option>
                </select>
              </div>

              <div className="adaptive-two-col">
                <div className="form-group">
                  <label htmlFor="tuner_date_from">Date From</label>
                  <input
                    id="tuner_date_from"
                    type="date"
                    value={form.date_from}
                    onChange={(e) => setForm((prev) => ({ ...prev, date_from: e.target.value }))}
                  />
                </div>
                <div className="form-group">
                  <label htmlFor="tuner_date_to">Date To</label>
                  <input
                    id="tuner_date_to"
                    type="date"
                    value={form.date_to}
                    onChange={(e) => setForm((prev) => ({ ...prev, date_to: e.target.value }))}
                  />
                </div>
              </div>

              <label className="field-row" htmlFor="tuner_l2_required">
                <span>Use only OHLCV + L2 covered dates</span>
                <input
                  id="tuner_l2_required"
                  type="checkbox"
                  checked={!!form.l2_required}
                  onChange={(e) =>
                    setForm((prev) => ({ ...prev, l2_required: e.target.checked }))
                  }
                />
              </label>

              <label className="field-row" htmlFor="tuner_l2_only">
                <span>Strict L2-only bars (advanced)</span>
                <input
                  id="tuner_l2_only"
                  type="checkbox"
                  checked={!!form.l2_only}
                  onChange={(e) => setForm((prev) => ({ ...prev, l2_only: e.target.checked }))}
                />
              </label>

              <label className="field-row" htmlFor="tuner_quick_mode">
                <span>Quick Approx Mode (fewer days, more trials)</span>
                <input
                  id="tuner_quick_mode"
                  type="checkbox"
                  checked={!!form.quick_mode}
                  onChange={(e) =>
                    setForm((prev) => ({ ...prev, quick_mode: e.target.checked }))
                  }
                />
              </label>

              {form.quick_mode && (
                <div className="adaptive-two-col">
                  <div className="form-group">
                    <label htmlFor="tuner_quick_days">Quick sample days</label>
                    <input
                      id="tuner_quick_days"
                      type="number"
                      min="1"
                      max="30"
                      value={form.quick_max_days}
                      onChange={(e) =>
                        setForm((prev) => ({
                          ...prev,
                          quick_max_days: Number(e.target.value),
                        }))
                      }
                    />
                  </div>
                  <div className="form-group">
                    <label htmlFor="tuner_quick_boost">Trial boost multiplier</label>
                    <input
                      id="tuner_quick_boost"
                      type="number"
                      min="1"
                      max="10"
                      value={form.quick_trial_boost}
                      onChange={(e) =>
                        setForm((prev) => ({
                          ...prev,
                          quick_trial_boost: Number(e.target.value),
                        }))
                      }
                    />
                  </div>
                </div>
              )}

              <div className="adaptive-two-col">
                <div className="form-group">
                  <label htmlFor="tuner_method">Method</label>
                  <select
                    id="tuner_method"
                    value={form.method}
                    onChange={(e) => setForm((prev) => ({ ...prev, method: e.target.value }))}
                  >
                    {!isV2 && <option value="grid">Grid Search</option>}
                    <option value="random">Random Search</option>
                    <option value="optuna">Optuna (fallback to random if unavailable)</option>
                  </select>
                </div>
                <div className="form-group">
                  <label htmlFor="tuner_trials">Trials</label>
                  <input
                    id="tuner_trials"
                    type="number"
                    min="1"
                    max="400"
                    value={form.n_trials}
                    onChange={(e) => setForm((prev) => ({ ...prev, n_trials: Number(e.target.value) }))}
                    disabled={!isV2 && form.method === "grid"}
                  />
                  <div className="field-hint">
                    Effective trial budget: {effectiveTrialBudgetPreview.effective}
                    {form.quick_mode && (
                      <> ({effectiveTrialBudgetPreview.requested} x{effectiveTrialBudgetPreview.boost})</>
                    )}
                  </div>
                </div>
              </div>

              <div className="adaptive-two-col">
                <div className="form-group">
                  <label htmlFor="tuner_score_metric">Score Metric</label>
                  <select
                    id="tuner_score_metric"
                    value={form.score_metric}
                    onChange={(e) =>
                      setForm((prev) => ({ ...prev, score_metric: e.target.value }))
                    }
                  >
                    <option value="pnl_pct">Avg PnL %</option>
                    <option value="pnl_dollars">Avg PnL $</option>
                    <option value="win_rate">Avg Win Rate %</option>
                    <option value="trade_adjusted">Trade-Adjusted Score</option>
                    <option value="robust">Robust (anti-overfit)</option>
                  </select>
                </div>
                <div className="form-group">
                  <label htmlFor="tuner_seed">Seed</label>
                  <input
                    id="tuner_seed"
                    type="number"
                    value={form.seed}
                    onChange={(e) => setForm((prev) => ({ ...prev, seed: Number(e.target.value) }))}
                    disabled={!isV2 && form.method === "grid"}
                  />
                </div>
              </div>

              <label className="field-row" htmlFor="tuner_persist_best">
                <span>Persist best candidate to AOS config</span>
                <input
                  id="tuner_persist_best"
                  type="checkbox"
                  checked={!!form.persist_best}
                  onChange={(e) =>
                    setForm((prev) => ({ ...prev, persist_best: e.target.checked }))
                  }
                />
              </label>
            </div>

            {/* V1 Search Space */}
            {!isV2 && (
              <div className="adaptive-section">
                <h3>Search Space (CSV lists)</h3>
                <div className="form-group">
                  <label htmlFor="tuner_selection_modes">Selection modes</label>
                  <input
                    id="tuner_selection_modes"
                    value={form.selection_modes}
                    onChange={(e) =>
                      setForm((prev) => ({ ...prev, selection_modes: e.target.value }))
                    }
                    placeholder="adaptive_top_n,all_enabled"
                  />
                </div>
                <div className="form-group">
                  <label htmlFor="tuner_max_active">max_active_strategies</label>
                  <input
                    id="tuner_max_active"
                    value={form.max_active_options}
                    onChange={(e) =>
                      setForm((prev) => ({ ...prev, max_active_options: e.target.value }))
                    }
                    placeholder="1,2,3,4,5"
                  />
                </div>
                <div className="form-group">
                  <label htmlFor="tuner_min_active">min_active_bars_before_switch</label>
                  <input
                    id="tuner_min_active"
                    value={form.min_active_bars_options}
                    onChange={(e) =>
                      setForm((prev) => ({ ...prev, min_active_bars_options: e.target.value }))
                    }
                    placeholder="0,2,4,8,12"
                  />
                </div>
                <div className="form-group">
                  <label htmlFor="tuner_cooldown">switch_cooldown_bars</label>
                  <input
                    id="tuner_cooldown"
                    value={form.switch_cooldown_bars_options}
                    onChange={(e) =>
                      setForm((prev) => ({ ...prev, switch_cooldown_bars_options: e.target.value }))
                    }
                    placeholder="0,1,2,4,8"
                  />
                </div>
                <div className="form-group">
                  <label htmlFor="tuner_flow_bias">flow_bias_enabled options</label>
                  <input
                    id="tuner_flow_bias"
                    value={form.flow_bias_options}
                    onChange={(e) =>
                      setForm((prev) => ({ ...prev, flow_bias_options: e.target.value }))
                    }
                    placeholder="true,false"
                  />
                </div>
                <div className="form-group">
                  <label htmlFor="tuner_fallback">use_ohlcv_fallbacks options</label>
                  <input
                    id="tuner_fallback"
                    value={form.ohlcv_fallback_options}
                    onChange={(e) =>
                      setForm((prev) => ({ ...prev, ohlcv_fallback_options: e.target.value }))
                    }
                    placeholder="true,false"
                  />
                </div>
              </div>
            )}

            {/* V2 Search Space */}
            {isV2 && (
              <div className="adaptive-section v2-search-space">
                <h3>V2 Vector Search Dimensions</h3>

                <div className="form-group">
                  <label htmlFor="tuner_v2_strategies">
                    Strategy Sets <span className="field-hint">(semicolon-separated groups, comma-separated within)</span>
                  </label>
                  <input
                    id="tuner_v2_strategies"
                    value={form.v2_strategy_sets}
                    onChange={(e) =>
                      setForm((prev) => ({ ...prev, v2_strategy_sets: e.target.value }))
                    }
                    placeholder="momentum_flow;absorption_reversal;momentum_flow,absorption_reversal"
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="tuner_v2_regime">
                    Regime Filter Sets <span className="field-hint">(semicolon-separated, e.g. TRENDING;TRENDING,MIXED)</span>
                  </label>
                  <input
                    id="tuner_v2_regime"
                    value={form.v2_regime_filter_sets}
                    onChange={(e) =>
                      setForm((prev) => ({ ...prev, v2_regime_filter_sets: e.target.value }))
                    }
                    placeholder="TRENDING;TRENDING,MIXED;TRENDING,MIXED,CHOPPY"
                  />
                </div>

                <div className="adaptive-two-col">
                  <div className="form-group">
                    <label htmlFor="tuner_v2_imbalance">L2 min_imbalance</label>
                    <input
                      id="tuner_v2_imbalance"
                      value={form.v2_l2_min_imbalance}
                      onChange={(e) =>
                        setForm((prev) => ({ ...prev, v2_l2_min_imbalance: e.target.value }))
                      }
                      placeholder="0.05,0.12,0.25"
                    />
                  </div>
                  <div className="form-group">
                    <label htmlFor="tuner_v2_delta">L2 min_delta</label>
                    <input
                      id="tuner_v2_delta"
                      value={form.v2_l2_min_delta}
                      onChange={(e) =>
                        setForm((prev) => ({ ...prev, v2_l2_min_delta: e.target.value }))
                      }
                      placeholder="50,100,200"
                    />
                  </div>
                </div>

                <div className="adaptive-two-col">
                  <div className="form-group">
                    <label htmlFor="tuner_v2_threshold">Evidence base_threshold</label>
                    <input
                      id="tuner_v2_threshold"
                      value={form.v2_base_threshold}
                      onChange={(e) =>
                        setForm((prev) => ({ ...prev, v2_base_threshold: e.target.value }))
                      }
                      placeholder="45,55,65"
                    />
                  </div>
                  <div className="form-group">
                    <label htmlFor="tuner_v2_sources">min_confirming_sources</label>
                    <input
                      id="tuner_v2_sources"
                      value={form.v2_min_confirming_sources}
                      onChange={(e) =>
                        setForm((prev) => ({ ...prev, v2_min_confirming_sources: e.target.value }))
                      }
                      placeholder="2,3"
                    />
                  </div>
                </div>

                {/* Per-strategy parameter tuning */}
                <div className="adaptive-two-col" style={{ marginTop: 8 }}>
                  <div className="form-group">
                    <label htmlFor="tuner_v2_min_confidence">min_confidence</label>
                    <input
                      id="tuner_v2_min_confidence"
                      value={form.v2_min_confidence}
                      onChange={(e) =>
                        setForm((prev) => ({ ...prev, v2_min_confidence: e.target.value }))
                      }
                      placeholder="50,55,60,65"
                    />
                  </div>
                  <div className="form-group">
                    <label htmlFor="tuner_v2_atr_stop">atr_stop_multiplier</label>
                    <input
                      id="tuner_v2_atr_stop"
                      value={form.v2_atr_stop_multiplier}
                      onChange={(e) =>
                        setForm((prev) => ({ ...prev, v2_atr_stop_multiplier: e.target.value }))
                      }
                      placeholder="0.7,1.0,1.3,1.8"
                    />
                  </div>
                </div>
                <div className="form-group" style={{ marginTop: 4 }}>
                  <label htmlFor="tuner_v2_rr_ratio">rr_ratio</label>
                  <input
                    id="tuner_v2_rr_ratio"
                    value={form.v2_rr_ratio}
                    onChange={(e) =>
                      setForm((prev) => ({ ...prev, v2_rr_ratio: e.target.value }))
                    }
                    placeholder="1.5,2.0,2.5,3.0"
                  />
                </div>
                <div className="form-group" style={{ marginTop: 4 }}>
                  <label htmlFor="tuner_v2_time_windows">Time windows (hours, ; separated)</label>
                  <input
                    id="tuner_v2_time_windows"
                    value={form.v2_time_windows}
                    onChange={(e) =>
                      setForm((prev) => ({ ...prev, v2_time_windows: e.target.value }))
                    }
                    placeholder="9,10;9,10,11,12;9,10,11,12,13,14,15"
                  />
                </div>
                <div className="form-group" style={{ marginTop: 4 }}>
                  <label htmlFor="tuner_v2_adverse_flow_consistency">Flow exit consistency thresh</label>
                  <input
                    id="tuner_v2_adverse_flow_consistency"
                    value={form.v2_adverse_flow_consistency}
                    onChange={(e) =>
                      setForm((prev) => ({ ...prev, v2_adverse_flow_consistency: e.target.value }))
                    }
                    placeholder="0.35,0.45,0.55"
                  />
                </div>
                <div className="form-group" style={{ marginTop: 4 }}>
                  <label htmlFor="tuner_v2_adverse_book_pressure">Book pressure exit thresh</label>
                  <input
                    id="tuner_v2_adverse_book_pressure"
                    value={form.v2_adverse_book_pressure}
                    onChange={(e) =>
                      setForm((prev) => ({ ...prev, v2_adverse_book_pressure: e.target.value }))
                    }
                    placeholder="0.10,0.15,0.22"
                  />
                </div>
                <div className="form-group" style={{ marginTop: 4 }}>
                  <label htmlFor="tuner_v2_time_exit_bars">Time exit bars</label>
                  <input
                    id="tuner_v2_time_exit_bars"
                    value={form.v2_time_exit_bars}
                    onChange={(e) =>
                      setForm((prev) => ({ ...prev, v2_time_exit_bars: e.target.value }))
                    }
                    placeholder="15,25,35,50"
                  />
                </div>
                <div className="form-group" style={{ marginTop: 4 }}>
                  <label htmlFor="tuner_v2_trailing_stop_pct">Trailing stop %</label>
                  <input
                    id="tuner_v2_trailing_stop_pct"
                    value={form.v2_trailing_stop_pct}
                    onChange={(e) =>
                      setForm((prev) => ({ ...prev, v2_trailing_stop_pct: e.target.value }))
                    }
                    placeholder="0.4,0.6,0.8,1.0,1.3"
                  />
                </div>

                <div className="form-group" style={{ marginTop: 8 }}>
                  <label style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <input
                      type="checkbox"
                      checked={form.neighborhood_search}
                      onChange={(e) =>
                        setForm((prev) => ({ ...prev, neighborhood_search: e.target.checked }))
                      }
                    />
                    Neighborhood search (perturb from baseline)
                  </label>
                </div>

                {/* Base adaptive params still available for v2 */}
                <details className="v2-base-params">
                  <summary>Base Adaptive Params</summary>
                  <div className="form-group">
                    <label htmlFor="tuner_v2_selection_modes">Selection modes</label>
                    <input
                      id="tuner_v2_selection_modes"
                      value={form.selection_modes}
                      onChange={(e) =>
                        setForm((prev) => ({ ...prev, selection_modes: e.target.value }))
                      }
                      placeholder="adaptive_top_n,all_enabled"
                    />
                  </div>
                  <div className="form-group">
                    <label htmlFor="tuner_v2_max_active">max_active_strategies</label>
                    <input
                      id="tuner_v2_max_active"
                      value={form.max_active_options}
                      onChange={(e) =>
                        setForm((prev) => ({ ...prev, max_active_options: e.target.value }))
                      }
                      placeholder="1,2,3,4,5"
                    />
                  </div>
                </details>
              </div>
            )}
          </div>

          {/* ============ RESULTS COLUMN ============ */}
          <div className="adaptive-tuner-results-col">
            <div className="adaptive-section">
              <h3>Job Status</h3>
              <div className="adaptive-preview-list">
                <div className="adaptive-preview-item">
                  <span>Job ID</span>
                  <strong>{activeJobId || "-"}</strong>
                </div>
                <div className="adaptive-preview-item">
                  <span>Status</span>
                  <strong>{job?.status || "idle"}</strong>
                </div>
                <div className="adaptive-preview-item">
                  <span>Evaluated Dates</span>
                  <strong>
                    {job?.effective_date_from && job?.effective_date_to
                      ? `${job.effective_date_from} -> ${job.effective_date_to}`
                      : "-"}
                  </strong>
                </div>
                <div className="adaptive-preview-item">
                  <span>Progress</span>
                  <strong>
                    {Number(job?.progress?.completed_trials || 0)} / {Number(job?.progress?.total_trials || 0)}
                  </strong>
                  <div className="tuner-progress-track">
                    <div className="tuner-progress-fill" style={{ width: `${progressPct}%` }} />
                  </div>
                </div>
                <div className="adaptive-preview-item">
                  <span>Tuning Mode</span>
                  <strong>{jobQuickMode ? "Quick Approx" : "Standard"}</strong>
                </div>
                <div className="adaptive-preview-item">
                  <span>Trial Budget</span>
                  <strong>
                    {jobTrialBudget
                      ? `${Number(jobTrialBudget.effective || 0)} (${Number(jobTrialBudget.requested || 0)} x${Number(jobTrialBudget.boost || 1)})`
                      : "-"}
                  </strong>
                </div>
                <div className="adaptive-preview-item">
                  <span>Sampled Days</span>
                  <strong>
                    {job
                      ? `${Number(job?.effective_days || 0)} / ${Number(job?.source_effective_days || 0)}`
                      : "-"}
                  </strong>
                </div>
              </div>
            </div>

            <div className="adaptive-section">
              <h3>Adaptive Tuned Profiles</h3>
              {!profileList.length ? (
                <div className="adaptive-empty">No saved adaptive tuner profiles for this ticker yet.</div>
              ) : (
                <div className="tuner-profile-list">
                  {profileList.map((profile, idx) => {
                    const profileId = String(profile?.profile_id || "");
                    const isActive = profileId && profileId === tickerOptions?.active_profile_id;
                    const profileVersion = Number(profile?.adaptive_version || 1);
                    return (
                      <div
                        className={`tuner-profile-item ${isActive ? "active" : ""}`}
                        key={profileId || `profile-${idx}`}
                      >
                        <div className="tuner-profile-head">
                          <strong>
                            {profileId || "profile"}
                            {profileVersion >= 2 && (
                              <span className="v2-badge">v2</span>
                            )}
                          </strong>
                          <span>{formatTimestamp(profile?.created_at)}</span>
                        </div>
                        <div className="tuner-profile-body">
                          <div>
                            {profileVersion >= 2
                              ? formatV2Candidate(profile?.candidate)
                              : formatCandidate(profile?.candidate)}
                          </div>
                          <div>
                            score {Number(profile?.score || 0).toFixed(4)} | {profile?.date_from || "?"}
                            {" -> "}
                            {profile?.date_to || "?"}
                          </div>
                        </div>
                        <div className="tuner-profile-actions">
                          <button
                            className="btn btn-secondary btn-sm"
                            onClick={() => handleApplyProfile(profileId)}
                            disabled={!profileId || applyingProfileId === profileId}
                          >
                            {applyingProfileId === profileId ? "Applying..." : "Apply To Backtest"}
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            <div className="adaptive-section">
              <h3>Best Candidate</h3>
              {!bestTrial ? (
                <div className="adaptive-empty">No best trial yet.</div>
              ) : (
                <>
                  <div className="adaptive-preview-list">
                    <div className="adaptive-preview-item">
                      <span>Score</span>
                      <strong>{Number(bestTrial?.score || 0).toFixed(4)}</strong>
                    </div>
                    <div className="adaptive-preview-item">
                      <span>Configuration</span>
                      <strong>
                        {jobVersion >= 2
                          ? formatV2Candidate(bestTrial?.candidate)
                          : formatCandidate(bestTrial?.candidate)}
                      </strong>
                    </div>
                    <div className="adaptive-preview-item">
                      <span>Metrics</span>
                      <strong>
                        avg_pnl_pct {Number(bestTrial?.metrics?.avg_pnl_pct || 0).toFixed(4)} | total_trades {Number(bestTrial?.metrics?.total_trades || 0)} | avg_win_rate {Number(bestTrial?.metrics?.avg_win_rate_pct || 0).toFixed(2)}%
                      </strong>
                    </div>
                  </div>
                </>
              )}
            </div>

            {/* V2 Vector Analysis Panel */}
            {jobVersion >= 2 && vectorAnalysis && (
              <div className="adaptive-section vector-analysis-panel">
                <h3>🔬 Vector Analysis</h3>

                {vectorAnalysis.dimension_importance && (
                  <div className="vector-subsection">
                    <h4>Dimension Importance</h4>
                    <DimensionImportanceBars importance={vectorAnalysis.dimension_importance} />
                  </div>
                )}

                {vectorAnalysis.top_interactions && (
                  <div className="vector-subsection">
                    <h4>Top Interactions</h4>
                    <InteractionsList interactions={vectorAnalysis.top_interactions} />
                  </div>
                )}

                {vectorAnalysis.surprising_vectors && (
                  <div className="vector-subsection">
                    <h4>Surprising Vectors</h4>
                    <SurprisingVectorsTable vectors={vectorAnalysis.surprising_vectors} />
                  </div>
                )}
              </div>
            )}

            <div className="adaptive-section">
              <h3>Trials</h3>
              <div className="tuner-trials-table-wrap">
                <table className="tuner-trials-table">
                  <thead>
                    <tr>
                      <th>#</th>
                      <th>Score</th>
                      <th>Avg PnL %</th>
                      <th>Trades</th>
                      <th>{jobVersion >= 2 ? "Vector" : "Candidate"}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sortedTrials.slice(0, 50).map((trial) => (
                      <tr
                        key={trial.trial_index}
                        className={
                          selectedTrial?.trial_index === trial.trial_index
                            ? "active"
                            : ""
                        }
                        onClick={() => setSelectedTrialIndex(trial.trial_index)}
                      >
                        <td>{trial.trial_index}</td>
                        <td>{Number(trial.score || 0).toFixed(4)}</td>
                        <td>{Number(trial?.metrics?.avg_pnl_pct || 0).toFixed(4)}</td>
                        <td>{Number(trial?.metrics?.total_trades || 0)}</td>
                        <td>
                          {jobVersion >= 2
                            ? formatV2Candidate(trial.candidate)
                            : formatCandidate(trial.candidate)}
                        </td>
                      </tr>
                    ))}
                    {!sortedTrials.length && (
                      <tr>
                        <td colSpan={5} className="adaptive-empty">
                          No trials yet.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="adaptive-section">
              <h3>Selected Trial Day Results</h3>
              <div className="tuner-day-results">
                {(selectedTrial?.day_results || []).map((row, idx) => (
                  <div className="tuner-day-result" key={`${row.date}-${idx}`}>
                    <div>
                      <strong>{row.date}</strong>
                    </div>
                    {row.success ? (
                      <div>
                        pnl {Number(row.pnl_pct || 0).toFixed(4)}% | trades {Number(row.trades || 0)} | win {Number(row.win_rate_pct || 0).toFixed(2)}%
                      </div>
                    ) : (
                      <div className="adaptive-error">{row.error || "failed"}</div>
                    )}
                  </div>
                ))}
                {(!selectedTrial?.day_results || !selectedTrial.day_results.length) && (
                  <div className="adaptive-empty">No day-level results yet.</div>
                )}
              </div>
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}

export default AdaptiveTuner;
