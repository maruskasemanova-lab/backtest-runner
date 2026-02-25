import { useCallback } from "react";
import type {
  ExecutionModuleField,
  OnExecutionModuleFieldValueChange,
  OnToggleExecutionModuleEnabled,
} from "./executionModulesTypes";

type ApplyExecutionFieldChangeOptions = {
  raw?: boolean;
};

type ApplyExecutionFieldChange = (
  configKey: string,
  value: unknown,
  options?: ApplyExecutionFieldChangeOptions,
) => void;

type NormalizeExecutionParamValue = (value: unknown, field: ExecutionModuleField) => unknown;

type Params = {
  applyExecutionFieldChange: ApplyExecutionFieldChange;
  normalizeExecutionParamValue: NormalizeExecutionParamValue;
};

type Result = {
  handleToggleEnabled: OnToggleExecutionModuleEnabled;
  handleFieldValueChange: OnExecutionModuleFieldValueChange;
};

export function useAdaptiveStudioExecutionModuleHandlers({
  applyExecutionFieldChange,
  normalizeExecutionParamValue,
}: Params): Result {
  const handleToggleEnabled = useCallback<OnToggleExecutionModuleEnabled>(
    (configKey, checked) => {
      applyExecutionFieldChange(configKey, checked, { raw: true });
    },
    [applyExecutionFieldChange],
  );

  const handleFieldValueChange = useCallback<OnExecutionModuleFieldValueChange>(
    (field, rawValue) => {
      applyExecutionFieldChange(field.key, normalizeExecutionParamValue(rawValue, field), { raw: true });
    },
    [applyExecutionFieldChange, normalizeExecutionParamValue],
  );

  return {
    handleToggleEnabled,
    handleFieldValueChange,
  };
}
