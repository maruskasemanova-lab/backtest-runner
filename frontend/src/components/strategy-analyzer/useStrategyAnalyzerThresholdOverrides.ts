import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  clampContextRiskThresholdOverrides,
  resolveContextRiskStrategyFloor,
} from "./strategyAnalyzerContextRiskFloors";

export type ThresholdOverrides = {
  base_threshold?: number | null;
  strategy_only_threshold?: number | null;
  strategy_weight?: number | null;
  min_confirming_sources?: number | null;
  base_risk_pct?: number | null;
  min_margin_over_threshold?: number | null;
  single_source_min_margin?: number | null;
  // Feature flags
  use_evidence_engine?: boolean | null;
  use_adaptive_regime?: boolean | null;
  use_calibration?: boolean | null;
  use_quality_sizing?: boolean | null;
  use_cross_asset?: boolean | null;
  use_edge_monitor?: boolean | null;
  // Session-level context risk
  context_aware_risk_enabled?: boolean | null;
  context_risk_min_room_pct?: number | null;
  context_risk_min_effective_rr?: number | null;
  // Pullback quality gate
  pullback_morning_window_enabled?: boolean | null;
  pullback_block_choppy_macro?: boolean | null;
  pullback_require_poc_on_trade_side?: boolean | null;
  pullback_min_price_trend_efficiency?: number | null;
  // Entry quality gate (intraday levels)
  intraday_levels_entry_quality_enabled?: boolean | null;
  intraday_levels_min_confluence_score?: number | null;
  intraday_levels_rvol_min_threshold?: number | null;
  intraday_levels_pullback_rvol_min_threshold?: number | null;
  cost_aware_sweep_min_risk_pct?: number | null;
  // Gate bypass toggles
  pullback_quality_gate_enabled?: boolean | null;
  momentum_diversification_gate_enabled?: boolean | null;
  bypass_all_entry_gates?: boolean | null;
  // Fixed threshold mode — disables all dynamic threshold adjustments
  use_fixed_threshold?: boolean | null;
};

export type ThresholdOverrideKey = keyof ThresholdOverrides;

export const SUPPORTED_THRESHOLD_OVERRIDE_KEYS = [
  "base_threshold",
  "strategy_only_threshold",
  "strategy_weight",
  "min_confirming_sources",
  "base_risk_pct",
  "min_margin_over_threshold",
  "single_source_min_margin",
  "use_evidence_engine",
  "use_adaptive_regime",
  "use_calibration",
  "use_quality_sizing",
  "use_cross_asset",
  "use_edge_monitor",
  "context_aware_risk_enabled",
  "context_risk_min_room_pct",
  "context_risk_min_effective_rr",
  "pullback_morning_window_enabled",
  "pullback_block_choppy_macro",
  "pullback_require_poc_on_trade_side",
  "pullback_min_price_trend_efficiency",
  "intraday_levels_entry_quality_enabled",
  "intraday_levels_min_confluence_score",
  "intraday_levels_rvol_min_threshold",
  "intraday_levels_pullback_rvol_min_threshold",
  "cost_aware_sweep_min_risk_pct",
  "pullback_quality_gate_enabled",
  "momentum_diversification_gate_enabled",
  "bypass_all_entry_gates",
  "use_fixed_threshold",
] as const satisfies readonly ThresholdOverrideKey[];

export const BOOLEAN_THRESHOLD_OVERRIDE_KEYS = [
  "use_evidence_engine",
  "use_adaptive_regime",
  "use_calibration",
  "use_quality_sizing",
  "use_cross_asset",
  "use_edge_monitor",
  "context_aware_risk_enabled",
  "pullback_morning_window_enabled",
  "pullback_block_choppy_macro",
  "pullback_require_poc_on_trade_side",
  "intraday_levels_entry_quality_enabled",
  "pullback_quality_gate_enabled",
  "momentum_diversification_gate_enabled",
  "bypass_all_entry_gates",
  "use_fixed_threshold",
 ] as const satisfies readonly ThresholdOverrideKey[];

const _BOOLEAN_KEYS = new Set<string>(BOOLEAN_THRESHOLD_OVERRIDE_KEYS);

type Args = {
  isAnalyzerAttachedRun: boolean;
  isPlayingRun: boolean;
  analyzerRunTerminal: boolean;
  activeRunApiBase: string | null;
  contextRiskStrategyKey?: string | null;
};

export function useStrategyAnalyzerThresholdOverrides({
  isAnalyzerAttachedRun,
  isPlayingRun,
  analyzerRunTerminal,
  activeRunApiBase,
  contextRiskStrategyKey = null,
}: Args) {
  const [overrides, setOverrides] = useState<ThresholdOverrides>({});
  const syncTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const syncBackoffUntilRef = useRef<number>(0);

  const isInteractive =
    isAnalyzerAttachedRun && !isPlayingRun && !analyzerRunTerminal;

  // Reset when run changes
  useEffect(() => {
    setOverrides({});
    syncBackoffUntilRef.current = 0;
  }, [activeRunApiBase]);

  const hasPendingOverrides = useMemo(
    () => Object.values(overrides).some((v) => v != null),
    [overrides],
  );

  const effectiveOverrides = useMemo(
    () =>
      clampContextRiskThresholdOverrides(overrides, contextRiskStrategyKey),
    [overrides, contextRiskStrategyKey],
  );

  const contextRiskStrategyFloor = useMemo(
    () => resolveContextRiskStrategyFloor(contextRiskStrategyKey),
    [contextRiskStrategyKey],
  );

  const buildPayload = useCallback((src: ThresholdOverrides) => {
    const effectiveSrc = clampContextRiskThresholdOverrides(
      src,
      contextRiskStrategyKey,
    );
    const payload: Record<string, number | boolean> = {};
    for (const [key, val] of Object.entries(effectiveSrc)) {
      if (val == null) continue;
      if (_BOOLEAN_KEYS.has(key)) {
        payload[key] = Boolean(val);
      } else if (key === "strategy_weight") {
        payload[key] = Math.max(0, Math.min(1, (val as number) / 100));
      } else if (key === "min_confirming_sources") {
        payload[key] = Math.round(Math.max(0, Math.min(5, val as number)));
      } else if (key === "base_risk_pct") {
        payload[key] = Math.max(0.0001, Math.min(0.05, (val as number) / 10000));
      } else if (key === "min_margin_over_threshold" || key === "single_source_min_margin") {
        payload[key] = Math.max(0, Math.min(30, val as number));
      } else if (key === "context_risk_min_room_pct" || key === "context_risk_min_effective_rr") {
        payload[key] = Math.max(0, val as number);
      } else if (key === "intraday_levels_min_confluence_score") {
        payload[key] = Math.round(Math.max(0, Math.min(10, val as number)));
      } else if (key === "intraday_levels_rvol_min_threshold" || key === "intraday_levels_pullback_rvol_min_threshold" || key === "cost_aware_sweep_min_risk_pct") {
        payload[key] = Math.max(0, val as number);
      } else {
        payload[key] = val as number;
      }
    }
    return payload;
  }, [contextRiskStrategyKey]);

  const doSync = useCallback(async (src: ThresholdOverrides) => {
    if (!activeRunApiBase) return;
    if (syncBackoffUntilRef.current > Date.now()) return;
    const payload = buildPayload(src);
    if (Object.keys(payload).length === 0) return;
    try {
      const endpoint = `${activeRunApiBase}/orchestrator-config`;
      const isLocalProxyHost =
        typeof window !== "undefined" &&
        (window.location.hostname === "localhost" ||
          window.location.hostname === "127.0.0.1");
      // In local dev prefer same-origin /api through Vite proxy to avoid
      // cross-origin CORS failures when API host/headers drift.
      const target = (() => {
        if (!isLocalProxyHost) return endpoint;
        try {
          const parsed = new URL(endpoint, window.location.origin);
          return new URL(
            `${parsed.pathname}${parsed.search}${parsed.hash}`,
            window.location.origin,
          );
        } catch (_error) {
          return endpoint;
        }
      })();
      const response = await fetch(target, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        const backup = response.clone();
        let detail = "";
        try {
          const parsed = await response.json();
          detail = String(parsed?.detail || parsed?.error || parsed?.message || "").trim();
        } catch (_error) {
          try {
            detail = String(await backup.text() || "").trim();
          } catch (_ignored) {
            detail = "";
          }
        }
        const suffix = detail ? `: ${detail}` : "";
        throw new Error(`HTTP ${response.status}${suffix}`);
      }
      syncBackoffUntilRef.current = 0;
    } catch (e) {
      syncBackoffUntilRef.current = Date.now() + 5000;
      console.error("Threshold sync failed (retrying in 5s):", e);
    }
  }, [activeRunApiBase, buildPayload]);

  // Auto-sync overrides with 300ms debounce when they change
  useEffect(() => {
    if (!hasPendingOverrides || !activeRunApiBase) return;
    if (syncTimerRef.current) clearTimeout(syncTimerRef.current);
    syncTimerRef.current = setTimeout(() => {
      void doSync(overrides);
    }, 300);
    return () => {
      if (syncTimerRef.current) clearTimeout(syncTimerRef.current);
    };
  }, [overrides, hasPendingOverrides, activeRunApiBase, doSync]);

  // Explicit sync for play/step (fires immediately, no debounce)
  const syncOverrides = useCallback(async () => {
    if (!activeRunApiBase || !hasPendingOverrides) return;
    if (syncTimerRef.current) clearTimeout(syncTimerRef.current);
    await doSync(overrides);
  }, [activeRunApiBase, overrides, hasPendingOverrides, doSync]);

  const updateOverride = useCallback(
    (key: ThresholdOverrideKey, value: number | boolean | null) => {
      setOverrides((prev) => ({ ...prev, [key]: value }));
    },
    [],
  );

  const replaceOverrides = useCallback((next: ThresholdOverrides) => {
    setOverrides(next);
  }, []);

  const resetOverrides = useCallback(() => {
    setOverrides({});
  }, []);

  return {
    thresholdOverrides: overrides,
    effectiveThresholdOverrides: effectiveOverrides,
    contextRiskStrategyFloor,
    isThresholdInteractive: isInteractive,
    hasPendingOverrides,
    updateThresholdOverride: updateOverride,
    replaceThresholdOverrides: replaceOverrides,
    resetThresholdOverrides: resetOverrides,
    syncThresholdOverrides: syncOverrides,
    buildThresholdPayload: buildPayload,
  };
}
