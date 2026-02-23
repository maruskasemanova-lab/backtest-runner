import { useEffect, useMemo, useState } from "react";

const WEEKDAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

const monthFormatter = new Intl.DateTimeFormat("en-US", {
  month: "long",
  year: "numeric",
  timeZone: "UTC",
});
const DEFAULT_ACCOUNT_SIZE = 10_000;
const DEFAULT_HISTORY_LIMIT = 5;
const MAX_HISTORY_LIMIT = 5000;

const toDateUtc = (value) => {
  if (!value || typeof value !== "string") return null;
  const date = new Date(`${value}T00:00:00Z`);
  return Number.isNaN(date.getTime()) ? null : date;
};

const toIsoDateUtc = (date) => {
  if (!(date instanceof Date)) return null;
  const year = date.getUTCFullYear();
  const month = String(date.getUTCMonth() + 1).padStart(2, "0");
  const day = String(date.getUTCDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
};

const formatPct = (value) => {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "n/a";
  const sign = numeric > 0 ? "+" : "";
  return `${sign}${numeric.toFixed(2)}%`;
};

const formatUsd = (value) => {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "n/a";
  const sign = numeric > 0 ? "+" : "";
  return `${sign}$${numeric.toFixed(2)}`;
};

const resolveAccountSize = (...candidates) => {
  for (const candidate of candidates) {
    const numeric = Number(candidate);
    if (Number.isFinite(numeric) && numeric > 0) return numeric;
  }
  return DEFAULT_ACCOUNT_SIZE;
};

const pnlPctFromDollars = (pnlDollars, accountSize) => {
  const dollars = Number(pnlDollars);
  const balance = Number(accountSize);
  if (!Number.isFinite(dollars) || !Number.isFinite(balance) || balance <= 0) return 0;
  return (dollars / balance) * 100;
};

const dayAccountSize = (dayResult) =>
  resolveAccountSize(
    dayResult?.execution_config?.account_size_usd,
    dayResult?.runs?.[0]?.execution_config?.account_size_usd,
    dayResult?.account_size_usd,
  );

const dayPnlPct = (dayResult) => pnlPctFromDollars(dayResult?.pnl_dollars, dayAccountSize(dayResult));

const runAccountSize = (run) =>
  resolveAccountSize(
    run?.execution_config?.account_size_usd,
    run?.account_size_usd,
  );

const runPnlPct = (run) => pnlPctFromDollars(run?.pnl_dollars, runAccountSize(run));
const runTotalPnlPct = (run) => pnlPctFromDollars(run?.run_total_pnl_dollars, runAccountSize(run));
const tradePnlPct = (trade) => pnlPctFromDollars(trade?.pnl_dollars, DEFAULT_ACCOUNT_SIZE);

const toOptionalInt = (value) => {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return null;
  return Math.trunc(numeric);
};

const toOptionalNumber = (value) => {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return null;
  return numeric;
};

const formatCount = (value) => {
  const numeric = toOptionalInt(value);
  if (numeric === null) return "n/a";
  return String(numeric);
};

const formatBarsPair = (processed, total) => {
  const processedInt = toOptionalInt(processed);
  const totalInt = toOptionalInt(total);
  if (processedInt === null && totalInt === null) return "n/a";
  return `${processedInt ?? "n/a"} / ${totalInt ?? "n/a"}`;
};

const normalizeHistoryLimit = (rawValue) => {
  const parsed = Number.parseInt(String(rawValue ?? ""), 10);
  if (!Number.isFinite(parsed) || parsed <= 0) return DEFAULT_HISTORY_LIMIT;
  return Math.min(parsed, MAX_HISTORY_LIMIT);
};

const formatTimeUtc = (value) => {
  if (!value || typeof value !== "string") return null;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return null;
  const hour = String(parsed.getUTCHours()).padStart(2, "0");
  const minute = String(parsed.getUTCMinutes()).padStart(2, "0");
  return `${hour}:${minute} UTC`;
};

const formatReasonLabel = (value) => {
  const normalized = String(value ?? "").trim();
  if (!normalized) return null;
  return normalized.replace(/_/g, " ");
};

const buildRunScopeKey = (run) => {
  const runId = String(run?.run_id || "").trim();
  if (!runId) return "";
  const reportDir = String(run?.report_dir || "").trim();
  return reportDir ? `${runId}@@${reportDir}` : runId;
};

const PROFILE_PLACEHOLDER_TOKENS = new Set(["none", "null", "n/a", "na", "undefined", "-"]);

const normalizeProfileToken = (value) => {
  const text = String(value ?? "").trim();
  if (!text) return "";
  const normalized = text.toLowerCase();
  if (PROFILE_PLACEHOLDER_TOKENS.has(normalized)) return "";
  return text;
};

const joinProfileTokens = (...values) => {
  const tokens = [];
  const seen = new Set();
  values.forEach((value) => {
    const normalized = normalizeProfileToken(value);
    if (!normalized) return;
    const key = normalized.toLowerCase();
    if (seen.has(key)) return;
    seen.add(key);
    tokens.push(normalized);
  });
  return tokens.length ? tokens.join(" | ") : null;
};

const resolveRunProfileFields = (run) => {
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

const collectAdaptiveProfileTokens = (dayResult) => {
  const tokens = [];
  const pushToken = (value) => {
    const text = normalizeProfileToken(value);
    if (!text) return;
    tokens.push(text);
  };

  pushToken(dayResult?.unified_profile_id);
  pushToken(dayResult?.unified_profile_name);
  pushToken(dayResult?.adaptive_profile_id);
  pushToken(dayResult?.adaptive_profile_name);
  pushToken(dayResult?.strategy_combo_profile_id);
  pushToken(dayResult?.strategy_combo_profile_name);
  pushToken(dayResult?.aos_applied?.unified_profile?.active_profile_id);
  pushToken(dayResult?.aos_applied?.unified_profile?.profile_id);
  pushToken(dayResult?.aos_applied?.unified_profile?.profile_name);
  pushToken(dayResult?.execution_config?.active_adaptive_tuner_profile_id);
  pushToken(dayResult?.aos_applied?.adaptive_profile?.active_profile_id);
  pushToken(dayResult?.aos_applied?.adaptive_profile?.profile_id);
  pushToken(dayResult?.aos_applied?.adaptive_profile?.profile_name);
  pushToken(dayResult?.aos_applied?.strategy_combo?.active_profile_id);
  pushToken(dayResult?.aos_applied?.strategy_combo?.profile_name);
  if (Array.isArray(dayResult?.adaptive_profile_ids)) {
    dayResult.adaptive_profile_ids.forEach((item) => pushToken(item));
  }
  if (Array.isArray(dayResult?.adaptive_profile_names)) {
    dayResult.adaptive_profile_names.forEach((item) => pushToken(item));
  }
  if (Array.isArray(dayResult?.strategy_combo_profile_ids)) {
    dayResult.strategy_combo_profile_ids.forEach((item) => pushToken(item));
  }
  if (Array.isArray(dayResult?.strategy_combo_profile_names)) {
    dayResult.strategy_combo_profile_names.forEach((item) => pushToken(item));
  }
  if (Array.isArray(dayResult?.unified_profile_ids)) {
    dayResult.unified_profile_ids.forEach((item) => pushToken(item));
  }
  if (Array.isArray(dayResult?.unified_profile_names)) {
    dayResult.unified_profile_names.forEach((item) => pushToken(item));
  }
  if (Array.isArray(dayResult?.runs)) {
    dayResult.runs.forEach((run) => {
      pushToken(run?.unified_profile_id);
      pushToken(run?.unified_profile_name);
      pushToken(run?.adaptive_profile_id);
      pushToken(run?.adaptive_profile_name);
      pushToken(run?.strategy_combo_profile_id);
      pushToken(run?.strategy_combo_profile_name);
      pushToken(run?.execution_config?.active_adaptive_tuner_profile_id);
    });
  }
  return [...new Set(tokens)];
};

const hasAdaptiveProfileSources = (dayResult) => {
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

const formatAdaptiveProfileList = (dayResult) => {
  const tokens = collectAdaptiveProfileTokens(dayResult);
  if (!tokens.length) return null;
  return tokens.join(" | ");
};

const buildTradeSummary = (trade, index) => {
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

const buildDayTooltip = (isoDate, dayResult) => {
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

const buildMonthGrid = (monthStartUtc, rangeStartUtc, rangeEndUtc, dayResultMap) => {
  const year = monthStartUtc.getUTCFullYear();
  const month = monthStartUtc.getUTCMonth();
  const firstDay = new Date(Date.UTC(year, month, 1));
  const daysInMonth = new Date(Date.UTC(year, month + 1, 0)).getUTCDate();

  const mondayFirstOffset = (firstDay.getUTCDay() + 6) % 7;
  const cells = [];
  for (let i = 0; i < mondayFirstOffset; i += 1) cells.push(null);

  for (let day = 1; day <= daysInMonth; day += 1) {
    const date = new Date(Date.UTC(year, month, day));
    const iso = toIsoDateUtc(date);
    const inRange = date >= rangeStartUtc && date <= rangeEndUtc;
    cells.push({
      isoDate: iso,
      day,
      inRange,
      result: iso ? dayResultMap.get(iso) || null : null,
    });
  }

  while (cells.length % 7 !== 0) cells.push(null);
  return cells;
};

const getDayCellStyle = (dayResult, maxAbsPnlPct) => {
  if (!dayResult) return {};
  if (dayResult.success === false) {
    return {
      background: "rgba(220, 38, 38, 0.18)",
      borderColor: "rgba(220, 38, 38, 0.45)",
    };
  }

  const pnlPct = dayPnlPct(dayResult);
  if (!Number.isFinite(pnlPct) || pnlPct === 0) return {};

  const scaleBase = maxAbsPnlPct > 0 ? maxAbsPnlPct : 1;
  const strength = Math.min(1, Math.abs(pnlPct) / scaleBase);
  const alpha = 0.18 + strength * 0.52;

  if (pnlPct > 0) {
    return {
      background: `rgba(15, 118, 110, ${alpha.toFixed(3)})`,
      borderColor: "rgba(15, 118, 110, 0.55)",
    };
  }
  return {
    background: `rgba(220, 38, 38, ${alpha.toFixed(3)})`,
    borderColor: "rgba(220, 38, 38, 0.55)",
  };
};

function DiagnosticCalendar() {
  const [draftTicker, setDraftTicker] = useState("MU");
  const [draftHistoryLimit, setDraftHistoryLimit] = useState(String(DEFAULT_HISTORY_LIMIT));
  const [draftAdaptiveProfileId, setDraftAdaptiveProfileId] = useState("");
  const [draftRunId, setDraftRunId] = useState("");
  const [queryTicker, setQueryTicker] = useState("MU");
  const [queryHistoryLimit, setQueryHistoryLimit] = useState(DEFAULT_HISTORY_LIMIT);
  const [queryAdaptiveProfileId, setQueryAdaptiveProfileId] = useState("");
  const [queryRunId, setQueryRunId] = useState("");
  const [report, setReport] = useState(null);
  const [selectedDate, setSelectedDate] = useState(null);
  const [activeDayRunKey, setActiveDayRunKey] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [tradeViewMode, setTradeViewMode] = useState("all");

  useEffect(() => {
    let cancelled = false;

    const fetchReport = async () => {
      setLoading(true);
      setError("");
      try {
        const params = new URLSearchParams();
        params.set("limit", String(queryHistoryLimit));
        params.set("include_multi_day", "true");
        params.set("include_zero_trade_runs", "true");
        if (queryRunId) params.set("run_id", queryRunId);
        if (queryAdaptiveProfileId) {
          params.set("unified_profile_id", queryAdaptiveProfileId);
          // Backward compatible alias for older backend filters.
          params.set("adaptive_profile_id", queryAdaptiveProfileId);
        }
        const requestUrl = `/api/reports/history/${encodeURIComponent(queryTicker)}?${params.toString()}`;
        const response = await fetch(requestUrl);
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) {
          const detail = payload?.detail ? String(payload.detail) : `HTTP ${response.status}`;
          throw new Error(detail);
        }
        if (!cancelled) setReport(payload);
      } catch (err) {
        if (!cancelled) {
          setReport(null);
          setSelectedDate(null);
          setError(err?.message || "Failed to load report.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    fetchReport();
    return () => {
      cancelled = true;
    };
  }, [queryTicker, queryHistoryLimit, queryRunId, queryAdaptiveProfileId]);

  const reportDayResults = useMemo(() => {
    if (!Array.isArray(report?.day_results)) return [];
    return report.day_results
      .filter((item) => item && typeof item === "object" && typeof item.date === "string")
      .sort((a, b) => String(a.date).localeCompare(String(b.date)));
  }, [report]);

  const dayResults = useMemo(() => {
    if (tradeViewMode !== "adaptive") return reportDayResults;
    return reportDayResults.filter(
      (item) =>
        Number(item?.total_trades ?? 0) > 0
        && hasAdaptiveProfileSources(item)
    );
  }, [reportDayResults, tradeViewMode]);

  const dayResultMap = useMemo(() => {
    const map = new Map();
    dayResults.forEach((item) => map.set(item.date, item));
    return map;
  }, [dayResults]);

  const rangeStart = useMemo(() => {
    if (tradeViewMode === "adaptive") {
      if (!dayResults.length) return null;
      return toDateUtc(dayResults[0].date);
    }
    const fromSplit = toDateUtc(report?.split?.start);
    if (fromSplit) return fromSplit;
    return dayResults.length ? toDateUtc(dayResults[0].date) : null;
  }, [report, dayResults, tradeViewMode]);

  const rangeEnd = useMemo(() => {
    if (tradeViewMode === "adaptive") {
      if (!dayResults.length) return null;
      return toDateUtc(dayResults[dayResults.length - 1].date);
    }
    const fromSplit = toDateUtc(report?.split?.end);
    if (fromSplit) return fromSplit;
    return dayResults.length ? toDateUtc(dayResults[dayResults.length - 1].date) : null;
  }, [report, dayResults, tradeViewMode]);

  const successfulDays = useMemo(
    () => dayResults.filter((item) => item.success !== false),
    [dayResults]
  );

  const maxAbsPnlPct = useMemo(() => {
    let maxValue = 0;
    successfulDays.forEach((item) => {
      const pnl = dayPnlPct(item);
      if (Number.isFinite(pnl)) maxValue = Math.max(maxValue, Math.abs(pnl));
    });
    return maxValue;
  }, [successfulDays]);

  const monthlyViews = useMemo(() => {
    if (!rangeStart || !rangeEnd) return [];
    const months = [];
    let cursor = new Date(Date.UTC(rangeStart.getUTCFullYear(), rangeStart.getUTCMonth(), 1));
    const stop = new Date(Date.UTC(rangeEnd.getUTCFullYear(), rangeEnd.getUTCMonth(), 1));

    while (cursor <= stop) {
      const monthStart = new Date(Date.UTC(cursor.getUTCFullYear(), cursor.getUTCMonth(), 1));
      months.push({
        id: `${monthStart.getUTCFullYear()}-${String(monthStart.getUTCMonth() + 1).padStart(2, "0")}`,
        label: monthFormatter.format(monthStart),
        cells: buildMonthGrid(monthStart, rangeStart, rangeEnd, dayResultMap),
      });
      cursor = new Date(Date.UTC(cursor.getUTCFullYear(), cursor.getUTCMonth() + 1, 1));
    }

    return months;
  }, [rangeStart, rangeEnd, dayResultMap]);

  const summary = useMemo(() => {
    const failedDays = dayResults.filter((item) => item.success === false).length;
    const totalDays = dayResults.length;
    const validDays = dayResults.filter((item) => item.success !== false).length;
    const totalTrades = dayResults.reduce((sum, item) => sum + Number(item?.total_trades ?? 0), 0);
    const totalPnlDollars = dayResults.reduce((sum, item) => {
      if (item?.success === false) return sum;
      return sum + Number(item?.pnl_dollars ?? 0);
    }, 0);
    const totalPnlPct = pnlPctFromDollars(totalPnlDollars, DEFAULT_ACCOUNT_SIZE);
    return {
      failedDays,
      totalDays,
      validDays,
      totalTrades,
      totalPnlPct,
      totalPnlDollars,
    };
  }, [report, dayResults]);

  useEffect(() => {
    if (!dayResults.length) {
      setSelectedDate(null);
      return;
    }

    setSelectedDate((prev) => {
      if (prev && dayResultMap.has(prev)) return prev;
      const firstFailed = dayResults.find((item) => item.success === false);
      if (firstFailed?.date) return firstFailed.date;
      const strongest = successfulDays
        .slice()
        .sort((a, b) => Math.abs(dayPnlPct(b)) - Math.abs(dayPnlPct(a)))[0];
      return strongest?.date || dayResults[0].date;
    });
  }, [dayResults, dayResultMap, successfulDays]);

  const selectedResult = selectedDate ? dayResultMap.get(selectedDate) || null : null;
  const selectedRuns = Array.isArray(selectedResult?.runs) ? selectedResult.runs : [];
  const dayStrategyNames = Array.isArray(selectedResult?.strategy_names) ? selectedResult.strategy_names : [];

  const selectedRunOptions = useMemo(() => {
    return selectedRuns
      .map((run, index) => {
        const scopeKey = buildRunScopeKey(run);
        if (!scopeKey) return null;
        const runId = String(run?.run_id || `run-${index + 1}`).trim();
        const savedAt = String(run?.report_saved_at || "").trim();
        const labelParts = [runId, `T:${Number(run?.total_trades ?? 0)}`];
        if (savedAt) labelParts.push(savedAt);
        return {
          scopeKey,
          runId,
          label: labelParts.join(" | "),
        };
      })
      .filter(Boolean);
  }, [selectedRuns]);

  const preferredDayRunKey = useMemo(() => {
    if (!selectedRunOptions.length) return "";
    const preferredRunId = String(queryRunId || "").trim();
    if (preferredRunId) {
      const matched = selectedRunOptions.find((item) => item.runId === preferredRunId);
      if (matched) return matched.scopeKey;
    }
    return selectedRunOptions[0].scopeKey;
  }, [selectedRunOptions, queryRunId]);

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

  const selectedRunRecord = useMemo(() => {
    if (!selectedRuns.length) return null;
    if (activeDayRunKey) {
      const matched = selectedRuns.find((run) => buildRunScopeKey(run) === activeDayRunKey);
      if (matched) return matched;
    }
    return selectedRuns[0] || null;
  }, [selectedRuns, activeDayRunKey]);

  const selectedStrategyNames = useMemo(() => {
    if (Array.isArray(selectedRunRecord?.strategy_names) && selectedRunRecord.strategy_names.length) {
      return selectedRunRecord.strategy_names;
    }
    return dayStrategyNames;
  }, [selectedRunRecord, dayStrategyNames]);

  const selectedRunProfiles = useMemo(
    () => resolveRunProfileFields(selectedRunRecord),
    [selectedRunRecord],
  );
  const selectedDayProfileList = selectedResult ? formatAdaptiveProfileList(selectedResult) : null;

  const selectedRunTradeDetails = useMemo(() => {
    const allTrades = Array.isArray(selectedResult?.trade_details) ? selectedResult.trade_details : [];
    if (!allTrades.length) return [];
    if (!selectedRunRecord) return allTrades;

    const selectedRunId = String(selectedRunRecord?.run_id || "").trim();
    const selectedReportDir = String(selectedRunRecord?.report_dir || "").trim();
    return allTrades.filter((trade) => {
      const tradeRunId = String(trade?.run_id || "").trim();
      if (selectedRunId && tradeRunId !== selectedRunId) return false;
      if (!selectedReportDir) return true;
      return String(trade?.report_dir || "").trim() === selectedReportDir;
    });
  }, [selectedResult, selectedRunRecord]);

  const dayDetailPnlPct = selectedRunRecord
    ? runPnlPct(selectedRunRecord)
    : dayPnlPct(selectedResult);
  const dayDetailPnlDollars = Number(selectedRunRecord?.pnl_dollars ?? selectedResult?.pnl_dollars ?? 0);
  const dayDetailTrades = Number(
    selectedRunRecord?.total_trades
      ?? (selectedRunTradeDetails.length || selectedResult?.total_trades || 0)
  );
  const dayDetailSignals =
    toOptionalInt(selectedRunRecord?.signals)
    ?? toOptionalInt(selectedResult?.signals);
  const dayDetailRegimeEvals =
    toOptionalInt(selectedRunRecord?.regime_evaluations)
    ?? toOptionalInt(selectedResult?.regime_evaluations);
  const dayDetailBarsProcessed =
    toOptionalInt(selectedRunRecord?.processed_bars)
    ?? toOptionalInt(selectedResult?.processed_bars);
  const dayDetailBarsTotal =
    toOptionalInt(selectedRunRecord?.total_bars)
    ?? toOptionalInt(selectedResult?.total_bars);

  const runDetailTrades = toOptionalInt(selectedRunRecord?.run_total_trades);
  const runDetailPnlPct = selectedRunRecord
    ? runTotalPnlPct(selectedRunRecord)
    : null;
  const runDetailPnlDollars = toOptionalNumber(selectedRunRecord?.run_total_pnl_dollars);
  const runDetailSignals = toOptionalInt(selectedRunRecord?.run_signals);
  const runDetailRegimeEvals = toOptionalInt(selectedRunRecord?.run_regime_evaluations);
  const runDetailBarsProcessed = toOptionalInt(selectedRunRecord?.run_processed_bars);
  const runDetailBarsTotal = toOptionalInt(selectedRunRecord?.run_total_bars);

  const adaptiveProfileOptions = useMemo(() => {
    const raw = Array.isArray(report?.filter_options?.unified_profiles)
      ? report.filter_options.unified_profiles
      : (Array.isArray(report?.filter_options?.adaptive_profiles)
          ? report.filter_options.adaptive_profiles
          : []);
    return raw
      .map((item) => {
        const profileId = String(item?.profile_id || "").trim();
        if (!profileId) return null;
        const profileName = String(item?.profile_name || "").trim();
        const isActive = Boolean(item?.active);
        const source = String(item?.source || "").trim();
        const labelParts = [profileId];
        if (profileName) labelParts.push(profileName);
        if (isActive) labelParts.push("active");
        if (source) labelParts.push(source);
        return {
          profileId,
          label: labelParts.join(" | "),
        };
      })
      .filter(Boolean);
  }, [report]);

  const runIdOptions = useMemo(() => {
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
      .filter(Boolean);
  }, [report]);

  useEffect(() => {
    if (!queryRunId) return;
    const exists = runIdOptions.some((item) => item.runId === queryRunId);
    if (exists) return;
    setDraftRunId("");
    setQueryRunId("");
  }, [queryRunId, runIdOptions]);

  const handleSubmit = (event) => {
    event.preventDefault();
    const ticker = String(draftTicker || "").trim().toUpperCase();
    const historyLimit = normalizeHistoryLimit(draftHistoryLimit);
    const runId = String(draftRunId || "").trim();
    const adaptiveProfileId = String(draftAdaptiveProfileId || "").trim();

    setDraftTicker(ticker || "MU");
    setDraftHistoryLimit(String(historyLimit));
    setDraftRunId(runId);
    setDraftAdaptiveProfileId(adaptiveProfileId);

    setQueryTicker(ticker || "MU");
    setQueryHistoryLimit(historyLimit);
    setQueryRunId(runId);
    setQueryAdaptiveProfileId(adaptiveProfileId);
  };

  const reportPath = useMemo(() => {
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
      `ticker=${queryTicker}`,
      `limit=${queryHistoryLimit}`,
    ];
    if (queryRunId) segments.push(`run_id=${queryRunId}`);
    if (queryAdaptiveProfileId) segments.push(`unified=${queryAdaptiveProfileId}`);
    return segments.join(" | ");
  }, [report, queryTicker, queryHistoryLimit, queryRunId, queryAdaptiveProfileId]);

  return (
    <main className="diagnostic-calendar-page">
      <section className="card diagnostic-toolbar-card">
        <div className="card-header">
          <span className="card-title">Diagnostic Calendar</span>
          <span className="diagnostic-source">source: {reportPath}</span>
        </div>
        <div className="card-body">
          <form className="diagnostic-toolbar" onSubmit={handleSubmit}>
            <label>
              Ticker
              <input
                type="text"
                value={draftTicker}
                onChange={(e) => setDraftTicker(e.target.value)}
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
                value={draftHistoryLimit}
                onChange={(e) => setDraftHistoryLimit(e.target.value)}
              />
            </label>
            <label>
              Unified Profile
              <select
                value={draftAdaptiveProfileId}
                onChange={(e) => setDraftAdaptiveProfileId(e.target.value)}
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
              Run
              <select
                value={draftRunId}
                onChange={(e) => setDraftRunId(e.target.value)}
              >
                <option value="">All</option>
                {runIdOptions.map((option) => (
                  <option key={`run-${option.runId}`} value={option.runId}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              View
              <select value={tradeViewMode} onChange={(e) => setTradeViewMode(e.target.value)}>
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

        </div>
      </section>

      <section className="diagnostic-calendar-layout">
        <div className="card diagnostic-months-card">
          <div className="card-header">
            <span className="card-title">By Day</span>
            <div className="diagnostic-legend">
              <span className="legend-chip profit">Profit</span>
              <span className="legend-chip flat">Flat</span>
              <span className="legend-chip loss">Loss</span>
              <span className="legend-chip failed">Failed</span>
            </div>
          </div>
          <div className="card-body diagnostic-months-body">
            {!loading && !report ? (
              <div className="diagnostic-empty">No history loaded.</div>
            ) : null}
            {!loading && report && !dayResults.length ? (
              <div className="diagnostic-empty">No days match selected filter.</div>
            ) : null}
            {monthlyViews.map((month) => (
              <section key={month.id} className="diagnostic-month">
                <h3>{month.label}</h3>
                <div className="diagnostic-weekdays">
                  {WEEKDAY_LABELS.map((label) => (
                    <span key={`${month.id}-${label}`}>{label}</span>
                  ))}
                </div>
                <div className="diagnostic-grid">
                  {month.cells.map((cell, idx) => {
                    if (!cell) {
                      return <div key={`${month.id}-blank-${idx}`} className="diagnostic-cell blank" />;
                    }

                    const result = cell.result;
                    const isSelected = selectedDate === cell.isoDate;
                    const isFailed = result?.success === false;
                    const pnl = dayPnlPct(result);
                    const pnlClass =
                      isFailed
                        ? "failed"
                        : pnl > 0
                          ? "profit"
                          : pnl < 0
                            ? "loss"
                            : "flat";

                    const classes = [
                      "diagnostic-cell",
                      pnlClass,
                      cell.inRange ? "in-range" : "out-range",
                      isSelected ? "selected" : "",
                    ].join(" ").trim();
                    const dayTrades = Number(result?.total_trades ?? 0);
                    const cellTooltip = buildDayTooltip(cell.isoDate, result);

                    return (
                      <button
                        key={cell.isoDate}
                        type="button"
                        className={classes}
                        style={getDayCellStyle(result, maxAbsPnlPct)}
                        disabled={!cell.inRange}
                        onClick={() => {
                          setSelectedDate(cell.isoDate);
                        }}
                        title={cellTooltip}
                      >
                        <span className="day-number">{cell.day}</span>
                        {result ? (
                          <>
                            <span className="day-pnl">
                              {result.success === false ? "ERR" : formatPct(dayPnlPct(result))}
                            </span>
                            <span className={`day-pnl-usd ${result.success === false ? "muted" : ""}`}>
                              {result.success === false ? "-" : formatUsd(result.pnl_dollars ?? 0)}
                            </span>
                            <span className="day-trades">T:{Number.isFinite(dayTrades) ? dayTrades : 0}</span>
                          </>
                        ) : (
                          <>
                            <span className="day-pnl muted">-</span>
                            <span className="day-pnl-usd muted">-</span>
                            <span className="day-trades muted">T:-</span>
                          </>
                        )}
                      </button>
                    );
                  })}
                </div>
              </section>
            ))}
          </div>
        </div>

        <aside className="card diagnostic-day-card">
          <div className="card-header">
            <span className="card-title">Day Detail</span>
            <span className="diagnostic-day-date">{selectedDate || "N/A"}</span>
          </div>
          <div className="card-body">
            {!selectedDate ? <div className="diagnostic-empty">Pick a day.</div> : null}

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
                          dayDetailPnlPct < 0
                            ? "negative"
                            : dayDetailPnlPct > 0
                              ? "positive"
                              : ""
                        }
                      >
                        {formatPct(dayDetailPnlPct)} / {formatUsd(dayDetailPnlDollars)}
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
                      <strong>{formatCount(dayDetailSignals)}</strong>
                    </div>
                    <div className="diagnostic-row">
                      <span>Day Trades</span>
                      <strong>{dayDetailTrades}</strong>
                    </div>
                    <div className="diagnostic-row">
                      <span>Run Trades</span>
                      <strong>{formatCount(runDetailTrades)}</strong>
                    </div>
                    <div className="diagnostic-row">
                      <span>Day Bars</span>
                      <strong>{formatBarsPair(dayDetailBarsProcessed, dayDetailBarsTotal)}</strong>
                    </div>
                    <div className="diagnostic-row">
                      <span>Run Bars</span>
                      <strong>{formatBarsPair(runDetailBarsProcessed, runDetailBarsTotal)}</strong>
                    </div>
                    <div className="diagnostic-row">
                      <span>Day Regime Evals</span>
                      <strong>{formatCount(dayDetailRegimeEvals)}</strong>
                    </div>
                    <div className="diagnostic-row">
                      <span>Run Signals</span>
                      <strong>{formatCount(runDetailSignals)}</strong>
                    </div>
                    <div className="diagnostic-row">
                      <span>Run Regime Evals</span>
                      <strong>{formatCount(runDetailRegimeEvals)}</strong>
                    </div>
                    <div className="diagnostic-row">
                      <span>Run PnL</span>
                      <strong
                        className={
                          (runDetailPnlPct ?? 0) < 0
                            ? "negative"
                            : (runDetailPnlPct ?? 0) > 0
                              ? "positive"
                              : ""
                        }
                      >
                        {formatPct(runDetailPnlPct)} / {formatUsd(runDetailPnlDollars)}
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
                    {selectedRuns.length ? (
                      <div className="diagnostic-trade-list">
                        <div className="diagnostic-trade-list-title">Runs (click to expand)</div>
                        {selectedRuns.map((run, index) => {
                          const runProfiles = resolveRunProfileFields(run);
                          const runSummaryProfile =
                            runProfiles.unifiedProfile
                            || runProfiles.adaptiveProfile
                            || runProfiles.strategyComboProfile;
                          return (
                            <details
                              key={`${selectedDate}-run-${String(run?.run_id || index)}`}
                              className="diagnostic-trade-item"
                            >
                              <summary>
                                {String(run?.run_id || `run-${index + 1}`)} | T:{Number(run?.total_trades ?? 0)}
                                {" | "}
                                {formatPct(runPnlPct(run))} / {formatUsd(run?.pnl_dollars)}
                                {runSummaryProfile ? ` | P:${runSummaryProfile}` : ""}
                              </summary>
                              <div className="diagnostic-trade-content">
                                <div className="diagnostic-row">
                                  <span>Saved At</span>
                                  <strong>{String(run?.report_saved_at || "n/a")}</strong>
                                </div>
                                <div className="diagnostic-row">
                                  <span>Date Label</span>
                                  <strong>{String(run?.date_label || selectedDate || "n/a")}</strong>
                                </div>
                                <div className="diagnostic-row">
                                  <span>Day Signals</span>
                                  <strong>{formatCount(run?.signals)}</strong>
                                </div>
                                <div className="diagnostic-row">
                                  <span>Day Regime Evals</span>
                                  <strong>{formatCount(run?.regime_evaluations)}</strong>
                                </div>
                                <div className="diagnostic-row">
                                  <span>Run Trades</span>
                                  <strong>{formatCount(run?.run_total_trades)}</strong>
                                </div>
                                <div className="diagnostic-row">
                                  <span>Run Bars</span>
                                  <strong>{formatBarsPair(run?.run_processed_bars, run?.run_total_bars)}</strong>
                                </div>
                                <div className="diagnostic-row">
                                  <span>Run PnL</span>
                                  <strong
                                    className={
                                      runTotalPnlPct(run) < 0
                                        ? "negative"
                                        : runTotalPnlPct(run) > 0
                                          ? "positive"
                                          : ""
                                    }
                                  >
                                    {formatPct(runTotalPnlPct(run))} / {formatUsd(run?.run_total_pnl_dollars)}
                                  </strong>
                                </div>
                                {Array.isArray(run?.strategy_names) && run.strategy_names.length ? (
                                  <div className="diagnostic-row">
                                    <span>Strategies</span>
                                    <strong>{run.strategy_names.join(", ")}</strong>
                                  </div>
                                ) : null}
                                {runProfiles.unifiedProfile ? (
                                  <div className="diagnostic-row">
                                    <span>Unified Profile</span>
                                    <strong>{runProfiles.unifiedProfile}</strong>
                                  </div>
                                ) : null}
                                {runProfiles.adaptiveProfile ? (
                                  <div className="diagnostic-row">
                                    <span>Adaptive Profile</span>
                                    <strong>{runProfiles.adaptiveProfile}</strong>
                                  </div>
                                ) : null}
                                {runProfiles.strategyComboProfile ? (
                                  <div className="diagnostic-row">
                                    <span>Strategy Combo Profile</span>
                                    <strong>{runProfiles.strategyComboProfile}</strong>
                                  </div>
                                ) : null}
                                {String(run?.profile_match_mode || "").trim() ? (
                                  <div className="diagnostic-row">
                                    <span>Profile Match</span>
                                    <strong>{String(run?.profile_match_mode || "")}</strong>
                                  </div>
                                ) : null}
                              </div>
                            </details>
                          );
                        })}
                      </div>
                    ) : null}
                    <div className="diagnostic-trade-list">
                      <div className="diagnostic-trade-list-title">
                        Trades for Run {String(selectedRunRecord?.run_id || "n/a")} (click to expand)
                      </div>
                      {selectedRunTradeDetails.length ? (
                        selectedRunTradeDetails.map((trade, index) => (
                          <details
                            key={
                              `${selectedDate}-${String(trade?.run_id || "")}-${String(trade?.report_dir || "")}-${String(trade?.trade_id ?? index)}`
                            }
                            className="diagnostic-trade-item"
                          >
                            <summary>{buildTradeSummary(trade, index)}</summary>
                            <div className="diagnostic-trade-content">
                              {String(trade?.run_id || "").trim() ? (
                                <div className="diagnostic-row">
                                  <span>Run ID</span>
                                  <strong>{String(trade?.run_id || "")}</strong>
                                </div>
                              ) : null}
                              {formatReasonLabel(trade?.entry_reason) ? (
                                <div className="diagnostic-row">
                                  <span>Entry Reason</span>
                                  <strong>{formatReasonLabel(trade?.entry_reason)}</strong>
                                </div>
                              ) : null}
                              {formatReasonLabel(trade?.exit_reason) ? (
                                <div className="diagnostic-row">
                                  <span>Exit Reason</span>
                                  <strong>{formatReasonLabel(trade?.exit_reason)}</strong>
                                </div>
                              ) : null}
                              {formatTimeUtc(trade?.entry_time) ? (
                                <div className="diagnostic-row">
                                  <span>Entry Time</span>
                                  <strong>{formatTimeUtc(trade?.entry_time)}</strong>
                                </div>
                              ) : null}
                              {formatTimeUtc(trade?.exit_time) ? (
                                <div className="diagnostic-row">
                                  <span>Exit Time</span>
                                  <strong>{formatTimeUtc(trade?.exit_time)}</strong>
                                </div>
                              ) : null}
                              <div className="diagnostic-row">
                                <span>Bars Held</span>
                                <strong>{Number(trade?.bars_held ?? 0)}</strong>
                              </div>
                              <div className="diagnostic-row">
                                <span>PnL</span>
                                <strong className={Number(trade?.pnl_dollars ?? 0) < 0 ? "negative" : Number(trade?.pnl_dollars ?? 0) > 0 ? "positive" : ""}>
                                  {formatPct(tradePnlPct(trade))} / {formatUsd(trade?.pnl_dollars)}
                                </strong>
                              </div>
                            </div>
                          </details>
                        ))
                      ) : (
                        <div className="diagnostic-empty">No closed trades for this day.</div>
                      )}
                    </div>
                  </>
                )}
              </div>
            ) : null}
          </div>
        </aside>
      </section>
    </main>
  );
}

export default DiagnosticCalendar;
