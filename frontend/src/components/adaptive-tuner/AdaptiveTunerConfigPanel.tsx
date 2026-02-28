import type { AdaptiveTunerControllerModel } from "./useAdaptiveTunerController";
import { formatRange } from "./adaptiveTunerViewHelpers";

type AdaptiveTunerConfigController = Pick<
  AdaptiveTunerControllerModel,
  | "form"
  | "setForm"
  | "tickerOptions"
  | "tickerOptionsList"
  | "loadingTickerOptions"
  | "isV2"
  | "effectiveTrialBudgetPreview"
  | "configPanelCollapsed"
  | "setConfigPanelCollapsed"
  | "submitting"
  | "handleStart"
  | "handleTickerChange"
>;

interface AdaptiveTunerConfigPanelProps {
  controller: AdaptiveTunerConfigController;
}

export function AdaptiveTunerConfigPanel({ controller }: AdaptiveTunerConfigPanelProps) {
  const {
    form,
    setForm,
    tickerOptions,
    tickerOptionsList,
    loadingTickerOptions,
    isV2,
    effectiveTrialBudgetPreview,
    configPanelCollapsed,
    setConfigPanelCollapsed,
    submitting,
    handleStart,
    handleTickerChange,
  } = controller;

  return (
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
                    onChange={(e) => setForm((prev) => ({ ...prev, quick_max_days: Number(e.target.value) }))}
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
                    onChange={(e) => setForm((prev) => ({ ...prev, quick_trial_boost: Number(e.target.value) }))}
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
                    onChange={(e) => setForm((prev) => ({ ...prev, switch_cooldown_bars_options: e.target.value }))}
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
                    onChange={(e) => setForm((prev) => ({ ...prev, ohlcv_fallback_options: e.target.value }))}
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
                    onChange={(e) => setForm((prev) => ({ ...prev, v2_regime_filter_sets: e.target.value }))}
                    placeholder="TRENDING;TRENDING,MIXED;TRENDING,MIXED,CHOPPY"
                  />
                </div>
                <div className="tuner-form-grid">
                  <div className="form-group">
                    <label htmlFor="tuner_v2_imbalance">L2 min_imbalance</label>
                    <input
                      id="tuner_v2_imbalance"
                      value={form.v2_l2_min_imbalance}
                      onChange={(e) => setForm((prev) => ({ ...prev, v2_l2_min_imbalance: e.target.value }))}
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
                      onChange={(e) => setForm((prev) => ({ ...prev, v2_atr_stop_multiplier: e.target.value }))}
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
  );
}
