import React from "react";
import MomentumDiversificationEditor from "./MomentumDiversificationEditor";
import {
  l2GateFieldConfig,
  SHOW_RUN_CONFIG_ADVANCED_EXECUTION_CONTROLS,
  tcbboGateFieldConfig,
} from "./runConfigHelpers";
import type { MomentumSleeveDraft } from "./momentumUtils";

interface OrderFlowSettingsProps {
  config: Record<string, any>;
  handleChange: (field: string, value: any) => void;
  momentumSleeves: MomentumSleeveDraft[];
  onMomentumSleeveChange: (
    index: number,
    field: keyof MomentumSleeveDraft,
    value: unknown,
  ) => void;
  onAddMomentumSleeve: () => void;
  onRemoveMomentumSleeve: (index: number) => void;
}

export function OrderFlowSettings({ 
  config, 
  handleChange,
  momentumSleeves,
  onMomentumSleeveChange,
  onAddMomentumSleeve,
  onRemoveMomentumSleeve
}: OrderFlowSettingsProps) {
  return (
    <>
      <div className="subsection-group" style={{ marginTop: 12 }}>
        <div className="tw-panel-title" style={{ marginBottom: 6 }}>
          Advanced Flow & Sweeps
        </div>
        <label className="field-row" htmlFor="liquidity_sweep_detection_enabled">
          <input
            id="liquidity_sweep_detection_enabled"
            type="checkbox"
            checked={!!config.liquidity_sweep_detection_enabled}
            onChange={(e) =>
              handleChange("liquidity_sweep_detection_enabled", e.target.checked)
            }
          />
          <span>Enable Liquidity Sweep Detection</span>
        </label>
        {config.liquidity_sweep_detection_enabled && (
          <div className="tw-grid-fit-190" style={{ marginTop: 8 }}>
            <div className="form-group">
              <label htmlFor="sweep_min_aggression_z">Min Aggression Z ({"<="})</label>
              <input
                id="sweep_min_aggression_z"
                type="number"
                step="0.1"
                value={config.sweep_min_aggression_z ?? ""}
                onChange={(e) =>
                  handleChange("sweep_min_aggression_z", Number(e.target.value))
                }
              />
            </div>
            <div className="form-group">
              <label htmlFor="sweep_min_book_pressure_z">Min Book Pressure Z ({">="})</label>
              <input
                id="sweep_min_book_pressure_z"
                type="number"
                step="0.1"
                value={config.sweep_min_book_pressure_z ?? ""}
                onChange={(e) =>
                  handleChange("sweep_min_book_pressure_z", Number(e.target.value))
                }
              />
            </div>
            <div className="form-group">
              <label htmlFor="sweep_max_price_change_pct">Max |5m Trend Slope| (%)</label>
              <input
                id="sweep_max_price_change_pct"
                type="number"
                min="0"
                step="0.01"
                value={config.sweep_max_price_change_pct ?? ""}
                onChange={(e) =>
                  handleChange(
                    "sweep_max_price_change_pct",
                    Math.max(0, Number(e.target.value)),
                  )
                }
              />
            </div>
            <div className="form-group">
              <label htmlFor="sweep_atr_buffer_multiplier">Sweep ATR Buffer Multiplier</label>
              <input
                id="sweep_atr_buffer_multiplier"
                type="number"
                min="0"
                step="0.05"
                value={config.sweep_atr_buffer_multiplier ?? ""}
                onChange={(e) =>
                  handleChange(
                    "sweep_atr_buffer_multiplier",
                    Math.max(0, Number(e.target.value)),
                  )
                }
              />
            </div>
          </div>
        )}
      </div>

      {SHOW_RUN_CONFIG_ADVANCED_EXECUTION_CONTROLS ? (
        <MomentumDiversificationEditor
          config={config as any}
          momentumSleeves={momentumSleeves}
          onChange={handleChange}
          onMomentumSleeveChange={onMomentumSleeveChange}
          onAddMomentumSleeve={onAddMomentumSleeve}
          onRemoveMomentumSleeve={onRemoveMomentumSleeve}
        />
      ) : (
        <div className="preset-copy">
          Exit/risk moduly a ich detaily sa nastavujú v `Global Modules` a cez unified profile.
        </div>
      )}

      {SHOW_RUN_CONFIG_ADVANCED_EXECUTION_CONTROLS && (
        <div className="tw-panel">
          <div className="tw-panel-title">L2 Confirmation Gate</div>
          <div className="tw-panel-hint">
            Applies an order-flow quality check before entry. Keep filters light to avoid overfitting.
          </div>
          <div className="form-group">
            <label className="field-row" htmlFor="l2_confirm_enabled">
              <span>Enable L2 Confirmation Gate</span>
              <input
                id="l2_confirm_enabled"
                type="checkbox"
                checked={config.l2_confirm_enabled || false}
                onChange={(e) => handleChange("l2_confirm_enabled", e.target.checked)}
              />
            </label>
          </div>

          {config.l2_confirm_enabled && (
            <div className="tw-grid-fit-190">
              {l2GateFieldConfig.map((field) => {
                const isLookback = field.key === "l2_lookback_bars";
                return (
                  <div key={field.key} className="form-group">
                    <label htmlFor={field.key}>{field.label}</label>
                    <input
                      id={field.key}
                      type="number"
                      min={field.min}
                      step={field.step}
                      value={config[field.key] ?? ""}
                      onChange={(e) =>
                        handleChange(
                          field.key,
                          isLookback
                            ? Math.max(1, Math.trunc(Number(e.target.value)))
                            : Number(e.target.value),
                        )
                      }
                    />
                    <div className="tw-inline-note">
                      {field.hint}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {SHOW_RUN_CONFIG_ADVANCED_EXECUTION_CONTROLS && (
        <div className="tw-panel">
          <div className="tw-panel-title">TCBBO Options Flow Gate</div>
          <div className="tw-panel-hint">
            Uses OPRA TCBBO options-flow features for confirmation/regime override and diagnostics.
          </div>
          <div className="form-group">
            <label className="field-row" htmlFor="tcbbo_gate_enabled">
              <span>Enable TCBBO Flow Gate</span>
              <input
                id="tcbbo_gate_enabled"
                type="checkbox"
                checked={config.tcbbo_gate_enabled !== false}
                onChange={(e) => handleChange("tcbbo_gate_enabled", e.target.checked)}
              />
            </label>
          </div>

          {config.tcbbo_gate_enabled !== false && (
            <div className="tw-grid-fit-190">
              {tcbboGateFieldConfig.map((field) => {
                const isLookback = field.key === "tcbbo_lookback_bars";
                return (
                  <div key={field.key} className="form-group">
                    <label htmlFor={field.key}>{field.label}</label>
                    <input
                      id={field.key}
                      type="number"
                      min={field.min}
                      step={field.step}
                      value={config[field.key] ?? ""}
                      onChange={(e) =>
                        handleChange(
                          field.key,
                          isLookback
                            ? Math.max(1, Math.trunc(Number(e.target.value)))
                            : Math.max(0, Number(e.target.value)),
                        )
                      }
                    />
                    <div className="tw-inline-note">{field.hint}</div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </>
  );
}
