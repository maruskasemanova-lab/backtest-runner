import type {
  DecisionPanelIntradayLevelsLike,
  DecisionPanelL2DiagnosticsLike,
  DecisionPanelRenderDetailLabel,
  DecisionPanelRenderFlag,
  DecisionPanelRenderSectionHeader,
} from "./decision-panel-types";

type Props = {
  l2Diagnostics: DecisionPanelL2DiagnosticsLike;
  intradayLevels: DecisionPanelIntradayLevelsLike;
  renderSectionHeader: DecisionPanelRenderSectionHeader;
  renderDetailLabel: DecisionPanelRenderDetailLabel;
  renderEnabled: DecisionPanelRenderFlag;
  t: (text: string) => string;
};

export default function DecisionPanelDetailMarketDiagnosticsSections({
  l2Diagnostics,
  intradayLevels,
  renderSectionHeader,
  renderDetailLabel,
  renderEnabled,
  t,
}: Props) {
  return (
    <>
      {l2Diagnostics.hasAny && (
        <>
          {renderSectionHeader("L2 Diagnostics")}
          {l2Diagnostics.flowScore != null && (
            <div className="detail-item">
              {renderDetailLabel("Flow Score")}
              <span className="detail-value">{l2Diagnostics.flowScore.toFixed(1)}</span>
            </div>
          )}
          {l2Diagnostics.signedAggression != null && (
            <div className="detail-item">
              {renderDetailLabel("Signed Aggression")}
              <span className="detail-value">{l2Diagnostics.signedAggression.toFixed(3)}</span>
            </div>
          )}
          {l2Diagnostics.l2AggressionZ != null && (
            <div className="detail-item">
              {renderDetailLabel("L2 Aggression Z")}
              <span className="detail-value">{l2Diagnostics.l2AggressionZ.toFixed(3)}</span>
            </div>
          )}
          {l2Diagnostics.l2BookPressureZ != null && (
            <div className="detail-item">
              {renderDetailLabel("L2 Book Pressure Z")}
              <span className="detail-value">{l2Diagnostics.l2BookPressureZ.toFixed(3)}</span>
            </div>
          )}
          {l2Diagnostics.absorptionRate != null && (
            <div className="detail-item">
              {renderDetailLabel("Absorption Rate")}
              <span className="detail-value">{l2Diagnostics.absorptionRate.toFixed(3)}</span>
            </div>
          )}
          {l2Diagnostics.largeTraderActivity != null && (
            <div className="detail-item">
              {renderDetailLabel("Large Trader Activity")}
              <span className="detail-value">{l2Diagnostics.largeTraderActivity.toFixed(3)}</span>
            </div>
          )}
          {l2Diagnostics.vwapExecutionFlow != null && (
            <div className="detail-item">
              {renderDetailLabel("VWAP Execution Flow", "VWAP Execution Flow (L2 Diagnostics)")}
              <span className="detail-value">{l2Diagnostics.vwapExecutionFlow.toFixed(3)}</span>
            </div>
          )}
          {l2Diagnostics.sweepDetected != null && (
            <div className="detail-item">
              {renderDetailLabel("Sweep Detected")}
              <span className="detail-value">
                {l2Diagnostics.sweepDetected ? t("yes") : t("no")}
              </span>
            </div>
          )}
          <div className="detail-item">
            {renderDetailLabel("L2 Source")}
            <span className="detail-value">
              {l2Diagnostics.sourcePath || t("Source unavailable")}
            </span>
          </div>
        </>
      )}

      {intradayLevels.hasAny && (
        <>
          {renderSectionHeader("Intraday Levels")}
          <div className="detail-item">
            {renderDetailLabel("Tracker")}
            <span className="detail-value">{renderEnabled(intradayLevels.enabled)}</span>
          </div>
          <div className="detail-item">
            {renderDetailLabel("Active / Tested / Broken")}
            <span className="detail-value">
              {Number(intradayLevels.stats.active_levels || 0)} /{" "}
              {Number(intradayLevels.stats.tested_levels || 0)} /{" "}
              {Number(intradayLevels.stats.broken_levels || 0)}
            </span>
          </div>
          <div className="detail-item">
            {renderDetailLabel("Bounce / Break Events")}
            <span className="detail-value">
              {Number(intradayLevels.stats.bounce_events || 0)} /{" "}
              {Number(intradayLevels.stats.break_events || 0)}
            </span>
          </div>
          <div className="detail-item">
            {renderDetailLabel("POC")}
            <span className="detail-value">
              {intradayLevels.volumeProfile.poc_price != null
                ? Number(intradayLevels.volumeProfile.poc_price).toFixed(2)
                : "n/a"}
            </span>
          </div>
          <div className="detail-item">
            {renderDetailLabel("Value Area")}
            <span className="detail-value">
              {intradayLevels.volumeProfile.value_area_low != null &&
              intradayLevels.volumeProfile.value_area_high != null
                ? `${Number(intradayLevels.volumeProfile.value_area_low).toFixed(2)} - ${Number(intradayLevels.volumeProfile.value_area_high).toFixed(2)}`
                : "n/a"}
            </span>
          </div>
          {intradayLevels.latestEvent && (
            <div className="detail-item">
              {renderDetailLabel("Latest Event")}
              <span className="detail-value">
                {String(intradayLevels.latestEvent.event_type || "event")}
                {intradayLevels.latestEvent.direction
                  ? ` (${String(intradayLevels.latestEvent.direction)})`
                  : ""}
                {intradayLevels.latestEvent.price != null
                  ? ` @ ${Number(intradayLevels.latestEvent.price).toFixed(2)}`
                  : ""}
              </span>
            </div>
          )}
        </>
      )}
    </>
  );
}
