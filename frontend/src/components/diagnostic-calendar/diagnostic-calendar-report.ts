import { Temporal } from "@js-temporal/polyfill";
import type {
  DiagnosticCalendarDayResult,
  DiagnosticCalendarMonthCell,
  DiagnosticCalendarProfileDaySummary,
  DiagnosticCalendarProfileOption,
  DiagnosticCalendarReport,
  DiagnosticCalendarReportBase,
  DiagnosticCalendarReportView,
  DiagnosticCalendarRun,
  DiagnosticCalendarRunFilterOption,
  DiagnosticCalendarTrade,
  DiagnosticCalendarTradeViewMode,
} from "./diagnostic-calendar-types";
import {
  DEFAULT_ACCOUNT_SIZE,
  dayAccountSize,
  dayPnlPct,
  formatMonthLabel,
  formatPct,
  formatReasonLabel,
  formatUsd,
  normalizeTradeViewMode,
  pnlPctFromDollars,
  runAccountSize,
  toDateUtc,
  toIsoDateUtc,
  tradePnlPct,
} from "./diagnostic-calendar-core";
import {
  formatAdaptiveProfileList,
  hasAdaptiveProfileSources,
  normalizeProfileToken,
  resolveRunProfileFields,
} from "./diagnostic-calendar-profiles";
import type { DiagnosticCalendarCellStyle } from "./diagnostic-calendar-core";

const UNASSIGNED_PROFILE_KEY = "__no_profile__";
const UNASSIGNED_PROFILE_LABEL = "No Profile";
const CONTEXT_RISK_EPSILON = 1e-9;

type DiagnosticCalendarProfileDayBucket = {
  accountSize: number;
  pnlDollars: number;
  profileKey: string;
  profileLabel: string;
  runCount: number;
  totalTrades: number;
};

const toFiniteNumber = (value: unknown): number | null => {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
};

const toOptionalBoolean = (value: unknown): boolean | null => {
  if (typeof value === "boolean") return value;
  const token = String(value ?? "").trim().toLowerCase();
  if (!token) return null;
  if (token === "true" || token === "1" || token === "yes") return true;
  if (token === "false" || token === "0" || token === "no") return false;
  return null;
};

const nearlyEqual = (left: number | null, right: number): boolean =>
  left !== null && Math.abs(left - right) <= CONTEXT_RISK_EPSILON;

const formatVariantNumber = (value: number | null): string =>
  value === null ? "n/a" : value.toFixed(2);

const toTradeSignature = (trade: DiagnosticCalendarTrade | null | undefined, fallbackIndex: number): string => {
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
  return signature.replace(/\|/g, "") ? signature : `trade-${fallbackIndex}`;
};

const dedupeTradeDetails = (trades: DiagnosticCalendarTrade[]): DiagnosticCalendarTrade[] => {
  if (!Array.isArray(trades) || trades.length <= 1) return Array.isArray(trades) ? trades : [];

  const bySignature = new Map<string, DiagnosticCalendarTrade>();
  trades.forEach((trade, index) => {
    const signature = toTradeSignature(trade, index);
    if (bySignature.has(signature)) return;
    bySignature.set(signature, trade);
  });
  return [...bySignature.values()];
};

const resolveContextRiskVariant = (
  run: DiagnosticCalendarRun | null | undefined,
): { profileKey: string; profileLabel: string } | null => {
  const runId = String(run?.run_id || "").trim().toLowerCase();
  const runRequestConfig = (
    run?.run_request_config && typeof run.run_request_config === "object"
      ? run.run_request_config
      : {}
  ) as Record<string, unknown>;

  const contextAwareRiskEnabled = toOptionalBoolean(runRequestConfig.context_aware_risk_enabled);
  const contextRiskMinRoomPct = toFiniteNumber(runRequestConfig.context_risk_min_room_pct);
  const contextRiskMinEffectiveRr = toFiniteNumber(runRequestConfig.context_risk_min_effective_rr);

  const isNoContextRisk = runId.includes("no_context_risk")
    || contextAwareRiskEnabled === false;
  if (isNoContextRisk) {
    return {
      profileKey: "variant:no_context_risk",
      profileLabel: `no_context_risk (room=${formatVariantNumber(contextRiskMinRoomPct)}, rr=${formatVariantNumber(contextRiskMinEffectiveRr)})`,
    };
  }

  const isRelaxedContext35 = runId.includes("relaxed_context_35")
    || (contextAwareRiskEnabled === true
      && nearlyEqual(contextRiskMinRoomPct, 0.02)
      && nearlyEqual(contextRiskMinEffectiveRr, 0.35));
  if (isRelaxedContext35) {
    return {
      profileKey: "variant:relaxed_context_35",
      profileLabel: `relaxed_context_35 (room=${formatVariantNumber(contextRiskMinRoomPct)}, rr=${formatVariantNumber(contextRiskMinEffectiveRr)})`,
    };
  }

  const isBaseline = runId.includes("baseline")
    || (contextAwareRiskEnabled === true
      && nearlyEqual(contextRiskMinRoomPct, 0.08)
      && nearlyEqual(contextRiskMinEffectiveRr, 0.50));
  if (isBaseline) {
    return {
      profileKey: "variant:baseline",
      profileLabel: `baseline (room=${formatVariantNumber(contextRiskMinRoomPct)}, rr=${formatVariantNumber(contextRiskMinEffectiveRr)})`,
    };
  }

  if (contextAwareRiskEnabled !== null && contextRiskMinRoomPct !== null && contextRiskMinEffectiveRr !== null) {
    const enabledToken = contextAwareRiskEnabled ? "on" : "off";
    return {
      profileKey: `variant:context_risk_${enabledToken}_${contextRiskMinRoomPct.toFixed(4)}_${contextRiskMinEffectiveRr.toFixed(4)}`,
      profileLabel: `context_risk_${enabledToken} (room=${formatVariantNumber(contextRiskMinRoomPct)}, rr=${formatVariantNumber(contextRiskMinEffectiveRr)})`,
    };
  }

  return null;
};

const firstProfileToken = (...values: unknown[]): string | null => {
  for (const value of values) {
    const token = normalizeProfileToken(value);
    if (token) return token;
  }
  return null;
};

export const resolveRunProfileIdentity = (
  run: DiagnosticCalendarRun | null | undefined,
): { profileKey: string; profileLabel: string } => {
  const contextRiskVariant = resolveContextRiskVariant(run);
  if (contextRiskVariant) return contextRiskVariant;

  const unifiedProfileId = firstProfileToken(
    run?.unified_profile_id,
    run?.execution_config?.unified_profile_id,
    run?.execution_config?.active_unified_profile_id,
    run?.aos_applied?.unified_profile?.active_profile_id,
    run?.aos_applied?.unified_profile?.profile_id,
  );
  const unifiedProfileName = firstProfileToken(
    run?.unified_profile_name,
    run?.execution_config?.unified_profile_name,
    run?.aos_applied?.unified_profile?.profile_name,
  );
  if (unifiedProfileId) {
    return {
      profileKey: unifiedProfileId.toLowerCase(),
      profileLabel: unifiedProfileName
        ? `${unifiedProfileId} | ${unifiedProfileName}`
        : unifiedProfileId,
    };
  }

  const adaptiveProfileId = firstProfileToken(
    run?.adaptive_profile_id,
    run?.execution_config?.adaptive_profile_id,
    run?.execution_config?.active_adaptive_tuner_profile_id,
    run?.aos_applied?.adaptive_profile?.active_profile_id,
    run?.aos_applied?.adaptive_profile?.profile_id,
  );
  const adaptiveProfileName = firstProfileToken(
    run?.adaptive_profile_name,
    run?.execution_config?.adaptive_profile_name,
    run?.aos_applied?.adaptive_profile?.profile_name,
  );
  if (adaptiveProfileId) {
    return {
      profileKey: adaptiveProfileId.toLowerCase(),
      profileLabel: adaptiveProfileName
        ? `${adaptiveProfileId} | ${adaptiveProfileName}`
        : adaptiveProfileId,
    };
  }

  const strategyComboProfileId = firstProfileToken(
    run?.strategy_combo_profile_id,
    run?.execution_config?.strategy_combo_profile_id,
    run?.execution_config?.active_strategy_combo_profile_id,
    run?.aos_applied?.strategy_combo?.active_profile_id,
    run?.aos_applied?.strategy_combo?.profile_id,
  );
  const strategyComboProfileName = firstProfileToken(
    run?.strategy_combo_profile_name,
    run?.aos_applied?.strategy_combo?.profile_name,
  );
  if (strategyComboProfileId) {
    return {
      profileKey: strategyComboProfileId.toLowerCase(),
      profileLabel: strategyComboProfileName
        ? `${strategyComboProfileId} | ${strategyComboProfileName}`
        : strategyComboProfileId,
    };
  }

  const profileFields = resolveRunProfileFields(run);
  const fallbackLabel = (
    profileFields.unifiedProfile
    || profileFields.adaptiveProfile
    || profileFields.strategyComboProfile
    || UNASSIGNED_PROFILE_LABEL
  );
  return {
    profileKey: normalizeProfileSummaryKey(fallbackLabel),
    profileLabel: fallbackLabel,
  };
};

const resolveDayFallbackProfileLabel = (
  dayResult: DiagnosticCalendarDayResult | null | undefined,
): string => {
  const formatted = formatAdaptiveProfileList(dayResult);
  if (formatted) return formatted;
  return UNASSIGNED_PROFILE_LABEL;
};

const normalizeProfileSummaryKey = (value: unknown): string => {
  const normalized = normalizeProfileToken(value);
  if (!normalized) return UNASSIGNED_PROFILE_KEY;
  return normalized.toLowerCase();
};

const upsertProfileDayBucket = ({
  accountSize,
  buckets,
  profileKey,
  profileLabel,
  pnlDollars,
  totalTrades,
}: {
  accountSize: number;
  buckets: Map<string, DiagnosticCalendarProfileDayBucket>;
  profileKey: string;
  profileLabel: string;
  pnlDollars: number;
  totalTrades: number;
}) => {
  const existing = buckets.get(profileKey);
  if (existing) {
    // Keep one representative row per day/profile; count duplicates via runCount.
    existing.runCount += 1;
    const existingScore = Math.abs(Number(existing.pnlDollars || 0));
    const nextScore = Math.abs(Number(pnlDollars || 0));
    const shouldReplaceRepresentative = totalTrades > existing.totalTrades
      || (totalTrades === existing.totalTrades && nextScore > existingScore);
    if (shouldReplaceRepresentative) {
      existing.totalTrades = totalTrades;
      existing.pnlDollars = pnlDollars;
      existing.profileLabel = profileLabel || existing.profileLabel;
    }
    if (!(existing.accountSize > 0) && accountSize > 0) {
      existing.accountSize = accountSize;
    }
    return;
  }
  buckets.set(profileKey, {
    accountSize: accountSize > 0 ? accountSize : DEFAULT_ACCOUNT_SIZE,
    pnlDollars,
    profileKey,
    profileLabel: profileLabel || UNASSIGNED_PROFILE_LABEL,
    runCount: 1,
    totalTrades,
  });
};

export const buildDayProfileSummaryMap = (
  dayResults: DiagnosticCalendarDayResult[],
): Map<string, DiagnosticCalendarProfileDaySummary[]> => {
  const map = new Map<string, DiagnosticCalendarProfileDaySummary[]>();

  dayResults.forEach((dayResult) => {
    const isoDate = String(dayResult?.date || "").trim();
    if (!isoDate) return;

    const runs = Array.isArray(dayResult?.runs) ? dayResult.runs : [];
    const buckets = new Map<string, DiagnosticCalendarProfileDayBucket>();

    if (runs.length) {
      runs.forEach((run) => {
        const profileIdentity = resolveRunProfileIdentity(run);
        upsertProfileDayBucket({
          accountSize: runAccountSize(run),
          buckets,
          profileKey: profileIdentity.profileKey,
          profileLabel: profileIdentity.profileLabel,
          pnlDollars: Number(run?.pnl_dollars ?? 0) || 0,
          totalTrades: Math.max(0, Number(run?.total_trades ?? 0) || 0),
        });
      });
    } else {
      const profileLabel = resolveDayFallbackProfileLabel(dayResult);
      const profileKey = normalizeProfileSummaryKey(profileLabel);
      upsertProfileDayBucket({
        accountSize: dayAccountSize(dayResult),
        buckets,
        profileKey,
        profileLabel,
        pnlDollars: Number(dayResult?.pnl_dollars ?? 0) || 0,
        totalTrades: Math.max(0, Number(dayResult?.total_trades ?? 0) || 0),
      });
    }

    const profileSummaries = [...buckets.values()]
      .map((bucket) => ({
        profileKey: bucket.profileKey,
        profileLabel: bucket.profileLabel || UNASSIGNED_PROFILE_LABEL,
        totalTrades: Math.max(0, Math.trunc(Number(bucket.totalTrades || 0))),
        pnlDollars: Number(bucket.pnlDollars || 0),
        pnlPct: pnlPctFromDollars(bucket.pnlDollars, bucket.accountSize),
        runCount: Math.max(1, Math.trunc(Number(bucket.runCount || 0))),
      }))
      .sort((left, right) => left.profileLabel.localeCompare(right.profileLabel));

    map.set(isoDate, profileSummaries);
  });

  return map;
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
  dayProfileSummaries: DiagnosticCalendarProfileDaySummary[] = [],
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
  if (dayProfileSummaries.length > 1) {
    lines.push("Profiles:");
    dayProfileSummaries.forEach((item) => {
      lines.push(
        `- ${item.profileLabel}: ${formatPct(item.pnlPct)} (${formatUsd(item.pnlDollars)}), T:${item.totalTrades}`
      );
    });
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

const toFiniteOrZero = (value: unknown): number => {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : 0;
};

const toOptionalTruncInt = (value: unknown): number | null => {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return null;
  return Math.trunc(numeric);
};

const pushToken = (set: Set<string>, value: unknown) => {
  const token = String(value ?? "").trim();
  if (token) set.add(token);
};

const resolveSingleValue = (set: Set<string>): string | null => {
  if (set.size !== 1) return null;
  return [...set][0] || null;
};

const buildVariantScopedDayResult = (
  dayResult: DiagnosticCalendarDayResult,
  variantFilterKey: string,
): DiagnosticCalendarDayResult | null => {
  if (!variantFilterKey) return dayResult;

  const dayRuns = Array.isArray(dayResult?.runs) ? dayResult.runs : [];
  if (!dayRuns.length) return null;

  const scopedRuns = dayRuns.filter((run) => {
    const identity = resolveRunProfileIdentity(run);
    const profileKey = String(identity?.profileKey || "").trim().toLowerCase();
    return profileKey === variantFilterKey;
  });
  if (!scopedRuns.length) return null;

  const scopedRunIds = new Set(
    scopedRuns
      .map((run) => String(run?.run_id || "").trim())
      .filter(Boolean),
  );
  const tradeDetails = Array.isArray(dayResult?.trade_details)
    ? dayResult.trade_details.filter((trade) => scopedRunIds.has(String(trade?.run_id || "").trim()))
    : [];
  const dedupedTradeDetails = dedupeTradeDetails(tradeDetails);

  const strategyNames = new Set<string>();
  const unifiedProfileIds = new Set<string>();
  const unifiedProfileNames = new Set<string>();
  const adaptiveProfileIds = new Set<string>();
  const adaptiveProfileNames = new Set<string>();
  const strategyComboProfileIds = new Set<string>();
  const strategyComboProfileNames = new Set<string>();
  const profileMatchModes = new Set<string>();
  let totalTrades = 0;
  let pnlDollars = 0;
  let signals = 0;
  let regimeEvaluations = 0;
  let processedBars = 0;
  let totalBars = 0;
  let processedBarsKnownRuns = 0;
  let totalBarsKnownRuns = 0;

  scopedRuns.forEach((run) => {
    totalTrades += Math.max(0, Math.trunc(toFiniteOrZero(run?.total_trades)));
    pnlDollars += toFiniteOrZero(run?.pnl_dollars);
    signals += Math.max(0, Math.trunc(toFiniteOrZero(run?.signals)));
    regimeEvaluations += Math.max(0, Math.trunc(toFiniteOrZero(run?.regime_evaluations)));

    const runProcessedBars = toOptionalTruncInt(run?.processed_bars);
    if (runProcessedBars !== null) {
      processedBars += runProcessedBars;
      processedBarsKnownRuns += 1;
    }
    const runTotalBars = toOptionalTruncInt(run?.total_bars);
    if (runTotalBars !== null) {
      totalBars += runTotalBars;
      totalBarsKnownRuns += 1;
    }

    if (Array.isArray(run?.strategy_names)) {
      run.strategy_names.forEach((name) => pushToken(strategyNames, name));
    }
    pushToken(unifiedProfileIds, run?.unified_profile_id);
    pushToken(unifiedProfileNames, run?.unified_profile_name);
    pushToken(adaptiveProfileIds, run?.adaptive_profile_id);
    pushToken(adaptiveProfileNames, run?.adaptive_profile_name);
    pushToken(strategyComboProfileIds, run?.strategy_combo_profile_id);
    pushToken(strategyComboProfileNames, run?.strategy_combo_profile_name);
    pushToken(profileMatchModes, run?.profile_match_mode);
  });

  const scopedTotalTrades = totalTrades > 0
    ? totalTrades
    : Math.max(0, dedupedTradeDetails.length);
  const dedupedTradePnlDollars = dedupedTradeDetails.reduce(
    (sum, trade) => sum + toFiniteOrZero(trade?.pnl_dollars),
    0,
  );
  const useTradeDerivedTotals = dedupedTradeDetails.length > 0;

  return {
    ...dayResult,
    adaptive_profile_id: resolveSingleValue(adaptiveProfileIds),
    adaptive_profile_ids: [...adaptiveProfileIds].sort(),
    adaptive_profile_name: resolveSingleValue(adaptiveProfileNames),
    adaptive_profile_names: [...adaptiveProfileNames].sort(),
    pnl_dollars: useTradeDerivedTotals ? dedupedTradePnlDollars : pnlDollars,
    processed_bars: processedBarsKnownRuns > 0 ? processedBars : null,
    profile_match_modes: [...profileMatchModes].sort(),
    regime_evaluations: regimeEvaluations,
    report_count: scopedRuns.length,
    runs: scopedRuns,
    signals,
    strategy_combo_profile_id: resolveSingleValue(strategyComboProfileIds),
    strategy_combo_profile_ids: [...strategyComboProfileIds].sort(),
    strategy_combo_profile_name: resolveSingleValue(strategyComboProfileNames),
    strategy_combo_profile_names: [...strategyComboProfileNames].sort(),
    strategy_names: [...strategyNames].sort(),
    total_bars: totalBarsKnownRuns > 0 ? totalBars : null,
    total_trades: useTradeDerivedTotals ? dedupedTradeDetails.length : scopedTotalTrades,
    trade_details: dedupedTradeDetails,
    unified_profile_id: resolveSingleValue(unifiedProfileIds),
    unified_profile_ids: [...unifiedProfileIds].sort(),
    unified_profile_name: resolveSingleValue(unifiedProfileNames),
    unified_profile_names: [...unifiedProfileNames].sort(),
  };
};

export const buildDiagnosticReportView = ({
  report,
  reportDayResults,
  tradeViewMode,
  variantFilter,
}: {
  report: DiagnosticCalendarReport | null | undefined;
  reportDayResults: DiagnosticCalendarDayResult[];
  tradeViewMode: DiagnosticCalendarTradeViewMode;
  variantFilter?: string;
}) => {
  const normalizedVariantFilter = String(variantFilter || "").trim().toLowerCase();
  const variantScopedDayResults = normalizedVariantFilter
    ? reportDayResults
      .map((item) => buildVariantScopedDayResult(item, normalizedVariantFilter))
      .filter((item): item is DiagnosticCalendarDayResult => Boolean(item))
    : reportDayResults;

  const dayResults = normalizeTradeViewMode(tradeViewMode) === "adaptive"
    ? variantScopedDayResults.filter(
        (item) => Number(item?.total_trades ?? 0) > 0 && hasAdaptiveProfileSources(item),
      )
    : variantScopedDayResults;

  const dayResultMap = new Map(dayResults.map((item) => [item.date, item]));
  const dayProfileSummaryMap = buildDayProfileSummaryMap(dayResults);
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
    dayProfileSummaryMap,
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
