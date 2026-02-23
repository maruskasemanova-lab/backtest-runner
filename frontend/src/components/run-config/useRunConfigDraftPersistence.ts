import { useEffect, useRef, useState } from "react";
import type { Dispatch, MutableRefObject, SetStateAction } from "react";
import {
  ACTIVE_UNIFIED_PROFILE_SENTINEL,
  RUN_CONFIG_DRAFT_VERSION,
  isPlainObject,
  mergeRunConfigWithDefaults,
  normalizeDraftVersion,
  normalizeProfileRefToken,
  writePersistedRunConfigDraft,
} from "./runConfigHelpers";

type UseRunConfigDraftPersistenceArgs = {
  authToken: string;
  ticker: string;
  config: Record<string, any>;
  setConfig: Dispatch<SetStateAction<Record<string, any>>>;
  selectedUnifiedProfileId: string;
  setSelectedUnifiedProfileId: (profileId: string) => void;
  unifiedProfilesLoading: boolean;
  unifiedProfilesResolved: boolean;
  unifiedProfiles: any[];
  persistedRunConfigDraftRef: MutableRefObject<Record<string, any> | null>;
};

export const useRunConfigDraftPersistence = ({
  authToken,
  ticker,
  config,
  setConfig,
  selectedUnifiedProfileId,
  setSelectedUnifiedProfileId,
  unifiedProfilesLoading,
  unifiedProfilesResolved,
  unifiedProfiles,
  persistedRunConfigDraftRef,
}: UseRunConfigDraftPersistenceArgs) => {
  const [remoteSettingsReady, setRemoteSettingsReady] = useState(false);
  const initialPersistedProfileAppliedRef = useRef(false);
  const remoteSettingsDebounceRef = useRef<number | null>(null);

  useEffect(() => {
    if (initialPersistedProfileAppliedRef.current) return;
    const normalizedTicker = String(ticker || "").trim().toUpperCase();
    if (!normalizedTicker) return;
    if (unifiedProfilesLoading) return;
    if (!unifiedProfilesResolved) return;
    initialPersistedProfileAppliedRef.current = true;

    const persistedSelected = normalizeProfileRefToken(
      persistedRunConfigDraftRef.current?.selected_unified_profile_id,
    );
    if (!persistedSelected) return;
    if (persistedSelected === ACTIVE_UNIFIED_PROFILE_SENTINEL) {
      setSelectedUnifiedProfileId(ACTIVE_UNIFIED_PROFILE_SENTINEL);
      return;
    }

    const known = unifiedProfiles.some(
      (profile) => String(profile?.profile_id || "").trim() === persistedSelected,
    );
    if (known) {
      setSelectedUnifiedProfileId(persistedSelected);
    }
  }, [
    persistedRunConfigDraftRef,
    setSelectedUnifiedProfileId,
    ticker,
    unifiedProfiles,
    unifiedProfilesLoading,
    unifiedProfilesResolved,
  ]);

  useEffect(() => {
    setRemoteSettingsReady(false);
    if (!authToken || typeof window === "undefined") {
      setRemoteSettingsReady(true);
      return;
    }
    let cancelled = false;

    const hydrateFromRemoteSettings = async () => {
      try {
        const response = await fetch("/api/v2/user/settings", {
          headers: {
            Authorization: `Bearer ${authToken}`,
          },
        });
        if (!response.ok) {
          return;
        }
        const payload = await response.json().catch(() => ({}));
        const settings =
          payload && typeof payload.settings === "object" && !Array.isArray(payload.settings)
            ? payload.settings
            : {};
        const remoteRawDraft =
          settings && typeof settings.run_config_draft === "object" ? settings.run_config_draft : null;
        if (!remoteRawDraft) return;

        const normalizedRemoteDraft =
          isPlainObject(remoteRawDraft.config)
            ? {
                version: Number(remoteRawDraft.version || RUN_CONFIG_DRAFT_VERSION),
                saved_at: String(remoteRawDraft.saved_at || ""),
                config: remoteRawDraft.config,
                selected_unified_profile_id: String(remoteRawDraft.selected_unified_profile_id || ""),
              }
            : isPlainObject(remoteRawDraft)
              ? {
                  version: 0,
                  saved_at: String(remoteRawDraft.saved_at || ""),
                  config: remoteRawDraft,
                  selected_unified_profile_id: "",
                }
              : null;
        if (!normalizedRemoteDraft || !isPlainObject(normalizedRemoteDraft.config)) {
          return;
        }

        const localSavedAtRaw = String(persistedRunConfigDraftRef.current?.saved_at || "");
        const remoteSavedAtRaw = String(normalizedRemoteDraft.saved_at || "");
        const localSavedAtMs = Date.parse(localSavedAtRaw);
        const remoteSavedAtMs = Date.parse(remoteSavedAtRaw);
        const hasLocalConfig =
          !!persistedRunConfigDraftRef.current &&
          isPlainObject(persistedRunConfigDraftRef.current.config);
        const localIsNewer =
          hasLocalConfig &&
          Number.isFinite(localSavedAtMs) &&
          Number.isFinite(remoteSavedAtMs) &&
          localSavedAtMs > remoteSavedAtMs;
        if (localIsNewer) {
          return;
        }

        persistedRunConfigDraftRef.current = normalizedRemoteDraft;
        if (cancelled) return;

        setConfig((prev) =>
          mergeRunConfigWithDefaults(
            normalizedRemoteDraft.config,
            prev,
            normalizeDraftVersion(normalizedRemoteDraft.version),
          )
        );
        const remoteSelected = normalizeProfileRefToken(
          normalizedRemoteDraft.selected_unified_profile_id,
        );
        if (remoteSelected) {
          setSelectedUnifiedProfileId(remoteSelected);
        }
      } catch (error) {
        console.warn("Failed to hydrate run config draft from user settings:", error);
      } finally {
        if (!cancelled) {
          setRemoteSettingsReady(true);
        }
      }
    };

    hydrateFromRemoteSettings();
    return () => {
      cancelled = true;
    };
  }, [authToken, persistedRunConfigDraftRef, setConfig, setSelectedUnifiedProfileId]);

  useEffect(() => {
    // Wait until the initial persisted profile has been restored before writing.
    // Otherwise the default sentinel value would overwrite the persisted selection.
    if (!initialPersistedProfileAppliedRef.current) return;

    const payload = writePersistedRunConfigDraft(config, selectedUnifiedProfileId);
    if (payload) {
      persistedRunConfigDraftRef.current = payload;
    }
  }, [config, persistedRunConfigDraftRef, selectedUnifiedProfileId]);

  useEffect(() => {
    if (!authToken || typeof window === "undefined") return undefined;
    if (!remoteSettingsReady) return undefined;
    if (!initialPersistedProfileAppliedRef.current) return undefined;

    if (remoteSettingsDebounceRef.current !== null) {
      window.clearTimeout(remoteSettingsDebounceRef.current);
      remoteSettingsDebounceRef.current = null;
    }
    const timeoutId = window.setTimeout(async () => {
      const draftPayload = {
        version: RUN_CONFIG_DRAFT_VERSION,
        saved_at: new Date().toISOString(),
        config,
        selected_unified_profile_id: String(selectedUnifiedProfileId || ""),
      };
      persistedRunConfigDraftRef.current = draftPayload;
      try {
        await fetch("/api/v2/user/settings", {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${authToken}`,
          },
          body: JSON.stringify({
            settings: {
              run_config_draft: draftPayload,
            },
          }),
        });
      } catch (error) {
        console.warn("Failed to persist run config draft to user settings:", error);
      }
    }, 650);
    remoteSettingsDebounceRef.current = timeoutId;

    return () => {
      if (remoteSettingsDebounceRef.current !== null) {
        window.clearTimeout(remoteSettingsDebounceRef.current);
        remoteSettingsDebounceRef.current = null;
      }
    };
  }, [authToken, config, persistedRunConfigDraftRef, remoteSettingsReady, selectedUnifiedProfileId]);
};
