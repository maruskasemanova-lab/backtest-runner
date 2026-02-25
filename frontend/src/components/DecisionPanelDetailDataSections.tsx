import type {
  DecisionPanelFormatGenericValue,
  DecisionPanelRenderDetailLabel,
  DecisionPanelRenderSectionHeader,
  DecisionPanelRenderValue,
} from "./decision-panel-types";

type Props = {
  metadata: Record<string, unknown>;
  details: Record<string, unknown> & { metadata?: unknown; costs?: unknown };
  renderSectionHeader: DecisionPanelRenderSectionHeader;
  renderDetailLabel: DecisionPanelRenderDetailLabel;
  renderValue: DecisionPanelRenderValue;
  formatGenericValue: DecisionPanelFormatGenericValue;
};

export default function DecisionPanelDetailDataSections({
  metadata,
  details,
  renderSectionHeader,
  renderDetailLabel,
  renderValue,
  formatGenericValue,
}: Props) {
  return (
    <>
      {Object.keys(metadata).length > 0 && (
        <>
          {renderSectionHeader("Signal Data (All Indicators)")}
          <div style={{ gridColumn: "1 / -1" }}>
            {Object.entries(metadata)
              .filter(([key]) => key !== "strategy")
              .map(([key, value]) => (
                <div key={key} style={{ marginBottom: "8px" }}>
                  <span
                    style={{
                      fontWeight: 600,
                      fontSize: "0.9em",
                      color: "var(--text-primary)",
                    }}
                  >
                    {key}:
                  </span>
                  <div style={{ marginTop: "2px" }}>{renderValue(value, key)}</div>
                </div>
              ))}
          </div>
        </>
      )}

      {Object.entries(details).length > 0 && !details.metadata && !details.costs && (
        <>
          {renderSectionHeader("Additional Details")}
          {Object.entries(details).map(([key, value]) => {
            if (
              [
                "metadata",
                "costs",
                "reasoning",
                "pnl_pct",
                "pnl_usd",
                "pnl_dollars",
                "stop_loss",
                "take_profit",
                "exit_reason",
                "risk_reward",
              ].includes(key)
            ) {
              return null;
            }
            return (
              <div className="detail-item" key={key}>
                {renderDetailLabel(key, {
                  tooltipLabel: key,
                  runtimeValue: value,
                  runtimeSource: `details.${key}`,
                })}
                <span className="detail-value">{formatGenericValue(value)}</span>
              </div>
            );
          })}
        </>
      )}
    </>
  );
}
