import type { Dispatch, SetStateAction } from "react";
import type {
  AdaptiveStudioFormState,
  AdaptiveStudioFormUpdater,
  AdaptiveStudioObjectRecord,
  AdaptiveStudioPriorityScope,
  AdaptiveStudioUnifiedProfileRow,
} from "../profileTypes";
import { useAdaptiveStudioEditorFormActions } from "./useAdaptiveStudioEditorFormActions";
import { useAdaptiveStudioUnifiedProfileActions } from "./useAdaptiveStudioUnifiedProfileActions";

type SaveAdaptiveConfigFn = (args: {
  nextConfig: AdaptiveStudioObjectRecord;
}) => Promise<AdaptiveStudioObjectRecord>;

type CaptureUnifiedProfileFn = (args: {
  profileName: string;
  setActive?: boolean;
}) => Promise<void>;

type ApplyUnifiedProfileFn = (args: {
  profile: AdaptiveStudioUnifiedProfileRow | null | undefined;
}) => Promise<void>;

type UseAdaptiveStudioEditorActionsArgs = {
  activeTicker: string;
  strategyUniverse: string[];
  rawTickerConfig: AdaptiveStudioObjectRecord;
  form: AdaptiveStudioFormState;
  unifiedDraftName: string;
  refreshAllData: () => Promise<void>;
  readExecutionConfigSnapshot: () => AdaptiveStudioObjectRecord;
  mergeExecutionConfigSnapshot: (snapshot: AdaptiveStudioObjectRecord) => void;
  saveAdaptiveConfig: SaveAdaptiveConfigFn;
  captureUnifiedProfile: CaptureUnifiedProfileFn;
  applyUnifiedProfile: ApplyUnifiedProfileFn;
  setError: Dispatch<SetStateAction<string | null>>;
  setNotice: Dispatch<SetStateAction<string | null>>;
  setForm: Dispatch<SetStateAction<AdaptiveStudioFormState>>;
  setIsDirty: Dispatch<SetStateAction<boolean>>;
};

type UseAdaptiveStudioEditorActionsResult = {
  updateForm: (updater: AdaptiveStudioFormUpdater) => void;
  markExecutionConfigDirty: () => void;
  handleSave: () => Promise<void>;
  handleReload: () => Promise<void>;
  handleCaptureUnifiedProfile: () => Promise<void>;
  handleSetActiveUnifiedProfile: (
    profile: AdaptiveStudioUnifiedProfileRow | null | undefined,
  ) => Promise<void>;
  handleLoadUnifiedProfileToEditor: (
    profile: AdaptiveStudioUnifiedProfileRow | null | undefined,
  ) => void;
  handleStrategySelectionModeChange: (value: unknown) => void;
  handleMaxActiveStrategiesChange: (value: unknown) => void;
  handleFlowBiasEnabledChange: (checked: boolean) => void;
  handleUseOhlcvFallbacksChange: (checked: boolean) => void;
  handleMinActiveBarsBeforeSwitchChange: (value: unknown) => void;
  handleSwitchCooldownBarsChange: (value: unknown) => void;
  movePriorityItem: (
    scope: AdaptiveStudioPriorityScope,
    key: string,
    index: number,
    direction: number,
  ) => void;
  toggleStrategyInList: (
    scope: AdaptiveStudioPriorityScope,
    key: string,
    strategy: string,
  ) => void;
  moveFlowBiasStrategy: (index: number, direction: number) => void;
  toggleFlowBiasStrategy: (strategy: string) => void;
};

export function useAdaptiveStudioEditorActions({
  activeTicker,
  strategyUniverse,
  rawTickerConfig,
  form,
  unifiedDraftName,
  refreshAllData,
  readExecutionConfigSnapshot,
  mergeExecutionConfigSnapshot,
  saveAdaptiveConfig,
  captureUnifiedProfile,
  applyUnifiedProfile,
  setError,
  setNotice,
  setForm,
  setIsDirty,
}: UseAdaptiveStudioEditorActionsArgs): UseAdaptiveStudioEditorActionsResult {
  const formActions = useAdaptiveStudioEditorFormActions({
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
  });

  const unifiedProfileActions = useAdaptiveStudioUnifiedProfileActions({
    activeTicker,
    strategyUniverse,
    rawTickerConfig,
    unifiedDraftName,
    refreshAllData,
    mergeExecutionConfigSnapshot,
    captureUnifiedProfile,
    applyUnifiedProfile,
    setError,
    setNotice,
    setForm,
    setIsDirty,
  });

  return {
    ...formActions,
    ...unifiedProfileActions,
  };
}
