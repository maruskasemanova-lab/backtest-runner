import { useCallback, useEffect, useState } from "react";
import type { ChangeEvent, Dispatch, SetStateAction } from "react";

type UseRunConfigUnifiedProfileSelectionArgs = {
  showProfileControls: boolean;
  ticker: string;
  activeProfileSentinel: string;
  unifiedProfiles: any[];
  fetchUnifiedProfiles: (ticker: string) => Promise<any>;
  setSelectedUnifiedProfileId: (profileId: string) => void;
  reloadAosAndProfiles: () => Promise<void>;
  applyUnifiedProfile: (
    ticker: string,
    profileId: string,
    options: { applyNow: boolean; applyExecution: boolean },
  ) => Promise<any>;
  setActiveUnifiedProfileId: (profileId: string) => void;
  hydrateRunConfigFromUnifiedProfile: (profile: any) => void;
  setError: Dispatch<SetStateAction<string | null>>;
};

export const useRunConfigUnifiedProfileSelection = ({
  showProfileControls,
  ticker,
  activeProfileSentinel,
  unifiedProfiles,
  fetchUnifiedProfiles,
  setSelectedUnifiedProfileId,
  reloadAosAndProfiles,
  applyUnifiedProfile,
  setActiveUnifiedProfileId,
  hydrateRunConfigFromUnifiedProfile,
  setError,
}: UseRunConfigUnifiedProfileSelectionArgs) => {
  const [unifiedProfileSwitching, setUnifiedProfileSwitching] = useState(false);

  useEffect(() => {
    if (!showProfileControls) return;
    const normalizedTicker = String(ticker || "").trim().toUpperCase();
    if (!normalizedTicker) return;
    fetchUnifiedProfiles(normalizedTicker);
  }, [fetchUnifiedProfiles, showProfileControls, ticker]);

  const handleUnifiedProfileSelectionChange = useCallback(
    async (event: ChangeEvent<HTMLSelectElement>) => {
      const nextSelection = String(event?.target?.value || "").trim();
      const normalizedSelection = nextSelection || activeProfileSentinel;
      setSelectedUnifiedProfileId(normalizedSelection);

      const upperTicker = String(ticker || "").trim().toUpperCase();
      if (!upperTicker) return;

      if (normalizedSelection === activeProfileSentinel) {
        await reloadAosAndProfiles();
        return;
      }

      const selectedProfile = unifiedProfiles.find(
        (profile) => String(profile?.profile_id || "").trim() === normalizedSelection,
      );

      setUnifiedProfileSwitching(true);
      setError(null);
      try {
        await applyUnifiedProfile(upperTicker, normalizedSelection, {
          applyNow: true,
          applyExecution: true,
        });
        setActiveUnifiedProfileId(normalizedSelection);
        if (selectedProfile) {
          hydrateRunConfigFromUnifiedProfile(selectedProfile);
        }
        await reloadAosAndProfiles();
      } catch (switchError) {
        const message =
          switchError instanceof Error ? switchError.message : String(switchError || "Unknown error");
        setError(`Failed to switch unified profile: ${message}`);
      } finally {
        setUnifiedProfileSwitching(false);
      }
    },
    [
      activeProfileSentinel,
      applyUnifiedProfile,
      hydrateRunConfigFromUnifiedProfile,
      reloadAosAndProfiles,
      setActiveUnifiedProfileId,
      setError,
      setSelectedUnifiedProfileId,
      ticker,
      unifiedProfiles,
    ],
  );

  return {
    unifiedProfileSwitching,
    handleUnifiedProfileSelectionChange,
  };
};
