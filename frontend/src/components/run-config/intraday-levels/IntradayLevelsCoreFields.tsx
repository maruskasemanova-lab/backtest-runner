import type { IntradayLevelsSectionProps } from "./intradayLevelsShared";

export function IntradayLevelsCoreFields({
  config,
  handleChange,
}: IntradayLevelsSectionProps) {
  return (
    <>
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
    </>
  );
}
