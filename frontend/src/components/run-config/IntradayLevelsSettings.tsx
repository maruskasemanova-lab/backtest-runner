import React from "react";

interface IntradayLevelsSettingsProps {
  config: Record<string, any>;
  handleChange: (field: string, value: any) => void;
}

export function IntradayLevelsSettings({ config, handleChange }: IntradayLevelsSettingsProps) {
  return (
    <div id="intraday_levels_section" className="tw-panel">
      <div className="tw-panel-title">Intraday Levels Tracker</div>
      <div className="tw-panel-hint">
        Session S/R + volume profile context with optional multi-day memory, opening-range anchors, POC migration, and composite profile.
      </div>
      <div className="form-group">
        <label className="field-row" htmlFor="intraday_levels_enabled">
          <span>Enable Intraday Levels Tracker</span>
          <input
            id="intraday_levels_enabled"
            type="checkbox"
            checked={!!config.intraday_levels_enabled}
            onChange={(e) => handleChange("intraday_levels_enabled", e.target.checked)}
          />
        </label>
      </div>
      {config.intraday_levels_enabled && (
        <div className="tw-grid-fit-190">
          <div className="form-group">
            <label htmlFor="intraday_levels_swing_left_bars">Swing Left Bars</label>
            <input
              id="intraday_levels_swing_left_bars"
              type="number"
              min="1"
              step="1"
              value={config.intraday_levels_swing_left_bars ?? ""}
              onChange={(e) =>
                handleChange(
                  "intraday_levels_swing_left_bars",
                  Math.max(1, Math.trunc(Number(e.target.value))),
                )
              }
            />
          </div>
          <div className="form-group">
            <label htmlFor="intraday_levels_swing_right_bars">Swing Right Bars</label>
            <input
              id="intraday_levels_swing_right_bars"
              type="number"
              min="1"
              step="1"
              value={config.intraday_levels_swing_right_bars ?? ""}
              onChange={(e) =>
                handleChange(
                  "intraday_levels_swing_right_bars",
                  Math.max(1, Math.trunc(Number(e.target.value))),
                )
              }
            />
          </div>
          <div className="form-group">
            <label htmlFor="intraday_levels_test_tolerance_pct">Test Tolerance (%)</label>
            <input
              id="intraday_levels_test_tolerance_pct"
              type="number"
              min="0"
              step="0.01"
              value={config.intraday_levels_test_tolerance_pct ?? ""}
              onChange={(e) =>
                handleChange("intraday_levels_test_tolerance_pct", Math.max(0, Number(e.target.value)))
              }
            />
          </div>
          <div className="form-group">
            <label htmlFor="intraday_levels_break_tolerance_pct">Break Tolerance (%)</label>
            <input
              id="intraday_levels_break_tolerance_pct"
              type="number"
              min="0"
              step="0.01"
              value={config.intraday_levels_break_tolerance_pct ?? ""}
              onChange={(e) =>
                handleChange("intraday_levels_break_tolerance_pct", Math.max(0, Number(e.target.value)))
              }
            />
          </div>
          <div className="form-group">
            <label htmlFor="intraday_levels_breakout_volume_lookback">Breakout Volume Lookback</label>
            <input
              id="intraday_levels_breakout_volume_lookback"
              type="number"
              min="2"
              step="1"
              value={config.intraday_levels_breakout_volume_lookback ?? ""}
              onChange={(e) =>
                handleChange(
                  "intraday_levels_breakout_volume_lookback",
                  Math.max(2, Math.trunc(Number(e.target.value))),
                )
              }
            />
          </div>
          <div className="form-group">
            <label htmlFor="intraday_levels_breakout_volume_multiplier">Breakout Volume Multiplier</label>
            <input
              id="intraday_levels_breakout_volume_multiplier"
              type="number"
              min="1"
              step="0.05"
              value={config.intraday_levels_breakout_volume_multiplier ?? ""}
              onChange={(e) =>
                handleChange(
                  "intraday_levels_breakout_volume_multiplier",
                  Math.max(1, Number(e.target.value)),
                )
              }
            />
          </div>
          <div className="form-group">
            <label htmlFor="intraday_levels_volume_profile_bin_size_pct">Volume Profile Bin Size (%)</label>
            <input
              id="intraday_levels_volume_profile_bin_size_pct"
              type="number"
              min="0.01"
              step="0.01"
              value={config.intraday_levels_volume_profile_bin_size_pct ?? ""}
              onChange={(e) =>
                handleChange(
                  "intraday_levels_volume_profile_bin_size_pct",
                  Math.max(0.01, Number(e.target.value)),
                )
              }
            />
          </div>
          <div className="form-group">
            <label htmlFor="intraday_levels_value_area_pct">Value Area Coverage (0-1)</label>
            <input
              id="intraday_levels_value_area_pct"
              type="number"
              min="0.5"
              max="0.95"
              step="0.01"
              value={config.intraday_levels_value_area_pct ?? ""}
              onChange={(e) =>
                handleChange(
                  "intraday_levels_value_area_pct",
                  Math.min(0.95, Math.max(0.5, Number(e.target.value))),
                )
              }
            />
          </div>
          <div className="form-group">
            <label className="field-row" htmlFor="intraday_levels_entry_quality_enabled">
              <span>Enable Entry Quality Gate</span>
              <input
                id="intraday_levels_entry_quality_enabled"
                type="checkbox"
                checked={!!config.intraday_levels_entry_quality_enabled}
                onChange={(e) =>
                  handleChange("intraday_levels_entry_quality_enabled", e.target.checked)
                }
              />
            </label>
          </div>
          <div className="form-group">
            <label htmlFor="intraday_levels_min_levels_for_context">Min Levels For Context</label>
            <input
              id="intraday_levels_min_levels_for_context"
              type="number"
              min="1"
              step="1"
              value={config.intraday_levels_min_levels_for_context ?? ""}
              onChange={(e) =>
                handleChange(
                  "intraday_levels_min_levels_for_context",
                  Math.max(1, Math.trunc(Number(e.target.value))),
                )
              }
            />
          </div>
          <div className="form-group">
            <label htmlFor="intraday_levels_entry_tolerance_pct">Entry Tolerance (%)</label>
            <input
              id="intraday_levels_entry_tolerance_pct"
              type="number"
              min="0.01"
              step="0.01"
              value={config.intraday_levels_entry_tolerance_pct ?? ""}
              onChange={(e) =>
                handleChange(
                  "intraday_levels_entry_tolerance_pct",
                  Math.max(0.01, Number(e.target.value)),
                )
              }
            />
          </div>
          <div className="form-group">
            <label htmlFor="intraday_levels_break_cooldown_bars">Break Cooldown (bars)</label>
            <input
              id="intraday_levels_break_cooldown_bars"
              type="number"
              min="1"
              step="1"
              value={config.intraday_levels_break_cooldown_bars ?? ""}
              onChange={(e) =>
                handleChange(
                  "intraday_levels_break_cooldown_bars",
                  Math.max(1, Math.trunc(Number(e.target.value))),
                )
              }
            />
          </div>
          <div className="form-group">
            <label htmlFor="intraday_levels_rotation_max_tests">Rotation Max Tests</label>
            <input
              id="intraday_levels_rotation_max_tests"
              type="number"
              min="1"
              step="1"
              value={config.intraday_levels_rotation_max_tests ?? ""}
              onChange={(e) =>
                handleChange(
                  "intraday_levels_rotation_max_tests",
                  Math.max(1, Math.trunc(Number(e.target.value))),
                )
              }
            />
          </div>
          <div className="form-group">
            <label htmlFor="intraday_levels_rotation_volume_max_ratio">Rotation Volume Ratio Max</label>
            <input
              id="intraday_levels_rotation_volume_max_ratio"
              type="number"
              min="0.1"
              max="2"
              step="0.01"
              value={config.intraday_levels_rotation_volume_max_ratio ?? ""}
              onChange={(e) =>
                handleChange(
                  "intraday_levels_rotation_volume_max_ratio",
                  Math.min(2, Math.max(0.1, Number(e.target.value))),
                )
              }
            />
          </div>
          <div className="form-group">
            <label htmlFor="intraday_levels_recent_bounce_lookback_bars">Recent Bounce Lookback</label>
            <input
              id="intraday_levels_recent_bounce_lookback_bars"
              type="number"
              min="1"
              step="1"
              value={config.intraday_levels_recent_bounce_lookback_bars ?? ""}
              onChange={(e) =>
                handleChange(
                  "intraday_levels_recent_bounce_lookback_bars",
                  Math.max(1, Math.trunc(Number(e.target.value))),
                )
              }
            />
          </div>
          <div className="form-group">
            <label className="field-row" htmlFor="intraday_levels_require_recent_bounce_for_mean_reversion">
              <span>MR Requires Recent Bounce</span>
              <input
                id="intraday_levels_require_recent_bounce_for_mean_reversion"
                type="checkbox"
                checked={!!config.intraday_levels_require_recent_bounce_for_mean_reversion}
                onChange={(e) =>
                  handleChange(
                    "intraday_levels_require_recent_bounce_for_mean_reversion",
                    e.target.checked,
                  )
                }
              />
            </label>
          </div>
          <div className="form-group">
            <label htmlFor="intraday_levels_momentum_break_max_age_bars">Momentum Break Max Age</label>
            <input
              id="intraday_levels_momentum_break_max_age_bars"
              type="number"
              min="1"
              step="1"
              value={config.intraday_levels_momentum_break_max_age_bars ?? ""}
              onChange={(e) =>
                handleChange(
                  "intraday_levels_momentum_break_max_age_bars",
                  Math.max(1, Math.trunc(Number(e.target.value))),
                )
              }
            />
          </div>
          <div className="form-group">
            <label htmlFor="intraday_levels_momentum_min_room_pct">Momentum Min Room (%)</label>
            <input
              id="intraday_levels_momentum_min_room_pct"
              type="number"
              min="0.01"
              step="0.01"
              value={config.intraday_levels_momentum_min_room_pct ?? ""}
              onChange={(e) =>
                handleChange(
                  "intraday_levels_momentum_min_room_pct",
                  Math.max(0.01, Number(e.target.value)),
                )
              }
            />
          </div>
          <div className="form-group">
            <label htmlFor="intraday_levels_momentum_min_broken_ratio">Momentum Min Broken Ratio</label>
            <input
              id="intraday_levels_momentum_min_broken_ratio"
              type="number"
              min="0"
              max="1"
              step="0.01"
              value={config.intraday_levels_momentum_min_broken_ratio ?? ""}
              onChange={(e) =>
                handleChange(
                  "intraday_levels_momentum_min_broken_ratio",
                  Math.min(1, Math.max(0, Number(e.target.value))),
                )
              }
            />
          </div>
          <div className="form-group">
            <label htmlFor="intraday_levels_min_confluence_score">Min Confluence Score</label>
            <input
              id="intraday_levels_min_confluence_score"
              type="number"
              min="1"
              step="1"
              value={config.intraday_levels_min_confluence_score ?? ""}
              onChange={(e) =>
                handleChange(
                  "intraday_levels_min_confluence_score",
                  Math.max(1, Math.trunc(Number(e.target.value))),
                )
              }
            />
          </div>
          <div className="form-group">
            <label className="field-row" htmlFor="intraday_levels_memory_enabled">
              <span>Enable Multi-Day Level Memory</span>
              <input
                id="intraday_levels_memory_enabled"
                type="checkbox"
                checked={!!config.intraday_levels_memory_enabled}
                onChange={(e) =>
                  handleChange("intraday_levels_memory_enabled", e.target.checked)
                }
              />
            </label>
          </div>
          <div className="form-group">
            <label htmlFor="intraday_levels_memory_min_tests">Memory Min Tests</label>
            <input
              id="intraday_levels_memory_min_tests"
              type="number"
              min="1"
              step="1"
              value={config.intraday_levels_memory_min_tests ?? ""}
              onChange={(e) =>
                handleChange(
                  "intraday_levels_memory_min_tests",
                  Math.max(1, Math.trunc(Number(e.target.value))),
                )
              }
            />
          </div>
          <div className="form-group">
            <label htmlFor="intraday_levels_memory_max_age_days">Memory Max Age (days)</label>
            <input
              id="intraday_levels_memory_max_age_days"
              type="number"
              min="1"
              step="1"
              value={config.intraday_levels_memory_max_age_days ?? ""}
              onChange={(e) =>
                handleChange(
                  "intraday_levels_memory_max_age_days",
                  Math.max(1, Math.trunc(Number(e.target.value))),
                )
              }
            />
          </div>
          <div className="form-group">
            <label htmlFor="intraday_levels_memory_decay_after_days">Memory Decay After (days)</label>
            <input
              id="intraday_levels_memory_decay_after_days"
              type="number"
              min="1"
              step="1"
              value={config.intraday_levels_memory_decay_after_days ?? ""}
              onChange={(e) =>
                handleChange(
                  "intraday_levels_memory_decay_after_days",
                  Math.max(1, Math.trunc(Number(e.target.value))),
                )
              }
            />
          </div>
          <div className="form-group">
            <label htmlFor="intraday_levels_memory_decay_weight">Memory Decay Weight</label>
            <input
              id="intraday_levels_memory_decay_weight"
              type="number"
              min="0.1"
              max="1"
              step="0.01"
              value={config.intraday_levels_memory_decay_weight ?? ""}
              onChange={(e) =>
                handleChange(
                  "intraday_levels_memory_decay_weight",
                  Math.min(1, Math.max(0.1, Number(e.target.value))),
                )
              }
            />
          </div>
          <div className="form-group">
            <label htmlFor="intraday_levels_memory_max_levels">Memory Max Levels</label>
            <input
              id="intraday_levels_memory_max_levels"
              type="number"
              min="1"
              step="1"
              value={config.intraday_levels_memory_max_levels ?? ""}
              onChange={(e) =>
                handleChange(
                  "intraday_levels_memory_max_levels",
                  Math.max(1, Math.trunc(Number(e.target.value))),
                )
              }
            />
          </div>
          <div className="form-group">
            <label className="field-row" htmlFor="intraday_levels_opening_range_enabled">
              <span>Enable Opening Range Anchors</span>
              <input
                id="intraday_levels_opening_range_enabled"
                type="checkbox"
                checked={!!config.intraday_levels_opening_range_enabled}
                onChange={(e) =>
                  handleChange("intraday_levels_opening_range_enabled", e.target.checked)
                }
              />
            </label>
          </div>
          <div className="form-group">
            <label htmlFor="intraday_levels_opening_range_minutes">Opening Range Minutes</label>
            <input
              id="intraday_levels_opening_range_minutes"
              type="number"
              min="5"
              step="1"
              value={config.intraday_levels_opening_range_minutes ?? ""}
              onChange={(e) =>
                handleChange(
                  "intraday_levels_opening_range_minutes",
                  Math.max(5, Math.trunc(Number(e.target.value))),
                )
              }
            />
          </div>
          <div className="form-group">
            <label htmlFor="intraday_levels_opening_range_break_tolerance_pct">OR Break Tolerance (%)</label>
            <input
              id="intraday_levels_opening_range_break_tolerance_pct"
              type="number"
              min="0.01"
              step="0.01"
              value={config.intraday_levels_opening_range_break_tolerance_pct ?? ""}
              onChange={(e) =>
                handleChange(
                  "intraday_levels_opening_range_break_tolerance_pct",
                  Math.max(0.01, Number(e.target.value)),
                )
              }
            />
          </div>
          <div className="form-group">
            <label className="field-row" htmlFor="intraday_levels_poc_migration_enabled">
              <span>Enable POC Migration Tracking</span>
              <input
                id="intraday_levels_poc_migration_enabled"
                type="checkbox"
                checked={!!config.intraday_levels_poc_migration_enabled}
                onChange={(e) =>
                  handleChange("intraday_levels_poc_migration_enabled", e.target.checked)
                }
              />
            </label>
          </div>
          <div className="form-group">
            <label htmlFor="intraday_levels_poc_migration_interval_bars">POC Interval (bars)</label>
            <input
              id="intraday_levels_poc_migration_interval_bars"
              type="number"
              min="1"
              step="1"
              value={config.intraday_levels_poc_migration_interval_bars ?? ""}
              onChange={(e) =>
                handleChange(
                  "intraday_levels_poc_migration_interval_bars",
                  Math.max(1, Math.trunc(Number(e.target.value))),
                )
              }
            />
          </div>
          <div className="form-group">
            <label htmlFor="intraday_levels_poc_migration_trend_threshold_pct">POC Trend Threshold (%)</label>
            <input
              id="intraday_levels_poc_migration_trend_threshold_pct"
              type="number"
              min="0.01"
              step="0.01"
              value={config.intraday_levels_poc_migration_trend_threshold_pct ?? ""}
              onChange={(e) =>
                handleChange(
                  "intraday_levels_poc_migration_trend_threshold_pct",
                  Math.max(0.01, Number(e.target.value)),
                )
              }
            />
          </div>
          <div className="form-group">
            <label htmlFor="intraday_levels_poc_migration_range_threshold_pct">POC Range Threshold (%)</label>
            <input
              id="intraday_levels_poc_migration_range_threshold_pct"
              type="number"
              min="0.01"
              step="0.01"
              value={config.intraday_levels_poc_migration_range_threshold_pct ?? ""}
              onChange={(e) =>
                handleChange(
                  "intraday_levels_poc_migration_range_threshold_pct",
                  Math.max(0.01, Number(e.target.value)),
                )
              }
            />
          </div>
          <div className="form-group">
            <label className="field-row" htmlFor="intraday_levels_composite_profile_enabled">
              <span>Enable Composite Volume Profile</span>
              <input
                id="intraday_levels_composite_profile_enabled"
                type="checkbox"
                checked={!!config.intraday_levels_composite_profile_enabled}
                onChange={(e) =>
                  handleChange("intraday_levels_composite_profile_enabled", e.target.checked)
                }
              />
            </label>
          </div>
          <div className="form-group">
            <label htmlFor="intraday_levels_composite_profile_days">Composite Days</label>
            <input
              id="intraday_levels_composite_profile_days"
              type="number"
              min="1"
              step="1"
              value={config.intraday_levels_composite_profile_days ?? ""}
              onChange={(e) =>
                handleChange(
                  "intraday_levels_composite_profile_days",
                  Math.max(1, Math.trunc(Number(e.target.value))),
                )
              }
            />
          </div>
          <div className="form-group">
            <label htmlFor="intraday_levels_composite_profile_current_day_weight">Composite Current-Day Weight</label>
            <input
              id="intraday_levels_composite_profile_current_day_weight"
              type="number"
              min="0.1"
              step="0.05"
              value={config.intraday_levels_composite_profile_current_day_weight ?? ""}
              onChange={(e) =>
                handleChange(
                  "intraday_levels_composite_profile_current_day_weight",
                  Math.max(0.1, Number(e.target.value)),
                )
              }
            />
          </div>
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
        </div>
      )}
    </div>
  );
}
