import { describe, expect, it } from "vitest";
import {
  buildDiagnosticCalendarUrl,
  buildDiagnosticHistoryRequestUrl,
  buildMonthGrid,
  buildDiagnosticReportBase,
  buildDiagnosticReportView,
  buildRunScopeKey,
  formatAdaptiveProfileList,
  formatMonthLabel,
  getDayCellStyle,
  hasAdaptiveProfileSources,
  readDiagnosticCalendarUrlState,
  resolveReportPath,
  resolveRunProfileFields,
  toDateUtc,
  toIsoDateUtc,
} from "./diagnostic-calendar-utils";

describe("diagnostic-calendar utils", () => {
  it("builds history request url with unified and legacy adaptive aliases", () => {
    const url = buildDiagnosticHistoryRequestUrl({
      ticker: "MU",
      historyLimit: 25,
      runId: "run-42",
      adaptiveProfileId: "profile-x",
    });

    expect(url).toContain("/api/reports/history/MU?");
    expect(url).toContain("limit=25");
    expect(url).toContain("include_multi_day=true");
    expect(url).toContain("include_zero_trade_runs=true");
    expect(url).toContain("run_id=run-42");
    expect(url).toContain("unified_profile_id=profile-x");
    expect(url).toContain("adaptive_profile_id=profile-x");
  });

  it("uses report source fallback when source hint is absent", () => {
    expect(
      resolveReportPath({
        report: { day_results: [], source_mode: "supabase_run_reports" },
        ticker: "MU",
        historyLimit: 5,
        runId: "",
        adaptiveProfileId: "",
      }),
    ).toBe("supabase.run_summaries | ticker=MU | limit=5");
  });

  it("parses and serializes diagnostic url filters", () => {
    const state = readDiagnosticCalendarUrlState(
      "?diag_ticker=nvda&diag_limit=13&diag_profile=profile-a&diag_run_id=run-7&diag_trade_view=adaptive",
    );

    expect(state).toEqual({
      adaptiveProfileId: "profile-a",
      historyLimit: 13,
      runId: "run-7",
      ticker: "NVDA",
      tradeViewMode: "adaptive",
    });

    expect(
      buildDiagnosticCalendarUrl({
        filters: state,
        href: "http://localhost:5173/?view=diagnostic",
      }),
    ).toContain("diag_ticker=NVDA");
  });

  it("builds run scope keys with report dir when present", () => {
    expect(buildRunScopeKey({ run_id: "run-1", report_dir: "/tmp/reports/a" })).toBe(
      "run-1@@/tmp/reports/a",
    );
    expect(buildRunScopeKey({ run_id: "run-1" })).toBe("run-1");
  });

  it("resolves run profiles from execution config and aos metadata", () => {
    expect(
      resolveRunProfileFields({
        execution_config: { unified_profile_id: "u-1" },
        aos_applied: {
          adaptive_profile: { profile_name: "adaptive-fast" },
          strategy_combo: { profile_id: "combo-7" },
        },
      }),
    ).toEqual({
      unifiedProfile: "u-1",
      adaptiveProfile: "adaptive-fast",
      strategyComboProfile: "combo-7",
    });
  });

  it("detects adaptive profile sources and aggregates unique profile tokens", () => {
    const dayResult = {
      date: "2025-01-02",
      execution_config: {
        entry_filter_source: "adaptive_profile",
        active_adaptive_tuner_profile_id: "adaptive-1",
      },
      unified_profile_id: "unified-a",
      unified_profile_names: ["Unified A", "Unified A"],
      runs: [
        {
          adaptive_profile_name: "adaptive-1",
          strategy_combo_profile_name: "combo-main",
        },
      ],
    };

    expect(hasAdaptiveProfileSources(dayResult)).toBe(true);
    expect(formatAdaptiveProfileList(dayResult)).toBe(
      "unified-a | adaptive-1 | Unified A | combo-main",
    );
  });

  it("builds monthly report view projections from normalized report data", () => {
    const reportBase = buildDiagnosticReportBase({
      day_results: [
        { date: "2025-01-03", pnl_dollars: 100, success: true, total_trades: 2 },
        { date: "2025-01-02", pnl_dollars: -50, success: true, total_trades: 1 },
      ],
      split: {
        start: "2025-01-01",
        end: "2025-01-31",
      },
    });

    const reportView = buildDiagnosticReportView({
      report: reportBase.report,
      reportDayResults: reportBase.reportDayResults,
      tradeViewMode: "all",
    });

    expect(reportView.dayResults.map((item) => item.date)).toEqual([
      "2025-01-02",
      "2025-01-03",
    ]);
    expect(reportView.summary.totalTrades).toBe(3);
    expect(reportView.monthlyViews).toHaveLength(1);
    expect(reportView.maxAbsPnlPct).toBeGreaterThan(0);
  });

  it("uses Temporal plain dates for month labels and grid generation", () => {
    const monthStart = toDateUtc("2025-02-01");
    const rangeStart = toDateUtc("2025-02-03");
    const rangeEnd = toDateUtc("2025-02-05");
    const cells = buildMonthGrid(
      monthStart,
      rangeStart,
      rangeEnd,
      new Map([["2025-02-04", { date: "2025-02-04" }]]),
    );

    expect(formatMonthLabel(monthStart)).toBe("February 2025");
    expect(toIsoDateUtc(monthStart)).toBe("2025-02-01");
    expect(cells.find((cell) => cell?.isoDate === "2025-02-04")?.result).toEqual({ date: "2025-02-04" });
    expect(cells.find((cell) => cell?.isoDate === "2025-02-02")?.inRange).toBe(false);
    expect(cells.find((cell) => cell?.isoDate === "2025-02-03")?.inRange).toBe(true);
  });

  it("returns css variable payloads for heatmap intensity instead of rgba strings", () => {
    expect(getDayCellStyle({ date: "2025-01-02", success: false }, 4)).toEqual({
      "--diagnostic-cell-border-intensity": "45%",
      "--diagnostic-cell-intensity": "18%",
    });

    expect(getDayCellStyle({ date: "2025-01-02", pnl_dollars: 100, execution_config: { account_size_usd: 10000 } }, 1)).toEqual({
      "--diagnostic-cell-border-intensity": "55%",
      "--diagnostic-cell-intensity": "70.0%",
    });
  });
});
