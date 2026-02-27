import { useEffect, useMemo, useRef } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
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
  selectedMarker: DecisionPanelMarkerLike | null;
  isDetailFullscreen: boolean;
  setIsDetailFullscreen: (value: boolean) => void;
  onSelectMarker: (marker: DecisionPanelMarkerLike & { __selectionSource?: string }) => void;
  t: (text: string) => string;
  renderTitle: (marker: DecisionPanelMarkerLike) => string;
};

const VIRTUAL_ROW_ESTIMATE_PX = 112;
const VIRTUAL_ROW_OVERSCAN = 10;

export default function DecisionPanelMarkerList({
  listTab,
  setListTab,
  decisionMarkers,
  eventMarkers,
  visibleMarkers,
  selectedMarker,
  isDetailFullscreen,
  setIsDetailFullscreen,
  onSelectMarker,
  t,
  renderTitle,
}: Props) {
  const scrollContainerRef = useRef<HTMLDivElement | null>(null);
  const reversedMarkers = useMemo(() => [...visibleMarkers].reverse(), [visibleMarkers]);
  const rowVirtualizer = useVirtualizer({
    count: reversedMarkers.length,
    getScrollElement: () => scrollContainerRef.current,
    estimateSize: () => VIRTUAL_ROW_ESTIMATE_PX,
    overscan: VIRTUAL_ROW_OVERSCAN,
  });

  const selectedIndex = useMemo(
    () => reversedMarkers.findIndex((marker) => isSameMarker(selectedMarker, marker)),
    [reversedMarkers, selectedMarker],
  );

  useEffect(() => {
    if (isDetailFullscreen) return;
    if (selectedIndex < 0) return;
    rowVirtualizer.scrollToIndex(selectedIndex, { align: "auto" });
  }, [isDetailFullscreen, rowVirtualizer, selectedIndex]);

  const virtualItems = rowVirtualizer.getVirtualItems();

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
      <div ref={scrollContainerRef} className="decision-list">
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

        {visibleMarkers.length > 0 && (
          <div
            style={{
              height: `${rowVirtualizer.getTotalSize()}px`,
              position: "relative",
              width: "100%",
            }}
          >
            {virtualItems.map((virtualRow) => {
              const marker = reversedMarkers[virtualRow.index];
              if (!marker) return null;

              const exitMetrics = formatExitMetrics(marker);
              const markerKey = getMarkerKey(marker, virtualRow.index);
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
                  ref={rowVirtualizer.measureElement}
                  data-index={virtualRow.index}
                  style={{
                    left: 0,
                    position: "absolute",
                    top: 0,
                    transform: `translateY(${virtualRow.start}px)`,
                    width: "100%",
                  }}
                >
                  <div
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
                </div>
              );
            })}
          </div>
        )}
      </div>
    </>
  );
}
