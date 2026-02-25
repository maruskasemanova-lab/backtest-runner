type Props = {
  strategySelectionMode: string;
  maxActiveStrategiesValue: number;
  flowBiasEnabled: boolean;
  useOhlcvFallbacks: boolean;
  minActiveBarsBeforeSwitchValue: number;
  switchCooldownBarsValue: number;
  onStrategySelectionModeChange: (value: string) => void;
  onMaxActiveStrategiesChange: (value: string) => void;
  onFlowBiasEnabledChange: (checked: boolean) => void;
  onUseOhlcvFallbacksChange: (checked: boolean) => void;
  onMinActiveBarsBeforeSwitchChange: (value: string) => void;
  onSwitchCooldownBarsChange: (value: string) => void;
};

export default function AdaptiveStudioSelectionFlowGate({
  strategySelectionMode,
  maxActiveStrategiesValue,
  flowBiasEnabled,
  useOhlcvFallbacks,
  minActiveBarsBeforeSwitchValue,
  switchCooldownBarsValue,
  onStrategySelectionModeChange,
  onMaxActiveStrategiesChange,
  onFlowBiasEnabledChange,
  onUseOhlcvFallbacksChange,
  onMinActiveBarsBeforeSwitchChange,
  onSwitchCooldownBarsChange,
}: Props) {
  return (
    <div className="adaptive-grid-2col">
      <div className="adaptive-section">
        <h3>Selection Mode</h3>
        <div className="form-group">
          <label htmlFor="adaptive_mode">Strategy selection mode</label>
          <select
            id="adaptive_mode"
            value={strategySelectionMode}
            onChange={(e) => onStrategySelectionModeChange(e.target.value)}
          >
            <option value="adaptive_top_n">Adaptive Top-N</option>
            <option value="all_enabled">All Enabled</option>
          </select>
        </div>
        <div className="form-group">
          <label htmlFor="adaptive_max_active">Max active strategies</label>
          <input
            id="adaptive_max_active"
            type="number"
            min="1"
            max="20"
            step="1"
            value={maxActiveStrategiesValue}
            onChange={(e) => onMaxActiveStrategiesChange(e.target.value)}
            disabled={strategySelectionMode === "all_enabled"}
          />
        </div>
      </div>

      <div className="adaptive-section">
        <h3>Flow Gate</h3>
        <label className="field-row" htmlFor="adaptive_flow_bias_enabled">
          <span>Prefer flow strategies when L2 exists</span>
          <input
            id="adaptive_flow_bias_enabled"
            type="checkbox"
            checked={flowBiasEnabled}
            onChange={(e) => onFlowBiasEnabledChange(e.target.checked)}
          />
        </label>
        <label className="field-row" htmlFor="adaptive_ohlcv_fallbacks">
          <span>OHLCV fallback when no L2</span>
          <input
            id="adaptive_ohlcv_fallbacks"
            type="checkbox"
            checked={useOhlcvFallbacks}
            onChange={(e) => onUseOhlcvFallbacksChange(e.target.checked)}
          />
        </label>
        <div className="form-group">
          <label htmlFor="adaptive_min_active_bars">Hysteresis (bars)</label>
          <input
            id="adaptive_min_active_bars"
            type="number"
            min="0"
            step="1"
            value={minActiveBarsBeforeSwitchValue}
            onChange={(e) => onMinActiveBarsBeforeSwitchChange(e.target.value)}
          />
        </div>
        <div className="form-group">
          <label htmlFor="adaptive_switch_cooldown_bars">Cooldown (bars)</label>
          <input
            id="adaptive_switch_cooldown_bars"
            type="number"
            min="0"
            step="1"
            value={switchCooldownBarsValue}
            onChange={(e) => onSwitchCooldownBarsChange(e.target.value)}
          />
        </div>
      </div>
    </div>
  );
}
