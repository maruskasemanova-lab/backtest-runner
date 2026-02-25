import type {
  DecisionPanelBreakEvenBufferLike,
  DecisionPanelBreakEvenComputedLike,
  DecisionPanelBreakEvenPayloadLike,
  DecisionPanelDecisionLogLike,
  DecisionPanelDetailsLike,
  DecisionPanelEntryQualityDiagnosticsLike,
  DecisionPanelFormatGenericValue,
  DecisionPanelFormatPctValue,
  DecisionPanelFormatPrice,
  DecisionPanelFormatTime,
  DecisionPanelIntradayLevelsLike,
  DecisionPanelL2DiagnosticsLike,
  DecisionPanelLevelContextLike,
  DecisionPanelMarkerLike,
  DecisionPanelMetadataLike,
  DecisionPanelRenderBreakEvenValue,
  DecisionPanelRenderDetailLabel,
  DecisionPanelRenderFlag,
  DecisionPanelRenderReasonValue,
  DecisionPanelRenderSectionHeader,
  DecisionPanelRenderValue,
  DecisionPanelResolvePnlPct,
} from "./decision-panel-types";
import DecisionPanelDecisionLogContent from "./DecisionPanelDecisionLogContent";
import DecisionPanelDetailCoreSections from "./DecisionPanelDetailCoreSections";
import DecisionPanelDetailDataSections from "./DecisionPanelDetailDataSections";
import DecisionPanelDetailGateDiagnosticsSections from "./DecisionPanelDetailGateDiagnosticsSections";
import DecisionPanelDetailMarketDiagnosticsSections from "./DecisionPanelDetailMarketDiagnosticsSections";

type Props = {
  detailTab: string;
  selectedMarker: DecisionPanelMarkerLike;
  details: DecisionPanelDetailsLike;
  metadata: DecisionPanelMetadataLike;
  l2Diagnostics: DecisionPanelL2DiagnosticsLike;
  intradayLevels: DecisionPanelIntradayLevelsLike;
  levelContext: DecisionPanelLevelContextLike;
  entryQualityDiagnostics: DecisionPanelEntryQualityDiagnosticsLike;
  decisionLog: DecisionPanelDecisionLogLike;
  t: (text: string) => string;
  renderDetailLabel: DecisionPanelRenderDetailLabel;
  renderSectionHeader: DecisionPanelRenderSectionHeader;
  renderCostLabel: (key: string) => string;
  resolvePnlPct: DecisionPanelResolvePnlPct;
  formatTime: DecisionPanelFormatTime;
  formatPrice: DecisionPanelFormatPrice;
  renderEnabled: DecisionPanelRenderFlag;
  renderYesNo: DecisionPanelRenderFlag;
  renderGateStatus: DecisionPanelRenderFlag;
  renderValue: DecisionPanelRenderValue;
  formatGenericValue: DecisionPanelFormatGenericValue;
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

export default function DecisionPanelDetailBody({
  detailTab,
  selectedMarker,
  details,
  metadata,
  l2Diagnostics,
  intradayLevels,
  levelContext,
  entryQualityDiagnostics,
  decisionLog,
  t,
  renderDetailLabel,
  renderSectionHeader,
  renderCostLabel,
  resolvePnlPct,
  formatTime,
  formatPrice,
  renderEnabled,
  renderYesNo,
  renderGateStatus,
  renderValue,
  formatGenericValue,
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
  if (detailTab === "raw") {
    return <pre className="decision-raw-json">{JSON.stringify(selectedMarker, null, 2)}</pre>;
  }

  if (detailTab === "decision_log") {
    return (
      <DecisionPanelDecisionLogContent
        renderDetailLabel={renderDetailLabel}
        decisionLog={decisionLog}
        selectedMarker={selectedMarker}
        renderReasonValue={renderReasonValue}
        breakEvenPayload={breakEvenPayload}
        renderBreakEvenTrigger={renderBreakEvenTrigger}
        renderBreakEvenProof={renderBreakEvenProof}
        breakEvenStopDisplayValue={breakEvenStopDisplayValue}
        breakEvenComputed={breakEvenComputed}
        breakEvenBuffer={breakEvenBuffer}
        breakEvenAntiSpikeSummary={breakEvenAntiSpikeSummary}
        formatPctValue={formatPctValue}
      />
    );
  }

  return (
    <div className="detail-grid">
      <DecisionPanelDetailCoreSections
        selectedMarker={selectedMarker}
        details={details}
        metadata={metadata}
        renderDetailLabel={renderDetailLabel}
        renderSectionHeader={renderSectionHeader}
        renderCostLabel={renderCostLabel}
        resolvePnlPct={resolvePnlPct}
        formatTime={formatTime}
        formatPrice={formatPrice}
      />

      <DecisionPanelDetailMarketDiagnosticsSections
        l2Diagnostics={l2Diagnostics}
        intradayLevels={intradayLevels}
        renderSectionHeader={renderSectionHeader}
        renderDetailLabel={renderDetailLabel}
        renderEnabled={renderEnabled}
        t={t}
      />

      <DecisionPanelDetailGateDiagnosticsSections
        levelContext={levelContext}
        entryQualityDiagnostics={entryQualityDiagnostics}
        renderSectionHeader={renderSectionHeader}
        renderDetailLabel={renderDetailLabel}
        renderYesNo={renderYesNo}
        renderGateStatus={renderGateStatus}
      />

      <DecisionPanelDetailDataSections
        metadata={metadata}
        details={details}
        renderSectionHeader={renderSectionHeader}
        renderDetailLabel={renderDetailLabel}
        renderValue={renderValue}
        formatGenericValue={formatGenericValue}
      />
    </div>
  );
}
