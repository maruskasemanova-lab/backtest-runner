import type { ExecutionModulesSnapshot } from "../executionModulesTypes";
import type {
  AdaptiveStudioComboProfileRow,
  AdaptiveStudioFormState,
  AdaptiveStudioObjectRecord,
  AdaptiveStudioStudioProfileRow,
} from "../profileTypes";
import {
  STUDIO_PROFILE_ACTIVE_KEY,
  STUDIO_PROFILE_LIST_KEY,
  STUDIO_PROFILE_MAX_ITEMS,
} from "../constants/adaptive-studio";
import {
  asObject,
  buildStudioProfileId,
  normalizeAdaptiveFormSnapshot,
} from "./adaptive-studio-transformers";

type BuildAdaptiveConfigUpdateArgs = {
  rawTickerConfig: AdaptiveStudioObjectRecord;
  form: AdaptiveStudioFormState;
  strategyUniverse: string[];
  executionModulesSnapshot: ExecutionModulesSnapshot;
  executionParamsSnapshot: ExecutionModulesSnapshot;
};

type ResolveLinkedComboProfileArgs = {
  activeComboId: string;
  comboList: AdaptiveStudioComboProfileRow[];
};

type BuildStudioProfileSaveConfigArgs = {
  activeTicker: string;
  currentConfig: AdaptiveStudioObjectRecord;
  currentProfiles: AdaptiveStudioStudioProfileRow[];
  profileName: string;
  form: AdaptiveStudioFormState;
  strategyUniverse: string[];
  executionModulesSnapshot: ExecutionModulesSnapshot;
  executionParamsSnapshot: ExecutionModulesSnapshot;
  comboProfileId: string;
  comboProfileName: string;
};

type BuildStudioProfileStateConfigArgs = {
  currentConfig: AdaptiveStudioObjectRecord;
  currentProfiles: AdaptiveStudioStudioProfileRow[];
  targetProfileId: string;
};

type BuildStudioProfileDeleteConfigArgs = BuildStudioProfileStateConfigArgs & {
  activeStudioProfileId: string;
};

type LinkedComboProfile = {
  comboProfileId: string;
  comboProfileName: string;
};

type StudioProfileSaveConfigResult = {
  nextConfig: AdaptiveStudioObjectRecord;
  savedProfileId: string;
};

type StudioProfileDeleteConfigResult = {
  nextConfig: AdaptiveStudioObjectRecord;
  nextActiveProfileId: string;
};

export const buildAdaptiveConfigUpdate = ({
  rawTickerConfig,
  form,
  strategyUniverse,
  executionModulesSnapshot,
  executionParamsSnapshot,
}: BuildAdaptiveConfigUpdateArgs): AdaptiveStudioObjectRecord => {
  const normalizedForm = normalizeAdaptiveFormSnapshot(form, strategyUniverse);
  const currentConfig = asObject(rawTickerConfig);
  const currentAdaptive = asObject(currentConfig.adaptive);
  const currentPositioning = asObject(currentConfig.positioning);

  return {
    ...currentConfig,
    strategy_selection_mode: normalizedForm.strategy_selection_mode,
    max_active_strategies: normalizedForm.max_active_strategies,
    positioning: {
      ...currentPositioning,
      ...executionModulesSnapshot,
      ...executionParamsSnapshot,
    },
    adaptive: {
      ...currentAdaptive,
      flow_bias_enabled: normalizedForm.flow_bias_enabled,
      use_ohlcv_fallbacks: normalizedForm.use_ohlcv_fallbacks,
      min_active_bars_before_switch: normalizedForm.min_active_bars_before_switch,
      switch_cooldown_bars: normalizedForm.switch_cooldown_bars,
      flow_bias_strategies: normalizedForm.flow_bias_strategies,
      regime_preferences: normalizedForm.regime_preferences,
      micro_regime_preferences: normalizedForm.micro_regime_preferences,
    },
  };
};

export const resolveLinkedComboProfile = ({
  activeComboId,
  comboList,
}: ResolveLinkedComboProfileArgs): LinkedComboProfile => {
  const comboProfileId = String(activeComboId || "").trim();
  if (!comboProfileId) {
    return {
      comboProfileId: "",
      comboProfileName: "",
    };
  }

  const linkedCombo = comboList.find(
    (profile) => String(profile?.profile_id || "").trim() === comboProfileId,
  );
  return {
    comboProfileId,
    comboProfileName: String(linkedCombo?.profile_name || comboProfileId).trim(),
  };
};

export const buildStudioProfileSaveConfig = ({
  activeTicker,
  currentConfig,
  currentProfiles,
  profileName,
  form,
  strategyUniverse,
  executionModulesSnapshot,
  executionParamsSnapshot,
  comboProfileId,
  comboProfileName,
}: BuildStudioProfileSaveConfigArgs): StudioProfileSaveConfigResult => {
  const existingIds = new Set(
    currentProfiles
      .map((profile) => String(profile?.profile_id || "").trim())
      .filter(Boolean),
  );
  const existingByName = currentProfiles.find(
    (profile) =>
      String(profile?.profile_name || "").trim().toLowerCase() === profileName.toLowerCase(),
  );
  const nowIso = new Date().toISOString();
  const profileId = existingByName
    ? String(existingByName.profile_id || "").trim()
    : buildStudioProfileId(activeTicker, profileName, existingIds);
  const createdAt = existingByName
    ? String(existingByName.created_at || nowIso)
    : nowIso;
  const nextProfile: AdaptiveStudioStudioProfileRow = {
    profile_id: profileId,
    profile_name: profileName,
    created_at: createdAt,
    updated_at: nowIso,
    adaptive_form: normalizeAdaptiveFormSnapshot(form, strategyUniverse),
    execution_modules: executionModulesSnapshot,
    execution_params: executionParamsSnapshot,
    strategy_combo_profile_id: comboProfileId,
    strategy_combo_profile_name: comboProfileName,
  };
  const nextProfiles = [
    nextProfile,
    ...currentProfiles.filter(
      (profile) => String(profile?.profile_id || "").trim() !== profileId,
    ),
  ].slice(0, STUDIO_PROFILE_MAX_ITEMS);

  return {
    savedProfileId: profileId,
    nextConfig: {
      ...currentConfig,
      [STUDIO_PROFILE_LIST_KEY]: nextProfiles,
      [STUDIO_PROFILE_ACTIVE_KEY]: profileId,
    },
  };
};

export const buildStudioProfileActiveConfig = ({
  currentConfig,
  currentProfiles,
  targetProfileId,
}: BuildStudioProfileStateConfigArgs): AdaptiveStudioObjectRecord => {
  return {
    ...currentConfig,
    [STUDIO_PROFILE_LIST_KEY]: currentProfiles,
    [STUDIO_PROFILE_ACTIVE_KEY]: targetProfileId,
  };
};

export const buildStudioProfileDeleteConfig = ({
  currentConfig,
  currentProfiles,
  activeStudioProfileId,
  targetProfileId,
}: BuildStudioProfileDeleteConfigArgs): StudioProfileDeleteConfigResult => {
  const nextProfiles = currentProfiles.filter(
    (profile) => String(profile?.profile_id || "").trim() !== targetProfileId,
  );
  const currentActiveProfileId = String(activeStudioProfileId || "").trim();
  const nextActiveProfileId =
    currentActiveProfileId === targetProfileId
      ? String(nextProfiles[0]?.profile_id || "").trim()
      : currentActiveProfileId;

  return {
    nextActiveProfileId,
    nextConfig: {
      ...currentConfig,
      [STUDIO_PROFILE_LIST_KEY]: nextProfiles,
      [STUDIO_PROFILE_ACTIVE_KEY]: nextActiveProfileId,
    },
  };
};
