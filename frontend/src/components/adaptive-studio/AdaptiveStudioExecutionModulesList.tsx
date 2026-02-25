import AdaptiveStudioExecutionModuleCard from "./AdaptiveStudioExecutionModuleCard";
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
  modules: readonly ExecutionModuleDefinition[];
  moduleFieldsByModule: Record<string, ExecutionModuleField[]>;
  categoryLabelsByCategory: Record<string, string>;
  executionConfigSnapshot: ExecutionModulesSnapshot | null | undefined;
  expandedExecutionModules: Record<string, boolean>;
  coerceBooleanValue: (value: unknown, fallback?: boolean) => boolean;
  onToggleExpanded: OnToggleExecutionModuleExpanded;
  onToggleEnabled: OnToggleExecutionModuleEnabled;
  getExecutionParamValue: GetExecutionParamValue;
  onFieldValueChange: OnExecutionModuleFieldValueChange;
};

export default function AdaptiveStudioExecutionModulesList({
  modules,
  moduleFieldsByModule,
  categoryLabelsByCategory,
  executionConfigSnapshot,
  expandedExecutionModules,
  coerceBooleanValue,
  onToggleExpanded,
  onToggleEnabled,
  getExecutionParamValue,
  onFieldValueChange,
}: Props) {
  return (
    <div className="sc-list">
      {modules.map((module) => {
        const enabled = !!coerceBooleanValue(executionConfigSnapshot?.[module.configKey], false);
        const moduleFields = moduleFieldsByModule[module.key] || [];
        const isExpanded = !!expandedExecutionModules[module.key];
        const categoryLabel = categoryLabelsByCategory[module.category] || "Other";
        return (
          <AdaptiveStudioExecutionModuleCard
            key={module.key}
            module={module}
            enabled={enabled}
            isExpanded={isExpanded}
            categoryLabel={categoryLabel}
            moduleFields={moduleFields}
            executionConfigSnapshot={executionConfigSnapshot || {}}
            onToggleExpanded={onToggleExpanded}
            onToggleEnabled={onToggleEnabled}
            getExecutionParamValue={getExecutionParamValue}
            onFieldValueChange={onFieldValueChange}
          />
        );
      })}
    </div>
  );
}
