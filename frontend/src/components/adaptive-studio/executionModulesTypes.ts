export type ExecutionModuleFieldOption = {
  value?: unknown;
  label?: unknown;
};

export type ExecutionModuleField = {
  key: string;
  label: string;
  type?: string;
  min?: number;
  max?: number;
  step?: number;
  fallback?: unknown;
  options?: ExecutionModuleFieldOption[];
  disabledWhen?: (snapshot: Record<string, unknown>) => boolean;
};

export type ExecutionModuleDefinition = {
  key: string;
  label: string;
  category: string;
  description?: string;
  configKey: string;
};

export type ExecutionModulesSnapshot = Record<string, unknown>;

export type OnToggleExecutionModuleExpanded = (moduleKey: string) => void;
export type OnToggleExecutionModuleEnabled = (configKey: string, checked: boolean) => void;
export type GetExecutionParamValue = (field: ExecutionModuleField) => unknown;
export type OnExecutionModuleFieldValueChange = (
  field: ExecutionModuleField,
  rawValue: unknown,
) => void;
