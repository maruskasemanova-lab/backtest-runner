import type { Dispatch, SetStateAction } from "react";
import type {
  AdaptiveStudioFormState,
  AdaptiveStudioObjectRecord,
  AdaptiveStudioUnifiedProfileRow,
} from "../profileTypes";
import {
  applyExecutionParamsSnapshot,
  applyTunedCandidateToForm,
  asObject,
  normalizeTickerAdaptiveForm,
} from "../utils/adaptive-studio-transformers";

type CaptureUnifiedProfileFn = (args: {
  profileName: string;
  setActive?: boolean;
}) => Promise<void>;

type ApplyUnifiedProfileFn = (args: {
  profile: AdaptiveStudioUnifiedProfileRow | null | undefined;
}) => Promise<void>;

type UseAdaptiveStudioUnifiedProfileActionsArgs = {
  activeTicker: string;
  strategyUniverse: string[];
  rawTickerConfig: AdaptiveStudioObjectRecord;
  unifiedDraftName: string;
  refreshAllData: () => Promise<void>;
  mergeExecutionConfigSnapshot: (snapshot: AdaptiveStudioObjectRecord) => void;
  captureUnifiedProfile: CaptureUnifiedProfileFn;
  applyUnifiedProfile: ApplyUnifiedProfileFn;
  setError: Dispatch<SetStateAction<string | null>>;
  setNotice: Dispatch<SetStateAction<string | null>>;
  setForm: Dispatch<SetStateAction<AdaptiveStudioFormState>>;
  setIsDirty: Dispatch<SetStateAction<boolean>>;
};

export function useAdaptiveStudioUnifiedProfileActions({
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
}: UseAdaptiveStudioUnifiedProfileActionsArgs) {
  const handleReload = async () => {
    if (!activeTicker) return;
    setError(null);
    setNotice(null);
    setIsDirty(false);
    await refreshAllData();
  };

  const handleLoadUnifiedProfileToEditor = (
    profile: AdaptiveStudioUnifiedProfileRow | null | undefined,
  ) => {
    const profileId = String(profile?.profile_id || "").trim();
    if (!profileId) {
      setError("Cannot load unified profile: missing profile ID.");
      return;
    }
    const strategyProfile = asObject(profile?.strategy_profile);
    const executionProfile = asObject(profile?.execution_profile);
    const mergedAdaptive = {
      ...asObject(rawTickerConfig?.adaptive),
      ...asObject(strategyProfile?.adaptive),
    };
    const mergedTickerConfig = {
      ...asObject(rawTickerConfig),
      ...strategyProfile,
      adaptive: mergedAdaptive,
    };
    let nextForm = normalizeTickerAdaptiveForm(mergedTickerConfig, strategyUniverse);
    const adaptiveCandidate = asObject(strategyProfile?.adaptive_candidate);
    if (Object.keys(adaptiveCandidate).length) {
      nextForm = applyTunedCandidateToForm(nextForm, adaptiveCandidate, strategyUniverse);
    }
    setForm(nextForm);
    setIsDirty(true);

    const executionPositioning = asObject(executionProfile?.positioning);
    if (Object.keys(executionPositioning).length) {
      mergeExecutionConfigSnapshot(executionPositioning);
      applyExecutionParamsSnapshot(executionPositioning);
    }
    setNotice(
      `Unified profile ${profile?.profile_name || profileId} loaded into editor (Strategy + Execution).`,
    );
  };

  const handleCaptureUnifiedProfile = async () => {
    if (!activeTicker) return;
    const profileName = String(unifiedDraftName || "").trim();
    if (!profileName) {
      setError("Unified profile name is required.");
      return;
    }
    setError(null);
    setNotice(null);
    try {
      await captureUnifiedProfile({ profileName, setActive: true });
      setIsDirty(false);
      setNotice(`Unified profile ${profileName} captured and set active.`);
    } catch (err) {
      console.error("Failed to capture unified profile:", err);
      setError(err instanceof Error ? err.message : "Failed to capture unified profile.");
    }
  };

  const handleSetActiveUnifiedProfile = async (
    profile: AdaptiveStudioUnifiedProfileRow | null | undefined,
  ) => {
    const profileId = String(profile?.profile_id || "").trim();
    if (!activeTicker || !profileId) return;
    setError(null);
    setNotice(null);
    try {
      await applyUnifiedProfile({ profile });
      setIsDirty(false);
      setNotice(
        `Unified profile ${profile?.profile_name || profileId} is now active for ${activeTicker}.`,
      );
    } catch (err) {
      console.error("Failed to set active unified profile:", err);
      setError(err instanceof Error ? err.message : "Failed to apply unified profile.");
    }
  };

  return {
    handleReload,
    handleLoadUnifiedProfileToEditor,
    handleCaptureUnifiedProfile,
    handleSetActiveUnifiedProfile,
  };
}
