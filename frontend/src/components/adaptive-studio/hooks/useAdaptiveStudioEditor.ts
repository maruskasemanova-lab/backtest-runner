import { useState } from "react";
import type {
  AdaptiveStudioActionLoadingToken,
  AdaptiveStudioFormState,
  AdaptiveStudioFormUpdater,
  AdaptiveStudioObjectRecord,
  AdaptiveStudioPriorityScope,
  AdaptiveStudioTunedProfileRow,
  AdaptiveStudioUnifiedProfileRow,
  AdaptiveStudioUnifiedViewTab,
} from "../profileTypes";
import {
  ADAPTIVE_STUDIO_TABS,
  DEFAULT_STRATEGIES,
} from "../constants/adaptive-studio";
import {
  asObject,
  flowSummary,
  normalizeMaxActive,
  normalizeTickerAdaptiveForm,
} from "../utils/adaptive-studio-transformers";
import { useAdaptiveStudioEditorActions } from "./useAdaptiveStudioEditorActions";
import { useAdaptiveStudioEditorSync } from "./useAdaptiveStudioEditorSync";

type AdaptiveStudioTabId = (typeof ADAPTIVE_STUDIO_TABS)[number]["id"];

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

type UseAdaptiveStudioEditorArgs = {
  activeTicker: string;
  availableTickers: string[];
  strategyUniverse: string[];
  rawTickerConfig: AdaptiveStudioObjectRecord;
  profileList: AdaptiveStudioTunedProfileRow[];
  activeProfileIdFromServer: string;
  unifiedList: AdaptiveStudioUnifiedProfileRow[];
  activeUnifiedIdFromServer: string;
  loading: boolean;
  profileLoading: boolean;
  comboLoading: boolean;
  unifiedLoading: boolean;
  saving: boolean;
  unifiedActionLoading: AdaptiveStudioActionLoadingToken;
  tickerConfigError: string | null;
  refreshAllData: () => Promise<void>;
  refreshExecutionConfigSnapshot: () => void;
  mergeExecutionConfigSnapshot: (snapshot: AdaptiveStudioObjectRecord) => void;
  readExecutionConfigSnapshot: () => AdaptiveStudioObjectRecord;
  saveAdaptiveConfig: SaveAdaptiveConfigFn;
  captureUnifiedProfile: CaptureUnifiedProfileFn;
  applyUnifiedProfile: ApplyUnifiedProfileFn;
};

type UseAdaptiveStudioEditorResult = {
  activeTab: AdaptiveStudioTabId;
  setActiveTab: (tab: AdaptiveStudioTabId) => void;
  error: string | null;
  notice: string | null;
  form: AdaptiveStudioFormState;
  unifiedDraftName: string;
  setUnifiedDraftName: (value: string) => void;
  unifiedViewTab: AdaptiveStudioUnifiedViewTab;
  setUnifiedViewTab: (tab: AdaptiveStudioUnifiedViewTab) => void;
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
  activeUnifiedProfile: AdaptiveStudioUnifiedProfileRow | null;
  strategyProfileData: AdaptiveStudioObjectRecord;
  executionProfileData: AdaptiveStudioObjectRecord;
  strategyModeLabel: string;
  l2BranchSummary: string;
  noL2BranchSummary: string;
  activeUnifiedLegacyComboSourceId: string;
  activeUnifiedLegacyTunedSourceId: string;
  surfaceError: string | null;
  hasTickers: boolean;
  reloadLoading: boolean;
  reloadDisabled: boolean;
  saveDisabled: boolean;
  captureDisabled: boolean;
  captureLoading: boolean;
};

export function useAdaptiveStudioEditor({
  activeTicker,
  availableTickers,
  strategyUniverse,
  rawTickerConfig,
  profileList,
  activeProfileIdFromServer,
  unifiedList,
  activeUnifiedIdFromServer,
  loading,
  profileLoading,
  comboLoading,
  unifiedLoading,
  saving,
  unifiedActionLoading,
  tickerConfigError,
  refreshAllData,
  refreshExecutionConfigSnapshot,
  mergeExecutionConfigSnapshot,
  readExecutionConfigSnapshot,
  saveAdaptiveConfig,
  captureUnifiedProfile,
  applyUnifiedProfile,
}: UseAdaptiveStudioEditorArgs): UseAdaptiveStudioEditorResult {
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [isDirty, setIsDirty] = useState(false);
  const [form, setForm] = useState<AdaptiveStudioFormState>(() =>
    normalizeTickerAdaptiveForm({}, DEFAULT_STRATEGIES),
  );
  const [unifiedDraftName, setUnifiedDraftName] = useState("");
  const [unifiedViewTab, setUnifiedViewTab] = useState<AdaptiveStudioUnifiedViewTab>("strategy");
  const [activeTab, setActiveTab] = useState<AdaptiveStudioTabId>("profiles");

  useAdaptiveStudioEditorSync({
    activeTicker,
    strategyUniverse,
    rawTickerConfig,
    profileList,
    activeProfileIdFromServer,
    unifiedList,
    activeUnifiedIdFromServer,
    isDirty,
    loading,
    tickerConfigError,
    refreshExecutionConfigSnapshot,
    mergeExecutionConfigSnapshot,
    setForm,
    setIsDirty,
  });

  const actions = useAdaptiveStudioEditorActions({
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
  });

  const activeUnifiedProfile = unifiedList.find(
    (profile) =>
      String(profile?.profile_id || "").trim() === String(activeUnifiedIdFromServer || "").trim(),
  ) || null;
  const strategyProfileData = asObject(activeUnifiedProfile?.strategy_profile);
  const executionProfileData = asObject(activeUnifiedProfile?.execution_profile);
  const strategyModeLabel =
    form.strategy_selection_mode === "all_enabled"
      ? "All enabled strategies"
      : `Adaptive top-${normalizeMaxActive(form.max_active_strategies, 3)}`;
  const l2BranchSummary = form.flow_bias_enabled
    ? `Flow bias ON: ${flowSummary(form.flow_bias_strategies)}`
    : "Flow bias OFF: no forced L2-first priority";
  const noL2BranchSummary = form.use_ohlcv_fallbacks
    ? "OHLCV fallback ON"
    : "OHLCV fallback OFF";
  const activeUnifiedLegacyComboSourceId = String(
    activeUnifiedProfile?.source_strategy_combo_profile_id || "",
  ).trim();
  const activeUnifiedLegacyTunedSourceId = String(
    activeUnifiedProfile?.source_adaptive_tuner_profile_id || "",
  ).trim();
  const hasTickers = availableTickers.length > 0;
  const reloadLoading = loading || unifiedLoading || profileLoading || comboLoading;
  const surfaceError = error || tickerConfigError;
  const reloadDisabled =
    loading ||
    saving ||
    unifiedLoading ||
    profileLoading ||
    comboLoading ||
    !!unifiedActionLoading ||
    !activeTicker;
  const saveDisabled = saving || loading || !!unifiedActionLoading || !activeTicker || !isDirty;
  const captureDisabled =
    !activeTicker || loading || saving || unifiedLoading || !!unifiedActionLoading;
  const captureLoading = unifiedActionLoading === "capture";

  return {
    activeTab,
    setActiveTab,
    error,
    notice,
    form,
    unifiedDraftName,
    setUnifiedDraftName,
    unifiedViewTab,
    setUnifiedViewTab,
    activeUnifiedProfile,
    strategyProfileData,
    executionProfileData,
    strategyModeLabel,
    l2BranchSummary,
    noL2BranchSummary,
    activeUnifiedLegacyComboSourceId,
    activeUnifiedLegacyTunedSourceId,
    surfaceError,
    hasTickers,
    reloadLoading,
    reloadDisabled,
    saveDisabled,
    captureDisabled,
    captureLoading,
    ...actions,
  };
}
