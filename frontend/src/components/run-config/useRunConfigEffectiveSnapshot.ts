import { useMemo } from "react";

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
    const activeColdStartEachDay = Boolean(effectiveConfig.cold_start_each_day ?? config.cold_start_each_day);
    const activeComparableMode = Boolean(effectiveConfig.comparable_mode ?? config.comparable_mode);
    const activeAosOptimizationsOnStart = Boolean(
      effectiveConfig.apply_aos_optimizations_on_start ?? config.apply_aos_optimizations_on_start,
    );
    const activeOrchestratorResetScope = String(
      effectiveConfig.orchestrator_reset_scope ||
        (activeComparableMode ? "all" : config.fast_start_session_reset ? "session" : "all"),
    ).toLowerCase();
    const activeStrategySelectionMode = normalizeStrategySelectionMode(
      effectiveConfig.strategy_selection_mode ?? aosTickerConfig?.strategy_selection_mode ?? "adaptive_top_n",
    );
    const activeMaxActiveStrategies = parseMaxActiveStrategies(
      effectiveConfig.max_active_strategies ?? aosTickerConfig?.max_active_strategies ?? 3,
      3,
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
      activeColdStartEachDay,
      activeComparableMode,
      activeAosOptimizationsOnStart,
      activeOrchestratorResetScope,
      activeStrategySelectionMode,
      activeMaxActiveStrategies,
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
