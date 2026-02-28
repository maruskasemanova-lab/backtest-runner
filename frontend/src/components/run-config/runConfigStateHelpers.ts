import { toBool, toFiniteNumber, normalizeIsoDay } from "../../utils";
import {
  buildIsoDayChunks,
  normalizePositioningConfig,
  normalizeStopLossMode,
  resolveFixedStopLossPct,
  resolveTickerCoverageRange,
} from "./runConfigHelpers";

type AnyRecord = Record<string, any>;

type BuildPrewarmPlanArgs = {
  config: AnyRecord;
  availableData: any;
  autoPrewarmTickers: Set<string>;
  chunkDays: number;
};

type ApplyUnifiedProfileArgs = {
  prev: AnyRecord;
  strategyProfile: AnyRecord;
  strategyRuntimeOverrides: AnyRecord;
  normalizeStrategySelectionMode: (value: unknown) => string;
  parseMaxActiveStrategies: (value: unknown, fallback?: number) => number;
};

export const selectRunningRunOptions = (activeRuns: any[]) => {
  const rows = Array.isArray(activeRuns) ? activeRuns : [];
  return rows.filter((row: any) => {
    if (!row || typeof row !== "object") return false;
    const running = !!row.is_running;
    const paused = !!row.is_paused;
    const phase = String(row.phase || "").trim().toUpperCase();
    return running || paused || phase === "INITIALIZED";
  });
};

export const enforceMuIntradayEntryQuality = (prev: AnyRecord, muTicker: string) => {
  const prevTicker = String(prev.ticker || "").trim().toUpperCase();
  if (prevTicker !== muTicker) return prev;
  if (!prev.intraday_levels_enabled) return prev;
  if (prev.intraday_levels_entry_quality_enabled) return prev;
  return {
    ...prev,
    intraday_levels_entry_quality_enabled: true,
  };
};

export const buildPrewarmPlanForConfig = ({
  config,
  availableData,
  autoPrewarmTickers,
  chunkDays,
}: BuildPrewarmPlanArgs) => {
  const ticker = String(config.ticker || "").trim().toUpperCase();
  if (!ticker) return null;
  if (!autoPrewarmTickers.has(ticker)) return null;

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
  const rangeChunks = buildIsoDayChunks(rangeStart, rangeEnd, chunkDays);

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
        chunk_days: chunkDays,
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
};

export const applyPositioningToRunConfig = (prev: AnyRecord, payload: any): AnyRecord => {
  const positioning = normalizePositioningConfig(payload);
  if (!Object.keys(positioning).length) return prev;

  const nextStopLossMode = normalizeStopLossMode(positioning.stop_loss_mode, prev.stop_loss_mode);
  const nextFixedStopLossPct = resolveFixedStopLossPct(
    nextStopLossMode,
    toFiniteNumber(positioning.fixed_stop_loss_pct, prev.fixed_stop_loss_pct),
  );

  return {
    ...prev,
    risk_per_trade_pct: toFiniteNumber(positioning.risk_per_trade_pct, prev.risk_per_trade_pct),
    max_position_notional_pct: toFiniteNumber(
      positioning.max_position_notional_pct,
      prev.max_position_notional_pct,
    ),
    max_fill_participation_rate: toFiniteNumber(
      positioning.max_fill_participation_rate,
      prev.max_fill_participation_rate,
    ),
    min_fill_ratio: toFiniteNumber(positioning.min_fill_ratio, prev.min_fill_ratio),
    trailing_stop_pct: Math.max(0, toFiniteNumber(positioning.trailing_stop_pct, prev.trailing_stop_pct)),
    global_exit_rr_ratio: Math.max(
      0,
      toFiniteNumber(positioning.global_exit_rr_ratio, prev.global_exit_rr_ratio),
    ),
    global_risk_atr_stop_multiplier: Math.max(
      0,
      toFiniteNumber(positioning.global_risk_atr_stop_multiplier, prev.global_risk_atr_stop_multiplier),
    ),
    global_risk_volume_stop_pct: Math.max(
      0,
      toFiniteNumber(positioning.global_risk_volume_stop_pct, prev.global_risk_volume_stop_pct),
    ),
    global_risk_min_stop_loss_pct: Math.max(
      0,
      toFiniteNumber(positioning.global_risk_min_stop_loss_pct, prev.global_risk_min_stop_loss_pct),
    ),
    trailing_activation_pct: toFiniteNumber(
      positioning.trailing_activation_pct,
      prev.trailing_activation_pct,
    ),
    break_even_buffer_pct: toFiniteNumber(positioning.break_even_buffer_pct, prev.break_even_buffer_pct),
    break_even_min_hold_bars: Math.max(
      1,
      Math.trunc(toFiniteNumber(positioning.break_even_min_hold_bars, prev.break_even_min_hold_bars)),
    ),
    trailing_enabled_in_choppy: toBool(positioning.trailing_enabled_in_choppy, prev.trailing_enabled_in_choppy),
    time_exit_bars: Math.max(1, Math.trunc(toFiniteNumber(positioning.time_exit_bars, prev.time_exit_bars))),
    adverse_flow_exit_enabled: toBool(positioning.adverse_flow_exit_enabled, prev.adverse_flow_exit_enabled),
    adverse_flow_threshold: toFiniteNumber(positioning.adverse_flow_threshold, prev.adverse_flow_threshold),
    adverse_flow_min_hold_bars: Math.max(
      1,
      Math.trunc(toFiniteNumber(positioning.adverse_flow_min_hold_bars, prev.adverse_flow_min_hold_bars)),
    ),
    stop_loss_mode: nextStopLossMode,
    fixed_stop_loss_pct: nextFixedStopLossPct,
  };
};

const applyProfileValuesToRunConfig = (next: AnyRecord, prev: AnyRecord, source: any) => {
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

export const resolveUnifiedProfileSections = (profile: any) => {
  if (!profile || typeof profile !== "object") return null;

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
    Object.keys(nestedExecutionPositioning).length > 0 ? nestedExecutionPositioning : executionProfile;

  return {
    strategyProfile,
    strategyRuntimeOverrides,
    executionPositioning,
  };
};

export const applyUnifiedProfileToRunConfig = ({
  prev,
  strategyProfile,
  strategyRuntimeOverrides,
  normalizeStrategySelectionMode,
  parseMaxActiveStrategies,
}: ApplyUnifiedProfileArgs): AnyRecord => {
  const next = { ...prev };
  applyProfileValuesToRunConfig(next, prev, strategyProfile);
  applyProfileValuesToRunConfig(next, prev, strategyRuntimeOverrides);

  const strategyMode = String(
    strategyRuntimeOverrides.strategy_selection_mode ?? strategyProfile.strategy_selection_mode ?? "",
  ).trim();
  if (strategyMode) {
    next.strategy_selection_mode = normalizeStrategySelectionMode(strategyMode);
  }

  const maxActiveStrategiesRaw =
    strategyRuntimeOverrides.max_active_strategies ?? strategyProfile.max_active_strategies;
  if (maxActiveStrategiesRaw !== undefined) {
    next.max_active_strategies = parseMaxActiveStrategies(maxActiveStrategiesRaw, prev.max_active_strategies);
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
};
