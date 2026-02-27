import type { ExecutionModuleField, ExecutionModulesSnapshot } from "../executionModulesTypes";
import type {
  AdaptiveStudioComboProfileRow,
  AdaptiveStudioFormState,
  AdaptiveStudioObjectRecord,
  AdaptiveStudioStudioProfileRow,
  AdaptiveStudioTunedProfileRow,
  AdaptiveStudioUnifiedProfileRow,
} from "../profileTypes";
import {
  DEFAULT_FLOW_BIAS_STRATEGIES,
  DEFAULT_MICRO_PREFERENCES,
  DEFAULT_REGIME_PREFERENCES,
  DEFAULT_STRATEGIES,
  EXECUTION_MODULE_PARAM_FIELDS,
  EXECUTION_MODULE_PROFILE_KEYS,
  MACRO_REGIMES,
  MICRO_REGIMES,
  STUDIO_PROFILE_MAX_ITEMS,
} from "../constants/adaptive-studio";

export const normalizeMode = (value: unknown): AdaptiveStudioFormState["strategy_selection_mode"] => {
  const normalized = String(value || "").trim().toLowerCase();
  return normalized === "all_enabled" ? "all_enabled" : "adaptive_top_n";
};

export const normalizeMaxActive = (value: unknown, fallback = 3): number => {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || !Number.isInteger(parsed)) {
    return fallback;
  }
  return Math.max(1, Math.min(20, parsed));
};

export const normalizeNonNegativeInt = (value: unknown, fallback = 0, max = 10000): number => {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || !Number.isInteger(parsed)) {
    return fallback;
  }
  return Math.max(0, Math.min(max, parsed));
};

export const toBoolean = (value: unknown, fallback = false): boolean => {
  if (typeof value === "boolean") return value;
  if (typeof value === "number") return value !== 0;
  if (typeof value === "string") {
    const normalized = value.trim().toLowerCase();
    if (["1", "true", "yes", "on"].includes(normalized)) return true;
    if (["0", "false", "no", "off"].includes(normalized)) return false;
  }
  return fallback;
};

export const normalizeProfileRefToken = (value: unknown): string => {
  const token = String(value || "").trim();
  if (!token) return "";
  const lowered = token.toLowerCase();
  if (lowered === "none" || lowered === "null" || lowered === "n/a" || lowered === "na") {
    return "";
  }
  return token;
};

export const canonicalizeStrategyName = (
  value: unknown,
  strategyUniverse: string[],
): string => {
  const raw = String(value || "").trim();
  if (!raw) return "";

  const normalized = raw
    .replace(/-/g, "_")
    .replace(/\s+/g, "_")
    .replace(/__+/g, "_")
    .toLowerCase();

  if (strategyUniverse.includes(normalized)) return normalized;

  const compact = normalized.replace(/_/g, "");
  const compactMatch = strategyUniverse.find((item) => item.replace(/_/g, "") === compact);
  if (compactMatch) return compactMatch;

  return normalized;
};

export const normalizeStrategyList = (
  value: unknown,
  fallback: string[],
  strategyUniverse: string[],
): string[] => {
  const source = Array.isArray(value) ? value : fallback;
  const normalized: string[] = [];
  const seen = new Set<string>();

  source.forEach((item) => {
    const key = canonicalizeStrategyName(item, strategyUniverse);
    if (!key || seen.has(key)) return;
    seen.add(key);
    normalized.push(key);
  });

  return normalized;
};

export const normalizePreferenceMap = (
  value: unknown,
  keys: string[],
  fallbackMap: Record<string, string[]>,
  strategyUniverse: string[],
): Record<string, string[]> => {
  const source = value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
  const normalized: Record<string, string[]> = {};

  keys.forEach((key) => {
    normalized[key] = normalizeStrategyList(
      source[key],
      fallbackMap[key] || [],
      strategyUniverse,
    );
  });

  return normalized;
};

export const cloneMap = (input: unknown): Record<string, string[]> => {
  const out: Record<string, string[]> = {};
  Object.entries(
    input && typeof input === "object" && !Array.isArray(input)
      ? (input as Record<string, unknown>)
      : {},
  ).forEach(([key, list]) => {
    out[key] = Array.isArray(list) ? [...list].map((item) => String(item || "")).filter(Boolean) : [];
  });
  return out;
};

export const strategyLabel = (name: unknown): string =>
  String(name || "")
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");

export const normalizeTickerAdaptiveForm = (
  tickerConfig: unknown,
  strategyUniverse: string[],
): AdaptiveStudioFormState => {
  const safeTickerConfig =
    tickerConfig && typeof tickerConfig === "object" && !Array.isArray(tickerConfig)
      ? (tickerConfig as Record<string, unknown>)
      : {};
  const adaptiveRaw =
    safeTickerConfig.adaptive && typeof safeTickerConfig.adaptive === "object" && !Array.isArray(safeTickerConfig.adaptive)
      ? (safeTickerConfig.adaptive as Record<string, unknown>)
      : {};

  return {
    strategy_selection_mode: normalizeMode(safeTickerConfig.strategy_selection_mode),
    max_active_strategies: normalizeMaxActive(safeTickerConfig.max_active_strategies, 3),
    flow_bias_enabled: toBoolean(adaptiveRaw.flow_bias_enabled, true),
    use_ohlcv_fallbacks: toBoolean(adaptiveRaw.use_ohlcv_fallbacks, true),
    min_active_bars_before_switch: normalizeNonNegativeInt(
      adaptiveRaw.min_active_bars_before_switch,
      0,
    ),
    switch_cooldown_bars: normalizeNonNegativeInt(adaptiveRaw.switch_cooldown_bars, 0),
    flow_bias_strategies: normalizeStrategyList(
      adaptiveRaw.flow_bias_strategies,
      DEFAULT_FLOW_BIAS_STRATEGIES,
      strategyUniverse,
    ),
    regime_preferences: normalizePreferenceMap(
      adaptiveRaw.regime_preferences,
      MACRO_REGIMES,
      DEFAULT_REGIME_PREFERENCES,
      strategyUniverse,
    ),
    micro_regime_preferences: normalizePreferenceMap(
      adaptiveRaw.micro_regime_preferences,
      MICRO_REGIMES,
      DEFAULT_MICRO_PREFERENCES,
      strategyUniverse,
    ),
  };
};

export const normalizeAdaptiveFormSnapshot = (
  value: unknown,
  strategyUniverse: string[],
): AdaptiveStudioFormState => {
  const source = value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
  return {
    strategy_selection_mode: normalizeMode(source.strategy_selection_mode),
    max_active_strategies: normalizeMaxActive(source.max_active_strategies, 3),
    flow_bias_enabled: toBoolean(source.flow_bias_enabled, true),
    use_ohlcv_fallbacks: toBoolean(source.use_ohlcv_fallbacks, true),
    min_active_bars_before_switch: normalizeNonNegativeInt(source.min_active_bars_before_switch, 0),
    switch_cooldown_bars: normalizeNonNegativeInt(source.switch_cooldown_bars, 0),
    flow_bias_strategies: normalizeStrategyList(
      source.flow_bias_strategies,
      DEFAULT_FLOW_BIAS_STRATEGIES,
      strategyUniverse,
    ),
    regime_preferences: normalizePreferenceMap(
      source.regime_preferences,
      MACRO_REGIMES,
      DEFAULT_REGIME_PREFERENCES,
      strategyUniverse,
    ),
    micro_regime_preferences: normalizePreferenceMap(
      source.micro_regime_preferences,
      MICRO_REGIMES,
      DEFAULT_MICRO_PREFERENCES,
      strategyUniverse,
    ),
  };
};

export const normalizeExecutionModulesSnapshot = (
  value: unknown,
): ExecutionModulesSnapshot => {
  const source = value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
  const normalized: ExecutionModulesSnapshot = {};
  EXECUTION_MODULE_PROFILE_KEYS.forEach((key) => {
    normalized[key] = toBoolean(source[key], false);
  });
  return normalized;
};

export const normalizeExecutionParamValue = (
  value: unknown,
  field: ExecutionModuleField,
): unknown => {
  if (field?.type === "boolean") {
    return toBoolean(value, !!field?.fallback);
  }
  if (field?.type === "select") {
    if (field?.key === "stop_loss_mode") {
      const raw = String(value ?? field?.fallback ?? "strategy")
        .trim()
        .toLowerCase();
      if (raw === "fixed" || raw === "capped") return raw;
      return "strategy";
    }
    const options = Array.isArray(field?.options) ? field.options : [];
    const allowed = options
      .map((item) => String(item?.value || "").trim())
      .filter(Boolean);
    const fallback = String(field?.fallback ?? allowed[0] ?? "").trim();
    const candidate = String(value ?? fallback).trim();
    return allowed.includes(candidate) ? candidate : fallback;
  }
  const parsed = Number(value);
  const fallback = Number(field?.fallback || 0);
  const min = Number(field?.min ?? Number.NEGATIVE_INFINITY);
  const max = Number(field?.max ?? Number.POSITIVE_INFINITY);
  const safe = Number.isFinite(parsed) ? parsed : fallback;
  const clamped = Math.max(min, Math.min(max, safe));
  if (field?.integer) {
    return Math.trunc(clamped);
  }
  return clamped;
};

export const normalizeExecutionParamsSnapshot = (
  value: unknown,
): ExecutionModulesSnapshot => {
  const source = value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
  const normalized: ExecutionModulesSnapshot = {};
  EXECUTION_MODULE_PARAM_FIELDS.forEach((field) => {
    normalized[field.key] = normalizeExecutionParamValue(source[field.key], field);
  });
  return normalized;
};

export const readExecutionConfigSnapshot = (): ExecutionModulesSnapshot => {
  if (typeof window === "undefined") return {};
  const raw = (window as typeof window & { __executionConfig?: unknown }).__executionConfig;
  return raw && typeof raw === "object" && !Array.isArray(raw)
    ? (raw as ExecutionModulesSnapshot)
    : {};
};

export const readExecutionModuleSnapshot = (): ExecutionModulesSnapshot => {
  return normalizeExecutionModulesSnapshot(readExecutionConfigSnapshot());
};

export const readExecutionParamsSnapshot = (): ExecutionModulesSnapshot => {
  return normalizeExecutionParamsSnapshot(readExecutionConfigSnapshot());
};

export const applyExecutionModuleSnapshot = (value: unknown): void => {
  if (typeof window === "undefined") return;
  const normalized = normalizeExecutionModulesSnapshot(value);
  Object.entries(normalized).forEach(([configKey, enabled]) => {
    window.dispatchEvent(
      new CustomEvent("execution-module-toggle", {
        detail: { configKey, value: !!enabled },
      }),
    );
  });
};

export const applyExecutionParamsSnapshot = (value: unknown): void => {
  if (typeof window === "undefined") return;
  const normalized = normalizeExecutionParamsSnapshot(value);
  Object.entries(normalized).forEach(([configKey, nextValue]) => {
    window.dispatchEvent(
      new CustomEvent("execution-module-toggle", {
        detail: { configKey, value: nextValue },
      }),
    );
  });
};

export const parseIsoMs = (value: unknown): number => {
  const parsed = Date.parse(String(value || ""));
  return Number.isFinite(parsed) ? parsed : 0;
};

export const asObject = (value: unknown): AdaptiveStudioObjectRecord =>
  value && typeof value === "object" && !Array.isArray(value)
    ? (value as AdaptiveStudioObjectRecord)
    : {};

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

export const toProfileSlug = (value: unknown): string =>
  String(value || "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 48);

export const buildStudioProfileId = (
  ticker: string,
  profileName: string,
  existingIds: Set<string>,
): string => {
  const baseTicker = String(ticker || "ticker").trim().toLowerCase() || "ticker";
  const slug = toProfileSlug(profileName) || "profile";
  const stamp = Date.now().toString(36);
  let candidate = `${baseTicker}-${slug}-${stamp}`;
  let suffix = 1;
  while (existingIds.has(candidate)) {
    candidate = `${baseTicker}-${slug}-${stamp}-${suffix}`;
    suffix += 1;
  }
  return candidate;
};

export const flowSummary = (strategies: unknown): string => {
  if (!Array.isArray(strategies) || strategies.length === 0) {
    return "none";
  }
  return strategies.slice(0, 3).map(strategyLabel).join(", ");
};

export const formatProfileTimestamp = (value: unknown): string => {
  if (!value) return "-";
  const parsed = Date.parse(String(value));
  if (Number.isNaN(parsed)) return String(value);
  return new Date(parsed).toLocaleString();
};

export const formatProfileCandidate = (candidate: unknown): string => {
  if (!candidate || typeof candidate !== "object") return "candidate unavailable";
  const candidateRow = candidate as Record<string, unknown>;
  const mode = normalizeMode(candidateRow.strategy_selection_mode);
  const maxActive = normalizeMaxActive(candidateRow.max_active_strategies, 3);
  const hysteresis = normalizeNonNegativeInt(candidateRow.min_active_bars_before_switch, 0);
  const cooldown = normalizeNonNegativeInt(candidateRow.switch_cooldown_bars, 0);
  const flowBias = toBoolean(candidateRow.flow_bias_enabled, true) ? "flow-bias on" : "flow-bias off";
  const fallback = toBoolean(candidateRow.use_ohlcv_fallbacks, true) ? "fallback on" : "fallback off";
  return `${mode === "all_enabled" ? "all enabled" : `adaptive top-${maxActive}`} | hysteresis ${hysteresis} | cooldown ${cooldown} | ${flowBias} | ${fallback}`;
};

export const buildRecomposedList = (
  currentList: unknown,
  fallbackList: unknown,
  enabledSet: Set<string>,
): string[] => {
  const filteredCurrent = (Array.isArray(currentList) ? currentList : []).filter((name) =>
    enabledSet.has(String(name)),
  );
  if (filteredCurrent.length > 0) return filteredCurrent.map((name) => String(name));
  const filteredFallback = (Array.isArray(fallbackList) ? fallbackList : []).filter((name) =>
    enabledSet.has(String(name)),
  );
  if (filteredFallback.length > 0) return filteredFallback.map((name) => String(name));
  return [];
};

export const applyTunedCandidateToForm = (
  formState: AdaptiveStudioFormState,
  candidate: unknown,
  strategyUniverse: string[],
): AdaptiveStudioFormState => {
  const source = candidate && typeof candidate === "object" && !Array.isArray(candidate)
    ? (candidate as Record<string, unknown>)
    : {};
  const base: AdaptiveStudioFormState = {
    ...formState,
    strategy_selection_mode: normalizeMode(source.strategy_selection_mode),
    max_active_strategies: normalizeMaxActive(
      source.max_active_strategies,
      normalizeMaxActive(formState.max_active_strategies, 3),
    ),
    flow_bias_enabled: toBoolean(source.flow_bias_enabled, formState.flow_bias_enabled),
    use_ohlcv_fallbacks: toBoolean(source.use_ohlcv_fallbacks, formState.use_ohlcv_fallbacks),
    min_active_bars_before_switch: normalizeNonNegativeInt(
      source.min_active_bars_before_switch,
      normalizeNonNegativeInt(formState.min_active_bars_before_switch, 0),
    ),
    switch_cooldown_bars: normalizeNonNegativeInt(
      source.switch_cooldown_bars,
      normalizeNonNegativeInt(formState.switch_cooldown_bars, 0),
    ),
  };

  const enabled = source.enabled_strategies;
  if (Array.isArray(enabled) && enabled.length > 0 && Array.isArray(strategyUniverse)) {
    const enabledSet = new Set(
      enabled.map((s) => canonicalizeStrategyName(s, strategyUniverse)).filter(Boolean),
    );
    const nextRegime: Record<string, string[]> = {};
    MACRO_REGIMES.forEach((key) => {
      nextRegime[key] = buildRecomposedList(
        base.regime_preferences?.[key],
        DEFAULT_REGIME_PREFERENCES[key],
        enabledSet,
      );
    });
    const nextMicro: Record<string, string[]> = {};
    MICRO_REGIMES.forEach((key) => {
      nextMicro[key] = buildRecomposedList(
        base.micro_regime_preferences?.[key],
        DEFAULT_MICRO_PREFERENCES[key],
        enabledSet,
      );
    });
    const nextFlowBias = buildRecomposedList(
      base.flow_bias_strategies,
      DEFAULT_FLOW_BIAS_STRATEGIES,
      enabledSet,
    );
    base.regime_preferences = nextRegime;
    base.micro_regime_preferences = nextMicro;
    base.flow_bias_strategies = nextFlowBias;
    base.max_active_strategies = Math.max(1, Math.min(base.max_active_strategies, enabledSet.size));
  }

  return base;
};

export const formatV2VectorSummary = (candidate: unknown): string[] | null => {
  if (!candidate || typeof candidate !== "object") return null;
  const candidateRow = candidate as Record<string, unknown>;
  const parts: string[] = [];
  const strategies = candidateRow.enabled_strategies;
  if (Array.isArray(strategies) && strategies.length) {
    parts.push(`Strategies: ${strategies.join(", ")}`);
  }
  const regime = candidateRow.regime_filter;
  if (Array.isArray(regime) && regime.length) {
    parts.push(`Regime: ${regime.join(", ")}`);
  }
  if (candidateRow.l2_min_imbalance != null) {
    parts.push(`L2 imb: ${Number(candidateRow.l2_min_imbalance).toFixed(3)}`);
  }
  if (candidateRow.l2_min_delta != null) {
    parts.push(`L2 delta: ${candidateRow.l2_min_delta}`);
  }
  if (candidateRow.base_threshold != null) {
    parts.push(`Evidence thr: ${candidateRow.base_threshold}`);
  }
  if (candidateRow.min_confirming_sources != null) {
    parts.push(`Min sources: ${candidateRow.min_confirming_sources}`);
  }
  if (candidateRow.min_confidence != null) {
    parts.push(`Confidence: ${candidateRow.min_confidence}`);
  }
  if (candidateRow.atr_stop_multiplier != null) {
    parts.push(`ATR stop: ${candidateRow.atr_stop_multiplier}`);
  }
  if (candidateRow.rr_ratio != null) {
    parts.push(`R:R: ${candidateRow.rr_ratio}`);
  }
  const hours = candidateRow.trading_hours;
  if (Array.isArray(hours) && hours.length) {
    parts.push(`Hours: ${hours.join(",")}`);
  }
  if (candidateRow.adverse_flow_consistency != null) {
    parts.push(`FlowExitCons: ${candidateRow.adverse_flow_consistency}`);
  }
  if (candidateRow.adverse_book_pressure != null) {
    parts.push(`BookExitThr: ${candidateRow.adverse_book_pressure}`);
  }
  return parts.length ? parts : null;
};

export const extractEnabledStrategiesFromCombo = (
  profile: AdaptiveStudioComboProfileRow | null | undefined,
  strategyUniverse: string[],
): string[] => {
  const strategyParams =
    profile && typeof profile === "object" && typeof profile.strategy_params === "object"
      ? (profile.strategy_params as AdaptiveStudioObjectRecord)
      : {};
  const enabled: string[] = [];
  Object.entries(strategyParams || {}).forEach(([name, params]) => {
    const canonical = canonicalizeStrategyName(name, strategyUniverse);
    if (!canonical) return;
    const isEnabled = !(params && typeof params === "object" && (params as { enabled?: unknown }).enabled === false);
    if (isEnabled) {
      enabled.push(canonical);
    }
  });
  return Array.from(new Set(enabled));
};

export const normalizeStrategyUniverse = (value: unknown): string[] => {
  const payload = asObject(value);
  const names = Object.keys(payload)
    .map((name) => canonicalizeStrategyName(name, DEFAULT_STRATEGIES))
    .filter(Boolean);
  return names.length
    ? Array.from(new Set([...DEFAULT_STRATEGIES, ...names]))
    : [...DEFAULT_STRATEGIES];
};

export const normalizeAvailableTickers = (value: unknown): string[] => {
  const payload = asObject(value);
  const tickers = Array.isArray(payload.tickers)
    ? payload.tickers.map((ticker) => String(ticker).toUpperCase()).filter(Boolean)
    : [];
  return Array.from(new Set(tickers));
};
