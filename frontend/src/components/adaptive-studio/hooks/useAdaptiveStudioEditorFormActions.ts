import type { Dispatch, SetStateAction } from "react";
import type {
  AdaptiveStudioFormState,
  AdaptiveStudioFormUpdater,
  AdaptiveStudioObjectRecord,
  AdaptiveStudioPriorityScope,
} from "../profileTypes";
import { DEFAULT_FLOW_BIAS_STRATEGIES } from "../constants/adaptive-studio";
import { buildAdaptiveConfigUpdate } from "../utils/adaptive-studio-builders";
import {
  cloneMap,
  normalizeExecutionModulesSnapshot,
  normalizeExecutionParamsSnapshot,
  normalizeMaxActive,
  normalizeMode,
  normalizeNonNegativeInt,
  normalizeStrategyList,
  normalizeTickerAdaptiveForm,
} from "../utils/adaptive-studio-transformers";

type SaveAdaptiveConfigFn = (args: {
  nextConfig: AdaptiveStudioObjectRecord;
}) => Promise<AdaptiveStudioObjectRecord>;

type UseAdaptiveStudioEditorFormActionsArgs = {
  activeTicker: string;
  strategyUniverse: string[];
  rawTickerConfig: AdaptiveStudioObjectRecord;
  form: AdaptiveStudioFormState;
  readExecutionConfigSnapshot: () => AdaptiveStudioObjectRecord;
  saveAdaptiveConfig: SaveAdaptiveConfigFn;
  setError: Dispatch<SetStateAction<string | null>>;
  setNotice: Dispatch<SetStateAction<string | null>>;
  setForm: Dispatch<SetStateAction<AdaptiveStudioFormState>>;
  setIsDirty: Dispatch<SetStateAction<boolean>>;
};

export function useAdaptiveStudioEditorFormActions({
  activeTicker,
  strategyUniverse,
  rawTickerConfig,
  form,
  readExecutionConfigSnapshot,
  saveAdaptiveConfig,
  setError,
  setNotice,
  setForm,
  setIsDirty,
}: UseAdaptiveStudioEditorFormActionsArgs) {
  const updateForm = (updater: AdaptiveStudioFormUpdater) => {
    setForm((prev) => {
      const next = typeof updater === "function" ? updater(prev) : updater;
      return next;
    });
    setIsDirty(true);
    setNotice(null);
  };

  const markExecutionConfigDirty = () => {
    setIsDirty(true);
    setNotice(null);
  };

  const updatePriorityList = (
    scope: AdaptiveStudioPriorityScope,
    key: string,
    nextList: string[],
  ) => {
    const normalized = normalizeStrategyList(nextList, [], strategyUniverse);
    updateForm((prev) => {
      const nextScope = cloneMap(prev[scope]);
      nextScope[key] = normalized;
      return {
        ...prev,
        [scope]: nextScope,
      };
    });
  };

  const toggleStrategyInList = (
    scope: AdaptiveStudioPriorityScope,
    key: string,
    strategy: string,
  ) => {
    const current = form?.[scope]?.[key] || [];
    const exists = current.includes(strategy);
    const next = exists ? current.filter((item) => item !== strategy) : [...current, strategy];
    updatePriorityList(scope, key, next);
  };

  const movePriorityItem = (
    scope: AdaptiveStudioPriorityScope,
    key: string,
    index: number,
    direction: number,
  ) => {
    const current = form?.[scope]?.[key] || [];
    const target = index + direction;
    if (target < 0 || target >= current.length) return;
    const next = [...current];
    const [item] = next.splice(index, 1);
    next.splice(target, 0, item);
    updatePriorityList(scope, key, next);
  };

  const updateFlowBiasStrategies = (nextList: string[]) => {
    updateForm((prev) => ({
      ...prev,
      flow_bias_strategies: normalizeStrategyList(
        nextList,
        DEFAULT_FLOW_BIAS_STRATEGIES,
        strategyUniverse,
      ),
    }));
  };

  const toggleFlowBiasStrategy = (strategy: string) => {
    const current = form.flow_bias_strategies || [];
    const exists = current.includes(strategy);
    updateFlowBiasStrategies(
      exists ? current.filter((item) => item !== strategy) : [...current, strategy],
    );
  };

  const moveFlowBiasStrategy = (index: number, direction: number) => {
    const current = [...(form.flow_bias_strategies || [])];
    const target = index + direction;
    if (target < 0 || target >= current.length) return;
    const [item] = current.splice(index, 1);
    current.splice(target, 0, item);
    updateFlowBiasStrategies(current);
  };

  const handleSave = async () => {
    if (!activeTicker) return;
    setError(null);
    setNotice(null);

    try {
      const executionSnapshot = readExecutionConfigSnapshot();
      const nextConfig = buildAdaptiveConfigUpdate({
        rawTickerConfig,
        form,
        strategyUniverse,
        executionModulesSnapshot: normalizeExecutionModulesSnapshot(executionSnapshot),
        executionParamsSnapshot: normalizeExecutionParamsSnapshot(executionSnapshot),
      });

      await saveAdaptiveConfig({ nextConfig });
      setForm(normalizeTickerAdaptiveForm(nextConfig, strategyUniverse));
      setIsDirty(false);
      setNotice("Adaptive + execution configuration saved. Changes are applied on the next run start.");
    } catch (err) {
      console.error("Failed to save adaptive config:", err);
      setError("Failed to save adaptive configuration.");
    }
  };

  const handleStrategySelectionModeChange = (value: unknown) => {
    updateForm((prev) => ({
      ...prev,
      strategy_selection_mode: normalizeMode(value),
    }));
  };

  const handleMaxActiveStrategiesChange = (value: unknown) => {
    updateForm((prev) => ({
      ...prev,
      max_active_strategies: normalizeMaxActive(value, 3),
    }));
  };

  const handleFlowBiasEnabledChange = (checked: boolean) => {
    updateForm((prev) => ({
      ...prev,
      flow_bias_enabled: checked,
    }));
  };

  const handleUseOhlcvFallbacksChange = (checked: boolean) => {
    updateForm((prev) => ({
      ...prev,
      use_ohlcv_fallbacks: checked,
    }));
  };

  const handleMinActiveBarsBeforeSwitchChange = (value: unknown) => {
    updateForm((prev) => ({
      ...prev,
      min_active_bars_before_switch: normalizeNonNegativeInt(value, 0),
    }));
  };

  const handleSwitchCooldownBarsChange = (value: unknown) => {
    updateForm((prev) => ({
      ...prev,
      switch_cooldown_bars: normalizeNonNegativeInt(value, 0),
    }));
  };

  return {
    updateForm,
    markExecutionConfigDirty,
    handleSave,
    handleStrategySelectionModeChange,
    handleMaxActiveStrategiesChange,
    handleFlowBiasEnabledChange,
    handleUseOhlcvFallbacksChange,
    handleMinActiveBarsBeforeSwitchChange,
    handleSwitchCooldownBarsChange,
    movePriorityItem,
    toggleStrategyInList,
    moveFlowBiasStrategy,
    toggleFlowBiasStrategy,
  };
}
