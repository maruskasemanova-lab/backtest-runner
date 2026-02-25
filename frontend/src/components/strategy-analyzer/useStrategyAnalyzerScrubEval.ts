import { useCallback, useEffect, useRef, useState } from "react";
import type { StrategyAnalyzerConditionsLiveAnalysis } from "./types";

type Params = {
  targetTime?: number | null;
  scrubbedCheckpointHasDecisionPayload: boolean;
  onEvaluateIntrabarSlice?: (ts: number) => Promise<StrategyAnalyzerConditionsLiveAnalysis>;
};

export function useStrategyAnalyzerScrubEval({
  targetTime,
  scrubbedCheckpointHasDecisionPayload,
  onEvaluateIntrabarSlice,
}: Params) {
  const [isScrubbingLiveEval, setIsScrubbingLiveEval] = useState(false);
  const [scrubLiveAnalysis, setScrubLiveAnalysis] =
    useState<StrategyAnalyzerConditionsLiveAnalysis>(null);
  const scrubEvalSeqRef = useRef(0);

  const handleEvaluateIntrabarSlice = useCallback(
    async (ts: number) => {
      if (typeof onEvaluateIntrabarSlice !== "function") return;

      const requestSeq = ++scrubEvalSeqRef.current;
      setIsScrubbingLiveEval(true);
      try {
        const result = await onEvaluateIntrabarSlice(ts);
        if (scrubEvalSeqRef.current !== requestSeq) return;
        setScrubLiveAnalysis(result);
      } catch (err) {
        if (scrubEvalSeqRef.current !== requestSeq) return;
        console.error("Intrabar slice evaluation failed:", err);
        setScrubLiveAnalysis(null);
      } finally {
        if (scrubEvalSeqRef.current === requestSeq) {
          setIsScrubbingLiveEval(false);
        }
      }
    },
    [onEvaluateIntrabarSlice]
  );

  useEffect(() => {
    if (
      Number.isFinite(targetTime) &&
      !scrubbedCheckpointHasDecisionPayload &&
      typeof onEvaluateIntrabarSlice === "function"
    ) {
      const delay = setTimeout(() => {
        handleEvaluateIntrabarSlice(Number(targetTime));
      }, 300);
      return () => clearTimeout(delay);
    }

    scrubEvalSeqRef.current += 1;
    setIsScrubbingLiveEval(false);
    setScrubLiveAnalysis(null);
  }, [
    targetTime,
    scrubbedCheckpointHasDecisionPayload,
    handleEvaluateIntrabarSlice,
    onEvaluateIntrabarSlice,
  ]);

  return {
    isScrubbingLiveEval,
    scrubLiveAnalysis,
  };
}
