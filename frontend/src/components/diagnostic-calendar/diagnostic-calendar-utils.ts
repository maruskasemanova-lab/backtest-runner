import { Temporal } from "@js-temporal/polyfill";
import type { CSSProperties } from "react";
import type {
  DiagnosticCalendarDayDetailState,
  DiagnosticCalendarDayResult,
  DiagnosticCalendarHistoryFilters,
  DiagnosticCalendarMonthCell,
  DiagnosticCalendarProfileOption,
  DiagnosticCalendarReport,
  DiagnosticCalendarReportBase,
  DiagnosticCalendarReportView,
  DiagnosticCalendarRun,
  DiagnosticCalendarRunFilterOption,
  DiagnosticCalendarRunOption,
  DiagnosticCalendarRunProfileFields,
  DiagnosticCalendarSnapshotSection,
  DiagnosticCalendarSummary,
  DiagnosticCalendarTrade,
  DiagnosticCalendarTradeViewMode,
  StrategyAnalyzerPayload,
} from "./diagnostic-calendar-types";

const monthFormatter = new Intl.DateTimeFormat("en-US", {
  month: "long",
  year: "numeric",
  timeZone: "UTC",
});

export const WEEKDAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
export const DEFAULT_DIAGNOSTIC_TICKER = "MU";
export const DEFAULT_ACCOUNT_SIZE = 10_000;
export const DEFAULT_HISTORY_LIMIT = 5;
export const MAX_HISTORY_LIMIT = 5000;
export const DEFAULT_TRADE_VIEW_MODE: DiagnosticCalendarTradeViewMode = "all";

type DiagnosticCalendarCellStyle = CSSProperties & {
  "--diagnostic-cell-border-intensity"?: string;
  "--diagnostic-cell-intensity"?: string;
};

export const DIAGNOSTIC_CALENDAR_URL_KEYS = {
  adaptiveProfileId: "diag_profile",
  historyLimit: "diag_limit",
  runId: "diag_run_id",
  ticker: "diag_ticker",
  tradeViewMode: "diag_trade_view",
} as const;

const toPlainDateValue = (value: Temporal.PlainDate | string | null | undefined): Temporal.PlainDate | null => {
  if (value instanceof Temporal.PlainDate) return value;
  if (!value || typeof value !== "string") return null;
  try {
    return Temporal.PlainDate.from(value);
  } catch {
    return null;
  }
};

const plainDateToUtcDate = (date: Temporal.PlainDate | string | null | undefined): Date | null => {
  const plainDate = toPlainDateValue(date);
  if (!plainDate) return null;
  return new Date(Date.UTC(plainDate.year, plainDate.month - 1, plainDate.day));
};

export const toDateUtc = (value: Temporal.PlainDate | string | null | undefined): Temporal.PlainDate | null =>
  toPlainDateValue(value);

export const toIsoDateUtc = (date: Temporal.PlainDate | string | null | undefined): string | null => {
  const plainDate = toPlainDateValue(date);
  return plainDate ? plainDate.toString() : null;
};

export const formatMonthLabel = (date: Temporal.PlainDate | string | null | undefined): string => {
  const utcDate = plainDateToUtcDate(date);
  return utcDate ? monthFormatter.format(utcDate) : "";
};

export const formatPct = (value: unknown): string => {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "n/a";
  const sign = numeric > 0 ? "+" : "";
  return `${sign}${numeric.toFixed(2)}%`;
};

export const formatUsd = (value: unknown): string => {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "n/a";
  const sign = numeric > 0 ? "+" : "";
  return `${sign}$${numeric.toFixed(2)}`;
};

export const resolveAccountSize = (...candidates: unknown[]): number => {
  for (const candidate of candidates) {
    const numeric = Number(candidate);
    if (Number.isFinite(numeric) && numeric > 0) return numeric;
  }
  return DEFAULT_ACCOUNT_SIZE;
};

export const pnlPctFromDollars = (pnlDollars: unknown, accountSize: unknown): number => {
  const dollars = Number(pnlDollars);
  const balance = Number(accountSize);
  if (!Number.isFinite(dollars) || !Number.isFinite(balance) || balance <= 0) return 0;
  return (dollars / balance) * 100;
};

export const dayAccountSize = (dayResult: DiagnosticCalendarDayResult | null | undefined): number =>
  resolveAccountSize(
    dayResult?.execution_config?.account_size_usd,
    dayResult?.runs?.[0]?.execution_config?.account_size_usd,
    dayResult?.account_size_usd,
  );

export const dayPnlPct = (dayResult: DiagnosticCalendarDayResult | null | undefined): number =>
  pnlPctFromDollars(dayResult?.pnl_dollars, dayAccountSize(dayResult));

export const runAccountSize = (run: DiagnosticCalendarRun | null | undefined): number =>
  resolveAccountSize(
    run?.execution_config?.account_size_usd,
    run?.account_size_usd,
  );

export const runPnlPct = (run: DiagnosticCalendarRun | null | undefined): number =>
  pnlPctFromDollars(run?.pnl_dollars, runAccountSize(run));
export const runTotalPnlPct = (run: DiagnosticCalendarRun | null | undefined): number =>
  pnlPctFromDollars(run?.run_total_pnl_dollars, runAccountSize(run));
export const tradePnlPct = (trade: DiagnosticCalendarTrade | null | undefined): number =>
  pnlPctFromDollars(trade?.pnl_dollars, DEFAULT_ACCOUNT_SIZE);

export const toOptionalInt = (value: unknown): number | null => {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return null;
  return Math.trunc(numeric);
};

export const toOptionalNumber = (value: unknown): number | null => {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return null;
  return numeric;
};

export const formatCount = (value: unknown): string => {
  const numeric = toOptionalInt(value);
  if (numeric === null) return "n/a";
  return String(numeric);
};

export const formatBarsPair = (processed: unknown, total: unknown): string => {
  const processedInt = toOptionalInt(processed);
  const totalInt = toOptionalInt(total);
  if (processedInt === null && totalInt === null) return "n/a";
  return `${processedInt ?? "n/a"} / ${totalInt ?? "n/a"}`;
};

export const normalizeHistoryLimit = (rawValue: unknown): number => {
  const parsed = Number.parseInt(String(rawValue ?? ""), 10);
  if (!Number.isFinite(parsed) || parsed <= 0) return DEFAULT_HISTORY_LIMIT;
  return Math.min(parsed, MAX_HISTORY_LIMIT);
};

export const normalizeTradeViewMode = (value: unknown): DiagnosticCalendarTradeViewMode =>
  String(value || "").trim().toLowerCase() === "adaptive"
    ? "adaptive"
    : DEFAULT_TRADE_VIEW_MODE;

export const normalizeTicker = (value: unknown): string => {
  const ticker = String(value || "").trim().toUpperCase();
  return ticker || DEFAULT_DIAGNOSTIC_TICKER;
};

export const readDiagnosticCalendarUrlState = (search = ""): DiagnosticCalendarHistoryFilters => {
  const params = new URLSearchParams(String(search || ""));
  return {
    adaptiveProfileId: String(params.get(DIAGNOSTIC_CALENDAR_URL_KEYS.adaptiveProfileId) || "").trim(),
    historyLimit: normalizeHistoryLimit(params.get(DIAGNOSTIC_CALENDAR_URL_KEYS.historyLimit)),
    runId: String(params.get(DIAGNOSTIC_CALENDAR_URL_KEYS.runId) || "").trim(),
    ticker: normalizeTicker(params.get(DIAGNOSTIC_CALENDAR_URL_KEYS.ticker)),
    tradeViewMode: normalizeTradeViewMode(params.get(DIAGNOSTIC_CALENDAR_URL_KEYS.tradeViewMode)),
  };
};

export const buildDiagnosticCalendarUrl = ({
  filters,
  href = "http://localhost/",
}: {
  filters: Partial<DiagnosticCalendarHistoryFilters> | null | undefined;
  href?: string;
}) => {
  const nextUrl = new URL(href);
  const ticker = normalizeTicker(filters?.ticker);
  const historyLimit = normalizeHistoryLimit(filters?.historyLimit);
  const adaptiveProfileId = String(filters?.adaptiveProfileId || "").trim();
  const runId = String(filters?.runId || "").trim();
  const tradeViewMode = normalizeTradeViewMode(filters?.tradeViewMode);

  nextUrl.searchParams.set(DIAGNOSTIC_CALENDAR_URL_KEYS.ticker, ticker);
  nextUrl.searchParams.set(DIAGNOSTIC_CALENDAR_URL_KEYS.historyLimit, String(historyLimit));

  if (adaptiveProfileId) nextUrl.searchParams.set(DIAGNOSTIC_CALENDAR_URL_KEYS.adaptiveProfileId, adaptiveProfileId);
  else nextUrl.searchParams.delete(DIAGNOSTIC_CALENDAR_URL_KEYS.adaptiveProfileId);

  if (runId) nextUrl.searchParams.set(DIAGNOSTIC_CALENDAR_URL_KEYS.runId, runId);
  else nextUrl.searchParams.delete(DIAGNOSTIC_CALENDAR_URL_KEYS.runId);

  if (tradeViewMode !== DEFAULT_TRADE_VIEW_MODE) {
    nextUrl.searchParams.set(DIAGNOSTIC_CALENDAR_URL_KEYS.tradeViewMode, tradeViewMode);
  } else {
    nextUrl.searchParams.delete(DIAGNOSTIC_CALENDAR_URL_KEYS.tradeViewMode);
  }

  return nextUrl.toString();
};

export const formatTimeUtc = (value: unknown): string | null => {
  if (!value || typeof value !== "string") return null;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return null;
  const hour = String(parsed.getUTCHours()).padStart(2, "0");
  const minute = String(parsed.getUTCMinutes()).padStart(2, "0");
  return `${hour}:${minute} UTC`;
};

export const formatReasonLabel = (value: unknown): string | null => {
  const normalized = String(value ?? "").trim();
  if (!normalized) return null;
  return normalized.replace(/_/g, " ");
};

export const isPlainRecord = (value: unknown): value is Record<string, unknown> =>
  Boolean(value) && typeof value === "object" && !Array.isArray(value);

export const buildRunScopeKey = (run: DiagnosticCalendarRun | null | undefined): string => {
  const runId = String(run?.run_id || "").trim();
  if (!runId) return "";
  const reportDir = String(run?.report_dir || "").trim();
  return reportDir ? `${runId}@@${reportDir}` : runId;
};

const PROFILE_PLACEHOLDER_TOKENS = new Set(["none", "null", "n/a", "na", "undefined", "-"]);

const uniqueCaseInsensitive = (values: unknown[]): string[] => {
  const tokensByKey = new Map<string, string>();
  values.forEach((value) => {
    const normalized = String(value || "").trim();
    if (!normalized) return;
    const key = normalized.toLowerCase();
    if (tokensByKey.has(key)) return;
    tokensByKey.set(key, normalized);
  });
  return [...tokensByKey.values()];
};

const flattenTokenSources = (values: unknown[]): unknown[] =>
  values.flatMap((value) => (Array.isArray(value) ? value : [value]));

export const normalizeProfileToken = (value: unknown): string => {
  const text = String(value ?? "").trim();
  if (!text) return "";
  const normalized = text.toLowerCase();
  if (PROFILE_PLACEHOLDER_TOKENS.has(normalized)) return "";
  return text;
};

export const joinProfileTokens = (...values: unknown[]): string | null => {
  const tokens = uniqueCaseInsensitive(
    flattenTokenSources(values)
      .map((value) => normalizeProfileToken(value))
      .filter(Boolean),
  );
  return tokens.length ? tokens.join(" | ") : null;
};

export const resolveRunProfileFields = (run: DiagnosticCalendarRun | null | undefined): DiagnosticCalendarRunProfileFields => {
  const unifiedProfile = joinProfileTokens(
    run?.unified_profile_id,
    run?.unified_profile_name,
    run?.execution_config?.unified_profile_id,
    run?.execution_config?.unified_profile_name,
    run?.aos_applied?.unified_profile?.active_profile_id,
    run?.aos_applied?.unified_profile?.profile_id,
    run?.aos_applied?.unified_profile?.profile_name,
  );
  const adaptiveProfile = joinProfileTokens(
    run?.adaptive_profile_id,
    run?.adaptive_profile_name,
    run?.execution_config?.adaptive_profile_id,
    run?.execution_config?.active_adaptive_tuner_profile_id,
    run?.aos_applied?.adaptive_profile?.active_profile_id,
    run?.aos_applied?.adaptive_profile?.profile_id,
    run?.aos_applied?.adaptive_profile?.profile_name,
  );
  const strategyComboProfile = joinProfileTokens(
    run?.strategy_combo_profile_id,
    run?.strategy_combo_profile_name,
    run?.execution_config?.strategy_combo_profile_id,
    run?.execution_config?.active_strategy_combo_profile_id,
    run?.aos_applied?.strategy_combo?.active_profile_id,
    run?.aos_applied?.strategy_combo?.profile_id,
    run?.aos_applied?.strategy_combo?.profile_name,
  );
  return {
    unifiedProfile,
    adaptiveProfile,
    strategyComboProfile,
  };
};

export const collectAdaptiveProfileTokens = (dayResult: DiagnosticCalendarDayResult | null | undefined): string[] => {
  const runProfileValues = Array.isArray(dayResult?.runs)
    ? dayResult.runs.flatMap((run) => [
        run?.unified_profile_id,
        run?.unified_profile_name,
        run?.adaptive_profile_id,
        run?.adaptive_profile_name,
        run?.strategy_combo_profile_id,
        run?.strategy_combo_profile_name,
        run?.execution_config?.active_adaptive_tuner_profile_id,
      ])
    : [];

  return uniqueCaseInsensitive(
    flattenTokenSources([
      dayResult?.unified_profile_id,
      dayResult?.unified_profile_name,
      dayResult?.adaptive_profile_id,
      dayResult?.adaptive_profile_name,
      dayResult?.strategy_combo_profile_id,
      dayResult?.strategy_combo_profile_name,
      dayResult?.aos_applied?.unified_profile?.active_profile_id,
      dayResult?.aos_applied?.unified_profile?.profile_id,
      dayResult?.aos_applied?.unified_profile?.profile_name,
      dayResult?.execution_config?.active_adaptive_tuner_profile_id,
      dayResult?.aos_applied?.adaptive_profile?.active_profile_id,
      dayResult?.aos_applied?.adaptive_profile?.profile_id,
      dayResult?.aos_applied?.adaptive_profile?.profile_name,
      dayResult?.aos_applied?.strategy_combo?.active_profile_id,
      dayResult?.aos_applied?.strategy_combo?.profile_name,
      dayResult?.adaptive_profile_ids,
      dayResult?.adaptive_profile_names,
      dayResult?.strategy_combo_profile_ids,
      dayResult?.strategy_combo_profile_names,
      dayResult?.unified_profile_ids,
      dayResult?.unified_profile_names,
      runProfileValues,
    ])
      .map((value) => normalizeProfileToken(value))
      .filter(Boolean),
  );
};

export const hasAdaptiveProfileSources = (dayResult: DiagnosticCalendarDayResult | null | undefined): boolean => {
  if (!dayResult || dayResult.success === false) return false;
  if (Array.isArray(dayResult?.unified_profile_ids) && dayResult.unified_profile_ids.length > 0) return true;
  if (Array.isArray(dayResult?.adaptive_profile_ids) && dayResult.adaptive_profile_ids.length > 0) return true;
  if (Array.isArray(dayResult?.profile_match_modes) && dayResult.profile_match_modes.length > 0) return true;
  if (Array.isArray(dayResult?.runs)) {
    const hasRunMatch = dayResult.runs.some((run) => {
      const mode = String(run?.profile_match_mode || "").trim().toLowerCase();
      if (mode === "exact" || mode === "hint") return true;
      const runUnifiedProfile = normalizeProfileToken(run?.unified_profile_id);
      if (runUnifiedProfile) return true;
      const runProfile = normalizeProfileToken(run?.adaptive_profile_id);
      return Boolean(runProfile);
    });
    if (hasRunMatch) return true;
  }
  if (Array.isArray(dayResult?.strategy_names)) {
    const hasAdaptiveStrategy = dayResult.strategy_names.some((name) =>
      String(name || "").trim().toLowerCase().includes("adaptive")
    );
    if (hasAdaptiveStrategy) return true;
  }
  if (dayResult?.aos_applied?.adaptive_profile?.candidate_applied === true) return true;
  if (dayResult?.aos_applied?.unified_profile?.active_profile_id) return true;

  const executionConfig = dayResult?.execution_config;
  if (!executionConfig || typeof executionConfig !== "object") return false;
  return Object.entries(executionConfig).some(
    ([key, value]) => key.endsWith("_source") && String(value || "").trim().toLowerCase() === "adaptive_profile"
  );
};

export const formatAdaptiveProfileList = (dayResult: DiagnosticCalendarDayResult | null | undefined): string | null => {
  const tokens = collectAdaptiveProfileTokens(dayResult);
  if (!tokens.length) return null;
  return tokens.join(" | ");
};

export const buildTradeSummary = (trade: DiagnosticCalendarTrade, index: number): string => {
  const parts = [`#${index + 1}`];
  const runId = String(trade?.run_id || "").trim();
  if (runId) parts.push(runId);
  const strategy = String(trade?.strategy || "").trim();
  const side = String(trade?.side || "").trim();
  if (strategy) parts.push(strategy);
  if (side) parts.push(side.toUpperCase());
  parts.push(`${formatPct(tradePnlPct(trade))} / ${formatUsd(trade?.pnl_dollars)}`);
  return parts.join(" | ");
};

export const buildDayTooltip = (
  isoDate: string,
  dayResult: DiagnosticCalendarDayResult | null | undefined,
): string => {
  if (!dayResult) return `${isoDate}\nNo run result.`;
  if (dayResult.success === false) {
    const error = String(dayResult.error || "Unknown error");
    return `${isoDate}\nStatus: Failed\nError: ${error}`;
  }

  const lines = [
    isoDate,
    `Day PnL: ${formatPct(dayPnlPct(dayResult))} (${formatUsd(dayResult.pnl_dollars)})`,
    `Trades: ${Number(dayResult.total_trades ?? 0)}`,
  ];
  const runCount = Number(
    dayResult?.report_count
      ?? (Array.isArray(dayResult?.runs) ? dayResult.runs.length : Number.NaN)
  );
  if (Number.isFinite(runCount) && runCount > 1) {
    lines.push(`Runs: ${runCount}`);
  }

  const trades = Array.isArray(dayResult.trade_details) ? dayResult.trade_details : [];
  if (!trades.length) {
    lines.push("No trades.");
    return lines.join("\n");
  }

  lines.push("Top trades:");
  trades.slice(0, 3).forEach((trade, index) => {
    const runId = String(trade?.run_id || "").trim();
    if (runId) lines.push(`#${index + 1} Run: ${runId}`);
    const entryReason = formatReasonLabel(trade?.entry_reason);
    const exitReason = formatReasonLabel(trade?.exit_reason);
    if (entryReason) lines.push(`#${index + 1} Entry: ${entryReason}`);
    if (exitReason) lines.push(`#${index + 1} Exit: ${exitReason}`);
    lines.push(`#${index + 1} PnL: ${formatPct(tradePnlPct(trade))} (${formatUsd(trade?.pnl_dollars)})`);
  });

  if (trades.length > 3) {
    lines.push(`... +${trades.length - 3} more trades`);
  }

  return lines.join("\n");
};

export const buildMonthGrid = (
  monthStartUtc: Temporal.PlainDate | string | null | undefined,
  rangeStartUtc: Temporal.PlainDate | string | null | undefined,
  rangeEndUtc: Temporal.PlainDate | string | null | undefined,
  dayResultMap: Map<string, DiagnosticCalendarDayResult>,
): Array<DiagnosticCalendarMonthCell | null> => {
  const monthStart = toPlainDateValue(monthStartUtc);
  const rangeStart = toPlainDateValue(rangeStartUtc);
  const rangeEnd = toPlainDateValue(rangeEndUtc);
  if (!monthStart || !rangeStart || !rangeEnd) return [];

  const mondayFirstOffset = monthStart.dayOfWeek - 1;
  const cells = [];
  for (let i = 0; i < mondayFirstOffset; i += 1) cells.push(null);

  for (let dayOffset = 0; dayOffset < monthStart.daysInMonth; dayOffset += 1) {
    const date = monthStart.add({ days: dayOffset });
    const iso = toIsoDateUtc(date);
    const inRange = Temporal.PlainDate.compare(date, rangeStart) >= 0
      && Temporal.PlainDate.compare(date, rangeEnd) <= 0;
    cells.push({
      isoDate: iso,
      day: date.day,
      inRange,
      result: iso ? dayResultMap.get(iso) || null : null,
    });
  }

  while (cells.length % 7 !== 0) cells.push(null);
  return cells;
};

export const getDayCellStyle = (
  dayResult: DiagnosticCalendarDayResult | null | undefined,
  maxAbsPnlPct: number,
): DiagnosticCalendarCellStyle => {
  if (!dayResult) return {};
  if (dayResult.success === false) {
    return {
      "--diagnostic-cell-border-intensity": "45%",
      "--diagnostic-cell-intensity": "18%",
    };
  }

  const pnlPct = dayPnlPct(dayResult);
  if (!Number.isFinite(pnlPct) || pnlPct === 0) return {};

  const scaleBase = maxAbsPnlPct > 0 ? maxAbsPnlPct : 1;
  const strength = Math.min(1, Math.abs(pnlPct) / scaleBase);
  const alphaPct = 18 + strength * 52;
  return {
    "--diagnostic-cell-border-intensity": "55%",
    "--diagnostic-cell-intensity": `${alphaPct.toFixed(1)}%`,
  };
};

export const buildAdaptiveProfileOptions = (
  report: DiagnosticCalendarReport | null | undefined,
): DiagnosticCalendarProfileOption[] => {
  const raw = Array.isArray(report?.filter_options?.unified_profiles)
    ? report.filter_options.unified_profiles
    : Array.isArray(report?.filter_options?.adaptive_profiles)
      ? report.filter_options.adaptive_profiles
      : [];

  return raw
    .map((item) => {
      const profileId = String(item?.profile_id || "").trim();
      if (!profileId) return null;
      const label = [
        profileId,
        String(item?.profile_name || "").trim(),
        item?.active ? "active" : "",
        String(item?.source || "").trim(),
      ]
        .filter(Boolean)
        .join(" | ");
      return {
        profileId,
        label,
      };
    })
    .filter((item): item is DiagnosticCalendarProfileOption => Boolean(item));
};

export const buildRunIdOptions = (
  report: DiagnosticCalendarReport | null | undefined,
): DiagnosticCalendarRunFilterOption[] => {
  const raw = Array.isArray(report?.filter_options?.run_ids)
    ? report.filter_options.run_ids
    : [];

  return raw
    .map((item) => {
      const runId = String(item?.run_id || "").trim();
      if (!runId) return null;
      const savedAt = String(item?.latest_saved_at || "").trim();
      return {
        runId,
        label: savedAt ? `${runId} | ${savedAt}` : runId,
      };
    })
    .filter((item): item is DiagnosticCalendarRunFilterOption => Boolean(item));
};

export const buildDiagnosticReportBase = (
  payload: DiagnosticCalendarReport | null,
): DiagnosticCalendarReportBase => {
  const report = payload ?? ({ day_results: [] } as DiagnosticCalendarReport);
  const reportDayResults = Array.isArray(report?.day_results)
    ? report.day_results
        .filter((item) => item && typeof item === "object" && typeof item.date === "string")
        .sort((left, right) => String(left.date).localeCompare(String(right.date)))
    : [];

  return {
    adaptiveProfileOptions: buildAdaptiveProfileOptions(report),
    report,
    reportDayResults,
    runIdOptions: buildRunIdOptions(report),
  };
};

export const buildDiagnosticSummary = (
  dayResults: DiagnosticCalendarDayResult[],
): DiagnosticCalendarSummary => {
  const failedDays = dayResults.filter((item) => item.success === false).length;
  const totalDays = dayResults.length;
  const validDays = dayResults.filter((item) => item.success !== false).length;
  const totalTrades = dayResults.reduce((sum, item) => sum + Number(item?.total_trades ?? 0), 0);
  const totalPnlDollars = dayResults.reduce((sum, item) => {
    if (item?.success === false) return sum;
    return sum + Number(item?.pnl_dollars ?? 0);
  }, 0);

  return {
    failedDays,
    totalDays,
    totalPnlDollars,
    totalPnlPct: pnlPctFromDollars(totalPnlDollars, DEFAULT_ACCOUNT_SIZE),
    totalTrades,
    validDays,
  };
};

export const buildDiagnosticReportView = ({
  report,
  reportDayResults,
  tradeViewMode,
}: {
  report: DiagnosticCalendarReport | null | undefined;
  reportDayResults: DiagnosticCalendarDayResult[];
  tradeViewMode: DiagnosticCalendarTradeViewMode;
}) => {
  const dayResults = normalizeTradeViewMode(tradeViewMode) === "adaptive"
    ? reportDayResults.filter(
        (item) => Number(item?.total_trades ?? 0) > 0 && hasAdaptiveProfileSources(item),
      )
    : reportDayResults;

  const dayResultMap = new Map(dayResults.map((item) => [item.date, item]));
  const rangeStart = normalizeTradeViewMode(tradeViewMode) === "adaptive"
    ? (dayResults.length ? toDateUtc(dayResults[0].date) : null)
    : toDateUtc(report?.split?.start) || (dayResults.length ? toDateUtc(dayResults[0].date) : null);
  const rangeEnd = normalizeTradeViewMode(tradeViewMode) === "adaptive"
    ? (dayResults.length ? toDateUtc(dayResults[dayResults.length - 1].date) : null)
    : toDateUtc(report?.split?.end)
      || (dayResults.length ? toDateUtc(dayResults[dayResults.length - 1].date) : null);
  const successfulDays = dayResults.filter((item) => item.success !== false);
  const maxAbsPnlPct = successfulDays.reduce((maxValue, item) => {
    const pnl = dayPnlPct(item);
    return Number.isFinite(pnl) ? Math.max(maxValue, Math.abs(pnl)) : maxValue;
  }, 0);

  const monthlyViews: DiagnosticCalendarReportView["monthlyViews"] = [];
  if (rangeStart && rangeEnd) {
    let cursor = rangeStart.with({ day: 1 });
    const stop = rangeEnd.with({ day: 1 });

    while (Temporal.PlainDate.compare(cursor, stop) <= 0) {
      const monthStart = cursor;
      monthlyViews.push({
        cells: buildMonthGrid(monthStart, rangeStart, rangeEnd, dayResultMap),
        id: `${monthStart.year}-${String(monthStart.month).padStart(2, "0")}`,
        label: formatMonthLabel(monthStart),
      });
      cursor = cursor.add({ months: 1 });
    }
  }

  return {
    dayResultMap,
    dayResults,
    maxAbsPnlPct,
    monthlyViews,
    summary: buildDiagnosticSummary(dayResults),
  };
};

export const resolvePreferredDiagnosticDate = ({
  dayResultMap,
  dayResults,
  previousSelectedDate,
}: {
  dayResultMap: Map<string, DiagnosticCalendarDayResult>;
  dayResults: DiagnosticCalendarDayResult[];
  previousSelectedDate: string | null;
}) => {
  if (!dayResults.length) return null;
  if (previousSelectedDate && dayResultMap.has(previousSelectedDate)) return previousSelectedDate;

  const firstFailed = dayResults.find((item) => item.success === false);
  if (firstFailed?.date) return firstFailed.date;

  const strongestSuccessfulDay = dayResults.reduce((bestMatch, item) => {
    if (item?.success === false) return bestMatch;
    if (!bestMatch) return item;
    return Math.abs(dayPnlPct(item)) > Math.abs(dayPnlPct(bestMatch)) ? item : bestMatch;
  }, null);

  return strongestSuccessfulDay?.date || dayResults[0].date;
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
  const allTrades = Array.isArray(selectedResult?.trade_details) ? selectedResult.trade_details : [];
  if (!allTrades.length || !selectedRunRecord) return allTrades;

  const selectedRunId = String(selectedRunRecord?.run_id || "").trim();
  const selectedReportDir = String(selectedRunRecord?.report_dir || "").trim();

  return allTrades.filter((trade) => {
    const tradeRunId = String(trade?.run_id || "").trim();
    if (selectedRunId && tradeRunId !== selectedRunId) return false;
    if (!selectedReportDir) return true;
    return String(trade?.report_dir || "").trim() === selectedReportDir;
  });
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
  return {
    ticker: normalizedTicker,
    isoDate: selectedDate,
    runKey: selectedRunKey,
    runId: selectedRunId,
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
