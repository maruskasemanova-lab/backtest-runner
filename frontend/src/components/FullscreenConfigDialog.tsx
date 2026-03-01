import React, { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { IntradayLevelsSettings } from "./run-config/IntradayLevelsSettings";
import { OrderFlowSettings } from "./run-config/OrderFlowSettings";
import { RiskManagementSettings } from "./run-config/RiskManagementSettings";

const isPlainRecord = (value: any): value is Record<string, any> =>
  Boolean(value) && typeof value === "object" && !Array.isArray(value);

const toPrettyJson = (value: any) => {
  try {
    return JSON.stringify(value, null, 2);
  } catch (error) {
    return String(value);
  }
};

type SnapshotEntry = {
  key: string;
  kind: "boolean" | "scalar" | "complex";
  boolValue: boolean;
  textValue: string;
  rows: number;
};

type SnapshotSection = {
  title: string;
  config?: Record<string, any> | null;
  description?: string;
};

const toSnapshotEntries = (config: any): SnapshotEntry[] => {
  if (!isPlainRecord(config)) return [];
  return Object.keys(config)
    .sort((a, b) => a.localeCompare(b))
    .map((key) => {
      const value = config[key];
      if (typeof value === "boolean") {
        return {
          key,
          kind: "boolean" as const,
          boolValue: value,
          textValue: value ? "true" : "false",
          rows: 1,
        };
      }
      if (
        typeof value === "string"
        || typeof value === "number"
        || typeof value === "bigint"
        || value === null
        || typeof value === "undefined"
      ) {
        const textValue =
          value === null ? "null" : typeof value === "undefined" ? "" : String(value);
        return {
          key,
          kind: "scalar" as const,
          boolValue: false,
          textValue,
          rows: 1,
        };
      }
      const textValue = toPrettyJson(value);
      const lineCount = textValue.split("\n").length;
      return {
        key,
        kind: "complex" as const,
        boolValue: false,
        textValue,
        rows: Math.min(14, Math.max(3, lineCount)),
      };
    });
};

type FullscreenConfigDialogProps = {
  isOpen: boolean;
  onClose: () => void;
  config?: Record<string, any>;
  handleChange?: (key: string, value: any) => void;
  momentumSleeves?: any[];
  onMomentumSleeveChange?: (...args: any[]) => void;
  onAddMomentumSleeve?: (...args: any[]) => void;
  onRemoveMomentumSleeve?: (...args: any[]) => void;
  activeProfile?: any;
  activeProfileId?: string;
  activeProfileName?: string;
  zIndex?: number;
  readOnly?: boolean;
  title?: string;
  subtitle?: string;
  snapshotSections?: SnapshotSection[];
};

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
  activeProfileId,
  activeProfileName,
  zIndex = 50,
  readOnly = false,
  title,
  subtitle,
  snapshotSections = [],
}: FullscreenConfigDialogProps) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  if (!isOpen || !mounted) return null;

  const safeConfig = isPlainRecord(config) ? config : {};
  const safeHandleChange = typeof handleChange === "function" ? handleChange : () => {};
  const safeMomentumSleeves = Array.isArray(momentumSleeves) ? momentumSleeves : [];
  const safeOnMomentumSleeveChange =
    typeof onMomentumSleeveChange === "function" ? onMomentumSleeveChange : () => {};
  const safeOnAddMomentumSleeve =
    typeof onAddMomentumSleeve === "function" ? onAddMomentumSleeve : () => {};
  const safeOnRemoveMomentumSleeve =
    typeof onRemoveMomentumSleeve === "function" ? onRemoveMomentumSleeve : () => {};
  const normalizedSnapshotSections: SnapshotSection[] = Array.isArray(snapshotSections)
    ? snapshotSections
      .filter((section) => isPlainRecord(section?.config) && Object.keys(section.config || {}).length > 0)
      .map((section) => ({
        title: String(section?.title || "Snapshot"),
        config: section?.config || {},
        description: typeof section?.description === "string" ? section.description : "",
      }))
    : [];
  const isSnapshotMode = Boolean(readOnly && normalizedSnapshotSections.length);

  // We map the activeProfile directly from config if there are overrides, falling back to the passed activeProfile.
  // This ensures inputs reflect immediate local edits before saving.
  const currentExecutionProfile = safeConfig.execution_profile || activeProfile?.execution_profile || {};
  const currentStrategyProfile = safeConfig.strategy_profile || activeProfile?.strategy_profile || {};
  const currentStrategyParams = currentStrategyProfile.strategy_params || {};
  const resolvedActiveProfileId = String(activeProfileId ?? activeProfile?.profile_id ?? "").trim();
  const resolvedActiveProfileName = String(activeProfileName ?? activeProfile?.profile_name ?? "").trim();
  const activeProfileSummary =
    resolvedActiveProfileName && resolvedActiveProfileId && resolvedActiveProfileName !== resolvedActiveProfileId
      ? `${resolvedActiveProfileName} (${resolvedActiveProfileId})`
      : resolvedActiveProfileName || resolvedActiveProfileId;
  const hasProfilePayload =
    Boolean(activeProfile)
    || Object.keys(currentExecutionProfile).length > 0
    || Object.keys(currentStrategyParams).length > 0;

  const handleExecutionParamChange = (key: string, value: any) => {
    safeHandleChange("execution_profile", {
      ...currentExecutionProfile,
      [key]: value,
    });
  };

  const handleStrategyParamValueChange = (strategyName: string, paramKey: string, value: any) => {
    safeHandleChange("strategy_profile", {
      ...currentStrategyProfile,
      strategy_params: {
        ...currentStrategyParams,
        [strategyName]: {
          ...(currentStrategyParams[strategyName] || {}),
          [paramKey]: value,
        },
      },
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
              disabled={readOnly}
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
          disabled={readOnly}
        />
      </div>
    );
  };

  const renderSnapshotField = (entry: SnapshotEntry, fieldPrefix: string) => {
    const fieldId = `${fieldPrefix}-${entry.key.replace(/[^a-zA-Z0-9_-]/g, "_")}`;
    const formattedLabel = entry.key.replace(/_/g, " ");

    if (entry.kind === "boolean") {
      return (
        <div className="form-group" key={`${fieldPrefix}-${entry.key}`}>
          <label className="field-row" htmlFor={fieldId}>
            <span style={{ textTransform: "capitalize" }}>{formattedLabel}</span>
            <input id={fieldId} type="checkbox" checked={entry.boolValue} disabled readOnly />
          </label>
        </div>
      );
    }

    if (entry.kind === "complex") {
      return (
        <div className="form-group" key={`${fieldPrefix}-${entry.key}`}>
          <label htmlFor={fieldId} style={{ textTransform: "capitalize" }}>{formattedLabel}</label>
          <textarea
            id={fieldId}
            value={entry.textValue}
            rows={entry.rows}
            disabled
            readOnly
            style={{ background: "rgba(15, 23, 42, 0.5)", fontFamily: "var(--font-mono)" }}
          />
        </div>
      );
    }

    return (
      <div className="form-group" key={`${fieldPrefix}-${entry.key}`}>
        <label htmlFor={fieldId} style={{ textTransform: "capitalize" }}>{formattedLabel}</label>
        <input
          id={fieldId}
          type="text"
          value={entry.textValue}
          disabled
          readOnly
          style={{ background: "rgba(15, 23, 42, 0.5)", fontFamily: "var(--font-mono)" }}
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
            <h2 className="card-title text-lg">
              {title || (isSnapshotMode ? "Run Config Snapshot" : "Full Profile Configuration")}
            </h2>
            <div className="text-xs text-gray-400 mt-1">
              {subtitle || (isSnapshotMode
                ? "Read-only configuration captured for this run."
                : "Configure all advanced parameters for the current run session.")}
            </div>
          </div>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={onClose}
          >
            {isSnapshotMode ? "Close" : "Close / Done"}
          </button>
        </div>

        <div className="card-body flex-1 overflow-y-auto flex flex-col lg:flex-row gap-6" style={{ padding: "24px" }}>
          {isSnapshotMode ? (
            <div className="flex-1 overflow-y-auto run-config-form">
              <div className="flex flex-col gap-4">
                {normalizedSnapshotSections.map((section, index) => {
                  const entries = toSnapshotEntries(section.config);
                  return (
                    <div className="tw-panel" key={`snapshot-section-${index}-${section.title}`}>
                      <div className="tw-panel-title">{section.title}</div>
                      {section.description ? (
                        <div className="text-xs text-gray-400 mt-2">{section.description}</div>
                      ) : null}
                      {entries.length ? (
                        <div className="tw-grid-fit-190" style={{ marginTop: "12px" }}>
                          {entries.map((entry) => renderSnapshotField(entry, `snapshot-${index}`))}
                        </div>
                      ) : (
                        <div className="text-xs text-slate-500 italic mt-2">No values captured.</div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          ) : (
            <>
              {/* Editable settings */}
              <fieldset
                disabled={readOnly}
                style={{ border: 0, margin: 0, padding: 0, minWidth: 0 }}
                className="flex-1 overflow-y-auto pr-2"
              >
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
                        value={safeConfig.account_size_usd}
                        onChange={(e) => safeHandleChange("account_size_usd", Number(e.target.value))}
                        style={{ background: "rgba(15, 23, 42, 0.6)" }}
                      />
                    </div>

                    <div className="form-group">
                      <label htmlFor="regime_minutes_fs">Regime Detection (min)</label>
                      <input
                        id="regime_minutes_fs"
                        type="number"
                        min="5"
                        value={safeConfig.regime_detection_minutes}
                        onChange={(e) => safeHandleChange("regime_detection_minutes", Number(e.target.value))}
                        style={{ background: "rgba(15, 23, 42, 0.6)" }}
                      />
                    </div>

                    <div className="form-group">
                      <label>Allowed Regimes (Override)</label>
                      <div className="checkbox-group" style={{ display: "flex", gap: "12px", marginTop: "4px" }}>
                        {["TRENDING", "CHOPPY", "MIXED"].map((regime) => {
                          const isChecked = (safeConfig.regime_filter || []).includes(regime);
                          return (
                            <label key={`fs-${regime}`} style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "0.85rem", cursor: "pointer" }}>
                              <input
                                type="checkbox"
                                checked={isChecked}
                                onChange={(e) => {
                                  const current = safeConfig.regime_filter || [];
                                  let next;
                                  if (e.target.checked) {
                                    next = [...current, regime];
                                  } else {
                                    next = current.filter((r: string) => r !== regime);
                                  }
                                  safeHandleChange("regime_filter", next);
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
                    <IntradayLevelsSettings config={safeConfig} handleChange={safeHandleChange} />
                  </div>

                  {/* Risk Management */}
                  <div className="flex flex-col gap-4">
                    <h3 className="text-sm font-bold uppercase tracking-wider text-red-400 border-b border-slate-700 pb-2">Risk Management</h3>
                    <RiskManagementSettings config={safeConfig} handleChange={safeHandleChange} />
                  </div>

                  {/* Order Flow & Momentum */}
                  <div className="flex flex-col gap-4 md:col-span-2">
                    <h3 className="text-sm font-bold uppercase tracking-wider text-amber-400 border-b border-slate-700 pb-2">Order Flow & Momentum</h3>
                    <OrderFlowSettings
                      config={safeConfig}
                      handleChange={safeHandleChange}
                      momentumSleeves={safeMomentumSleeves}
                      onMomentumSleeveChange={safeOnMomentumSleeveChange}
                      onAddMomentumSleeve={safeOnAddMomentumSleeve}
                      onRemoveMomentumSleeve={safeOnRemoveMomentumSleeve}
                    />
                  </div>
                </div>
              </fieldset>

              {/* Raw JSON Profile viewer */}
              <fieldset
                disabled={readOnly}
                style={{ border: 0, margin: 0, padding: 0, minWidth: 0 }}
                className="w-full lg:w-1/3 flex flex-col gap-2 border-l border-slate-700 pl-6"
              >
                <h3 className="text-sm font-bold uppercase tracking-wider text-indigo-400 border-b border-slate-700 pb-2">Active Unified Profile Settings</h3>
                <div className="text-xs text-gray-400 mb-2">
                  All active strategy parameters and execution constraints loaded from this profile.
                </div>
                <div className="text-xs text-slate-400 mb-2">
                  {activeProfileSummary
                    ? `Using unified profile: ${activeProfileSummary}`
                    : "Using unified profile: unresolved"}
                </div>
                {hasProfilePayload ? (
                  <div className="flex-1 overflow-auto bg-slate-900/50 border border-slate-800 rounded-md p-4 flex flex-col gap-4">

                    {/* execution_profile metadata */}
                    {Object.keys(currentExecutionProfile).length > 0 && (
                      <div className="tw-panel">
                        <div className="tw-panel-title">Execution & Positioning</div>
                        <div className="tw-grid-fit-190" style={{ marginTop: "12px" }}>
                          {Object.entries(currentExecutionProfile).map(([key, value]: any) => {
                            if (key === "positioning" && typeof value === "object") return null;
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
                    {activeProfileSummary
                      ? `No unified profile payload loaded for ${activeProfileSummary}.`
                      : "No active unified profile selected."}
                  </div>
                )}
              </fieldset>
            </>
          )}
        </div>
      </div>
    </div>,
    document.body
  );
}
