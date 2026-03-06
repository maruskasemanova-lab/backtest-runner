import { renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { extractStrategyConditionsPanelData } from "./StrategyConditionsPanelData";
import { useStrategyAnalyzerConditions } from "./useStrategyAnalyzerConditions";

describe("useStrategyAnalyzerConditions", () => {
  it("uses the matching scrub execution-status marker while preserving the scrubbed live snapshot", () => {
    const rangeScrubMeta = {
      targetTime: Date.parse("2026-02-17T20:23:00Z") / 1000,
      targetLocal: "2026-02-17T20:23",
      progressedPoints: 678,
      progressedMaxOffset: 678,
      clampedOffset: 678,
      targetCheckpoint: null,
      targetBar: {
        bar_index: 674,
        timestamp: "2026-02-17T20:23:00Z",
        analysis: {
          signal_rejected: {
            gate: "mu_choppy_filter",
          },
        },
      },
    } as any;

    const scrubMarkers = [
      {
        marker_type: "execution_status",
        bar_index: 674,
        timestamp: "2026-02-17T20:23:12Z",
        title: "Signal Dropped (Context Risk)",
        strategy: "pending_signal",
        details: {
          context_risk: {
            strategy_key: "MomentumFlow",
            room_pct: 0.029252,
            min_room_pct: 0.08,
          },
        },
      },
    ] as any;

    const { result } = renderHook(() =>
      useStrategyAnalyzerConditions({
        rangeScrubMeta,
        scrubMarkers,
        selectedMarker: null,
        latestBarAnalysis: null,
      }),
    );

    expect(result.current.scrubbedConditionsActive).toBe(true);
    expect(result.current.effectiveConditionsMarker?.title).toBe(
      "Signal Dropped (Context Risk)",
    );
    expect(result.current.stableConditionsLiveAnalysis?.signal_rejected?.gate).toBe(
      "mu_choppy_filter",
    );

    const panelData = extractStrategyConditionsPanelData(
      result.current.effectiveConditionsMarker,
      result.current.stableConditionsLiveAnalysis,
    );
    expect(panelData?.selectedStrategy).toBe("MomentumFlow");
    expect(panelData?.contextRisk?.min_room_pct).toBe(0.08);
  });
});
