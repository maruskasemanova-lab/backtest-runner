import { useCallback, useEffect, useMemo, useState } from "react";

interface UseComboProfilesArgs {
  selectedTicker?: string;
  resolvedUrl: string;
  fetchStrategies: () => Promise<Record<string, any> | null>;
}

interface ComboProfile {
  profile_id?: string;
  profile_name?: string;
  strategy_params?: Record<string, unknown>;
  created_at?: string;
  updated_at?: string;
}

interface UseComboProfilesResult {
  comboProfiles: ComboProfile[];
  comboActiveProfileId: string;
  comboSelectedProfileId: string;
  comboProfileName: string;
  comboLoading: boolean;
  comboBusy: boolean;
  comboError: string | null;
  comboNotice: string | null;
  setComboSelectedProfileId: (value: string) => void;
  setComboProfileName: (value: string) => void;
  setComboNotice: (value: string | null) => void;
  fetchStrategyCombos: (ticker: string) => Promise<Record<string, any> | null>;
  captureCurrentCombo: () => Promise<void>;
  applySelectedCombo: () => Promise<void>;
  selectedComboProfile: ComboProfile | null;
}

export function useComboProfiles({
  selectedTicker,
  resolvedUrl,
  fetchStrategies,
}: UseComboProfilesArgs): UseComboProfilesResult {
  const [comboProfiles, setComboProfiles] = useState<ComboProfile[]>([]);
  const [comboActiveProfileId, setComboActiveProfileId] = useState("");
  const [comboSelectedProfileId, setComboSelectedProfileId] = useState("");
  const [comboProfileName, setComboProfileName] = useState("");
  const [comboLoading, setComboLoading] = useState(false);
  const [comboBusy, setComboBusy] = useState(false);
  const [comboError, setComboError] = useState<string | null>(null);
  const [comboNotice, setComboNotice] = useState<string | null>(null);

  const fetchStrategyCombos = useCallback(async (ticker: string) => {
    const upperTicker = String(ticker || "").toUpperCase().trim();
    if (!upperTicker) {
      setComboProfiles([]);
      setComboActiveProfileId("");
      setComboSelectedProfileId("");
      setComboError(null);
      return null;
    }
    setComboLoading(true);
    setComboError(null);
    try {
      const resp = await fetch(`/api/strategy-combos/${upperTicker}`);
      if (!resp.ok) {
        throw new Error(`HTTP ${resp.status}`);
      }
      const payload = await resp.json();
      const profiles = Array.isArray(payload?.profiles) ? payload.profiles : [];
      const activeId = String(payload?.active_profile_id || "").trim();
      setComboProfiles(profiles);
      setComboActiveProfileId(activeId);
      setComboSelectedProfileId((prev) => {
        const prevId = String(prev || "").trim();
        if (prevId && profiles.some((profile: ComboProfile) => String(profile?.profile_id || "") === prevId)) {
          return prevId;
        }
        if (activeId) return activeId;
        const firstId = String(profiles[0]?.profile_id || "").trim();
        return firstId;
      });
      return payload;
    } catch (err: any) {
      console.error("Failed to load strategy combos:", err);
      setComboError(`Failed to load strategy combinations: ${err.message}`);
      setComboProfiles([]);
      setComboActiveProfileId("");
      setComboSelectedProfileId("");
      return null;
    } finally {
      setComboLoading(false);
    }
  }, []);

  const captureCurrentCombo = useCallback(async () => {
    const upperTicker = String(selectedTicker || "").toUpperCase().trim();
    if (!upperTicker) return;
    setComboBusy(true);
    setComboError(null);
    setComboNotice(null);
    try {
      const resp = await fetch("/api/strategy-combos/capture", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ticker: upperTicker,
          profile_name: comboProfileName || null,
          strategy_api_url: resolvedUrl,
          set_active: true,
        }),
      });
      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        throw new Error(data?.detail || `HTTP ${resp.status}`);
      }
      const payload = await resp.json();
      const capturedId = String(payload?.profile?.profile_id || "").trim();
      setComboNotice(
        capturedId
          ? `Captured combo ${capturedId} for ${upperTicker}.`
          : `Captured strategy combination for ${upperTicker}.`,
      );
      if (capturedId) {
        setComboSelectedProfileId(capturedId);
      }
      await fetchStrategyCombos(upperTicker);
      window.dispatchEvent(
        new CustomEvent("strategy-combo-updated", {
          detail: { ticker: upperTicker, active_profile_id: capturedId || null },
        }),
      );
    } catch (err: any) {
      setComboError(`Failed to capture strategy combination: ${err.message}`);
    } finally {
      setComboBusy(false);
    }
  }, [comboProfileName, fetchStrategyCombos, resolvedUrl, selectedTicker]);

  const applySelectedCombo = useCallback(async () => {
    const upperTicker = String(selectedTicker || "").toUpperCase().trim();
    const profileId = String(comboSelectedProfileId || "").trim();
    if (!upperTicker || !profileId) return;
    setComboBusy(true);
    setComboError(null);
    setComboNotice(null);
    try {
      const resp = await fetch("/api/strategy-combos/apply", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ticker: upperTicker,
          profile_id: profileId,
          strategy_api_url: resolvedUrl,
          apply_now: true,
        }),
      });
      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        throw new Error(data?.detail || `HTTP ${resp.status}`);
      }
      const payload = await resp.json();
      const appliedCount = Number(payload?.apply_result?.applied_count || 0);
      const failedCount = Number(payload?.apply_result?.failed_count || 0);
      setComboNotice(
        `Applied combo ${profileId} (${appliedCount} strategies updated${failedCount ? `, ${failedCount} failed` : ""}).`,
      );
      await Promise.all([fetchStrategyCombos(upperTicker), fetchStrategies()]);
      window.dispatchEvent(
        new CustomEvent("strategy-combo-updated", {
          detail: { ticker: upperTicker, active_profile_id: profileId },
        }),
      );
    } catch (err: any) {
      setComboError(`Failed to apply strategy combination: ${err.message}`);
    } finally {
      setComboBusy(false);
    }
  }, [comboSelectedProfileId, fetchStrategies, fetchStrategyCombos, resolvedUrl, selectedTicker]);

  useEffect(() => {
    const upperTicker = String(selectedTicker || "").toUpperCase().trim();
    if (!upperTicker) {
      setComboProfiles([]);
      setComboActiveProfileId("");
      setComboSelectedProfileId("");
      setComboProfileName("");
      setComboNotice(null);
      setComboError(null);
      return;
    }
    setComboProfileName((prev) => prev || `${upperTicker}-combo`);
    fetchStrategyCombos(upperTicker);
  }, [fetchStrategyCombos, selectedTicker]);

  const selectedComboProfile = useMemo(() => {
    const selectedId = String(comboSelectedProfileId || "").trim();
    if (!selectedId) return null;
    return (
      comboProfiles.find(
        (profile) => String(profile?.profile_id || "").trim() === selectedId,
      ) || null
    );
  }, [comboProfiles, comboSelectedProfileId]);

  return {
    comboProfiles,
    comboActiveProfileId,
    comboSelectedProfileId,
    comboProfileName,
    comboLoading,
    comboBusy,
    comboError,
    comboNotice,
    setComboSelectedProfileId,
    setComboProfileName,
    setComboNotice,
    fetchStrategyCombos,
    captureCurrentCombo,
    applySelectedCombo,
    selectedComboProfile,
  };
}
