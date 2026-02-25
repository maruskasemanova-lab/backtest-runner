import { safeNum } from "./StrategyConditionsPanelShared";

type StrategyConditionsPanelSourceMap = Record<string, number> | null;

export interface StrategyConditionsPanelDataValue {
  source: "marker" | "live";
  combinedScore: number | null;
  strategyScore: number | null;
  flowScore: number | null;
  threshold: number | null;
  thresholdReason: string | null;
  passed: boolean | null;
  confirmingSources: number | null;
  requiredConfirmingSources: number | null;
  alignedSourceKeys: string[];
  l2HasCoverage: boolean | null;
  l2QualityOk: boolean | null;
  l2AggressionZ: number | null;
  l2BookPressureZ: number | null;
  signedAggression: number | null;
  microRegime: string | null;
  regime: string | null;
  todBoost: number | null;
  headwindBoost: number | null;
  top3: any[];
  activeStrategies: any[];
  selectedStrategy: string | null;
  sweepDetected: boolean | null;
  tcbboPassed: boolean | null;
  signalDirection: string | null;
  rejectionGate: string | null;
  rejectionReason: string | null;
  rejectionDetails: any;
  contextRisk: any;
  levelQuality: number | null;
  intrabarCoverage: number | null;
  intrabarMovePct: number | null;
  intrabarPushRatio: number | null;
  intrabarSpreadBps: number | null;
  intrabarHasCoverage: boolean | null;
  markerType: string;
  barTimestamp: string | number | null;
  sourceContributions: StrategyConditionsPanelSourceMap;
  sourceWeights: StrategyConditionsPanelSourceMap;
  calibratedProbability: number | null;
  intrabarOnlyCheckpoint: boolean;
  liveAnalysisSource: any | null;
}

export function extractStrategyConditionsPanelData(
  marker: any,
  liveAnalysis: any,
): StrategyConditionsPanelDataValue | null {
  // ── From a decision marker ──
  if (marker) {
    const details = marker?.details || {};
    const metadata = details?.metadata || details?.signal_metadata || {};
    const ls = metadata?.layer_scores || details?.layer_scores || details?.signal_metadata?.layer_scores || {};
    const cd =
      metadata?.candidate_diagnostics ||
      details?.candidate_diagnostics ||
      details?.signal_metadata?.candidate_diagnostics ||
      {};
    const flowSnapshot = details?.flow_snapshot || metadata?.order_flow || details?.signal_metadata?.order_flow || {};
    const signalRejected = details?.signal_rejected || {};
    const intrabarSnapshot = details?.intrabar_1s || metadata?.intrabar_1s || details?.signal_metadata?.intrabar_1s || {};
    const tcbbo =
      details?.tcbbo_confirmation ||
      metadata?.tcbbo_confirmation ||
      details?.signal_metadata?.tcbbo_confirmation ||
      {};
    const levelCtx = details?.level_context || metadata?.level_context || details?.signal_metadata?.level_context || {};

    return {
      source: "marker" as const,
      combinedScore: safeNum(ls.combined_score ?? ls.combined_norm_0_100),
      strategyScore: safeNum(ls.strategy_score),
      flowScore: safeNum(ls.flow_score ?? flowSnapshot?.flow_score),
      threshold: safeNum(ls.threshold_used ?? ls.threshold ?? ls.trade_gate_threshold),
      thresholdReason: ls.threshold_used_reason || null,
      passed: typeof ls.passed === "boolean" ? ls.passed : null,
      confirmingSources: safeNum(ls.confirming_sources ?? ls.aligned_evidence_sources),
      requiredConfirmingSources: safeNum(ls.required_confirming_sources),
      alignedSourceKeys: Array.isArray(ls.aligned_source_keys) ? ls.aligned_source_keys : [],
      l2HasCoverage: typeof ls.l2_has_coverage === "boolean" ? ls.l2_has_coverage : null,
      l2QualityOk: typeof ls.l2_quality_ok === "boolean" ? ls.l2_quality_ok : null,
      l2AggressionZ: safeNum(ls.l2_aggression_z ?? flowSnapshot?.l2_aggression_z),
      l2BookPressureZ: safeNum(ls.l2_book_pressure_z ?? flowSnapshot?.l2_book_pressure_z),
      signedAggression: safeNum(flowSnapshot?.signed_aggression ?? ls.signed_aggression),
      microRegime: ls.micro_regime || null,
      regime: marker?.regime || null,
      todBoost: safeNum(ls.tod_threshold_boost),
      headwindBoost: safeNum(ls.headwind_threshold_boost),
      top3: Array.isArray(cd.top3) ? cd.top3 : [],
      activeStrategies: Array.isArray(cd.active_strategies) ? cd.active_strategies : [],
      selectedStrategy: cd.strategy_name || marker?.strategy || null,
      sweepDetected: typeof ls.sweep_detected === "boolean" ? ls.sweep_detected : null,
      tcbboPassed: typeof tcbbo?.passed === "boolean" ? tcbbo.passed : null,
      signalDirection: signalRejected?.signal_type || marker?.side || details?.side || cd?.signal_type || null,
      rejectionGate: signalRejected?.gate || null,
      rejectionReason: signalRejected?.reason || null,
      rejectionDetails: signalRejected && typeof signalRejected === "object" && signalRejected.gate ? signalRejected : null,
      contextRisk: details?.context_risk && typeof details.context_risk === "object" ? details.context_risk : null,
      levelQuality: safeNum(levelCtx?.quality_score ?? levelCtx?.entry_quality),
      intrabarCoverage: safeNum(intrabarSnapshot?.coverage_points),
      intrabarMovePct: safeNum(intrabarSnapshot?.mid_move_pct),
      intrabarPushRatio: safeNum(intrabarSnapshot?.push_ratio),
      intrabarSpreadBps: safeNum(intrabarSnapshot?.spread_bps_avg),
      intrabarHasCoverage:
        typeof intrabarSnapshot?.has_intrabar_coverage === "boolean" ? intrabarSnapshot.has_intrabar_coverage : null,
      markerType: String(marker?.marker_type || "").trim(),
      barTimestamp: marker?.timestamp || marker?.time || null,
      sourceContributions:
        ls.source_contributions && typeof ls.source_contributions === "object" ? ls.source_contributions : null,
      sourceWeights: ls.source_weights && typeof ls.source_weights === "object" ? ls.source_weights : null,
      calibratedProbability: safeNum(ls.calibrated_probability),
      intrabarOnlyCheckpoint: false,
      liveAnalysisSource: null,
    };
  }

  // ── From live bar analysis (streamed with each bar) ──
  if (liveAnalysis) {
    const ls = liveAnalysis?.layer_scores || {};
    const sr = liveAnalysis?.signal_rejected || {};
    const cd = liveAnalysis?.candidate_diagnostics || {};
    const intrabar = liveAnalysis?.intrabar_1s || {};
    const tcbbo = liveAnalysis?.tcbbo_confirmation || {};
    const intrabarOnlyCheckpoint = Boolean(liveAnalysis?.checkpoint_mode && liveAnalysis?.intrabar_only_checkpoint);

    return {
      source: "live" as const,
      combinedScore: safeNum(ls.combined_score ?? ls.combined_norm_0_100),
      strategyScore: safeNum(ls.strategy_score),
      flowScore: safeNum(ls.flow_score),
      threshold: safeNum(ls.threshold_used ?? ls.threshold ?? ls.trade_gate_threshold),
      thresholdReason: ls.threshold_used_reason || null,
      passed: typeof ls.passed === "boolean" ? ls.passed : null,
      confirmingSources: safeNum(ls.confirming_sources ?? ls.aligned_evidence_sources),
      requiredConfirmingSources: safeNum(ls.required_confirming_sources),
      alignedSourceKeys: Array.isArray(ls.aligned_source_keys) ? ls.aligned_source_keys : [],
      l2HasCoverage: typeof ls.l2_has_coverage === "boolean" ? ls.l2_has_coverage : null,
      l2QualityOk: typeof ls.l2_quality_ok === "boolean" ? ls.l2_quality_ok : null,
      l2AggressionZ: safeNum(ls.l2_aggression_z),
      l2BookPressureZ: safeNum(ls.l2_book_pressure_z),
      signedAggression: safeNum(ls.signed_aggression),
      microRegime: ls.micro_regime || null,
      regime: null,
      todBoost: safeNum(ls.tod_threshold_boost),
      headwindBoost: safeNum(ls.headwind_threshold_boost),
      top3: Array.isArray(cd.top3) ? cd.top3 : [],
      activeStrategies: Array.isArray(cd.active_strategies) ? cd.active_strategies : [],
      selectedStrategy: cd.strategy_name || null,
      sweepDetected: typeof ls.sweep_detected === "boolean" ? ls.sweep_detected : null,
      tcbboPassed: tcbbo?.enabled === true ? (typeof tcbbo?.passed === "boolean" ? tcbbo.passed : null) : null,
      signalDirection: sr?.signal_type || cd?.signal_type || null,
      rejectionGate: sr?.gate || null,
      rejectionReason: sr?.reason || null,
      rejectionDetails: sr && typeof sr === "object" && sr.gate ? sr : null,
      contextRisk:
        liveAnalysis?.context_risk && typeof liveAnalysis.context_risk === "object" ? liveAnalysis.context_risk : null,
      levelQuality: null,
      intrabarCoverage: safeNum(intrabar?.coverage_points),
      intrabarMovePct: safeNum(intrabar?.mid_move_pct),
      intrabarPushRatio: safeNum(intrabar?.push_ratio),
      intrabarSpreadBps: safeNum(intrabar?.spread_bps_avg),
      intrabarHasCoverage: typeof intrabar?.has_intrabar_coverage === "boolean" ? intrabar.has_intrabar_coverage : null,
      markerType: intrabarOnlyCheckpoint ? "5s checkpoint" : liveAnalysis?.warmup_only ? "warmup" : "live bar",
      intrabarOnlyCheckpoint,
      liveAnalysisSource: liveAnalysis,
      barTimestamp: liveAnalysis?.timestamp || null,
      sourceContributions:
        ls.source_contributions && typeof ls.source_contributions === "object" ? ls.source_contributions : null,
      sourceWeights: ls.source_weights && typeof ls.source_weights === "object" ? ls.source_weights : null,
      calibratedProbability: safeNum(ls.calibrated_probability),
    };
  }

  return null;
}

export type StrategyConditionsPanelData = ReturnType<typeof extractStrategyConditionsPanelData>;
