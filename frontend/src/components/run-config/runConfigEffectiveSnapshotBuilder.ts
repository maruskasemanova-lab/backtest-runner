import {
  buildActiveContextRiskSnapshot,
  buildActiveIntradayLevelsSnapshot,
  buildActiveMomentumDiversificationSnapshot,
  resolveEffectiveUnifiedProfileId,
} from "./runConfigEffectiveSnapshotSections";

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

export type BuildRunConfigEffectiveSnapshotArgs = {
  config: Record<string, any>;
  effectiveExecutionConfig: Record<string, any> | null;
  aosTickerConfig: Record<string, any>;
  selectedUnifiedProfileId: string;
  activeUnifiedProfileId: string;
  activeProfileSentinel: string;
  normalizeStrategySelectionMode: (value: unknown) => string;
  parseMaxActiveStrategies: (value: unknown, fallback?: number) => number;
};

export const buildRunConfigEffectiveSnapshot = ({
  config,
  effectiveExecutionConfig,
  aosTickerConfig,
  selectedUnifiedProfileId,
  activeUnifiedProfileId,
  activeProfileSentinel,
  normalizeStrategySelectionMode,
  parseMaxActiveStrategies,
}: BuildRunConfigEffectiveSnapshotArgs) => {
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
    const activeIntradayLevelsSnapshot = buildActiveIntradayLevelsSnapshot({
      config,
      effectiveConfig,
    });
    const activeContextRiskSnapshot = buildActiveContextRiskSnapshot({
      config,
      effectiveConfig,
    });
    const activeMomentumDiversificationSnapshot = buildActiveMomentumDiversificationSnapshot({
      effectiveConfig,
    });
    const effectiveUnifiedProfileId = resolveEffectiveUnifiedProfileId({
      effectiveConfig,
      selectedUnifiedProfileId,
      activeUnifiedProfileId,
      activeProfileSentinel,
    });

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
      ...activeIntradayLevelsSnapshot,
      ...activeContextRiskSnapshot,
      ...activeMomentumDiversificationSnapshot,
      effectiveUnifiedProfileId,
    };
};
