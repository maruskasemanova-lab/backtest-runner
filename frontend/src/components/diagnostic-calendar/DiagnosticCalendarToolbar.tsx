import { useEffect, useState } from "react";
import type {
  DiagnosticCalendarDraftFilters,
  DiagnosticCalendarProfileOption,
  DiagnosticCalendarReport,
  DiagnosticCalendarRunFilterOption,
  DiagnosticCalendarSummary,
} from "./diagnostic-calendar-types";
import {
  MAX_HISTORY_LIMIT,
  formatPct,
  formatUsd,
} from "./diagnostic-calendar-utils";

type DiagnosticCalendarToolbarProps = {
  adaptiveProfileOptions: DiagnosticCalendarProfileOption[];
  appliedFilters: DiagnosticCalendarDraftFilters;
  applyDraftFilters: (filters: DiagnosticCalendarDraftFilters) => void;
  error: string;
  loading: boolean;
  report: DiagnosticCalendarReport | null;
  reportPath: string;
  runIdOptions: DiagnosticCalendarRunFilterOption[];
  setTradeViewMode: (value: string) => void;
  summary: DiagnosticCalendarSummary;
  tradeViewMode: string;
};

function DiagnosticCalendarToolbar({
  adaptiveProfileOptions,
  appliedFilters,
  applyDraftFilters,
  error,
  loading,
  report,
  reportPath,
  runIdOptions,
  setTradeViewMode,
  summary,
  tradeViewMode,
}: DiagnosticCalendarToolbarProps) {
  const [draftFilters, setDraftFilters] = useState(appliedFilters);

  useEffect(() => {
    setDraftFilters(appliedFilters);
  }, [appliedFilters]);

  return (
    <section className="card diagnostic-toolbar-card">
      <div className="card-header">
        <span className="card-title">Diagnostic Calendar</span>
        <span className="diagnostic-source">source: {reportPath}</span>
      </div>
      <div className="card-body">
        <form
          className="diagnostic-toolbar"
          onSubmit={(event) => {
            event.preventDefault();
            applyDraftFilters(draftFilters);
          }}
        >
          <label>
            Ticker
            <input
              type="text"
              value={draftFilters.ticker}
              onChange={(event) => setDraftFilters((previous) => ({ ...previous, ticker: event.target.value }))}
              maxLength={16}
              placeholder="MU"
            />
          </label>
          <label>
            History Limit
            <input
              type="number"
              min="1"
              max={MAX_HISTORY_LIMIT}
              step="1"
              value={draftFilters.historyLimit}
              onChange={(event) => setDraftFilters((previous) => ({ ...previous, historyLimit: event.target.value }))}
            />
          </label>
          <label>
            Unified Profile
            <select
              value={draftFilters.adaptiveProfileId}
              onChange={(event) => setDraftFilters((previous) => ({ ...previous, adaptiveProfileId: event.target.value }))}
            >
              <option value="">All</option>
              {adaptiveProfileOptions.map((option) => (
                <option key={`adaptive-${option.profileId}`} value={option.profileId}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            Run
            <select
              value={draftFilters.runId}
              onChange={(event) => setDraftFilters((previous) => ({ ...previous, runId: event.target.value }))}
            >
              <option value="">All</option>
              {runIdOptions.map((option) => (
                <option key={`run-${option.runId}`} value={option.runId}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            View
            <select value={tradeViewMode} onChange={(event) => setTradeViewMode(event.target.value)}>
              <option value="all">All Days</option>
              <option value="adaptive">Unified/Profile Trades</option>
            </select>
          </label>
          <button className="btn btn-primary" type="submit" disabled={loading}>
            {loading ? "Loading..." : "Load History"}
          </button>
        </form>

        {error ? <div className="diagnostic-error">{error}</div> : null}

        {report ? (
          <div className="diagnostic-kpis">
            <div className="diagnostic-kpi">
              <span>Valid Days</span>
              <strong>{summary.validDays}</strong>
            </div>
            <div className="diagnostic-kpi">
              <span>Failed Days</span>
              <strong>{summary.failedDays}</strong>
            </div>
            <div className="diagnostic-kpi">
              <span>Total Trades</span>
              <strong>{summary.totalTrades}</strong>
            </div>
            <div className="diagnostic-kpi">
              <span>Total PnL</span>
              <strong className={summary.totalPnlPct < 0 ? "negative" : summary.totalPnlPct > 0 ? "positive" : ""}>
                {formatPct(summary.totalPnlPct)} / {formatUsd(summary.totalPnlDollars)}
              </strong>
            </div>
            <div className="diagnostic-kpi">
              <span>Coverage</span>
              <strong>{summary.validDays}/{summary.totalDays} days</strong>
            </div>
          </div>
        ) : null}
      </div>
    </section>
  );
}

export default DiagnosticCalendarToolbar;
