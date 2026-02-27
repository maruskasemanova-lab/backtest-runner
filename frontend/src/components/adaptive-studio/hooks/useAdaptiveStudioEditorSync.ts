import { useEffect } from "react";
import type { Dispatch, SetStateAction } from "react";
import type {
  AdaptiveStudioFormState,
  AdaptiveStudioObjectRecord,
  AdaptiveStudioTunedProfileRow,
  AdaptiveStudioUnifiedProfileRow,
} from "../profileTypes";
import {
  applyExecutionModuleSnapshot,
  applyExecutionParamsSnapshot,
  applyTunedCandidateToForm,
  asObject,
  normalizeProfileRefToken,
  normalizeTickerAdaptiveForm,
} from "../utils/adaptive-studio-transformers";

type UseAdaptiveStudioEditorSyncArgs = {
  activeTicker: string;
  strategyUniverse: string[];
  rawTickerConfig: AdaptiveStudioObjectRecord;
  profileList: AdaptiveStudioTunedProfileRow[];
  activeProfileIdFromServer: string;
  unifiedList: AdaptiveStudioUnifiedProfileRow[];
  activeUnifiedIdFromServer: string;
  isDirty: boolean;
  loading: boolean;
  tickerConfigError: string | null;
  refreshExecutionConfigSnapshot: () => void;
  mergeExecutionConfigSnapshot: (snapshot: AdaptiveStudioObjectRecord) => void;
  setForm: Dispatch<SetStateAction<AdaptiveStudioFormState>>;
  setIsDirty: Dispatch<SetStateAction<boolean>>;
};

export function useAdaptiveStudioEditorSync({
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
}: UseAdaptiveStudioEditorSyncArgs) {
  useEffect(() => {
    if (!activeTicker) {
      setForm(normalizeTickerAdaptiveForm({}, strategyUniverse));
      setIsDirty(false);
      return;
    }
    if (tickerConfigError) {
      setForm(normalizeTickerAdaptiveForm({}, strategyUniverse));
      setIsDirty(false);
      return;
    }
    if (loading || isDirty) return;

    refreshExecutionConfigSnapshot();

    const executionFromTickerConfig = asObject(rawTickerConfig?.positioning);
    if (Object.keys(executionFromTickerConfig).length) {
      mergeExecutionConfigSnapshot(executionFromTickerConfig);
      applyExecutionModuleSnapshot(executionFromTickerConfig);
      applyExecutionParamsSnapshot(executionFromTickerConfig);
    }

    const baseForm = normalizeTickerAdaptiveForm(rawTickerConfig, strategyUniverse);
    let nextForm = baseForm;
    const syncedActiveUnifiedProfile = unifiedList.find(
      (profile) =>
        String(profile?.profile_id || "").trim() === String(activeUnifiedIdFromServer || "").trim(),
    ) || null;
    const unifiedStrategyProfile = asObject(syncedActiveUnifiedProfile?.strategy_profile);

    if (Object.keys(unifiedStrategyProfile).length) {
      const mergedAdaptive = {
        ...asObject(rawTickerConfig?.adaptive),
        ...asObject(unifiedStrategyProfile?.adaptive),
      };
      const mergedTickerConfig = {
        ...rawTickerConfig,
        ...unifiedStrategyProfile,
        adaptive: mergedAdaptive,
      };
      nextForm = normalizeTickerAdaptiveForm(mergedTickerConfig, strategyUniverse);
      const unifiedCandidate = asObject(unifiedStrategyProfile?.adaptive_candidate);
      if (Object.keys(unifiedCandidate).length) {
        nextForm = applyTunedCandidateToForm(nextForm, unifiedCandidate, strategyUniverse);
      }
      const executionFromUnified = asObject(
        asObject(syncedActiveUnifiedProfile?.execution_profile)?.positioning,
      );
      if (Object.keys(executionFromUnified).length) {
        mergeExecutionConfigSnapshot(executionFromUnified);
        applyExecutionModuleSnapshot(executionFromUnified);
        applyExecutionParamsSnapshot(executionFromUnified);
      }
    }

    const resolvedActiveProfileId = normalizeProfileRefToken(
      activeProfileIdFromServer || rawTickerConfig?.active_adaptive_tuner_profile_id || "",
    );
    const activeProfile = profileList.find(
      (profile) => String(profile?.profile_id || "").trim() === resolvedActiveProfileId,
    ) || null;
    if (
      !Object.keys(unifiedStrategyProfile).length &&
      activeProfile?.candidate &&
      typeof activeProfile.candidate === "object" &&
      !Array.isArray(activeProfile.candidate)
    ) {
      nextForm = applyTunedCandidateToForm(baseForm, activeProfile.candidate, strategyUniverse);
    }

    setForm(nextForm);
    setIsDirty(false);
  }, [
    activeProfileIdFromServer,
    activeTicker,
    isDirty,
    loading,
    mergeExecutionConfigSnapshot,
    profileList,
    rawTickerConfig,
    refreshExecutionConfigSnapshot,
    setForm,
    setIsDirty,
    strategyUniverse,
    tickerConfigError,
    unifiedList,
    activeUnifiedIdFromServer,
  ]);
}
