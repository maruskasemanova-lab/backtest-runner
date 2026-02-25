type ExecutionModuleRowLike = {
  key?: unknown;
};

type ExecutionConfigSnapshotLike = Record<string, unknown> | null | undefined;

export const buildExpandedExecutionModuleDefaults = (
  modules: ExecutionModuleRowLike[],
): Record<string, boolean> => {
  const defaults: Record<string, boolean> = {};
  modules.forEach((module) => {
    const moduleKey = String(module?.key || "").trim();
    if (!moduleKey) return;
    defaults[moduleKey] = true;
  });
  return defaults;
};

export const countEnabledExecutionModules = (
  modules: ExecutionConfigSnapshotLike,
  profileKeys: readonly string[],
): number => {
  return profileKeys.reduce((acc, key) => acc + (modules?.[key] ? 1 : 0), 0);
};
