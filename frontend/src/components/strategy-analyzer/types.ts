import type { Dispatch, MutableRefObject, SetStateAction } from "react";
import type {
  CandlestickChartHandle,
  CandlestickChartMarker,
  CandlestickChartVisibleRange,
} from "../CandlestickChart";

export type StrategyAnalyzerTradeEvalMode = "standard" | "intrabar_1s" | "intrabar_5s";
export type StrategyAnalyzerContextRiskPresetKey =
  | "current_defaults"
  | "baseline"
  | "relaxed_context_35"
  | "no_context_risk";

export type StrategyAnalyzerRunControlOptions = {
  trade_eval_mode?: StrategyAnalyzerTradeEvalMode | string;
  speed_ms?: number | string;
};

export type StrategyAnalyzerPlaybackProgress = {
  warmupDone: number;
  warmupTotal: number;
  tradeDone: number;
  tradeTotal: number;
  tradeProgressPct: number;
  isInitializing: boolean;
} | null;

export type StrategyAnalyzerConditionsPanelBadge = {
  label: string;
  tone: "accent" | "muted";
} | null;

export type StrategyAnalyzerAnyObject = Record<string, any>;

export type StrategyAnalyzerDecisionMarker = {
  time?: string | number | null;
  timestamp?: string | number | null;
  bar_index?: number | null;
  marker_type?: string | null;
  regime?: string | null;
  strategy?: string | null;
  [key: string]: any;
};

export type StrategyAnalyzerChartBarLike = {
  time?: number | string | null;
  bar_index?: number | null;
  __wfPlaceholder?: boolean;
  [key: string]: any;
};

export type StrategyAnalyzerPreviewBar = StrategyAnalyzerChartBarLike & {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
};

export type StrategyAnalyzerRunBarLike = StrategyAnalyzerChartBarLike & {
  warmup_only?: boolean;
  intrabar_eval_trace?: StrategyAnalyzerAnyObject | null;
  analysis?: StrategyAnalyzerAnyObject | null;
  strategy_analysis?: StrategyAnalyzerAnyObject | null;
};

export type StrategyAnalyzerAttachedRunState = {
  phase?: string | null;
  is_running?: boolean | null;
  current_bar_index?: number | null;
  total_bars?: number | null;
  progress_pct?: number | null;
  [key: string]: any;
};

export type StrategyAnalyzerChartMarkerClickTarget =
  | CandlestickChartMarker
  | StrategyAnalyzerDecisionMarker
  | string
  | number;

export type StrategyAnalyzerStartRunPayload = {
  run_id: string;
  ticker: string;
  date_from: string;
  date_to: string;
  start_time: string | null;
  end_time: string | null;
  trade_start_time: string | null;
  trade_end_time: string | null;
  strategy_api_url: string;
  include_extended_hours: boolean;
  trade_eval_mode: StrategyAnalyzerTradeEvalMode;
  context_aware_risk_enabled?: boolean;
  context_risk_min_room_pct?: number;
  context_risk_min_effective_rr?: number;
  __client_hint?: "strategy_analyzer";
};

export type StrategyAnalyzerStartRunResult = {
  run_key?: string | null;
  [key: string]: unknown;
} | null;

export type StrategyAnalyzerRangeScrubTimelinePoint = {
  kind?: string;
  time?: number | null;
  barTime?: number | null;
  checkpoint?: StrategyAnalyzerAnyObject | null;
  checkpointIndex?: number;
  runBar?: StrategyAnalyzerRunBarLike;
};

export type StrategyAnalyzerChartWindow = CandlestickChartVisibleRange;
export type StrategyAnalyzerChartHandle = CandlestickChartHandle;

export type StrategyAnalyzerRangePlaybackMeta = {
  rawFromSec: number;
  rawToSec: number;
  tradeStartTs: number;
  tradeEndTs: number;
  warmupStartTs: number;
  tradeStartIdx: number | null;
  tradeEndIdx: number | null;
  warmupStartIdx: number | null;
  tradeStartLocal: string;
  tradeEndLocal: string;
  warmupStartLocal: string;
  tradeTotalBars: number;
  warmupTotalBars: number;
} | null;

export type StrategyAnalyzerRunBarAnalysisSnapshot = {
  layer_scores?: StrategyAnalyzerAnyObject | null;
  signal_rejected?: StrategyAnalyzerAnyObject | null;
  candidate_diagnostics?: StrategyAnalyzerAnyObject | null;
  intrabar_1s?: StrategyAnalyzerAnyObject | null;
  intrabar_eval_trace?: StrategyAnalyzerAnyObject | null;
  intraday_levels?: StrategyAnalyzerAnyObject | null;
  intrabar_confirmation?: StrategyAnalyzerAnyObject | null;
  micro_confirmation?: StrategyAnalyzerAnyObject | null;
  level_context?: StrategyAnalyzerAnyObject | null;
  context_risk?: StrategyAnalyzerAnyObject | null;
  warmup_only?: boolean;
  bar_index?: number | null;
  timestamp?: string | number | null;
  checkpoint_mode?: boolean;
  intrabar_only_checkpoint?: boolean;
  checkpoint_offset_sec?: number | null;
  provisional?: boolean | null;
};

export type StrategyAnalyzerConditionsLiveAnalysis =
  | (StrategyAnalyzerRunBarAnalysisSnapshot & StrategyAnalyzerAnyObject)
  | null;

export type StrategyAnalyzerRangeScrubBase = {
  tradeStartIdx: number | null;
  tradeEndIdx: number | null;
  startTime: number;
  endTime: number;
  progressedTradeBars: StrategyAnalyzerRunBarLike[];
  progressedBars: number;
  progressedPoints: number;
  timelinePoints: StrategyAnalyzerRangeScrubTimelinePoint[];
  tradeTotalBars: number;
  progressPct: number;
  fullMaxOffset: number;
  progressedMaxOffset: number;
  enabledTrackPct: number;
  estimatedPointsPerBar: number;
  sliderStepBars: number;
  sliderStepSeconds: number | null;
  startLocal: string;
  endLocal: string;
};

export type StrategyAnalyzerRangeScrubMeta = (StrategyAnalyzerRangeScrubBase & {
  clampedOffset: number;
  targetPoint: StrategyAnalyzerRangeScrubTimelinePoint | null;
  targetBar: StrategyAnalyzerChartBarLike | null;
  targetCheckpoint: StrategyAnalyzerAnyObject | null;
  targetTime: number | null;
  targetLocal: string | null;
}) | null;

export type StrategyAnalyzerConditionsRangeScrubMeta = StrategyAnalyzerRangeScrubMeta;

export type StrategyAnalyzerOnStartRun = (
  config: StrategyAnalyzerStartRunPayload
) => Promise<StrategyAnalyzerStartRunResult>;

export type StrategyAnalyzerOnRunControl = (
  options?: StrategyAnalyzerRunControlOptions
) => Promise<unknown> | void;

export type StrategyAnalyzerOnPauseRun = () => Promise<unknown> | void;

export type StrategyAnalyzerOnClearRun = () => Promise<unknown> | void;

export type StrategyAnalyzerConditionsState = {
  isScrubbingLiveEval: boolean;
  scrubbedConditionsActive: boolean;
  effectiveConditionsMarker: StrategyAnalyzerDecisionMarker | null;
  stableConditionsLiveAnalysis: StrategyAnalyzerConditionsLiveAnalysis;
  hasConditionsPanelData: boolean;
  conditionsPanelBadge: StrategyAnalyzerConditionsPanelBadge;
};

export type StrategyAnalyzerOnEvaluateIntrabarSlice = (
  ts: number
) => Promise<StrategyAnalyzerConditionsLiveAnalysis>;

export type StrategyAnalyzerTimelineCacheState = {
  processedRunBarCount: number;
  runBarsByTime: Map<number, StrategyAnalyzerRunBarLike>;
  progressedTradeBars: StrategyAnalyzerRunBarLike[];
  timelinePoints: StrategyAnalyzerRangeScrubTimelinePoint[];
  observedCheckpointCounts: number[];
  warmupDone: number;
  tradeDone: number;
  startTime: number | null;
  endTime: number | null;
  rangeKey: string | null;
};

export type StrategyAnalyzerTimelineCacheRef = MutableRefObject<StrategyAnalyzerTimelineCacheState>;

export type BooleanStateSetter = Dispatch<SetStateAction<boolean>>;

export type StrategyAnalyzerWfoGridConfig = {
  contextRiskMinSlValues: string;
  timeExitBarsValues: string;
  breakEvenMinRValues: string;
  breakEvenProofBookPressureValues: string;
  evRelaxationThresholdValues: string;
  signedAggressionBlockZValues: string;
  includeBaseline: boolean;
  maxCombinations: number;
  parallelWorkers: number;
};

export type StrategyAnalyzerWfoMetrics = {
  totalTrades: number;
  winRate: number;
  totalPnlDollars: number;
  maxDrawdownDollars: number;
  profitFactor: number | null;
};

export type StrategyAnalyzerWfoVariantStatus =
  | "pending"
  | "running"
  | "completed"
  | "failed";

export type StrategyAnalyzerWfoVariantResult = {
  id: string;
  label: string;
  status: StrategyAnalyzerWfoVariantStatus;
  overrides: Record<string, number>;
  runKey: string | null;
  metrics: StrategyAnalyzerWfoMetrics | null;
  objectiveScore: number;
  error: string | null;
};
