import { useCallback, type Dispatch, type SetStateAction } from 'react';
import type {
  CandlestickChartBar,
  CandlestickChartMarker,
} from '../components/CandlestickChart';
import type { IntradayLevelsDialogSelection } from '../intradayLevelsUtils';
import { buildIntradayLevelsDialogSelection } from '../intradayLevelsUtils';
import type {
  StrategyAnalyzerChartMarkerClickTarget,
  StrategyAnalyzerConditionsLiveAnalysis,
  StrategyAnalyzerDecisionMarker,
} from '../components/strategy-analyzer/types';
import { normalizeText, toUnixSeconds } from '../utils';

type UseChartSelectionActionsArgs = {
  decisionEvents: StrategyAnalyzerDecisionMarker[];
  markers: StrategyAnalyzerDecisionMarker[];
  timeframe: string;
  currentBar: Record<string, any> | null;
  latestBarAnalysis: StrategyAnalyzerConditionsLiveAnalysis;
  setSelectedMarker: Dispatch<SetStateAction<StrategyAnalyzerDecisionMarker | null>>;
  setSelectedIntrabar: Dispatch<SetStateAction<any>>;
  setSelectedIntradayLevels: Dispatch<SetStateAction<IntradayLevelsDialogSelection | null>>;
};

const resolveChartTimeframeSeconds = (timeframe: string): number => {
  const normalized = String(timeframe || '').trim().toLowerCase();
  if (normalized === '1h') return 3600;
  const minutes = Number.parseInt(normalized, 10);
  return Number.isFinite(minutes) && minutes > 0 ? minutes * 60 : 60;
};

const scoreMarkerMatch = (
  candidate: StrategyAnalyzerDecisionMarker | null | undefined,
  target: CandlestickChartMarker | StrategyAnalyzerDecisionMarker | null | undefined,
) => {
  if (!candidate || !target) return Number.NEGATIVE_INFINITY;

  const candidateId = normalizeText(candidate.id);
  const targetId = normalizeText(target.id);
  if (candidateId && targetId && candidateId === targetId) {
    return Number.POSITIVE_INFINITY;
  }

  let score = 0;

  const candidateType = normalizeText(candidate.marker_type);
  const targetType = normalizeText(target.marker_type);
  if (candidateType && targetType) {
    score += candidateType === targetType ? 500 : -200;
  }

  const candidateSide = normalizeText(candidate.side ?? candidate.details?.side);
  const targetSide = normalizeText(target.side ?? target.details?.side);
  if (candidateSide && targetSide && candidateSide === targetSide) {
    score += 180;
  }

  const candidateStrategy = normalizeText(candidate.strategy);
  const targetStrategy = normalizeText(target.strategy);
  if (candidateStrategy && targetStrategy && candidateStrategy === targetStrategy) {
    score += 140;
  }

  const candidateRegime = normalizeText(candidate.regime);
  const targetRegime = normalizeText(target.regime);
  if (candidateRegime && targetRegime && candidateRegime === targetRegime) {
    score += 120;
  }

  const candidateSignal = normalizeText(candidate.details?.signal_type);
  const targetSignal = normalizeText(target.details?.signal_type);
  if (candidateSignal && targetSignal && candidateSignal === targetSignal) {
    score += 80;
  }

  const candidateRun = normalizeText(candidate.run_id ?? candidate.details?.run_id);
  const targetRun = normalizeText(target.run_id ?? target.details?.run_id);
  if (candidateRun && targetRun && candidateRun === targetRun) {
    score += 90;
  }

  const candidateTicker = normalizeText(candidate.ticker ?? candidate.details?.ticker);
  const targetTicker = normalizeText(target.ticker ?? target.details?.ticker);
  if (candidateTicker && targetTicker && candidateTicker === targetTicker) {
    score += 60;
  }

  const candidateTitle = normalizeText(candidate.title);
  const targetTitle = normalizeText(target.title);
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

export const useChartSelectionActions = ({
  decisionEvents,
  markers,
  timeframe,
  currentBar,
  latestBarAnalysis,
  setSelectedMarker,
  setSelectedIntrabar,
  setSelectedIntradayLevels,
}: UseChartSelectionActionsArgs) => {
  const handleMarkerClick = useCallback(
    (markerOrId: StrategyAnalyzerChartMarkerClickTarget | null | undefined) => {
      if (!markerOrId) return;

      if (typeof markerOrId !== 'object') {
        const marker = decisionEvents.find((eventMarker) => eventMarker.id === markerOrId);
        if (marker) {
          setSelectedMarker({
            ...marker,
            __selectionSource: 'chart',
          } as StrategyAnalyzerDecisionMarker);
        }
        return;
      }

      let bestMatch: StrategyAnalyzerDecisionMarker | null = null;
      let bestScore = Number.NEGATIVE_INFINITY;
      decisionEvents.forEach((eventMarker) => {
        const score = scoreMarkerMatch(eventMarker, markerOrId);
        if (score > bestScore) {
          bestScore = score;
          bestMatch = eventMarker;
        }
      });

      if (bestMatch && bestScore > 100) {
        setSelectedMarker({
          ...bestMatch,
          __selectionSource: 'chart',
        } as StrategyAnalyzerDecisionMarker);
        return;
      }

      setSelectedMarker({
        ...markerOrId,
        __selectionSource: 'chart',
      } as StrategyAnalyzerDecisionMarker);
    },
    [decisionEvents, setSelectedMarker],
  );

  const closeIntradayLevelsDialog = useCallback(() => {
    setSelectedIntradayLevels(null);
  }, [setSelectedIntradayLevels]);

  const handleBarClick = useCallback(
    (bar: CandlestickChartBar | null | undefined) => {
      if (!bar || typeof bar !== 'object') return;

      setSelectedIntrabar(bar);
      const timeframeSeconds = resolveChartTimeframeSeconds(timeframe);
      const barTime = Number(bar.time);
      const currentBarTime = toUnixSeconds(currentBar?.timestamp ?? currentBar?.time);
      const shouldUseLatestBarAnalysisFallback =
        Number.isFinite(currentBarTime) &&
        Number.isFinite(barTime) &&
        Math.floor(currentBarTime) === Math.floor(barTime);

      const selection = buildIntradayLevelsDialogSelection({
        bar,
        allMarkers: markers,
        timeframeSeconds,
        fallbackAnalysis: shouldUseLatestBarAnalysisFallback ? latestBarAnalysis : null,
        fallbackAnalysisSourcePath: 'latest_bar_analysis',
      });
      if (selection) {
        setSelectedIntradayLevels(selection);
      }
    },
    [
      currentBar?.time,
      currentBar?.timestamp,
      latestBarAnalysis,
      markers,
      setSelectedIntrabar,
      setSelectedIntradayLevels,
      timeframe,
    ],
  );

  return {
    handleMarkerClick,
    closeIntradayLevelsDialog,
    handleBarClick,
  };
};
