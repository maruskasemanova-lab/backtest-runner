import type {
  DiagnosticCalendarDayResult,
  DiagnosticCalendarMonthView,
  DiagnosticCalendarReport,
} from "./diagnostic-calendar-types";
import {
  WEEKDAY_LABELS,
  buildDayTooltip,
  dayPnlPct,
  formatPct,
  formatUsd,
  getDayCellStyle,
} from "./diagnostic-calendar-utils";

type DiagnosticCalendarMonthGridProps = {
  dayResults: DiagnosticCalendarDayResult[];
  loading: boolean;
  maxAbsPnlPct: number;
  monthlyViews: DiagnosticCalendarMonthView[];
  report: DiagnosticCalendarReport | null;
  selectedDate: string | null;
  setSelectedDate: (isoDate: string) => void;
};

function DiagnosticCalendarMonthGrid({
  dayResults,
  loading,
  maxAbsPnlPct,
  monthlyViews,
  report,
  selectedDate,
  setSelectedDate,
}: DiagnosticCalendarMonthGridProps) {
  return (
    <div className="card diagnostic-months-card">
      <div className="card-header">
        <span className="card-title">By Day</span>
        <div className="diagnostic-legend">
          <span className="legend-chip profit">Profit</span>
          <span className="legend-chip flat">Flat</span>
          <span className="legend-chip loss">Loss</span>
          <span className="legend-chip failed">Failed</span>
        </div>
      </div>
      <div className="card-body diagnostic-months-body">
        {!loading && !report ? (
          <div className="diagnostic-empty">No history loaded.</div>
        ) : null}
        {!loading && report && !dayResults.length ? (
          <div className="diagnostic-empty">No days match selected filter.</div>
        ) : null}
        {monthlyViews.map((month) => (
          <section key={month.id} className="diagnostic-month">
            <h3>{month.label}</h3>
            <div className="diagnostic-weekdays">
              {WEEKDAY_LABELS.map((label) => (
                <span key={`${month.id}-${label}`}>{label}</span>
              ))}
            </div>
            <div className="diagnostic-grid">
              {month.cells.map((cell, idx) => {
                if (!cell) {
                  return <div key={`${month.id}-blank-${idx}`} className="diagnostic-cell blank" />;
                }

                const result = cell.result;
                const isSelected = selectedDate === cell.isoDate;
                const isFailed = result?.success === false;
                const pnl = dayPnlPct(result);
                const pnlClass =
                  isFailed
                    ? "failed"
                    : pnl > 0
                      ? "profit"
                      : pnl < 0
                        ? "loss"
                        : "flat";

                const classes = [
                  "diagnostic-cell",
                  pnlClass,
                  cell.inRange ? "in-range" : "out-range",
                  isSelected ? "selected" : "",
                ].join(" ").trim();
                const dayTrades = Number(result?.total_trades ?? 0);
                const cellTooltip = buildDayTooltip(cell.isoDate, result);

                return (
                  <button
                    key={cell.isoDate}
                    type="button"
                    className={classes}
                    style={getDayCellStyle(result, maxAbsPnlPct)}
                    disabled={!cell.inRange}
                    onClick={() => {
                      setSelectedDate(cell.isoDate);
                    }}
                    title={cellTooltip}
                  >
                    <span className="day-number">{cell.day}</span>
                    {result ? (
                      <>
                        <span className="day-pnl">
                          {result.success === false ? "ERR" : formatPct(dayPnlPct(result))}
                        </span>
                        <span className={`day-pnl-usd ${result.success === false ? "muted" : ""}`}>
                          {result.success === false ? "-" : formatUsd(result.pnl_dollars ?? 0)}
                        </span>
                        <span className="day-trades">T:{Number.isFinite(dayTrades) ? dayTrades : 0}</span>
                      </>
                    ) : (
                      <>
                        <span className="day-pnl muted">-</span>
                        <span className="day-pnl-usd muted">-</span>
                        <span className="day-trades muted">T:-</span>
                      </>
                    )}
                  </button>
                );
              })}
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}

export default DiagnosticCalendarMonthGrid;
