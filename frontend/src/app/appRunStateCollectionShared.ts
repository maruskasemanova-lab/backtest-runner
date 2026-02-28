import type {
  CandlestickChartBar,
  CandlestickChartMarker,
} from '../components/CandlestickChart';
import type {
  StrategyAnalyzerAttachedRunState,
  StrategyAnalyzerDecisionMarker,
  StrategyAnalyzerRunBarLike,
} from '../components/strategy-analyzer/types';
import { toUnixSeconds } from '../utils';
import { normalizeNonEmptyToken } from './appRunStateStateHelpers';

const scoreExactTokenMatch = (
  candidateValue: unknown,
  targetValue: unknown,
  weight: number,
): number => {
  const candidateToken = normalizeNonEmptyToken(candidateValue).toLowerCase();
  const targetToken = normalizeNonEmptyToken(targetValue).toLowerCase();
  return candidateToken && targetToken && candidateToken === targetToken ? weight : 0;
};

const scoreTokenMatchWithPenalty = (
  candidateValue: unknown,
  targetValue: unknown,
  matchWeight: number,
  mismatchPenalty: number,
): number => {
  const candidateToken = normalizeNonEmptyToken(candidateValue).toLowerCase();
  const targetToken = normalizeNonEmptyToken(targetValue).toLowerCase();
  if (!candidateToken || !targetToken) return 0;
  return candidateToken === targetToken ? matchWeight : mismatchPenalty;
};

const scoreTimeProximity = (candidateTs: number, targetTs: number): number => {
  if (!Number.isFinite(candidateTs) || !Number.isFinite(targetTs)) return 0;
  const diff = Math.abs(candidateTs - targetTs);
  if (diff <= 1) return 220;
  if (diff <= 5) return 170;
  if (diff <= 60) return 120;
  if (diff <= 300) return 70;
  if (diff <= 1800) return 20;
  return -Math.min(220, diff / 20);
};

const scorePriceProximity = (candidatePrice: number, targetPrice: number): number => {
  if (!Number.isFinite(candidatePrice) || !Number.isFinite(targetPrice)) return 0;
  return 120 / (1 + Math.abs(candidatePrice - targetPrice));
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
  score += scoreTokenMatchWithPenalty(candidate.marker_type, target.marker_type, 500, -200);
  score += scoreExactTokenMatch(candidate.side ?? candidate.details?.side, target.side ?? target.details?.side, 180);
  score += scoreExactTokenMatch(candidate.strategy, target.strategy, 140);
  score += scoreExactTokenMatch(candidate.regime, target.regime, 120);
  score += scoreExactTokenMatch(candidate.details?.signal_type, target.details?.signal_type, 80);
  score += scoreExactTokenMatch(candidate.run_id ?? candidate.details?.run_id, target.run_id ?? target.details?.run_id, 90);
  score += scoreExactTokenMatch(candidate.ticker ?? candidate.details?.ticker, target.ticker ?? target.details?.ticker, 60);
  score += scoreExactTokenMatch(candidate.title, target.title, 40);
  score += scoreTimeProximity(
    toUnixSeconds(candidate.time ?? candidate.timestamp),
    toUnixSeconds(target.time ?? target.timestamp),
  );
  score += scorePriceProximity(Number(candidate.price), Number(target.price));

  return score;
};
