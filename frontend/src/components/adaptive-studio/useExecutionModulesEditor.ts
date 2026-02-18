import { useCallback, useEffect, useMemo, useState } from "react";

interface ExecutionModuleRow {
  key: string;
}

interface ExecutionParamField {
  key: string;
}

interface UseExecutionModulesEditorArgs {
  modules: ExecutionModuleRow[];
  normalizeExecutionParamValue: (value: unknown, field: ExecutionParamField) => unknown;
  readExecutionConfigSnapshot: () => Record<string, any>;
}

interface UseExecutionModulesEditorResult {
  executionConfigSnapshot: Record<string, any>;
  expandedExecutionModules: Record<string, boolean>;
  toggleExecutionModuleExpanded: (moduleKey: string) => void;
  expandAllExecutionModules: () => void;
  collapseAllExecutionModules: () => void;
  refreshExecutionConfigSnapshot: () => void;
  updateExecutionConfigField: (configKey: string, value: unknown, options?: Record<string, any>) => void;
  mergeExecutionConfigSnapshot: (snapshot: Record<string, any>) => void;
  getExecutionParamValue: (field: ExecutionParamField) => unknown;
}

const EXEC_CONFIG_SNAPSHOT_EVENT = "execution-config-snapshot";
const EXEC_CONFIG_SNAPSHOT_REQUEST_EVENT = "execution-config-snapshot-request";
const EXEC_MODULE_TOGGLE_EVENT = "execution-module-toggle";

const buildExpandedDefaults = (modules: ExecutionModuleRow[]) => {
  const defaults: Record<string, boolean> = {};
  modules.forEach((module) => {
    const moduleKey = String(module?.key || "").trim();
    if (!moduleKey) return;
    defaults[moduleKey] = true;
  });
  return defaults;
};

export const useExecutionModulesEditor = ({
  modules,
  normalizeExecutionParamValue,
  readExecutionConfigSnapshot,
}: UseExecutionModulesEditorArgs): UseExecutionModulesEditorResult => {
  const expandedDefaults = useMemo(() => buildExpandedDefaults(modules), [modules]);
  const [executionConfigSnapshot, setExecutionConfigSnapshot] = useState<Record<string, any>>(
    () => readExecutionConfigSnapshot(),
  );
  const [expandedExecutionModules, setExpandedExecutionModules] = useState<Record<string, boolean>>(
    () => ({ ...expandedDefaults }),
  );

  useEffect(() => {
    setExpandedExecutionModules((prev) => ({
      ...expandedDefaults,
      ...(prev && typeof prev === "object" ? prev : {}),
    }));
  }, [expandedDefaults]);

  useEffect(() => {
    const handleExecutionSnapshot = (event: Event) => {
      const detail = (event as CustomEvent).detail;
      if (!detail || typeof detail !== "object" || Array.isArray(detail)) return;
      setExecutionConfigSnapshot(detail as Record<string, any>);
    };

    window.addEventListener(EXEC_CONFIG_SNAPSHOT_EVENT, handleExecutionSnapshot);
    const initialSnapshot = readExecutionConfigSnapshot();
    if (Object.keys(initialSnapshot).length) {
      setExecutionConfigSnapshot(initialSnapshot);
    }
    window.dispatchEvent(new CustomEvent(EXEC_CONFIG_SNAPSHOT_REQUEST_EVENT));

    return () => {
      window.removeEventListener(EXEC_CONFIG_SNAPSHOT_EVENT, handleExecutionSnapshot);
    };
  }, [readExecutionConfigSnapshot]);

  const toggleExecutionModuleExpanded = useCallback((moduleKey: string) => {
    setExpandedExecutionModules((prev) => ({
      ...(prev && typeof prev === "object" ? prev : {}),
      [moduleKey]: !prev?.[moduleKey],
    }));
  }, []);

  const expandAllExecutionModules = useCallback(() => {
    setExpandedExecutionModules({ ...expandedDefaults });
  }, [expandedDefaults]);

  const collapseAllExecutionModules = useCallback(() => {
    const next: Record<string, boolean> = {};
    modules.forEach((module) => {
      const moduleKey = String(module?.key || "").trim();
      if (!moduleKey) return;
      next[moduleKey] = false;
    });
    setExpandedExecutionModules(next);
  }, [modules]);

  const refreshExecutionConfigSnapshot = useCallback(() => {
    window.dispatchEvent(new CustomEvent(EXEC_CONFIG_SNAPSHOT_REQUEST_EVENT));
    setExecutionConfigSnapshot(readExecutionConfigSnapshot());
  }, [readExecutionConfigSnapshot]);

  const updateExecutionConfigField = useCallback(
    (configKey: string, value: unknown, options: Record<string, any> = {}) => {
      const nextValue = options?.raw === true ? value : Number(value);
      setExecutionConfigSnapshot((prev) => ({
        ...(prev && typeof prev === "object" ? prev : {}),
        [configKey]: nextValue,
      }));
      window.dispatchEvent(
        new CustomEvent(EXEC_MODULE_TOGGLE_EVENT, {
          detail: { configKey, value: nextValue },
        }),
      );
    },
    [],
  );

  const mergeExecutionConfigSnapshot = useCallback((snapshot: Record<string, any>) => {
    setExecutionConfigSnapshot((prev) => ({
      ...(prev && typeof prev === "object" ? prev : {}),
      ...(snapshot && typeof snapshot === "object" ? snapshot : {}),
    }));
  }, []);

  const getExecutionParamValue = useCallback(
    (field: ExecutionParamField) => {
      return normalizeExecutionParamValue(executionConfigSnapshot?.[field.key], field);
    },
    [executionConfigSnapshot, normalizeExecutionParamValue],
  );

  return {
    executionConfigSnapshot,
    expandedExecutionModules,
    toggleExecutionModuleExpanded,
    expandAllExecutionModules,
    collapseAllExecutionModules,
    refreshExecutionConfigSnapshot,
    updateExecutionConfigField,
    mergeExecutionConfigSnapshot,
    getExecutionParamValue,
  };
};
