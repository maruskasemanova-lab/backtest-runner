import { useCallback, useMemo } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import type {
  AdaptiveStudioComboProfileRow,
  AdaptiveStudioObjectRecord,
  AdaptiveStudioStudioProfileRow,
  AdaptiveStudioTunedProfileRow,
  AdaptiveStudioUnifiedProfileRow,
} from "../profileTypes";
import {
  STUDIO_PROFILE_ACTIVE_KEY,
  STUDIO_PROFILE_LIST_KEY,
} from "../constants/adaptive-studio";
import {
  asObject,
  buildLegacyUnifiedProfiles,
  normalizeAvailableTickers,
  normalizeProfileRefToken,
  normalizeStrategyUniverse,
  normalizeStudioProfiles,
  normalizeUnifiedProfiles,
} from "../utils/adaptive-studio-transformers";

type AdaptiveStudioServerOptionsResult<Row> = {
  activeProfileId: string;
  profiles: Row[];
};

type UseAdaptiveStudioDataArgs = {
  activeTicker: string;
  strategyApiBase: string;
  strategyUniverseFallback: string[];
};

type UseAdaptiveStudioDataResult = {
  availableTickers: string[];
  strategyUniverse: string[];
  rawTickerConfig: AdaptiveStudioObjectRecord;
  studioProfileList: AdaptiveStudioStudioProfileRow[];
  activeStudioProfileId: string;
  profileList: AdaptiveStudioTunedProfileRow[];
  activeProfileIdFromServer: string;
  comboList: AdaptiveStudioComboProfileRow[];
  activeComboIdFromServer: string;
  unifiedList: AdaptiveStudioUnifiedProfileRow[];
  activeUnifiedIdFromServer: string;
  loading: boolean;
  profileLoading: boolean;
  comboLoading: boolean;
  unifiedLoading: boolean;
  tickerConfigError: string | null;
  profileError: string | null;
  comboError: string | null;
  unifiedError: string | null;
  refreshActiveTickerData: () => Promise<void>;
  refreshAllData: () => Promise<void>;
  setTickerConfigCache: (nextConfig: AdaptiveStudioObjectRecord) => void;
};

const buildOptionsResult = <Row,>(
  payload: unknown,
  rowGuard: (value: unknown) => value is Row,
): AdaptiveStudioServerOptionsResult<Row> => {
  const source = asObject(payload);
  return {
    activeProfileId: normalizeProfileRefToken(source.active_profile_id),
    profiles: Array.isArray(source.profiles) ? source.profiles.filter(rowGuard) : [],
  };
};

const isObjectRow = <T extends Record<string, unknown>>(value: unknown): value is T =>
  Boolean(value) && typeof value === "object" && !Array.isArray(value);

export function useAdaptiveStudioData({
  activeTicker,
  strategyApiBase,
  strategyUniverseFallback,
}: UseAdaptiveStudioDataArgs): UseAdaptiveStudioDataResult {
  const queryClient = useQueryClient();
  const normalizedTicker = String(activeTicker || "").toUpperCase();
  const availableTickersQuery = useQuery({
    queryKey: ["adaptive-studio", "available-tickers"],
    queryFn: async ({ signal }) => {
      const response = await fetch("/api/available-data?refresh=1", { signal });
      if (!response.ok) return [];
      const payload = await response.json().catch(() => ({}));
      return normalizeAvailableTickers(payload);
    },
    staleTime: 60_000,
  });

  const strategyUniverseQuery = useQuery({
    queryKey: ["adaptive-studio", "strategy-universe", strategyApiBase],
    queryFn: async ({ signal }) => {
      const response = await fetch(`${strategyApiBase}/api/strategies`, { signal });
      if (!response.ok) return [...strategyUniverseFallback];
      const payload = await response.json().catch(() => ({}));
      return normalizeStrategyUniverse(payload);
    },
    staleTime: 60_000,
  });

  const tickerConfigQueryKey = ["adaptive-studio", "ticker-config", normalizedTicker] as const;
  const profileOptionsQueryKey = ["adaptive-studio", "profile-options", normalizedTicker] as const;
  const comboOptionsQueryKey = ["adaptive-studio", "combo-options", normalizedTicker] as const;
  const unifiedProfilesQueryKey = ["adaptive-studio", "unified-profiles", normalizedTicker] as const;

  const tickerConfigQuery = useQuery({
    queryKey: tickerConfigQueryKey,
    enabled: Boolean(normalizedTicker),
    queryFn: async ({ signal }) => {
      const response = await fetch(`/api/aos-config/${normalizedTicker}`, { signal });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const payload = await response.json().catch(() => ({}));
      return asObject(payload);
    },
    retry: false,
    staleTime: 30_000,
  });

  const profileOptionsQuery = useQuery({
    queryKey: profileOptionsQueryKey,
    enabled: Boolean(normalizedTicker),
    queryFn: async ({ signal }) => {
      const response = await fetch(`/api/adaptive-tuner/options/${normalizedTicker}`, { signal });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const payload = await response.json().catch(() => ({}));
      return buildOptionsResult<AdaptiveStudioTunedProfileRow>(payload, isObjectRow);
    },
    retry: false,
    staleTime: 30_000,
  });

  const comboOptionsQuery = useQuery({
    queryKey: comboOptionsQueryKey,
    enabled: Boolean(normalizedTicker),
    queryFn: async ({ signal }) => {
      const response = await fetch(`/api/strategy-combos/${normalizedTicker}`, { signal });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const payload = await response.json().catch(() => ({}));
      return buildOptionsResult<AdaptiveStudioComboProfileRow>(payload, isObjectRow);
    },
    retry: false,
    staleTime: 30_000,
  });

  const unifiedProfilesQuery = useQuery({
    queryKey: unifiedProfilesQueryKey,
    enabled:
      Boolean(normalizedTicker) &&
      tickerConfigQuery.isFetched &&
      profileOptionsQuery.isFetched &&
      comboOptionsQuery.isFetched,
    queryFn: async ({ signal }) => {
      const response = await fetch(`/api/profiles/${normalizedTicker}`, { signal });
      if (response.ok) {
        const payload = await response.json().catch(() => ({}));
        const source = asObject(payload);
        return {
          activeProfileId: normalizeProfileRefToken(source.active_profile_id),
          profiles: normalizeUnifiedProfiles(source.profiles),
        };
      }

      const fallbackPayload = buildLegacyUnifiedProfiles({
        ticker: normalizedTicker,
        tickerConfig: queryClient.getQueryData<AdaptiveStudioObjectRecord>(tickerConfigQueryKey),
        comboPayload: (() => {
          const comboData = queryClient.getQueryData<AdaptiveStudioServerOptionsResult<AdaptiveStudioComboProfileRow>>(comboOptionsQueryKey);
          return comboData
            ? { active_profile_id: comboData.activeProfileId, profiles: comboData.profiles }
            : null;
        })(),
        tunedPayload: (() => {
          const profileData = queryClient.getQueryData<AdaptiveStudioServerOptionsResult<AdaptiveStudioTunedProfileRow>>(profileOptionsQueryKey);
          return profileData
            ? { active_profile_id: profileData.activeProfileId, profiles: profileData.profiles }
            : null;
        })(),
      });

      return {
        activeProfileId: normalizeProfileRefToken(fallbackPayload.active_profile_id),
        profiles: normalizeUnifiedProfiles(fallbackPayload.profiles),
      };
    },
    retry: false,
    staleTime: 30_000,
  });

  const availableTickers = availableTickersQuery.data ?? [];
  const strategyUniverse = strategyUniverseQuery.data ?? [...strategyUniverseFallback];
  const rawTickerConfig = tickerConfigQuery.data ?? {};
  const studioProfileList = useMemo(
    () => normalizeStudioProfiles(rawTickerConfig?.[STUDIO_PROFILE_LIST_KEY], strategyUniverse),
    [rawTickerConfig, strategyUniverse],
  );
  const activeStudioProfileId = useMemo(() => {
    const requestedActiveStudioId = String(rawTickerConfig?.[STUDIO_PROFILE_ACTIVE_KEY] || "").trim();
    const resolvedActiveStudioId = studioProfileList.some(
      (profile) => String(profile?.profile_id || "").trim() === requestedActiveStudioId,
    )
      ? requestedActiveStudioId
      : "";
    return resolvedActiveStudioId;
  }, [rawTickerConfig, studioProfileList]);

  const refreshActiveTickerData = useCallback(async () => {
    if (!normalizedTicker) return;
    await Promise.all([
      tickerConfigQuery.refetch(),
      profileOptionsQuery.refetch(),
      comboOptionsQuery.refetch(),
    ]);
    await unifiedProfilesQuery.refetch();
  }, [comboOptionsQuery, normalizedTicker, profileOptionsQuery, tickerConfigQuery, unifiedProfilesQuery]);

  const refreshAllData = useCallback(async () => {
    await Promise.all([
      availableTickersQuery.refetch(),
      strategyUniverseQuery.refetch(),
      refreshActiveTickerData(),
    ]);
  }, [availableTickersQuery, refreshActiveTickerData, strategyUniverseQuery]);

  const setTickerConfigCache = useCallback((nextConfig: AdaptiveStudioObjectRecord) => {
    if (!normalizedTicker) return;
    queryClient.setQueryData(tickerConfigQueryKey, nextConfig);
  }, [normalizedTicker, queryClient, tickerConfigQueryKey]);

  return {
    availableTickers,
    strategyUniverse,
    rawTickerConfig,
    studioProfileList,
    activeStudioProfileId,
    profileList: profileOptionsQuery.data?.profiles ?? [],
    activeProfileIdFromServer: profileOptionsQuery.data?.activeProfileId ?? "",
    comboList: comboOptionsQuery.data?.profiles ?? [],
    activeComboIdFromServer: comboOptionsQuery.data?.activeProfileId ?? "",
    unifiedList: unifiedProfilesQuery.data?.profiles ?? [],
    activeUnifiedIdFromServer: unifiedProfilesQuery.data?.activeProfileId ?? "",
    loading: Boolean(normalizedTicker) && tickerConfigQuery.isFetching,
    profileLoading: Boolean(normalizedTicker) && profileOptionsQuery.isFetching,
    comboLoading: Boolean(normalizedTicker) && comboOptionsQuery.isFetching,
    unifiedLoading: Boolean(normalizedTicker) && unifiedProfilesQuery.isFetching,
    tickerConfigError: tickerConfigQuery.isError ? "Failed to load adaptive configuration for selected ticker." : null,
    profileError: profileOptionsQuery.isError ? "Failed to load adaptive tuned profiles for this ticker." : null,
    comboError: comboOptionsQuery.isError ? "Failed to load strategy combinations for this ticker." : null,
    unifiedError: unifiedProfilesQuery.isError ? "Failed to load unified profiles for this ticker." : null,
    refreshActiveTickerData,
    refreshAllData,
    setTickerConfigCache,
  };
}
