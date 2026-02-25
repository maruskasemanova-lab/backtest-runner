import type { CSSProperties, ReactNode } from "react";
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
  detachedToggleButtonStyle: CSSProperties;
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
  detachedToggleButtonStyle,
  isConditionsDetached,
  isDecisionsDetached,
  setIsConditionsDetached,
  setIsDecisionsDetached,
  entryConditionsContent,
  decisionsContent,
}: Props) {
  return (
    <>
      <aside
        style={{
          flex: "0 0 380px",
          width: "380px",
          maxWidth: "100%",
          minHeight: 0,
          display: "flex",
          flexDirection: "column",
          gap: "0.75rem",
          overflow: "hidden",
        }}
      >
        <div
          className="card"
          style={{
            flex: hasConditionsPanelData ? "1 1 0" : "0 0 auto",
            minHeight: hasConditionsPanelData ? 120 : 0,
            display: "flex",
            flexDirection: "column",
            overflow: "hidden",
            position: "relative",
          }}
        >
          <div
            className="card-header"
            style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}
          >
            <span className="card-title">Entry Conditions</span>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <span style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>
                {conditionsPanelBadge ? (
                  <span
                    style={{
                      color:
                        conditionsPanelBadge.tone === "accent"
                          ? "var(--accent-blue, #3b82f6)"
                          : "var(--text-muted)",
                      fontWeight: conditionsPanelBadge.tone === "accent" ? 600 : 500,
                      fontSize: "0.78rem",
                    }}
                  >
                    {conditionsPanelBadge.label}
                  </span>
                ) : null}
              </span>
              <button
                type="button"
                style={detachedToggleButtonStyle}
                onClick={() => setIsConditionsDetached((previous) => !previous)}
              >
                {isConditionsDetached ? "Dock" : "Open window"}
              </button>
            </div>
          </div>
          {isConditionsDetached ? (
            <div style={{ padding: "0.75rem 1rem", color: "var(--text-muted)", fontSize: "0.8rem" }}>
              Opened in separate window.
            </div>
          ) : (
            entryConditionsContent
          )}
        </div>

        <div
          className="card decision-panel"
          style={{
            flex: "1 1 0",
            minHeight: 120,
            display: "flex",
            flexDirection: "column",
            overflow: "hidden",
          }}
        >
          <div
            className="card-header"
            style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}
          >
            <span className="card-title">Decisions</span>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <span style={{ color: "var(--text-muted)", fontSize: "0.8rem" }}>
                {analyzerDecisionEventsCount} total
              </span>
              <button
                type="button"
                style={detachedToggleButtonStyle}
                onClick={() => setIsDecisionsDetached((previous) => !previous)}
              >
                {isDecisionsDetached ? "Dock" : "Open window"}
              </button>
            </div>
          </div>
          {isDecisionsDetached ? (
            <div style={{ padding: "0.75rem 1rem", color: "var(--text-muted)", fontSize: "0.8rem" }}>
              Opened in separate window.
            </div>
          ) : (
            decisionsContent
          )}
        </div>
      </aside>

      <ExternalWindowPortal
        isOpen={Boolean(isConditionsDetached)}
        title={`Entry Conditions - ${ticker}`}
        windowName="strategy-analyzer-conditions"
        width={560}
        height={780}
        onClose={() => setIsConditionsDetached(() => false)}
      >
        <div
          className="card"
          style={{
            margin: 0,
            borderRadius: 0,
            height: "100%",
            display: "flex",
            flexDirection: "column",
            overflow: "hidden",
            position: "relative",
          }}
        >
          <div
            className="card-header"
            style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}
          >
            <span className="card-title">Entry Conditions</span>
            <button
              type="button"
              style={detachedToggleButtonStyle}
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
        <div
          className="card decision-panel"
          style={{
            margin: 0,
            borderRadius: 0,
            height: "100%",
            display: "flex",
            flexDirection: "column",
            overflow: "hidden",
          }}
        >
          <div
            className="card-header"
            style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}
          >
            <span className="card-title">Decisions</span>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <span style={{ color: "var(--text-muted)", fontSize: "0.8rem" }}>
                {analyzerDecisionEventsCount} total
              </span>
              <button
                type="button"
                style={detachedToggleButtonStyle}
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
