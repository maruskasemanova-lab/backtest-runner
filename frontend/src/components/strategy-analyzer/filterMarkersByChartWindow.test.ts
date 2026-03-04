import { describe, expect, it } from "vitest";
import { filterMarkersByChartWindow } from "./filterMarkersByChartWindow";
import type { StrategyAnalyzerDecisionMarker } from "./types";

describe("filterMarkersByChartWindow", () => {
  it("returns only markers inside selected chart time window", () => {
    const markers: StrategyAnalyzerDecisionMarker[] = [
      { id: "m1", marker_type: "signal_generated", timestamp: "2026-01-29T15:13:00+00:00" },
      { id: "m2", marker_type: "entry_executed", timestamp: "2026-01-29T20:31:00+00:00" },
      { id: "m3", marker_type: "take_profit_hit", timestamp: "2026-01-30T10:00:00+00:00" },
    ];

    const from = Date.parse("2026-01-29T00:00:00+00:00") / 1000;
    const to = Date.parse("2026-01-29T23:59:59+00:00") / 1000;
    const filtered = filterMarkersByChartWindow(markers, { from, to });

    expect(filtered.map((marker) => marker.id)).toEqual(["m1", "m2"]);
  });

  it("returns original markers when chart window is missing", () => {
    const markers: StrategyAnalyzerDecisionMarker[] = [
      { id: "m1", marker_type: "signal_generated", timestamp: "2026-01-29T15:13:00+00:00" },
      { id: "m2", marker_type: "entry_executed", timestamp: "2026-01-29T20:31:00+00:00" },
    ];

    expect(filterMarkersByChartWindow(markers, null)).toEqual(markers);
  });
});
