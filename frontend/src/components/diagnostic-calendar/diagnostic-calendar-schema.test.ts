import { describe, expect, it } from "vitest";
import { parseDiagnosticCalendarReport } from "./diagnostic-calendar-schema";

describe("diagnostic-calendar schema", () => {
  it("parses valid diagnostic report payloads", () => {
    expect(parseDiagnosticCalendarReport({
      day_results: [
        {
          date: "2025-01-02",
          pnl_dollars: 25,
          processed_bars: null,
          runs: [
            {
              run_processed_bars: null,
              run_id: "run-1",
              run_total_bars: null,
              total_trades: 2,
            },
          ],
          success: true,
          total_trades: 2,
        },
      ],
      filter_options: {
        run_ids: [{ run_id: "run-1", latest_saved_at: "2025-01-02T15:00:00Z" }],
        unified_profiles: [{ profile_id: "u-1", profile_name: "Unified 1" }],
      },
      source_mode: "supabase_run_reports",
      split: {
        end: "2025-01-31",
        start: "2025-01-01",
      },
    })).toMatchObject({
      day_results: [{ date: "2025-01-02" }],
      source_mode: "supabase_run_reports",
    });
  });

  it("accepts null diagnostic profile metadata from history payloads", () => {
    expect(parseDiagnosticCalendarReport({
      day_results: [
        {
          adaptive_profile_id: null,
          adaptive_profile_name: null,
          aos_applied: {
            adaptive_profile: {
              active_profile_id: null,
              profile_id: null,
              profile_name: null,
            },
            strategy_combo: {
              active_profile_id: null,
              profile_id: null,
              profile_name: null,
            },
            unified_profile: {
              active_profile_id: null,
              profile_id: null,
              profile_name: null,
            },
          },
          date: "2026-02-03",
          strategy_combo_profile_id: null,
          strategy_combo_profile_name: null,
          unified_profile_id: null,
          unified_profile_name: null,
          runs: [
            {
              adaptive_profile_id: null,
              adaptive_profile_name: null,
              profile_match_mode: null,
              run_id: "run-1",
              strategy_combo_profile_id: null,
              strategy_combo_profile_name: null,
              unified_profile_id: null,
              unified_profile_name: null,
            },
          ],
        },
      ],
    })).toMatchObject({
      day_results: [
        {
          adaptive_profile_id: null,
          date: "2026-02-03",
          strategy_combo_profile_id: null,
          unified_profile_id: null,
          runs: [
            {
              adaptive_profile_id: null,
              profile_match_mode: null,
              run_id: "run-1",
              strategy_combo_profile_id: null,
              unified_profile_id: null,
            },
          ],
        },
      ],
    });
  });

  it("rejects invalid day result shapes with explicit path info", () => {
    expect(() => parseDiagnosticCalendarReport({
      day_results: [
        {
          pnl_dollars: 25,
        },
      ],
    })).toThrow(/day_results\.0\.date/);
  });
});
