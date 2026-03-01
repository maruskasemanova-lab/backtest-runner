import { useEffect, useMemo } from "react";
import { useRunConfigState } from "../run-config/useRunConfigState";
import { ACTIVE_UNIFIED_PROFILE_SENTINEL } from "../run-config/runConfigHelpers";

/**
 * Standalone useRunConfigState for StrategyAnalyzer usage.
 * Creates an independent config state not connected to the main RunConfig sidebar.
 * Syncs the ticker when the parent's ticker changes.
 */
export function useStrategyAnalyzerConfigState(ticker: string) {
  const state = useRunConfigState({
    onStart: async () => null,
    isRunning: false,
    onTickerChange: () => {},
    effectiveExecutionConfig: null,
    activeRuns: [],
    activeRunKey: "",
    onAttachRun: () => {},
    onKillRun: undefined,
    sidebarSubsection: "profiles",
    authToken: "",
    activeRunState: null,
  });

  const currentTicker = String(state.config?.ticker || "")
    .trim()
    .toUpperCase();

  useEffect(() => {
    const upperTicker = String(ticker || "").trim().toUpperCase();
    if (!upperTicker) return;
    if (currentTicker === upperTicker) return;
    state.handleTickerChange(upperTicker);
  }, [currentTicker, ticker, state.handleTickerChange]);

  const activeProfileId = useMemo(() => {
    const selectedId = String(state.selectedUnifiedProfileId || "").trim();
    if (!selectedId || selectedId === ACTIVE_UNIFIED_PROFILE_SENTINEL) {
      return String(state.activeUnifiedProfileId || "").trim();
    }
    return selectedId;
  }, [state.activeUnifiedProfileId, state.selectedUnifiedProfileId]);

  const activeProfile = useMemo(() => {
    if (!activeProfileId) return null;
    const profiles = Array.isArray(state.unifiedProfiles)
      ? state.unifiedProfiles
      : [];
    return (
      profiles.find(
        (p: any) => String(p?.profile_id || "").trim() === activeProfileId,
      ) || null
    );
  }, [activeProfileId, state.unifiedProfiles]);

  return {
    config: state.config,
    handleChange: state.handleChange,
    momentumSleeves: state.momentumSleeves,
    handleMomentumSleeveChange: state.handleMomentumSleeveChange,
    handleAddMomentumSleeve: state.handleAddMomentumSleeve,
    handleRemoveMomentumSleeve: state.handleRemoveMomentumSleeve,
    activeProfile,
    activeProfileId,
  };
}
