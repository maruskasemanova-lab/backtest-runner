import { Temporal } from "@js-temporal/polyfill";
import type {
  DiagnosticCalendarDayResult,
  DiagnosticCalendarMonthCell,
  DiagnosticCalendarProfileOption,
  DiagnosticCalendarReport,
  DiagnosticCalendarReportBase,
  DiagnosticCalendarReportView,
  DiagnosticCalendarRunFilterOption,
  DiagnosticCalendarTrade,
  DiagnosticCalendarTradeViewMode,
} from "./diagnostic-calendar-types";
import {
  DEFAULT_ACCOUNT_SIZE,
  dayPnlPct,
  formatMonthLabel,
  formatPct,
  formatReasonLabel,
  formatUsd,
  normalizeTradeViewMode,
  pnlPctFromDollars,
  toDateUtc,
  toIsoDateUtc,
  tradePnlPct,
} from "./diagnostic-calendar-core";
import { hasAdaptiveProfileSources } from "./diagnostic-calendar-profiles";
import type { DiagnosticCalendarCellStyle } from "./diagnostic-calendar-core";

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
  const monthStart = toDateUtc(monthStartUtc);
  const rangeStart = toDateUtc(rangeStartUtc);
  const rangeEnd = toDateUtc(rangeEndUtc);
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
) => {
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
