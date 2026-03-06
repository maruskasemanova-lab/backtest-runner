import { describe, expect, it } from "vitest";

import {
  canonicalizeStrategyKey,
  clampContextRiskThresholdOverrides,
  resolveContextRiskStrategyFloor,
} from "./strategyAnalyzerContextRiskFloors";

describe("strategyAnalyzerContextRiskFloors", () => {
  it("canonicalizes strategy names to the engine keys", () => {
    expect(canonicalizeStrategyKey("MomentumFlow")).toBe("momentum_flow");
    expect(canonicalizeStrategyKey("mean reversion")).toBe("mean_reversion");
  });

  it("returns the same strategy floors as the strategy engine", () => {
    expect(resolveContextRiskStrategyFloor("momentum")).toEqual({
      strategyKey: "momentum",
      minRoomPct: 0.08,
      minEffectiveRr: 0.8,
    });
    expect(resolveContextRiskStrategyFloor("rotation")).toEqual({
      strategyKey: "rotation",
      minRoomPct: 0.02,
      minEffectiveRr: 0.3,
    });
  });

  it("clamps context-risk overrides below the active strategy floor", () => {
    expect(
      clampContextRiskThresholdOverrides(
        {
          context_risk_min_room_pct: 0.02,
          context_risk_min_effective_rr: 0.35,
          min_confirming_sources: 2,
        },
        "momentum_flow",
      ),
    ).toEqual({
      context_risk_min_room_pct: 0.08,
      context_risk_min_effective_rr: 0.8,
      min_confirming_sources: 2,
    });
  });
});
