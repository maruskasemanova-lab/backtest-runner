import type { ReactNode } from "react";

export type RiskManagementConfig = Record<string, any>;
export type RiskManagementChangeHandler = (field: string, value: any) => void;

type RiskManagementPanelProps = {
  title: string;
  hint: string;
  children: ReactNode;
};

type RiskManagementNumberFieldProps = {
  config: RiskManagementConfig;
  field: string;
  label: string;
  handleChange: RiskManagementChangeHandler;
  min?: number | string;
  max?: number | string;
  step?: number | string;
  disabled?: boolean;
  fallbackValue?: number;
  normalize?: (value: number) => number;
};

type RiskManagementCheckboxFieldProps = {
  field: string;
  label: string;
  checked: boolean;
  handleChange: RiskManagementChangeHandler;
};

type RiskManagementSelectOption = {
  value: string;
  label: string;
};

type RiskManagementSelectFieldProps = {
  config: RiskManagementConfig;
  field: string;
  label: string;
  handleChange: RiskManagementChangeHandler;
  options: RiskManagementSelectOption[];
  defaultValue?: string;
};

export function RiskManagementPanel({
  title,
  hint,
  children,
}: RiskManagementPanelProps) {
  return (
    <div className="tw-panel">
      <div className="tw-panel-title">{title}</div>
      <div className="tw-panel-hint">{hint}</div>
      {children}
    </div>
  );
}

export function RiskManagementNumberField({
  config,
  field,
  label,
  handleChange,
  min,
  max,
  step,
  disabled,
  fallbackValue,
  normalize,
}: RiskManagementNumberFieldProps) {
  const value = config[field] ?? (fallbackValue ?? "");

  return (
    <div className="form-group">
      <label htmlFor={field}>{label}</label>
      <input
        id={field}
        type="number"
        min={min}
        max={max}
        step={step}
        value={value}
        disabled={disabled}
        onChange={(event) => {
          const rawValue = Number(event.target.value);
          handleChange(field, normalize ? normalize(rawValue) : rawValue);
        }}
      />
    </div>
  );
}

export function RiskManagementCheckboxField({
  field,
  label,
  checked,
  handleChange,
}: RiskManagementCheckboxFieldProps) {
  return (
    <div className="form-group">
      <label className="field-row" htmlFor={field}>
        <span>{label}</span>
        <input
          id={field}
          type="checkbox"
          checked={checked}
          onChange={(event) => handleChange(field, event.target.checked)}
        />
      </label>
    </div>
  );
}

export function RiskManagementSelectField({
  config,
  field,
  label,
  handleChange,
  options,
  defaultValue = "",
}: RiskManagementSelectFieldProps) {
  return (
    <div className="form-group">
      <label htmlFor={field}>{label}</label>
      <select
        id={field}
        value={config[field] || defaultValue}
        onChange={(event) => handleChange(field, event.target.value)}
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </div>
  );
}
