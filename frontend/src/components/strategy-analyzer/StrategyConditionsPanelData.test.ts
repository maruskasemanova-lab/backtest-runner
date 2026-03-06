import { describe, expect, it } from "vitest";

import { extractStrategyConditionsPanelData } from "./StrategyConditionsPanelData";

describe("extractStrategyConditionsPanelData", () => {
  it("uses live level context and tcbbo confirmation in the evidence panel payload", () => {
    const data = extractStrategyConditionsPanelData(null, {
      timestamp: "2026-02-17T15:10:00Z",
      layer_scores: {
        combined_score: 64.2,
        threshold_used: 61.1,
      },
      level_context: {
        quality_score: 5.7,
      },
      tcbbo_confirmation: {
        passed: false,
      },
      intrabar_1s: {
        coverage_points: 18,
      },
    });

    expect(data).toMatchObject({
      source: "live",
      levelQuality: 5.7,
      tcbboPassed: false,
      intrabarCoverage: 18,
    });
  });

  it("prefers context-risk strategy_key over generic marker strategy placeholders", () => {
    const data = extractStrategyConditionsPanelData(
      {
        strategy: "pending_signal",
        details: {
          context_risk: {
            strategy_key: "MomentumFlow",
          },
        },
      },
      null,
    );

    expect(data?.selectedStrategy).toBe("MomentumFlow");
  });
});
