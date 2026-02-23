import { useMemo } from "react";

const START_MODE_STANDARD = "standard";
const START_MODE_FAST_RESTART = "fast_restart";
const START_MODE_RESUME_WARM_START = "resume_warm_start";
const START_MODE_DAY_ISOLATED_AUDIT = "day_isolated_audit";
const START_MODE_VALUES = new Set([
  START_MODE_STANDARD,
  START_MODE_FAST_RESTART,
  START_MODE_RESUME_WARM_START,
  START_MODE_DAY_ISOLATED_AUDIT,
]);
const START_MODE_LABELS: Record<string, string> = {
  [START_MODE_STANDARD]: "Standard",
  [START_MODE_FAST_RESTART]: "Fast Restart",
  [START_MODE_RESUME_WARM_START]: "Resume (Warm Start)",
  [START_MODE_DAY_ISOLATED_AUDIT]: "Day-Isolated Audit",
};

const normalizeStartMode = (value: unknown, fallback: string = START_MODE_FAST_RESTART): string => {
  const normalized = String(value || "").trim().toLowerCase();
  return START_MODE_VALUES.has(normalized) ? normalized : fallback;
};

const deriveRequestedStartMode = (config: Record<string, any>): string => {
  const explicitStartMode = String(config?.start_mode || "").trim();
  if (explicitStartMode) {
    return normalizeStartMode(explicitStartMode, START_MODE_FAST_RESTART);
  }
  if (config?.comparable_mode || config?.cold_start_each_day) {
    return START_MODE_DAY_ISOLATED_AUDIT;
  }
  const checkpointPath = String(config?.checkpoint_path || "").trim();
  if (checkpointPath) {
    return START_MODE_RESUME_WARM_START;
  }
  if (typeof config?.fast_start_session_reset === "boolean") {
    return config.fast_start_session_reset ? START_MODE_FAST_RESTART : START_MODE_STANDARD;
  }
  return START_MODE_FAST_RESTART;
};

const deriveEffectiveStartMode = (
  effectiveConfig: Record<string, any>,
  requestedStartMode: string,
): string => {
  const comparableMode = Boolean(effectiveConfig?.comparable_mode);
  const coldStartEachDay = Boolean(effectiveConfig?.cold_start_each_day);
  const checkpointPath = String(effectiveConfig?.checkpoint_path || "").trim();
  const resetScope = String(effectiveConfig?.orchestrator_reset_scope || "").trim().toLowerCase();

  if (comparableMode || coldStartEachDay) {
    return START_MODE_DAY_ISOLATED_AUDIT;
  }
  if (resetScope === "session") {
    return checkpointPath ? START_MODE_RESUME_WARM_START : START_MODE_FAST_RESTART;
  }
  if (resetScope === "all") {
    return START_MODE_STANDARD;
  }
  return normalizeStartMode(requestedStartMode, START_MODE_FAST_RESTART);
};

type UseRunConfigEffectiveSnapshotArgs = {
  config: Record<string, any>;
  effectiveExecutionConfig: Record<string, any> | null;
  aosTickerConfig: Record<string, any>;
  selectedUnifiedProfileId: string;
  activeUnifiedProfileId: string;
  activeProfileSentinel: string;
  normalizeStrategySelectionMode: (value: unknown) => string;
  parseMaxActiveStrategies: (value: unknown, fallback?: number) => number;
};

export const useRunConfigEffectiveSnapshot = ({
  config,
  effectiveExecutionConfig,
  aosTickerConfig,
  selectedUnifiedProfileId,
  activeUnifiedProfileId,
  activeProfileSentinel,
  normalizeStrategySelectionMode,
  parseMaxActiveStrategies,
}: UseRunConfigEffectiveSnapshotArgs) =>
  useMemo(() => {
    const effectiveConfig: Record<string, any> =
      effectiveExecutionConfig && typeof effectiveExecutionConfig === "object"
        ? (effectiveExecutionConfig as Record<string, any>)
        : {};
    const hasEffectiveConfig = !!effectiveExecutionConfig;
    const activeRiskPerTradePct = Number(
      effectiveConfig.risk_per_trade_pct ?? config.risk_per_trade_pct ?? 0,
    );
    const activeMaxPositionNotionalPct = Number(
      effectiveConfig.max_position_notional_pct ?? config.max_position_notional_pct ?? 0,
    );
    const activeMaxFillParticipationRate = Number(
      effectiveConfig.max_fill_participation_rate ?? config.max_fill_participation_rate ?? 0,
    );
    const activeMinFillRatio = Number(effectiveConfig.min_fill_ratio ?? config.min_fill_ratio ?? 0);
    const activeTimeExitBars = Number(effectiveConfig.time_exit_bars ?? config.time_exit_bars ?? 0);
    const activeAdverseFlowEnabled = Boolean(
      effectiveConfig.adverse_flow_exit_enabled ?? config.adverse_flow_exit_enabled,
    );
    const activeAdverseFlowThreshold = Number(
      effectiveConfig.adverse_flow_threshold ?? config.adverse_flow_threshold ?? 0,
    );
    const activeAdverseFlowMinHoldBars = Number(
      effectiveConfig.adverse_flow_min_hold_bars ?? config.adverse_flow_min_hold_bars ?? 0,
    );
    const activeStopLossMode = String(effectiveConfig.stop_loss_mode ?? config.stop_loss_mode ?? "strategy");
    const activeFixedStopLossPct = Number(
      effectiveConfig.fixed_stop_loss_pct ?? config.fixed_stop_loss_pct ?? 0,
    );
    const activeTrailingActivationPct = Number(
      effectiveConfig.trailing_activation_pct ?? config.trailing_activation_pct ?? 0,
    );
    const activeTrailingStopPct = Number(effectiveConfig.trailing_stop_pct ?? config.trailing_stop_pct ?? 0);
    const activeGlobalExitRrRatio = Number(
      effectiveConfig.global_exit_rr_ratio ?? config.global_exit_rr_ratio ?? 0,
    );
    const activeGlobalRiskAtrStopMultiplier = Number(
      effectiveConfig.global_risk_atr_stop_multiplier ?? config.global_risk_atr_stop_multiplier ?? 0,
    );
    const activeGlobalRiskVolumeStopPct = Number(
      effectiveConfig.global_risk_volume_stop_pct ?? config.global_risk_volume_stop_pct ?? 0,
    );
    const activeGlobalRiskMinStopLossPct = Number(
      effectiveConfig.global_risk_min_stop_loss_pct ?? config.global_risk_min_stop_loss_pct ?? 0,
    );
    const activeBreakEvenBufferPct = Number(
      effectiveConfig.break_even_buffer_pct ?? config.break_even_buffer_pct ?? 0,
    );
    const activeBreakEvenMinHoldBars = Number(
      effectiveConfig.break_even_min_hold_bars ?? config.break_even_min_hold_bars ?? 0,
    );
    const activeTrailingInChoppy = Boolean(
      effectiveConfig.trailing_enabled_in_choppy ?? config.trailing_enabled_in_choppy,
    );
    const requestedStartMode = deriveRequestedStartMode(config);
    const activeStartMode = hasEffectiveConfig
      ? deriveEffectiveStartMode(effectiveConfig, requestedStartMode)
      : requestedStartMode;
    const activeStartModeLabel = START_MODE_LABELS[activeStartMode] || START_MODE_LABELS[START_MODE_FAST_RESTART];
    const activeColdStartEachDay = Boolean(
      effectiveConfig.cold_start_each_day ?? (activeStartMode === START_MODE_DAY_ISOLATED_AUDIT),
    );
    const activeComparableMode = Boolean(
      effectiveConfig.comparable_mode ?? (activeStartMode === START_MODE_DAY_ISOLATED_AUDIT),
    );
    const activeAosOptimizationsOnStart = Boolean(
      effectiveConfig.apply_aos_optimizations_on_start ?? config.apply_aos_optimizations_on_start,
    );
    const activeOrchestratorResetScope = String(
      effectiveConfig.orchestrator_reset_scope ||
        (activeStartMode === START_MODE_STANDARD || activeStartMode === START_MODE_DAY_ISOLATED_AUDIT
          ? "all"
          : "session"),
    ).toLowerCase();
    const requestedStrategySelectionMode = String(config?.strategy_selection_mode || "").trim();
    const activeStrategySelectionMode = normalizeStrategySelectionMode(
      requestedStrategySelectionMode ||
        aosTickerConfig?.strategy_selection_mode ||
        effectiveConfig.strategy_selection_mode ||
        "all_enabled",
    );
    const requestedMaxActiveStrategies = config?.max_active_strategies;
    const activeMaxActiveStrategies = parseMaxActiveStrategies(
      requestedMaxActiveStrategies ??
        aosTickerConfig?.max_active_strategies ??
        effectiveConfig.max_active_strategies ??
        20,
      20,
    );
    const activeIntradayLevelsEnabled = Boolean(
      effectiveConfig.intraday_levels_enabled ?? config.intraday_levels_enabled,
    );
    const activeIntradayLevelsSwingLeftBars = Math.max(
      1,
      Math.trunc(
        Number(
          effectiveConfig.intraday_levels_swing_left_bars ?? config.intraday_levels_swing_left_bars ?? 2,
        ),
      ),
    );
    const activeIntradayLevelsSwingRightBars = Math.max(
      1,
      Math.trunc(
        Number(
          effectiveConfig.intraday_levels_swing_right_bars ??
            config.intraday_levels_swing_right_bars ??
            2,
        ),
      ),
    );
    const activeIntradayLevelsTestTolerancePct = Math.max(
      0,
      Number(
        effectiveConfig.intraday_levels_test_tolerance_pct ??
          config.intraday_levels_test_tolerance_pct ??
          0.08,
      ),
    );
    const activeIntradayLevelsBreakTolerancePct = Math.max(
      0,
      Number(
        effectiveConfig.intraday_levels_break_tolerance_pct ??
          config.intraday_levels_break_tolerance_pct ??
          0.05,
      ),
    );
    const activeIntradayLevelsBreakoutVolumeLookback = Math.max(
      2,
      Math.trunc(
        Number(
          effectiveConfig.intraday_levels_breakout_volume_lookback ??
            config.intraday_levels_breakout_volume_lookback ??
            20,
        ),
      ),
    );
    const activeIntradayLevelsBreakoutVolumeMultiplier = Math.max(
      1,
      Number(
        effectiveConfig.intraday_levels_breakout_volume_multiplier ??
          config.intraday_levels_breakout_volume_multiplier ??
          1.2,
      ),
    );
    const activeIntradayLevelsVolumeProfileBinSizePct = Math.max(
      0.01,
      Number(
        effectiveConfig.intraday_levels_volume_profile_bin_size_pct ??
          config.intraday_levels_volume_profile_bin_size_pct ??
          0.05,
      ),
    );
    const activeIntradayLevelsValueAreaPct = Math.min(
      0.95,
      Math.max(
        0.5,
        Number(
          effectiveConfig.intraday_levels_value_area_pct ??
            config.intraday_levels_value_area_pct ??
            0.7,
        ),
      ),
    );
    const activeIntradayLevelsEntryQualityEnabled = Boolean(
      effectiveConfig.intraday_levels_entry_quality_enabled ??
        config.intraday_levels_entry_quality_enabled ??
        true,
    );
    const activeIntradayLevelsMinLevelsForContext = Math.max(
      1,
      Math.trunc(
        Number(
          effectiveConfig.intraday_levels_min_levels_for_context ??
            config.intraday_levels_min_levels_for_context ??
            2,
        ),
      ),
    );
    const activeIntradayLevelsEntryTolerancePct = Math.max(
      0.01,
      Number(
        effectiveConfig.intraday_levels_entry_tolerance_pct ??
          config.intraday_levels_entry_tolerance_pct ??
          0.1,
      ),
    );
    const activeIntradayLevelsBreakCooldownBars = Math.max(
      1,
      Math.trunc(
        Number(
          effectiveConfig.intraday_levels_break_cooldown_bars ??
            config.intraday_levels_break_cooldown_bars ??
            6,
        ),
      ),
    );
    const activeIntradayLevelsRotationMaxTests = Math.max(
      1,
      Math.trunc(
        Number(
          effectiveConfig.intraday_levels_rotation_max_tests ??
            config.intraday_levels_rotation_max_tests ??
            2,
        ),
      ),
    );
    const activeIntradayLevelsRotationVolumeMaxRatio = Math.min(
      2.0,
      Math.max(
        0.1,
        Number(
          effectiveConfig.intraday_levels_rotation_volume_max_ratio ??
            config.intraday_levels_rotation_volume_max_ratio ??
            0.95,
        ),
      ),
    );
    const activeIntradayLevelsRecentBounceLookbackBars = Math.max(
      1,
      Math.trunc(
        Number(
          effectiveConfig.intraday_levels_recent_bounce_lookback_bars ??
            config.intraday_levels_recent_bounce_lookback_bars ??
            6,
        ),
      ),
    );
    const activeIntradayLevelsRequireRecentBounceForMeanReversion = Boolean(
      effectiveConfig.intraday_levels_require_recent_bounce_for_mean_reversion ??
        config.intraday_levels_require_recent_bounce_for_mean_reversion ??
        true,
    );
    const activeIntradayLevelsMomentumBreakMaxAgeBars = Math.max(
      1,
      Math.trunc(
        Number(
          effectiveConfig.intraday_levels_momentum_break_max_age_bars ??
            config.intraday_levels_momentum_break_max_age_bars ??
            3,
        ),
      ),
    );
    const activeIntradayLevelsMomentumMinRoomPct = Math.max(
      0.01,
      Number(
        effectiveConfig.intraday_levels_momentum_min_room_pct ??
          config.intraday_levels_momentum_min_room_pct ??
          0.3,
      ),
    );
    const activeIntradayLevelsMomentumMinBrokenRatio = Math.min(
      1.0,
      Math.max(
        0.0,
        Number(
          effectiveConfig.intraday_levels_momentum_min_broken_ratio ??
            config.intraday_levels_momentum_min_broken_ratio ??
          0.3,
        ),
      ),
    );
    const activeIntradayLevelsMinConfluenceScore = Math.max(
      1,
      Math.trunc(
        Number(
          effectiveConfig.intraday_levels_min_confluence_score ??
            config.intraday_levels_min_confluence_score ??
            2,
        ),
      ),
    );
    const activeIntradayLevelsMemoryEnabled = Boolean(
      effectiveConfig.intraday_levels_memory_enabled ??
        config.intraday_levels_memory_enabled ??
        true,
    );
    const activeIntradayLevelsMemoryMinTests = Math.max(
      1,
      Math.trunc(
        Number(
          effectiveConfig.intraday_levels_memory_min_tests ??
            config.intraday_levels_memory_min_tests ??
            2,
        ),
      ),
    );
    const activeIntradayLevelsMemoryMaxAgeDays = Math.max(
      1,
      Math.trunc(
        Number(
          effectiveConfig.intraday_levels_memory_max_age_days ??
            config.intraday_levels_memory_max_age_days ??
            5,
        ),
      ),
    );
    const activeIntradayLevelsMemoryDecayAfterDays = Math.max(
      1,
      Math.trunc(
        Number(
          effectiveConfig.intraday_levels_memory_decay_after_days ??
            config.intraday_levels_memory_decay_after_days ??
            2,
        ),
      ),
    );
    const activeIntradayLevelsMemoryDecayWeight = Math.min(
      1.0,
      Math.max(
        0.1,
        Number(
          effectiveConfig.intraday_levels_memory_decay_weight ??
            config.intraday_levels_memory_decay_weight ??
            0.5,
        ),
      ),
    );
    const activeIntradayLevelsMemoryMaxLevels = Math.max(
      1,
      Math.trunc(
        Number(
          effectiveConfig.intraday_levels_memory_max_levels ??
            config.intraday_levels_memory_max_levels ??
            12,
        ),
      ),
    );
    const activeIntradayLevelsOpeningRangeEnabled = Boolean(
      effectiveConfig.intraday_levels_opening_range_enabled ??
        config.intraday_levels_opening_range_enabled ??
        true,
    );
    const activeIntradayLevelsOpeningRangeMinutes = Math.max(
      5,
      Math.trunc(
        Number(
          effectiveConfig.intraday_levels_opening_range_minutes ??
            config.intraday_levels_opening_range_minutes ??
            30,
        ),
      ),
    );
    const activeIntradayLevelsOpeningRangeBreakTolerancePct = Math.max(
      0.01,
      Number(
        effectiveConfig.intraday_levels_opening_range_break_tolerance_pct ??
          config.intraday_levels_opening_range_break_tolerance_pct ??
          0.05,
      ),
    );
    const activeIntradayLevelsPocMigrationEnabled = Boolean(
      effectiveConfig.intraday_levels_poc_migration_enabled ??
        config.intraday_levels_poc_migration_enabled ??
        true,
    );
    const activeIntradayLevelsPocMigrationIntervalBars = Math.max(
      1,
      Math.trunc(
        Number(
          effectiveConfig.intraday_levels_poc_migration_interval_bars ??
            config.intraday_levels_poc_migration_interval_bars ??
            30,
        ),
      ),
    );
    const activeIntradayLevelsPocMigrationTrendThresholdPct = Math.max(
      0.01,
      Number(
        effectiveConfig.intraday_levels_poc_migration_trend_threshold_pct ??
          config.intraday_levels_poc_migration_trend_threshold_pct ??
          0.2,
      ),
    );
    const activeIntradayLevelsPocMigrationRangeThresholdPct = Math.max(
      0.01,
      Number(
        effectiveConfig.intraday_levels_poc_migration_range_threshold_pct ??
          config.intraday_levels_poc_migration_range_threshold_pct ??
          0.1,
      ),
    );
    const activeIntradayLevelsCompositeProfileEnabled = Boolean(
      effectiveConfig.intraday_levels_composite_profile_enabled ??
        config.intraday_levels_composite_profile_enabled ??
        true,
    );
    const activeIntradayLevelsCompositeProfileDays = Math.max(
      1,
      Math.trunc(
        Number(
          effectiveConfig.intraday_levels_composite_profile_days ??
            config.intraday_levels_composite_profile_days ??
            3,
        ),
      ),
    );
    const activeIntradayLevelsCompositeProfileCurrentDayWeight = Math.max(
      0.1,
      Number(
        effectiveConfig.intraday_levels_composite_profile_current_day_weight ??
          config.intraday_levels_composite_profile_current_day_weight ??
          1.0,
      ),
    );
    const activeIntradayLevelsSpikeDetectionEnabled = Boolean(
      effectiveConfig.intraday_levels_spike_detection_enabled ??
        config.intraday_levels_spike_detection_enabled ??
        true,
    );
    const activeIntradayLevelsSpikeMinWickRatio = Math.min(
      0.95,
      Math.max(
        0.4,
        Number(
          effectiveConfig.intraday_levels_spike_min_wick_ratio ??
            config.intraday_levels_spike_min_wick_ratio ??
            0.6,
        ),
      ),
    );
    const activeIntradayLevelsPriorDayAnchorsEnabled = Boolean(
      effectiveConfig.intraday_levels_prior_day_anchors_enabled ??
        config.intraday_levels_prior_day_anchors_enabled ??
        true,
    );
    const activeIntradayLevelsGapAnalysisEnabled = Boolean(
      effectiveConfig.intraday_levels_gap_analysis_enabled ??
        config.intraday_levels_gap_analysis_enabled ??
        true,
    );
    const activeIntradayLevelsGapMinPct = Math.max(
      0,
      Number(
        effectiveConfig.intraday_levels_gap_min_pct ??
          config.intraday_levels_gap_min_pct ??
          0.3,
      ),
    );
    const activeIntradayLevelsGapMomentumThresholdPct = Math.max(
      0.1,
      Number(
        effectiveConfig.intraday_levels_gap_momentum_threshold_pct ??
          config.intraday_levels_gap_momentum_threshold_pct ??
          2.0,
      ),
    );
    const activeIntradayLevelsRvolFilterEnabled = Boolean(
      effectiveConfig.intraday_levels_rvol_filter_enabled ??
        config.intraday_levels_rvol_filter_enabled ??
        true,
    );
    const activeIntradayLevelsRvolLookbackBars = Math.max(
      5,
      Math.trunc(
        Number(
          effectiveConfig.intraday_levels_rvol_lookback_bars ??
            config.intraday_levels_rvol_lookback_bars ??
            20,
        ),
      ),
    );
    const activeIntradayLevelsRvolMinThreshold = Math.max(
      0,
      Number(
        effectiveConfig.intraday_levels_rvol_min_threshold ??
          config.intraday_levels_rvol_min_threshold ??
          0.8,
      ),
    );
    const activeIntradayLevelsRvolStrongThreshold = Math.max(
      0.1,
      Number(
        effectiveConfig.intraday_levels_rvol_strong_threshold ??
          config.intraday_levels_rvol_strong_threshold ??
          1.5,
      ),
    );
    const activeIntradayLevelsAdaptiveWindowEnabled = Boolean(
      effectiveConfig.intraday_levels_adaptive_window_enabled ??
        config.intraday_levels_adaptive_window_enabled ??
        true,
    );
    const activeIntradayLevelsAdaptiveWindowMinBars = Math.max(
      1,
      Math.trunc(
        Number(
          effectiveConfig.intraday_levels_adaptive_window_min_bars ??
            config.intraday_levels_adaptive_window_min_bars ??
            6,
        ),
      ),
    );
    const activeIntradayLevelsAdaptiveWindowRvolThreshold = Math.max(
      0,
      Number(
        effectiveConfig.intraday_levels_adaptive_window_rvol_threshold ??
          config.intraday_levels_adaptive_window_rvol_threshold ??
          1.0,
      ),
    );
    const activeIntradayLevelsAdaptiveWindowAtrRatioMax = Math.max(
      0.1,
      Number(
        effectiveConfig.intraday_levels_adaptive_window_atr_ratio_max ??
          config.intraday_levels_adaptive_window_atr_ratio_max ??
          1.5,
      ),
    );
    const activeIntradayLevelsMicroConfirmationEnabled = Boolean(
      effectiveConfig.intraday_levels_micro_confirmation_enabled ??
        config.intraday_levels_micro_confirmation_enabled ??
        false,
    );
    const activeIntradayLevelsMicroConfirmationBars = Math.max(
      1,
      Math.trunc(
        Number(
          effectiveConfig.intraday_levels_micro_confirmation_bars ??
            config.intraday_levels_micro_confirmation_bars ??
            2,
        ),
      ),
    );
    const activeIntradayLevelsConfluenceSizingEnabled = Boolean(
      effectiveConfig.intraday_levels_confluence_sizing_enabled ??
        config.intraday_levels_confluence_sizing_enabled ??
        false,
    );
    const activeContextAwareRiskEnabled = Boolean(
      effectiveConfig.context_aware_risk_enabled ?? config.context_aware_risk_enabled ?? false,
    );
    const activeContextRiskSlBufferPct = Math.max(
      0,
      Number(effectiveConfig.context_risk_sl_buffer_pct ?? config.context_risk_sl_buffer_pct ?? 0.03),
    );
    const activeContextRiskMinRoomPct = Math.max(
      0,
      Number(effectiveConfig.context_risk_min_room_pct ?? config.context_risk_min_room_pct ?? 0.15),
    );
    const activeContextRiskMinEffectiveRr = Math.max(
      0,
      Number(
        effectiveConfig.context_risk_min_effective_rr ?? config.context_risk_min_effective_rr ?? 0.8,
      ),
    );
    const activeContextRiskTrailingTightenZone = Math.max(
      0,
      Math.min(
        1,
        Number(
          effectiveConfig.context_risk_trailing_tighten_zone ??
            config.context_risk_trailing_tighten_zone ??
            0.2,
        ),
      ),
    );
    const activeContextRiskTrailingTightenFactor = Math.max(
      0,
      Math.min(
        1,
        Number(
          effectiveConfig.context_risk_trailing_tighten_factor ??
            config.context_risk_trailing_tighten_factor ??
            0.5,
        ),
      ),
    );
    const activeContextRiskLevelTrailEnabled = Boolean(
      effectiveConfig.context_risk_level_trail_enabled ??
        config.context_risk_level_trail_enabled ??
        true,
    );
    const activeContextRiskMaxAnchorSearchPct = Math.max(
      0.1,
      Number(
        effectiveConfig.context_risk_max_anchor_search_pct ??
          config.context_risk_max_anchor_search_pct ??
          1.5,
      ),
    );
    const activeContextRiskMinLevelTestsForSl = Math.max(
      0,
      Math.trunc(
        Number(
          effectiveConfig.context_risk_min_level_tests_for_sl ??
            config.context_risk_min_level_tests_for_sl ??
            1,
        ),
      ),
    );
    const activeMomentumDiversificationRaw =
      effectiveConfig?.momentum_diversification &&
      typeof effectiveConfig.momentum_diversification === "object" &&
      !Array.isArray(effectiveConfig.momentum_diversification)
        ? effectiveConfig.momentum_diversification
        : {};
    const activeMomentumDiversificationApplied = Boolean(effectiveConfig?.momentum_diversification_applied);
    const activeMomentumDiversificationSource = String(
      effectiveConfig?.momentum_diversification_source || "none",
    );
    const effectiveUnifiedProfileIdFromRun = String(
      effectiveConfig?.unified_profile_id ||
        effectiveConfig?.unified_profile?.active_profile_id ||
        effectiveConfig?.unified_profile?.profile_id ||
        "",
    ).trim();
    const requestedUnifiedProfileId =
      selectedUnifiedProfileId === activeProfileSentinel
        ? ""
        : String(selectedUnifiedProfileId || "").trim();
    const effectiveUnifiedProfileId =
      effectiveUnifiedProfileIdFromRun ||
      requestedUnifiedProfileId ||
      String(activeUnifiedProfileId || "").trim();

    return {
      effectiveConfig,
      hasEffectiveConfig,
      activeRiskPerTradePct,
      activeMaxPositionNotionalPct,
      activeMaxFillParticipationRate,
      activeMinFillRatio,
      activeTimeExitBars,
      activeAdverseFlowEnabled,
      activeAdverseFlowThreshold,
      activeAdverseFlowMinHoldBars,
      activeStopLossMode,
      activeFixedStopLossPct,
      activeTrailingActivationPct,
      activeTrailingStopPct,
      activeGlobalExitRrRatio,
      activeGlobalRiskAtrStopMultiplier,
      activeGlobalRiskVolumeStopPct,
      activeGlobalRiskMinStopLossPct,
      activeBreakEvenBufferPct,
      activeBreakEvenMinHoldBars,
      activeTrailingInChoppy,
      requestedStartMode,
      activeStartMode,
      activeStartModeLabel,
      activeColdStartEachDay,
      activeComparableMode,
      activeAosOptimizationsOnStart,
      activeOrchestratorResetScope,
      activeStrategySelectionMode,
      activeMaxActiveStrategies,
      activeIntradayLevelsEnabled,
      activeIntradayLevelsSwingLeftBars,
      activeIntradayLevelsSwingRightBars,
      activeIntradayLevelsTestTolerancePct,
      activeIntradayLevelsBreakTolerancePct,
      activeIntradayLevelsBreakoutVolumeLookback,
      activeIntradayLevelsBreakoutVolumeMultiplier,
      activeIntradayLevelsVolumeProfileBinSizePct,
      activeIntradayLevelsValueAreaPct,
      activeIntradayLevelsEntryQualityEnabled,
      activeIntradayLevelsMinLevelsForContext,
      activeIntradayLevelsEntryTolerancePct,
      activeIntradayLevelsBreakCooldownBars,
      activeIntradayLevelsRotationMaxTests,
      activeIntradayLevelsRotationVolumeMaxRatio,
      activeIntradayLevelsRecentBounceLookbackBars,
      activeIntradayLevelsRequireRecentBounceForMeanReversion,
      activeIntradayLevelsMomentumBreakMaxAgeBars,
      activeIntradayLevelsMomentumMinRoomPct,
      activeIntradayLevelsMomentumMinBrokenRatio,
      activeIntradayLevelsMinConfluenceScore,
      activeIntradayLevelsMemoryEnabled,
      activeIntradayLevelsMemoryMinTests,
      activeIntradayLevelsMemoryMaxAgeDays,
      activeIntradayLevelsMemoryDecayAfterDays,
      activeIntradayLevelsMemoryDecayWeight,
      activeIntradayLevelsMemoryMaxLevels,
      activeIntradayLevelsOpeningRangeEnabled,
      activeIntradayLevelsOpeningRangeMinutes,
      activeIntradayLevelsOpeningRangeBreakTolerancePct,
      activeIntradayLevelsPocMigrationEnabled,
      activeIntradayLevelsPocMigrationIntervalBars,
      activeIntradayLevelsPocMigrationTrendThresholdPct,
      activeIntradayLevelsPocMigrationRangeThresholdPct,
      activeIntradayLevelsCompositeProfileEnabled,
      activeIntradayLevelsCompositeProfileDays,
      activeIntradayLevelsCompositeProfileCurrentDayWeight,
      activeIntradayLevelsSpikeDetectionEnabled,
      activeIntradayLevelsSpikeMinWickRatio,
      activeIntradayLevelsPriorDayAnchorsEnabled,
      activeIntradayLevelsGapAnalysisEnabled,
      activeIntradayLevelsGapMinPct,
      activeIntradayLevelsGapMomentumThresholdPct,
      activeIntradayLevelsRvolFilterEnabled,
      activeIntradayLevelsRvolLookbackBars,
      activeIntradayLevelsRvolMinThreshold,
      activeIntradayLevelsRvolStrongThreshold,
      activeIntradayLevelsAdaptiveWindowEnabled,
      activeIntradayLevelsAdaptiveWindowMinBars,
      activeIntradayLevelsAdaptiveWindowRvolThreshold,
      activeIntradayLevelsAdaptiveWindowAtrRatioMax,
      activeIntradayLevelsMicroConfirmationEnabled,
      activeIntradayLevelsMicroConfirmationBars,
      activeIntradayLevelsConfluenceSizingEnabled,
      activeContextAwareRiskEnabled,
      activeContextRiskSlBufferPct,
      activeContextRiskMinRoomPct,
      activeContextRiskMinEffectiveRr,
      activeContextRiskTrailingTightenZone,
      activeContextRiskTrailingTightenFactor,
      activeContextRiskLevelTrailEnabled,
      activeContextRiskMaxAnchorSearchPct,
      activeContextRiskMinLevelTestsForSl,
      activeMomentumDiversificationRaw,
      activeMomentumDiversificationApplied,
      activeMomentumDiversificationSource,
      effectiveUnifiedProfileId,
    };
  }, [
    activeProfileSentinel,
    activeUnifiedProfileId,
    aosTickerConfig,
    config,
    effectiveExecutionConfig,
    normalizeStrategySelectionMode,
    parseMaxActiveStrategies,
    selectedUnifiedProfileId,
  ]);
