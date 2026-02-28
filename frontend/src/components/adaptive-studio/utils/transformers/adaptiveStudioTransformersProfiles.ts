import type {
  AdaptiveStudioComboProfileRow,
  AdaptiveStudioObjectRecord,
  AdaptiveStudioStudioProfileRow,
  AdaptiveStudioTunedProfileRow,
  AdaptiveStudioUnifiedProfileRow,
} from "../../profileTypes";
import { STUDIO_PROFILE_MAX_ITEMS } from "../../constants/adaptive-studio";
import {
  asObject,
  normalizeAdaptiveFormSnapshot,
  normalizeMaxActive,
  normalizeMode,
  normalizeProfileRefToken,
  parseIsoMs,
  toBoolean,
} from "./adaptiveStudioTransformersCore";
import {
  normalizeExecutionModulesSnapshot,
  normalizeExecutionParamsSnapshot,
} from "./adaptiveStudioTransformersExecution";

export const normalizeStudioProfiles = (
  value: unknown,
  strategyUniverse: string[],
): AdaptiveStudioStudioProfileRow[] => {
  if (!Array.isArray(value)) return [];
  const seen = new Set<string>();
  const rows: AdaptiveStudioStudioProfileRow[] = [];
  value.forEach((item) => {
    if (!item || typeof item !== "object" || Array.isArray(item)) return;
    const row = item as Record<string, unknown>;
    const profileId = String(row.profile_id || "").trim();
    if (!profileId || seen.has(profileId)) return;
    seen.add(profileId);
    const profileName = String(row.profile_name || profileId).trim() || profileId;
    const createdAt = String(row.created_at || "").trim() || new Date().toISOString();
    const updatedAt = String(row.updated_at || "").trim() || createdAt;
    rows.push({
      profile_id: profileId,
      profile_name: profileName,
      created_at: createdAt,
      updated_at: updatedAt,
      adaptive_form: normalizeAdaptiveFormSnapshot(row.adaptive_form, strategyUniverse),
      execution_modules: normalizeExecutionModulesSnapshot(row.execution_modules),
      execution_params: normalizeExecutionParamsSnapshot(row.execution_params),
      strategy_combo_profile_id: String(row.strategy_combo_profile_id || "").trim(),
      strategy_combo_profile_name: String(row.strategy_combo_profile_name || "").trim(),
    });
  });
  rows.sort((a, b) => parseIsoMs(b.updated_at) - parseIsoMs(a.updated_at));
  return rows.slice(0, STUDIO_PROFILE_MAX_ITEMS);
};

export const extractAdaptiveCandidate = (profile: unknown): AdaptiveStudioObjectRecord => {
  const row = asObject(profile);
  const candidate = asObject(row.candidate);
  if (Object.keys(candidate).length) return candidate;
  const bestTrial = asObject(row.best_trial);
  return asObject(bestTrial.candidate);
};

export const normalizeUnifiedProfiles = (
  value: unknown,
): AdaptiveStudioUnifiedProfileRow[] => {
  if (!Array.isArray(value)) return [];
  const out: AdaptiveStudioUnifiedProfileRow[] = [];
  const seen = new Set<string>();
  value.forEach((item) => {
    const row = asObject(item);
    const profileId = String(row.profile_id || "").trim();
    if (!profileId || seen.has(profileId)) return;
    seen.add(profileId);
    out.push({
      profile_id: profileId,
      profile_name: String(row.profile_name || profileId).trim() || profileId,
      created_at: String(row.created_at || "").trim() || new Date().toISOString(),
      updated_at: String(row.updated_at || "").trim() || String(row.created_at || "").trim() || new Date().toISOString(),
      strategy_profile: asObject(row.strategy_profile),
      execution_profile: asObject(row.execution_profile),
      source_strategy_combo_profile_id: String(row.source_strategy_combo_profile_id || "").trim(),
      source_adaptive_tuner_profile_id: String(row.source_adaptive_tuner_profile_id || "").trim(),
    });
  });
  out.sort((a, b) => parseIsoMs(b.updated_at) - parseIsoMs(a.updated_at));
  return out.slice(0, STUDIO_PROFILE_MAX_ITEMS);
};

export const buildLegacyUnifiedProfiles = ({
  ticker,
  tickerConfig,
  comboPayload,
  tunedPayload,
}: {
  ticker: string;
  tickerConfig?: unknown;
  comboPayload?: unknown;
  tunedPayload?: unknown;
}): {
  profiles: AdaptiveStudioUnifiedProfileRow[];
  active_profile_id: string | null;
  legacy_fallback: boolean;
} => {
  const safeTicker = asObject(tickerConfig);
  const comboPayloadObject = asObject(comboPayload);
  const tunedPayloadObject = asObject(tunedPayload);
  const comboProfiles = Array.isArray(comboPayloadObject.profiles)
    ? (comboPayloadObject.profiles as AdaptiveStudioComboProfileRow[])
    : [];
  const comboActiveId = normalizeProfileRefToken(
    comboPayloadObject.active_profile_id ?? comboPayloadObject.activeProfileId,
  );
  const tunedProfiles = Array.isArray(tunedPayloadObject.profiles)
    ? (tunedPayloadObject.profiles as AdaptiveStudioTunedProfileRow[])
    : [];
  const tunedActiveId = normalizeProfileRefToken(
    tunedPayloadObject.active_profile_id ?? tunedPayloadObject.activeProfileId,
  );
  const nowIso = new Date().toISOString();
  const baseExecutionProfile = {
    positioning: asObject(safeTicker.positioning),
  };
  const orderWithActive = <T extends { profile_id?: unknown; updated_at?: unknown; created_at?: unknown }>(
    rows: T[],
    activeId: string,
  ): T[] => {
    const activeRows: T[] = [];
    const restRows: T[] = [];
    rows.forEach((row) => {
      if (String(row?.profile_id || "").trim() === activeId) {
        activeRows.push(row);
      } else {
        restRows.push(row);
      }
    });
    restRows.sort(
      (a, b) => parseIsoMs(b?.updated_at || b?.created_at) - parseIsoMs(a?.updated_at || a?.created_at),
    );
    return [...activeRows, ...restRows];
  };
  const comboCandidates = orderWithActive(comboProfiles, comboActiveId);
  const tunedCandidates = orderWithActive(tunedProfiles, tunedActiveId);
  const limitedCombos = comboCandidates.length ? comboCandidates.slice(0, 12) : [null];
  const limitedTuned = tunedCandidates.length ? tunedCandidates.slice(0, 12) : [null];

  const makeProfile = ({
    comboProfile,
    tunedProfile,
  }: {
    comboProfile: AdaptiveStudioComboProfileRow | null;
    tunedProfile: AdaptiveStudioTunedProfileRow | null;
  }): AdaptiveStudioUnifiedProfileRow => {
    const comboId = String(comboProfile?.profile_id || "").trim();
    const profileTunedId = String(tunedProfile?.profile_id || "").trim();
    const comboName = String(comboProfile?.profile_name || comboId || "").trim();
    const tunedName = String(tunedProfile?.profile_name || profileTunedId || "").trim();
    const profileName = comboName && tunedName
      ? `legacy: ${comboName} + ${tunedName}`
      : `legacy: ${comboName || tunedName || "profile"}`;
    const strategyProfile: AdaptiveStudioObjectRecord = {
      strategy_params: asObject(comboProfile?.strategy_params),
      strategy_selection_mode: normalizeMode(safeTicker.strategy_selection_mode),
      max_active_strategies: normalizeMaxActive(safeTicker.max_active_strategies, 3),
      trading_hours: Array.isArray(safeTicker.trading_hours) ? safeTicker.trading_hours : [],
      time_filter_enabled: toBoolean(safeTicker.time_filter_enabled, false),
      long_only: toBoolean(safeTicker.long_only, false),
      l2: asObject(safeTicker.l2),
      adaptive: asObject(safeTicker.adaptive),
      active_strategy_combo_profile_id: comboId,
      active_adaptive_tuner_profile_id: profileTunedId,
    };
    const candidate = extractAdaptiveCandidate(tunedProfile);
    if (Object.keys(candidate).length) {
      strategyProfile.adaptive_candidate = candidate;
    }
    return {
      profile_id: `legacy-unified-${String(ticker || "").toUpperCase()}-${comboId || "none"}-${profileTunedId || "none"}`,
      profile_name: profileName,
      created_at: String(comboProfile?.created_at || tunedProfile?.created_at || nowIso),
      updated_at: String(
        comboProfile?.updated_at ||
          comboProfile?.created_at ||
          tunedProfile?.updated_at ||
          tunedProfile?.created_at ||
          nowIso,
      ),
      strategy_profile: strategyProfile,
      execution_profile: baseExecutionProfile,
      source_strategy_combo_profile_id: comboId,
      source_adaptive_tuner_profile_id: profileTunedId,
    };
  };

  const rows: AdaptiveStudioUnifiedProfileRow[] = [];
  limitedCombos.forEach((combo) => {
    limitedTuned.forEach((tuned) => {
      if (!combo && !tuned) return;
      rows.push(makeProfile({
        comboProfile: combo,
        tunedProfile: tuned,
      }));
    });
  });
  const uniqueRows: AdaptiveStudioUnifiedProfileRow[] = [];
  const seen = new Set<string>();
  rows.forEach((row) => {
    const rowId = String(row?.profile_id || "").trim();
    if (!rowId || seen.has(rowId)) return;
    seen.add(rowId);
    uniqueRows.push(row);
  });
  uniqueRows.sort(
    (a, b) => parseIsoMs(b?.updated_at || b?.created_at) - parseIsoMs(a?.updated_at || a?.created_at),
  );
  const derivedActiveProfileId = `legacy-unified-${String(ticker || "").toUpperCase()}-${comboActiveId || "none"}-${tunedActiveId || "none"}`;
  const activeProfileId = seen.has(derivedActiveProfileId)
    ? derivedActiveProfileId
    : String(uniqueRows[0]?.profile_id || "").trim();
  return {
    profiles: uniqueRows.slice(0, STUDIO_PROFILE_MAX_ITEMS),
    active_profile_id: activeProfileId || null,
    legacy_fallback: true,
  };
};

