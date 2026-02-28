import type {
  CandlestickChartBar,
  CandlestickChartMarker,
} from '../components/CandlestickChart';
import type {
  StrategyAnalyzerAttachedRunState,
  StrategyAnalyzerConditionsLiveAnalysis,
  StrategyAnalyzerDecisionMarker,
  StrategyAnalyzerRunBarLike,
} from '../components/strategy-analyzer/types';
import { normalizeIsoDay, toUnixSeconds } from '../utils';

type AnyRecord = Record<string, any>;

type RunKeyParts = {
  runId: string;
  ticker: string;
  date: string;
};

type RunDateWindow = {
  dateFrom: string;
  dateTo: string;
  startTime: string;
  endTime: string;
};

type BarAnalysisArtifacts = {
  nestedAnalysis: AnyRecord | null;
  layerScores: AnyRecord | null;
  signalRejected: AnyRecord | null;
  candidateDiagnostics: AnyRecord | null;
  intrabarEvalTrace: AnyRecord | null;
  intradayLevelsSnapshot: AnyRecord | null;
  levelContextSnapshot: AnyRecord | null;
  entryQualityDiagnosticsSnapshot: AnyRecord | null;
  latestCheckpoint: AnyRecord | null;
  resolvedWarmupOnly: boolean | undefined;
  resolvedBarIndex: number | undefined;
  shouldAttachAnalysisPayload: boolean;
};

const RUN_RANGE_LABEL_PATTERN = /^(\d{4}-\d{2}-\d{2})_to_(\d{4}-\d{2}-\d{2})$/;

const asObjectRecord = (value: unknown): AnyRecord | null =>
  value && typeof value === 'object' && !Array.isArray(value) ? (value as AnyRecord) : null;

const getBarAnalysisArtifacts = (bar: StrategyAnalyzerRunBarLike | AnyRecord | null | undefined): BarAnalysisArtifacts => {
  const row = asObjectRecord(bar) || {};
  const analysisPayload = asObjectRecord(row.analysis);
  const strategyAnalysisPayload = asObjectRecord(row.strategy_analysis);
  const nestedAnalysis = analysisPayload || strategyAnalysisPayload || null;
  const layerScores =
    asObjectRecord(row.layer_scores) ||
    asObjectRecord(nestedAnalysis?.layer_scores) ||
    null;
  const signalRejected =
    asObjectRecord(row.signal_rejected) ||
    asObjectRecord(nestedAnalysis?.signal_rejected) ||
    null;
  const candidateDiagnostics =
    asObjectRecord(row.candidate_diagnostics) ||
    asObjectRecord(nestedAnalysis?.candidate_diagnostics) ||
    null;
  const intrabarEvalTrace =
    asObjectRecord(row.intrabar_eval_trace) ||
    asObjectRecord(nestedAnalysis?.intrabar_eval_trace) ||
    null;
  const intradayLevelsSnapshot =
    asObjectRecord(row.intraday_levels) ||
    asObjectRecord(analysisPayload?.intraday_levels) ||
    asObjectRecord(analysisPayload?.metadata?.intraday_levels) ||
    asObjectRecord(analysisPayload?.indicators?.intraday_levels) ||
    asObjectRecord(analysisPayload?.signal_metadata?.intraday_levels) ||
    asObjectRecord(analysisPayload?.signal?.intraday_levels) ||
    asObjectRecord(analysisPayload?.signal?.metadata?.intraday_levels) ||
    asObjectRecord(strategyAnalysisPayload?.intraday_levels) ||
    asObjectRecord(strategyAnalysisPayload?.metadata?.intraday_levels) ||
    asObjectRecord(strategyAnalysisPayload?.indicators?.intraday_levels) ||
    asObjectRecord(strategyAnalysisPayload?.signal_metadata?.intraday_levels) ||
    asObjectRecord(strategyAnalysisPayload?.signal?.intraday_levels) ||
    asObjectRecord(strategyAnalysisPayload?.signal?.metadata?.intraday_levels) ||
    null;
  const levelContextSnapshot =
    asObjectRecord(row.level_context) ||
    asObjectRecord(analysisPayload?.level_context) ||
    asObjectRecord(analysisPayload?.signal_metadata?.level_context) ||
    asObjectRecord(strategyAnalysisPayload?.level_context) ||
    asObjectRecord(strategyAnalysisPayload?.signal_metadata?.level_context) ||
    null;
  const entryQualityDiagnosticsSnapshot =
    asObjectRecord(row.entry_quality_diagnostics) ||
    asObjectRecord(analysisPayload?.entry_quality_diagnostics) ||
    asObjectRecord(strategyAnalysisPayload?.entry_quality_diagnostics) ||
    null;
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

export const parseRunKey = (value: unknown): RunKeyParts | null => {
  const raw = String(value || '').trim();
  if (!raw) return null;
  const parts = raw.split(':');
  if (parts.length < 3) return null;
  const date = parts.pop();
  const ticker = parts.pop();
  const runId = parts.join(':');
  if (!runId || !ticker || !date) return null;
  return { runId, ticker, date };
};

export const buildRunKeyFromState = (runStateRow: AnyRecord | null | undefined): string | null => {
  if (!runStateRow || typeof runStateRow !== 'object') return null;
  const runId = String(runStateRow.run_id || '').trim();
  const ticker = String(runStateRow.ticker || '').trim();
  const date = String(runStateRow.date || '').trim();
  if (!runId || !ticker || !date) return null;
  return `${runId}:${ticker}:${date}`;
};

export const buildRunApiBase = (runParts: RunKeyParts | null): string | null => {
  if (!runParts) return null;
  return `/api/run/${encodeURIComponent(runParts.runId)}/${encodeURIComponent(runParts.ticker)}/${encodeURIComponent(runParts.date)}`;
};

export const resolveRunDateWindow = (stateRow: AnyRecord | null | undefined): RunDateWindow | null => {
  const row = stateRow && typeof stateRow === 'object' ? stateRow : {};
  const rawDate = String(row.date || '').trim();
  const rangeMatch = rawDate.match(RUN_RANGE_LABEL_PATTERN);
  const from = normalizeIsoDay(row.date_from) || normalizeIsoDay(rangeMatch?.[1]) || normalizeIsoDay(rawDate);
  let to = normalizeIsoDay(row.date_to) || normalizeIsoDay(rangeMatch?.[2]) || from;
  if (!from) return null;
  if (!to || to < from) {
    to = from;
  }
  return {
    dateFrom: from,
    dateTo: to,
    startTime: `${from}T04:00:00Z`,
    endTime: `${to}T20:00:00Z`,
  };
};

export const readErrorDetail = async (response: Response, fallback: string): Promise<string> => {
  const backup = response.clone();
  try {
    const payload = await response.json();
    if (payload && typeof payload === 'object') {
      const detail = payload.detail ?? payload.error ?? payload.message;
      if (detail !== null && detail !== undefined && String(detail).trim()) {
        return String(detail);
      }
    }
  } catch (_error) {
    // Fallback to plain-text body below.
  }

  try {
    const raw = await backup.text();
    const text = String(raw || '').trim();
    if (text) return text;
  } catch (_error) {
    // Ignore and use fallback.
  }

  return String(fallback || '').trim() || 'Unknown error';
};

export const normalizeNonEmptyToken = (value: unknown): string => {
  const token = String(value ?? '').trim();
  return token || '';
};

const pickFirstNonEmptyToken = (...values: unknown[]): string => {
  for (const value of values) {
    const token = normalizeNonEmptyToken(value);
    if (token) return token;
  }
  return '';
};

const extractRunProfileMetadata = (payload: unknown) => {
  const row = payload && typeof payload === 'object' ? (payload as AnyRecord) : {};
  const reportMeta =
    row.report_metadata && typeof row.report_metadata === 'object' ? row.report_metadata : {};
  const aosApplied = row.aos_applied && typeof row.aos_applied === 'object' ? row.aos_applied : {};
  const unifiedMeta =
    aosApplied.unified_profile && typeof aosApplied.unified_profile === 'object'
      ? aosApplied.unified_profile
      : {};
  const adaptiveMeta =
    aosApplied.adaptive_profile && typeof aosApplied.adaptive_profile === 'object'
      ? aosApplied.adaptive_profile
      : {};
  const comboMeta =
    aosApplied.strategy_combo && typeof aosApplied.strategy_combo === 'object'
      ? aosApplied.strategy_combo
      : {};

  return {
    unified_profile_id: pickFirstNonEmptyToken(
      reportMeta.unified_profile_id,
      row.unified_profile_id,
      unifiedMeta.active_profile_id,
      unifiedMeta.profile_id,
    ),
    unified_profile_name: pickFirstNonEmptyToken(
      reportMeta.unified_profile_name,
      row.unified_profile_name,
      unifiedMeta.profile_name,
    ),
    adaptive_profile_id: pickFirstNonEmptyToken(
      reportMeta.adaptive_profile_id,
      row.adaptive_profile_id,
      adaptiveMeta.active_profile_id,
      adaptiveMeta.profile_id,
    ),
    strategy_combo_profile_id: pickFirstNonEmptyToken(
      reportMeta.strategy_combo_profile_id,
      row.strategy_combo_profile_id,
      comboMeta.active_profile_id,
      comboMeta.profile_id,
    ),
  };
};

export const buildEffectiveExecutionConfigSnapshot = (payload: unknown): AnyRecord | null => {
  if (!payload || typeof payload !== 'object') return null;

  const source = payload as AnyRecord;
  const executionConfig =
    source.execution_config && typeof source.execution_config === 'object'
      ? { ...source.execution_config }
      : {};
  const profileMeta = extractRunProfileMetadata(payload);

  if (profileMeta.unified_profile_id && !normalizeNonEmptyToken(executionConfig.unified_profile_id)) {
    executionConfig.unified_profile_id = profileMeta.unified_profile_id;
  }
  if (
    profileMeta.unified_profile_name &&
    !normalizeNonEmptyToken(executionConfig.unified_profile_name)
  ) {
    executionConfig.unified_profile_name = profileMeta.unified_profile_name;
  }
  if (profileMeta.adaptive_profile_id && !normalizeNonEmptyToken(executionConfig.adaptive_profile_id)) {
    executionConfig.adaptive_profile_id = profileMeta.adaptive_profile_id;
  }
  if (
    profileMeta.strategy_combo_profile_id &&
    !normalizeNonEmptyToken(executionConfig.strategy_combo_profile_id)
  ) {
    executionConfig.strategy_combo_profile_id = profileMeta.strategy_combo_profile_id;
  }

  return Object.keys(executionConfig).length ? executionConfig : null;
};

export const resolveTradeModeFromExecutionConfig = (
  executionConfig: AnyRecord | null | undefined,
  fallbackMode = 'standard',
): string => {
  const fallback =
    fallbackMode === 'intrabar_5s' ||
    fallbackMode === 'intrabar_1s' ||
    fallbackMode === 'standard'
      ? fallbackMode
      : 'standard';
  if (!executionConfig || typeof executionConfig !== 'object') return fallback;

  const explicitMode = String(executionConfig.trade_eval_mode || '')
    .trim()
    .toLowerCase();
  if (
    explicitMode === 'intrabar_5s' ||
    explicitMode === 'intrabar_1s' ||
    explicitMode === 'standard'
  ) {
    return explicitMode;
  }

  if (typeof executionConfig.intrabar_execution_recalc_1s === 'boolean') {
    if (!executionConfig.intrabar_execution_recalc_1s) return 'standard';
    const step = Number(executionConfig.intrabar_eval_step_seconds || 1);
    return Number.isFinite(step) && step >= 5 ? 'intrabar_5s' : 'intrabar_1s';
  }

  return fallback;
};

export const toChartBar = (bar: StrategyAnalyzerRunBarLike | AnyRecord | null | undefined): CandlestickChartBar | null => {
  if (!bar || typeof bar !== 'object') return null;
  const time = toUnixSeconds(bar.timestamp ?? bar.time);
  const open = Number(bar.open);
  const high = Number(bar.high);
  const low = Number(bar.low);
  const close = Number(bar.close);
  const volume = Number(bar.volume);

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
  } = getBarAnalysisArtifacts(bar);

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
          timestamp: typeof bar.timestamp === 'string' ? bar.timestamp : undefined,
          ...(shouldAttachAnalysisPayload ? { analysis: nestedAnalysis } : {}),
        }
      : {}),
  };
};

export const extractLiveBarAnalysis = (
  bar: StrategyAnalyzerRunBarLike | null | undefined,
): StrategyAnalyzerConditionsLiveAnalysis => {
  if (!bar || typeof bar !== 'object') return null;

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
  } = getBarAnalysisArtifacts(bar);

  if (
    !layerScores &&
    !intrabarEvalTrace &&
    !intradayLevelsSnapshot &&
    !levelContextSnapshot &&
    !entryQualityDiagnosticsSnapshot
  ) {
    return null;
  }

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
    timestamp: typeof bar.timestamp === 'string' ? bar.timestamp : null,
    ...(nestedAnalysis?.intrabar_confirmation && typeof nestedAnalysis.intrabar_confirmation === 'object'
      ? { intrabar_confirmation: nestedAnalysis.intrabar_confirmation }
      : {}),
    ...(nestedAnalysis?.micro_confirmation && typeof nestedAnalysis.micro_confirmation === 'object'
      ? { micro_confirmation: nestedAnalysis.micro_confirmation }
      : {}),
    ...(nestedAnalysis?.context_risk && typeof nestedAnalysis.context_risk === 'object'
      ? { context_risk: nestedAnalysis.context_risk }
      : {}),
  };
};

export const mergeRunStateWithStreamBar = (
  previousState: StrategyAnalyzerAttachedRunState | null,
  bar: StrategyAnalyzerRunBarLike | null | undefined,
): StrategyAnalyzerAttachedRunState | null => {
  if (!previousState) return null;

  const totalBars = Number(previousState.total_bars || 0);
  const streamIndex = Number(bar?.bar_index);
  const legacyIndex = Number(bar?.index);

  const rawCurrent = Number.isFinite(streamIndex)
    ? streamIndex + 1
    : (Number.isFinite(legacyIndex)
        ? legacyIndex + 1
        : Number(previousState.current_bar_index || 0) + 1);

  const current = totalBars > 0
    ? Math.min(totalBars, Math.max(0, rawCurrent))
    : Math.max(0, rawCurrent);
  const progress = totalBars > 0
    ? Math.min(100, Math.max(0, (current / totalBars) * 100))
    : 0;

  return {
    ...previousState,
    current_bar_index: current,
    progress_pct: progress,
  };
};

export const upsertStreamChartBar = (
  previousBars: CandlestickChartBar[],
  nextBar: CandlestickChartBar,
): CandlestickChartBar[] => {
  if (!previousBars.length) return [nextBar];
  const lastBar = previousBars[previousBars.length - 1];
  if (Math.abs(Number(lastBar?.time || 0) - Number(nextBar.time || 0)) < 0.0001) {
    const updatedBars = [...previousBars];
    updatedBars[updatedBars.length - 1] = nextBar;
    return updatedBars;
  }
  return [...previousBars, nextBar];
};

export const upsertDecisionMarker = (
  previousMarkers: StrategyAnalyzerDecisionMarker[],
  nextMarker: StrategyAnalyzerDecisionMarker,
): StrategyAnalyzerDecisionMarker[] => {
  const markerIndex = previousMarkers.findIndex((marker) => marker.id === nextMarker.id);
  if (markerIndex !== -1) {
    const updatedMarkers = [...previousMarkers];
    updatedMarkers[markerIndex] = { ...previousMarkers[markerIndex], ...nextMarker };
    return updatedMarkers;
  }
  return [...previousMarkers, nextMarker];
};

export const scoreMarkerMatch = (
  candidate: StrategyAnalyzerDecisionMarker | null | undefined,
  target: CandlestickChartMarker | StrategyAnalyzerDecisionMarker | null | undefined,
): number => {
  if (!candidate || !target) return Number.NEGATIVE_INFINITY;

  const candidateId = normalizeNonEmptyToken(candidate.id).toLowerCase();
  const targetId = normalizeNonEmptyToken(target.id).toLowerCase();
  if (candidateId && targetId && candidateId === targetId) {
    return Number.POSITIVE_INFINITY;
  }

  let score = 0;

  const candidateType = normalizeNonEmptyToken(candidate.marker_type).toLowerCase();
  const targetType = normalizeNonEmptyToken(target.marker_type).toLowerCase();
  if (candidateType && targetType) {
    score += candidateType === targetType ? 500 : -200;
  }

  const candidateSide = normalizeNonEmptyToken(candidate.side ?? candidate.details?.side).toLowerCase();
  const targetSide = normalizeNonEmptyToken(target.side ?? target.details?.side).toLowerCase();
  if (candidateSide && targetSide && candidateSide === targetSide) {
    score += 180;
  }

  const candidateStrategy = normalizeNonEmptyToken(candidate.strategy).toLowerCase();
  const targetStrategy = normalizeNonEmptyToken(target.strategy).toLowerCase();
  if (candidateStrategy && targetStrategy && candidateStrategy === targetStrategy) {
    score += 140;
  }

  const candidateRegime = normalizeNonEmptyToken(candidate.regime).toLowerCase();
  const targetRegime = normalizeNonEmptyToken(target.regime).toLowerCase();
  if (candidateRegime && targetRegime && candidateRegime === targetRegime) {
    score += 120;
  }

  const candidateSignal = normalizeNonEmptyToken(candidate.details?.signal_type).toLowerCase();
  const targetSignal = normalizeNonEmptyToken(target.details?.signal_type).toLowerCase();
  if (candidateSignal && targetSignal && candidateSignal === targetSignal) {
    score += 80;
  }

  const candidateRun = normalizeNonEmptyToken(candidate.run_id ?? candidate.details?.run_id).toLowerCase();
  const targetRun = normalizeNonEmptyToken(target.run_id ?? target.details?.run_id).toLowerCase();
  if (candidateRun && targetRun && candidateRun === targetRun) {
    score += 90;
  }

  const candidateTicker = normalizeNonEmptyToken(candidate.ticker ?? candidate.details?.ticker).toLowerCase();
  const targetTicker = normalizeNonEmptyToken(target.ticker ?? target.details?.ticker).toLowerCase();
  if (candidateTicker && targetTicker && candidateTicker === targetTicker) {
    score += 60;
  }

  const candidateTitle = normalizeNonEmptyToken(candidate.title).toLowerCase();
  const targetTitle = normalizeNonEmptyToken(target.title).toLowerCase();
  if (candidateTitle && targetTitle && candidateTitle === targetTitle) {
    score += 40;
  }

  const candidateTs = toUnixSeconds(candidate.time ?? candidate.timestamp);
  const targetTs = toUnixSeconds(target.time ?? target.timestamp);
  if (Number.isFinite(candidateTs) && Number.isFinite(targetTs)) {
    const diff = Math.abs(candidateTs - targetTs);
    if (diff <= 1) score += 220;
    else if (diff <= 5) score += 170;
    else if (diff <= 60) score += 120;
    else if (diff <= 300) score += 70;
    else if (diff <= 1800) score += 20;
    else score -= Math.min(220, diff / 20);
  }

  const candidatePrice = Number(candidate.price);
  const targetPrice = Number(target.price);
  if (Number.isFinite(candidatePrice) && Number.isFinite(targetPrice)) {
    const diff = Math.abs(candidatePrice - targetPrice);
    score += 120 / (1 + diff);
  }

  return score;
};
