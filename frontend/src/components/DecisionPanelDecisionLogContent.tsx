import type {
  DecisionPanelBreakEvenBufferLike,
  DecisionPanelBreakEvenComputedLike,
  DecisionPanelBreakEvenPayloadLike,
  DecisionPanelDecisionLogLike,
  DecisionPanelFormatPctValue,
  DecisionPanelMarkerLike,
  DecisionPanelRenderBreakEvenValue,
  DecisionPanelRenderDetailLabel,
  DecisionPanelRenderReasonValue,
} from "./decision-panel-types";

type Props = {
  renderDetailLabel: DecisionPanelRenderDetailLabel;
  decisionLog: DecisionPanelDecisionLogLike;
  selectedMarker: DecisionPanelMarkerLike;
  renderReasonValue: DecisionPanelRenderReasonValue;
  breakEvenPayload: DecisionPanelBreakEvenPayloadLike | null;
  renderBreakEvenTrigger: DecisionPanelRenderBreakEvenValue;
  renderBreakEvenProof: DecisionPanelRenderBreakEvenValue;
  breakEvenStopDisplayValue: unknown;
  breakEvenComputed: DecisionPanelBreakEvenComputedLike | null;
  breakEvenBuffer: DecisionPanelBreakEvenBufferLike | null;
  breakEvenAntiSpikeSummary: unknown;
  formatPctValue: DecisionPanelFormatPctValue;
};

export default function DecisionPanelDecisionLogContent({
  renderDetailLabel,
  decisionLog,
  selectedMarker,
  renderReasonValue,
  breakEvenPayload,
  renderBreakEvenTrigger,
  renderBreakEvenProof,
  breakEvenStopDisplayValue,
  breakEvenComputed,
  breakEvenBuffer,
  breakEvenAntiSpikeSummary,
  formatPctValue,
}: Props) {
  return (
    <div className="detail-grid">
      <div className="detail-item">
        {renderDetailLabel("Decision Action")}
        <span className="detail-value">
          {String(decisionLog.payload?.decision_state?.action || "n/a")}
        </span>
      </div>
      <div className="detail-item">
        {renderDetailLabel("Decision Phase")}
        <span className="detail-value">
          {String(decisionLog.payload?.decision_state?.phase || "n/a")}
        </span>
      </div>
      <div className="detail-item">
        {renderDetailLabel("Regime / Micro")}
        <span className="detail-value">
          {String(decisionLog.payload?.decision_state?.regime || "n/a")} /{" "}
          {String(decisionLog.payload?.decision_state?.micro_regime || "n/a")}
        </span>
      </div>
      <div className="detail-item">
        {renderDetailLabel("Selected Strategy")}
        <span className="detail-value">
          {String(
            decisionLog.payload?.decision_state?.selected_strategy || selectedMarker?.strategy || "n/a",
          )}
        </span>
      </div>
      <div className="detail-item">
        {renderDetailLabel("SL Reason")}
        <span className="detail-value">
          {renderReasonValue(decisionLog.payload?.context_risk?.sl_reason)}
        </span>
      </div>
      <div className="detail-item">
        {renderDetailLabel("TP Reason")}
        <span className="detail-value">
          {renderReasonValue(decisionLog.payload?.context_risk?.tp_reason)}
        </span>
      </div>
      <div className="detail-item">
        {renderDetailLabel("Effective RR")}
        <span className="detail-value">
          {decisionLog.payload?.context_risk?.effective_rr != null
            ? Number(decisionLog.payload.context_risk.effective_rr).toFixed(4)
            : "n/a"}
        </span>
      </div>
      <div className="detail-item">
        {renderDetailLabel("Risk %")}
        <span className="detail-value">
          {decisionLog.payload?.context_risk?.risk_pct != null
            ? `${Number(decisionLog.payload.context_risk.risk_pct).toFixed(4)}%`
            : "n/a"}
        </span>
      </div>
      <div className="detail-item">
        {renderDetailLabel("Break-even State")}
        <span className="detail-value">
          {String(breakEvenPayload?.state || "n/a")}
        </span>
      </div>
      <div className="detail-item">
        {renderDetailLabel("Break-even Trigger")}
        <span className="detail-value">
          {renderBreakEvenTrigger(breakEvenPayload?.activation_reason)}
        </span>
      </div>
      <div className="detail-item">
        {renderDetailLabel("Break-even Proof")}
        <span className="detail-value">
          {renderBreakEvenProof(breakEvenPayload)}
        </span>
      </div>
      <div className="detail-item">
        {renderDetailLabel("Break-even Stop")}
        <span className="detail-value">
          {breakEvenStopDisplayValue != null
            ? Number(breakEvenStopDisplayValue).toFixed(4)
            : "n/a"}
        </span>
      </div>
      <div className="detail-item">
        {renderDetailLabel("Break-even Costs %")}
        <span className="detail-value">
          {formatPctValue(breakEvenComputed?.total_costs_pct, 5)}
        </span>
      </div>
      <div className="detail-item">
        {renderDetailLabel("Break-even Buffer %")}
        <span className="detail-value">
          {formatPctValue(breakEvenBuffer?.selected_buffer_pct, 5)}
        </span>
      </div>
      <div className="detail-item">
        {renderDetailLabel("Break-even Anti-Spike")}
        <span className="detail-value">{breakEvenAntiSpikeSummary}</span>
      </div>
      <div className="detail-item">
        {renderDetailLabel("VWAP Execution Flow", "VWAP Execution Flow (Decision Log)")}
        <span className="detail-value">
          {decisionLog.payload?.flow_snapshot?.vwap_execution_flow != null
            ? Number(decisionLog.payload.flow_snapshot.vwap_execution_flow).toFixed(3)
            : "n/a"}
        </span>
      </div>
      <div className="detail-item" style={{ gridColumn: "1 / -1" }}>
        {renderDetailLabel("Complete Decision Payload")}
        <pre className="decision-raw-json" style={{ marginTop: 8 }}>
          {JSON.stringify(decisionLog.payload, null, 2)}
        </pre>
      </div>
    </div>
  );
}
