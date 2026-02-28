import { Fragment } from "react";
import { formatTimestamp } from "../../utils";
import type { AdaptiveTunerControllerModel } from "./useAdaptiveTunerController";
import {
  DimensionImportanceBars,
  InteractionsList,
  SurprisingVectorsTable,
  formatCandidate,
  formatV2Candidate,
} from "./adaptiveTunerViewHelpers";

type AdaptiveTunerResultsController = Pick<
  AdaptiveTunerControllerModel,
  | "resultsTab"
  | "setResultsTab"
  | "profileFilter"
  | "setProfileFilter"
  | "profileSort"
  | "setProfileSort"
  | "filteredSortedProfiles"
  | "applyingProfileId"
  | "handleApplyProfile"
  | "jobVersion"
  | "selectedTrialIndex"
  | "setSelectedTrialIndex"
  | "vectorAnalysis"
>;

interface AdaptiveTunerResultsPanelProps {
  controller: AdaptiveTunerResultsController;
  activeProfileId: string;
  trialRows: Record<string, any>[];
}

export function AdaptiveTunerResultsPanel({
  controller,
  activeProfileId,
  trialRows,
}: AdaptiveTunerResultsPanelProps) {
  const {
    resultsTab,
    setResultsTab,
    profileFilter,
    setProfileFilter,
    profileSort,
    setProfileSort,
    filteredSortedProfiles,
    applyingProfileId,
    handleApplyProfile,
    jobVersion,
    selectedTrialIndex,
    setSelectedTrialIndex,
    vectorAnalysis,
  } = controller;

  return (
    <section className="tuner-results-area">
      <div className="tuner-results-tabs" role="tablist" aria-label="Adaptive tuner results">
        <button
          type="button"
          className={resultsTab === "profiles" ? "active" : ""}
          onClick={() => setResultsTab("profiles")}
        >
          Profiles
        </button>
        <button
          type="button"
          className={resultsTab === "trials" ? "active" : ""}
          onClick={() => setResultsTab("trials")}
        >
          Trials
        </button>
        <button
          type="button"
          className={resultsTab === "analysis" ? "active" : ""}
          onClick={() => setResultsTab("analysis")}
        >
          Analysis
        </button>
      </div>

      {resultsTab === "profiles" && (
        <div className="tuner-results-panel">
          <div className="tuner-profile-filter-bar">
            <div className="form-group">
              <label htmlFor="tuner_profile_version_filter">Version</label>
              <select
                id="tuner_profile_version_filter"
                value={profileFilter.version}
                onChange={(e) =>
                  setProfileFilter((prev: Record<string, any>) => ({
                    ...prev,
                    version: e.target.value,
                  }))
                }
              >
                <option value="all">All</option>
                <option value="1">v1</option>
                <option value="2">v2</option>
              </select>
            </div>
            <div className="form-group">
              <label htmlFor="tuner_profile_date_from">Created from</label>
              <input
                id="tuner_profile_date_from"
                type="date"
                value={profileFilter.dateFrom}
                onChange={(e) =>
                  setProfileFilter((prev: Record<string, any>) => ({
                    ...prev,
                    dateFrom: e.target.value,
                  }))
                }
              />
            </div>
            <div className="form-group">
              <label htmlFor="tuner_profile_date_to">Created to</label>
              <input
                id="tuner_profile_date_to"
                type="date"
                value={profileFilter.dateTo}
                onChange={(e) =>
                  setProfileFilter((prev: Record<string, any>) => ({
                    ...prev,
                    dateTo: e.target.value,
                  }))
                }
              />
            </div>
            <div className="form-group">
              <label htmlFor="tuner_profile_sort_field">Sort by</label>
              <select
                id="tuner_profile_sort_field"
                value={profileSort.field}
                onChange={(e) =>
                  setProfileSort((prev: Record<string, any>) => ({
                    ...prev,
                    field: e.target.value,
                  }))
                }
              >
                <option value="score">Score</option>
                <option value="date">Date</option>
                <option value="trades">Trades</option>
              </select>
            </div>
            <button
              type="button"
              className="btn btn-secondary tuner-sort-direction"
              onClick={() =>
                setProfileSort((prev: Record<string, any>) => ({
                  ...prev,
                  direction: prev.direction === "asc" ? "desc" : "asc",
                }))
              }
            >
              {profileSort.direction === "asc" ? "Ascending" : "Descending"}
            </button>
          </div>

          {!filteredSortedProfiles.length ? (
            <div className="adaptive-empty">No profiles match current filter.</div>
          ) : (
            <div className="tuner-profile-grid">
              {filteredSortedProfiles.map((profile, idx) => {
                const profileId = String(profile?.profile_id || "");
                const profileVersion = Number(profile?.adaptive_version || 1);
                const isActive = profileId && profileId === activeProfileId;
                return (
                  <article
                    className={`tuner-profile-card ${isActive ? "active" : ""}`}
                    key={profileId || `profile-${idx}`}
                  >
                    <div className="tuner-profile-card-head">
                      <strong>{profileId || "profile"}</strong>
                      <div className="tuner-profile-badges">
                        {isActive && <span className="tuner-badge-active">Active</span>}
                        <span className="tuner-badge-version">v{profileVersion}</span>
                      </div>
                    </div>

                    <div className="tuner-profile-meta-line">
                      {profile?.date_from || "?"}
                      {" -> "}
                      {profile?.date_to || "?"}
                    </div>
                    <div className="tuner-profile-meta-line">{formatTimestamp(profile?.created_at)}</div>

                    <div className="tuner-profile-metrics">
                      <span className="tuner-metric-chip">Score {Number(profile?.score || 0).toFixed(4)}</span>
                      <span className="tuner-metric-chip">
                        PnL {Number(profile?.metrics?.avg_pnl_pct || 0).toFixed(4)}%
                      </span>
                      <span className="tuner-metric-chip">
                        WR {Number(profile?.metrics?.avg_win_rate_pct || 0).toFixed(2)}%
                      </span>
                      <span className="tuner-metric-chip">
                        Trades {Number(profile?.metrics?.total_trades || 0)}
                      </span>
                    </div>

                    <p className="tuner-profile-candidate">
                      {profileVersion >= 2
                        ? formatV2Candidate(profile?.candidate)
                        : formatCandidate(profile?.candidate)}
                    </p>

                    <div className="tuner-profile-actions">
                      <button
                        className="btn btn-secondary btn-sm"
                        onClick={() => handleApplyProfile(profileId)}
                        disabled={!profileId || applyingProfileId === profileId}
                      >
                        {applyingProfileId === profileId ? "Applying..." : "Apply"}
                      </button>
                    </div>
                  </article>
                );
              })}
            </div>
          )}
        </div>
      )}

      {resultsTab === "trials" && (
        <div className="tuner-results-panel">
          <div className="tuner-trials-table-wrap">
            <table className="tuner-trials-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Score</th>
                  <th>Avg PnL %</th>
                  <th>Win Rate</th>
                  <th>Trades</th>
                  <th>{jobVersion >= 2 ? "Vector" : "Candidate"}</th>
                </tr>
              </thead>
              <tbody>
                {trialRows.map((trial) => {
                  const isExpanded = selectedTrialIndex === trial.trial_index;
                  return (
                    <Fragment key={trial.trial_index}>
                      <tr
                        className={isExpanded ? "active" : ""}
                        onClick={() =>
                          setSelectedTrialIndex((prev) => (prev === trial.trial_index ? null : trial.trial_index))
                        }
                      >
                        <td>{trial.trial_index}</td>
                        <td>{Number(trial.score || 0).toFixed(4)}</td>
                        <td>{Number(trial?.metrics?.avg_pnl_pct || 0).toFixed(4)}</td>
                        <td>{Number(trial?.metrics?.avg_win_rate_pct || 0).toFixed(2)}%</td>
                        <td>{Number(trial?.metrics?.total_trades || 0)}</td>
                        <td>
                          {jobVersion >= 2 ? formatV2Candidate(trial?.candidate) : formatCandidate(trial?.candidate)}
                        </td>
                      </tr>

                      {isExpanded && (
                        <tr className="tuner-trial-expanded-row">
                          <td colSpan={6}>
                            <div className="tuner-trial-expanded">
                              {Array.isArray(trial?.day_results) && trial.day_results.length ? (
                                <div className="tuner-day-results-inline">
                                  {trial.day_results.map((row: Record<string, any>, idx: number) => (
                                    <div
                                      className={`tuner-day-result-pill ${row?.success ? "success" : "failed"}`}
                                      key={`${row?.date || "day"}-${idx}`}
                                    >
                                      <strong>{row?.date || "?"}</strong>
                                      {row?.success ? (
                                        <span>
                                          pnl {Number(row?.pnl_pct || 0).toFixed(4)}% | trades{" "}
                                          {Number(row?.trades || 0)} | win {Number(row?.win_rate_pct || 0).toFixed(2)}%
                                        </span>
                                      ) : (
                                        <span>{row?.error || "failed"}</span>
                                      )}
                                    </div>
                                  ))}
                                </div>
                              ) : (
                                <div className="adaptive-empty">No day-level results.</div>
                              )}
                            </div>
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  );
                })}

                {!trialRows.length && (
                  <tr>
                    <td colSpan={6} className="adaptive-empty">
                      No trials yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {resultsTab === "analysis" && (
        <div className="tuner-results-panel">
          {jobVersion < 2 ? (
            <div className="adaptive-empty">Vector analysis is available for v2 tuning jobs.</div>
          ) : !vectorAnalysis ? (
            <div className="adaptive-empty">No vector analysis available for the selected job.</div>
          ) : (
            <div className="vector-analysis-panel">
              {vectorAnalysis.dimension_importance && (
                <div className="vector-subsection">
                  <h4>Dimension Importance</h4>
                  <DimensionImportanceBars importance={vectorAnalysis.dimension_importance} />
                </div>
              )}

              {vectorAnalysis.top_interactions && (
                <div className="vector-subsection">
                  <h4>Top Interactions</h4>
                  <InteractionsList interactions={vectorAnalysis.top_interactions} />
                </div>
              )}

              {vectorAnalysis.surprising_vectors && (
                <div className="vector-subsection">
                  <h4>Surprising Vectors</h4>
                  <SurprisingVectorsTable vectors={vectorAnalysis.surprising_vectors} />
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </section>
  );
}
