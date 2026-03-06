import type { StrategyAnalyzerRunBarAnalysisSnapshot } from "./types";

const pickFirstObject = (...values: unknown[]): Record<string, any> | null => {
  for (const value of values) {
    if (value && typeof value === "object" && !Array.isArray(value)) {
      return value as Record<string, any>;
    }
  }
  return null;
};

export function extractRunBarAnalysis(bar: any): StrategyAnalyzerRunBarAnalysisSnapshot | null {
  if (!bar || typeof bar !== "object") return null;
  const hasLayerScoresOnBar = Boolean(
    (bar.layer_scores && typeof bar.layer_scores === "object") ||
      (bar.analysis?.layer_scores && typeof bar.analysis.layer_scores === "object") ||
      (bar.strategy_analysis?.layer_scores && typeof bar.strategy_analysis.layer_scores === "object")
  );
  const checkpointIntrabar =
    bar.intrabar_1s && typeof bar.intrabar_1s === "object" ? bar.intrabar_1s : null;
  const checkpointLayerScores =
    bar.layer_scores && typeof bar.layer_scores === "object" ? bar.layer_scores : null;
  const checkpointSignalRejected =
    bar.signal_rejected && typeof bar.signal_rejected === "object" ? bar.signal_rejected : null;
  const checkpointCandidateDiagnostics =
    bar.candidate_diagnostics && typeof bar.candidate_diagnostics === "object"
      ? bar.candidate_diagnostics
      : null;
  const checkpointEntryQualityDiagnostics =
    bar.entry_quality_diagnostics && typeof bar.entry_quality_diagnostics === "object"
      ? bar.entry_quality_diagnostics
      : null;
  const checkpointTcbboConfirmation =
    bar.tcbbo_confirmation && typeof bar.tcbbo_confirmation === "object"
      ? bar.tcbbo_confirmation
      : null;
  const checkpointLike =
    !hasLayerScoresOnBar &&
    (checkpointIntrabar ||
      Number.isFinite(Number(bar?.offset_sec)) ||
      typeof bar?.provisional === "boolean");
  if (checkpointLike) {
    const hasCheckpointScores = Boolean(checkpointLayerScores);
    return {
      layer_scores: checkpointLayerScores,
      signal_rejected: checkpointSignalRejected,
      candidate_diagnostics: checkpointCandidateDiagnostics,
      intrabar_1s: checkpointIntrabar,
      intrabar_confirmation:
        bar.intrabar_confirmation && typeof bar.intrabar_confirmation === "object"
          ? bar.intrabar_confirmation
          : null,
      micro_confirmation:
        bar.micro_confirmation && typeof bar.micro_confirmation === "object"
          ? bar.micro_confirmation
          : null,
      level_context:
        bar.level_context && typeof bar.level_context === "object" ? bar.level_context : null,
      context_risk:
        bar.context_risk && typeof bar.context_risk === "object" ? bar.context_risk : null,
      entry_quality_diagnostics: checkpointEntryQualityDiagnostics,
      tcbbo_confirmation: checkpointTcbboConfirmation,
      warmup_only: false,
      bar_index: null,
      checkpoint_mode: true,
      intrabar_only_checkpoint: !hasCheckpointScores,
      checkpoint_offset_sec: Number.isFinite(Number(bar?.offset_sec)) ? Number(bar.offset_sec) : null,
      provisional: typeof bar?.provisional === "boolean" ? Boolean(bar.provisional) : null,
      timestamp: typeof bar?.timestamp === "string" ? bar.timestamp : null,
      bar_action: typeof bar?.action === "string" ? bar.action : null,
      bar_reason: typeof bar?.reason === "string" ? bar.reason : null,
    };
  }

  const layerScores =
    (bar.layer_scores && typeof bar.layer_scores === "object" && bar.layer_scores) ||
    (bar.analysis?.layer_scores &&
      typeof bar.analysis.layer_scores === "object" &&
      bar.analysis.layer_scores) ||
    (bar.strategy_analysis?.layer_scores &&
      typeof bar.strategy_analysis.layer_scores === "object" &&
      bar.strategy_analysis.layer_scores) ||
    null;
  const intradayLevels =
    pickFirstObject(
      bar.intraday_levels,
      bar.analysis?.intraday_levels,
      bar.analysis?.metadata?.intraday_levels,
      bar.analysis?.signal_metadata?.intraday_levels,
      bar.analysis?.signal?.metadata?.intraday_levels,
      bar.strategy_analysis?.intraday_levels,
      bar.strategy_analysis?.metadata?.intraday_levels,
      bar.strategy_analysis?.signal_metadata?.intraday_levels,
    );

  const signalRejected = pickFirstObject(
    bar.signal_rejected,
    bar.analysis?.signal_rejected,
    bar.strategy_analysis?.signal_rejected,
  );
  const candidateDiagnostics = pickFirstObject(
    bar.candidate_diagnostics,
    bar.analysis?.candidate_diagnostics,
    bar.strategy_analysis?.candidate_diagnostics,
  );
  const intrabar1s = pickFirstObject(
    bar.intrabar_1s,
    bar.analysis?.intrabar_1s,
    bar.strategy_analysis?.intrabar_1s,
  );
  const intrabarEvalTrace = pickFirstObject(
    bar.intrabar_eval_trace,
    bar.analysis?.intrabar_eval_trace,
    bar.strategy_analysis?.intrabar_eval_trace,
  );
  const intrabarConfirmation = pickFirstObject(
    bar.intrabar_confirmation,
    bar.analysis?.intrabar_confirmation,
    bar.strategy_analysis?.intrabar_confirmation,
  );
  const microConfirmation = pickFirstObject(
    bar.micro_confirmation,
    bar.analysis?.micro_confirmation,
    bar.strategy_analysis?.micro_confirmation,
  );
  const levelContext = pickFirstObject(
    bar.level_context,
    bar.analysis?.level_context,
    bar.analysis?.signal_metadata?.level_context,
    bar.strategy_analysis?.level_context,
    bar.strategy_analysis?.signal_metadata?.level_context,
  );
  const contextRisk = pickFirstObject(
    bar.context_risk,
    bar.analysis?.context_risk,
    bar.strategy_analysis?.context_risk,
  );
  const entryQualityDiagnostics = pickFirstObject(
    bar.entry_quality_diagnostics,
    bar.analysis?.entry_quality_diagnostics,
    bar.strategy_analysis?.entry_quality_diagnostics,
  );
  const tcbboConfirmation = pickFirstObject(
    bar.tcbbo_confirmation,
    bar.analysis?.tcbbo_confirmation,
    bar.analysis?.signal_metadata?.tcbbo_confirmation,
    bar.strategy_analysis?.tcbbo_confirmation,
    bar.strategy_analysis?.signal_metadata?.tcbbo_confirmation,
  );

  if (
    !layerScores &&
    !signalRejected &&
    !candidateDiagnostics &&
    !intrabar1s &&
    !intrabarEvalTrace &&
    !intradayLevels &&
    !intrabarConfirmation &&
    !microConfirmation &&
    !levelContext &&
    !contextRisk &&
    !entryQualityDiagnostics &&
    !tcbboConfirmation
  ) {
    return null;
  }

  const warmupOnly =
    typeof bar.warmup_only === "boolean"
      ? bar.warmup_only
      : typeof bar.analysis?.warmup_only === "boolean"
        ? bar.analysis.warmup_only
        : typeof bar.strategy_analysis?.warmup_only === "boolean"
          ? bar.strategy_analysis.warmup_only
          : false;
  const barIndexCandidate =
    bar.bar_index ?? bar.analysis?.bar_index ?? bar.strategy_analysis?.bar_index ?? null;

  return {
    layer_scores: layerScores,
    signal_rejected: signalRejected,
    candidate_diagnostics: candidateDiagnostics,
    intrabar_1s: intrabar1s,
    intrabar_eval_trace: intrabarEvalTrace,
    intraday_levels: intradayLevels,
    intrabar_confirmation: intrabarConfirmation,
    micro_confirmation: microConfirmation,
    level_context: levelContext,
    context_risk: contextRisk,
    entry_quality_diagnostics: entryQualityDiagnostics,
    tcbbo_confirmation: tcbboConfirmation,
    bar_index: Number.isFinite(Number(barIndexCandidate)) ? Number(barIndexCandidate) : null,
    warmup_only: warmupOnly,
    timestamp: bar.timestamp || bar.analysis?.timestamp || bar.strategy_analysis?.timestamp || null,
    bar_action:
      bar.action ?? bar.analysis?.action ?? bar.strategy_analysis?.action ?? null,
    bar_reason:
      bar.reason ?? bar.analysis?.reason ?? bar.strategy_analysis?.reason ?? null,
  };
}
