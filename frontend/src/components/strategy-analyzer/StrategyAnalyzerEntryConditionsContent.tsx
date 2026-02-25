import StrategyConditionsPanel from "./StrategyConditionsPanel";
import type {
  StrategyAnalyzerConditionsLiveAnalysis,
  StrategyAnalyzerDecisionMarker,
} from "./types";

type Props = {
  effectiveConditionsMarker: StrategyAnalyzerDecisionMarker | null;
  stableConditionsLiveAnalysis: StrategyAnalyzerConditionsLiveAnalysis;
  isScrubbingLiveEval: boolean;
};

export default function StrategyAnalyzerEntryConditionsContent({
  effectiveConditionsMarker,
  stableConditionsLiveAnalysis,
  isScrubbingLiveEval,
}: Props) {
  return (
    <div style={{ flex: 1, minHeight: 0, overflowY: "auto", overflowX: "hidden", position: "relative" }}>
      <StrategyConditionsPanel
        marker={effectiveConditionsMarker}
        liveAnalysis={stableConditionsLiveAnalysis}
      />
      {isScrubbingLiveEval ? (
        <div
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            width: "100%",
            height: "100%",
            background: "rgba(0,0,0,0.2)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <span style={{ color: "var(--text-muted)", fontSize: "0.8rem" }}>evaluating...</span>
        </div>
      ) : null}
    </div>
  );
}
