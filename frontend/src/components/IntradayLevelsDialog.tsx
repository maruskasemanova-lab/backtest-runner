import { useEffect, useMemo, type MouseEvent as ReactMouseEvent } from "react";
import { toIsoTimestamp, toUnixSeconds } from "../utils";
import type {
  IntradayLevelsDialogSelection,
  IntradayLevelsObject,
} from "../intradayLevelsUtils";

type IntradayLevelsLevelRow = IntradayLevelsObject & {
  __key: string;
  key?: string;
  value?: unknown;
};

const EMPTY_OBJECT: IntradayLevelsObject = {};

const isObjectRecord = (value: unknown): value is IntradayLevelsObject =>
  Boolean(value) && typeof value === "object" && !Array.isArray(value);

const toFiniteNumber = (value: unknown): number | null => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
};

const formatNumber = (value: unknown, digits = 2): string => {
  const parsed = toFiniteNumber(value);
  return parsed === null ? "n/a" : parsed.toFixed(digits);
};

const formatCandleValue = (value: unknown): string => {
  const parsed = toFiniteNumber(value);
  return parsed === null ? "n/a" : parsed.toFixed(2);
};

const extractLevelRows = (payload: unknown): IntradayLevelsLevelRow[] => {
  if (!isObjectRecord(payload)) return [];
  const rawLevels = payload.levels;
  if (Array.isArray(rawLevels)) {
    return rawLevels.map((entry: unknown, index: number): IntradayLevelsLevelRow => {
      if (isObjectRecord(entry)) {
        const key = String(entry.id || entry.level_id || entry.name || `level-${index}`);
        return { __key: key, ...entry };
      }
      return { __key: `level-${index}`, value: entry };
    });
  }
  if (isObjectRecord(rawLevels)) {
    return Object.entries(rawLevels).map(
      ([key, entry]: [string, unknown], index: number): IntradayLevelsLevelRow => {
      if (isObjectRecord(entry)) {
        return {
          __key: String(entry.id || entry.level_id || key || `level-${index}`),
          key,
          ...entry,
        };
      }
      return { __key: String(key), key, value: entry };
      }
    );
  }
  return [];
};

type IntradayLevelsDialogProps = IntradayLevelsDialogSelection & {
  onClose?: () => void;
};

function IntradayLevelsDialog({
  bar,
  payload,
  sourcePath,
  sourceMarker,
  relatedMarkers,
  timeframeSeconds = 60,
  onClose,
}: IntradayLevelsDialogProps) {
  const safePayload = isObjectRecord(payload) ? payload : null;
  const stats = isObjectRecord(safePayload?.stats) ? safePayload.stats : EMPTY_OBJECT;
  const volumeProfile = isObjectRecord(safePayload?.volume_profile)
    ? safePayload.volume_profile
    : EMPTY_OBJECT;
  const latestEvent = isObjectRecord(safePayload?.latest_event) ? safePayload.latest_event : null;

  const levelRows = useMemo(() => extractLevelRows(safePayload), [safePayload]);
  const markersInWindow = Array.isArray(relatedMarkers) ? relatedMarkers : [];

  const barTime = Number(bar?.time);
  const barTimeLabel = Number.isFinite(barTime) ? toIsoTimestamp(barTime) : "n/a";
  const timeframeLabel =
    timeframeSeconds >= 3600
      ? `${Math.round(timeframeSeconds / 3600)}h`
      : `${Math.max(1, Math.round(timeframeSeconds / 60))}m`;
  const sourceMarkerTime = toUnixSeconds(sourceMarker?.time ?? sourceMarker?.timestamp);
  const sourceMarkerLabel = sourceMarker
    ? `${String(sourceMarker.marker_type || "marker")} @ ${
        Number.isFinite(sourceMarkerTime) ? toIsoTimestamp(sourceMarkerTime) : "n/a"
      }`
    : "n/a";

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose?.();
      }
    };
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [onClose]);

  return (
    <div className="intraday-levels-dialog-shell" role="presentation">
      <div className="intraday-levels-dialog-backdrop" onClick={onClose} />
      <section
        className="intraday-levels-dialog"
        role="dialog"
        aria-modal="true"
        aria-label="Intraday levels detail"
        onClick={(event: ReactMouseEvent) => event.stopPropagation()}
      >
        <header className="intraday-levels-dialog__header">
          <div className="intraday-levels-dialog__heading">
            <h3>Intraday Levels</h3>
            <p>{barTimeLabel}</p>
          </div>
          <button
            type="button"
            className="intraday-levels-dialog__close"
            onClick={onClose}
            aria-label="Close intraday levels dialog"
          >
            ×
          </button>
        </header>

        <div className="intraday-levels-dialog__meta">
          <div className="intraday-levels-dialog__meta-item">
            <span>Timeframe</span>
            <strong>{timeframeLabel}</strong>
          </div>
          <div className="intraday-levels-dialog__meta-item">
            <span>Candle OHLC</span>
            <strong>
              {formatCandleValue(bar?.open)} / {formatCandleValue(bar?.high)} /{" "}
              {formatCandleValue(bar?.low)} / {formatCandleValue(bar?.close)}
            </strong>
          </div>
          <div className="intraday-levels-dialog__meta-item">
            <span>Source Path</span>
            <strong>{sourcePath || "not available"}</strong>
          </div>
          <div className="intraday-levels-dialog__meta-item">
            <span>Source Marker</span>
            <strong>{sourceMarkerLabel}</strong>
          </div>
          <div className="intraday-levels-dialog__meta-item">
            <span>Markers In Window</span>
            <strong>{markersInWindow.length}</strong>
          </div>
        </div>

        <div className="intraday-levels-dialog__body">
          {!safePayload && (
            <div className="intraday-levels-dialog__empty">
              No intraday levels payload found for this candle.
            </div>
          )}

          {safePayload && (
            <>
              <div className="intraday-levels-dialog__summary">
                <div className="intraday-levels-dialog__summary-card">
                  <span>Tracker</span>
                  <strong>{safePayload.enabled === false ? "disabled" : "enabled"}</strong>
                </div>
                <div className="intraday-levels-dialog__summary-card">
                  <span>Active / Tested / Broken</span>
                  <strong>
                    {Number(stats.active_levels || 0)} / {Number(stats.tested_levels || 0)} /{" "}
                    {Number(stats.broken_levels || 0)}
                  </strong>
                </div>
                <div className="intraday-levels-dialog__summary-card">
                  <span>Bounce / Break</span>
                  <strong>
                    {Number(stats.bounce_events || 0)} / {Number(stats.break_events || 0)}
                  </strong>
                </div>
                <div className="intraday-levels-dialog__summary-card">
                  <span>POC / Value Area</span>
                  <strong>
                    {formatNumber(volumeProfile.poc_price)} /{" "}
                    {volumeProfile.value_area_low != null && volumeProfile.value_area_high != null
                      ? `${formatNumber(volumeProfile.value_area_low)} - ${formatNumber(volumeProfile.value_area_high)}`
                      : "n/a"}
                  </strong>
                </div>
                <div className="intraday-levels-dialog__summary-card">
                  <span>Latest Event</span>
                  <strong>
                    {latestEvent
                      ? `${String(latestEvent.event_type || "event")}${
                          latestEvent.direction ? ` (${String(latestEvent.direction)})` : ""
                        }${latestEvent.price != null ? ` @ ${formatNumber(latestEvent.price)}` : ""}`
                      : "n/a"}
                  </strong>
                </div>
              </div>

              {levelRows.length > 0 && (
                <div className="intraday-levels-dialog__levels">
                  <h4>Levels ({levelRows.length})</h4>
                  <div className="intraday-levels-dialog__table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th>Level</th>
                          <th>Price</th>
                          <th>Status</th>
                          <th>Tests</th>
                        </tr>
                      </thead>
                      <tbody>
                        {levelRows.map((row) => {
                          const label = String(
                            row.key || row.name || row.label || row.level_type || row.type || row.__key,
                          );
                          const price = row.price ?? row.level_price ?? row.value ?? row.level;
                          const status =
                            row.status ??
                            row.state ??
                            (row.broken === true ? "broken" : row.tested ? "tested" : "active");
                          const tests = row.tests ?? row.test_count ?? row.touch_count ?? row.hits ?? "n/a";
                          return (
                            <tr key={row.__key}>
                              <td>{label}</td>
                              <td>{formatNumber(price)}</td>
                              <td>{String(status)}</td>
                              <td>{String(tests)}</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              <div className="intraday-levels-dialog__raw">
                <h4>Raw Intraday Levels Payload</h4>
                <pre>{JSON.stringify(safePayload, null, 2)}</pre>
              </div>
            </>
          )}
        </div>
      </section>
    </div>
  );
}

export default IntradayLevelsDialog;
