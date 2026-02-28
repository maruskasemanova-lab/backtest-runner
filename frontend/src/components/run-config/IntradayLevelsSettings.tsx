import { IntradayLevelsCoreFields } from "./intraday-levels/IntradayLevelsCoreFields";
import { IntradayLevelsMarketContextFields } from "./intraday-levels/IntradayLevelsMarketContextFields";
import { IntradayLevelsMemoryAndProfileFields } from "./intraday-levels/IntradayLevelsMemoryAndProfileFields";

interface IntradayLevelsSettingsProps {
  config: Record<string, any>;
  handleChange: (field: string, value: any) => void;
}

export function IntradayLevelsSettings({
  config,
  handleChange,
}: IntradayLevelsSettingsProps) {
  return (
    <div id="intraday_levels_section" className="tw-panel">
      <div className="tw-panel-title">Intraday Levels Tracker</div>
      <div className="tw-panel-hint">
        Session S/R + volume profile context with optional multi-day memory,
        opening-range anchors, POC migration, and composite profile.
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
          <IntradayLevelsCoreFields config={config} handleChange={handleChange} />
          <IntradayLevelsMemoryAndProfileFields
            config={config}
            handleChange={handleChange}
          />
          <IntradayLevelsMarketContextFields
            config={config}
            handleChange={handleChange}
          />
        </div>
      )}
    </div>
  );
}
