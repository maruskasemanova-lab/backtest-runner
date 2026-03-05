import React from "react";
import StrategySettings from "../StrategySettings";
import {
  ExecutionSizingPanel,
  StopLossAndBreakEvenPanel,
  PartialTakeProfitPanel,
  AdverseFlowExitPanel,
  ContextAwareRiskPanel,
  MicroConfirmationPanel,
} from "../run-config/RiskManagementPanels";
import { OrderFlowSettings } from "../run-config/OrderFlowSettings";
import { IntradayLevelsSettings } from "../run-config/IntradayLevelsSettings";
import { UNIFIED_CONFIG_SECTIONS, type UnifiedConfigSectionId } from "./types";

const isPlainRecord = (v: any): v is Record<string, any> =>
  Boolean(v) && typeof v === "object" && !Array.isArray(v);

interface SectionHeaderProps {
  label: string;
  description: string;
  colorClass: string;
}

function SectionHeader({ label, description, colorClass }: SectionHeaderProps) {
  return (
    <div className="unified-config-section-header">
      <h3 className={`unified-config-section-title ${colorClass}`}>{label}</h3>
      <div className="unified-config-section-desc">{description}</div>
    </div>
  );
}

interface UnifiedConfigSectionsProps {
  config: Record<string, any>;
  handleChange: (field: string, value: any) => void;
  momentumSleeves: any[];
  onMomentumSleeveChange: (...args: any[]) => void;
  onAddMomentumSleeve: (...args: any[]) => void;
  onRemoveMomentumSleeve: (...args: any[]) => void;
  strategyApiUrl: string;
  selectedTicker: string;
  activeProfile?: any;
  activeProfileId?: string;
  activeProfileName?: string;
  readOnly?: boolean;
  setSectionRef: (id: string, node: HTMLDivElement | null) => void;
}

export function UnifiedConfigSections({
  config,
  handleChange,
  momentumSleeves,
  onMomentumSleeveChange,
  onAddMomentumSleeve,
  onRemoveMomentumSleeve,
  strategyApiUrl,
  selectedTicker,
  activeProfile,
  activeProfileId,
  activeProfileName,
  readOnly = false,
  setSectionRef,
}: UnifiedConfigSectionsProps) {
  const sectionMeta = Object.fromEntries(
    UNIFIED_CONFIG_SECTIONS.map((s) => [s.id, s]),
  ) as Record<UnifiedConfigSectionId, (typeof UNIFIED_CONFIG_SECTIONS)[number]>;

  return (
    <>
      {/* ── Section 1: Strategies & Entry ── */}
      <div
        ref={(node) => setSectionRef("strategies", node)}
        data-section-id="strategies"
      >
        <SectionHeader {...sectionMeta.strategies} />
        <StrategySettings
          apiUrl={strategyApiUrl}
          selectedTicker={selectedTicker}
          initialExpandAll
        />
      </div>

      {/* ── Section 2: Risk & Position Sizing ── */}
      <div
        ref={(node) => setSectionRef("risk_sizing", node)}
        data-section-id="risk_sizing"
      >
        <SectionHeader {...sectionMeta.risk_sizing} />
        <fieldset disabled={readOnly} className="ui-fieldset-reset">
          <div className="ui-form-stack run-config-form">
            <ExecutionSizingPanel config={config} handleChange={handleChange} />
            <StopLossAndBreakEvenPanel
              config={config}
              handleChange={handleChange}
            />
          </div>
        </fieldset>
      </div>

      {/* ── Section 3: Exit Management ── */}
      <div
        ref={(node) => setSectionRef("exit_management", node)}
        data-section-id="exit_management"
      >
        <SectionHeader {...sectionMeta.exit_management} />
        <fieldset disabled={readOnly} className="ui-fieldset-reset">
          <div className="ui-form-stack run-config-form">
            <PartialTakeProfitPanel
              config={config}
              handleChange={handleChange}
            />
            <AdverseFlowExitPanel config={config} handleChange={handleChange} />
          </div>
        </fieldset>
      </div>

      {/* ── Section 4: Order Flow Gates ── */}
      <div
        ref={(node) => setSectionRef("order_flow", node)}
        data-section-id="order_flow"
      >
        <SectionHeader {...sectionMeta.order_flow} />
        <fieldset disabled={readOnly} className="ui-fieldset-reset">
          <div className="ui-form-stack run-config-form">
            <OrderFlowSettings
              config={config}
              handleChange={handleChange}
              momentumSleeves={momentumSleeves}
              onMomentumSleeveChange={onMomentumSleeveChange}
              onAddMomentumSleeve={onAddMomentumSleeve}
              onRemoveMomentumSleeve={onRemoveMomentumSleeve}
            />
          </div>
        </fieldset>
      </div>

      {/* ── Section 5: Regime & Market ── */}
      <div
        ref={(node) => setSectionRef("regime_market", node)}
        data-section-id="regime_market"
      >
        <SectionHeader {...sectionMeta.regime_market} />
        <fieldset disabled={readOnly} className="ui-fieldset-reset">
          <div className="ui-form-stack run-config-form">
            <div className="tw-panel">
              <div className="tw-panel-title">Regime Detection</div>
              <div className="tw-panel-hint">
                How frequently the market regime is re-evaluated and which
                regimes are allowed for trading.
              </div>
              <div className="tw-grid-fit-190 ui-mt-sm">
                <div className="form-group">
                  <label htmlFor="regime_minutes_uc">
                    Regime Detection (min)
                  </label>
                  <input
                    id="regime_minutes_uc"
                    type="number"
                    min="5"
                    value={config.regime_detection_minutes ?? ""}
                    onChange={(e) =>
                      handleChange(
                        "regime_detection_minutes",
                        Number(e.target.value),
                      )
                    }
                  />
                </div>
              </div>
              <div className="form-group ui-mt-sm">
                <label>Allowed Regimes (Override)</label>
                <div className="unified-config-choice-row ui-mt-xs">
                  {["TRENDING", "CHOPPY", "MIXED"].map((regime) => {
                    const isChecked = (config.regime_filter || []).includes(
                      regime,
                    );
                    return (
                      <label
                        key={`uc-${regime}`}
                        className="unified-config-choice"
                      >
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={(e) => {
                            const current = config.regime_filter || [];
                            const next = e.target.checked
                              ? [...current, regime]
                              : current.filter((r: string) => r !== regime);
                            handleChange("regime_filter", next);
                          }}
                        />
                        {regime}
                      </label>
                    );
                  })}
                </div>
                <div className="ui-form-help ui-mt-xs">
                  Leave all unchecked to allow ALL regimes.
                </div>
              </div>
            </div>
            <ContextAwareRiskPanel
              config={config}
              handleChange={handleChange}
            />
          </div>
        </fieldset>
      </div>

      {/* ── Section 6: General Settings ── */}
      <div
        ref={(node) => setSectionRef("general", node)}
        data-section-id="general"
      >
        <SectionHeader {...sectionMeta.general} />
        <fieldset disabled={readOnly} className="ui-fieldset-reset">
          <div className="ui-form-stack run-config-form">
            <div className="tw-panel">
              <div className="tw-panel-title">Account</div>
              <div className="tw-grid-fit-190 ui-mt-sm">
                <div className="form-group">
                  <label htmlFor="account_size_usd_uc">
                    Account Size (USD)
                  </label>
                  <input
                    id="account_size_usd_uc"
                    type="number"
                    min="100"
                    step="100"
                    value={config.account_size_usd ?? ""}
                    onChange={(e) =>
                      handleChange("account_size_usd", Number(e.target.value))
                    }
                  />
                </div>
              </div>
            </div>
            <IntradayLevelsSettings
              config={config}
              handleChange={handleChange}
            />
            <MicroConfirmationPanel
              config={config}
              handleChange={handleChange}
            />
          </div>
        </fieldset>
      </div>

      {/* ── Section 7: Active Profile ── */}
      <div
        ref={(node) => setSectionRef("active_profile", node)}
        data-section-id="active_profile"
      >
        <SectionHeader {...sectionMeta.active_profile} />
        <ActiveProfileViewer
          config={config}
          activeProfile={activeProfile}
          activeProfileId={activeProfileId}
          activeProfileName={activeProfileName}
          readOnly={readOnly}
          handleChange={handleChange}
        />
      </div>
    </>
  );
}

/* ── Active Profile Viewer (extracted from FullscreenConfigDialog) ── */

interface ActiveProfileViewerProps {
  config: Record<string, any>;
  activeProfile?: any;
  activeProfileId?: string;
  activeProfileName?: string;
  readOnly?: boolean;
  handleChange: (field: string, value: any) => void;
}

function ActiveProfileViewer({
  config,
  activeProfile,
  activeProfileId,
  activeProfileName,
  readOnly = false,
  handleChange,
}: ActiveProfileViewerProps) {
  const currentExecutionProfile =
    config.execution_profile || activeProfile?.execution_profile || {};
  const currentStrategyProfile =
    config.strategy_profile || activeProfile?.strategy_profile || {};
  const currentStrategyParams = currentStrategyProfile.strategy_params || {};

  const resolvedId = String(
    activeProfileId ?? activeProfile?.profile_id ?? "",
  ).trim();
  const resolvedName = String(
    activeProfileName ?? activeProfile?.profile_name ?? "",
  ).trim();
  const summary =
    resolvedName && resolvedId && resolvedName !== resolvedId
      ? `${resolvedName} (${resolvedId})`
      : resolvedName || resolvedId;

  const hasPayload =
    Boolean(activeProfile) ||
    Object.keys(currentExecutionProfile).length > 0 ||
    Object.keys(currentStrategyParams).length > 0;

  const handleExecutionParamChange = (key: string, value: any) => {
    handleChange("execution_profile", {
      ...currentExecutionProfile,
      [key]: value,
    });
  };

  const handleStrategyParamValueChange = (
    strategyName: string,
    paramKey: string,
    value: any,
  ) => {
    handleChange("strategy_profile", {
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

  if (!hasPayload) {
    return (
      <div className="tw-panel">
        <div className="ui-note ui-note-compact unified-config-empty">
          {summary
            ? `No unified profile payload loaded for ${summary}.`
            : "No active unified profile selected."}
        </div>
      </div>
    );
  }

  return (
    <div className="ui-form-stack">
      <div className="ui-form-help">
        {summary
          ? `Using unified profile: ${summary}`
          : "Using unified profile: unresolved"}
      </div>

      {Object.keys(currentExecutionProfile).length > 0 && (
        <div className="tw-panel">
          <div className="tw-panel-title">Execution & Positioning</div>
          <div className="tw-grid-fit-190 ui-mt-md">
            {Object.entries(currentExecutionProfile).map(
              ([key, value]: any) => {
                if (key === "positioning" && typeof value === "object")
                  return null;
                return renderProfileField(
                  key,
                  value,
                  (val) => handleExecutionParamChange(key, val),
                  "exec-uc",
                  readOnly,
                );
              },
            )}
          </div>
        </div>
      )}

      {Object.keys(currentStrategyParams).length > 0 && (
        <div className="tw-panel">
          <div className="tw-panel-title">Strategy Parameters</div>
          <div className="ui-stack-lg ui-mt-md">
            {Object.entries(currentStrategyParams).map(
              ([strategyName, params]: any) => (
                <div key={strategyName}>
                  <div className="text-sm font-bold text-blue-400 mb-3 border-b border-slate-700/50 pb-1">
                    {strategyName}
                  </div>
                  <div className="tw-grid-fit-190">
                    {Object.entries(params).map(([paramKey, paramVal]: any) =>
                      renderProfileField(
                        paramKey,
                        paramVal,
                        (val) =>
                          handleStrategyParamValueChange(
                            strategyName,
                            paramKey,
                            val,
                          ),
                        `${strategyName}-uc`,
                        readOnly,
                      ),
                    )}
                  </div>
                </div>
              ),
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function renderProfileField(
  key: string,
  value: any,
  onChange: (val: any) => void,
  idPrefix: string,
  disabled: boolean,
) {
  const isBool = typeof value === "boolean";
  const isNum = typeof value === "number";
  const id = `${idPrefix}-${key}`;
  const label = key.replace(/_/g, " ");

  if (isBool) {
    return (
      <div className="form-group" key={key}>
        <label className="field-row" htmlFor={id}>
          <span className="ui-field-capitalize">{label}</span>
          <input
            id={id}
            type="checkbox"
            checked={!!value}
            onChange={(e) => onChange(e.target.checked)}
            disabled={disabled}
          />
        </label>
      </div>
    );
  }

  return (
    <div className="form-group" key={key}>
      <label htmlFor={id} className="ui-field-capitalize">
        {label}
      </label>
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
        disabled={disabled}
      />
    </div>
  );
}
