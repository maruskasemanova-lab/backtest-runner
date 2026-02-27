import { describe, expect, it } from "vitest";
import {
  buildMomentumConfigFromDraft,
  mergeMomentumIntoTickerConfig,
  normalizeMomentumDraft,
  parseTickerConfigText,
} from "./aosOptimizationsMomentum";

describe("aosOptimizationsMomentum helpers", () => {
  it("normalizes momentum draft and sleeve fields", () => {
    const normalized = normalizeMomentumDraft({
      apply_to_strategies: "momentum_flow,momentum_flow,pullback",
      allowed_micro_regimes: "trending_up, breakout",
      blocked_micro_regimes: "choppy, absorption",
      sleeves: [
        {
          sleeve_id: "Impulse Alpha",
          min_flow_score: 101,
          fail_fast_max_bars: 0,
        },
      ],
    });

    expect(normalized.apply_to_strategies).toBe("momentum_flow,pullback");
    expect(normalized.allowed_micro_regimes).toBe("TRENDING_UP,BREAKOUT");
    expect(normalized.blocked_micro_regimes).toBe("CHOPPY,ABSORPTION");
    expect(normalized.sleeves[0].sleeve_id).toBe("impulse_alpha");
    expect(normalized.sleeves[0].min_flow_score).toBe(100);
    expect(normalized.sleeves[0].fail_fast_max_bars).toBe(1);
  });

  it("builds momentum payload from draft including optional lists", () => {
    const payload = buildMomentumConfigFromDraft({
      enabled: true,
      apply_to_strategies: "momentum_flow,pullback",
      allowed_micro_regimes: "TRENDING_UP",
      blocked_micro_regimes: "CHOPPY",
      sleeves: [
        {
          sleeve_id: "alpha",
          apply_to_strategies: "momentum_flow",
          min_flow_score: 61,
        },
      ],
    });

    expect(payload.apply_to_strategies).toEqual(["momentum_flow", "pullback"]);
    expect(payload.allowed_micro_regimes).toEqual(["TRENDING_UP"]);
    expect(payload.blocked_micro_regimes).toEqual(["CHOPPY"]);
    expect(Array.isArray(payload.sleeves)).toBe(true);
    expect((payload.sleeves as Array<Record<string, unknown>>)[0].sleeve_id).toBe("alpha");
  });

  it("merges momentum payload into adaptive ticker config", () => {
    const merged = mergeMomentumIntoTickerConfig(
      {
        adaptive: { flow_bias_enabled: true },
        positioning: { trailing_enabled_in_choppy: true },
      },
      {
        enabled: true,
        min_flow_score: 66,
      },
    );

    expect(merged.positioning).toEqual({ trailing_enabled_in_choppy: true });
    expect((merged.adaptive as Record<string, unknown>).flow_bias_enabled).toBe(true);
    expect(
      ((merged.adaptive as Record<string, unknown>).momentum_diversification as Record<string, unknown>).min_flow_score,
    ).toBe(66);
  });

  it("parses valid ticker config JSON and rejects invalid values", () => {
    expect(parseTickerConfigText('{"adaptive": {"x": 1}}')).toEqual({ adaptive: { x: 1 } });
    expect(() => parseTickerConfigText("[1,2,3]")).toThrow("Ticker config JSON must be an object.");
    expect(() => parseTickerConfigText("{ nope")).toThrow("Invalid JSON");
  });
});
