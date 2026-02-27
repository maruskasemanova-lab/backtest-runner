import type {
  DiagnosticCalendarDayDetailModel,
  StrategyAnalyzerPayload,
} from "./diagnostic-calendar-types";
import {
  formatBarsPair,
  formatCount,
  formatPct,
  formatUsd,
} from "./diagnostic-calendar-utils";
import DiagnosticCalendarRunList from "./DiagnosticCalendarRunList";
import DiagnosticCalendarTradeList from "./DiagnosticCalendarTradeList";

type DiagnosticCalendarDayDetailProps = {
  model: DiagnosticCalendarDayDetailModel;
  onOpenInStrategyAnalyzer?: (payload: StrategyAnalyzerPayload) => void;
  setActiveDayRunKey: (value: string) => void;
  setShowRunConfigSnapshotDialog: (value: boolean) => void;
};

function DiagnosticCalendarDayDetail({
  model,
  onOpenInStrategyAnalyzer,
  setActiveDayRunKey,
  setShowRunConfigSnapshotDialog,
}: DiagnosticCalendarDayDetailProps) {
  const {
    activeDayRunKey,
    canOpenSelectedDayInAnalyzer,
    dayMetrics,
    hasSelectedRunConfigSnapshot,
    runMetrics,
    selectedDate,
    selectedDayAnalyzerPayload,
    selectedDayProfileList,
    selectedResult,
    selectedRunOptions,
    selectedRunProfiles,
    selectedRunRecord,
    selectedRunTradeDetails,
    selectedRuns,
    selectedStrategyNames,
  } = model;

  return (
    <aside className="card diagnostic-day-card">
      <div className="card-header">
        <span className="card-title">Day Detail</span>
        <span className="diagnostic-day-date">{selectedDate || "N/A"}</span>
      </div>
      <div className="card-body">
        {!selectedDate ? <div className="diagnostic-empty">Pick a day.</div> : null}
        <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: selectedDate ? "0.75rem" : 0 }}>
          <button
            type="button"
            className="btn btn-secondary"
            disabled={!canOpenSelectedDayInAnalyzer}
            onClick={() => {
              if (!selectedDayAnalyzerPayload) return;
              onOpenInStrategyAnalyzer?.(selectedDayAnalyzerPayload);
            }}
            title={selectedDate ? "Open selected day in Strategy Analyzer" : "Pick a day first"}
            style={{ padding: "6px 12px", fontSize: "0.8rem", fontWeight: 600 }}
          >
            Open In Strategy Analyzer
          </button>
        </div>

        {selectedDate && !selectedResult ? (
          <div className="diagnostic-empty">No run result for this day.</div>
        ) : null}

        {selectedResult ? (
          <div className="diagnostic-day-details">
            <div className="diagnostic-row">
              <span>Status</span>
              <strong className={selectedResult.success === false ? "negative" : "positive"}>
                {selectedResult.success === false ? "Failed" : "Processed"}
              </strong>
            </div>
            {selectedResult.success === false ? (
              <div className="diagnostic-error detail">{String(selectedResult.error || "Unknown error")}</div>
            ) : (
              <>
                <div className="diagnostic-row">
                  <span>PnL</span>
                  <strong
                    className={
                      dayMetrics.pnlPct < 0
                        ? "negative"
                        : dayMetrics.pnlPct > 0
                          ? "positive"
                          : ""
                    }
                  >
                    {formatPct(dayMetrics.pnlPct)} / {formatUsd(dayMetrics.pnlDollars)}
                  </strong>
                </div>
                {Number(selectedResult.report_count ?? 0) > 0 ? (
                  <div className="diagnostic-row">
                    <span>Runs</span>
                    <strong>{Number(selectedResult.report_count ?? 0)}</strong>
                  </div>
                ) : null}
                {selectedRunOptions.length ? (
                  <div className="diagnostic-row">
                    <span>Day Run</span>
                    {selectedRunOptions.length === 1 ? (
                      <strong>{selectedRunOptions[0].label}</strong>
                    ) : (
                      <select
                        className="diagnostic-inline-select"
                        value={activeDayRunKey}
                        onChange={(event) => setActiveDayRunKey(String(event.target.value || ""))}
                      >
                        {selectedRunOptions.map((option) => (
                          <option key={`day-run-${option.scopeKey}`} value={option.scopeKey}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                    )}
                  </div>
                ) : null}
                <div className="diagnostic-row">
                  <span>Day Signals</span>
                  <strong>{formatCount(dayMetrics.signals)}</strong>
                </div>
                <div className="diagnostic-row">
                  <span>Day Trades</span>
                  <strong>{dayMetrics.trades}</strong>
                </div>
                <div className="diagnostic-row">
                  <span>Run Trades</span>
                  <strong>{formatCount(runMetrics.trades)}</strong>
                </div>
                <div className="diagnostic-row">
                  <span>Day Bars</span>
                  <strong>{formatBarsPair(dayMetrics.barsProcessed, dayMetrics.barsTotal)}</strong>
                </div>
                <div className="diagnostic-row">
                  <span>Run Bars</span>
                  <strong>{formatBarsPair(runMetrics.barsProcessed, runMetrics.barsTotal)}</strong>
                </div>
                <div className="diagnostic-row">
                  <span>Day Regime Evals</span>
                  <strong>{formatCount(dayMetrics.regimeEvals)}</strong>
                </div>
                <div className="diagnostic-row">
                  <span>Run Signals</span>
                  <strong>{formatCount(runMetrics.signals)}</strong>
                </div>
                <div className="diagnostic-row">
                  <span>Run Regime Evals</span>
                  <strong>{formatCount(runMetrics.regimeEvals)}</strong>
                </div>
                <div className="diagnostic-row">
                  <span>Run PnL</span>
                  <strong
                    className={
                      (runMetrics.pnlPct ?? 0) < 0
                        ? "negative"
                        : (runMetrics.pnlPct ?? 0) > 0
                          ? "positive"
                          : ""
                    }
                  >
                    {formatPct(runMetrics.pnlPct)} / {formatUsd(runMetrics.pnlDollars)}
                  </strong>
                </div>
                {selectedRunProfiles.unifiedProfile ? (
                  <div className="diagnostic-row">
                    <span>Unified Profile (Run)</span>
                    <strong>{selectedRunProfiles.unifiedProfile}</strong>
                  </div>
                ) : null}
                {selectedRunProfiles.adaptiveProfile ? (
                  <div className="diagnostic-row">
                    <span>Adaptive Profile (Run)</span>
                    <strong>{selectedRunProfiles.adaptiveProfile}</strong>
                  </div>
                ) : null}
                {selectedRunProfiles.strategyComboProfile ? (
                  <div className="diagnostic-row">
                    <span>Strategy Combo (Run)</span>
                    <strong>{selectedRunProfiles.strategyComboProfile}</strong>
                  </div>
                ) : null}
                {selectedRuns.length > 1 && selectedDayProfileList ? (
                  <div className="diagnostic-row">
                    <span>Profiles (Day Aggregate)</span>
                    <strong>{selectedDayProfileList}</strong>
                  </div>
                ) : null}
                {selectedStrategyNames.length ? (
                  <div className="diagnostic-row">
                    <span>Strategies</span>
                    <strong>{selectedStrategyNames.join(", ")}</strong>
                  </div>
                ) : null}
                {hasSelectedRunConfigSnapshot ? (
                  <div className="diagnostic-row">
                    <span>Run Config Snapshot</span>
                    <button
                      type="button"
                      className="btn btn-secondary tw-btn-compact"
                      onClick={() => setShowRunConfigSnapshotDialog(true)}
                    >
                      View Full Snapshot
                    </button>
                  </div>
                ) : null}
                <DiagnosticCalendarRunList
                  selectedDate={selectedDate}
                  selectedRuns={selectedRuns}
                />
                <DiagnosticCalendarTradeList
                  selectedDate={selectedDate}
                  selectedRunRecord={selectedRunRecord}
                  selectedRunTradeDetails={selectedRunTradeDetails}
                />
              </>
            )}
          </div>
        ) : null}
      </div>
    </aside>
  );
}

export default DiagnosticCalendarDayDetail;
