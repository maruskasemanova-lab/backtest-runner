import type {
  DiagnosticCalendarDayDetailState,
  DiagnosticCalendarDayResult,
  DiagnosticCalendarReport,
  DiagnosticCalendarRun,
  DiagnosticCalendarRunFilterOption,
  DiagnosticCalendarRunOption,
  DiagnosticCalendarSnapshotSection,
  DiagnosticCalendarTrade,
} from "./diagnostic-calendar-types";
import {
  buildRunScopeKey,
  dayPnlPct,
  isPlainRecord,
  normalizeTicker,
  runPnlPct,
  runTotalPnlPct,
  toOptionalInt,
  toOptionalNumber,
} from "./diagnostic-calendar-core";
import { formatAdaptiveProfileList, resolveRunProfileFields } from "./diagnostic-calendar-profiles";
import { resolveRunProfileIdentity } from "./diagnostic-calendar-report";

export const dedupeRunsByProfile = (
  runs: DiagnosticCalendarRun[],
): DiagnosticCalendarRun[] => {
  if (!Array.isArray(runs) || runs.length <= 1) return Array.isArray(runs) ? runs : [];

  const byProfileKey = new Map<string, DiagnosticCalendarRun>();
  const scoreRun = (run: DiagnosticCalendarRun | null | undefined): { pnlAbs: number; trades: number } => {
    const trades = Math.max(0, Math.trunc(Number(run?.total_trades ?? 0) || 0));
    const pnlAbs = Math.abs(Number(run?.pnl_dollars ?? 0) || 0);
    return { pnlAbs, trades };
  };
  runs.forEach((run, index) => {
    const identity = resolveRunProfileIdentity(run);
    const profileKey = String(identity?.profileKey || "").trim().toLowerCase();
    const fallbackKey = String(buildRunScopeKey(run) || `run-${index + 1}`).trim().toLowerCase();
    const dedupeKey = profileKey || fallbackKey;
    if (!dedupeKey) return;
    const existing = byProfileKey.get(dedupeKey);
    if (!existing) {
      byProfileKey.set(dedupeKey, run);
      return;
    }
    const existingScore = scoreRun(existing);
    const nextScore = scoreRun(run);
    const shouldReplace = nextScore.trades > existingScore.trades
      || (nextScore.trades === existingScore.trades && nextScore.pnlAbs > existingScore.pnlAbs);
    if (shouldReplace) {
      byProfileKey.set(dedupeKey, run);
    }
  });

  return [...byProfileKey.values()];
};

export const buildSelectedRunOptions = (
  selectedRuns: DiagnosticCalendarRun[],
): DiagnosticCalendarRunOption[] =>
  selectedRuns
    .map((run, index) => {
      const scopeKey = buildRunScopeKey(run);
      if (!scopeKey) return null;
      const runId = String(run?.run_id || `run-${index + 1}`).trim();
      const savedAt = String(run?.report_saved_at || "").trim();
      return {
        label: [runId, `T:${Number(run?.total_trades ?? 0)}`, savedAt].filter(Boolean).join(" | "),
        runId,
        scopeKey,
      };
    })
    .filter((item): item is DiagnosticCalendarRunOption => Boolean(item));

export const resolvePreferredDayRunKey = ({
  queryRunId,
  selectedRunOptions,
}: {
  queryRunId: string;
  selectedRunOptions: DiagnosticCalendarRunOption[];
}): string => {
  if (!selectedRunOptions.length) return "";
  const preferredRunId = String(queryRunId || "").trim();
  if (!preferredRunId) return selectedRunOptions[0].scopeKey;
  return selectedRunOptions.find((item) => item.runId === preferredRunId)?.scopeKey
    || selectedRunOptions[0].scopeKey;
};

export const resolveSelectedRunRecord = ({
  activeDayRunKey,
  selectedRuns,
}: {
  activeDayRunKey: string;
  selectedRuns: DiagnosticCalendarRun[];
}): DiagnosticCalendarRun | null => {
  if (!selectedRuns.length) return null;
  if (!activeDayRunKey) return selectedRuns[0] || null;
  return selectedRuns.find((run) => buildRunScopeKey(run) === activeDayRunKey) || selectedRuns[0] || null;
};

export const buildSelectedRunTradeDetails = ({
  selectedResult,
  selectedRunRecord,
}: {
  selectedResult: DiagnosticCalendarDayResult | null;
  selectedRunRecord: DiagnosticCalendarRun | null;
}): DiagnosticCalendarTrade[] => {
  const dedupeTradeList = (trades: DiagnosticCalendarTrade[]): DiagnosticCalendarTrade[] => {
    if (!Array.isArray(trades) || trades.length <= 1) return Array.isArray(trades) ? trades : [];

    const bySignature = new Map<string, DiagnosticCalendarTrade>();
    trades.forEach((trade, index) => {
      const tradeId = String(trade?.trade_id ?? "").trim().toLowerCase();
      const strategy = String(trade?.strategy ?? "").trim().toLowerCase();
      const side = String(trade?.side ?? "").trim().toLowerCase();
      const entryTime = String(trade?.entry_time ?? "").trim();
      const exitTime = String(trade?.exit_time ?? "").trim();
      const entryReason = String(trade?.entry_reason ?? "").trim().toLowerCase();
      const exitReason = String(trade?.exit_reason ?? "").trim().toLowerCase();
      const barsHeldValue = Number(trade?.bars_held);
      const barsHeld = Number.isFinite(barsHeldValue) ? String(Math.trunc(barsHeldValue)) : "";
      const pnlValue = Number(trade?.pnl_dollars);
      const pnl = Number.isFinite(pnlValue) ? pnlValue.toFixed(8) : "";
      const signature = [
        tradeId,
        strategy,
        side,
        entryTime,
        exitTime,
        entryReason,
        exitReason,
        barsHeld,
        pnl,
      ].join("||");
      const key = signature.replace(/\|/g, "") ? signature : `trade-${index}`;
      if (bySignature.has(key)) return;
      bySignature.set(key, trade);
    });
    return [...bySignature.values()];
  };

  const allTrades = Array.isArray(selectedResult?.trade_details) ? selectedResult.trade_details : [];
  if (!allTrades.length || !selectedRunRecord) return allTrades;

  const selectedRunId = String(selectedRunRecord?.run_id || "").trim();
  const selectedReportDir = String(selectedRunRecord?.report_dir || "").trim();

  const directMatches = allTrades.filter((trade) => {
    const tradeRunId = String(trade?.run_id || "").trim();
    if (selectedRunId && tradeRunId !== selectedRunId) return false;
    if (!selectedReportDir) return true;
    return String(trade?.report_dir || "").trim() === selectedReportDir;
  });
  if (directMatches.length) return directMatches;

  const selectedProfileKey = String(resolveRunProfileIdentity(selectedRunRecord)?.profileKey || "").trim().toLowerCase();
  if (!selectedProfileKey) return directMatches;

  const dayRuns = Array.isArray(selectedResult?.runs) ? selectedResult.runs : [];
  if (!dayRuns.length) return directMatches;

  const runIdToProfileKey = new Map<string, string>();
  const distinctProfileKeys = new Set<string>();
  dayRuns.forEach((run) => {
    const runId = String(run?.run_id || "").trim();
    if (!runId) return;
    const profileKey = String(resolveRunProfileIdentity(run)?.profileKey || "").trim().toLowerCase();
    if (!profileKey) return;
    if (!runIdToProfileKey.has(runId)) runIdToProfileKey.set(runId, profileKey);
    distinctProfileKeys.add(profileKey);
  });

  const profileMatches = allTrades.filter((trade) => {
    const tradeRunId = String(trade?.run_id || "").trim();
    if (!tradeRunId) return false;
    return runIdToProfileKey.get(tradeRunId) === selectedProfileKey;
  });
  if (profileMatches.length) return dedupeTradeList(profileMatches);

  if (distinctProfileKeys.size === 1) return dedupeTradeList(allTrades);
  return directMatches;
};

export const buildRunConfigSnapshotSections = ({
  selectedRunExecutionConfig,
  selectedRunRequestConfig,
}: {
  selectedRunExecutionConfig: Record<string, unknown>;
  selectedRunRequestConfig: Record<string, unknown>;
}): DiagnosticCalendarSnapshotSection[] => {
  const sections = [];
  if (isPlainRecord(selectedRunRequestConfig) && Object.keys(selectedRunRequestConfig).length) {
    sections.push({
      title: "Run Request Config",
      description: "Exact start payload snapshot captured for this run.",
      config: selectedRunRequestConfig,
    });
  }
  if (isPlainRecord(selectedRunExecutionConfig) && Object.keys(selectedRunExecutionConfig).length) {
    sections.push({
      title: "Effective Execution Config",
      description: "Resolved runtime execution settings after profile/default merge.",
      config: selectedRunExecutionConfig,
    });
  }
  return sections;
};

const RUN_KEY_RANGE_PATTERN = /^(\d{4}-\d{2}-\d{2})_to_(\d{4}-\d{2}-\d{2})$/;

const extractRunKeyDateRange = (
  runKey: string | null | undefined,
): { dateFrom: string; dateTo: string } | null => {
  if (!runKey) return null;
  const datePart = String(runKey).trim().split(":").pop() || "";
  const match = datePart.match(RUN_KEY_RANGE_PATTERN);
  if (!match) return null;
  return { dateFrom: match[1], dateTo: match[2] };
};

export const buildSelectedDayAnalyzerPayload = ({
  selectedDate,
  selectedRunRecord,
  ticker,
}: {
  selectedDate: string | null;
  selectedRunRecord: DiagnosticCalendarRun | null;
  ticker: string;
}) => {
  if (!selectedDate) return null;
  const normalizedTicker = normalizeTicker(ticker);
  if (!normalizedTicker) return null;
  const selectedRunKey = String(selectedRunRecord?.run_key || "").trim() || null;
  const selectedRunId = String(selectedRunRecord?.run_id || "").trim() || null;
  const selectedProfileKey = String(resolveRunProfileIdentity(selectedRunRecord)?.profileKey || "")
    .trim()
    .toLowerCase();
  const selectedVariantKey = selectedProfileKey.startsWith("variant:")
    ? selectedProfileKey
    : null;
  const dateRange = extractRunKeyDateRange(selectedRunKey);
  return {
    ticker: normalizedTicker,
    isoDate: selectedDate,
    runKey: selectedRunKey,
    runId: selectedRunId,
    variantKey: selectedVariantKey,
    dateFrom: dateRange?.dateFrom ?? null,
    dateTo: dateRange?.dateTo ?? null,
  };
};

export const buildSelectedRunSnapshotSubtitle = ({
  selectedDate,
  selectedRunRecord,
  ticker,
}: {
  selectedDate: string | null;
  selectedRunRecord: DiagnosticCalendarRun | null;
  ticker: string;
}) => {
  const normalizedTicker = normalizeTicker(ticker);
  const dateLabel = String(selectedDate || "").trim();
  const runId = String(selectedRunRecord?.run_id || "").trim();
  const context = [normalizedTicker, dateLabel].filter(Boolean).join(" | ");
  if (runId && context) return `${context} | Run ${runId}`;
  if (runId) return `Run ${runId}`;
  return context || "Read-only diagnostic snapshot";
};

export const buildDiagnosticDayDetailState = ({
  activeDayRunKey,
  selectedDate,
  selectedResult,
  selectedRunOptions,
  selectedRunRecord,
  selectedRuns,
  ticker,
}: {
  activeDayRunKey: string;
  selectedDate: string | null;
  selectedResult: DiagnosticCalendarDayResult | null;
  selectedRunOptions: DiagnosticCalendarRunOption[];
  selectedRunRecord: DiagnosticCalendarRun | null;
  selectedRuns: DiagnosticCalendarRun[];
  ticker: string;
}): DiagnosticCalendarDayDetailState => {
  const selectedStrategyNames = Array.isArray(selectedRunRecord?.strategy_names)
    && selectedRunRecord.strategy_names.length
    ? selectedRunRecord.strategy_names
    : Array.isArray(selectedResult?.strategy_names)
      ? selectedResult.strategy_names
      : [];
  const selectedRunProfiles = resolveRunProfileFields(selectedRunRecord);
  const selectedDayProfileList = selectedResult ? formatAdaptiveProfileList(selectedResult) : null;
  const selectedRunRequestConfig = isPlainRecord(selectedRunRecord?.run_request_config)
    ? selectedRunRecord.run_request_config
    : isPlainRecord(selectedResult?.run_request_config)
      ? selectedResult.run_request_config
      : {};
  const selectedRunExecutionConfig = isPlainRecord(selectedRunRecord?.execution_config)
    ? selectedRunRecord.execution_config
    : isPlainRecord(selectedResult?.execution_config)
      ? selectedResult.execution_config
      : {};
  const selectedRunConfigSnapshotSections = buildRunConfigSnapshotSections({
    selectedRunExecutionConfig,
    selectedRunRequestConfig,
  });
  const selectedRunTradeDetails = buildSelectedRunTradeDetails({ selectedResult, selectedRunRecord });
  const selectedDayAnalyzerPayload = buildSelectedDayAnalyzerPayload({
    selectedDate,
    selectedRunRecord,
    ticker,
  });

  const dayMetrics = {
    barsProcessed:
      toOptionalInt(selectedRunRecord?.processed_bars) ?? toOptionalInt(selectedResult?.processed_bars),
    barsTotal:
      toOptionalInt(selectedRunRecord?.total_bars) ?? toOptionalInt(selectedResult?.total_bars),
    pnlDollars: Number(selectedRunRecord?.pnl_dollars ?? selectedResult?.pnl_dollars ?? 0),
    pnlPct: selectedRunRecord ? runPnlPct(selectedRunRecord) : dayPnlPct(selectedResult),
    regimeEvals:
      toOptionalInt(selectedRunRecord?.regime_evaluations)
      ?? toOptionalInt(selectedResult?.regime_evaluations),
    signals: toOptionalInt(selectedRunRecord?.signals) ?? toOptionalInt(selectedResult?.signals),
    trades: Number(
      selectedRunRecord?.total_trades
        ?? (selectedRunTradeDetails.length || selectedResult?.total_trades || 0),
    ),
  };

  const runMetrics = {
    barsProcessed: toOptionalInt(selectedRunRecord?.run_processed_bars),
    barsTotal: toOptionalInt(selectedRunRecord?.run_total_bars),
    pnlDollars: toOptionalNumber(selectedRunRecord?.run_total_pnl_dollars),
    pnlPct: selectedRunRecord ? runTotalPnlPct(selectedRunRecord) : null,
    regimeEvals: toOptionalInt(selectedRunRecord?.run_regime_evaluations),
    signals: toOptionalInt(selectedRunRecord?.run_signals),
    trades: toOptionalInt(selectedRunRecord?.run_total_trades),
  };

  return {
    dayDetailModel: {
      activeDayRunKey,
      canOpenSelectedDayInAnalyzer: Boolean(selectedDayAnalyzerPayload),
      dayMetrics,
      hasSelectedRunConfigSnapshot: selectedRunConfigSnapshotSections.length > 0,
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
    },
    selectedRunConfigSnapshotSections,
    selectedRunSnapshotSubtitle: buildSelectedRunSnapshotSubtitle({
      selectedDate,
      selectedRunRecord,
      ticker,
    }),
  };
};

export const buildDiagnosticHistoryRequestUrl = ({
  ticker,
  historyLimit,
  runId,
  adaptiveProfileId,
}: {
  ticker: string;
  historyLimit: number;
  runId: string;
  adaptiveProfileId: string;
}) => {
  const params = new URLSearchParams();
  params.set("limit", String(historyLimit));
  params.set("include_multi_day", "true");
  params.set("include_zero_trade_runs", "true");
  if (runId) params.set("run_id", runId);
  if (adaptiveProfileId) {
    params.set("unified_profile_id", adaptiveProfileId);
    params.set("adaptive_profile_id", adaptiveProfileId);
  }
  return `/api/reports/history/${encodeURIComponent(ticker)}?${params.toString()}`;
};

export const resolveReportPath = ({
  report,
  ticker,
  historyLimit,
  runId,
  adaptiveProfileId,
}: {
  report: DiagnosticCalendarReport | null | undefined;
  ticker: string;
  historyLimit: number;
  runId: string;
  adaptiveProfileId: string;
}) => {
  const sourceMode = String(report?.source_mode || "").trim().toLowerCase();
  const sourceHint = String(report?.source_path_hint || "").trim();
  let sourceLabel = sourceHint;
  if (!sourceLabel) {
    if (sourceMode === "supabase_run_reports") sourceLabel = "supabase.run_summaries";
    else if (sourceMode === "sqlite_run_reports") sourceLabel = "sqlite.run_summaries";
    else if (sourceMode === "run_reports_store") sourceLabel = "run_reports_store";
    else sourceLabel = "reports/*/session_summary.json";
  }
  const segments = [
    sourceLabel,
    `ticker=${ticker}`,
    `limit=${historyLimit}`,
  ];
  if (runId) segments.push(`run_id=${runId}`);
  if (adaptiveProfileId) segments.push(`unified=${adaptiveProfileId}`);
  return segments.join(" | ");
};
