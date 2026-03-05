import StrategyConditionsPanel from "./StrategyConditionsPanel";
import type {
  StrategyAnalyzerConditionsLiveAnalysis,
  StrategyAnalyzerDecisionMarker,
} from "./types";
import type { ThresholdOverrides, ThresholdOverrideKey } from "./useStrategyAnalyzerThresholdOverrides";

type Props = {
  effectiveConditionsMarker: StrategyAnalyzerDecisionMarker | null;
  stableConditionsLiveAnalysis: StrategyAnalyzerConditionsLiveAnalysis;
  isScrubbingLiveEval: boolean;
  isThresholdInteractive?: boolean;
  thresholdOverrides?: ThresholdOverrides;
  onThresholdOverrideChange?: (key: ThresholdOverrideKey, value: number | boolean) => void;
  hasPendingOverrides?: boolean;
};

export default function StrategyAnalyzerEntryConditionsContent({
  effectiveConditionsMarker,
  stableConditionsLiveAnalysis,
  isScrubbingLiveEval,
  isThresholdInteractive,
  thresholdOverrides,
  onThresholdOverrideChange,
  hasPendingOverrides,
}: Props) {
  return (
    <div className="sa-entry-conditions-surface">
      <StrategyConditionsPanel
        marker={effectiveConditionsMarker}
        liveAnalysis={stableConditionsLiveAnalysis}
        isThresholdInteractive={isThresholdInteractive}
        thresholdOverrides={thresholdOverrides}
        onThresholdOverrideChange={onThresholdOverrideChange}
        hasPendingOverrides={hasPendingOverrides}
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
