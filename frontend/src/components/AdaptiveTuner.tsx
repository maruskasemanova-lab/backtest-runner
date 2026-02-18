import { Fragment } from "react";
import { formatTimestamp } from "../utils";
import { useAdaptiveTunerController } from "./adaptive-tuner/useAdaptiveTunerController";

interface AdaptiveTunerProps {
  selectedTicker?: string;
  onTickerChange?: (ticker: string) => void;
  strategyApiUrl?: string;
}

type GenericRecord = Record<string, any>;

interface RangeSummary {
  start?: string;
  end?: string;
  total_days?: number;
}

interface DimensionImportanceBarsProps {
  importance?: Record<string, number> | null;
}

interface InteractionItem {
  dimensions?: string;
  pair?: string;
  effect?: number;
  delta?: number;
  count?: number;
}

interface SurprisingVector {
  label?: string;
  key?: string;
  candidate?: Record<string, unknown>;
  score?: number;
  z_score?: number;
  trades?: number;
  trade_count?: number;
}

const formatCandidate = (candidate: GenericRecord | null | undefined) => {
  if (!candidate || typeof candidate !== "object") return "-";
  const mode = candidate.strategy_selection_mode || "adaptive_top_n";
  return `${mode} | top=${candidate.max_active_strategies} | hysteresis=${candidate.min_active_bars_before_switch} | cooldown=${candidate.switch_cooldown_bars} | flowBias=${candidate.flow_bias_enabled ? "on" : "off"} | fallback=${candidate.use_ohlcv_fallbacks ? "on" : "off"}`;
};

const formatV2Candidate = (candidate: GenericRecord | null | undefined) => {
  if (!candidate || typeof candidate !== "object") return "-";
  const parts: string[] = [];
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

const formatRange = (range: RangeSummary | null | undefined) => {
  if (!range || !range.start || !range.end) return "-";
  return `${range.start} -> ${range.end} (${Number(range.total_days || 0)} days)`;
};

const formatJobLabel = (job: Record<string, any>) => {
  const jobId = String(job?.job_id || "").slice(0, 8) || "job";
  const status = String(job?.status || "idle").toLowerCase();
  const version = Number(job?.adaptive_version || job?.request?.adaptive_version || 1);
  return `${jobId} | v${version} | ${status}`;
};

const statusClassName = (status: string) => {
  const normalized = String(status || "").toLowerCase();
  if (normalized === "running") return "running";
  if (normalized === "completed") return "completed";
  if (normalized === "failed") return "failed";
  if (normalized === "queued") return "queued";
  return "idle";
};

function DimensionImportanceBars({ importance }: DimensionImportanceBarsProps) {
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

function InteractionsList({ interactions }: { interactions?: InteractionItem[] | null }) {
  if (!Array.isArray(interactions) || !interactions.length) return null;
  return (
    <div className="vector-interactions-list">
      {interactions.slice(0, 8).map((ix, idx) => (
        <div className="vector-interaction-item" key={idx}>
          <span className="interaction-dims">{ix.dimensions || ix.pair || "?"}</span>
          <span className="interaction-effect">
            Δ={Number(ix.effect ?? ix.delta ?? 0).toFixed(4)}
          </span>
          {ix.count != null && <span className="interaction-count">n={ix.count}</span>}
        </div>
      ))}
    </div>
  );
}

function SurprisingVectorsTable({ vectors }: { vectors?: SurprisingVector[] | null }) {
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

function AdaptiveTuner({ selectedTicker, onTickerChange, strategyApiUrl }: AdaptiveTunerProps) {
  const {
    form,
    setForm,
    tickerOptions,
    jobHistory,
    loadingTickerOptions,
    submitting,
    applyingProfileId,
    error,
    notice,
    selectedJobId,
    setSelectedJobId,
    job,
    selectedTrialIndex,
    setSelectedTrialIndex,
    resultsTab,
    setResultsTab,
    profileFilter,
    setProfileFilter,
    profileSort,
    setProfileSort,
    filteredSortedProfiles,
    isV2,
    etaEstimate,
    configPanelCollapsed,
    setConfigPanelCollapsed,
    sortedTrials,
    progressPct,
    effectiveTrialBudgetPreview,
    tickerOptionsList,
    bestTrial,
    jobVersion,
    jobQuickMode,
    jobTrialBudget,
    vectorAnalysis,
    handleStart,
    handleApplyProfile,
    handleTickerChange,
  } = useAdaptiveTunerController({
    selectedTicker,
    onTickerChange,
    strategyApiUrl,
  });

  const activeProfileId = String(tickerOptions?.active_profile_id || "").trim();
  const jobStatus = statusClassName(String(job?.status || (submitting ? "running" : "idle")));
  const completedTrials = Number(job?.progress?.completed_trials || 0);
  const totalTrials = Number(job?.progress?.total_trials || 0);
  const trialRows = sortedTrials.slice(0, 80);

  return (
    <main className="tuner-page">
      <aside className={`tuner-config-panel ${configPanelCollapsed ? "collapsed" : ""}`}>
        <div className="tuner-config-header">
          <button
            type="button"
            className="tuner-collapse-toggle"
            onClick={() => setConfigPanelCollapsed((prev: boolean) => !prev)}
            aria-label={configPanelCollapsed ? "Expand configuration panel" : "Collapse configuration panel"}
            title={configPanelCollapsed ? "Expand configuration panel" : "Collapse configuration panel"}
          >
            {configPanelCollapsed ? "»" : "«"}
          </button>
          {!configPanelCollapsed && (
            <>
              <div className="tuner-config-header-main">
                <h2>Adaptive Tuner</h2>
                <div className="tuner-config-header-meta">
                  <span className="tuner-version-badge">v{Number(form.adaptive_version || 1)}</span>
                  <span className="tuner-ticker-pill">{form.ticker || "-"}</span>
                </div>
              </div>
              <button className="btn btn-primary" onClick={handleStart} disabled={submitting}>
                {submitting ? "Running..." : "Start"}
              </button>
            </>
          )}
        </div>

        {configPanelCollapsed ? (
          <div className="tuner-config-collapsed">
            <span>Config</span>
          </div>
        ) : (
          <div className="tuner-config-body">
            <details className="tuner-form-section" open>
              <summary>Run Setup</summary>
              <div className="tuner-form-grid">
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
                      const version = Number(e.target.value);
                      setForm((prev) => ({
                        ...prev,
                        adaptive_version: version,
                        method: version === 2 && prev.method === "grid" ? "random" : prev.method,
                        n_trials: version === 2 ? Math.max(prev.n_trials, 32) : prev.n_trials,
                      }));
                    }}
                  >
                    <option value={1}>v1</option>
                    <option value={2}>v2</option>
                  </select>
                </div>

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

              <div className="tuner-coverage-grid">
                <div className="tuner-coverage-item">
                  <span>OHLCV</span>
                  <strong>{formatRange(tickerOptions?.ohlcv_range)}</strong>
                </div>
                <div className="tuner-coverage-item">
                  <span>L2 (mbp-10)</span>
                  <strong>{formatRange(tickerOptions?.l2_range)}</strong>
                </div>
                <div className="tuner-coverage-item">
                  <span>Overlap</span>
                  <strong>{formatRange(tickerOptions?.l2_overlap_range)}</strong>
                </div>
              </div>

              {loadingTickerOptions && <div className="adaptive-empty">Loading ticker coverage...</div>}

              <label className="field-row" htmlFor="tuner_l2_required">
                <span>Use only OHLCV + L2 covered dates</span>
                <input
                  id="tuner_l2_required"
                  type="checkbox"
                  checked={!!form.l2_required}
                  onChange={(e) => setForm((prev) => ({ ...prev, l2_required: e.target.checked }))}
                />
              </label>

              <label className="field-row" htmlFor="tuner_l2_only">
                <span>Strict L2-only bars</span>
                <input
                  id="tuner_l2_only"
                  type="checkbox"
                  checked={!!form.l2_only}
                  onChange={(e) => setForm((prev) => ({ ...prev, l2_only: e.target.checked }))}
                />
              </label>

              <label className="field-row" htmlFor="tuner_quick_mode">
                <span>Quick Approx Mode</span>
                <input
                  id="tuner_quick_mode"
                  type="checkbox"
                  checked={!!form.quick_mode}
                  onChange={(e) => setForm((prev) => ({ ...prev, quick_mode: e.target.checked }))}
                />
              </label>

              {form.quick_mode && (
                <div className="tuner-form-grid">
                  <div className="form-group">
                    <label htmlFor="tuner_quick_days">Quick sample days</label>
                    <input
                      id="tuner_quick_days"
                      type="number"
                      min="1"
                      max="30"
                      value={form.quick_max_days}
                      onChange={(e) =>
                        setForm((prev) => ({ ...prev, quick_max_days: Number(e.target.value) }))
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
                        setForm((prev) => ({ ...prev, quick_trial_boost: Number(e.target.value) }))
                      }
                    />
                  </div>
                </div>
              )}
            </details>

            <details className="tuner-form-section" open>
              <summary>Search Parameters</summary>
              <div className="tuner-form-grid">
                <div className="form-group">
                  <label htmlFor="tuner_method">Method</label>
                  <select
                    id="tuner_method"
                    value={form.method}
                    onChange={(e) => setForm((prev) => ({ ...prev, method: e.target.value }))}
                  >
                    {!isV2 && <option value="grid">Grid Search</option>}
                    <option value="random">Random Search</option>
                    <option value="optuna">Optuna (fallback to random)</option>
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
                <div className="form-group">
                  <label htmlFor="tuner_score_metric">Score Metric</label>
                  <select
                    id="tuner_score_metric"
                    value={form.score_metric}
                    onChange={(e) => setForm((prev) => ({ ...prev, score_metric: e.target.value }))}
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
                  onChange={(e) => setForm((prev) => ({ ...prev, persist_best: e.target.checked }))}
                />
              </label>
            </details>

            <details className="tuner-form-section">
              <summary>Search Space</summary>
              {!isV2 ? (
                <div className="tuner-form-stack">
                  <div className="field-hint">CSV values are de-duplicated and validated before submit.</div>
                  <div className="form-group">
                    <label htmlFor="tuner_selection_modes">Selection modes</label>
                    <input
                      id="tuner_selection_modes"
                      value={form.selection_modes}
                      onChange={(e) => setForm((prev) => ({ ...prev, selection_modes: e.target.value }))}
                      placeholder="adaptive_top_n,all_enabled"
                    />
                  </div>
                  <div className="form-group">
                    <label htmlFor="tuner_max_active">max_active_strategies</label>
                    <input
                      id="tuner_max_active"
                      value={form.max_active_options}
                      onChange={(e) => setForm((prev) => ({ ...prev, max_active_options: e.target.value }))}
                      placeholder="1,2,3,4,5"
                    />
                  </div>
                  <div className="form-group">
                    <label htmlFor="tuner_min_active">min_active_bars_before_switch</label>
                    <input
                      id="tuner_min_active"
                      value={form.min_active_bars_options}
                      onChange={(e) => setForm((prev) => ({ ...prev, min_active_bars_options: e.target.value }))}
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
                      onChange={(e) => setForm((prev) => ({ ...prev, flow_bias_options: e.target.value }))}
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
              ) : (
                <div className="tuner-form-stack">
                  <div className="field-hint">
                    Semicolon-separated groups, comma-separated values inside each group.
                  </div>
                  <div className="form-group">
                    <label htmlFor="tuner_v2_strategies">Strategy sets</label>
                    <input
                      id="tuner_v2_strategies"
                      value={form.v2_strategy_sets}
                      onChange={(e) => setForm((prev) => ({ ...prev, v2_strategy_sets: e.target.value }))}
                      placeholder="momentum_flow;absorption_reversal;momentum_flow,absorption_reversal"
                    />
                  </div>
                  <div className="form-group">
                    <label htmlFor="tuner_v2_regime">Regime filter sets</label>
                    <input
                      id="tuner_v2_regime"
                      value={form.v2_regime_filter_sets}
                      onChange={(e) =>
                        setForm((prev) => ({ ...prev, v2_regime_filter_sets: e.target.value }))
                      }
                      placeholder="TRENDING;TRENDING,MIXED;TRENDING,MIXED,CHOPPY"
                    />
                  </div>
                  <div className="tuner-form-grid">
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
                        onChange={(e) => setForm((prev) => ({ ...prev, v2_l2_min_delta: e.target.value }))}
                        placeholder="50,100,200"
                      />
                    </div>
                    <div className="form-group">
                      <label htmlFor="tuner_v2_threshold">base_threshold</label>
                      <input
                        id="tuner_v2_threshold"
                        value={form.v2_base_threshold}
                        onChange={(e) => setForm((prev) => ({ ...prev, v2_base_threshold: e.target.value }))}
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
                    <div className="form-group">
                      <label htmlFor="tuner_v2_min_confidence">min_confidence</label>
                      <input
                        id="tuner_v2_min_confidence"
                        value={form.v2_min_confidence}
                        onChange={(e) => setForm((prev) => ({ ...prev, v2_min_confidence: e.target.value }))}
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
                    <div className="form-group">
                      <label htmlFor="tuner_v2_rr_ratio">rr_ratio</label>
                      <input
                        id="tuner_v2_rr_ratio"
                        value={form.v2_rr_ratio}
                        onChange={(e) => setForm((prev) => ({ ...prev, v2_rr_ratio: e.target.value }))}
                        placeholder="1.5,2.0,2.5,3.0"
                      />
                    </div>
                    <div className="form-group">
                      <label htmlFor="tuner_v2_time_windows">Time windows</label>
                      <input
                        id="tuner_v2_time_windows"
                        value={form.v2_time_windows}
                        onChange={(e) => setForm((prev) => ({ ...prev, v2_time_windows: e.target.value }))}
                        placeholder="9,10;9,10,11,12;9,10,11,12,13,14,15"
                      />
                    </div>
                    <div className="form-group">
                      <label htmlFor="tuner_v2_adverse_flow_consistency">Flow exit consistency</label>
                      <input
                        id="tuner_v2_adverse_flow_consistency"
                        value={form.v2_adverse_flow_consistency}
                        onChange={(e) =>
                          setForm((prev) => ({ ...prev, v2_adverse_flow_consistency: e.target.value }))
                        }
                        placeholder="0.35,0.45,0.55"
                      />
                    </div>
                    <div className="form-group">
                      <label htmlFor="tuner_v2_adverse_book_pressure">Book pressure exit</label>
                      <input
                        id="tuner_v2_adverse_book_pressure"
                        value={form.v2_adverse_book_pressure}
                        onChange={(e) =>
                          setForm((prev) => ({ ...prev, v2_adverse_book_pressure: e.target.value }))
                        }
                        placeholder="0.10,0.15,0.22"
                      />
                    </div>
                    <div className="form-group">
                      <label htmlFor="tuner_v2_time_exit_bars">Time exit bars</label>
                      <input
                        id="tuner_v2_time_exit_bars"
                        value={form.v2_time_exit_bars}
                        onChange={(e) => setForm((prev) => ({ ...prev, v2_time_exit_bars: e.target.value }))}
                        placeholder="15,25,35,50"
                      />
                    </div>
                    <div className="form-group">
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
                  </div>
                  <label className="field-row" htmlFor="tuner_v2_neighborhood_search">
                    <span>Neighborhood search</span>
                    <input
                      id="tuner_v2_neighborhood_search"
                      type="checkbox"
                      checked={!!form.neighborhood_search}
                      onChange={(e) => setForm((prev) => ({ ...prev, neighborhood_search: e.target.checked }))}
                    />
                  </label>
                </div>
              )}
            </details>
          </div>
        )}
      </aside>

      <div className="tuner-main-content">
        <section className="tuner-monitor">
          <div className="tuner-monitor-top">
            <div>
              <h3>Job Monitor</h3>
              <p>{job?.job_id ? `Job ${job.job_id}` : "No tuning job selected yet."}</p>
            </div>
            <span className={`tuner-status-badge ${jobStatus}`}>{job?.status || "idle"}</span>
          </div>

          {(error || notice) && (
            <div className="tuner-alerts">
              {error && <div className="adaptive-error">{error}</div>}
              {notice && <div className="adaptive-notice">{notice}</div>}
            </div>
          )}

          <div className="tuner-history-picker">
            <label htmlFor="tuner_job_history">Job history</label>
            <select
              id="tuner_job_history"
              value={selectedJobId || ""}
              onChange={(e) => setSelectedJobId(e.target.value || null)}
            >
              {!jobHistory.length && <option value="">No jobs yet</option>}
              {jobHistory.map((historyJob) => {
                const historyId = String(historyJob?.job_id || "");
                if (!historyId) return null;
                return (
                  <option key={historyId} value={historyId}>
                    {formatJobLabel(historyJob)}
                  </option>
                );
              })}
            </select>
          </div>

          <div className="tuner-progress-large-track">
            <div
              className={`tuner-progress-large-fill ${jobStatus === "running" ? "running" : ""}`}
              style={{ width: `${progressPct}%` }}
            />
          </div>

          <div className="tuner-monitor-stats">
            <div className="tuner-monitor-stat">
              <span>Progress</span>
              <strong>{progressPct.toFixed(1)}%</strong>
            </div>
            <div className="tuner-monitor-stat">
              <span>Trials</span>
              <strong>
                {completedTrials} / {totalTrials}
              </strong>
            </div>
            <div className="tuner-monitor-stat">
              <span>ETA</span>
              <strong>{etaEstimate?.label || "-"}</strong>
            </div>
            <div className="tuner-monitor-stat">
              <span>Score metric</span>
              <strong>{String(job?.request?.score_metric || form.score_metric)}</strong>
            </div>
          </div>

          <div className="tuner-best-score-card">
            <div className="tuner-best-score-head">
              <span>Best Score</span>
              <strong>{Number(bestTrial?.score || 0).toFixed(4)}</strong>
            </div>
            <div className="tuner-best-score-metrics">
              <span>PnL {Number(bestTrial?.metrics?.avg_pnl_pct || 0).toFixed(4)}%</span>
              <span>WR {Number(bestTrial?.metrics?.avg_win_rate_pct || 0).toFixed(2)}%</span>
              <span>Trades {Number(bestTrial?.metrics?.total_trades || 0)}</span>
            </div>
          </div>

          <div className="tuner-monitor-meta">
            <span>Mode: {jobQuickMode ? "Quick" : "Standard"}</span>
            <span>Version: v{jobVersion}</span>
            <span>Days: {Number(job?.effective_days || 0)}</span>
            <span>
              Budget:{" "}
              {jobTrialBudget
                ? `${Number(jobTrialBudget.effective || 0)} (${Number(jobTrialBudget.requested || 0)} x${Number(jobTrialBudget.boost || 1)})`
                : "-"}
            </span>
            <span>ETA at: {etaEstimate?.etaAt ? formatTimestamp(etaEstimate.etaAt) : "-"}</span>
          </div>
        </section>

        <section className="tuner-results-area">
          <div className="tuner-results-tabs" role="tablist" aria-label="Adaptive tuner results">
            <button
              type="button"
              className={resultsTab === "profiles" ? "active" : ""}
              onClick={() => setResultsTab("profiles")}
            >
              Profiles
            </button>
            <button
              type="button"
              className={resultsTab === "trials" ? "active" : ""}
              onClick={() => setResultsTab("trials")}
            >
              Trials
            </button>
            <button
              type="button"
              className={resultsTab === "analysis" ? "active" : ""}
              onClick={() => setResultsTab("analysis")}
            >
              Analysis
            </button>
          </div>

          {resultsTab === "profiles" && (
            <div className="tuner-results-panel">
              <div className="tuner-profile-filter-bar">
                <div className="form-group">
                  <label htmlFor="tuner_profile_version_filter">Version</label>
                  <select
                    id="tuner_profile_version_filter"
                    value={profileFilter.version}
                    onChange={(e) =>
                      setProfileFilter((prev: Record<string, any>) => ({
                        ...prev,
                        version: e.target.value,
                      }))
                    }
                  >
                    <option value="all">All</option>
                    <option value="1">v1</option>
                    <option value="2">v2</option>
                  </select>
                </div>
                <div className="form-group">
                  <label htmlFor="tuner_profile_date_from">Created from</label>
                  <input
                    id="tuner_profile_date_from"
                    type="date"
                    value={profileFilter.dateFrom}
                    onChange={(e) =>
                      setProfileFilter((prev: Record<string, any>) => ({
                        ...prev,
                        dateFrom: e.target.value,
                      }))
                    }
                  />
                </div>
                <div className="form-group">
                  <label htmlFor="tuner_profile_date_to">Created to</label>
                  <input
                    id="tuner_profile_date_to"
                    type="date"
                    value={profileFilter.dateTo}
                    onChange={(e) =>
                      setProfileFilter((prev: Record<string, any>) => ({
                        ...prev,
                        dateTo: e.target.value,
                      }))
                    }
                  />
                </div>
                <div className="form-group">
                  <label htmlFor="tuner_profile_sort_field">Sort by</label>
                  <select
                    id="tuner_profile_sort_field"
                    value={profileSort.field}
                    onChange={(e) =>
                      setProfileSort((prev: Record<string, any>) => ({
                        ...prev,
                        field: e.target.value,
                      }))
                    }
                  >
                    <option value="score">Score</option>
                    <option value="date">Date</option>
                    <option value="trades">Trades</option>
                  </select>
                </div>
                <button
                  type="button"
                  className="btn btn-secondary tuner-sort-direction"
                  onClick={() =>
                    setProfileSort((prev: Record<string, any>) => ({
                      ...prev,
                      direction: prev.direction === "asc" ? "desc" : "asc",
                    }))
                  }
                >
                  {profileSort.direction === "asc" ? "Ascending" : "Descending"}
                </button>
              </div>

              {!filteredSortedProfiles.length ? (
                <div className="adaptive-empty">No profiles match current filter.</div>
              ) : (
                <div className="tuner-profile-grid">
                  {filteredSortedProfiles.map((profile, idx) => {
                    const profileId = String(profile?.profile_id || "");
                    const profileVersion = Number(profile?.adaptive_version || 1);
                    const isActive = profileId && profileId === activeProfileId;
                    return (
                      <article
                        className={`tuner-profile-card ${isActive ? "active" : ""}`}
                        key={profileId || `profile-${idx}`}
                      >
                        <div className="tuner-profile-card-head">
                          <strong>{profileId || "profile"}</strong>
                          <div className="tuner-profile-badges">
                            {isActive && <span className="tuner-badge-active">Active</span>}
                            <span className="tuner-badge-version">v{profileVersion}</span>
                          </div>
                        </div>

                        <div className="tuner-profile-meta-line">
                          {profile?.date_from || "?"}
                          {" -> "}
                          {profile?.date_to || "?"}
                        </div>
                        <div className="tuner-profile-meta-line">{formatTimestamp(profile?.created_at)}</div>

                        <div className="tuner-profile-metrics">
                          <span className="tuner-metric-chip">Score {Number(profile?.score || 0).toFixed(4)}</span>
                          <span className="tuner-metric-chip">
                            PnL {Number(profile?.metrics?.avg_pnl_pct || 0).toFixed(4)}%
                          </span>
                          <span className="tuner-metric-chip">
                            WR {Number(profile?.metrics?.avg_win_rate_pct || 0).toFixed(2)}%
                          </span>
                          <span className="tuner-metric-chip">
                            Trades {Number(profile?.metrics?.total_trades || 0)}
                          </span>
                        </div>

                        <p className="tuner-profile-candidate">
                          {profileVersion >= 2
                            ? formatV2Candidate(profile?.candidate)
                            : formatCandidate(profile?.candidate)}
                        </p>

                        <div className="tuner-profile-actions">
                          <button
                            className="btn btn-secondary btn-sm"
                            onClick={() => handleApplyProfile(profileId)}
                            disabled={!profileId || applyingProfileId === profileId}
                          >
                            {applyingProfileId === profileId ? "Applying..." : "Apply"}
                          </button>
                        </div>
                      </article>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {resultsTab === "trials" && (
            <div className="tuner-results-panel">
              <div className="tuner-trials-table-wrap">
                <table className="tuner-trials-table">
                  <thead>
                    <tr>
                      <th>#</th>
                      <th>Score</th>
                      <th>Avg PnL %</th>
                      <th>Win Rate</th>
                      <th>Trades</th>
                      <th>{jobVersion >= 2 ? "Vector" : "Candidate"}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {trialRows.map((trial) => {
                      const isExpanded = selectedTrialIndex === trial.trial_index;
                      return (
                        <Fragment key={trial.trial_index}>
                          <tr
                            className={isExpanded ? "active" : ""}
                            onClick={() =>
                              setSelectedTrialIndex((prev) =>
                                prev === trial.trial_index ? null : trial.trial_index,
                              )
                            }
                          >
                            <td>{trial.trial_index}</td>
                            <td>{Number(trial.score || 0).toFixed(4)}</td>
                            <td>{Number(trial?.metrics?.avg_pnl_pct || 0).toFixed(4)}</td>
                            <td>{Number(trial?.metrics?.avg_win_rate_pct || 0).toFixed(2)}%</td>
                            <td>{Number(trial?.metrics?.total_trades || 0)}</td>
                            <td>
                              {jobVersion >= 2
                                ? formatV2Candidate(trial?.candidate)
                                : formatCandidate(trial?.candidate)}
                            </td>
                          </tr>

                          {isExpanded && (
                            <tr className="tuner-trial-expanded-row">
                              <td colSpan={6}>
                                <div className="tuner-trial-expanded">
                                  {Array.isArray(trial?.day_results) && trial.day_results.length ? (
                                    <div className="tuner-day-results-inline">
                                      {trial.day_results.map((row: Record<string, any>, idx: number) => (
                                        <div
                                          className={`tuner-day-result-pill ${row?.success ? "success" : "failed"}`}
                                          key={`${row?.date || "day"}-${idx}`}
                                        >
                                          <strong>{row?.date || "?"}</strong>
                                          {row?.success ? (
                                            <span>
                                              pnl {Number(row?.pnl_pct || 0).toFixed(4)}% | trades{" "}
                                              {Number(row?.trades || 0)} | win{" "}
                                              {Number(row?.win_rate_pct || 0).toFixed(2)}%
                                            </span>
                                          ) : (
                                            <span>{row?.error || "failed"}</span>
                                          )}
                                        </div>
                                      ))}
                                    </div>
                                  ) : (
                                    <div className="adaptive-empty">No day-level results.</div>
                                  )}
                                </div>
                              </td>
                            </tr>
                          )}
                        </Fragment>
                      );
                    })}

                    {!trialRows.length && (
                      <tr>
                        <td colSpan={6} className="adaptive-empty">
                          No trials yet.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {resultsTab === "analysis" && (
            <div className="tuner-results-panel">
              {jobVersion < 2 ? (
                <div className="adaptive-empty">Vector analysis is available for v2 tuning jobs.</div>
              ) : !vectorAnalysis ? (
                <div className="adaptive-empty">No vector analysis available for the selected job.</div>
              ) : (
                <div className="vector-analysis-panel">
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
            </div>
          )}
        </section>
      </div>
    </main>
  );
}

export default AdaptiveTuner;
