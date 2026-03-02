import { describe, expect, it } from "vitest";
import {
  buildDiagnosticCalendarUrl,
  buildDiagnosticHistoryRequestUrl,
  buildMonthGrid,
  buildDiagnosticReportBase,
  buildDayProfileSummaryMap,
  buildDiagnosticReportView,
  buildRunScopeKey,
  buildSelectedRunTradeDetails,
  dedupeRunsByProfile,
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
      variantFilter: "",
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

  it("deduplicates selected day runs to one run per profile identity", () => {
    const deduped = dedupeRunsByProfile([
      {
        run_id: "run-latest",
        report_dir: "/tmp/latest",
        unified_profile_id: "u-alpha",
        total_trades: 0,
      },
      {
        run_id: "run-older",
        report_dir: "/tmp/older",
        unified_profile_id: "u-alpha",
        total_trades: 3,
      },
      {
        run_id: "run-other-profile",
        report_dir: "/tmp/other",
        unified_profile_id: "u-beta",
        total_trades: 3,
      },
    ]);

    expect(deduped.map((run) => run.run_id)).toEqual([
      "run-older",
      "run-other-profile",
    ]);
  });

  it("falls back to profile-scoped trade matching when selected run id has no direct trades", () => {
    const selectedResult = {
      date: "2026-02-18",
      runs: [
        {
          run_id: "screen-ctx_min_sl_040-20260218",
          total_trades: 18,
          run_request_config: {
            context_aware_risk_enabled: true,
            context_risk_min_room_pct: 0.08,
            context_risk_min_effective_rr: 0.5,
          },
        },
        {
          run_id: "oos-b7-comp-baseline-20260218",
          total_trades: 18,
          run_request_config: {
            context_aware_risk_enabled: true,
            context_risk_min_room_pct: 0.08,
            context_risk_min_effective_rr: 0.5,
          },
        },
      ],
      trade_details: [
        { run_id: "oos-b7-comp-baseline-20260218", trade_id: "t1", pnl_dollars: 10 },
        { run_id: "oos-b7-comp-baseline-20260218", trade_id: "t2", pnl_dollars: 8 },
      ],
    };

    const selectedTrades = buildSelectedRunTradeDetails({
      selectedResult,
      selectedRunRecord: selectedResult.runs[0],
    });

    expect(selectedTrades.map((trade) => trade.trade_id)).toEqual(["t1", "t2"]);
  });

  it("deduplicates profile-scoped trades replicated across multiple runs", () => {
    const selectedResult = {
      date: "2026-02-18",
      runs: [
        {
          run_id: "screen-ctx_min_sl_040-20260218",
          run_request_config: {
            context_aware_risk_enabled: true,
            context_risk_min_room_pct: 0.08,
            context_risk_min_effective_rr: 0.5,
          },
        },
        {
          run_id: "oos-b3-baseline-20260218",
          run_request_config: {
            context_aware_risk_enabled: true,
            context_risk_min_room_pct: 0.08,
            context_risk_min_effective_rr: 0.5,
          },
        },
        {
          run_id: "oos-b7-comp-baseline-20260218",
          run_request_config: {
            context_aware_risk_enabled: true,
            context_risk_min_room_pct: 0.08,
            context_risk_min_effective_rr: 0.5,
          },
        },
      ],
      trade_details: [
        {
          run_id: "oos-b3-baseline-20260218",
          strategy: "Momentum",
          side: "LONG",
          entry_time: "2026-02-18T15:45:00Z",
          exit_time: "2026-02-18T16:00:00Z",
          pnl_dollars: 177.4,
          trade_id: "diag-20260218",
        },
        {
          run_id: "oos-b7-comp-baseline-20260218",
          strategy: "Momentum",
          side: "LONG",
          entry_time: "2026-02-18T15:45:00Z",
          exit_time: "2026-02-18T16:00:00Z",
          pnl_dollars: 177.4,
          trade_id: "diag-20260218",
        },
      ],
    };

    const selectedTrades = buildSelectedRunTradeDetails({
      selectedResult,
      selectedRunRecord: selectedResult.runs[0],
    });

    expect(selectedTrades).toHaveLength(1);
    expect(selectedTrades[0]).toMatchObject({
      strategy: "Momentum",
      side: "LONG",
      pnl_dollars: 177.4,
      trade_id: "diag-20260218",
    });
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
    expect(
      reportView.dayProfileSummaryMap.get("2025-01-03")?.map((item) => item.profileLabel)
    ).toEqual(["No Profile"]);
    expect(reportView.summary.totalTrades).toBe(3);
    expect(reportView.monthlyViews).toHaveLength(1);
    expect(reportView.maxAbsPnlPct).toBeGreaterThan(0);
  });

  it("filters day results to selected variant and keeps only matching trades", () => {
    const reportBase = buildDiagnosticReportBase({
      day_results: [
        {
          date: "2026-02-05",
          runs: [
            {
              run_id: "oos-b7-comp-baseline-20260205",
              total_trades: 2,
              pnl_dollars: 40,
              signals: 7,
              regime_evaluations: 6,
              execution_config: { account_size_usd: 10000 },
              run_request_config: {
                context_aware_risk_enabled: true,
                context_risk_min_room_pct: 0.08,
                context_risk_min_effective_rr: 0.5,
              },
            },
            {
              run_id: "oos-b7-comp-relaxed_context_35-20260205",
              total_trades: 3,
              pnl_dollars: 15,
              signals: 4,
              regime_evaluations: 5,
              execution_config: { account_size_usd: 10000 },
              run_request_config: {
                context_aware_risk_enabled: true,
                context_risk_min_room_pct: 0.02,
                context_risk_min_effective_rr: 0.35,
              },
            },
          ],
          trade_details: [
            { run_id: "oos-b7-comp-baseline-20260205", pnl_dollars: 20 },
            { run_id: "oos-b7-comp-baseline-20260205", pnl_dollars: 20 },
            { run_id: "oos-b7-comp-relaxed_context_35-20260205", pnl_dollars: 15 },
          ],
        },
      ],
    });

    const reportView = buildDiagnosticReportView({
      report: reportBase.report,
      reportDayResults: reportBase.reportDayResults,
      tradeViewMode: "all",
      variantFilter: "variant:baseline",
    });

    expect(reportView.dayResults).toHaveLength(1);
    expect(reportView.dayResults[0]?.runs?.map((run) => run.run_id)).toEqual([
      "oos-b7-comp-baseline-20260205",
    ]);
    expect(reportView.dayResults[0]?.trade_details?.map((trade) => trade.run_id)).toEqual([
      "oos-b7-comp-baseline-20260205",
    ]);
    expect(Number(reportView.dayResults[0]?.pnl_dollars ?? 0)).toBe(20);
    expect(Number(reportView.dayResults[0]?.total_trades ?? 0)).toBe(1);
  });

  it("deduplicates same-day runs by profile into one profile summary row", () => {
    const summaryMap = buildDayProfileSummaryMap([
      {
        date: "2025-01-08",
        runs: [
          {
            total_trades: 2,
            pnl_dollars: 120,
            unified_profile_id: "u-alpha",
            execution_config: { account_size_usd: 10000 },
          },
          {
            total_trades: 1,
            pnl_dollars: -20,
            unified_profile_id: "u-alpha",
            execution_config: { account_size_usd: 10000 },
          },
          {
            total_trades: 3,
            pnl_dollars: 80,
            unified_profile_id: "u-beta",
            execution_config: { account_size_usd: 10000 },
          },
        ],
      },
    ]);

    expect(summaryMap.get("2025-01-08")).toEqual([
      {
        profileKey: "u-alpha",
        profileLabel: "u-alpha",
        totalTrades: 2,
        pnlDollars: 120,
        pnlPct: 1.2,
        runCount: 2,
      },
      {
        profileKey: "u-beta",
        profileLabel: "u-beta",
        totalTrades: 3,
        pnlDollars: 80,
        pnlPct: 0.8,
        runCount: 1,
      },
    ]);
  });

  it("groups comparator runs by context-risk variant when unified profile id is shared", () => {
    const summaryMap = buildDayProfileSummaryMap([
      {
        date: "2026-02-24",
        runs: [
          {
            run_id: "oos-b7-comp-baseline-20260224",
            unified_profile_id: "792e993d1d95",
            total_trades: 3,
            pnl_dollars: -12.9686,
            execution_config: { account_size_usd: 10000 },
            run_request_config: {
              context_aware_risk_enabled: true,
              context_risk_min_room_pct: 0.08,
              context_risk_min_effective_rr: 0.5,
            },
          },
          {
            run_id: "oos-b8-comp2-baseline-20260224",
            unified_profile_id: "792e993d1d95",
            total_trades: 1,
            pnl_dollars: 2.0,
            execution_config: { account_size_usd: 10000 },
            run_request_config: {
              context_aware_risk_enabled: true,
              context_risk_min_room_pct: 0.08,
              context_risk_min_effective_rr: 0.5,
            },
          },
          {
            run_id: "oos-b7-comp-relaxed_context_35-20260224",
            unified_profile_id: "792e993d1d95",
            total_trades: 3,
            pnl_dollars: -12.9686,
            execution_config: { account_size_usd: 10000 },
            run_request_config: {
              context_aware_risk_enabled: true,
              context_risk_min_room_pct: 0.02,
              context_risk_min_effective_rr: 0.35,
            },
          },
          {
            run_id: "oos-b7-comp-no_context_risk-20260224",
            unified_profile_id: "792e993d1d95",
            total_trades: 2,
            pnl_dollars: 39.2179,
            execution_config: { account_size_usd: 10000 },
            run_request_config: {
              context_aware_risk_enabled: false,
              context_risk_min_room_pct: 0.08,
              context_risk_min_effective_rr: 0.5,
            },
          },
        ],
      },
    ]);

    const rows = summaryMap.get("2026-02-24") || [];
    expect(rows).toHaveLength(3);
    expect(rows.map((item) => item.profileKey)).toEqual([
      "variant:baseline",
      "variant:no_context_risk",
      "variant:relaxed_context_35",
    ]);

    expect(rows[0]).toMatchObject({
      profileLabel: "baseline (room=0.08, rr=0.50)",
      totalTrades: 3,
      pnlDollars: -12.9686,
      runCount: 2,
    });
    expect(rows[0].pnlPct).toBeCloseTo(-0.129686, 9);

    expect(rows[1]).toMatchObject({
      profileLabel: "no_context_risk (room=0.08, rr=0.50)",
      totalTrades: 2,
      pnlDollars: 39.2179,
      runCount: 1,
    });
    expect(rows[1].pnlPct).toBeCloseTo(0.392179, 9);

    expect(rows[2]).toMatchObject({
      profileLabel: "relaxed_context_35 (room=0.02, rr=0.35)",
      totalTrades: 3,
      pnlDollars: -12.9686,
      runCount: 1,
    });
    expect(rows[2].pnlPct).toBeCloseTo(-0.129686, 9);
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
