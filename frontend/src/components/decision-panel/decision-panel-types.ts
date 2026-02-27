import type { CSSProperties, ReactNode } from "react";
import type {
  DecisionPanelBreakEvenResolution,
  DecisionPanelDecisionLogResult,
  DecisionPanelEntryQualityDiagnosticsResult,
  DecisionPanelIntradayLevelsResult,
  DecisionPanelL2DiagnosticsResult,
  DecisionPanelLevelContextResult,
} from "./decision-panel-diagnostics";

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

export type DecisionPanelDecisionLogLike = DecisionPanelDecisionLogResult;
export type DecisionPanelDecisionLogPayloadLike = NonNullable<DecisionPanelDecisionLogLike["payload"]>;
export type DecisionPanelDecisionStateLike = NonNullable<
  DecisionPanelDecisionLogPayloadLike["decision_state"]
>;
export type DecisionPanelContextRiskLike = NonNullable<
  DecisionPanelDecisionLogPayloadLike["context_risk"]
>;
export type DecisionPanelFlowSnapshotLike = NonNullable<
  DecisionPanelDecisionLogPayloadLike["flow_snapshot"]
>;

export type DecisionPanelBreakEvenPayloadLike = NonNullable<DecisionPanelBreakEvenResolution["value"]>;

export type DecisionPanelBreakEvenComputedLike = {
  total_costs_pct?: unknown;
  [key: string]: unknown;
};

export type DecisionPanelBreakEvenBufferLike = {
  selected_buffer_pct?: unknown;
  [key: string]: unknown;
};

export type DecisionPanelL2DiagnosticsLike = DecisionPanelL2DiagnosticsResult;
export type DecisionPanelIntradayLevelsLike = DecisionPanelIntradayLevelsResult;
export type DecisionPanelIntradayLevelsStatsLike = DecisionPanelIntradayLevelsLike["stats"];
export type DecisionPanelIntradayLevelsVolumeProfileLike =
  DecisionPanelIntradayLevelsLike["volumeProfile"];
export type DecisionPanelIntradayLevelsLatestEventLike = NonNullable<
  DecisionPanelIntradayLevelsLike["latestEvent"]
>;

export type DecisionPanelLevelContextLike = DecisionPanelLevelContextResult;
export type DecisionPanelLevelContextPayloadLike = DecisionPanelLevelContextLike["payload"];
export type DecisionPanelLevelContextStatsLike = NonNullable<
  DecisionPanelLevelContextPayloadLike["stats"]
>;
export type DecisionPanelLevelContextVolumeProfileLike = NonNullable<
  DecisionPanelLevelContextPayloadLike["volume_profile"]
>;

export type DecisionPanelEntryQualityDiagnosticsLike = DecisionPanelEntryQualityDiagnosticsResult;
export type DecisionPanelEntryQualityDiagnosticsPayloadLike =
  DecisionPanelEntryQualityDiagnosticsLike["payload"];
