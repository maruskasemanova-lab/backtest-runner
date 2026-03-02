import { describe, expect, it } from "vitest";
import {
  DEFAULT_STRATEGY_ANALYZER_CONTEXT_RISK_PRESET,
  STRATEGY_ANALYZER_CONTEXT_RISK_PRESET_OPTIONS,
  resolveStrategyAnalyzerContextRiskOverrides,
  strategyAnalyzerContextRiskRunIdToken,
} from "./strategyAnalyzerContextRiskPresets";

describe("strategyAnalyzerContextRiskPresets", () => {
  it("keeps current defaults preset as safe default", () => {
    expect(DEFAULT_STRATEGY_ANALYZER_CONTEXT_RISK_PRESET).toBe("current_defaults");
    expect(resolveStrategyAnalyzerContextRiskOverrides("current_defaults")).toEqual({});
    expect(strategyAnalyzerContextRiskRunIdToken("current_defaults")).toBe("default");
  });

  it("exposes baseline and relaxed context presets with expected payload overrides", () => {
    expect(resolveStrategyAnalyzerContextRiskOverrides("baseline")).toEqual({
      context_aware_risk_enabled: true,
      context_risk_min_room_pct: 0.08,
      context_risk_min_effective_rr: 0.5,
    });
    expect(resolveStrategyAnalyzerContextRiskOverrides("relaxed_context_35")).toEqual({
      context_aware_risk_enabled: true,
      context_risk_min_room_pct: 0.02,
      context_risk_min_effective_rr: 0.35,
    });
    expect(resolveStrategyAnalyzerContextRiskOverrides("no_context_risk")).toEqual({
      context_aware_risk_enabled: false,
    });
  });

  it("contains visible baseline option label", () => {
    const labels = STRATEGY_ANALYZER_CONTEXT_RISK_PRESET_OPTIONS.map((item) => item.label);
    expect(labels).toContain("baseline (room=0.08, rr=0.50)");
  });
});
