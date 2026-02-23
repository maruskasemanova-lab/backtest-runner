import { useState, useEffect, useCallback, useRef, useMemo } from "react";
import { toFiniteNumber, toBool, normalizeIsoDay } from "../../utils";
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
  buildIsoDayChunks,
  normalizeAosTickerConfig,
  normalizePositioningConfig,
  normalizeStopLossMode,
  resolveFixedStopLossPct,
  resolveTickerCoverageRange,
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
  const runningRunOptions = useMemo(() => {
    const rows = Array.isArray(activeRuns) ? activeRuns : [];
    return rows.filter((row: any) => {
      if (!row || typeof row !== "object") return false;
      const running = !!row.is_running;
      const paused = !!row.is_paused;
      const phase = String(row.phase || "").trim().toUpperCase();
      return running || paused || phase === "INITIALIZED";
    });
  }, [activeRuns]);
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
    setConfig((prev: any) => {
      const prevTicker = String(prev.ticker || "").trim().toUpperCase();
      if (prevTicker !== MU_TICKER) return prev;
      if (!prev.intraday_levels_enabled) return prev;
      if (prev.intraday_levels_entry_quality_enabled) return prev;
      return {
        ...prev,
        intraday_levels_entry_quality_enabled: true,
      };
    });
  }, [
    config.ticker,
    config.intraday_levels_enabled,
    config.intraday_levels_entry_quality_enabled,
    setConfig,
  ]);

  const buildPrewarmPlan = useCallback(() => {
    const ticker = String(config.ticker || "").trim().toUpperCase();
    if (!ticker) return null;
    if (!AUTO_PREWARM_TICKERS.has(ticker)) return null;
    const basePayload = {
      ticker,
      allow_mock_data: false,
      l2_only: !!config.l2_only,
      l2_confirm_enabled: !!config.l2_confirm_enabled,
      include_extended_hours: !!config.include_extended_hours,
      comparable_mode: false,
    };
    const coverage = resolveTickerCoverageRange({
      availableData,
      ticker,
      l2Only: !!config.l2_only,
    });
    const selectedDateFrom = normalizeIsoDay(config.date_from || config.date);
    const selectedDateTo = normalizeIsoDay(config.date_to || config.date_from || config.date);
    const selectedRangeReady = !!selectedDateFrom && !!selectedDateTo && selectedDateFrom <= selectedDateTo;
    const range = coverage.effectiveRange;
    const rangeStart = selectedRangeReady ? selectedDateFrom : normalizeIsoDay(range?.start);
    const rangeEnd = selectedRangeReady ? selectedDateTo : normalizeIsoDay(range?.end);
    const rangeChunks = buildIsoDayChunks(rangeStart, rangeEnd, AUTO_PREWARM_CHUNK_DAYS);

    if (rangeChunks.length > 0) {
      const chunkPayloads = rangeChunks.map((chunk) => ({
        ...basePayload,
        prewarm_scope: "range",
        date: chunk.date_from,
        date_from: chunk.date_from,
        date_to: chunk.date_to,
      }));
      return {
        keyPayload: {
          ...basePayload,
          prewarm_scope: "range",
          date_from: rangeStart,
          date_to: rangeEnd,
          chunk_days: AUTO_PREWARM_CHUNK_DAYS,
        },
        chunkPayloads,
      };
    }

    return {
      keyPayload: {
        ...basePayload,
        prewarm_scope: "ticker",
      },
      chunkPayloads: [
        {
          ...basePayload,
          prewarm_scope: "ticker",
        },
      ],
    };
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
    const positioning = normalizePositioningConfig(payload);
    if (!Object.keys(positioning).length) return;

    setConfig((prev: any) => {
      const nextStopLossMode = normalizeStopLossMode(positioning.stop_loss_mode, prev.stop_loss_mode);
      const nextFixedStopLossPct = resolveFixedStopLossPct(
        nextStopLossMode,
        toFiniteNumber(positioning.fixed_stop_loss_pct, prev.fixed_stop_loss_pct)
      );
      return {
        ...prev,
        risk_per_trade_pct: toFiniteNumber(positioning.risk_per_trade_pct, prev.risk_per_trade_pct),
        max_position_notional_pct: toFiniteNumber(
          positioning.max_position_notional_pct,
          prev.max_position_notional_pct
        ),
        max_fill_participation_rate: toFiniteNumber(
          positioning.max_fill_participation_rate,
          prev.max_fill_participation_rate
        ),
        min_fill_ratio: toFiniteNumber(positioning.min_fill_ratio, prev.min_fill_ratio),
        trailing_stop_pct: Math.max(
          0,
          toFiniteNumber(positioning.trailing_stop_pct, prev.trailing_stop_pct)
        ),
        global_exit_rr_ratio: Math.max(
          0,
          toFiniteNumber(positioning.global_exit_rr_ratio, prev.global_exit_rr_ratio)
        ),
        global_risk_atr_stop_multiplier: Math.max(
          0,
          toFiniteNumber(
            positioning.global_risk_atr_stop_multiplier,
            prev.global_risk_atr_stop_multiplier
          )
        ),
        global_risk_volume_stop_pct: Math.max(
          0,
          toFiniteNumber(positioning.global_risk_volume_stop_pct, prev.global_risk_volume_stop_pct)
        ),
        global_risk_min_stop_loss_pct: Math.max(
          0,
          toFiniteNumber(
            positioning.global_risk_min_stop_loss_pct,
            prev.global_risk_min_stop_loss_pct
          )
        ),
        trailing_activation_pct: toFiniteNumber(
          positioning.trailing_activation_pct,
          prev.trailing_activation_pct
        ),
        break_even_buffer_pct: toFiniteNumber(
          positioning.break_even_buffer_pct,
          prev.break_even_buffer_pct
        ),
        break_even_min_hold_bars: Math.max(
          1,
          Math.trunc(
            toFiniteNumber(positioning.break_even_min_hold_bars, prev.break_even_min_hold_bars)
          )
        ),
        trailing_enabled_in_choppy: toBool(
          positioning.trailing_enabled_in_choppy,
          prev.trailing_enabled_in_choppy
        ),
        time_exit_bars: Math.max(
          1,
          Math.trunc(toFiniteNumber(positioning.time_exit_bars, prev.time_exit_bars))
        ),
        adverse_flow_exit_enabled: toBool(
          positioning.adverse_flow_exit_enabled,
          prev.adverse_flow_exit_enabled
        ),
        adverse_flow_threshold: toFiniteNumber(
          positioning.adverse_flow_threshold,
          prev.adverse_flow_threshold
        ),
        adverse_flow_min_hold_bars: Math.max(
          1,
          Math.trunc(
            toFiniteNumber(positioning.adverse_flow_min_hold_bars, prev.adverse_flow_min_hold_bars)
          )
        ),
        stop_loss_mode: nextStopLossMode,
        fixed_stop_loss_pct: nextFixedStopLossPct,
      };
    });
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
    activeProfileSentinel: ACTIVE_UNIFIED_PROFILE_SENTINEL,
    normalizeProfileRefToken,
    normalizeAosTickerConfig,
    hydrateExecutionConfigFromPositioning,
  });

  const hydrateRunConfigFromUnifiedProfile = useCallback(
    (profile: any) => {
      if (!profile || typeof profile !== "object") return;

      const strategyProfile =
        profile.strategy_profile && typeof profile.strategy_profile === "object"
          ? profile.strategy_profile
          : {};
      const executionProfile =
        profile.execution_profile && typeof profile.execution_profile === "object"
          ? profile.execution_profile
          : {};
      const strategyRuntimeOverrides =
        strategyProfile.runtime_overrides && typeof strategyProfile.runtime_overrides === "object"
          ? strategyProfile.runtime_overrides
          : {};
      const nestedExecutionPositioning = normalizePositioningConfig(executionProfile);
      const executionPositioning =
        Object.keys(nestedExecutionPositioning).length > 0
          ? nestedExecutionPositioning
          : executionProfile;

      if (Object.keys(executionPositioning).length) {
        hydrateExecutionConfigFromPositioning({ positioning: executionPositioning });
      }

      const applyProfileValuesToRunConfig = (next: any, prev: any, source: any) => {
        if (!source || typeof source !== "object" || Array.isArray(source)) return;
        Object.keys(prev).forEach((key) => {
          if (!Object.prototype.hasOwnProperty.call(source, key)) return;
          const incoming = source[key];
          if (incoming === undefined) return;
          const previousValue = prev[key];

          if (typeof previousValue === "boolean") {
            next[key] = toBool(incoming, previousValue);
            return;
          }
          if (typeof previousValue === "number") {
            const parsed = Number(incoming);
            if (Number.isFinite(parsed)) {
              next[key] = parsed;
            }
            return;
          }
          if (typeof previousValue === "string") {
            next[key] = String(incoming);
            return;
          }
          if (Array.isArray(previousValue) && Array.isArray(incoming)) {
            next[key] = [...incoming];
            return;
          }
          if (
            previousValue === null &&
            (typeof incoming === "string" ||
              typeof incoming === "number" ||
              typeof incoming === "boolean" ||
              incoming === null)
          ) {
            next[key] = incoming;
          }
        });
      };

      setConfig((prev: any) => {
        const next = { ...prev };
        applyProfileValuesToRunConfig(next, prev, strategyProfile);
        applyProfileValuesToRunConfig(next, prev, strategyRuntimeOverrides);

        const strategyMode = String(
          strategyRuntimeOverrides.strategy_selection_mode ??
            strategyProfile.strategy_selection_mode ??
            "",
        ).trim();
        if (strategyMode) {
          next.strategy_selection_mode = normalizeStrategySelectionMode(strategyMode);
        }
        const maxActiveStrategiesRaw =
          strategyRuntimeOverrides.max_active_strategies ?? strategyProfile.max_active_strategies;
        if (maxActiveStrategiesRaw !== undefined) {
          next.max_active_strategies = parseMaxActiveStrategies(
            maxActiveStrategiesRaw,
            prev.max_active_strategies,
          );
        }
        const l2 = strategyProfile.l2;
        if (l2 && typeof l2 === "object" && !Array.isArray(l2)) {
          if (l2.min_imbalance !== undefined) {
            next.l2_min_imbalance = Number(l2.min_imbalance);
          }
          if (l2.min_directional_consistency !== undefined) {
            next.l2_min_directional_consistency = Number(l2.min_directional_consistency);
          }
          if (l2.min_signed_aggression !== undefined) {
            next.l2_min_signed_aggression = Number(l2.min_signed_aggression);
          }
          if (l2.lookback_bars !== undefined) {
            next.l2_lookback_bars = Math.max(1, Math.trunc(Number(l2.lookback_bars)));
          }
        }
        return next;
      });
    },
    [hydrateExecutionConfigFromPositioning],
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
