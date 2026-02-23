import React, { useMemo } from "react";
import { ProFieldGuide, ProPlaybookItem, StrategyRuleOverview } from "../strategy-settings/types"; // Assuming types moved or exist

const FORMULA_OPERATOR_TOKENS = [
  "and",
  "or",
  "not",
  "(",
  ")",
  ">",
  ">=",
  "<",
  "<=",
  "==",
  "!=",
];
const DEFAULT_FORMULA_VARIABLES = [
  "flow_score",
  "signed_aggression",
  "directional_consistency",
  "imbalance",
  "book_pressure",
  "participation_ratio",
  "intrabar_move_pct",
  "intrabar_push_ratio",
  "intrabar_coverage_points",
  "intrabar_directional_consistency",
  "regime",
  "trend_score",
  "ma_trend",
  "volume_trend",
  "atr",
  "adx",
  "rsi",
  "position_side",
  "bars_held",
  "position_pnl_pct",
  "entry_price",
  "stop_loss",
  "take_profit",
];

const regimeOptions = ["TRENDING", "CHOPPY", "MIXED"];

interface StrategyFieldRendererProps {
  name: string;
  field: string;
  value: any;
  drafts: Record<string, Record<string, any>>;
  strategies: Record<string, any> | null;
  updateDraftField: (name: string, field: string, value: any) => void;
  appendFormulaToken: (name: string, field: string, token: string) => void;
  setDrafts: React.Dispatch<React.SetStateAction<Record<string, Record<string, any>>>>;
  showProNotes: boolean;
  getFieldGuide: (field: string) => ProFieldGuide | null;
  formatFieldLabel: (field: string) => string;
}

export function StrategyFieldRenderer({
  name,
  field,
  value,
  drafts,
  strategies,
  updateDraftField,
  appendFormulaToken,
  setDrafts,
  showProNotes,
  getFieldGuide,
  formatFieldLabel,
}: StrategyFieldRendererProps) {
  const fieldGuide = showProNotes ? getFieldGuide(field) : null;
  const guideTitle = fieldGuide
    ? `Pro range: ${fieldGuide.range}. ${fieldGuide.behavior}`
    : undefined;

  if (field === "custom_entry_formula" || field === "custom_exit_formula") {
    const isEntryFormula = field === "custom_entry_formula";
    const enabledField = isEntryFormula
      ? "custom_entry_formula_enabled"
      : "custom_exit_formula_enabled";
    const enabled = Boolean(
      drafts[name]?.[enabledField] ??
        strategies?.[name]?.[enabledField] ??
        false,
    );
    const rawVars =
      drafts[name]?.custom_formula_supported_variables ??
      strategies?.[name]?.custom_formula_supported_variables;
    const formulaVars =
      Array.isArray(rawVars) && rawVars.length
        ? rawVars.map((item) => String(item || "").trim()).filter(Boolean)
        : DEFAULT_FORMULA_VARIABLES;
    const formulaExamples =
      drafts[name]?.custom_formula_examples ??
      strategies?.[name]?.custom_formula_examples ??
      {};
    const entryExample = String(
      formulaExamples?.entry ||
        "regime in ('TRENDING','MIXED') and flow_score >= 55 and signed_aggression > 0.05",
    );
    const exitExample = String(
      formulaExamples?.exit ||
        "position_side == 'long' and (position_pnl_pct < -0.35 or flow_score < 40)",
    );
    const currentFormula = String(drafts[name]?.[field] ?? value ?? "");

    return (
      <div className="sc-formula-field" key={field}>
        <label className="sc-field-label">
          {isEntryFormula ? "Custom Entry Formula" : "Custom Exit Formula"}
        </label>
        <textarea
          className="sc-formula-input"
          rows={3}
          value={currentFormula}
          disabled={!enabled}
          placeholder={
            enabled
              ? "Write boolean formula (and/or, >, <, ==, !=, in, min/max/abs...)"
              : "Enable formula switch first"
          }
          onChange={(e) => updateDraftField(name, field, e.target.value)}
        />
        <div className="sc-formula-tools">
          <div className="sc-formula-ops">
            {FORMULA_OPERATOR_TOKENS.map((token) => (
              <button
                key={`${field}-${token}`}
                className="sc-formula-op-btn"
                type="button"
                disabled={!enabled}
                onClick={() => appendFormulaToken(name, field, token)}
              >
                {token}
              </button>
            ))}
          </div>
          <select
            className="sc-formula-var-select"
            disabled={!enabled}
            value=""
            onChange={(e) => {
              if (!e.target.value) return;
              appendFormulaToken(name, field, e.target.value);
              e.target.value = ""; // Reset after selection (in React wait doesn't easily work with synthetic events without ref but for select it usually works fine if controlled by key hack or just value="")
            }}
          >
            <option value="">Insert variable...</option>
            {formulaVars.map((variableName) => (
              <option key={`${field}-${variableName}`} value={variableName}>
                {variableName}
              </option>
            ))}
          </select>
        </div>
        <span className="sc-field-meta">
          Example: {isEntryFormula ? entryExample : exitExample}
        </span>
      </div>
    );
  }

  if (field === "allowed_regimes" && Array.isArray(value)) {
    return (
      <div key={field} className="sc-regime-field">
        <span className="sc-field-label">Allowed Regimes</span>
        <div className="sc-regime-options">
          {regimeOptions.map((opt) => {
            const checked = (
              drafts[name]?.allowed_regimes ||
              value ||
              []
            ).includes(opt);
            return (
              <label key={opt} className="sc-regime-chip">
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={(e) => {
                    const current = new Set(
                      drafts[name]?.allowed_regimes || value || [],
                    );
                    e.target.checked ? current.add(opt) : current.delete(opt);
                    updateDraftField(
                      name,
                      "allowed_regimes",
                      Array.from(current),
                    );
                  }}
                />
                {opt}
              </label>
            );
          })}
        </div>
        {fieldGuide && (
          <span className="sc-field-meta" title={fieldGuide.behavior}>
            Pro: {fieldGuide.range}
          </span>
        )}
      </div>
    );
  }

  if (
    field === "trailing_stop_mode" ||
    field === "exit_mode" ||
    field === "risk_mode"
  ) {
    const isRiskMode = field === "risk_mode";
    const modeField = isRiskMode ? "risk_mode" : "exit_mode";
    const currentMode =
      String(
        drafts[name]?.[modeField] ??
          drafts[name]?.trailing_stop_mode ??
          value ??
          "custom",
      )
        .trim()
        .toLowerCase() === "global"
        ? "global"
        : "custom";
    return (
      <div className="sc-field" key={field}>
        <label className="sc-field-label">
          {isRiskMode ? "Risk Source" : "Exit Source"}
        </label>
        <select
          value={currentMode}
          onChange={(e) =>
            setDrafts((prev) => ({
              ...prev,
              [name]: {
                ...(prev[name] || {}),
                [modeField]: e.target.value,
                ...(!isRiskMode
                  ? { trailing_stop_mode: e.target.value }
                  : {}),
              },
            }))
          }
          className="sc-field-input"
          title={guideTitle}
        >
          <option value="custom">Custom (strategy)</option>
          <option value="global">Global (modules)</option>
        </select>
        {fieldGuide && (
          <span className="sc-field-meta" title={fieldGuide.behavior}>
            Pro: {fieldGuide.range}
          </span>
        )}
      </div>
    );
  }

  if (typeof value === "number") {
    return (
      <div className="sc-field" key={field}>
        <label className="sc-field-label">{formatFieldLabel(field)}</label>
        <input
          type="number"
          step="0.01"
          value={drafts[name]?.[field] ?? value}
          onChange={(e) => updateDraftField(name, field, Number(e.target.value))}
          className="sc-field-input"
          title={guideTitle}
        />
        {fieldGuide && (
          <span className="sc-field-meta" title={fieldGuide.behavior}>
            Pro: {fieldGuide.range}
          </span>
        )}
      </div>
    );
  }

  if (typeof value === "boolean") {
    return (
      <div className="sc-field sc-field-bool" key={field}>
        <label className="sc-field-label">{formatFieldLabel(field)}</label>
        <input
          type="checkbox"
          checked={drafts[name]?.[field] ?? value}
          onChange={(e) => updateDraftField(name, field, e.target.checked)}
          className="sc-field-check"
          title={guideTitle}
        />
        {fieldGuide && (
          <span className="sc-field-meta" title={fieldGuide.behavior}>
            Pro: {fieldGuide.range}
          </span>
        )}
      </div>
    );
  }

  return null;
}
