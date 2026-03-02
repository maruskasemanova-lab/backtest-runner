import { useEffect, useMemo, useState } from "react";
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
  resolveRunProfileIdentity,
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
  setVariantFilter: (value: string) => void;
  summary: DiagnosticCalendarSummary;
  tradeViewMode: string;
  variantFilter: string;
};

type DiagnosticRunSortMode = "latest" | "profit_desc";
type DiagnosticVariantSummary = {
  runIds: Set<string>;
  totalPnlDollars: number;
  totalTrades: number;
  variantKey: string;
  variantLabel: string;
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
  setVariantFilter,
  summary,
  tradeViewMode,
  variantFilter,
}: DiagnosticCalendarToolbarProps) {
  const [draftFilters, setDraftFilters] = useState(appliedFilters);
  const [runSearch, setRunSearch] = useState("");
  const [runSortMode, setRunSortMode] = useState<DiagnosticRunSortMode>("profit_desc");

  useEffect(() => {
    setDraftFilters(appliedFilters);
  }, [appliedFilters]);

  const runPnlByRunId = useMemo(() => {
    const map = new Map<string, number>();
    if (!report || !Array.isArray(report.day_results)) return map;

    report.day_results.forEach((dayResult) => {
      const runs = Array.isArray(dayResult?.runs) ? dayResult.runs : [];
      runs.forEach((run) => {
        const runId = String(run?.run_id || "").trim();
        if (!runId) return;
        const pnlDollars = Number(run?.pnl_dollars ?? 0);
        const nextPnl = (Number.isFinite(pnlDollars) ? pnlDollars : 0) + (map.get(runId) || 0);
        map.set(runId, nextPnl);
      });
    });
    return map;
  }, [report]);

  const contextVariantSummaries = useMemo(() => {
    const buckets = new Map<string, DiagnosticVariantSummary>();
    if (!report || !Array.isArray(report.day_results)) return [] as DiagnosticVariantSummary[];

    report.day_results.forEach((dayResult) => {
      const runs = Array.isArray(dayResult?.runs) ? dayResult.runs : [];
      runs.forEach((run) => {
        const runId = String(run?.run_id || "").trim();
        if (!runId) return;

        const profileIdentity = resolveRunProfileIdentity(run);
        const variantKey = String(profileIdentity?.profileKey || "").trim();
        if (!variantKey.startsWith("variant:")) return;

        const variantLabel = String(profileIdentity?.profileLabel || variantKey).trim() || variantKey;
        const pnlDollars = Number(run?.pnl_dollars ?? 0);
        const runPnlDollars = Number.isFinite(pnlDollars) ? pnlDollars : 0;
        const runTrades = Math.max(0, Number(run?.total_trades ?? 0) || 0);

        const existing = buckets.get(variantKey);
        if (existing) {
          existing.runIds.add(runId);
          existing.totalPnlDollars += runPnlDollars;
          existing.totalTrades += runTrades;
          return;
        }

        buckets.set(variantKey, {
          runIds: new Set([runId]),
          totalPnlDollars: runPnlDollars,
          totalTrades: runTrades,
          variantKey,
          variantLabel,
        });
      });
    });

    return [...buckets.values()].sort((left, right) => {
      if (right.totalPnlDollars !== left.totalPnlDollars) {
        return right.totalPnlDollars - left.totalPnlDollars;
      }
      return left.variantLabel.localeCompare(right.variantLabel);
    });
  }, [report]);

  const variantRunIdsByKey = useMemo(() => {
    const map = new Map<string, Set<string>>();
    contextVariantSummaries.forEach((item) => {
      map.set(item.variantKey, item.runIds);
    });
    return map;
  }, [contextVariantSummaries]);

  const variantScopedRunIdOptions = useMemo(() => {
    if (!variantFilter) return runIdOptions;
    const allowedRunIds = variantRunIdsByKey.get(variantFilter);
    if (!allowedRunIds || !allowedRunIds.size) return [] as DiagnosticCalendarRunFilterOption[];
    return runIdOptions.filter((option) => allowedRunIds.has(option.runId));
  }, [runIdOptions, variantFilter, variantRunIdsByKey]);

  useEffect(() => {
    if (!variantFilter) return;
    if (contextVariantSummaries.some((item) => item.variantKey === variantFilter)) return;
    setVariantFilter("");
  }, [contextVariantSummaries, variantFilter]);

  useEffect(() => {
    if (!variantFilter) return;
    const selectedRunId = String(draftFilters.runId || "").trim();
    if (!selectedRunId) return;
    const allowedRunIds = variantRunIdsByKey.get(variantFilter);
    if (allowedRunIds?.has(selectedRunId)) return;
    setDraftFilters((previous) => ({ ...previous, runId: "" }));
  }, [draftFilters.runId, variantFilter, variantRunIdsByKey]);

  const filteredRunIdOptions = useMemo(() => {
    const normalizedNeedle = String(runSearch || "").trim().toLowerCase();
    const searchable = normalizedNeedle
      ? variantScopedRunIdOptions.filter((option) => {
        const runId = String(option?.runId || "").trim().toLowerCase();
        const label = String(option?.label || "").trim().toLowerCase();
        return runId.includes(normalizedNeedle) || label.includes(normalizedNeedle);
      })
      : variantScopedRunIdOptions;

    const sorted = runSortMode === "profit_desc"
      ? [...searchable].sort((left, right) => {
        const leftPnl = runPnlByRunId.get(left.runId);
        const rightPnl = runPnlByRunId.get(right.runId);
        const leftScore = typeof leftPnl === "number" && Number.isFinite(leftPnl)
          ? leftPnl
          : Number.NEGATIVE_INFINITY;
        const rightScore = typeof rightPnl === "number" && Number.isFinite(rightPnl)
          ? rightPnl
          : Number.NEGATIVE_INFINITY;
        if (rightScore !== leftScore) return rightScore - leftScore;
        return String(left.label || left.runId).localeCompare(String(right.label || right.runId));
      })
      : searchable;

    const selectedRunId = String(draftFilters.runId || "").trim();
    if (!selectedRunId) return sorted;
    if (variantFilter) return sorted;
    if (sorted.some((option) => option.runId === selectedRunId)) return sorted;

    const selectedOption = runIdOptions.find((option) => option.runId === selectedRunId);
    return selectedOption ? [selectedOption, ...sorted] : sorted;
  }, [
    draftFilters.runId,
    runIdOptions,
    runPnlByRunId,
    runSearch,
    runSortMode,
    variantFilter,
    variantScopedRunIdOptions,
  ]);

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
            Config Variant
            <select
              className="diagnostic-run-variant"
              value={variantFilter}
              onChange={(event) => setVariantFilter(String(event.target.value || ""))}
              disabled={!contextVariantSummaries.length}
            >
              <option value="">All</option>
              {contextVariantSummaries.map((item) => (
                <option key={`variant-${item.variantKey}`} value={item.variantKey}>
                  {item.variantLabel}
                </option>
              ))}
            </select>
          </label>
          <label>
            Run
            <input
              className="diagnostic-run-search"
              type="text"
              value={runSearch}
              onChange={(event) => setRunSearch(event.target.value)}
              placeholder="Search run id..."
            />
            <select
              className="diagnostic-run-sort"
              value={runSortMode}
              onChange={(event) => setRunSortMode(String(event.target.value || "profit_desc") as DiagnosticRunSortMode)}
            >
              <option value="profit_desc">Most Profitable</option>
              <option value="latest">Latest Saved</option>
            </select>
            <select
              value={draftFilters.runId}
              onChange={(event) => setDraftFilters((previous) => ({ ...previous, runId: event.target.value }))}
            >
              <option value="">All</option>
              {filteredRunIdOptions.map((option) => (
                <option key={`run-${option.runId}`} value={option.runId}>
                  {option.label}
                </option>
              ))}
            </select>
            <span className="diagnostic-filter-hint">
              {filteredRunIdOptions.length} / {variantScopedRunIdOptions.length} runs
            </span>
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
        {contextVariantSummaries.length ? (
          <div className="diagnostic-variant-leaderboard">
            <div className="diagnostic-variant-leaderboard-head">
              <strong>Config PnL Leaderboard</strong>
              <span className="diagnostic-filter-hint">
                {contextVariantSummaries.length} variants
              </span>
            </div>
            <div className="diagnostic-variant-leaderboard-list">
              {contextVariantSummaries.map((item) => {
                const pnlClass = item.totalPnlDollars > 0
                  ? "positive"
                  : item.totalPnlDollars < 0
                    ? "negative"
                    : "flat";
                const isActive = variantFilter === item.variantKey;
                return (
                  <button
                    key={`leaderboard-${item.variantKey}`}
                    type="button"
                    className={`diagnostic-variant-row ${isActive ? "active" : ""}`}
                    onClick={() => setVariantFilter(item.variantKey)}
                    title={`Filter runs by ${item.variantLabel}`}
                  >
                    <span className="diagnostic-variant-row-label">{item.variantLabel}</span>
                    <span className={`diagnostic-variant-row-metrics ${pnlClass}`}>
                      {formatUsd(item.totalPnlDollars)} | T:{item.totalTrades} | R:{item.runIds.size}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>
        ) : null}
      </div>
    </section>
  );
}

export default DiagnosticCalendarToolbar;
