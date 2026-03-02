import type { ReactNode } from "react";
import ExternalWindowPortal from "../ExternalWindowPortal";
import type {
  BooleanStateSetter,
  StrategyAnalyzerConditionsPanelBadge,
} from "./types";

type Props = {
  ticker: string;
  analyzerDecisionEventsCount: number;
  hasConditionsPanelData: boolean;
  conditionsPanelBadge: StrategyAnalyzerConditionsPanelBadge;
  isConditionsDetached: boolean;
  isDecisionsDetached: boolean;
  setIsConditionsDetached: BooleanStateSetter;
  setIsDecisionsDetached: BooleanStateSetter;
  entryConditionsContent: ReactNode;
  decisionsContent: ReactNode;
};

export default function StrategyAnalyzerAttachedPanels({
  ticker,
  analyzerDecisionEventsCount,
  hasConditionsPanelData,
  conditionsPanelBadge,
  isConditionsDetached,
  isDecisionsDetached,
  setIsConditionsDetached,
  setIsDecisionsDetached,
  entryConditionsContent,
  decisionsContent,
}: Props) {
  return (
    <>
      <div className="sa-attached-stack">
        <div
          className={`card sa-stack-card ${hasConditionsPanelData ? "sa-stack-card-fill" : ""}`}
        >
          <div className="card-header sa-stack-card-header">
            <span className="card-title">Entry Conditions</span>
            <div className="sa-stack-card-meta">
              {conditionsPanelBadge ? (
                <span
                  className={`sa-badge-note ${
                    conditionsPanelBadge.tone === "accent" ? "is-accent" : ""
                  }`}
                >
                  {conditionsPanelBadge.label}
                </span>
              ) : null}
              <button
                type="button"
                className="sa-detach-btn"
                onClick={() => setIsConditionsDetached((previous) => !previous)}
              >
                {isConditionsDetached ? "Dock" : "Open window"}
              </button>
            </div>
          </div>
          {isConditionsDetached ? (
            <div className="sa-stack-note">Opened in separate window.</div>
          ) : (
            entryConditionsContent
          )}
        </div>

        <div className="card decision-panel sa-stack-card sa-stack-card-fill">
          <div className="card-header sa-stack-card-header">
            <span className="card-title">Decisions</span>
            <div className="sa-stack-card-meta">
              <span className="sa-badge-note">{analyzerDecisionEventsCount} total</span>
              <button
                type="button"
                className="sa-detach-btn"
                onClick={() => setIsDecisionsDetached((previous) => !previous)}
              >
                {isDecisionsDetached ? "Dock" : "Open window"}
              </button>
            </div>
          </div>
          {isDecisionsDetached ? (
            <div className="sa-stack-note">Opened in separate window.</div>
          ) : (
            decisionsContent
          )}
        </div>
      </div>

      <ExternalWindowPortal
        isOpen={Boolean(isConditionsDetached)}
        title={`Entry Conditions - ${ticker}`}
        windowName="strategy-analyzer-conditions"
        width={560}
        height={780}
        onClose={() => setIsConditionsDetached(() => false)}
      >
        <div className="card sa-detached-surface">
          <div className="card-header sa-stack-card-header">
            <span className="card-title">Entry Conditions</span>
            <button
              type="button"
              className="sa-detach-btn"
              onClick={() => setIsConditionsDetached(() => false)}
            >
              Dock
            </button>
          </div>
          {entryConditionsContent}
        </div>
      </ExternalWindowPortal>

      <ExternalWindowPortal
        isOpen={Boolean(isDecisionsDetached)}
        title={`Decisions - ${ticker}`}
        windowName="strategy-analyzer-decisions"
        width={760}
        height={860}
        onClose={() => setIsDecisionsDetached(() => false)}
      >
        <div className="card decision-panel sa-detached-surface">
          <div className="card-header sa-stack-card-header">
            <span className="card-title">Decisions</span>
            <div className="sa-stack-card-meta">
              <span className="sa-badge-note">{analyzerDecisionEventsCount} total</span>
              <button
                type="button"
                className="sa-detach-btn"
                onClick={() => setIsDecisionsDetached(() => false)}
              >
                Dock
              </button>
            </div>
          </div>
          {decisionsContent}
        </div>
      </ExternalWindowPortal>
    </>
  );
}
