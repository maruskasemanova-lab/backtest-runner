import { useCallback, useEffect, useRef, useState } from "react";

type FetchTickerAosOptions = {
  hydrateExecution?: boolean;
};

type ApplyUnifiedProfileOptions = {
  applyNow?: boolean;
  applyExecution?: boolean;
};

type UseRunConfigProfilesArgs = {
  ticker: string;
  strategyApiUrl: string;
  activeProfileSentinel: string;
  normalizeProfileRefToken: (value: unknown) => string;
  normalizeAosTickerConfig: (payload: unknown) => Record<string, any>;
  hydrateExecutionConfigFromPositioning: (payload: Record<string, any>) => void;
};

export const useRunConfigProfiles = ({
  ticker,
  strategyApiUrl,
  activeProfileSentinel,
  normalizeProfileRefToken,
  normalizeAosTickerConfig,
  hydrateExecutionConfigFromPositioning,
}: UseRunConfigProfilesArgs) => {
  const [aosLoading, setAosLoading] = useState(false);
  const [aosError, setAosError] = useState<string | null>(null);
  const [aosTickerConfig, setAosTickerConfig] = useState<Record<string, any>>({});
  const [unifiedProfilesLoading, setUnifiedProfilesLoading] = useState(false);
  const [unifiedProfilesResolved, setUnifiedProfilesResolved] = useState(false);
  const [unifiedProfilesError, setUnifiedProfilesError] = useState<string | null>(null);
  const [unifiedProfiles, setUnifiedProfiles] = useState<any[]>([]);
  const [activeUnifiedProfileId, setActiveUnifiedProfileId] = useState("");
  const [selectedUnifiedProfileId, setSelectedUnifiedProfileId] = useState(activeProfileSentinel);
  const lastFetchedTickerRef = useRef("");

  const fetchTickerAosConfig = useCallback(
    async (rawTicker: string, options: FetchTickerAosOptions = {}) => {
      const { hydrateExecution = false } = options;
      const upperTicker = String(rawTicker || "").trim().toUpperCase();
      if (!upperTicker) return null;
      setAosLoading(true);
      setAosError(null);

      try {
        const resp = await fetch(`/api/aos-config/${upperTicker}`);
        if (!resp.ok) {
          throw new Error(`HTTP ${resp.status}`);
        }
        const payload = await resp.json();
        const normalized = normalizeAosTickerConfig(payload);
        setAosTickerConfig(normalized);
        if (hydrateExecution) {
          hydrateExecutionConfigFromPositioning(normalized);
        }
        return normalized;
      } catch (error) {
        console.error("Failed to fetch AOS config:", error);
        setAosError("Failed to load AOS settings for selected ticker/profile.");
        setAosTickerConfig({});
        return null;
      } finally {
        setAosLoading(false);
      }
    },
    [hydrateExecutionConfigFromPositioning, normalizeAosTickerConfig],
  );

  const fetchUnifiedProfiles = useCallback(
    async (rawTicker: string) => {
      const upperTicker = String(rawTicker || "").trim().toUpperCase();
      if (!upperTicker) return null;
      setUnifiedProfilesLoading(true);
      setUnifiedProfilesResolved(false);
      setUnifiedProfilesError(null);
      try {
        const resp = await fetch(`/api/profiles/${upperTicker}`);
        if (!resp.ok) {
          throw new Error(`Failed to load unified profiles (HTTP ${resp.status}).`);
        }
        const payload = await resp.json();
        const profiles = Array.isArray(payload?.profiles) ? payload.profiles : [];
        const activeProfileId = normalizeProfileRefToken(payload?.active_profile_id);
        const knownIds = new Set(
          profiles
            .map((profile) => String(profile?.profile_id || "").trim())
            .filter(Boolean),
        );

        setUnifiedProfiles(profiles);
        setActiveUnifiedProfileId(activeProfileId);
        setSelectedUnifiedProfileId((prev) => {
          const prevId = String(prev || "").trim();
          if (prevId && prevId !== activeProfileSentinel && knownIds.has(prevId)) {
            return prevId;
          }
          return activeProfileSentinel;
        });
        return payload;
      } catch (error) {
        console.error("Failed to fetch unified profiles:", error);
        setUnifiedProfilesError("Failed to load unified profiles.");
        setUnifiedProfiles([]);
        setActiveUnifiedProfileId("");
        setSelectedUnifiedProfileId((prev) => {
          const prevId = String(prev || "").trim();
          return prevId || activeProfileSentinel;
        });
        return null;
      } finally {
        setUnifiedProfilesLoading(false);
        setUnifiedProfilesResolved(true);
      }
    },
    [activeProfileSentinel, normalizeProfileRefToken],
  );

  const applyUnifiedProfile = useCallback(
    async (
      rawTicker: string,
      profileId: string,
      options: ApplyUnifiedProfileOptions = {},
    ) => {
      const upperTicker = String(rawTicker || "").trim().toUpperCase();
      const targetProfileId = String(profileId || "").trim();
      if (!upperTicker || !targetProfileId) return null;

      const resp = await fetch("/api/profiles/apply", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ticker: upperTicker,
          profile_id: targetProfileId,
          strategy_api_url: strategyApiUrl,
          apply_now: !!options.applyNow,
          apply_execution: options.applyExecution !== false,
        }),
      });
      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        throw new Error(String(data?.detail || `HTTP ${resp.status}`));
      }
      return await resp.json();
    },
    [strategyApiUrl],
  );

  const reloadAosAndProfiles = useCallback(async () => {
    const upperTicker = String(ticker || "").trim().toUpperCase();
    if (!upperTicker) return;
    await Promise.all([
      fetchTickerAosConfig(upperTicker, { hydrateExecution: true }),
      fetchUnifiedProfiles(upperTicker),
    ]);
  }, [fetchTickerAosConfig, fetchUnifiedProfiles, ticker]);

  useEffect(() => {
    const upperTicker = String(ticker || "").trim().toUpperCase();
    if (!upperTicker) {
      lastFetchedTickerRef.current = "";
      setAosTickerConfig({});
      setAosError(null);
      setUnifiedProfiles([]);
      setActiveUnifiedProfileId("");
      setSelectedUnifiedProfileId(activeProfileSentinel);
      setUnifiedProfilesResolved(false);
      setUnifiedProfilesError(null);
      return;
    }

    // Only re-fetch when ticker actually changes to avoid overwriting
    // manual strategy sidebar toggles with a stale profile state.
    if (lastFetchedTickerRef.current === upperTicker) {
      return;
    }
    lastFetchedTickerRef.current = upperTicker;

    fetchTickerAosConfig(upperTicker, { hydrateExecution: true });
    fetchUnifiedProfiles(upperTicker);
  }, [activeProfileSentinel, fetchTickerAosConfig, fetchUnifiedProfiles, ticker]);

  return {
    aosLoading,
    aosError,
    aosTickerConfig,
    unifiedProfilesLoading,
    unifiedProfilesResolved,
    unifiedProfilesError,
    unifiedProfiles,
    activeUnifiedProfileId,
    setActiveUnifiedProfileId,
    selectedUnifiedProfileId,
    setSelectedUnifiedProfileId,
    fetchTickerAosConfig,
    fetchUnifiedProfiles,
    applyUnifiedProfile,
    reloadAosAndProfiles,
  };
};
