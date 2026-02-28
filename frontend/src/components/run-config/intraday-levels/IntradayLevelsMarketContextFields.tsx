import type { IntradayLevelsSectionProps } from "./intradayLevelsShared";

export function IntradayLevelsMarketContextFields({
  config,
  handleChange,
}: IntradayLevelsSectionProps) {
  return (
    <>
          <div className="form-group">
            <label className="field-row" htmlFor="intraday_levels_spike_detection_enabled">
              <span>Enable Spike High/Low Levels</span>
              <input
                id="intraday_levels_spike_detection_enabled"
                type="checkbox"
                checked={!!config.intraday_levels_spike_detection_enabled}
                onChange={(e) =>
                  handleChange("intraday_levels_spike_detection_enabled", e.target.checked)
                }
              />
            </label>
          </div>
          <div className="form-group">
            <label htmlFor="intraday_levels_spike_min_wick_ratio">Spike Min Wick Ratio</label>
            <input
              id="intraday_levels_spike_min_wick_ratio"
              type="number"
              min="0.4"
              max="0.95"
              step="0.01"
              value={config.intraday_levels_spike_min_wick_ratio ?? ""}
              onChange={(e) =>
                handleChange(
                  "intraday_levels_spike_min_wick_ratio",
                  Math.min(0.95, Math.max(0.4, Number(e.target.value))),
                )
              }
            />
          </div>
          <div className="form-group">
            <label className="field-row" htmlFor="intraday_levels_prior_day_anchors_enabled">
              <span>Enable Prior-Day Anchors (PDH/PDL/PDC)</span>
              <input
                id="intraday_levels_prior_day_anchors_enabled"
                type="checkbox"
                checked={!!config.intraday_levels_prior_day_anchors_enabled}
                onChange={(e) =>
                  handleChange("intraday_levels_prior_day_anchors_enabled", e.target.checked)
                }
              />
            </label>
          </div>
          <div className="form-group">
            <label className="field-row" htmlFor="intraday_levels_gap_analysis_enabled">
              <span>Enable Gap Analysis</span>
              <input
                id="intraday_levels_gap_analysis_enabled"
                type="checkbox"
                checked={!!config.intraday_levels_gap_analysis_enabled}
                onChange={(e) =>
                  handleChange("intraday_levels_gap_analysis_enabled", e.target.checked)
                }
              />
            </label>
          </div>
          <div className="form-group">
            <label htmlFor="intraday_levels_gap_min_pct">Gap Min (%)</label>
            <input
              id="intraday_levels_gap_min_pct"
              type="number"
              min="0"
              step="0.01"
              value={config.intraday_levels_gap_min_pct ?? ""}
              onChange={(e) =>
                handleChange("intraday_levels_gap_min_pct", Math.max(0, Number(e.target.value)))
              }
            />
          </div>
          <div className="form-group">
            <label htmlFor="intraday_levels_gap_momentum_threshold_pct">Gap Momentum Threshold (%)</label>
            <input
              id="intraday_levels_gap_momentum_threshold_pct"
              type="number"
              min="0.1"
              step="0.1"
              value={config.intraday_levels_gap_momentum_threshold_pct ?? ""}
              onChange={(e) =>
                handleChange(
                  "intraday_levels_gap_momentum_threshold_pct",
                  Math.max(0.1, Number(e.target.value)),
                )
              }
            />
          </div>
          <div className="form-group">
            <label className="field-row" htmlFor="intraday_levels_rvol_filter_enabled">
              <span>Enable RVOL Filter</span>
              <input
                id="intraday_levels_rvol_filter_enabled"
                type="checkbox"
                checked={!!config.intraday_levels_rvol_filter_enabled}
                onChange={(e) =>
                  handleChange("intraday_levels_rvol_filter_enabled", e.target.checked)
                }
              />
            </label>
          </div>
          <div className="form-group">
            <label htmlFor="intraday_levels_rvol_lookback_bars">RVOL Lookback Bars</label>
            <input
              id="intraday_levels_rvol_lookback_bars"
              type="number"
              min="5"
              step="1"
              value={config.intraday_levels_rvol_lookback_bars ?? ""}
              onChange={(e) =>
                handleChange(
                  "intraday_levels_rvol_lookback_bars",
                  Math.max(5, Math.trunc(Number(e.target.value))),
                )
              }
            />
          </div>
          <div className="form-group">
            <label htmlFor="intraday_levels_rvol_min_threshold">RVOL Min Threshold</label>
            <input
              id="intraday_levels_rvol_min_threshold"
              type="number"
              min="0"
              step="0.05"
              value={config.intraday_levels_rvol_min_threshold ?? ""}
              onChange={(e) =>
                handleChange(
                  "intraday_levels_rvol_min_threshold",
                  Math.max(0, Number(e.target.value)),
                )
              }
            />
          </div>
          <div className="form-group">
            <label htmlFor="intraday_levels_rvol_strong_threshold">RVOL Strong Threshold</label>
            <input
              id="intraday_levels_rvol_strong_threshold"
              type="number"
              min="0.1"
              step="0.1"
              value={config.intraday_levels_rvol_strong_threshold ?? ""}
              onChange={(e) =>
                handleChange(
                  "intraday_levels_rvol_strong_threshold",
                  Math.max(0.1, Number(e.target.value)),
                )
              }
            />
          </div>
          <div className="form-group">
            <label className="field-row" htmlFor="intraday_levels_adaptive_window_enabled">
              <span>Enable Adaptive Time Window</span>
              <input
                id="intraday_levels_adaptive_window_enabled"
                type="checkbox"
                checked={!!config.intraday_levels_adaptive_window_enabled}
                onChange={(e) =>
                  handleChange("intraday_levels_adaptive_window_enabled", e.target.checked)
                }
              />
            </label>
          </div>
          <div className="form-group">
            <label htmlFor="intraday_levels_adaptive_window_min_bars">Adaptive Window Min Bars</label>
            <input
              id="intraday_levels_adaptive_window_min_bars"
              type="number"
              min="1"
              step="1"
              value={config.intraday_levels_adaptive_window_min_bars ?? ""}
              onChange={(e) =>
                handleChange(
                  "intraday_levels_adaptive_window_min_bars",
                  Math.max(1, Math.trunc(Number(e.target.value))),
                )
              }
            />
          </div>
          <div className="form-group">
            <label htmlFor="intraday_levels_adaptive_window_rvol_threshold">Adaptive Window RVOL Threshold</label>
            <input
              id="intraday_levels_adaptive_window_rvol_threshold"
              type="number"
              min="0"
              step="0.05"
              value={config.intraday_levels_adaptive_window_rvol_threshold ?? ""}
              onChange={(e) =>
                handleChange(
                  "intraday_levels_adaptive_window_rvol_threshold",
                  Math.max(0, Number(e.target.value)),
                )
              }
            />
          </div>
          <div className="form-group">
            <label htmlFor="intraday_levels_adaptive_window_atr_ratio_max">Adaptive Window ATR Ratio Max</label>
            <input
              id="intraday_levels_adaptive_window_atr_ratio_max"
              type="number"
              min="0.1"
              step="0.1"
              value={config.intraday_levels_adaptive_window_atr_ratio_max ?? ""}
              onChange={(e) =>
                handleChange(
                  "intraday_levels_adaptive_window_atr_ratio_max",
                  Math.max(0.1, Number(e.target.value)),
                )
              }
            />
          </div>
          <div className="form-group">
            <label className="field-row" htmlFor="intraday_levels_micro_confirmation_enabled">
              <span>Enable 2-Bar Micro Confirmation</span>
              <input
                id="intraday_levels_micro_confirmation_enabled"
                type="checkbox"
                checked={!!config.intraday_levels_micro_confirmation_enabled}
                onChange={(e) =>
                  handleChange("intraday_levels_micro_confirmation_enabled", e.target.checked)
                }
              />
            </label>
          </div>
          <div className="form-group">
            <label htmlFor="intraday_levels_micro_confirmation_bars">Micro Confirmation Bars</label>
            <input
              id="intraday_levels_micro_confirmation_bars"
              type="number"
              min="1"
              step="1"
              value={config.intraday_levels_micro_confirmation_bars ?? ""}
              onChange={(e) =>
                handleChange(
                  "intraday_levels_micro_confirmation_bars",
                  Math.max(1, Math.trunc(Number(e.target.value))),
                )
              }
            />
          </div>
          <div className="form-group">
            <label className="field-row" htmlFor="intraday_levels_confluence_sizing_enabled">
              <span>Enable Confluence-Based Position Sizing</span>
              <input
                id="intraday_levels_confluence_sizing_enabled"
                type="checkbox"
                checked={!!config.intraday_levels_confluence_sizing_enabled}
                onChange={(e) =>
                  handleChange("intraday_levels_confluence_sizing_enabled", e.target.checked)
                }
              />
            </label>
          </div>
    </>
  );
}
