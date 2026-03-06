import { useEffect, useMemo, useRef } from "react";
import {
  deriveScrubbedLiveAnalysis,
  hasDecisionPayload,
  resolveScrubbedDecisionMarker,
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
  scrubMarkers?: StrategyAnalyzerDecisionMarker[];
  selectedMarker: StrategyAnalyzerDecisionMarker | null;
  latestBarAnalysis: StrategyAnalyzerConditionsLiveAnalysis;
  onEvaluateIntrabarSlice?: (ts: number) => Promise<StrategyAnalyzerConditionsLiveAnalysis>;
};

export function useStrategyAnalyzerConditions({
  rangeScrubMeta,
  scrubMarkers = [],
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
  const scrubbedConditionsMarker = useMemo(
    () =>
      scrubbedConditionsActive
        ? resolveScrubbedDecisionMarker(rangeScrubMeta, scrubMarkers)
        : null,
    [scrubbedConditionsActive, rangeScrubMeta, scrubMarkers],
  );
  const effectiveConditionsMarker = scrubbedConditionsActive
    ? scrubbedConditionsMarker
    : selectedMarker;
  const effectiveConditionsLiveAnalysis: StrategyAnalyzerConditionsLiveAnalysis = scrubbedConditionsActive
    ? (() => {
        const base = scrubbedCheckpointHasDecisionPayload
          ? scrubbedLiveAnalysis
          : scrubLiveAnalysis
            ? {
                ...scrubbedLiveAnalysis,
                ...scrubLiveAnalysis,
                layer_scores:
                  scrubLiveAnalysis.layer_scores || scrubbedLiveAnalysis?.layer_scores,
                candidate_diagnostics:
                  scrubLiveAnalysis.candidate_diagnostics ||
                  scrubLiveAnalysis.signal?.metadata?.candidate_diagnostics ||
                  scrubbedLiveAnalysis?.candidate_diagnostics,
                signal_rejected:
                  scrubLiveAnalysis.signal_rejected || scrubbedLiveAnalysis?.signal_rejected,
                intrabar_1s: scrubLiveAnalysis.intrabar_1s || scrubbedLiveAnalysis?.intrabar_1s,
                intrabar_eval_trace:
                  scrubLiveAnalysis.intrabar_eval_trace ||
                  scrubbedLiveAnalysis?.intrabar_eval_trace,
                intraday_levels:
                  scrubLiveAnalysis.intraday_levels || scrubbedLiveAnalysis?.intraday_levels,
                intrabar_confirmation:
                  scrubLiveAnalysis.intrabar_confirmation ||
                  scrubbedLiveAnalysis?.intrabar_confirmation,
                micro_confirmation:
                  scrubLiveAnalysis.micro_confirmation ||
                  scrubbedLiveAnalysis?.micro_confirmation,
                level_context:
                  scrubLiveAnalysis.level_context || scrubbedLiveAnalysis?.level_context,
                context_risk:
                  scrubLiveAnalysis.context_risk || scrubbedLiveAnalysis?.context_risk,
                entry_quality_diagnostics:
                  scrubLiveAnalysis.entry_quality_diagnostics ||
                  scrubbedLiveAnalysis?.entry_quality_diagnostics,
                tcbbo_confirmation:
                  scrubLiveAnalysis.tcbbo_confirmation ||
                  scrubbedLiveAnalysis?.tcbbo_confirmation,
                bar_action: scrubLiveAnalysis.bar_action || scrubbedLiveAnalysis?.bar_action,
                bar_reason: scrubLiveAnalysis.bar_reason || scrubbedLiveAnalysis?.bar_reason,
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
