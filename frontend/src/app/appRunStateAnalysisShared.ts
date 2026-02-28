import type {
  CandlestickChartBar,
} from '../components/CandlestickChart';
import type {
  StrategyAnalyzerConditionsLiveAnalysis,
  StrategyAnalyzerRunBarLike,
} from '../components/strategy-analyzer/types';
import { toUnixSeconds } from '../utils';
import { asObjectRecord } from './appRunStateStateHelpers';
import type { AnyRecord, BarAnalysisArtifacts } from './appRunStateSharedTypes';

const pickFirstObjectRecord = (...values: unknown[]): AnyRecord | null => {
  for (const value of values) {
    const record = asObjectRecord(value);
    if (record) return record;
  }
  return null;
};

const getBarAnalysisArtifacts = (
  bar: StrategyAnalyzerRunBarLike | AnyRecord | null | undefined,
): BarAnalysisArtifacts => {
  const row = asObjectRecord(bar) || {};
  const analysisPayload = asObjectRecord(row.analysis);
  const strategyAnalysisPayload = asObjectRecord(row.strategy_analysis);
  const nestedAnalysis = analysisPayload || strategyAnalysisPayload || null;
  const layerScores = pickFirstObjectRecord(row.layer_scores, nestedAnalysis?.layer_scores);
  const signalRejected = pickFirstObjectRecord(row.signal_rejected, nestedAnalysis?.signal_rejected);
  const candidateDiagnostics = pickFirstObjectRecord(
    row.candidate_diagnostics,
    nestedAnalysis?.candidate_diagnostics,
  );
  const intrabarEvalTrace = pickFirstObjectRecord(
    row.intrabar_eval_trace,
    nestedAnalysis?.intrabar_eval_trace,
  );
  const intradayLevelsSnapshot = pickFirstObjectRecord(
    row.intraday_levels,
    analysisPayload?.intraday_levels,
    analysisPayload?.metadata?.intraday_levels,
    analysisPayload?.indicators?.intraday_levels,
    analysisPayload?.signal_metadata?.intraday_levels,
    analysisPayload?.signal?.intraday_levels,
    analysisPayload?.signal?.metadata?.intraday_levels,
    strategyAnalysisPayload?.intraday_levels,
    strategyAnalysisPayload?.metadata?.intraday_levels,
    strategyAnalysisPayload?.indicators?.intraday_levels,
    strategyAnalysisPayload?.signal_metadata?.intraday_levels,
    strategyAnalysisPayload?.signal?.intraday_levels,
    strategyAnalysisPayload?.signal?.metadata?.intraday_levels,
  );
  const levelContextSnapshot = pickFirstObjectRecord(
    row.level_context,
    analysisPayload?.level_context,
    analysisPayload?.signal_metadata?.level_context,
    strategyAnalysisPayload?.level_context,
    strategyAnalysisPayload?.signal_metadata?.level_context,
  );
  const entryQualityDiagnosticsSnapshot = pickFirstObjectRecord(
    row.entry_quality_diagnostics,
    analysisPayload?.entry_quality_diagnostics,
    strategyAnalysisPayload?.entry_quality_diagnostics,
  );
  const nestedWarmupOnly =
    typeof nestedAnalysis?.warmup_only === 'boolean' ? nestedAnalysis.warmup_only : undefined;
  const nestedBarIndex = nestedAnalysis?.bar_index;
  const resolvedWarmupOnly =
    typeof row.warmup_only === 'boolean' ? row.warmup_only : nestedWarmupOnly;
  const resolvedBarIndex =
    Number.isFinite(Number(row.bar_index))
      ? Number(row.bar_index)
      : (Number.isFinite(Number(nestedBarIndex)) ? Number(nestedBarIndex) : undefined);
  const traceCheckpoints = Array.isArray(intrabarEvalTrace?.checkpoints)
    ? intrabarEvalTrace.checkpoints
    : [];
  const latestCheckpoint = asObjectRecord(traceCheckpoints[traceCheckpoints.length - 1]) || null;
  const shouldAttachAnalysisPayload = Boolean(
    nestedAnalysis &&
      (layerScores ||
        signalRejected ||
        candidateDiagnostics ||
        intrabarEvalTrace ||
        intradayLevelsSnapshot ||
        levelContextSnapshot ||
        entryQualityDiagnosticsSnapshot ||
        nestedAnalysis?.intrabar_1s),
  );

  return {
    nestedAnalysis,
    layerScores,
    signalRejected,
    candidateDiagnostics,
    intrabarEvalTrace,
    intradayLevelsSnapshot,
    levelContextSnapshot,
    entryQualityDiagnosticsSnapshot,
    latestCheckpoint,
    resolvedWarmupOnly,
    resolvedBarIndex,
    shouldAttachAnalysisPayload,
  };
};

export const toChartBar = (
  bar: StrategyAnalyzerRunBarLike | AnyRecord | null | undefined,
): CandlestickChartBar | null => {
  const row = asObjectRecord(bar);
  if (!row) return null;

  const time = toUnixSeconds(row.timestamp ?? row.time);
  const open = Number(row.open);
  const high = Number(row.high);
  const low = Number(row.low);
  const close = Number(row.close);
  const volume = Number(row.volume);

  if (!Number.isFinite(time)) return null;
  if (!Number.isFinite(open) || !Number.isFinite(high) || !Number.isFinite(low) || !Number.isFinite(close)) {
    return null;
  }

  const {
    nestedAnalysis,
    layerScores,
    signalRejected,
    candidateDiagnostics,
    intrabarEvalTrace,
    intradayLevelsSnapshot,
    levelContextSnapshot,
    entryQualityDiagnosticsSnapshot,
    resolvedWarmupOnly,
    resolvedBarIndex,
    shouldAttachAnalysisPayload,
  } = getBarAnalysisArtifacts(row);

  return {
    time,
    open,
    high,
    low,
    close,
    volume: Number.isFinite(volume) ? volume : 0,
    ...(typeof resolvedWarmupOnly === 'boolean' ? { warmup_only: resolvedWarmupOnly } : {}),
    ...(resolvedBarIndex !== undefined ? { bar_index: resolvedBarIndex } : {}),
    ...(intradayLevelsSnapshot ? { intraday_levels: intradayLevelsSnapshot } : {}),
    ...(levelContextSnapshot ? { level_context: levelContextSnapshot } : {}),
    ...(entryQualityDiagnosticsSnapshot
      ? { entry_quality_diagnostics: entryQualityDiagnosticsSnapshot }
      : {}),
    ...(layerScores ||
    signalRejected ||
    candidateDiagnostics ||
    intrabarEvalTrace ||
    intradayLevelsSnapshot ||
    levelContextSnapshot ||
    entryQualityDiagnosticsSnapshot
      ? {
          layer_scores: layerScores || undefined,
          signal_rejected: signalRejected || undefined,
          candidate_diagnostics: candidateDiagnostics || undefined,
          intrabar_eval_trace: intrabarEvalTrace || undefined,
          timestamp: typeof row.timestamp === 'string' ? row.timestamp : undefined,
          ...(shouldAttachAnalysisPayload ? { analysis: nestedAnalysis } : {}),
        }
      : {}),
  };
};

export const extractLiveBarAnalysis = (
  bar: StrategyAnalyzerRunBarLike | null | undefined,
): StrategyAnalyzerConditionsLiveAnalysis => {
  const row = asObjectRecord(bar);
  if (!row) return null;

  const {
    nestedAnalysis,
    layerScores,
    signalRejected,
    candidateDiagnostics,
    intrabarEvalTrace,
    intradayLevelsSnapshot,
    levelContextSnapshot,
    entryQualityDiagnosticsSnapshot,
    latestCheckpoint,
    resolvedWarmupOnly,
    resolvedBarIndex,
  } = getBarAnalysisArtifacts(row);

  if (
    !layerScores &&
    !intrabarEvalTrace &&
    !intradayLevelsSnapshot &&
    !levelContextSnapshot &&
    !entryQualityDiagnosticsSnapshot
  ) {
    return null;
  }

  const intrabarConfirmation = asObjectRecord(nestedAnalysis?.intrabar_confirmation);
  const microConfirmation = asObjectRecord(nestedAnalysis?.micro_confirmation);
  const contextRisk = asObjectRecord(nestedAnalysis?.context_risk);

  return {
    layer_scores: layerScores || null,
    signal_rejected: signalRejected || null,
    candidate_diagnostics: candidateDiagnostics || null,
    intrabar_eval_trace: intrabarEvalTrace || null,
    intrabar_1s: asObjectRecord(latestCheckpoint?.intrabar_1s),
    intraday_levels: intradayLevelsSnapshot || null,
    level_context: levelContextSnapshot || null,
    entry_quality_diagnostics: entryQualityDiagnosticsSnapshot || null,
    bar_index: resolvedBarIndex ?? null,
    warmup_only: Boolean(resolvedWarmupOnly),
    timestamp: typeof row.timestamp === 'string' ? row.timestamp : null,
    ...(intrabarConfirmation ? { intrabar_confirmation: intrabarConfirmation } : {}),
    ...(microConfirmation ? { micro_confirmation: microConfirmation } : {}),
    ...(contextRisk ? { context_risk: contextRisk } : {}),
  };
};
