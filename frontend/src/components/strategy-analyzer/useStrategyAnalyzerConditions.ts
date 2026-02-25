import { useEffect, useMemo, useRef } from "react";
import {
  deriveScrubbedLiveAnalysis,
  hasDecisionPayload,
} from "./scrubConditionsUtils";
import { useStrategyAnalyzerScrubEval } from "./useStrategyAnalyzerScrubEval";
import type {
  StrategyAnalyzerConditionsLiveAnalysis,
  StrategyAnalyzerConditionsPanelBadge,
  StrategyAnalyzerConditionsRangeScrubMeta,
  StrategyAnalyzerConditionsState,
  StrategyAnalyzerDecisionMarker,
} from "./types";

type Params = {
  rangeScrubMeta: StrategyAnalyzerConditionsRangeScrubMeta;
  selectedMarker: StrategyAnalyzerDecisionMarker | null;
  latestBarAnalysis: StrategyAnalyzerConditionsLiveAnalysis;
  onEvaluateIntrabarSlice?: (ts: number) => Promise<StrategyAnalyzerConditionsLiveAnalysis>;
};

export function useStrategyAnalyzerConditions({
  rangeScrubMeta,
  selectedMarker,
  latestBarAnalysis,
  onEvaluateIntrabarSlice,
}: Params): StrategyAnalyzerConditionsState {
  const lastStableScrubAnalysisRef = useRef<StrategyAnalyzerConditionsLiveAnalysis>(null);

  const scrubbedLiveAnalysis = useMemo(() => {
    return deriveScrubbedLiveAnalysis(rangeScrubMeta);
  }, [rangeScrubMeta]);

  const scrubbedCheckpointHasDecisionPayload = useMemo(() => {
    return hasDecisionPayload(scrubbedLiveAnalysis);
  }, [scrubbedLiveAnalysis]);

  const { isScrubbingLiveEval, scrubLiveAnalysis } = useStrategyAnalyzerScrubEval({
    targetTime: rangeScrubMeta?.targetTime ?? null,
    scrubbedCheckpointHasDecisionPayload,
    onEvaluateIntrabarSlice,
  });

  const scrubbedConditionsActive = Boolean(
    rangeScrubMeta && Number(rangeScrubMeta.progressedPoints || 0) > 0
  );
  const effectiveConditionsMarker = scrubbedConditionsActive ? null : selectedMarker;
  const effectiveConditionsLiveAnalysis: StrategyAnalyzerConditionsLiveAnalysis = effectiveConditionsMarker
    ? null
    : scrubbedConditionsActive
      ? (() => {
          const base = scrubbedCheckpointHasDecisionPayload
            ? scrubbedLiveAnalysis
            : scrubLiveAnalysis
              ? {
                  ...scrubbedLiveAnalysis,
                  ...scrubLiveAnalysis,
                  candidate_diagnostics:
                    scrubLiveAnalysis.candidate_diagnostics ||
                    scrubLiveAnalysis.signal?.metadata?.candidate_diagnostics ||
                    scrubbedLiveAnalysis?.candidate_diagnostics,
                  signal_rejected:
                    scrubLiveAnalysis.signal_rejected || scrubbedLiveAnalysis?.signal_rejected,
                  checkpoint_mode: false,
                  intrabar_only_checkpoint: false,
                }
              : scrubbedLiveAnalysis ||
                ((rangeScrubMeta?.clampedOffset ?? -1) === (rangeScrubMeta?.progressedMaxOffset ?? -2)
                  ? latestBarAnalysis
                  : null);
          if (base && !base.timestamp && rangeScrubMeta?.targetTime) {
            return { ...base, timestamp: rangeScrubMeta.targetTime };
          }
          return base;
        })()
      : !selectedMarker
        ? latestBarAnalysis
        : null;

  useEffect(() => {
    if (!scrubbedConditionsActive) {
      lastStableScrubAnalysisRef.current = null;
      return;
    }
    if (effectiveConditionsLiveAnalysis && typeof effectiveConditionsLiveAnalysis === "object") {
      lastStableScrubAnalysisRef.current = effectiveConditionsLiveAnalysis;
    }
  }, [scrubbedConditionsActive, effectiveConditionsLiveAnalysis]);

  const stableConditionsLiveAnalysis: StrategyAnalyzerConditionsLiveAnalysis = scrubbedConditionsActive
    ? effectiveConditionsLiveAnalysis || lastStableScrubAnalysisRef.current
    : effectiveConditionsLiveAnalysis;

  const hasConditionsPanelData = Boolean(
    effectiveConditionsMarker || stableConditionsLiveAnalysis || scrubbedConditionsActive
  );

  const conditionsPanelBadge = useMemo<StrategyAnalyzerConditionsPanelBadge>(() => {
    if (scrubbedConditionsActive) {
      if (rangeScrubMeta?.targetLocal) {
        return {
          label: `scrub ${rangeScrubMeta.targetLocal.replace("T", " ")}`,
          tone: "muted" as const,
        };
      }
      return { label: "scrub", tone: "muted" as const };
    }
    if (selectedMarker) {
      return {
        label: selectedMarker.strategy || selectedMarker.marker_type?.replace(/_/g, " "),
        tone: "accent" as const,
      };
    }
    if (latestBarAnalysis) {
      return { label: "live", tone: "muted" as const };
    }
    return null;
  }, [scrubbedConditionsActive, rangeScrubMeta, selectedMarker, latestBarAnalysis]);

  return {
    isScrubbingLiveEval,
    scrubbedConditionsActive,
    effectiveConditionsMarker,
    stableConditionsLiveAnalysis,
    hasConditionsPanelData,
    conditionsPanelBadge,
  };
}
