import { describe, expect, it } from "vitest";

import type { StrategyConditionsPanelDataValue } from "./StrategyConditionsPanelData";
import { resolveActivationMinimumUpdates } from "./strategyAnalyzerActivationMinimums";

function buildBasePanelData(): StrategyConditionsPanelDataValue {
  return {
    source: "live",
    combinedScore: null,
    strategyScore: null,
    flowScore: null,
    threshold: null,
    thresholdReason: null,
    passed: null,
    confirmingSources: null,
    requiredConfirmingSources: null,
    alignedSourceKeys: [],
    l2HasCoverage: null,
    l2QualityOk: null,
    l2AggressionZ: null,
    l2BookPressureZ: null,
    signedAggression: null,
    microRegime: null,
    regime: null,
    todBoost: null,
    headwindBoost: null,
    top3: [],
    activeStrategies: [],
    selectedStrategy: null,
    sweepDetected: null,
    tcbboPassed: null,
    signalDirection: null,
    rejectionGate: null,
    rejectionReason: null,
    rejectionDetails: null,
    contextRisk: null,
    levelQuality: null,
    intrabarCoverage: null,
    intrabarMovePct: null,
    intrabarPushRatio: null,
    intrabarSpreadBps: null,
    intrabarHasCoverage: null,
    markerType: "live bar",
    barTimestamp: null,
    sourceContributions: null,
    sourceWeights: null,
    calibratedProbability: null,
    intrabarOnlyCheckpoint: false,
    liveAnalysisSource: null,
    barAction: null,
    barReason: null,
  };
}

describe("resolveActivationMinimumUpdates", () => {
  it("derives exact activation minimums from current rejection diagnostics", () => {
    const data: StrategyConditionsPanelDataValue = {
      ...buildBasePanelData(),
      combinedScore: 63.24,
      threshold: 60.11,
      confirmingSources: 3,
      selectedStrategy: "mean_reversion",
      barTimestamp: "2026-03-05T14:10:00Z",
      contextRisk: {
        room_pct: 0.27,
        effective_rr: 1.18,
      },
      rejectionDetails: {
        gate: "threshold",
        required_margin: 3,
        score_minus_model_threshold: 3,
        details: {
          trend_efficiency: 0.41,
        },
        risk_pct: 0.16,
        level_context: {
          stats: { near_confluence_score: 4 },
          market_activity: { rvol: 1.42 },
        },
      },
    };

    const updates = resolveActivationMinimumUpdates({ data });
    const mapped = Object.fromEntries(updates.map((entry) => [entry.key, entry.value]));

    expect(mapped).toMatchObject({
      base_threshold: 60.24,
      min_margin_over_threshold: 3,
      single_source_min_margin: 3,
      min_confirming_sources: 3,
      context_risk_min_room_pct: 0.27,
      context_risk_min_effective_rr: 1.18,
      intraday_levels_min_confluence_score: 4,
      intraday_levels_rvol_min_threshold: 1.42,
      intraday_levels_pullback_rvol_min_threshold: 1.42,
      pullback_min_price_trend_efficiency: 0.41,
      cost_aware_sweep_min_risk_pct: 0.16,
    });
  });

  it("skips updates that are already set to the exact same minimums", () => {
    const data: StrategyConditionsPanelDataValue = {
      ...buildBasePanelData(),
      combinedScore: 61.5,
      threshold: 58.5,
      confirmingSources: 2,
      selectedStrategy: "rotation",
      rejectionDetails: {
        required_margin: 3,
      },
    };

    const updates = resolveActivationMinimumUpdates({
      data,
      currentOverrides: {
        base_threshold: 58.5,
        min_margin_over_threshold: 3,
        single_source_min_margin: 3,
        min_confirming_sources: 2,
      },
    });

    expect(updates).toEqual([]);
  });

  it("falls back to score-threshold gap when explicit required margin is missing", () => {
    const data: StrategyConditionsPanelDataValue = {
      ...buildBasePanelData(),
      combinedScore: 59.7,
      threshold: 56.2,
      selectedStrategy: "momentum",
    };

    const updates = resolveActivationMinimumUpdates({ data });
    const marginUpdate = updates.find((entry) => entry.key === "min_margin_over_threshold");
    const baseUpdate = updates.find((entry) => entry.key === "base_threshold");

    expect(marginUpdate?.value).toBe(3.5);
    expect(baseUpdate?.value).toBe(56.2);
  });

  it("uses current model gap instead of stricter required margin to unlock activation", () => {
    const data: StrategyConditionsPanelDataValue = {
      ...buildBasePanelData(),
      combinedScore: 63,
      threshold: 61,
      selectedStrategy: "mean_reversion",
      rejectionDetails: {
        gate: "threshold",
        required_margin: 5,
        score_minus_model_threshold: 2,
      },
    };

    const updates = resolveActivationMinimumUpdates({ data });
    const mapped = Object.fromEntries(updates.map((entry) => [entry.key, entry.value]));

    expect(mapped.min_margin_over_threshold).toBe(2);
    expect(mapped.single_source_min_margin).toBe(2);
    expect(mapped.base_threshold).toBe(61);
  });

  it("extracts confirming sources from reasoning when numeric field is missing", () => {
    const data: StrategyConditionsPanelDataValue = {
      ...buildBasePanelData(),
      combinedScore: 55.5,
      threshold: 29.9,
      selectedStrategy: "momentum",
      rejectionDetails: {
        gate: "threshold",
        reasoning: "Evidence: [...] | Ensemble: score=55.5 thresh=29.9 confirming=1/5 | SKIP",
      },
    };

    const updates = resolveActivationMinimumUpdates({ data });
    const mapped = Object.fromEntries(updates.map((entry) => [entry.key, entry.value]));

    expect(mapped.min_confirming_sources).toBe(1);
  });
});
