import type { EffectiveSnapshotConfigContext } from "./types";

export const buildActiveIntradayLevelsSnapshot = ({
  config,
  effectiveConfig,
}: EffectiveSnapshotConfigContext) => {
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

  return {
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
  };
};
