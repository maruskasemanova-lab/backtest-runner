import type {
  DiagnosticCalendarRun,
  DiagnosticCalendarTrade,
} from "./diagnostic-calendar-types";
import {
  buildTradeSummary,
  formatPct,
  formatReasonLabel,
  formatTimeUtc,
  formatUsd,
  tradePnlPct,
} from "./diagnostic-calendar-utils";

type DiagnosticCalendarTradeListProps = {
  selectedDate: string | null;
  selectedRunRecord: DiagnosticCalendarRun | null;
  selectedRunTradeDetails: DiagnosticCalendarTrade[];
};

function DiagnosticCalendarTradeList({
  selectedDate,
  selectedRunRecord,
  selectedRunTradeDetails,
}: DiagnosticCalendarTradeListProps) {
  return (
    <div className="diagnostic-trade-list">
      <div className="diagnostic-trade-list-title">
        Trades for Run {String(selectedRunRecord?.run_id || "n/a")} (click to expand)
      </div>
      {selectedRunTradeDetails.length ? (
        selectedRunTradeDetails.map((trade, index) => (
          <details
            key={
              `${selectedDate}-${String(trade?.run_id || "")}-${String(trade?.report_dir || "")}-${String(trade?.trade_id ?? index)}`
            }
            className="diagnostic-trade-item"
          >
            <summary>{buildTradeSummary(trade, index)}</summary>
            <div className="diagnostic-trade-content">
              {String(trade?.run_id || "").trim() ? (
                <div className="diagnostic-row">
                  <span>Run ID</span>
                  <strong>{String(trade?.run_id || "")}</strong>
                </div>
              ) : null}
              {formatReasonLabel(trade?.entry_reason) ? (
                <div className="diagnostic-row">
                  <span>Entry Reason</span>
                  <strong>{formatReasonLabel(trade?.entry_reason)}</strong>
                </div>
              ) : null}
              {formatReasonLabel(trade?.exit_reason) ? (
                <div className="diagnostic-row">
                  <span>Exit Reason</span>
                  <strong>{formatReasonLabel(trade?.exit_reason)}</strong>
                </div>
              ) : null}
              {formatTimeUtc(trade?.entry_time) ? (
                <div className="diagnostic-row">
                  <span>Entry Time</span>
                  <strong>{formatTimeUtc(trade?.entry_time)}</strong>
                </div>
              ) : null}
              {formatTimeUtc(trade?.exit_time) ? (
                <div className="diagnostic-row">
                  <span>Exit Time</span>
                  <strong>{formatTimeUtc(trade?.exit_time)}</strong>
                </div>
              ) : null}
              <div className="diagnostic-row">
                <span>Bars Held</span>
                <strong>{Number(trade?.bars_held ?? 0)}</strong>
              </div>
              <div className="diagnostic-row">
                <span>PnL</span>
                <strong className={Number(trade?.pnl_dollars ?? 0) < 0 ? "negative" : Number(trade?.pnl_dollars ?? 0) > 0 ? "positive" : ""}>
                  {formatPct(tradePnlPct(trade))} / {formatUsd(trade?.pnl_dollars)}
                </strong>
              </div>
            </div>
          </details>
        ))
      ) : (
        <div className="diagnostic-empty">No closed trades for this day.</div>
      )}
    </div>
  );
}

export default DiagnosticCalendarTradeList;
