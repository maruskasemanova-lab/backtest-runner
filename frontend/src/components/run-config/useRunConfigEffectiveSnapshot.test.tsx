import { renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { useRunConfigEffectiveSnapshot } from "./useRunConfigEffectiveSnapshot";

const normalizeStrategySelectionMode = (value: unknown): string =>
  String(value || "").trim().toLowerCase() === "all_enabled" ? "all_enabled" : "adaptive_top_n";

const parseMaxActiveStrategies = (value: unknown, fallback = 3): number => {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return fallback;
  return Math.max(1, Math.trunc(parsed));
};

describe("useRunConfigEffectiveSnapshot strategy mode precedence", () => {
  it("prefers AOS ticker strategy mode over stale effective execution config", () => {
    const { result } = renderHook(() =>
      useRunConfigEffectiveSnapshot({
        config: {},
        effectiveExecutionConfig: {
          strategy_selection_mode: "all_enabled",
          max_active_strategies: 7,
        },
        aosTickerConfig: {
          strategy_selection_mode: "adaptive_top_n",
          max_active_strategies: 1,
        },
        selectedUnifiedProfileId: "",
        activeUnifiedProfileId: "",
        activeProfileSentinel: "__ACTIVE__",
        normalizeStrategySelectionMode,
        parseMaxActiveStrategies,
      }),
    );

    expect(result.current.activeStrategySelectionMode).toBe("adaptive_top_n");
    expect(result.current.activeMaxActiveStrategies).toBe(1);
  });

  it("honors explicit run-config strategy mode override", () => {
    const { result } = renderHook(() =>
      useRunConfigEffectiveSnapshot({
        config: {
          strategy_selection_mode: "all_enabled",
          max_active_strategies: 5,
        },
        effectiveExecutionConfig: {
          strategy_selection_mode: "adaptive_top_n",
          max_active_strategies: 2,
        },
        aosTickerConfig: {
          strategy_selection_mode: "adaptive_top_n",
          max_active_strategies: 1,
        },
        selectedUnifiedProfileId: "",
        activeUnifiedProfileId: "",
        activeProfileSentinel: "__ACTIVE__",
        normalizeStrategySelectionMode,
        parseMaxActiveStrategies,
      }),
    );

    expect(result.current.activeStrategySelectionMode).toBe("all_enabled");
    expect(result.current.activeMaxActiveStrategies).toBe(5);
  });

  it("defaults to all_enabled when no mode is provided", () => {
    const { result } = renderHook(() =>
      useRunConfigEffectiveSnapshot({
        config: {},
        effectiveExecutionConfig: null,
        aosTickerConfig: {},
        selectedUnifiedProfileId: "",
        activeUnifiedProfileId: "",
        activeProfileSentinel: "__ACTIVE__",
        normalizeStrategySelectionMode,
        parseMaxActiveStrategies,
      }),
    );

    expect(result.current.activeStrategySelectionMode).toBe("all_enabled");
    expect(result.current.activeMaxActiveStrategies).toBe(20);
  });
});
