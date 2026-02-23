import React from "react";
import { SHOW_RUN_CONFIG_ADVANCED_EXECUTION_CONTROLS } from "./runConfigHelpers";

interface RiskManagementSettingsProps {
  config: Record<string, any>;
  handleChange: (field: string, value: any) => void;
}

export function RiskManagementSettings({ config, handleChange }: RiskManagementSettingsProps) {
  if (!SHOW_RUN_CONFIG_ADVANCED_EXECUTION_CONTROLS) {
    return null;
  }

  return (
    <>
      <div className="tw-panel">
        <div className="tw-panel-title">Execution Sizing</div>
        <div className="tw-panel-hint">
          Tieto nastavenia riadia veľkosť pozície, fill realizmus a maximálnu dĺžku držania.
        </div>
        <div className="form-group">
          <label htmlFor="risk_per_trade_pct">Risk Per Trade (%)</label>
          <input
            id="risk_per_trade_pct"
            type="number"
            min="0.1"
            max="10"
            step="0.1"
            value={config.risk_per_trade_pct ?? ""}
            onChange={(e) => handleChange("risk_per_trade_pct", Number(e.target.value))}
          />
        </div>

        <div className="form-group">
          <label htmlFor="max_position_notional_pct">Max Position Notional (%)</label>
          <input
            id="max_position_notional_pct"
            type="number"
            min="1"
            max="100"
            step="1"
            value={config.max_position_notional_pct ?? ""}
            onChange={(e) => handleChange("max_position_notional_pct", Number(e.target.value))}
          />
        </div>

        <div className="form-group">
          <label htmlFor="max_fill_participation_rate">Max Fill Participation (0-1)</label>
          <input
            id="max_fill_participation_rate"
            type="number"
            min="0.01"
            max="1"
            step="0.01"
            value={config.max_fill_participation_rate ?? ""}
            onChange={(e) => handleChange("max_fill_participation_rate", Number(e.target.value))}
          />
        </div>

        <div className="form-group">
          <label htmlFor="min_fill_ratio">Min Fill Ratio (0-1)</label>
          <input
            id="min_fill_ratio"
            type="number"
            min="0.01"
            max="1"
            step="0.01"
            value={config.min_fill_ratio ?? ""}
            onChange={(e) => handleChange("min_fill_ratio", Number(e.target.value))}
          />
        </div>

        <div className="form-group">
          <label htmlFor="time_exit_bars">Time Exit (bars)</label>
          <input
            id="time_exit_bars"
            type="number"
            min="1"
            step="1"
            value={config.time_exit_bars ?? ""}
            onChange={(e) => handleChange("time_exit_bars", Number(e.target.value))}
          />
        </div>
      </div>

      {/* Context-Aware Risk Management */}
      <div className="tw-panel">
        <div className="tw-panel-title">Context-Aware Risk (Level-Anchored SL/TP)</div>
        <div className="tw-panel-hint">
          Prispôsobí SL a TP podľa najbližších S/R úrovní.
        </div>
        <div className="form-group">
          <label className="field-row" htmlFor="context_aware_risk_enabled">
            <span>Enable Context-Aware Risk</span>
            <input
              id="context_aware_risk_enabled"
              type="checkbox"
              checked={!!config.context_aware_risk_enabled}
              onChange={(e) => handleChange("context_aware_risk_enabled", e.target.checked)}
            />
          </label>
        </div>
        
        {config.context_aware_risk_enabled && (
          <div className="tw-grid-fit-190" style={{ paddingTop: 4 }}>
            <div className="form-group">
              <label htmlFor="context_risk_sl_buffer_pct">SL Buffer (%)</label>
              <input
                id="context_risk_sl_buffer_pct"
                type="number"
                min="0"
                step="0.01"
                value={config.context_risk_sl_buffer_pct ?? ""}
                onChange={(e) =>
                  handleChange("context_risk_sl_buffer_pct", Math.max(0, Number(e.target.value)))
                }
              />
            </div>
            <div className="form-group">
              <label htmlFor="context_risk_min_sl_pct">Min SL Floor (%)</label>
              <input
                id="context_risk_min_sl_pct"
                type="number"
                min="0"
                step="0.01"
                value={config.context_risk_min_sl_pct ?? ""}
                onChange={(e) =>
                  handleChange("context_risk_min_sl_pct", Math.max(0, Number(e.target.value)))
                }
              />
            </div>
            <div className="form-group">
              <label htmlFor="context_risk_min_room_pct">Min Room (%)</label>
              <input
                id="context_risk_min_room_pct"
                type="number"
                min="0"
                step="0.01"
                value={config.context_risk_min_room_pct ?? ""}
                onChange={(e) =>
                  handleChange("context_risk_min_room_pct", Math.max(0, Number(e.target.value)))
                }
              />
            </div>
            <div className="form-group">
              <label htmlFor="context_risk_min_effective_rr">Min Effective RR</label>
              <input
                id="context_risk_min_effective_rr"
                type="number"
                min="0"
                step="0.1"
                value={config.context_risk_min_effective_rr ?? ""}
                onChange={(e) =>
                  handleChange("context_risk_min_effective_rr", Math.max(0, Number(e.target.value)))
                }
              />
            </div>
            <div className="form-group">
              <label htmlFor="context_risk_trailing_tighten_zone">Trailing Tighten Zone (0-1)</label>
              <input
                id="context_risk_trailing_tighten_zone"
                type="number"
                min="0"
                max="1"
                step="0.05"
                value={config.context_risk_trailing_tighten_zone ?? ""}
                onChange={(e) =>
                  handleChange(
                    "context_risk_trailing_tighten_zone",
                    Math.max(0, Math.min(1, Number(e.target.value))),
                  )
                }
              />
            </div>
            <div className="form-group">
              <label htmlFor="context_risk_trailing_tighten_factor">Trailing Tighten Factor (0-1)</label>
              <input
                id="context_risk_trailing_tighten_factor"
                type="number"
                min="0"
                max="1"
                step="0.05"
                value={config.context_risk_trailing_tighten_factor ?? ""}
                onChange={(e) =>
                  handleChange(
                    "context_risk_trailing_tighten_factor",
                    Math.max(0, Math.min(1, Number(e.target.value))),
                  )
                }
              />
            </div>
            <div className="form-group">
              <label htmlFor="context_risk_max_anchor_search_pct">Max Anchor Search (%)</label>
              <input
                id="context_risk_max_anchor_search_pct"
                type="number"
                min="0.1"
                step="0.1"
                value={config.context_risk_max_anchor_search_pct ?? ""}
                onChange={(e) =>
                  handleChange("context_risk_max_anchor_search_pct", Math.max(0.1, Number(e.target.value)))
                }
              />
            </div>
            <div className="form-group">
              <label htmlFor="context_risk_min_level_tests_for_sl">Min Level Tests for SL</label>
              <input
                id="context_risk_min_level_tests_for_sl"
                type="number"
                min="0"
                step="1"
                value={config.context_risk_min_level_tests_for_sl ?? ""}
                onChange={(e) =>
                  handleChange(
                    "context_risk_min_level_tests_for_sl",
                    Math.max(0, Math.trunc(Number(e.target.value))),
                  )
                }
              />
            </div>
            <div className="form-group">
              <label className="field-row" htmlFor="context_risk_level_trail_enabled">
                <span>Trail SL along levels</span>
                <input
                  id="context_risk_level_trail_enabled"
                  type="checkbox"
                  checked={!!config.context_risk_level_trail_enabled}
                  onChange={(e) => handleChange("context_risk_level_trail_enabled", e.target.checked)}
                />
              </label>
            </div>
          </div>
        )}
      </div>

      <div className="tw-panel">
        <div className="tw-panel-title">Stop-Loss And Break-Even</div>
        <div className="tw-panel-hint">
          `strategy` = stop zo stratégie, `fixed` = vždy fixné %, `capped` = prísnejší zo strategy/fixed.
        </div>
        <div className="form-group">
          <label htmlFor="stop_loss_mode">Stop-Loss Mode</label>
          <select
            id="stop_loss_mode"
            value={config.stop_loss_mode || "strategy"}
            onChange={(e) => handleChange("stop_loss_mode", e.target.value)}
          >
            <option value="strategy">strategy (use strategy stop)</option>
            <option value="fixed">fixed (always fixed % stop)</option>
            <option value="capped">capped (cap only wide stops)</option>
          </select>
        </div>

        <div className="form-group">
          <label htmlFor="fixed_stop_loss_pct">Fixed Stop-Loss (%)</label>
          <input
            id="fixed_stop_loss_pct"
            type="number"
            min="0.01"
            max="5"
            step="0.05"
            value={config.fixed_stop_loss_pct ?? ""}
            onChange={(e) => handleChange("fixed_stop_loss_pct", Number(e.target.value))}
            disabled={config.stop_loss_mode === "strategy"}
          />
        </div>
        <div className="form-group">
          <label htmlFor="trailing_stop_pct">Global Trailing Stop (%)</label>
          <input
            id="trailing_stop_pct"
            type="number"
            min="0"
            max="5"
            step="0.01"
            value={config.trailing_stop_pct ?? ""}
            onChange={(e) => handleChange("trailing_stop_pct", Number(e.target.value))}
          />
        </div>
        <div className="form-group">
          <label htmlFor="global_exit_rr_ratio">Global Exit RR Ratio</label>
          <input
            id="global_exit_rr_ratio"
            type="number"
            min="0"
            max="10"
            step="0.05"
            value={config.global_exit_rr_ratio ?? ""}
            onChange={(e) => handleChange("global_exit_rr_ratio", Number(e.target.value))}
          />
        </div>
        <div className="form-group">
          <label htmlFor="global_risk_atr_stop_multiplier">Global Risk ATR Stop Multiplier</label>
          <input
            id="global_risk_atr_stop_multiplier"
            type="number"
            min="0"
            max="10"
            step="0.05"
            value={config.global_risk_atr_stop_multiplier ?? ""}
            onChange={(e) =>
              handleChange("global_risk_atr_stop_multiplier", Number(e.target.value))
            }
          />
        </div>
        <div className="form-group">
          <label htmlFor="global_risk_volume_stop_pct">Global Risk Volume Stop (%)</label>
          <input
            id="global_risk_volume_stop_pct"
            type="number"
            min="0"
            max="10"
            step="0.05"
            value={config.global_risk_volume_stop_pct ?? ""}
            onChange={(e) => handleChange("global_risk_volume_stop_pct", Number(e.target.value))}
          />
        </div>
        <div className="form-group">
          <label htmlFor="global_risk_min_stop_loss_pct">Global Risk Min Stop-Loss (%)</label>
          <input
            id="global_risk_min_stop_loss_pct"
            type="number"
            min="0"
            max="5"
            step="0.01"
            value={config.global_risk_min_stop_loss_pct ?? ""}
            onChange={(e) =>
              handleChange("global_risk_min_stop_loss_pct", Number(e.target.value))
            }
          />
        </div>

        <div className="form-group">
          <label htmlFor="trailing_activation_pct">Trailing Activation (% MFE)</label>
          <input
            id="trailing_activation_pct"
            type="number"
            min="0"
            max="5"
            step="0.01"
            value={config.trailing_activation_pct ?? ""}
            onChange={(e) => handleChange("trailing_activation_pct", Number(e.target.value))}
          />
        </div>

        <div className="form-group">
          <label htmlFor="break_even_activation_min_mfe_pct">BE Activation Min MFE (%)</label>
          <input
            id="break_even_activation_min_mfe_pct"
            type="number"
            min="0"
            max="5"
            step="0.01"
            value={config.break_even_activation_min_mfe_pct ?? ""}
            onChange={(e) =>
              handleChange("break_even_activation_min_mfe_pct", Math.max(0, Number(e.target.value)))
            }
          />
        </div>
        <div className="form-group">
          <label className="field-row" htmlFor="break_even_activation_use_levels">
            <span>BE Require Levels Proof</span>
            <input
              id="break_even_activation_use_levels"
              type="checkbox"
              checked={config.break_even_activation_use_levels !== false}
              onChange={(e) => handleChange("break_even_activation_use_levels", e.target.checked)}
            />
          </label>
        </div>
        <div className="form-group">
          <label className="field-row" htmlFor="break_even_activation_use_l2">
            <span>BE Require L2 Proof</span>
            <input
              id="break_even_activation_use_l2"
              type="checkbox"
              checked={config.break_even_activation_use_l2 !== false}
              onChange={(e) => handleChange("break_even_activation_use_l2", e.target.checked)}
            />
          </label>
        </div>

        <div className="form-group">
          <label htmlFor="break_even_activation_min_r">BE Activation Min R</label>
          <input
            id="break_even_activation_min_r"
            type="number"
            min="0"
            max="5"
            step="0.1"
            value={config.break_even_activation_min_r ?? ""}
            onChange={(e) =>
              handleChange("break_even_activation_min_r", Math.max(0, Number(e.target.value)))
            }
          />
        </div>

        <div className="form-group">
          <label htmlFor="break_even_activation_min_r_trending_5m">BE Min R (Trending 5m)</label>
          <input
            id="break_even_activation_min_r_trending_5m"
            type="number"
            min="0"
            max="5"
            step="0.1"
            value={config.break_even_activation_min_r_trending_5m ?? ""}
            onChange={(e) =>
              handleChange("break_even_activation_min_r_trending_5m", Math.max(0, Number(e.target.value)))
            }
          />
        </div>

        <div className="form-group">
          <label htmlFor="break_even_activation_min_r_choppy_5m">BE Min R (Choppy 5m)</label>
          <input
            id="break_even_activation_min_r_choppy_5m"
            type="number"
            min="0"
            max="5"
            step="0.1"
            value={config.break_even_activation_min_r_choppy_5m ?? ""}
            onChange={(e) =>
              handleChange("break_even_activation_min_r_choppy_5m", Math.max(0, Number(e.target.value)))
            }
          />
        </div>

        <div className="form-group">
          <label htmlFor="break_even_buffer_pct">Break-even Buffer (%)</label>
          <input
            id="break_even_buffer_pct"
            type="number"
            min="0"
            max="2"
            step="0.01"
            value={config.break_even_buffer_pct ?? ""}
            onChange={(e) => handleChange("break_even_buffer_pct", Number(e.target.value))}
          />
        </div>

        <div className="form-group">
          <label htmlFor="break_even_min_hold_bars">Break-even Min Hold (bars)</label>
          <input
            id="break_even_min_hold_bars"
            type="number"
            min="1"
            step="1"
            value={config.break_even_min_hold_bars ?? ""}
            onChange={(e) => handleChange("break_even_min_hold_bars", Number(e.target.value))}
          />
        </div>

        <div className="form-group">
          <label className="field-row" htmlFor="trailing_enabled_in_choppy">
            <span>Enable Trailing In CHOPPY</span>
            <input
              id="trailing_enabled_in_choppy"
              type="checkbox"
              checked={!!config.trailing_enabled_in_choppy}
              onChange={(e) => handleChange("trailing_enabled_in_choppy", e.target.checked)}
            />
          </label>
        </div>
      </div>

      <div className="tw-panel">
        <div className="tw-panel-title">Partial Take Profit</div>
        <div className="tw-panel-hint">
          Ak je aktivovaný, systém vezme časť pozície pri dosiahnutí RR cieľa a posunie stop na BE.
        </div>
        <div className="form-group">
          <label className="field-row" htmlFor="enable_partial_take_profit">
            <span>Enable Partial Take Profit</span>
            <input
              id="enable_partial_take_profit"
              type="checkbox"
              checked={config.enable_partial_take_profit !== false}
              onChange={(e) => handleChange("enable_partial_take_profit", e.target.checked)}
            />
          </label>
        </div>

        {config.enable_partial_take_profit !== false && (
          <>
            <div className="form-group">
              <label htmlFor="partial_take_profit_rr">Partial TP Target (R-multiple)</label>
              <input
                id="partial_take_profit_rr"
                type="number"
                min="0.25"
                max="10"
                step="0.1"
                value={config.partial_take_profit_rr ?? ""}
                onChange={(e) =>
                  handleChange("partial_take_profit_rr", Math.max(0.25, Number(e.target.value)))
                }
              />
            </div>
            <div className="form-group">
              <label htmlFor="partial_take_profit_fraction">Partial TP Fraction (0.05-0.95)</label>
              <input
                id="partial_take_profit_fraction"
                type="number"
                min="0.05"
                max="0.95"
                step="0.05"
                value={config.partial_take_profit_fraction ?? ""}
                onChange={(e) =>
                  handleChange(
                    "partial_take_profit_fraction",
                    Math.max(0.05, Math.min(0.95, Number(e.target.value))),
                  )
                }
              />
            </div>
            <div className="form-group">
              <label htmlFor="partial_flow_deterioration_min_r">
                Flow Deterioration Min R (0 = disabled)
              </label>
              <input
                id="partial_flow_deterioration_min_r"
                type="number"
                min="0"
                max="5"
                step="0.1"
                value={config.partial_flow_deterioration_min_r ?? 0.5}
                onChange={(e) =>
                  handleChange(
                    "partial_flow_deterioration_min_r",
                    Math.max(0, Number(e.target.value)),
                  )
                }
              />
            </div>
            <div className="form-group">
              <label className="field-row" htmlFor="partial_flow_deterioration_skip_be">
                <span>Skip BE After Flow Deterioration Partial</span>
                <input
                  id="partial_flow_deterioration_skip_be"
                  type="checkbox"
                  checked={config.partial_flow_deterioration_skip_be !== false}
                  onChange={(e) =>
                    handleChange("partial_flow_deterioration_skip_be", e.target.checked)
                  }
                />
              </label>
            </div>
          </>
        )}
      </div>

      <div className="tw-panel">
        <div className="tw-panel-title">Micro Confirmation</div>
        <div className="tw-panel-hint">
          2-bar potvrdenie pred vstupom. Pre daytrading odporúčané VYPNUTÉ.
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
      </div>

      <div className="tw-panel">
        <div className="tw-panel-title">Adverse Flow Exit</div>
        <div className="tw-panel-hint">
          Ochranný exit pri zhoršení order-flow podmienok po vstupe.
        </div>
        <div className="form-group">
          <label className="field-row" htmlFor="adverse_flow_exit_enabled">
            <span>Adverse Flow Exit Enabled</span>
            <input
              id="adverse_flow_exit_enabled"
              type="checkbox"
              checked={!!config.adverse_flow_exit_enabled}
              onChange={(e) => handleChange("adverse_flow_exit_enabled", e.target.checked)}
            />
          </label>
        </div>

        <div className="form-group">
          <label htmlFor="adverse_flow_threshold">Adverse Flow Threshold</label>
          <input
            id="adverse_flow_threshold"
            type="number"
            min="0.02"
            max="1"
            step="0.01"
            value={config.adverse_flow_threshold ?? ""}
            onChange={(e) => handleChange("adverse_flow_threshold", Number(e.target.value))}
          />
        </div>

        <div className="form-group">
          <label htmlFor="adverse_flow_min_hold_bars">Adverse Flow Min Hold (bars)</label>
          <input
            id="adverse_flow_min_hold_bars"
            type="number"
            min="1"
            step="1"
            value={config.adverse_flow_min_hold_bars ?? ""}
            onChange={(e) => handleChange("adverse_flow_min_hold_bars", Number(e.target.value))}
          />
        </div>
      </div>
    </>
  );
}
