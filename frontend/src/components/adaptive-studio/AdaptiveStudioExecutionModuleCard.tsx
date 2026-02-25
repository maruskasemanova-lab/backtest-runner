import type { MouseEvent } from "react";
import type {
  ExecutionModuleDefinition,
  ExecutionModuleField,
  ExecutionModulesSnapshot,
  GetExecutionParamValue,
  OnExecutionModuleFieldValueChange,
  OnToggleExecutionModuleEnabled,
  OnToggleExecutionModuleExpanded,
} from "./executionModulesTypes";

type Props = {
  module: ExecutionModuleDefinition;
  enabled: boolean;
  isExpanded: boolean;
  categoryLabel: string;
  moduleFields: ExecutionModuleField[];
  executionConfigSnapshot: ExecutionModulesSnapshot;
  onToggleExpanded: OnToggleExecutionModuleExpanded;
  onToggleEnabled: OnToggleExecutionModuleEnabled;
  getExecutionParamValue: GetExecutionParamValue;
  onFieldValueChange: OnExecutionModuleFieldValueChange;
};

export default function AdaptiveStudioExecutionModuleCard({
  module,
  enabled,
  isExpanded,
  categoryLabel,
  moduleFields,
  executionConfigSnapshot,
  onToggleExpanded,
  onToggleEnabled,
  getExecutionParamValue,
  onFieldValueChange,
}: Props) {
  const handleControlsClick = (e: MouseEvent<HTMLDivElement>) => {
    e.stopPropagation();
  };

  return (
    <div
      className={`sc-item ${enabled ? "on" : "off"} ${isExpanded ? "open" : ""}`}
    >
      <div
        className="sc-item-head"
        onClick={() => onToggleExpanded(module.key)}
      >
        <div className="sc-item-info">
          <span className="sc-item-name">{module.label}</span>
          <span className={`sc-cat ${module.category}`}>{categoryLabel}</span>
          <span className="sc-regimes">{module.description}</span>
        </div>
        <div className="sc-item-controls" onClick={handleControlsClick}>
          <label className="switch" htmlFor={`studio_module_${module.key}`}>
            <input
              id={`studio_module_${module.key}`}
              type="checkbox"
              checked={enabled}
              onChange={(e) => onToggleEnabled(module.configKey, e.target.checked)}
            />
            <span className="slider" />
          </label>
        </div>
        <span className={`sc-expand-arrow ${isExpanded ? "open" : ""}`}>›</span>
      </div>

      {isExpanded && (
        <div className="sc-item-body">
          <div className="sc-section">
            <div className="sc-section-label">Configuration</div>
            {moduleFields.length === 0 ? (
              <div className="sc-msg">No additional configuration fields.</div>
            ) : (
              <div className="sc-grid">
                {moduleFields.map((field) => {
                  const fieldId = `studio_${module.key}_${field.key}`;
                  const fieldDisabled =
                    typeof field?.disabledWhen === "function"
                      ? !!field.disabledWhen(executionConfigSnapshot || {})
                      : false;

                  if (field.type === "boolean") {
                    return (
                      <div key={field.key} className="sc-field sc-field-bool">
                        <label className="sc-field-label" htmlFor={fieldId}>
                          {field.label}
                        </label>
                        <input
                          id={fieldId}
                          type="checkbox"
                          className="sc-field-check"
                          checked={!!getExecutionParamValue(field)}
                          disabled={fieldDisabled}
                          onChange={(e) => onFieldValueChange(field, e.target.checked)}
                        />
                      </div>
                    );
                  }

                  if (field.type === "select") {
                    const selectedValue = String(
                      getExecutionParamValue(field) ?? field.fallback ?? "",
                    );
                    return (
                      <div key={field.key} className="sc-field">
                        <label className="sc-field-label" htmlFor={fieldId}>
                          {field.label}
                        </label>
                        <select
                          id={fieldId}
                          className="sc-field-input"
                          value={selectedValue}
                          disabled={fieldDisabled}
                          onChange={(e) => onFieldValueChange(field, e.target.value)}
                        >
                          {(Array.isArray(field.options) ? field.options : []).map((option) => {
                            const optionValue = String(option?.value || "");
                            const optionLabel = String(option?.label || optionValue);
                            return (
                              <option key={optionValue} value={optionValue}>
                                {optionLabel}
                              </option>
                            );
                          })}
                        </select>
                      </div>
                    );
                  }

                  return (
                    <div key={field.key} className="sc-field">
                      <label className="sc-field-label" htmlFor={fieldId}>
                        {field.label}
                      </label>
                      <input
                        id={fieldId}
                        type="number"
                        min={field.min}
                        max={field.max}
                        step={field.step}
                        className="sc-field-input"
                        value={
                          getExecutionParamValue(field) as
                            | string
                            | number
                            | readonly string[]
                            | undefined
                        }
                        disabled={fieldDisabled}
                        onChange={(e) => onFieldValueChange(field, e.target.value)}
                      />
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
