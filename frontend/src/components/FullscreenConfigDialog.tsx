import React, { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { IntradayLevelsSettings } from "./run-config/IntradayLevelsSettings";
import { OrderFlowSettings } from "./run-config/OrderFlowSettings";
import { RiskManagementSettings } from "./run-config/RiskManagementSettings";

export function FullscreenConfigDialog({
  isOpen,
  onClose,
  config,
  handleChange,
  momentumSleeves,
  onMomentumSleeveChange,
  onAddMomentumSleeve,
  onRemoveMomentumSleeve,
  activeProfile,
  zIndex = 50,
}: any) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  if (!isOpen || !mounted) return null;

  // We map the activeProfile directly from config if there are overrides, falling back to the passed activeProfile.
  // This ensures inputs reflect immediate local edits before saving.
  const currentExecutionProfile = config.execution_profile || activeProfile?.execution_profile || {};
  const currentStrategyProfile = config.strategy_profile || activeProfile?.strategy_profile || {};
  const currentStrategyParams = currentStrategyProfile.strategy_params || {};

  const handleExecutionParamChange = (key: string, value: any) => {
    handleChange("execution_profile", {
      ...currentExecutionProfile,
      [key]: value,
    });
  };

  const handleStrategyParamValueChange = (strategyName: string, paramKey: string, value: any) => {
    handleChange("strategy_profile", {
      ...currentStrategyProfile,
      strategy_params: {
        ...currentStrategyParams,
        [strategyName]: {
          ...(currentStrategyParams[strategyName] || {}),
          [paramKey]: value,
        }
      }
    });
  };

  const renderDynamicInput = (key: string, value: any, onChange: (val: any) => void, idPrefix: string) => {
    const isBool = typeof value === "boolean";
    const id = `${idPrefix}-${key}`;
    const formattedLabel = key.replace(/_/g, " ");

    if (isBool) {
      return (
        <div className="form-group" key={key}>
          <label className="field-row" htmlFor={id}>
            <span style={{ textTransform: "capitalize" }}>{formattedLabel}</span>
            <input
              id={id}
              type="checkbox"
              checked={!!value}
              onChange={(e) => onChange(e.target.checked)}
            />
          </label>
        </div>
      );
    }

    const isNum = typeof value === "number";
    return (
      <div className="form-group" key={key}>
        <label htmlFor={id} style={{ textTransform: "capitalize" }}>{formattedLabel}</label>
        <input
          id={id}
          type={isNum ? "number" : "text"}
          step={isNum ? "any" : undefined}
          value={value !== null && value !== undefined ? String(value) : ""}
          onChange={(e) => {
            const val = e.target.value;
            if (isNum || (!isNaN(Number(val)) && val.trim() !== "")) {
              onChange(Number(val));
            } else {
              onChange(val);
            }
          }}
        />
      </div>
    );
  };

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{
        backgroundColor: "rgba(15, 23, 42, 0.85)",
        backdropFilter: "blur(4px)",
        zIndex,
      }}
    >
      <div
        className="card w-[95vw] h-[95vh] flex flex-col overflow-hidden animate-fade-in"
        style={{ background: "var(--sidebar-bg-subtle)", borderColor: "var(--sidebar-border)" }}
      >
        <div className="card-header flex justify-between items-center" style={{ padding: "16px 24px" }}>
          <div>
            <h2 className="card-title text-lg">Full Profile Configuration</h2>
            <div className="text-xs text-gray-400 mt-1">
              Configure all advanced parameters for the current run session.
            </div>
          </div>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={onClose}
          >
            Close / Done
          </button>
        </div>
        
        <div className="card-body flex-1 overflow-y-auto flex flex-col lg:flex-row gap-6" style={{ padding: "24px" }}>
          {/* Editable settings */}
          <div className="flex-1 overflow-y-auto pr-2">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-2 mb-6 gap-6 run-config-form">
              
              {/* General Logic */}
              <div className="flex flex-col gap-4">
                <h3 className="text-sm font-bold uppercase tracking-wider text-blue-400 border-b border-slate-700 pb-2">General Trade Parameters</h3>
              
              <div className="form-group">
                <label htmlFor="account_size_usd_fs">Account Size (USD)</label>
                <input
                  id="account_size_usd_fs"
                  type="number"
                  min="100"
                  step="100"
                  value={config.account_size_usd}
                  onChange={(e) => handleChange("account_size_usd", Number(e.target.value))}
                  style={{ background: "rgba(15, 23, 42, 0.6)" }}
                />
              </div>

              <div className="form-group">
                <label htmlFor="regime_minutes_fs">Regime Detection (min)</label>
                <input
                  id="regime_minutes_fs"
                  type="number"
                  min="5"
                  value={config.regime_detection_minutes}
                  onChange={(e) => handleChange("regime_detection_minutes", Number(e.target.value))}
                  style={{ background: "rgba(15, 23, 42, 0.6)" }}
                />
              </div>

              <div className="form-group">
                <label>Allowed Regimes (Override)</label>
                <div className="checkbox-group" style={{ display: "flex", gap: "12px", marginTop: "4px" }}>
                  {["TRENDING", "CHOPPY", "MIXED"].map((regime) => {
                    const isChecked = (config.regime_filter || []).includes(regime);
                    return (
                      <label key={`fs-${regime}`} style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "0.85rem", cursor: "pointer" }}>
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={(e) => {
                            const current = config.regime_filter || [];
                            let next;
                            if (e.target.checked) {
                              next = [...current, regime];
                            } else {
                              next = current.filter((r: string) => r !== regime);
                            }
                            handleChange("regime_filter", next);
                          }}
                        />
                        {regime}
                      </label>
                    );
                  })}
                </div>
                <div style={{ color: "var(--text-muted)", fontSize: "0.78rem", marginTop: "4px" }}>
                  Select allowed regimes to override ticker defaults. Leave all unchecked to allow ALL.
                </div>
              </div>
            </div>

            {/* Intraday Levels */}
            <div className="flex flex-col gap-4">
              <h3 className="text-sm font-bold uppercase tracking-wider text-emerald-400 border-b border-slate-700 pb-2">Levels & Zones</h3>
              <IntradayLevelsSettings config={config} handleChange={handleChange} />
            </div>

            {/* Risk Management */}
            <div className="flex flex-col gap-4">
              <h3 className="text-sm font-bold uppercase tracking-wider text-red-400 border-b border-slate-700 pb-2">Risk Management</h3>
              <RiskManagementSettings config={config} handleChange={handleChange} />
            </div>

            {/* Order Flow & Momentum */}
            <div className="flex flex-col gap-4 md:col-span-2">
              <h3 className="text-sm font-bold uppercase tracking-wider text-amber-400 border-b border-slate-700 pb-2">Order Flow & Momentum</h3>
              <OrderFlowSettings
                config={config}
                handleChange={handleChange}
                momentumSleeves={momentumSleeves}
                onMomentumSleeveChange={onMomentumSleeveChange}
                onAddMomentumSleeve={onAddMomentumSleeve}
                onRemoveMomentumSleeve={onRemoveMomentumSleeve}
              />
            </div>
            </div>
          </div>

          {/* Raw JSON Profile viewer */}
          <div className="w-full lg:w-1/3 flex flex-col gap-2 border-l border-slate-700 pl-6">
            <h3 className="text-sm font-bold uppercase tracking-wider text-indigo-400 border-b border-slate-700 pb-2">Active Unified Profile Settings</h3>
            <div className="text-xs text-gray-400 mb-2">
              All active strategy parameters and execution constraints loaded from this profile.
            </div>
            {activeProfile ? (
              <div className="flex-1 overflow-auto bg-slate-900/50 border border-slate-800 rounded-md p-4 flex flex-col gap-4">
                
                {/* execution_profile metadata */}
                {Object.keys(currentExecutionProfile).length > 0 && (
                  <div className="tw-panel">
                    <div className="tw-panel-title">Execution & Positioning</div>
                    <div className="tw-grid-fit-190" style={{ marginTop: "12px" }}>
                      {Object.entries(currentExecutionProfile).map(([key, value]: any) => {
                        if (key === "positioning" && typeof value === 'object') return null;
                        return renderDynamicInput(key, value, (val) => handleExecutionParamChange(key, val), "exec");
                      })}
                    </div>
                  </div>
                )}

                {/* strategy_params */}
                {Object.keys(currentStrategyParams).length > 0 && (
                  <div className="tw-panel">
                    <div className="tw-panel-title">Strategy Parameters</div>
                    <div className="flex flex-col gap-6" style={{ marginTop: "12px" }}>
                      {Object.entries(currentStrategyParams).map(([strategyName, params]: any) => (
                        <div key={strategyName}>
                          <div className="text-sm font-bold text-blue-400 mb-3 border-b border-slate-700/50 pb-1">{strategyName}</div>
                          <div className="tw-grid-fit-190">
                            {Object.entries(params).map(([paramKey, paramVal]: any) => 
                              renderDynamicInput(paramKey, paramVal, (val) => handleStrategyParamValueChange(strategyName, paramKey, val), strategyName)
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                
                {/* Fallback if both empty */}
                {(Object.keys(currentStrategyParams).length === 0 && Object.keys(currentExecutionProfile).length === 0) && (
                  <div className="text-xs text-slate-500 italic">No detailed parameters found in profile.</div>
                )}

              </div>
            ) : (
              <div className="flex-1 flex items-center justify-center bg-slate-900 rounded-md border border-slate-800 text-slate-500 text-sm italic">
                No active unified profile selected.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>,
    document.body
  );
}
