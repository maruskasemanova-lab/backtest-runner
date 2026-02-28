import type { IntradayLevelsSectionProps } from "./intradayLevelsShared";

export function IntradayLevelsMemoryAndProfileFields({
  config,
  handleChange,
}: IntradayLevelsSectionProps) {
  return (
    <>
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
    </>
  );
}
