import AdaptiveStudioExecutionModulesList from "./AdaptiveStudioExecutionModulesList";
import AdaptiveStudioExecutionModulesToolbar from "./AdaptiveStudioExecutionModulesToolbar";
import { countEnabledExecutionModules } from "./executionModulesUtils";
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
  moduleProfileKeys: readonly string[];
  moduleFieldsByModule: Record<string, ExecutionModuleField[]>;
  categoryLabelsByCategory: Record<string, string>;
  executionConfigSnapshot: ExecutionModulesSnapshot | null | undefined;
  expandedExecutionModules: Record<string, boolean>;
  coerceBooleanValue: (value: unknown, fallback?: boolean) => boolean;
  onRefresh: () => void;
  onExpandAll: () => void;
  onCollapseAll: () => void;
  onToggleExpanded: OnToggleExecutionModuleExpanded;
  onToggleEnabled: OnToggleExecutionModuleEnabled;
  getExecutionParamValue: GetExecutionParamValue;
  onFieldValueChange: OnExecutionModuleFieldValueChange;
};

export default function AdaptiveStudioExecutionModulesPanel({
  modules,
  moduleProfileKeys,
  moduleFieldsByModule,
  categoryLabelsByCategory,
  executionConfigSnapshot,
  expandedExecutionModules,
  coerceBooleanValue,
  onRefresh,
  onExpandAll,
  onCollapseAll,
  onToggleExpanded,
  onToggleEnabled,
  getExecutionParamValue,
  onFieldValueChange,
}: Props) {
  return (
    <div className="sc-panel">
      <AdaptiveStudioExecutionModulesToolbar
        enabledCount={countEnabledExecutionModules(executionConfigSnapshot, moduleProfileKeys)}
        totalCount={modules.length}
        onRefresh={onRefresh}
        onExpandAll={onExpandAll}
        onCollapseAll={onCollapseAll}
      />

      <AdaptiveStudioExecutionModulesList
        modules={modules}
        moduleFieldsByModule={moduleFieldsByModule}
        categoryLabelsByCategory={categoryLabelsByCategory}
        executionConfigSnapshot={executionConfigSnapshot}
        expandedExecutionModules={expandedExecutionModules}
        coerceBooleanValue={coerceBooleanValue}
        onToggleExpanded={onToggleExpanded}
        onToggleEnabled={onToggleEnabled}
        getExecutionParamValue={getExecutionParamValue}
        onFieldValueChange={onFieldValueChange}
      />
    </div>
  );
}
