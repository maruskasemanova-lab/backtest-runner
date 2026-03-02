import type {
  StrategyAnalyzerContextRiskPresetKey,
  StrategyAnalyzerStartRunPayload,
} from "./types";

type ContextRiskOverrides = Pick<
  StrategyAnalyzerStartRunPayload,
  | "context_aware_risk_enabled"
  | "context_risk_min_room_pct"
  | "context_risk_min_effective_rr"
>;

export type StrategyAnalyzerContextRiskPresetOption = {
  key: StrategyAnalyzerContextRiskPresetKey;
  label: string;
};

export const DEFAULT_STRATEGY_ANALYZER_CONTEXT_RISK_PRESET: StrategyAnalyzerContextRiskPresetKey =
  "current_defaults";

export const STRATEGY_ANALYZER_CONTEXT_RISK_PRESET_OPTIONS: readonly StrategyAnalyzerContextRiskPresetOption[] =
  [
    {
      key: "current_defaults",
      label: "Current defaults",
    },
    {
      key: "baseline",
      label: "baseline (room=0.08, rr=0.50)",
    },
    {
      key: "relaxed_context_35",
      label: "relaxed_context_35 (room=0.02, rr=0.35)",
    },
    {
      key: "no_context_risk",
      label: "no_context_risk",
    },
  ];

const PRESET_OVERRIDES: Record<StrategyAnalyzerContextRiskPresetKey, ContextRiskOverrides> = {
  current_defaults: {},
  baseline: {
    context_aware_risk_enabled: true,
    context_risk_min_room_pct: 0.08,
    context_risk_min_effective_rr: 0.5,
  },
  relaxed_context_35: {
    context_aware_risk_enabled: true,
    context_risk_min_room_pct: 0.02,
    context_risk_min_effective_rr: 0.35,
  },
  no_context_risk: {
    context_aware_risk_enabled: false,
  },
};

export const resolveStrategyAnalyzerContextRiskOverrides = (
  presetKey: StrategyAnalyzerContextRiskPresetKey,
): ContextRiskOverrides => PRESET_OVERRIDES[presetKey] ?? PRESET_OVERRIDES.current_defaults;

export const strategyAnalyzerContextRiskRunIdToken = (
  presetKey: StrategyAnalyzerContextRiskPresetKey,
): string => {
  if (presetKey === "current_defaults") return "default";
  return presetKey;
};
