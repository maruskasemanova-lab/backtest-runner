import { formatTimestamp } from "../../utils";
import type { AdaptiveTunerControllerModel } from "./useAdaptiveTunerController";
import { formatJobLabel, statusClassName } from "./adaptiveTunerViewHelpers";

type AdaptiveTunerMonitorController = Pick<
  AdaptiveTunerControllerModel,
  | "job"
  | "submitting"
  | "error"
  | "notice"
  | "selectedJobId"
  | "setSelectedJobId"
  | "jobHistory"
  | "progressPct"
  | "etaEstimate"
  | "bestTrial"
  | "jobQuickMode"
  | "jobVersion"
  | "jobTrialBudget"
  | "form"
>;

interface AdaptiveTunerMonitorPanelProps {
  controller: AdaptiveTunerMonitorController;
}

export function AdaptiveTunerMonitorPanel({ controller }: AdaptiveTunerMonitorPanelProps) {
  const {
    job,
    submitting,
    error,
    notice,
    selectedJobId,
    setSelectedJobId,
    jobHistory,
    progressPct,
    etaEstimate,
    bestTrial,
    jobQuickMode,
    jobVersion,
    jobTrialBudget,
    form,
  } = controller;

  const jobStatus = statusClassName(String(job?.status || (submitting ? "running" : "idle")));
  const completedTrials = Number(job?.progress?.completed_trials || 0);
  const totalTrials = Number(job?.progress?.total_trials || 0);

  return (
    <section className="tuner-monitor">
      <div className="tuner-monitor-top">
        <div>
          <h3>Job Monitor</h3>
          <p>{job?.job_id ? `Job ${job.job_id}` : "No tuning job selected yet."}</p>
        </div>
        <span className={`tuner-status-badge ${jobStatus}`}>{job?.status || "idle"}</span>
      </div>

      {(error || notice) && (
        <div className="tuner-alerts">
          {error && <div className="adaptive-error">{error}</div>}
          {notice && <div className="adaptive-notice">{notice}</div>}
        </div>
      )}

      <div className="tuner-history-picker">
        <label htmlFor="tuner_job_history">Job history</label>
        <select
          id="tuner_job_history"
          value={selectedJobId || ""}
          onChange={(e) => setSelectedJobId(e.target.value || null)}
        >
          {!jobHistory.length && <option value="">No jobs yet</option>}
          {jobHistory.map((historyJob) => {
            const historyId = String(historyJob?.job_id || "");
            if (!historyId) return null;
            return (
              <option key={historyId} value={historyId}>
                {formatJobLabel(historyJob)}
              </option>
            );
          })}
        </select>
      </div>

      <div className="tuner-progress-large-track">
        <div
          className={`tuner-progress-large-fill ${jobStatus === "running" ? "running" : ""}`}
          style={{ width: `${progressPct}%` }}
        />
      </div>

      <div className="tuner-monitor-stats">
        <div className="tuner-monitor-stat">
          <span>Progress</span>
          <strong>{progressPct.toFixed(1)}%</strong>
        </div>
        <div className="tuner-monitor-stat">
          <span>Trials</span>
          <strong>
            {completedTrials} / {totalTrials}
          </strong>
        </div>
        <div className="tuner-monitor-stat">
          <span>ETA</span>
          <strong>{etaEstimate?.label || "-"}</strong>
        </div>
        <div className="tuner-monitor-stat">
          <span>Score metric</span>
          <strong>{String(job?.request?.score_metric || form.score_metric)}</strong>
        </div>
      </div>

      <div className="tuner-best-score-card">
        <div className="tuner-best-score-head">
          <span>Best Score</span>
          <strong>{Number(bestTrial?.score || 0).toFixed(4)}</strong>
        </div>
        <div className="tuner-best-score-metrics">
          <span>PnL {Number(bestTrial?.metrics?.avg_pnl_pct || 0).toFixed(4)}%</span>
          <span>WR {Number(bestTrial?.metrics?.avg_win_rate_pct || 0).toFixed(2)}%</span>
          <span>Trades {Number(bestTrial?.metrics?.total_trades || 0)}</span>
        </div>
      </div>

      <div className="tuner-monitor-meta">
        <span>Mode: {jobQuickMode ? "Quick" : "Standard"}</span>
        <span>Version: v{jobVersion}</span>
        <span>Days: {Number(job?.effective_days || 0)}</span>
        <span>
          Budget:{" "}
          {jobTrialBudget
            ? `${Number(jobTrialBudget.effective || 0)} (${Number(jobTrialBudget.requested || 0)} x${Number(jobTrialBudget.boost || 1)})`
            : "-"}
        </span>
        <span>ETA at: {etaEstimate?.etaAt ? formatTimestamp(etaEstimate.etaAt) : "-"}</span>
      </div>
    </section>
  );
}
