import type { DiagnosticCalendarRun } from "./diagnostic-calendar-types";
import {
  formatBarsPair,
  formatCount,
  formatPct,
  formatUsd,
  resolveRunProfileFields,
  runPnlPct,
  runTotalPnlPct,
} from "./diagnostic-calendar-utils";

type DiagnosticCalendarRunListProps = {
  selectedDate: string | null;
  selectedRuns: DiagnosticCalendarRun[];
};

function DiagnosticCalendarRunList({
  selectedDate,
  selectedRuns,
}: DiagnosticCalendarRunListProps) {
  if (!selectedRuns.length) return null;

  return (
    <div className="diagnostic-trade-list">
      <div className="diagnostic-trade-list-title">Runs (click to expand)</div>
      {selectedRuns.map((run, index) => {
        const runProfiles = resolveRunProfileFields(run);
        const runSummaryProfile =
          runProfiles.unifiedProfile
          || runProfiles.adaptiveProfile
          || runProfiles.strategyComboProfile;

        return (
          <details
            key={`${selectedDate}-run-${String(run?.run_id || index)}`}
            className="diagnostic-trade-item"
          >
            <summary>
              {String(run?.run_id || `run-${index + 1}`)} | T:{Number(run?.total_trades ?? 0)}
              {" | "}
              {formatPct(runPnlPct(run))} / {formatUsd(run?.pnl_dollars)}
              {runSummaryProfile ? ` | P:${runSummaryProfile}` : ""}
            </summary>
            <div className="diagnostic-trade-content">
              <div className="diagnostic-row">
                <span>Saved At</span>
                <strong>{String(run?.report_saved_at || "n/a")}</strong>
              </div>
              <div className="diagnostic-row">
                <span>Date Label</span>
                <strong>{String(run?.date_label || selectedDate || "n/a")}</strong>
              </div>
              <div className="diagnostic-row">
                <span>Day Signals</span>
                <strong>{formatCount(run?.signals)}</strong>
              </div>
              <div className="diagnostic-row">
                <span>Day Regime Evals</span>
                <strong>{formatCount(run?.regime_evaluations)}</strong>
              </div>
              <div className="diagnostic-row">
                <span>Run Trades</span>
                <strong>{formatCount(run?.run_total_trades)}</strong>
              </div>
              <div className="diagnostic-row">
                <span>Run Bars</span>
                <strong>{formatBarsPair(run?.run_processed_bars, run?.run_total_bars)}</strong>
              </div>
              <div className="diagnostic-row">
                <span>Run PnL</span>
                <strong
                  className={
                    runTotalPnlPct(run) < 0
                      ? "negative"
                      : runTotalPnlPct(run) > 0
                        ? "positive"
                        : ""
                  }
                >
                  {formatPct(runTotalPnlPct(run))} / {formatUsd(run?.run_total_pnl_dollars)}
                </strong>
              </div>
              {Array.isArray(run?.strategy_names) && run.strategy_names.length ? (
                <div className="diagnostic-row">
                  <span>Strategies</span>
                  <strong>{run.strategy_names.join(", ")}</strong>
                </div>
              ) : null}
              {runProfiles.unifiedProfile ? (
                <div className="diagnostic-row">
                  <span>Unified Profile</span>
                  <strong>{runProfiles.unifiedProfile}</strong>
                </div>
              ) : null}
              {runProfiles.adaptiveProfile ? (
                <div className="diagnostic-row">
                  <span>Adaptive Profile</span>
                  <strong>{runProfiles.adaptiveProfile}</strong>
                </div>
              ) : null}
              {runProfiles.strategyComboProfile ? (
                <div className="diagnostic-row">
                  <span>Strategy Combo Profile</span>
                  <strong>{runProfiles.strategyComboProfile}</strong>
                </div>
              ) : null}
              {String(run?.profile_match_mode || "").trim() ? (
                <div className="diagnostic-row">
                  <span>Profile Match</span>
                  <strong>{String(run?.profile_match_mode || "")}</strong>
                </div>
              ) : null}
            </div>
          </details>
        );
      })}
    </div>
  );
}

export default DiagnosticCalendarRunList;
