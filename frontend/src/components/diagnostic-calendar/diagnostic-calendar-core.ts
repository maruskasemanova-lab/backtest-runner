import { Temporal } from "@js-temporal/polyfill";
import type { CSSProperties } from "react";
import type {
  DiagnosticCalendarDayResult,
  DiagnosticCalendarHistoryFilters,
  DiagnosticCalendarRun,
  DiagnosticCalendarTrade,
  DiagnosticCalendarTradeViewMode,
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

export type DiagnosticCalendarCellStyle = CSSProperties & {
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

const toPlainDateValue = (
  value: Temporal.PlainDate | string | null | undefined,
): Temporal.PlainDate | null => {
  if (value instanceof Temporal.PlainDate) return value;
  if (!value || typeof value !== "string") return null;
  try {
    return Temporal.PlainDate.from(value);
  } catch {
    return null;
  }
};

const plainDateToUtcDate = (
  date: Temporal.PlainDate | string | null | undefined,
): Date | null => {
  const plainDate = toPlainDateValue(date);
  if (!plainDate) return null;
  return new Date(Date.UTC(plainDate.year, plainDate.month - 1, plainDate.day));
};

export const toDateUtc = (
  value: Temporal.PlainDate | string | null | undefined,
): Temporal.PlainDate | null => toPlainDateValue(value);

export const toIsoDateUtc = (
  date: Temporal.PlainDate | string | null | undefined,
): string | null => {
  const plainDate = toPlainDateValue(date);
  return plainDate ? plainDate.toString() : null;
};

export const formatMonthLabel = (
  date: Temporal.PlainDate | string | null | undefined,
): string => {
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

export const pnlPctFromDollars = (
  pnlDollars: unknown,
  accountSize: unknown,
): number => {
  const dollars = Number(pnlDollars);
  const balance = Number(accountSize);
  if (!Number.isFinite(dollars) || !Number.isFinite(balance) || balance <= 0) return 0;
  return (dollars / balance) * 100;
};

export const dayAccountSize = (
  dayResult: DiagnosticCalendarDayResult | null | undefined,
): number =>
  resolveAccountSize(
    dayResult?.execution_config?.account_size_usd,
    dayResult?.runs?.[0]?.execution_config?.account_size_usd,
    dayResult?.account_size_usd,
  );

export const dayPnlPct = (
  dayResult: DiagnosticCalendarDayResult | null | undefined,
): number => pnlPctFromDollars(dayResult?.pnl_dollars, dayAccountSize(dayResult));

export const runAccountSize = (run: DiagnosticCalendarRun | null | undefined): number =>
  resolveAccountSize(
    run?.execution_config?.account_size_usd,
    run?.account_size_usd,
  );

export const runPnlPct = (run: DiagnosticCalendarRun | null | undefined): number =>
  pnlPctFromDollars(run?.pnl_dollars, runAccountSize(run));

export const runTotalPnlPct = (
  run: DiagnosticCalendarRun | null | undefined,
): number => pnlPctFromDollars(run?.run_total_pnl_dollars, runAccountSize(run));

export const tradePnlPct = (
  trade: DiagnosticCalendarTrade | null | undefined,
): number => pnlPctFromDollars(trade?.pnl_dollars, DEFAULT_ACCOUNT_SIZE);

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

export const normalizeTradeViewMode = (
  value: unknown,
): DiagnosticCalendarTradeViewMode =>
  String(value || "").trim().toLowerCase() === "adaptive"
    ? "adaptive"
    : DEFAULT_TRADE_VIEW_MODE;

export const normalizeTicker = (value: unknown): string => {
  const ticker = String(value || "").trim().toUpperCase();
  return ticker || DEFAULT_DIAGNOSTIC_TICKER;
};

export const readDiagnosticCalendarUrlState = (
  search = "",
): DiagnosticCalendarHistoryFilters => {
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
