import type { CSSProperties, ReactNode } from "react";

export type DecisionPanelDetailLabelOptions = {
  tooltipLabel?: string;
  style?: CSSProperties;
  runtimeValue?: unknown;
  runtimeSource?: string;
  runtimeFlow?: string | string[] | null;
};

export type DecisionPanelDetailLabelArg = string | DecisionPanelDetailLabelOptions;

export type DecisionPanelRenderDetailLabel = (
  label: string,
  tooltipLabelOrOptions?: DecisionPanelDetailLabelArg,
  style?: CSSProperties,
) => ReactNode;

export type DecisionPanelRenderSectionHeader = (title: string) => ReactNode;
export type DecisionPanelRenderFlag = (flag: unknown) => ReactNode;
export type DecisionPanelRenderValue = (value: unknown, keyPrefix?: string) => ReactNode;
export type DecisionPanelFormatGenericValue = (value: unknown) => ReactNode;
export type DecisionPanelRenderReasonValue = (value: unknown) => ReactNode;
export type DecisionPanelRenderBreakEvenValue = (value: unknown) => ReactNode;
export type DecisionPanelFormatPctValue = (value: unknown, digits?: number) => ReactNode;
export type DecisionPanelResolvePnlPct = (
  details: Record<string, unknown>,
  pnlDollars: unknown,
) => number | null;
export type DecisionPanelFormatTime = (timestamp: unknown) => string;
export type DecisionPanelFormatPrice = (value: unknown) => string;

export type DecisionPanelTooltipRuntimeEntry = {
  value?: unknown;
  source?: string;
  flow?: string[];
};

export type DecisionPanelTooltipRuntimeMap = Record<
  string,
  DecisionPanelTooltipRuntimeEntry | undefined
>;

export type DecisionPanelTooltipSelectedMarkerRef = {
  id?: unknown;
  timestamp?: unknown;
  time?: unknown;
};

export type DecisionPanelMarkerLike = {
  marker_type: string;
  timestamp?: unknown;
  time?: unknown;
  price?: unknown;
  side?: unknown;
  strategy?: unknown;
  confidence?: unknown;
  title?: unknown;
  description?: unknown;
  id?: unknown;
  ticker?: unknown;
  run_id?: unknown;
  details?: (Record<string, unknown> & {
    metadata?: unknown;
    exit_reason?: unknown;
  }) | null;
  [key: string]: unknown;
};

export type DecisionPanelMetadataLike = Record<string, unknown> & {
  strategy?: unknown;
};

export type DecisionPanelDetailsLike = Record<string, unknown> & {
  metadata?: unknown;
  costs?: Record<string, unknown> | null;
  stop_loss?: number | null;
  take_profit?: number | null;
  risk_reward?: number | null;
  exit_reason?: unknown;
  pnl_dollars?: unknown;
  pnl_usd?: unknown;
  bars_held?: unknown;
  reasoning?: unknown;
};

export type DecisionPanelDecisionStateLike = {
  action?: unknown;
  phase?: unknown;
  regime?: unknown;
  micro_regime?: unknown;
  selected_strategy?: unknown;
  [key: string]: unknown;
};

export type DecisionPanelContextRiskLike = {
  sl_reason?: unknown;
  tp_reason?: unknown;
  effective_rr?: unknown;
  risk_pct?: unknown;
  [key: string]: unknown;
};

export type DecisionPanelFlowSnapshotLike = {
  vwap_execution_flow?: unknown;
  [key: string]: unknown;
};

export type DecisionPanelDecisionLogPayloadLike = {
  decision_state?: DecisionPanelDecisionStateLike | null;
  context_risk?: DecisionPanelContextRiskLike | null;
  flow_snapshot?: DecisionPanelFlowSnapshotLike | null;
  [key: string]: unknown;
};

export type DecisionPanelDecisionLogLike = {
  hasAny?: boolean;
  payload?: DecisionPanelDecisionLogPayloadLike | null;
  [key: string]: unknown;
};

export type DecisionPanelBreakEvenPayloadLike = {
  state?: unknown;
  activation_reason?: unknown;
  [key: string]: unknown;
};

export type DecisionPanelBreakEvenComputedLike = {
  total_costs_pct?: unknown;
  [key: string]: unknown;
};

export type DecisionPanelBreakEvenBufferLike = {
  selected_buffer_pct?: unknown;
  [key: string]: unknown;
};

export type DecisionPanelL2DiagnosticsLike = {
  hasAny: boolean;
  flowScore?: number | null;
  signedAggression?: number | null;
  l2AggressionZ?: number | null;
  l2BookPressureZ?: number | null;
  absorptionRate?: number | null;
  largeTraderActivity?: number | null;
  vwapExecutionFlow?: number | null;
  sweepDetected?: boolean | null;
  sourcePath?: string | null;
  [key: string]: unknown;
};

export type DecisionPanelIntradayLevelsStatsLike = Record<string, unknown> & {
  active_levels?: unknown;
  tested_levels?: unknown;
  broken_levels?: unknown;
  bounce_events?: unknown;
  break_events?: unknown;
};

export type DecisionPanelIntradayLevelsVolumeProfileLike = Record<string, unknown> & {
  poc_price?: unknown;
  value_area_low?: unknown;
  value_area_high?: unknown;
};

export type DecisionPanelIntradayLevelsLatestEventLike = Record<string, unknown> & {
  event_type?: unknown;
  direction?: unknown;
  price?: unknown;
};

export type DecisionPanelIntradayLevelsLike = {
  hasAny: boolean;
  enabled?: unknown;
  stats: DecisionPanelIntradayLevelsStatsLike;
  volumeProfile: DecisionPanelIntradayLevelsVolumeProfileLike;
  latestEvent?: DecisionPanelIntradayLevelsLatestEventLike | null;
  [key: string]: unknown;
};

export type DecisionPanelLevelContextStatsLike = Record<string, unknown> & {
  near_tested_levels_count?: unknown;
};

export type DecisionPanelLevelContextVolumeProfileLike = Record<string, unknown> & {
  value_area_position?: unknown;
  poc_on_trade_side?: unknown;
};

export type DecisionPanelLevelContextPayloadLike = Record<string, unknown> & {
  passed?: unknown;
  strategy_key?: unknown;
  reason?: unknown;
  stats?: DecisionPanelLevelContextStatsLike | null;
  volume_profile?: DecisionPanelLevelContextVolumeProfileLike | null;
  room_to_next_opposite_level_pct?: unknown;
};

export type DecisionPanelLevelContextLike = {
  hasAny: boolean;
  payload: DecisionPanelLevelContextPayloadLike;
  reasons: string[];
  [key: string]: unknown;
};

export type DecisionPanelEntryQualityDiagnosticsPayloadLike = Record<string, unknown> & {
  is_first_bar_stop_loss?: unknown;
  stop_distance_pct?: unknown;
  vwap_distance_pct?: unknown;
  near_confluence_score?: unknown;
  near_tested_levels_count?: unknown;
  poc_on_trade_side?: unknown;
};

export type DecisionPanelEntryQualityDiagnosticsLike = {
  hasAny: boolean;
  payload: DecisionPanelEntryQualityDiagnosticsPayloadLike;
  tags: string[];
  [key: string]: unknown;
};
