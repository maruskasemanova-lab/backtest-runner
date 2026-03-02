import { useCallback, useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  parseAsInteger,
  parseAsString,
  parseAsStringLiteral,
  useQueryStates,
} from "nuqs";
import { parseDiagnosticCalendarReport } from "./diagnostic-calendar-schema";
import {
  DEFAULT_TRADE_VIEW_MODE,
  DEFAULT_DIAGNOSTIC_TICKER,
  DEFAULT_HISTORY_LIMIT,
  DIAGNOSTIC_CALENDAR_URL_KEYS,
  buildDiagnosticDayDetailState,
  buildDiagnosticHistoryRequestUrl,
  buildDiagnosticReportBase,
  buildDiagnosticReportView,
  buildSelectedRunOptions,
  dedupeRunsByProfile,
  normalizeHistoryLimit,
  normalizeTicker,
  normalizeTradeViewMode,
  resolvePreferredDayRunKey,
  resolvePreferredDiagnosticDate,
  resolveReportPath,
  resolveSelectedRunRecord,
} from "./diagnostic-calendar-utils";

const EMPTY_REPORT_BASE = buildDiagnosticReportBase(null);
const DIAGNOSTIC_TRADE_VIEW_MODES = ["all", "adaptive"] as const;
const diagnosticUrlParsers = {
  adaptiveProfileId: parseAsString.withDefault(""),
  historyLimit: parseAsInteger
    .withDefault(DEFAULT_HISTORY_LIMIT)
    .withOptions({ clearOnDefault: false }),
  runId: parseAsString.withDefault(""),
  ticker: parseAsString
    .withDefault(DEFAULT_DIAGNOSTIC_TICKER)
    .withOptions({ clearOnDefault: false }),
  tradeViewMode: parseAsStringLiteral(DIAGNOSTIC_TRADE_VIEW_MODES)
    .withDefault(DEFAULT_TRADE_VIEW_MODE),
  variantFilter: parseAsString.withDefault(""),
};

const buildQueryErrorMessage = (error) => {
  if (error instanceof Error) {
    return String(error.message || "Failed to load report.");
  }
  return "Failed to load report.";
};

const buildDraftFilters = (urlFilters) => ({
  adaptiveProfileId: String(urlFilters?.adaptiveProfileId || "").trim(),
  historyLimit: String(normalizeHistoryLimit(urlFilters?.historyLimit)),
  runId: String(urlFilters?.runId || "").trim(),
  ticker: normalizeTicker(urlFilters?.ticker),
});

const normalizeUrlFilters = (filters) => ({
  adaptiveProfileId: String(filters?.adaptiveProfileId || "").trim(),
  historyLimit: normalizeHistoryLimit(filters?.historyLimit),
  runId: String(filters?.runId || "").trim(),
  ticker: normalizeTicker(filters?.ticker),
  tradeViewMode: normalizeTradeViewMode(filters?.tradeViewMode),
  variantFilter: String(filters?.variantFilter || "").trim(),
});

export default function useDiagnosticCalendarViewModel() {
  const [queryState, setQueryState] = useQueryStates(diagnosticUrlParsers, {
    history: "replace",
    urlKeys: DIAGNOSTIC_CALENDAR_URL_KEYS,
  });
  const urlFilters = useMemo(
    () => normalizeUrlFilters(queryState),
    [queryState],
  );
  const [selectedDate, setSelectedDate] = useState(null);
  const [activeDayRunKey, setActiveDayRunKey] = useState("");
  const [showRunConfigSnapshotDialog, setShowRunConfigSnapshotDialog] = useState(false);
  const appliedFilters = useMemo(
    () => buildDraftFilters(urlFilters),
    [urlFilters],
  );

  const commitUrlFilters = useCallback((nextFilters) => {
    const normalizedFilters = normalizeUrlFilters(nextFilters);
    void setQueryState(normalizedFilters);
    return normalizedFilters;
  }, [setQueryState]);

  const reportQuery = useQuery({
    queryKey: [
      "diagnostic-calendar-history",
      urlFilters.ticker,
      urlFilters.historyLimit,
      urlFilters.adaptiveProfileId,
      urlFilters.runId,
    ],
    queryFn: async ({ signal }) => {
      const response = await fetch(
        buildDiagnosticHistoryRequestUrl({
          adaptiveProfileId: urlFilters.adaptiveProfileId,
          historyLimit: urlFilters.historyLimit,
          runId: urlFilters.runId,
          ticker: urlFilters.ticker,
        }),
        { signal },
      );
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        const detail = payload?.detail ? String(payload.detail) : `HTTP ${response.status}`;
        throw new Error(detail);
      }
      return payload;
    },
    retry: false,
    select: (payload) => buildDiagnosticReportBase(parseDiagnosticCalendarReport(payload)),
    staleTime: 30_000,
  });

  const reportBase = reportQuery.data ?? EMPTY_REPORT_BASE;
  const reportView = useMemo(
    () => buildDiagnosticReportView({
      report: reportBase.report,
      reportDayResults: reportBase.reportDayResults,
      tradeViewMode: urlFilters.tradeViewMode,
      variantFilter: urlFilters.variantFilter,
    }),
    [reportBase, urlFilters.tradeViewMode, urlFilters.variantFilter],
  );

  useEffect(() => {
    setSelectedDate((previousSelectedDate) => resolvePreferredDiagnosticDate({
      dayResultMap: reportView.dayResultMap,
      dayResults: reportView.dayResults,
      previousSelectedDate,
    }));
  }, [reportView.dayResultMap, reportView.dayResults]);

  const selectedResult = selectedDate ? reportView.dayResultMap.get(selectedDate) || null : null;
  const selectedRuns = useMemo(() => {
    const rawRuns = Array.isArray(selectedResult?.runs) ? selectedResult.runs : [];
    return dedupeRunsByProfile(rawRuns);
  }, [selectedResult]);
  const selectedRunOptions = useMemo(
    () => buildSelectedRunOptions(selectedRuns),
    [selectedRuns],
  );
  const preferredDayRunKey = useMemo(
    () => resolvePreferredDayRunKey({
      queryRunId: urlFilters.runId,
      selectedRunOptions,
    }),
    [selectedRunOptions, urlFilters.runId],
  );

  useEffect(() => {
    if (!selectedRunOptions.length) {
      if (activeDayRunKey) setActiveDayRunKey("");
      return;
    }
    if (activeDayRunKey && selectedRunOptions.some((item) => item.scopeKey === activeDayRunKey)) {
      return;
    }
    setActiveDayRunKey(preferredDayRunKey);
  }, [activeDayRunKey, preferredDayRunKey, selectedRunOptions]);

  const selectedRunRecord = useMemo(
    () => resolveSelectedRunRecord({
      activeDayRunKey,
      selectedRuns,
    }),
    [activeDayRunKey, selectedRuns],
  );

  const dayDetailState = useMemo(
    () => buildDiagnosticDayDetailState({
      activeDayRunKey,
      selectedDate,
      selectedResult,
      selectedRunOptions,
      selectedRunRecord,
      selectedRuns,
      ticker: urlFilters.ticker,
    }),
    [
      activeDayRunKey,
      selectedDate,
      selectedResult,
      selectedRunOptions,
      selectedRunRecord,
      selectedRuns,
      urlFilters.ticker,
    ],
  );

  useEffect(() => {
    if (!reportQuery.isSuccess || !urlFilters.runId) return;
    const exists = reportBase.runIdOptions.some((item) => item.runId === urlFilters.runId);
    if (exists) return;

    commitUrlFilters({
      ...urlFilters,
      runId: "",
    });
  }, [commitUrlFilters, reportBase.runIdOptions, reportQuery.isSuccess, urlFilters]);

  useEffect(() => {
    if (dayDetailState.dayDetailModel.hasSelectedRunConfigSnapshot || !showRunConfigSnapshotDialog) return;
    setShowRunConfigSnapshotDialog(false);
  }, [dayDetailState.dayDetailModel.hasSelectedRunConfigSnapshot, showRunConfigSnapshotDialog]);

  const setTradeViewMode = useCallback((value) => {
    commitUrlFilters({
      ...urlFilters,
      tradeViewMode: value,
    });
  }, [commitUrlFilters, urlFilters]);

  const setVariantFilter = useCallback((value) => {
    const nextVariantFilter = String(value || "").trim();
    commitUrlFilters({
      ...urlFilters,
      runId: nextVariantFilter ? "" : urlFilters.runId,
      variantFilter: nextVariantFilter,
    });
  }, [commitUrlFilters, urlFilters]);

  const applyDraftFilters = useCallback((draftFilters) => {
    const nextDraftFilters = {
      adaptiveProfileId: String(draftFilters.adaptiveProfileId || "").trim(),
      historyLimit: String(normalizeHistoryLimit(draftFilters.historyLimit)),
      runId: String(draftFilters.runId || "").trim(),
      ticker: normalizeTicker(draftFilters.ticker),
    };

    commitUrlFilters({
      ...urlFilters,
      ...nextDraftFilters,
    });
  }, [commitUrlFilters, urlFilters]);

  const report = reportQuery.isError ? null : reportBase.report;
  const error = reportQuery.isError ? buildQueryErrorMessage(reportQuery.error) : "";

  return {
    calendarModel: {
      dayProfileSummaryMap: reportView.dayProfileSummaryMap,
      dayResults: reportView.dayResults,
      loading: reportQuery.isFetching,
      maxAbsPnlPct: reportView.maxAbsPnlPct,
      monthlyViews: reportView.monthlyViews,
      report,
      selectedDate,
      setSelectedDate,
    },
    dayDetailModel: dayDetailState.dayDetailModel,
    dialogModel: {
      selectedRunConfigSnapshotSections: dayDetailState.selectedRunConfigSnapshotSections,
      selectedRunSnapshotSubtitle: dayDetailState.selectedRunSnapshotSubtitle,
      setShowRunConfigSnapshotDialog,
      showRunConfigSnapshotDialog,
    },
    error,
    filterModel: {
      adaptiveProfileOptions: reportBase.adaptiveProfileOptions,
      appliedFilters,
      applyDraftFilters,
      runIdOptions: reportBase.runIdOptions,
      setTradeViewMode,
      setVariantFilter,
      tradeViewMode: urlFilters.tradeViewMode || DEFAULT_TRADE_VIEW_MODE,
      variantFilter: urlFilters.variantFilter,
    },
    reportPath: resolveReportPath({
      adaptiveProfileId: urlFilters.adaptiveProfileId,
      historyLimit: urlFilters.historyLimit,
      report,
      runId: urlFilters.runId,
      ticker: urlFilters.ticker,
    }),
    setActiveDayRunKey,
    summary: reportView.summary,
  };
}
