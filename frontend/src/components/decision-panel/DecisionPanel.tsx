import { memo, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import {
  DECISION_PANEL_LANGUAGE_STORAGE_KEY,
  formatGenericValue,
  formatPrice,
  formatTime,
  formatTooltipRuntimeValue,
  getMarkerIcon,
  isDecisionMarker,
  renderValue,
  resolveDecisionLanguage,
  resolvePnlPct,
  resolveTooltipBaseLabel,
} from "./decision-panel-utils";
import DecisionPanelDetailChrome from "./DecisionPanelDetailChrome";
import DecisionPanelDetailBody from "./DecisionPanelDetailBody";
import DecisionPanelMarkerList from "./DecisionPanelMarkerList";
import useDecisionPanelTooltips from "./useDecisionPanelTooltips";
import useDecisionPanelViewModel from "./useDecisionPanelViewModel";

function DecisionPanel({ markers, selectedMarker, onSelectMarker }) {
  const [detailTab, setDetailTab] = useState('details');
  const [listTab, setListTab] = useState('decisions');
  const [isDetailFullscreen, setIsDetailFullscreen] = useState(false);
  const [uiLanguage, setUiLanguage] = useState(resolveDecisionLanguage);
  const panelRootRef = useRef(null);
  const fallbackDocument = typeof document !== "undefined" ? document : null;
  const portalDocument = panelRootRef.current?.ownerDocument || fallbackDocument;
  const portalWindow = portalDocument?.defaultView || (typeof window !== "undefined" ? window : null);
  const portalBody = portalDocument?.body || (typeof document !== "undefined" ? document.body : null);

  useEffect(() => {
    if (!portalWindow?.localStorage) return;
    portalWindow.localStorage.setItem(DECISION_PANEL_LANGUAGE_STORAGE_KEY, uiLanguage);
  }, [portalWindow, uiLanguage]);

  useEffect(() => {
    if (!selectedMarker) {
      setIsDetailFullscreen(false);
      return;
    }
    setDetailTab('details');
    if (selectedMarker?.__selectionSource === "decision_panel") {
      setIsDetailFullscreen(true);
    } else if (selectedMarker?.__selectionSource === "chart") {
      setIsDetailFullscreen(false);
    }
  }, [
    selectedMarker?.id,
    selectedMarker?.timestamp,
    selectedMarker?.time,
    selectedMarker?.__selectionSource,
  ]);

  useEffect(() => {
    if (!isDetailFullscreen) return undefined;
    if (!portalDocument || !portalWindow) return undefined;
    const previousOverflow = portalDocument.body.style.overflow;
    portalDocument.body.style.overflow = 'hidden';
    const handleKeyDown = (event) => {
      if (event.key === 'Escape') {
        setIsDetailFullscreen(false);
      }
    };
    portalWindow.addEventListener('keydown', handleKeyDown);
    return () => {
      portalWindow.removeEventListener('keydown', handleKeyDown);
      portalDocument.body.style.overflow = previousOverflow;
    };
  }, [isDetailFullscreen, portalDocument, portalWindow]);

  useEffect(() => {
    if (!selectedMarker) return;
    setListTab(isDecisionMarker(selectedMarker) ? 'decisions' : 'events');
  }, [selectedMarker?.id, selectedMarker?.timestamp, selectedMarker?.time, selectedMarker?.marker_type]);

  const decisionMarkers = useMemo(
    () => (markers || []).filter(isDecisionMarker),
    [markers]
  );
  const eventMarkers = useMemo(
    () => (markers || []).filter((marker) => !isDecisionMarker(marker)),
    [markers]
  );
  const visibleMarkers = useMemo(
    () => (listTab === 'decisions' ? decisionMarkers : eventMarkers),
    [decisionMarkers, eventMarkers, listTab]
  );

  const hasAnyMarkers = Array.isArray(markers) && markers.length > 0;
  const {
    details,
    metadata,
    l2Diagnostics,
    intradayLevels,
    levelContext,
    entryQualityDiagnostics,
    decisionLog,
    t,
    renderYesNo,
    renderEnabled,
    renderGateStatus,
    renderCostLabel,
    renderReasonValue,
    breakEvenPayload,
    renderBreakEvenTrigger,
    renderBreakEvenProof,
    breakEvenStopDisplayValue,
    breakEvenComputed,
    breakEvenBuffer,
    breakEvenAntiSpikeSummary,
    formatPctValue,
    tooltipLocaleText,
    baseTooltipFor,
    runtimeTooltipByLabel,
  } = useDecisionPanelViewModel({
    selectedMarker,
    uiLanguage,
  });

  const renderTitle = (marker) => {
    const markerPnlUsd = marker?.details?.pnl_usd ?? marker?.details?.pnl_dollars;
    const markerPnlPct = resolvePnlPct(marker?.details, markerPnlUsd);
    if (marker.marker_type === 'take_profit_hit' && markerPnlPct !== null && markerPnlPct <= 0) {
      return `${marker.title || t("Take Profit")} (${t("net loss")})`;
    }
    return marker.title || marker.marker_type || t("Decision");
  };

  const {
    activeHelpTooltip,
    setActiveHelpTooltip,
    renderDetailLabel,
  } = useDecisionPanelTooltips({
    portalWindow,
    runtimeTooltipByLabel,
    resolveTooltipBaseLabel,
    formatTooltipRuntimeValue,
    tooltipLocaleText,
    baseTooltipFor,
    t,
    selectedMarker,
    detailTab,
    uiLanguage,
    isDetailFullscreen,
  });
  
  // Helper to render sections
  const renderSectionHeader = (title) => (
    <div className="detail-item" style={{ gridColumn: '1 / -1', borderTop: '1px solid var(--border-color)', paddingTop: 'var(--spacing-sm)', marginTop: 'var(--spacing-xs)', marginBottom: 'var(--spacing-xs)' }}>
      {renderDetailLabel(title, title, { fontWeight: 600, color: 'var(--text-primary)' })}
    </div>
  );

  const renderDecisionDetail = (fullscreen = false) => (
    <div
      className={`decision-detail ${fullscreen ? 'fullscreen' : ''}`}
      onClick={(event) => {
        if (fullscreen) {
          event.stopPropagation();
        }
      }}
    >
      <DecisionPanelDetailChrome
        fullscreen={fullscreen}
        title={`${getMarkerIcon(selectedMarker)} ${renderTitle(selectedMarker)}`}
        t={t}
        uiLanguage={uiLanguage}
        setUiLanguage={setUiLanguage}
        detailTab={detailTab}
        setDetailTab={setDetailTab}
        onToggleFullscreen={() => setIsDetailFullscreen((prev) => !prev)}
        activeHelpTooltip={activeHelpTooltip}
        onClosePinnedTooltip={() => setActiveHelpTooltip(null)}
      />
      <DecisionPanelDetailBody
        detailTab={detailTab}
        selectedMarker={selectedMarker}
        details={details}
        metadata={metadata}
        l2Diagnostics={l2Diagnostics}
        intradayLevels={intradayLevels}
        levelContext={levelContext}
        entryQualityDiagnostics={entryQualityDiagnostics}
        decisionLog={decisionLog}
        t={t}
        renderDetailLabel={renderDetailLabel}
        renderSectionHeader={renderSectionHeader}
        renderCostLabel={renderCostLabel}
        resolvePnlPct={resolvePnlPct}
        formatTime={formatTime}
        formatPrice={formatPrice}
        renderEnabled={renderEnabled}
        renderYesNo={renderYesNo}
        renderGateStatus={renderGateStatus}
        renderValue={renderValue}
        formatGenericValue={formatGenericValue}
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
    </div>
  );

  return (
    <div
      ref={(node) => {
        panelRootRef.current = node;
      }}
      style={{ display: "flex", flexDirection: "column", minHeight: 0, height: "100%" }}
    >
      {hasAnyMarkers ? (
        <>
          <DecisionPanelMarkerList
            listTab={listTab}
            setListTab={setListTab}
            decisionMarkers={decisionMarkers}
            eventMarkers={eventMarkers}
            visibleMarkers={visibleMarkers}
            selectedMarker={selectedMarker}
            isDetailFullscreen={isDetailFullscreen}
            setIsDetailFullscreen={setIsDetailFullscreen}
            onSelectMarker={onSelectMarker}
            t={t}
            renderTitle={renderTitle}
          />

          {activeHelpTooltip && !activeHelpTooltip.pinned && portalBody &&
            createPortal(
              <div
                className={`decision-help-tooltip ${activeHelpTooltip.placeAbove ? "above" : ""}`}
                role="tooltip"
                aria-live="polite"
                style={{
                  top: activeHelpTooltip.top,
                  left: activeHelpTooltip.left,
                  maxWidth: activeHelpTooltip.maxWidth,
                }}
              >
                {activeHelpTooltip.text}
              </div>,
              portalBody,
            )}
          
          {/* Detail Panel */}
          {selectedMarker && (
            <>
              {!isDetailFullscreen && renderDecisionDetail(false)}
              {isDetailFullscreen && portalBody &&
                createPortal(
                  <>
                    <div
                      className="decision-detail-backdrop"
                      onClick={() => setIsDetailFullscreen(false)}
                    />
                    {renderDecisionDetail(true)}
                  </>,
                  portalBody,
                )}
            </>
          )}
        </>
      ) : (
        <div className="decision-list">
          <div className="empty-state">
            <div className="icon">📭</div>
            <p>
              {t("No decisions yet. Start the backtest to see trading decisions appear here.")}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

export default memo(DecisionPanel);
