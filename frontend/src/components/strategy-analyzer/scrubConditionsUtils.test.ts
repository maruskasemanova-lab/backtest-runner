import { describe, expect, it } from "vitest";

import {
  deriveScrubbedLiveAnalysis,
  resolveScrubbedDecisionMarker,
} from "./scrubConditionsUtils";

describe("deriveScrubbedLiveAnalysis", () => {
  it("preserves checkpoint and direct evidence diagnostics when scrub snapshots are merged", () => {
    const snapshot = deriveScrubbedLiveAnalysis({
      targetCheckpoint: {
        offset_sec: 5,
        level_context: { quality_score: 4.5 },
        tcbbo_confirmation: { passed: true },
      },
      targetBar: {
        timestamp: "2026-02-17T15:15:00Z",
        analysis: {
          layer_scores: { combined_score: 62.8 },
          context_risk: { room_pct: 0.31 },
          entry_quality_diagnostics: { grade: "A-" },
        },
      },
      progressedTradeBars: [],
      targetTime: null,
      progressedPoints: 0,
    } as any);

    expect(snapshot).toMatchObject({
      layer_scores: { combined_score: 62.8 },
      level_context: { quality_score: 4.5 },
      context_risk: { room_pct: 0.31 },
      entry_quality_diagnostics: { grade: "A-" },
      tcbbo_confirmation: { passed: true },
    });
  });

  it("prefers the matching execution-status marker with richer evidence on the scrubbed bar", () => {
    const marker = resolveScrubbedDecisionMarker(
      {
        targetTime: Date.parse("2026-02-17T20:23:00Z") / 1000,
        targetBar: { bar_index: 674 },
      } as any,
      [
        {
          marker_type: "signal_generated",
          bar_index: 674,
          timestamp: "2026-02-17T20:23:00Z",
          strategy: "MomentumFlow",
        },
        {
          marker_type: "execution_status",
          bar_index: 674,
          timestamp: "2026-02-17T20:23:12Z",
          title: "Signal Dropped (Context Risk)",
          details: {
            context_risk: {
              strategy_key: "MomentumFlow",
              room_pct: 0.029252,
            },
          },
        },
        {
          marker_type: "execution_status",
          bar_index: 673,
          timestamp: "2026-02-17T20:22:55Z",
          title: "Signal Dropped (Cooldown)",
          details: {
            signal_rejected: {
              gate: "cooldown",
            },
          },
        },
      ] as any,
    );

    expect(marker).toMatchObject({
      marker_type: "execution_status",
      title: "Signal Dropped (Context Risk)",
    });
    expect(marker?.details?.context_risk?.strategy_key).toBe("MomentumFlow");
  });
});
