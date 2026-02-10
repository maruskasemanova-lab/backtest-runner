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
  selection_modes: "adaptive_top_n,all_enabled",
  max_active_options: "1,2,3,4,5",
  min_active_bars_options: "0,2,4,8,12",
  switch_cooldown_bars_options: "0,1,2,4,8",
  flow_bias_options: "true,false",
  ohlcv_fallback_options: "true,false",
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

const formatCandidate = (candidate) => {
  if (!candidate || typeof candidate !== "object") return "-";
  const mode = candidate.strategy_selection_mode || "adaptive_top_n";
  return `${mode} | top=${candidate.max_active_strategies} | hysteresis=${candidate.min_active_bars_before_switch} | cooldown=${candidate.switch_cooldown_bars} | flowBias=${candidate.flow_bias_enabled ? "on" : "off"} | fallback=${candidate.use_ohlcv_fallbacks ? "on" : "off"}`;
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

  const profileList = useMemo(() => {
    return Array.isArray(tickerOptions?.profiles) ? tickerOptions.profiles : [];
  }, [tickerOptions]);

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

      const payload = {
        ticker: form.ticker,
        date_from: form.date_from,
        date_to: form.date_to,
        strategy_api_url: strategyApiUrl || `http://${window.location.hostname}:8001`,
        method: form.method,
        adaptive_version: 1,
        n_trials: Number(form.n_trials || 16),
        score_metric: form.score_metric,
        seed: Number(form.seed || 42),
        persist_best: !!form.persist_best,
        l2_required: !!form.l2_required,
        l2_confirm_enabled: true,
        l2_only: !!form.l2_only,
        selection_modes: parseModeCsv(form.selection_modes),
        max_active_options: parseIntCsv(form.max_active_options, { min: 1, max: 20 }),
        min_active_bars_options: parseIntCsv(form.min_active_bars_options, { min: 0, max: 500 }),
        switch_cooldown_bars_options: parseIntCsv(form.switch_cooldown_bars_options, {
          min: 0,
          max: 500,
        }),
        flow_bias_options: parseBoolCsv(form.flow_bias_options),
        ohlcv_fallback_options: parseBoolCsv(form.ohlcv_fallback_options),
      };

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
        `Adaptive tuner job queued: ${data.job_id} (${data.effective_days || 0} effective days)`
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
          <span className="card-title">Adaptive Tuner (L2-Aware)</span>
          <button className="btn btn-primary" onClick={handleStart} disabled={submitting}>
            {submitting ? "Running..." : "Start Tuning"}
          </button>
        </div>

        <div className="card-body adaptive-tuner-layout">
          <div className="adaptive-tuner-form-col">
            <div className="adaptive-info-box">
              Tuning targets Adaptive Studio <strong>Version 1</strong>. Ticker options are based on
              real data coverage from your catalog, including OHLCV and L2 overlap.
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
                <input id="tuner_version" value="v1" readOnly />
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

              <div className="adaptive-two-col">
                <div className="form-group">
                  <label htmlFor="tuner_method">Method</label>
                  <select
                    id="tuner_method"
                    value={form.method}
                    onChange={(e) => setForm((prev) => ({ ...prev, method: e.target.value }))}
                  >
                    <option value="grid">Grid Search</option>
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
                    disabled={form.method === "grid"}
                  />
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
                  </select>
                </div>
                <div className="form-group">
                  <label htmlFor="tuner_seed">Seed</label>
                  <input
                    id="tuner_seed"
                    type="number"
                    value={form.seed}
                    onChange={(e) => setForm((prev) => ({ ...prev, seed: Number(e.target.value) }))}
                    disabled={form.method === "grid"}
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
          </div>

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
                    return (
                      <div
                        className={`tuner-profile-item ${isActive ? "active" : ""}`}
                        key={profileId || `profile-${idx}`}
                      >
                        <div className="tuner-profile-head">
                          <strong>{profileId || "profile"}</strong>
                          <span>{formatTimestamp(profile?.created_at)}</span>
                        </div>
                        <div className="tuner-profile-body">
                          <div>{formatCandidate(profile?.candidate)}</div>
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
                      <strong>{formatCandidate(bestTrial?.candidate)}</strong>
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
                      <th>Candidate</th>
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
                        <td>{formatCandidate(trial.candidate)}</td>
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
