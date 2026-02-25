import { useCallback, useEffect, useState } from "react";
import {
  buildIntradayLevelsDialogSelection,
  type IntradayLevelsDialogSelection,
} from "../../intradayLevelsUtils";
import type {
  StrategyAnalyzerChartBarLike,
  StrategyAnalyzerConditionsLiveAnalysis,
  StrategyAnalyzerDecisionMarker,
} from "./types";

type Params = {
  analyzerDecisionEvents: StrategyAnalyzerDecisionMarker[];
  stableConditionsLiveAnalysis: StrategyAnalyzerConditionsLiveAnalysis;
  analyzerRunKey: string | null;
  selectedRangeFrom: string | null;
  selectedRangeTo: string | null;
};

export function useIntradayLevelsDialog({
  analyzerDecisionEvents,
  stableConditionsLiveAnalysis,
  analyzerRunKey,
  selectedRangeFrom,
  selectedRangeTo,
}: Params) {
  const [selectedIntradayLevels, setSelectedIntradayLevels] = useState<IntradayLevelsDialogSelection | null>(null);

  const handleAnalyzerBarClick = useCallback(
    (bar: StrategyAnalyzerChartBarLike) => {
      if (!bar || typeof bar !== "object" || bar.__wfPlaceholder) return;

      const selection = buildIntradayLevelsDialogSelection({
        bar,
        allMarkers: analyzerDecisionEvents,
        timeframeSeconds: 60,
        fallbackAnalysis: stableConditionsLiveAnalysis,
        fallbackAnalysisSourcePath: "effective_conditions_live_analysis",
      });
      if (selection) {
        setSelectedIntradayLevels(selection);
      }
    },
    [analyzerDecisionEvents, stableConditionsLiveAnalysis]
  );

  const closeIntradayLevelsDialog = useCallback(() => {
    setSelectedIntradayLevels(null);
  }, []);

  useEffect(() => {
    setSelectedIntradayLevels(null);
  }, [analyzerRunKey, selectedRangeFrom, selectedRangeTo]);

  return {
    selectedIntradayLevels,
    handleAnalyzerBarClick,
    closeIntradayLevelsDialog,
  };
}
