import DecisionPanel from "../DecisionPanel";
import type { StrategyAnalyzerDecisionMarker } from "./types";

type Props = {
  analyzerDecisionEvents: StrategyAnalyzerDecisionMarker[];
  selectedMarker: StrategyAnalyzerDecisionMarker | null;
  onDecisionSelectMarker?: (marker: StrategyAnalyzerDecisionMarker) => void;
};

export default function StrategyAnalyzerDecisionsContent({
  analyzerDecisionEvents,
  selectedMarker,
  onDecisionSelectMarker,
}: Props) {
  const decisionSelectHandler = onDecisionSelectMarker || (() => {});

  return (
    <div
      className="card-body"
      style={{
        flex: 1,
        minHeight: 0,
        overflow: "hidden",
        display: "flex",
        flexDirection: "column",
      }}
    >
      <DecisionPanel
        markers={analyzerDecisionEvents}
        selectedMarker={selectedMarker}
        onSelectMarker={decisionSelectHandler}
      />
    </div>
  );
}
