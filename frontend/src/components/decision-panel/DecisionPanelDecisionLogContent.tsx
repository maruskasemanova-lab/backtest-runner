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
            decisionLog.payload?.decision_state?.selected_strategy ||
              selectedMarker?.strategy ||
              "n/a",
          )}
        </span>
      </div>
      <div className="detail-item">
        {renderDetailLabel("SL Reason")}
        <span className="detail-value">
          {renderReasonValue(decisionLog.payload?.context_risk?.sl_reason)}
        </span>
      </div>
      {(() => {
        const slReason = String(
          decisionLog.payload?.context_risk?.sl_reason || "",
        );
        const isStrategySL = slReason === "strategy_stop_loss";
        const isCappedFixedFloor = slReason.startsWith("capped_fixed_floor");
        const isFixedStopLossPct = slReason.startsWith("fixed_stop_loss_pct");

        if (!isStrategySL && !isCappedFixedFloor && !isFixedStopLossPct)
          return null;

        let mathFormula = "";

        if (isCappedFixedFloor || isFixedStopLossPct) {
          const riskControls = (decisionLog.payload?.risk_controls ||
            {}) as Record<string, unknown>;
          const minSlPct =
            riskControls.context_risk_min_sl_pct ??
            riskControls.min_sl_pct ??
            "N/A";
          const fixedPct = riskControls.fixed_stop_loss_pct ?? "N/A";

          if (isCappedFixedFloor) {
            const val = slReason.split(":")[1] || minSlPct;
            mathFormula = `max(Strategy SL, Minimum Floor SL [${val}%])`;
          } else {
            const val = slReason.split(":")[1] || fixedPct;
            mathFormula = `Entry ± Fixed ${val}%`;
          }
        } else if (isStrategySL) {
          const signalMeta = (decisionLog.payload?.signal_metadata ||
            decisionLog.payload?.metadata ||
            {}) as Record<string, unknown>;
          if (signalMeta.stop_type === "hybrid_price_space") {
            const sideStr = String(
              selectedMarker?.side || signalMeta.flow_direction || "",
            );
            const isLong =
              sideStr.toLowerCase().includes("long") ||
              sideStr.toLowerCase().includes("support");

            const atrStop = signalMeta.atr_stop;
            const levelStop = signalMeta.level_stop;

            if (atrStop != null && levelStop != null) {
              mathFormula = isLong
                ? `max(ATR Stop: $${atrStop}, Level Stop: $${levelStop})`
                : `min(ATR Stop: $${atrStop}, Level Stop: $${levelStop})`;
            }
          }
        }

        if (!mathFormula) return null;

        return (
          <div className="detail-item">
            {renderDetailLabel("SL Logic")}
            <span className="detail-value decision-detail-secondary">
              {mathFormula}
            </span>
          </div>
        );
      })()}
      <div className="detail-item">
        {renderDetailLabel("TP Reason")}
        <span className="detail-value">
          {renderReasonValue(decisionLog.payload?.context_risk?.tp_reason)}
        </span>
      </div>
      {(() => {
        const tpReason = decisionLog.payload?.context_risk?.tp_reason;
        if (tpReason !== "strategy_take_profit") return null;

        const signalMeta = (decisionLog.payload?.signal_metadata ||
          decisionLog.payload?.metadata ||
          {}) as Record<string, unknown>;
        if (signalMeta.stop_type !== "hybrid_price_space") return null;

        const sideStr = String(
          selectedMarker?.side || signalMeta.flow_direction || "",
        );
        const isLong =
          sideStr.toLowerCase().includes("long") ||
          sideStr.toLowerCase().includes("support");

        const pocPrice = signalMeta.poc_price;

        // Try context_risk effective_rr first, then fallback to signal_metadata effective_rr
        let effectiveRr = decisionLog.payload?.context_risk?.effective_rr;
        if (effectiveRr == null) {
          effectiveRr = signalMeta.effective_rr;
        }

        const rr = Number(effectiveRr || 0).toFixed(2);

        let mathFormula = `Entry ± (Risk × ${rr} R:R)`;
        if (pocPrice != null) {
          mathFormula = isLong
            ? `min(Base TP [RR ${rr}], POC: $${pocPrice})`
            : `max(Base TP [RR ${rr}], POC: $${pocPrice})`;
        }

        return (
          <div className="detail-item">
            {renderDetailLabel("TP Logic")}
            <span className="detail-value decision-detail-secondary">
              {mathFormula}
            </span>
          </div>
        );
      })()}
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
        {renderDetailLabel(
          "VWAP Execution Flow",
          "VWAP Execution Flow (Decision Log)",
        )}
        <span className="detail-value">
          {decisionLog.payload?.flow_snapshot?.vwap_execution_flow != null
            ? Number(
                decisionLog.payload.flow_snapshot.vwap_execution_flow,
              ).toFixed(3)
            : "n/a"}
        </span>
      </div>
      <div className="detail-item decision-detail-span-full">
        {renderDetailLabel("Complete Decision Payload")}
        <pre className="decision-raw-json ui-mt-sm">
          {JSON.stringify(decisionLog.payload, null, 2)}
        </pre>
      </div>
    </div>
  );
}
