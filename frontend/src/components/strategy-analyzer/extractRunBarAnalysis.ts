import type { StrategyAnalyzerRunBarAnalysisSnapshot } from "./types";

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
      warmup_only: false,
      bar_index: null,
      checkpoint_mode: true,
      intrabar_only_checkpoint: !hasCheckpointScores,
      checkpoint_offset_sec: Number.isFinite(Number(bar?.offset_sec)) ? Number(bar.offset_sec) : null,
      provisional: typeof bar?.provisional === "boolean" ? Boolean(bar.provisional) : null,
      timestamp: typeof bar?.timestamp === "string" ? bar.timestamp : null,
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
    (bar.intraday_levels && typeof bar.intraday_levels === "object" ? bar.intraday_levels : null) ||
    (bar.analysis?.intraday_levels && typeof bar.analysis.intraday_levels === "object"
      ? bar.analysis.intraday_levels
      : null) ||
    (bar.analysis?.metadata?.intraday_levels &&
    typeof bar.analysis.metadata.intraday_levels === "object"
      ? bar.analysis.metadata.intraday_levels
      : null) ||
    (bar.analysis?.signal_metadata?.intraday_levels &&
    typeof bar.analysis.signal_metadata.intraday_levels === "object"
      ? bar.analysis.signal_metadata.intraday_levels
      : null) ||
    (bar.analysis?.signal?.metadata?.intraday_levels &&
    typeof bar.analysis.signal.metadata.intraday_levels === "object"
      ? bar.analysis.signal.metadata.intraday_levels
      : null) ||
    (bar.strategy_analysis?.intraday_levels &&
    typeof bar.strategy_analysis.intraday_levels === "object"
      ? bar.strategy_analysis.intraday_levels
      : null) ||
    (bar.strategy_analysis?.metadata?.intraday_levels &&
    typeof bar.strategy_analysis.metadata.intraday_levels === "object"
      ? bar.strategy_analysis.metadata.intraday_levels
      : null) ||
    (bar.strategy_analysis?.signal_metadata?.intraday_levels &&
    typeof bar.strategy_analysis.signal_metadata.intraday_levels === "object"
      ? bar.strategy_analysis.signal_metadata.intraday_levels
      : null) ||
    null;
  if (!layerScores && !intradayLevels) return null;

  const signalRejected =
    bar.signal_rejected ?? bar.analysis?.signal_rejected ?? bar.strategy_analysis?.signal_rejected ?? null;
  const candidateDiagnostics =
    bar.candidate_diagnostics ??
    bar.analysis?.candidate_diagnostics ??
    bar.strategy_analysis?.candidate_diagnostics ??
    null;
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
    intrabar_1s:
      (bar.intrabar_1s && typeof bar.intrabar_1s === "object" ? bar.intrabar_1s : null) ||
      (bar.analysis?.intrabar_1s && typeof bar.analysis.intrabar_1s === "object"
        ? bar.analysis.intrabar_1s
        : null) ||
      (bar.strategy_analysis?.intrabar_1s &&
      typeof bar.strategy_analysis.intrabar_1s === "object"
        ? bar.strategy_analysis.intrabar_1s
        : null),
    intrabar_eval_trace:
      (bar.intrabar_eval_trace && typeof bar.intrabar_eval_trace === "object"
        ? bar.intrabar_eval_trace
        : null) ||
      (bar.analysis?.intrabar_eval_trace && typeof bar.analysis.intrabar_eval_trace === "object"
        ? bar.analysis.intrabar_eval_trace
        : null) ||
      (bar.strategy_analysis?.intrabar_eval_trace &&
      typeof bar.strategy_analysis.intrabar_eval_trace === "object"
        ? bar.strategy_analysis.intrabar_eval_trace
        : null),
    intraday_levels: intradayLevels,
    bar_index: Number.isFinite(Number(barIndexCandidate)) ? Number(barIndexCandidate) : null,
    warmup_only: warmupOnly,
    timestamp: bar.timestamp || bar.analysis?.timestamp || bar.strategy_analysis?.timestamp || null,
  };
}
