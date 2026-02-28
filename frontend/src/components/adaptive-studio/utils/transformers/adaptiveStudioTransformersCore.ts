import type {
  AdaptiveStudioComboProfileRow,
  AdaptiveStudioFormState,
  AdaptiveStudioObjectRecord,
} from "../../profileTypes";
import {
  DEFAULT_FLOW_BIAS_STRATEGIES,
  DEFAULT_MICRO_PREFERENCES,
  DEFAULT_REGIME_PREFERENCES,
  DEFAULT_STRATEGIES,
  MACRO_REGIMES,
  MICRO_REGIMES,
} from "../../constants/adaptive-studio";

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
export const parseIsoMs = (value: unknown): number => {
  const parsed = Date.parse(String(value || ""));
  return Number.isFinite(parsed) ? parsed : 0;
};

export const asObject = (value: unknown): AdaptiveStudioObjectRecord =>
  value && typeof value === "object" && !Array.isArray(value)
    ? (value as AdaptiveStudioObjectRecord)
    : {};
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
