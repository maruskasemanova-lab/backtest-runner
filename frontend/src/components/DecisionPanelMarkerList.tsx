import type {
  DecisionPanelIntradayLevelsLatestEventLike,
  DecisionPanelMarkerLike,
} from "./decision-panel-types";
import { extractIntradayLevels } from "./decision-panel-diagnostics";
import {
  formatExitMetrics,
  formatTime,
  getMarkerIcon,
  getMarkerKey,
  isSameMarker,
} from "./decision-panel-utils";

type Props = {
  listTab: string;
  setListTab: (value: string) => void;
  decisionMarkers: DecisionPanelMarkerLike[];
  eventMarkers: DecisionPanelMarkerLike[];
  visibleMarkers: DecisionPanelMarkerLike[];
  renderedMarkers: DecisionPanelMarkerLike[];
  hasMoreRows: boolean;
  selectedMarker: DecisionPanelMarkerLike | null;
  itemRefs: { current: Map<string, HTMLElement> };
  setIsDetailFullscreen: (value: boolean) => void;
  onSelectMarker: (marker: DecisionPanelMarkerLike & { __selectionSource?: string }) => void;
  t: (text: string) => string;
  renderTitle: (marker: DecisionPanelMarkerLike) => string;
  setVisibleRows: (updater: (prev: number) => number) => void;
  decisionListLoadStep: number;
};

export default function DecisionPanelMarkerList({
  listTab,
  setListTab,
  decisionMarkers,
  eventMarkers,
  visibleMarkers,
  renderedMarkers,
  hasMoreRows,
  selectedMarker,
  itemRefs,
  setIsDetailFullscreen,
  onSelectMarker,
  t,
  renderTitle,
  setVisibleRows,
  decisionListLoadStep,
}: Props) {
  return (
    <>
      <div className="decision-list-tabs">
        <button
          className={`decision-list-tab ${listTab === "decisions" ? "active" : ""}`}
          onClick={() => setListTab("decisions")}
        >
          {t("Decisions")} ({decisionMarkers.length})
        </button>
        <button
          className={`decision-list-tab ${listTab === "events" ? "active" : ""}`}
          onClick={() => setListTab("events")}
        >
          {t("Events")} ({eventMarkers.length})
        </button>
      </div>
      <div className="decision-list">
        {visibleMarkers.length === 0 && (
          <div className="empty-state">
            <div className="icon">🗂️</div>
            <p>
              {listTab === "decisions"
                ? t("No trading decisions in this run yet.")
                : t("No non-decision events in this run yet.")}
            </p>
          </div>
        )}
        {renderedMarkers.map((marker, idx) => {
          const exitMetrics = formatExitMetrics(marker);
          const markerKey = getMarkerKey(marker, idx);
          const selected = isSameMarker(selectedMarker, marker);
          const markerDetails = marker?.details || {};
          const markerMetadata = markerDetails?.metadata || {};
          const markerIntradayLevels = extractIntradayLevels(marker, markerDetails, markerMetadata);
          const markerIntradayEvent =
            markerIntradayLevels?.latestEvent && typeof markerIntradayLevels.latestEvent === "object"
              ? (markerIntradayLevels.latestEvent as DecisionPanelIntradayLevelsLatestEventLike)
              : null;
          const markerIntradayEventType = String(markerIntradayEvent?.event_type || "").toLowerCase();
          const markerIntradayEventDirection = String(markerIntradayEvent?.direction || "").toLowerCase();
          const markerIntradayEventLabel = markerIntradayEvent
            ? `Levels ${markerIntradayEventType || "event"}${markerIntradayEventDirection ? ` ${markerIntradayEventDirection}` : ""}${
                markerIntradayEvent.price != null ? ` @ ${Number(markerIntradayEvent.price).toFixed(2)}` : ""
              }`
            : "";
          const markerIntradayEventColor =
            markerIntradayEventType === "break"
              ? "var(--accent-green)"
              : markerIntradayEventType === "bounce"
                ? "var(--text-secondary)"
                : "var(--text-muted)";

          return (
            <div
              key={markerKey}
              ref={(node) => {
                if (node) itemRefs.current.set(markerKey, node);
                else itemRefs.current.delete(markerKey);
              }}
              className={`decision-item ${marker.marker_type} ${selected ? "selected" : ""}`}
              onClick={() => {
                setIsDetailFullscreen(true);
                onSelectMarker({
                  ...marker,
                  __selectionSource: "decision_panel",
                });
              }}
            >
              <div className="decision-header">
                <span className="decision-title">
                  {getMarkerIcon(marker)} {renderTitle(marker)}
                </span>
                <span className="decision-time">{formatTime(marker.timestamp)}</span>
              </div>
              <div className="decision-description">
                {exitMetrics
                  ? `${t("Reason")}: ${marker.details?.exit_reason || "n/a"}`
                  : marker.description || t("No description")}
                {exitMetrics && (
                  <div
                    style={{
                      marginTop: 4,
                      color: "var(--text-muted)",
                      fontSize: "0.78rem",
                      fontWeight: 600,
                    }}
                  >
                    {exitMetrics}
                  </div>
                )}
                {markerIntradayEvent && (
                  <div
                    style={{
                      marginTop: 4,
                      color: markerIntradayEventColor,
                      fontSize: "0.75rem",
                      fontWeight: 600,
                    }}
                  >
                    {markerIntradayEventLabel}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
      {hasMoreRows && (
        <div style={{ padding: "0 var(--spacing-sm) var(--spacing-sm)" }}>
          <button
            type="button"
            className="btn btn-secondary tw-full-btn"
            onClick={() =>
              setVisibleRows((prev) => Math.min(visibleMarkers.length, prev + decisionListLoadStep))
            }
          >
            {t("Load older")} ({visibleMarkers.length - renderedMarkers.length} {t("remaining")})
          </button>
        </div>
      )}
    </>
  );
}
