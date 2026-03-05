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

function PanelDockButton({
  detached,
  onClick,
}: {
  detached: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      className="sa-detach-btn sa-detach-btn-compact"
      onClick={onClick}
    >
      {detached ? "Dock panel" : "Pop out"}
    </button>
  );
}

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
        <div className="card decision-panel sa-stack-card sa-stack-card-fill sa-stack-card-decisions">
          <div className="card-header sa-stack-card-header">
            <div className="sa-stack-card-heading">
              <span className="card-title">Decision Tape</span>
              <span className="sa-stack-card-subtitle">
                Chronological replay log for every state change, order and exit.
              </span>
            </div>
            <div className="sa-stack-card-meta">
              <span className="sa-badge-note">{analyzerDecisionEventsCount} events</span>
              <PanelDockButton
                detached={isDecisionsDetached}
                onClick={() => setIsDecisionsDetached((previous) => !previous)}
              />
            </div>
          </div>
          {isDecisionsDetached ? (
            <div className="sa-stack-note">Decision Tape is opened in a separate window.</div>
          ) : (
            decisionsContent
          )}
        </div>

        <div className="card sa-stack-card sa-stack-card-entry">
          <div className="card-header sa-stack-card-header">
            <div className="sa-stack-card-heading">
              <span className="card-title">Entry Audit</span>
              <span className="sa-stack-card-subtitle">
                Gate-by-gate view of the selected bar so you can see what blocked or allowed the trade.
              </span>
            </div>
            <div className="sa-stack-card-meta">
              {conditionsPanelBadge ? (
                <span
                  className={`sa-badge-note ${
                    conditionsPanelBadge.tone === "accent" ? "is-accent" : ""
                  }`}
                >
                  {conditionsPanelBadge.label}
                </span>
              ) : (
                <span className="sa-badge-note">
                  {hasConditionsPanelData ? "Audit ready" : "Select a bar or decision"}
                </span>
              )}
              <PanelDockButton
                detached={isConditionsDetached}
                onClick={() => setIsConditionsDetached((previous) => !previous)}
              />
            </div>
          </div>
          {isConditionsDetached ? (
            <div className="sa-stack-note">Entry Audit is opened in a separate window.</div>
          ) : (
            entryConditionsContent
          )}
        </div>
      </div>

      <ExternalWindowPortal
        isOpen={Boolean(isDecisionsDetached)}
        title={`Decision Tape - ${ticker}`}
        windowName="strategy-analyzer-decisions"
        width={760}
        height={860}
        onClose={() => setIsDecisionsDetached(() => false)}
      >
        <div className="card decision-panel sa-detached-surface">
          <div className="card-header sa-stack-card-header">
            <div className="sa-stack-card-heading">
              <span className="card-title">Decision Tape</span>
              <span className="sa-stack-card-subtitle">{analyzerDecisionEventsCount} replay events</span>
            </div>
            <PanelDockButton
              detached={true}
              onClick={() => setIsDecisionsDetached(() => false)}
            />
          </div>
          {decisionsContent}
        </div>
      </ExternalWindowPortal>

      <ExternalWindowPortal
        isOpen={Boolean(isConditionsDetached)}
        title={`Entry Audit - ${ticker}`}
        windowName="strategy-analyzer-conditions"
        width={560}
        height={780}
        onClose={() => setIsConditionsDetached(() => false)}
      >
        <div className="card sa-detached-surface">
          <div className="card-header sa-stack-card-header">
            <div className="sa-stack-card-heading">
              <span className="card-title">Entry Audit</span>
              <span className="sa-stack-card-subtitle">
                {hasConditionsPanelData ? "Selected decision diagnostics" : "Waiting for selection"}
              </span>
            </div>
            <PanelDockButton
              detached={true}
              onClick={() => setIsConditionsDetached(() => false)}
            />
          </div>
          {entryConditionsContent}
        </div>
      </ExternalWindowPortal>
    </>
  );
}
