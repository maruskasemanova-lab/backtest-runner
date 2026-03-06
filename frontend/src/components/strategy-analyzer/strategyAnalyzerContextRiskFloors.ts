import type { ThresholdOverrides } from "./useStrategyAnalyzerThresholdOverrides";

export type StrategyAnalyzerContextRiskStrategyFloor = {
  strategyKey: string;
  minRoomPct: number;
  minEffectiveRr: number;
};

const CONTEXT_RISK_STRATEGY_FLOORS: Record<
  string,
  Omit<StrategyAnalyzerContextRiskStrategyFloor, "strategyKey">
> = {
  momentum: { minRoomPct: 0.08, minEffectiveRr: 0.8 },
  momentum_flow: { minRoomPct: 0.08, minEffectiveRr: 0.8 },
  pullback: { minRoomPct: 0.05, minEffectiveRr: 0.6 },
  mean_reversion: { minRoomPct: 0.03, minEffectiveRr: 0.4 },
  rotation: { minRoomPct: 0.02, minEffectiveRr: 0.3 },
  vwap_magnet: { minRoomPct: 0.03, minEffectiveRr: 0.4 },
  volume_profile: { minRoomPct: 0.03, minEffectiveRr: 0.4 },
  evidence_scalp: { minRoomPct: 0.08, minEffectiveRr: 0.8 },
  level_fade: { minRoomPct: 0.05, minEffectiveRr: 0.6 },
};

const COMPACT_ALIASES = Object.fromEntries(
  Object.keys(CONTEXT_RISK_STRATEGY_FLOORS).map((key) => [
    key.replace(/_/g, ""),
    key,
  ]),
);

export const canonicalizeStrategyKey = (value: unknown): string => {
  const text = String(value ?? "").trim();
  if (!text) return "";

  const normalized = text.replace(/-/g, "_").replace(/\s+/g, "_");
  const step1 = normalized.replace(/(.)([A-Z][a-z]+)/g, "$1_$2");
  const step2 = step1.replace(/([a-z0-9])([A-Z])/g, "$1_$2");
  const snake = step2.replace(/_+/g, "_").replace(/^_+|_+$/g, "").toLowerCase();
  if (!snake) return "";

  const compact = snake.replace(/[^a-z0-9]/g, "");
  return COMPACT_ALIASES[compact] ?? snake;
};

export const resolveContextRiskStrategyFloor = (
  strategyKey: unknown,
): StrategyAnalyzerContextRiskStrategyFloor | null => {
  const canonicalKey = canonicalizeStrategyKey(strategyKey);
  if (!canonicalKey) return null;
  const floor = CONTEXT_RISK_STRATEGY_FLOORS[canonicalKey];
  if (!floor) return null;
  return {
    strategyKey: canonicalKey,
    ...floor,
  };
};

export const clampContextRiskThresholdOverrides = (
  overrides: ThresholdOverrides | null | undefined,
  strategyKey: unknown,
): ThresholdOverrides => {
  const floor = resolveContextRiskStrategyFloor(strategyKey);
  const next: ThresholdOverrides = { ...(overrides ?? {}) };
  if (!floor) return next;

  if (
    typeof next.context_risk_min_room_pct === "number" &&
    Number.isFinite(next.context_risk_min_room_pct)
  ) {
    next.context_risk_min_room_pct = Math.max(
      floor.minRoomPct,
      next.context_risk_min_room_pct,
    );
  }
  if (
    typeof next.context_risk_min_effective_rr === "number" &&
    Number.isFinite(next.context_risk_min_effective_rr)
  ) {
    next.context_risk_min_effective_rr = Math.max(
      floor.minEffectiveRr,
      next.context_risk_min_effective_rr,
    );
  }
  return next;
};
