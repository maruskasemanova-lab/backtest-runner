import { useState, useEffect, useCallback, useRef, useMemo } from "react";
import { useMomentumSleeves } from "./useMomentumSleeves";
import { useExecutionConfigBus } from "./useExecutionConfigBus";
import { useLoadingElapsedSeconds } from "./useLoadingElapsedSeconds";
import { useRunConfigProfiles } from "./useRunConfigProfiles";
import { useRunConfigEffectiveSnapshot } from "./useRunConfigEffectiveSnapshot";
import { useRunConfigCheckpoints } from "./useRunConfigCheckpoints";
import { useRunConfigPrewarm } from "./useRunConfigPrewarm";
import { useAttachedRunHydration } from "./useAttachedRunHydration";
import { useRunConfigStartHandler } from "./useRunConfigStartHandler";
import { useRunConfigFormHandlers } from "./useRunConfigFormHandlers";
import { useRunConfigAvailableData } from "./useRunConfigAvailableData";
import { useRunConfigDraftPersistence } from "./useRunConfigDraftPersistence";
import { useRunConfigUnifiedProfileSelection } from "./useRunConfigUnifiedProfileSelection";
import {
  applyPositioningToRunConfig,
  applyUnifiedProfileToRunConfig,
  buildPrewarmPlanForConfig,
  enforceMuIntradayEntryQuality,
  resolveUnifiedProfileSections,
  selectRunningRunOptions,
} from "./runConfigStateHelpers";

import {
  normalizeStrategySelectionMode,
  parseMaxActiveStrategies,
  normalizeProfileRefToken,
  ACTIVE_UNIFIED_PROFILE_SENTINEL,
  MU_TICKER,
  MU_REPRO_PROFILE_ID,
  MU_SCALP_PROFILE_ID,
  AUTO_PREWARM_TICKERS,
  AUTO_PREWARM_CHUNK_DAYS,
  AUTO_PREWARM_CHUNK_MAX_RETRIES,
  AUTO_PREWARM_RETRY_BASE_MS,
  START_MODE_FAST_RESTART,
  START_MODE_RESUME_WARM_START,
  START_MODE_OPTIONS,
  normalizeStartMode,
  deriveStartModeFromLegacyFlags,
  resolveStartModeRuntime,
  isPlainObject,
  readPersistedRunConfigDraft,
  normalizeDraftVersion,
  mergeRunConfigWithDefaults,
  parseRunKeyIdentity,
  resolveAttachedRunDates,
  normalizeAosTickerConfig,
  normalizeStopLossMode,
  resolveFixedStopLossPct,
  buildDefaultRunConfig,
  formatPrewarmReadyMessage,
} from "./runConfigHelpers";

export interface UseRunConfigStateProps {
  onStart: any;
  isRunning: boolean;
  onTickerChange: any;
  effectiveExecutionConfig: any;
  activeRuns: any[];
  activeRunKey: string;
  onAttachRun: any;
  onKillRun?: (runKey: string) => Promise<void>;
  sidebarSubsection: string;
  authToken: string;
  activeRunState: any;
}

export function useRunConfigState({
  onStart,
  isRunning,
  onTickerChange,
  effectiveExecutionConfig,
  activeRuns = [],
  activeRunKey = "",
  onAttachRun,
  onKillRun,
  sidebarSubsection = "all",
  authToken = "",
  activeRunState = null,
}: UseRunConfigStateProps) {
  const persistedRunConfigDraftRef = useRef<Record<string, any> | null>(null);
  if (persistedRunConfigDraftRef.current === null) {
    persistedRunConfigDraftRef.current = readPersistedRunConfigDraft();
  }

  const [config, setConfig] = useState(() => {
    const defaults = buildDefaultRunConfig();
    const persistedConfig =
      persistedRunConfigDraftRef.current && isPlainObject(persistedRunConfigDraftRef.current.config)
        ? persistedRunConfigDraftRef.current.config
        : null;
    const persistedVersion = normalizeDraftVersion(persistedRunConfigDraftRef.current?.version);
    return mergeRunConfigWithDefaults(persistedConfig, defaults, persistedVersion);
  });

  const [loading, setLoading] = useState(false);
  const [cacheFlushLoading, setCacheFlushLoading] = useState(false);
  const [killRunLoading, setKillRunLoading] = useState(false);
  const [cacheFlushMessage, setCacheFlushMessage] = useState<string | null>(null);
  const [startTiming, setStartTiming] = useState(null);
  const [error, setError] = useState<string | null>(null);
  const loadingElapsedSec = useLoadingElapsedSeconds(loading);
  const initialTickerSyncRef = useRef(false);
  const { availableData, availableDataError } = useRunConfigAvailableData({
    setConfig,
    onTickerChange,
  });

  const strategyApiBase = (config.strategy_api_url || "").replace(/\/+$/, "");
  const runningRunOptions = useMemo(() => selectRunningRunOptions(activeRuns), [activeRuns]);
  const selectedStartMode = normalizeStartMode(
    deriveStartModeFromLegacyFlags(config, START_MODE_FAST_RESTART),
    START_MODE_FAST_RESTART
  );
  const startModeRuntime = resolveStartModeRuntime(selectedStartMode);
  const selectedStartModeOption =
    START_MODE_OPTIONS.find((option) => option.value === selectedStartMode) || START_MODE_OPTIONS[1];
  const showDateRangeControls = sidebarSubsection === "all" || sidebarSubsection === "dates";
  const showProfileControls = sidebarSubsection === "all" || sidebarSubsection === "profiles";
  const showStartControls = sidebarSubsection === "all" || sidebarSubsection === "start";

  useEffect(() => {
    const ticker = String(config.ticker || "").trim().toUpperCase();
    if (ticker !== MU_TICKER) return;
    if (!config.intraday_levels_enabled) return;
    if (config.intraday_levels_entry_quality_enabled) return;
    setConfig((prev: any) => enforceMuIntradayEntryQuality(prev, MU_TICKER));
  }, [
    config.ticker,
    config.intraday_levels_enabled,
    config.intraday_levels_entry_quality_enabled,
    setConfig,
  ]);

  const buildPrewarmPlan = useCallback(() => {
    return buildPrewarmPlanForConfig({
      config,
      availableData,
      autoPrewarmTickers: AUTO_PREWARM_TICKERS,
      chunkDays: AUTO_PREWARM_CHUNK_DAYS,
    });
  }, [
    availableData,
    config.date,
    config.date_from,
    config.date_to,
    config.include_extended_hours,
    config.l2_confirm_enabled,
    config.l2_only,
    config.ticker,
  ]);

  const hydrateExecutionConfigFromPositioning = useCallback((payload: any) => {
    setConfig((prev: any) => applyPositioningToRunConfig(prev, payload));
  }, []);

  const {
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
  } = useRunConfigProfiles({
    ticker: config.ticker,
    strategyApiUrl: config.strategy_api_url,
    authToken,
    activeProfileSentinel: ACTIVE_UNIFIED_PROFILE_SENTINEL,
    normalizeProfileRefToken,
    normalizeAosTickerConfig,
    hydrateExecutionConfigFromPositioning,
  });

  const hydrateRunConfigFromUnifiedProfile = useCallback(
    (profile: any) => {
      const sections = resolveUnifiedProfileSections(profile);
      if (!sections) return;

      if (Object.keys(sections.executionPositioning).length) {
        hydrateExecutionConfigFromPositioning({ positioning: sections.executionPositioning });
      }

      setConfig((prev: any) =>
        applyUnifiedProfileToRunConfig({
          prev,
          strategyProfile: sections.strategyProfile,
          strategyRuntimeOverrides: sections.strategyRuntimeOverrides,
          normalizeStrategySelectionMode,
          parseMaxActiveStrategies,
        }),
      );
    },
    [
      hydrateExecutionConfigFromPositioning,
      normalizeStrategySelectionMode,
      parseMaxActiveStrategies,
    ],
  );

  const { unifiedProfileSwitching, handleUnifiedProfileSelectionChange } =
    useRunConfigUnifiedProfileSelection({
      showProfileControls,
      ticker: config.ticker,
      activeProfileSentinel: ACTIVE_UNIFIED_PROFILE_SENTINEL,
      unifiedProfiles,
      fetchUnifiedProfiles,
      setSelectedUnifiedProfileId,
      reloadAosAndProfiles,
      applyUnifiedProfile,
      setActiveUnifiedProfileId,
      hydrateRunConfigFromUnifiedProfile,
      setError,
    });

  useEffect(() => {
    if (initialTickerSyncRef.current) return;
    const ticker = String(config.ticker || "").trim().toUpperCase();
    if (!ticker || typeof onTickerChange !== "function") return;
    initialTickerSyncRef.current = true;
    onTickerChange(ticker);
  }, [config.ticker, onTickerChange]);

  useRunConfigDraftPersistence({
    authToken,
    ticker: config.ticker,
    config,
    setConfig,
    selectedUnifiedProfileId,
    setSelectedUnifiedProfileId,
    unifiedProfilesLoading,
    unifiedProfilesResolved,
    unifiedProfiles,
    persistedRunConfigDraftRef,
  });

  const {
    checkpointCatalog,
    checkpointLoading,
    checkpointSaving,
    checkpointMessage,
    checkpointApiUnavailable,
    formatCheckpointLabel,
    fetchCheckpoints,
    handleSaveCheckpointNow,
  } = useRunConfigCheckpoints({
    strategyApiBase,
    selectedStartMode,
    resumeWarmStartModeValue: START_MODE_RESUME_WARM_START,
    config,
    setConfig,
  });

  useExecutionConfigBus(config, setConfig);
  const { prewarmStatus, setPrewarmStatus, triggerPrewarmRefresh } = useRunConfigPrewarm({
    buildPrewarmPlan,
    formatPrewarmReadyMessage,
    chunkMaxRetries: AUTO_PREWARM_CHUNK_MAX_RETRIES,
    retryBaseMs: AUTO_PREWARM_RETRY_BASE_MS,
  });

  const handleChange = (field: string, value: any) => {
    setConfig((prev: any) => {
      if (field === "stop_loss_mode") {
        const nextStopLossMode = normalizeStopLossMode(value, prev.stop_loss_mode);
        return {
          ...prev,
          stop_loss_mode: nextStopLossMode,
          fixed_stop_loss_pct: resolveFixedStopLossPct(nextStopLossMode, prev.fixed_stop_loss_pct),
        };
      }
      return { ...prev, [field]: value };
    });
  };
  const {
    handleMomentumSleeveChange,
    handleAddMomentumSleeve,
    handleRemoveMomentumSleeve,
  } = useMomentumSleeves(setConfig);

  const { hydrateConfigFromAttachedRun, markHydratedAttachedRunKey } = useAttachedRunHydration({
    activeRunKey,
    activeRunState,
    runningRunOptions,
    effectiveExecutionConfig,
    currentTicker: config.ticker,
    onTickerChange,
    setConfig,
    setSelectedUnifiedProfileId,
    resolveAttachedRunDates,
    normalizeProfileRefToken,
    parseRunKeyIdentity,
  });

  const handleFlushRunCache = async () => {
    setCacheFlushLoading(true);
    setError(null);
    setCacheFlushMessage(null);
    try {
      const resp = await fetch("/api/run/cache/flush?include_disk=true", { method: "POST" });
      const payload = await resp.json().catch(() => ({}));
      if (!resp.ok) {
        throw new Error(payload?.detail || `HTTP ${resp.status}`);
      }
      const beforeMem = Number(payload?.before?.memory?.base_bars_entries || 0);
      const afterMem = Number(payload?.after?.memory?.base_bars_entries || 0);
      setCacheFlushMessage(`Run cache flushed (memory bars ${beforeMem} -> ${afterMem}).`);
      triggerPrewarmRefresh();
    } catch (err: any) {
      setError(`Cache flush failed: ${err.message}`);
    } finally {
      setCacheFlushLoading(false);
    }
  };

  const {
    dateRange,
    handleDateFromChange,
    handleDateToChange,
    handleTickerChange,
    handleApplyMuReproPreset,
    handleApplyMuScalpPreset,
  } = useRunConfigFormHandlers({
    config,
    setConfig,
    availableData,
    onTickerChange,
    setSelectedUnifiedProfileId,
    muReproProfileId: MU_REPRO_PROFILE_ID,
    muScalpProfileId: MU_SCALP_PROFILE_ID,
  });

  const handleReloadAosAndProfiles = useCallback(async () => {
    await reloadAosAndProfiles();
  }, [reloadAosAndProfiles]);

  const handleKillSelectedRun = useCallback(async () => {
    const targetRunKey = String(activeRunKey || "").trim();
    if (!targetRunKey) {
      setError("Select running run first.");
      return;
    }
    if (typeof onKillRun !== "function") {
      setError("Kill action is unavailable.");
      return;
    }

    setKillRunLoading(true);
    setError(null);
    setCacheFlushMessage(null);
    try {
      await onKillRun(targetRunKey);
    } catch (err: any) {
      setError(String(err?.message || "Failed to kill run."));
    } finally {
      setKillRunLoading(false);
    }
  }, [activeRunKey, onKillRun]);

  const momentumSleeves = Array.isArray(config.momentum_sleeves) ? config.momentum_sleeves : [];
  const effectiveSnapshot = useRunConfigEffectiveSnapshot({
    config,
    effectiveExecutionConfig,
    aosTickerConfig,
    selectedUnifiedProfileId,
    activeUnifiedProfileId,
    activeProfileSentinel: ACTIVE_UNIFIED_PROFILE_SENTINEL,
    normalizeStrategySelectionMode,
    parseMaxActiveStrategies,
  });

  const activeStrategySelectionMode = effectiveSnapshot.activeStrategySelectionMode;
  const activeMaxActiveStrategies = effectiveSnapshot.activeMaxActiveStrategies;

  const handleSubmit = useRunConfigStartHandler({
    config,
    setConfig,
    onStart,
    setLoading,
    setStartTiming,
    setError,
    setCacheFlushMessage,
    setPrewarmStatus,
    selectedUnifiedProfileId,
    applyUnifiedProfile,
    activeUnifiedProfileId,
    setActiveUnifiedProfileId,
    fetchTickerAosConfig,
    fetchUnifiedProfiles,
    activeStrategySelectionMode,
    activeMaxActiveStrategies,
    activeRunOptions: activeRuns,
  });
  
  return {
    config,
    handleChange,
    loading,
    error,
    killRunLoading,
    cacheFlushLoading,
    cacheFlushMessage,
    startTiming,
    loadingElapsedSec,
    availableData,
    availableDataError,
    runningRunOptions,
    selectedStartMode,
    startModeRuntime,
    selectedStartModeOption,
    showDateRangeControls,
    showProfileControls,
    showStartControls,
    triggerPrewarmRefresh,
    aosLoading,
    unifiedProfilesLoading,
    unifiedProfiles,
    activeUnifiedProfileId,
    selectedUnifiedProfileId,
    handleUnifiedProfileSelectionChange,
    unifiedProfileSwitching,
    checkpointCatalog,
    checkpointLoading,
    checkpointSaving,
    checkpointMessage,
    formatCheckpointLabel,
    handleSaveCheckpointNow,
    fetchCheckpoints,
    prewarmStatus,
    momentumSleeves,
    handleMomentumSleeveChange,
    handleAddMomentumSleeve,
    handleRemoveMomentumSleeve,
    hydrateConfigFromAttachedRun,
    markHydratedAttachedRunKey,
    handleFlushRunCache,
    dateRange,
    handleDateFromChange,
    handleDateToChange,
    handleTickerChange,
    handleReloadAosAndProfiles,
    handleKillSelectedRun,
    effectiveSnapshot,
    handleSubmit,
  };
}
