import type {
  DecisionPanelEntryQualityDiagnosticsLike,
  DecisionPanelLevelContextLike,
  DecisionPanelRenderDetailLabel,
  DecisionPanelRenderFlag,
  DecisionPanelRenderSectionHeader,
} from "./decision-panel-types";

type Props = {
  levelContext: DecisionPanelLevelContextLike;
  entryQualityDiagnostics: DecisionPanelEntryQualityDiagnosticsLike;
  renderSectionHeader: DecisionPanelRenderSectionHeader;
  renderDetailLabel: DecisionPanelRenderDetailLabel;
  renderYesNo: DecisionPanelRenderFlag;
  renderGateStatus: DecisionPanelRenderFlag;
};

export default function DecisionPanelDetailGateDiagnosticsSections({
  levelContext,
  entryQualityDiagnostics,
  renderSectionHeader,
  renderDetailLabel,
  renderYesNo,
  renderGateStatus,
}: Props) {
  return (
    <>
      {levelContext.hasAny && (
        <>
          {renderSectionHeader("Level Context Gate")}
          <div className="detail-item">
            {renderDetailLabel("Status")}
            <span className="detail-value">{renderGateStatus(levelContext.payload.passed)}</span>
          </div>
          <div className="detail-item">
            {renderDetailLabel("Strategy", "Strategy (Gate)")}
            <span className="detail-value">
              {String(levelContext.payload.strategy_key || "n/a")}
            </span>
          </div>
          <div className="detail-item">
            {renderDetailLabel("Gate Reason")}
            <span className="detail-value">{String(levelContext.payload.reason || "n/a")}</span>
          </div>
          <div className="detail-item">
            {renderDetailLabel("Near Tested Levels", "Near Tested Levels (Gate)")}
            <span className="detail-value">
              {Number(levelContext.payload?.stats?.near_tested_levels_count || 0)}
            </span>
          </div>
          <div className="detail-item">
            {renderDetailLabel("Value Area Position")}
            <span className="detail-value">
              {String(levelContext.payload?.volume_profile?.value_area_position || "n/a")}
            </span>
          </div>
          <div className="detail-item">
            {renderDetailLabel("POC On Trade Side", "POC On Trade Side (Gate)")}
            <span className="detail-value">
              {renderYesNo(levelContext.payload?.volume_profile?.poc_on_trade_side)}
            </span>
          </div>
          <div className="detail-item">
            {renderDetailLabel("Room To Next Opposite Level")}
            <span className="detail-value">
              {levelContext.payload?.room_to_next_opposite_level_pct != null
                ? `${Number(levelContext.payload.room_to_next_opposite_level_pct).toFixed(3)}%`
                : "n/a"}
            </span>
          </div>
          {levelContext.reasons.length > 0 && (
            <div className="detail-item" style={{ gridColumn: "1 / -1" }}>
              {renderDetailLabel("Fail Reasons")}
              <span className="detail-value">{levelContext.reasons.join(", ")}</span>
            </div>
          )}
        </>
      )}

      {entryQualityDiagnostics.hasAny && (
        <>
          {renderSectionHeader("Entry Timing Diagnostics")}
          <div className="detail-item">
            {renderDetailLabel("First-Bar Stop Loss")}
            <span className="detail-value">
              {renderYesNo(entryQualityDiagnostics.payload?.is_first_bar_stop_loss)}
            </span>
          </div>
          <div className="detail-item">
            {renderDetailLabel("Stop Distance")}
            <span className="detail-value">
              {entryQualityDiagnostics.payload?.stop_distance_pct != null
                ? `${Number(entryQualityDiagnostics.payload.stop_distance_pct).toFixed(3)}%`
                : "n/a"}
            </span>
          </div>
          <div className="detail-item">
            {renderDetailLabel("VWAP Distance")}
            <span className="detail-value">
              {entryQualityDiagnostics.payload?.vwap_distance_pct != null
                ? `${Number(entryQualityDiagnostics.payload.vwap_distance_pct).toFixed(3)}%`
                : "n/a"}
            </span>
          </div>
          <div className="detail-item">
            {renderDetailLabel("Confluence Score")}
            <span className="detail-value">
              {entryQualityDiagnostics.payload?.near_confluence_score != null
                ? Number(entryQualityDiagnostics.payload.near_confluence_score)
                : "n/a"}
            </span>
          </div>
          <div className="detail-item">
            {renderDetailLabel("Near Tested Levels", "Near Tested Levels (Entry Timing)")}
            <span className="detail-value">
              {entryQualityDiagnostics.payload?.near_tested_levels_count != null
                ? Number(entryQualityDiagnostics.payload.near_tested_levels_count)
                : "n/a"}
            </span>
          </div>
          <div className="detail-item">
            {renderDetailLabel("POC On Trade Side", "POC On Trade Side (Entry Timing)")}
            <span className="detail-value">
              {renderYesNo(entryQualityDiagnostics.payload?.poc_on_trade_side)}
            </span>
          </div>
          {entryQualityDiagnostics.tags.length > 0 && (
            <div className="detail-item" style={{ gridColumn: "1 / -1" }}>
              {renderDetailLabel("Diagnosis Tags")}
              <span className="detail-value">{entryQualityDiagnostics.tags.join(", ")}</span>
            </div>
          )}
        </>
      )}
    </>
  );
}
