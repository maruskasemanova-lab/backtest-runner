import type {
  DecisionPanelDetailsLike,
  DecisionPanelFormatPrice,
  DecisionPanelFormatTime,
  DecisionPanelMarkerLike,
  DecisionPanelMetadataLike,
  DecisionPanelRenderDetailLabel,
  DecisionPanelRenderSectionHeader,
  DecisionPanelResolvePnlPct,
} from "./decision-panel-types";

type Props = {
  selectedMarker: DecisionPanelMarkerLike;
  details: DecisionPanelDetailsLike;
  metadata: DecisionPanelMetadataLike;
  renderDetailLabel: DecisionPanelRenderDetailLabel;
  renderSectionHeader: DecisionPanelRenderSectionHeader;
  renderCostLabel: (key: string) => string;
  resolvePnlPct: DecisionPanelResolvePnlPct;
  formatTime: DecisionPanelFormatTime;
  formatPrice: DecisionPanelFormatPrice;
};

export default function DecisionPanelDetailCoreSections({
  selectedMarker,
  details,
  metadata,
  renderDetailLabel,
  renderSectionHeader,
  renderCostLabel,
  resolvePnlPct,
  formatTime,
  formatPrice,
}: Props) {
  return (
    <>
      <div className="detail-item">
        {renderDetailLabel("Event Type")}
        <span className="detail-value">{selectedMarker.marker_type || "n/a"}</span>
      </div>
      <div className="detail-item">
        {renderDetailLabel("Time")}
        <span className="detail-value">{formatTime(selectedMarker.timestamp)}</span>
      </div>
      <div className="detail-item">
        {renderDetailLabel("Price")}
        <span className="detail-value">{formatPrice(selectedMarker.price)}</span>
      </div>
      {selectedMarker.side && (
        <div className="detail-item">
          {renderDetailLabel("Side")}
          <span
            className="detail-value"
            style={{
              color: selectedMarker.side === "long" ? "var(--accent-green)" : "var(--accent-red)",
              fontWeight: 700,
            }}
          >
            {String(selectedMarker.side).toUpperCase()}
          </span>
        </div>
      )}

      {selectedMarker.marker_type === "entry_executed" && (
        <>
          <div className="detail-item">
            {renderDetailLabel("Strategy", "Strategy (Entry)")}
            <span className="detail-value">
              {selectedMarker.strategy || metadata.strategy || "Unknown"}
            </span>
          </div>
          <div className="detail-item">
            {renderDetailLabel("Confidence")}
            <span className="detail-value">
              {selectedMarker.confidence != null
                ? Number(selectedMarker.confidence).toFixed(0)
                : "N/A"}
              %
            </span>
          </div>
          {details.stop_loss && (
            <div className="detail-item">
              {renderDetailLabel("Stop Loss")}
              <span className="detail-value">${details.stop_loss.toFixed(2)}</span>
            </div>
          )}
          {details.take_profit && (
            <div className="detail-item">
              {renderDetailLabel("Take Profit")}
              <span className="detail-value">${details.take_profit.toFixed(2)}</span>
            </div>
          )}
          {details.risk_reward && (
            <div className="detail-item">
              {renderDetailLabel("R:R Ratio")}
              <span className="detail-value">{details.risk_reward.toFixed(2)}</span>
            </div>
          )}
        </>
      )}

      {["exit_executed", "stop_loss_hit", "take_profit_hit"].includes(
        String(selectedMarker.marker_type || ""),
      ) && (
        <>
          {(() => {
            const slReason = String(details.exit_reason || "");
            const isStrategySL = slReason === "strategy_stop_loss";
            const isCappedFixedFloor = slReason.startsWith("capped_fixed_floor");
            const isFixedStopLossPct = slReason.startsWith("fixed_stop_loss_pct");

            if (!isStrategySL && !isCappedFixedFloor && !isFixedStopLossPct) return null;

            const signalMeta = (details.signal_metadata || metadata || {}) as Record<string, unknown>;
            const sideStr = String(selectedMarker.side || signalMeta.flow_direction || "");
            const isLong = sideStr.toLowerCase().includes("long") || sideStr.toLowerCase().includes("support");

            let mathFormula = "";

            if (isCappedFixedFloor || isFixedStopLossPct) {
               const riskControls = ((details.risk_controls || signalMeta.risk_controls || metadata?.risk_controls || {}) as Record<string, unknown>);
               const minSlPct = riskControls.context_risk_min_sl_pct ?? riskControls.min_sl_pct ?? "N/A";
               const fixedPct = riskControls.fixed_stop_loss_pct ?? "N/A";
               
               if (isCappedFixedFloor) {
                 const val = slReason.split(":")[1] || minSlPct;
                 mathFormula = `max(Strategy SL, Minimum Floor SL [${val}%])`;
               } else {
                 const val = slReason.split(":")[1] || fixedPct;
                 mathFormula = `Entry ± Fixed ${val}%`;
               }
            } else if (isStrategySL && signalMeta.stop_type === "hybrid_price_space") {
              const atrStop = signalMeta.atr_stop;
              const levelStop = signalMeta.level_stop;
              if (atrStop != null && levelStop != null) {
                mathFormula = isLong 
                  ? `max(ATR Stop: $${atrStop}, Level Stop: $${levelStop})`
                  : `min(ATR Stop: $${atrStop}, Level Stop: $${levelStop})`;
              }
            }

            if (!mathFormula) return null;

            return (
              <div className="detail-item">
                {renderDetailLabel("SL Logic")}
                <span className="detail-value" style={{ fontSize: "0.9em", color: "var(--text-secondary)" }}>
                  {mathFormula}
                </span>
              </div>
            );
          })()}
          {(() => {
            const tpReason = String(details.exit_reason || "");
            if (tpReason !== "strategy_take_profit") return null;

            const signalMeta = (details.signal_metadata || metadata || {}) as Record<string, unknown>;
            if (signalMeta.stop_type !== "hybrid_price_space") return null;

            const sideStr = String(selectedMarker.side || signalMeta.flow_direction || "");
            const isLong = sideStr.toLowerCase().includes("long") || sideStr.toLowerCase().includes("support");

            const pocPrice = signalMeta.poc_price;
            
            // Try explicit RR from details/risk_controls first, then metadata
            let effectiveRr = (details.risk_controls as Record<string, unknown>)?.effective_rr;
            if (effectiveRr == null) {
               effectiveRr = details.risk_reward ?? signalMeta.effective_rr;
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
                <span className="detail-value" style={{ fontSize: "0.9em", color: "var(--text-secondary)" }}>
                   {mathFormula}
                </span>
              </div>
            );
          })()}
          {(details.pnl_dollars != null || details.pnl_usd != null) && (
            <div className="detail-item">
              {renderDetailLabel("PnL")}
              <span
                className={`detail-value ${
                  (resolvePnlPct(details, details.pnl_dollars ?? details.pnl_usd) ?? 0) >= 0
                    ? "positive"
                    : "negative"
                }`}
              >
                {(() => {
                  const pct = resolvePnlPct(details, details.pnl_dollars ?? details.pnl_usd);
                  if (pct == null) return "n/a";
                  return `${pct >= 0 ? "+" : ""}${pct.toFixed(2)}%`;
                })()}
              </span>
            </div>
          )}
          {(details.pnl_dollars != null || details.pnl_usd != null) && (
            <div className="detail-item">
              {renderDetailLabel("PnL $")}
              <span
                className={`detail-value ${
                  (details.pnl_dollars ?? details.pnl_usd) >= 0 ? "positive" : "negative"
                }`}
              >
                {(details.pnl_dollars ?? details.pnl_usd) >= 0 ? "+" : ""}$
                {Number(details.pnl_dollars ?? details.pnl_usd).toFixed(2)}
              </span>
            </div>
          )}
          {details.bars_held && (
            <div className="detail-item">
              {renderDetailLabel("Bars Held")}
              <span className="detail-value">{details.bars_held}</span>
            </div>
          )}
        </>
      )}

      {details.reasoning && (
        <div
          style={{
            gridColumn: "1 / -1",
            marginTop: "10px",
            padding: "10px",
            background: "rgba(15, 23, 42, 0.04)",
            borderRadius: "4px",
          }}
        >
          <div style={{ marginBottom: "5px" }}>
            {renderDetailLabel("Reasoning", "Reasoning", { fontWeight: 600 })}
          </div>
          <div
            className="detail-value"
            style={{ whiteSpace: "normal", fontSize: "0.9em", lineHeight: "1.4" }}
          >
            {details.reasoning}
          </div>
        </div>
      )}

      {details.costs && (
        <>
          {renderSectionHeader("Trading Costs")}
          {Object.entries(details.costs).map(([k, v]) => (
            <div className="detail-item" key={`cost-${k}`}>
              {renderDetailLabel(renderCostLabel(k), {
                tooltipLabel: renderCostLabel(k),
                runtimeValue: v,
                runtimeSource: `details.costs.${k}`,
              })}
              <span className="detail-value">${Number(v).toFixed(4)}</span>
            </div>
          ))}
        </>
      )}
    </>
  );
}
