import type {
  DiagnosticCalendarDayResult,
  DiagnosticCalendarRun,
  DiagnosticCalendarRunProfileFields,
} from "./diagnostic-calendar-types";

const PROFILE_PLACEHOLDER_TOKENS = new Set(["none", "null", "n/a", "na", "undefined", "-"]);

const uniqueCaseInsensitive = (values: unknown[]): string[] => {
  const tokensByKey = new Map<string, string>();
  values.forEach((value) => {
    const normalized = String(value || "").trim();
    if (!normalized) return;
    const key = normalized.toLowerCase();
    if (tokensByKey.has(key)) return;
    tokensByKey.set(key, normalized);
  });
  return [...tokensByKey.values()];
};

const flattenTokenSources = (values: unknown[]): unknown[] =>
  values.flatMap((value) => (Array.isArray(value) ? value : [value]));

export const normalizeProfileToken = (value: unknown): string => {
  const text = String(value ?? "").trim();
  if (!text) return "";
  const normalized = text.toLowerCase();
  if (PROFILE_PLACEHOLDER_TOKENS.has(normalized)) return "";
  return text;
};

export const joinProfileTokens = (...values: unknown[]): string | null => {
  const tokens = uniqueCaseInsensitive(
    flattenTokenSources(values)
      .map((value) => normalizeProfileToken(value))
      .filter(Boolean),
  );
  return tokens.length ? tokens.join(" | ") : null;
};

export const resolveRunProfileFields = (
  run: DiagnosticCalendarRun | null | undefined,
): DiagnosticCalendarRunProfileFields => {
  const unifiedProfile = joinProfileTokens(
    run?.unified_profile_id,
    run?.unified_profile_name,
    run?.execution_config?.unified_profile_id,
    run?.execution_config?.unified_profile_name,
    run?.aos_applied?.unified_profile?.active_profile_id,
    run?.aos_applied?.unified_profile?.profile_id,
    run?.aos_applied?.unified_profile?.profile_name,
  );
  const adaptiveProfile = joinProfileTokens(
    run?.adaptive_profile_id,
    run?.adaptive_profile_name,
    run?.execution_config?.adaptive_profile_id,
    run?.execution_config?.active_adaptive_tuner_profile_id,
    run?.aos_applied?.adaptive_profile?.active_profile_id,
    run?.aos_applied?.adaptive_profile?.profile_id,
    run?.aos_applied?.adaptive_profile?.profile_name,
  );
  const strategyComboProfile = joinProfileTokens(
    run?.strategy_combo_profile_id,
    run?.strategy_combo_profile_name,
    run?.execution_config?.strategy_combo_profile_id,
    run?.execution_config?.active_strategy_combo_profile_id,
    run?.aos_applied?.strategy_combo?.active_profile_id,
    run?.aos_applied?.strategy_combo?.profile_id,
    run?.aos_applied?.strategy_combo?.profile_name,
  );
  return {
    unifiedProfile,
    adaptiveProfile,
    strategyComboProfile,
  };
};

export const collectAdaptiveProfileTokens = (
  dayResult: DiagnosticCalendarDayResult | null | undefined,
): string[] => {
  const runProfileValues = Array.isArray(dayResult?.runs)
    ? dayResult.runs.flatMap((run) => [
        run?.unified_profile_id,
        run?.unified_profile_name,
        run?.adaptive_profile_id,
        run?.adaptive_profile_name,
        run?.strategy_combo_profile_id,
        run?.strategy_combo_profile_name,
        run?.execution_config?.active_adaptive_tuner_profile_id,
      ])
    : [];

  return uniqueCaseInsensitive(
    flattenTokenSources([
      dayResult?.unified_profile_id,
      dayResult?.unified_profile_name,
      dayResult?.adaptive_profile_id,
      dayResult?.adaptive_profile_name,
      dayResult?.strategy_combo_profile_id,
      dayResult?.strategy_combo_profile_name,
      dayResult?.aos_applied?.unified_profile?.active_profile_id,
      dayResult?.aos_applied?.unified_profile?.profile_id,
      dayResult?.aos_applied?.unified_profile?.profile_name,
      dayResult?.execution_config?.active_adaptive_tuner_profile_id,
      dayResult?.aos_applied?.adaptive_profile?.active_profile_id,
      dayResult?.aos_applied?.adaptive_profile?.profile_id,
      dayResult?.aos_applied?.adaptive_profile?.profile_name,
      dayResult?.aos_applied?.strategy_combo?.active_profile_id,
      dayResult?.aos_applied?.strategy_combo?.profile_name,
      dayResult?.adaptive_profile_ids,
      dayResult?.adaptive_profile_names,
      dayResult?.strategy_combo_profile_ids,
      dayResult?.strategy_combo_profile_names,
      dayResult?.unified_profile_ids,
      dayResult?.unified_profile_names,
      runProfileValues,
    ])
      .map((value) => normalizeProfileToken(value))
      .filter(Boolean),
  );
};

export const hasAdaptiveProfileSources = (
  dayResult: DiagnosticCalendarDayResult | null | undefined,
): boolean => {
  if (!dayResult || dayResult.success === false) return false;
  if (Array.isArray(dayResult?.unified_profile_ids) && dayResult.unified_profile_ids.length > 0) return true;
  if (Array.isArray(dayResult?.adaptive_profile_ids) && dayResult.adaptive_profile_ids.length > 0) return true;
  if (Array.isArray(dayResult?.profile_match_modes) && dayResult.profile_match_modes.length > 0) return true;
  if (Array.isArray(dayResult?.runs)) {
    const hasRunMatch = dayResult.runs.some((run) => {
      const mode = String(run?.profile_match_mode || "").trim().toLowerCase();
      if (mode === "exact" || mode === "hint") return true;
      const runUnifiedProfile = normalizeProfileToken(run?.unified_profile_id);
      if (runUnifiedProfile) return true;
      const runProfile = normalizeProfileToken(run?.adaptive_profile_id);
      return Boolean(runProfile);
    });
    if (hasRunMatch) return true;
  }
  if (Array.isArray(dayResult?.strategy_names)) {
    const hasAdaptiveStrategy = dayResult.strategy_names.some((name) =>
      String(name || "").trim().toLowerCase().includes("adaptive")
    );
    if (hasAdaptiveStrategy) return true;
  }
  if (dayResult?.aos_applied?.adaptive_profile?.candidate_applied === true) return true;
  if (dayResult?.aos_applied?.unified_profile?.active_profile_id) return true;

  const executionConfig = dayResult?.execution_config;
  if (!executionConfig || typeof executionConfig !== "object") return false;
  return Object.entries(executionConfig).some(
    ([key, value]) => key.endsWith("_source") && String(value || "").trim().toLowerCase() === "adaptive_profile"
  );
};

export const formatAdaptiveProfileList = (
  dayResult: DiagnosticCalendarDayResult | null | undefined,
): string | null => {
  const tokens = collectAdaptiveProfileTokens(dayResult);
  if (!tokens.length) return null;
  return tokens.join(" | ");
};
