import { useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  BarChart2,
  Target,
  Crosshair,
  Zap,
  AlertTriangle,
} from "lucide-react";
import { extractStrategyConditionsPanelData } from "./StrategyConditionsPanelData";
import { StrategyConditionsPanelRejectionDetail as RejectionDetail } from "./StrategyConditionsPanelRejectionDetail";
import {
  InteractiveMiniBar,
  MiniBar,
  SectionLabel,
  cx,
  safeNum,
} from "./StrategyConditionsPanelShared";
import type {
  ThresholdOverrides,
  ThresholdOverrideKey,
} from "./useStrategyAnalyzerThresholdOverrides";
import { resolveContextRiskStrategyFloor } from "./strategyAnalyzerContextRiskFloors";
import { resolveActivationMinimumUpdates } from "./strategyAnalyzerActivationMinimums";

/* ── gate badge (compact) ────────────────────────────────────────── */

const FEATURE_TOGGLE_OPTIONS = [
  ["use_evidence_engine", "Evidence Engine"],
  ["use_adaptive_regime", "Adaptive Regime"],
  ["use_calibration", "Calibration"],
  ["use_quality_sizing", "Quality Sizing"],
  ["use_cross_asset", "Cross-Asset"],
  ["use_edge_monitor", "Edge Monitor"],
  ["context_aware_risk_enabled", "Context Risk"],
  ["intraday_levels_entry_quality_enabled", "Entry Quality"],
  ["pullback_quality_gate_enabled", "Pullback Quality"],
  ["momentum_diversification_gate_enabled", "Momentum Div"],
] as const;

const PULLBACK_TOGGLE_OPTIONS = [
  ["pullback_morning_window_enabled", "Morning Window"],
  ["pullback_block_choppy_macro", "Block Choppy"],
  ["pullback_require_poc_on_trade_side", "Require POC Side"],
] as const;

function GateBadge({
  label,
  passed,
}: {
  label: string;
  passed: boolean | null;
}) {
  if (passed == null) return null;
  return (
    <span className={cx("sa-pill", passed ? "is-success" : "is-danger")}>
      <span className="sa-pill__icon">{passed ? "\u2713" : "\u2717"}</span>
      {label}
    </span>
  );
}

function ModeToggleButton({
  active,
  tone,
  label,
  activeLabel,
  icon,
  activeIcon,
  onClick,
  title,
  spaced,
}: {
  active: boolean;
  tone: "success" | "warning" | "danger";
  label: string;
  activeLabel: string;
  icon: string;
  activeIcon: string;
  onClick: () => void;
  title?: string;
  spaced?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      className={cx(
        "sa-mode-button",
        active && `is-${tone}`,
        spaced && "is-spaced",
      )}
    >
      <span className="sa-pill__icon is-large">
        {active ? activeIcon : icon}
      </span>
      {active ? activeLabel : label}
    </button>
  );
}

function FeatureToggleButton({
  label,
  isOn,
  isOverridden,
  onClick,
}: {
  label: string;
  isOn: boolean;
  isOverridden: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cx("sa-chip-button", isOn ? "is-success" : "is-danger")}
    >
      <span className="sa-pill__icon">{isOn ? "✓" : "✗"}</span>
      {label}
      {isOverridden && <span className="sa-chip-button__meta">mod</span>}
    </button>
  );
}

function RequirementBar({
  label,
  current,
  minimum,
  failed,
  currentLabel,
  minimumLabel,
}: {
  label: string;
  current: number;
  minimum: number;
  failed: boolean;
  currentLabel: string;
  minimumLabel: string;
}) {
  const widthPct = Math.min(100, (current / minimum) * 100);
  return (
    <div className="sa-metric">
      <div className="sa-metric__header">
        <span className="sa-metric__label">{label}</span>
        <span
          className={cx(
            "sa-metric__value",
            failed ? "is-danger" : "is-success",
          )}
        >
          {currentLabel} / {minimumLabel} min
        </span>
      </div>
      <div className="sa-track">
        <div
          className={cx("sa-track__fill", failed ? "is-danger" : "is-success")}
          style={{ width: `${widthPct}%` }}
        />
        <div className="sa-track__threshold is-end" />
      </div>
    </div>
  );
}

function thresholdHeadlineFromDetails(d: any): string {
  const subtype =
    typeof d?.rejection_subtype === "string" ? d.rejection_subtype : "";
  const subtypeLabels: Record<string, string> = {
    score_below_trade_threshold: "Score príliš nízky na vstup",
    margin_insufficient: "Nedostatočný margin nad model threshold",
    ensemble_execute_false: "Model vstup zamietol (execute=false)",
    headwind_or_trade_threshold: "Trade threshold / headwind blokuje vstup",
  };
  if (subtypeLabels[subtype]) return subtypeLabels[subtype];

  const score = safeNum(d?.combined_score) ?? safeNum(d?.combined_norm_0_100);
  const threshold =
    safeNum(d?.threshold_used) ?? safeNum(d?.trade_gate_threshold);
  if (score != null && threshold != null && score >= threshold) {
    return "Vstup zamietnutý mimo čistého score prahu";
  }
  return "Score príliš nízky na vstup";
}

/* ── rejection detail renderer ────────────────────────────────────── */

/* ── main panel ───────────────────────────────────────────────────── */

interface StrategyConditionsPanelProps {
  marker: any;
  liveAnalysis?: any;
  isThresholdInteractive?: boolean;
  thresholdOverrides?: ThresholdOverrides;
  onThresholdOverrideChange?: (
    key: ThresholdOverrideKey,
    value: number | boolean,
  ) => void;
  hasPendingOverrides?: boolean;
}

export default function StrategyConditionsPanel({
  marker,
  liveAnalysis,
  isThresholdInteractive,
  thresholdOverrides,
  onThresholdOverrideChange,
  hasPendingOverrides,
}: StrategyConditionsPanelProps) {
  const [autoSetActivationMinimums, setAutoSetActivationMinimums] =
    useState(false);
  const lastAutoApplyKeyRef = useRef<string>("");
  const rawData = useMemo(
    () => extractStrategyConditionsPanelData(marker, liveAnalysis),
    [marker, liveAnalysis],
  );

  // Local re-evaluation: override gate results based on current threshold overrides
  // so the UI updates instantly when user adjusts sliders (without waiting for Play/Step)
  const data = useMemo(() => {
    if (!rawData) return null;
    if (!thresholdOverrides || !isThresholdInteractive) return rawData;

    const patched = { ...rawData };

    // ── Master bypass: clear ALL rejections when bypass_all_entry_gates is on ──
    if (thresholdOverrides.bypass_all_entry_gates === true) {
      if (patched.rejectionGate && patched.rejectionGate !== "threshold") {
        // Clear non-threshold rejections — scoring threshold is handled below
        patched.passed = true;
        patched.rejectionGate = null;
        patched.rejectionReason = null;
        patched.rejectionDetails = null;
      }
    }

    // ── Locally recalculate combined score when strategy_weight changes ──
    if (
      thresholdOverrides.strategy_weight != null &&
      patched.sourceContributions &&
      patched.sourceWeights
    ) {
      const contributions = patched.sourceContributions as Record<
        string,
        number
      >;
      const origWeights = patched.sourceWeights as Record<string, number>;
      // strategy_weight override is stored as 0-100 in the UI, converted to 0-1 for the payload
      const newStrategyWeight = thresholdOverrides.strategy_weight / 100;

      // Recompute weighted sum with the new strategy weight
      let totalWeightedScore = 0;
      let totalWeight = 0;
      for (const [key, contribution] of Object.entries(contributions)) {
        if (contribution == null || contribution <= 0) continue;
        const origWeight = origWeights[key] ?? 0;
        if (origWeight <= 0) continue;
        // The raw score for this source = contribution / origWeight
        const rawScore = contribution / origWeight;
        // Apply new weight for strategy sources, keep original for others
        const isStrategy = key.startsWith("strategy:");
        const effectiveWeight = isStrategy ? newStrategyWeight : origWeight;
        totalWeightedScore += rawScore * effectiveWeight;
        totalWeight += effectiveWeight;
      }
      if (totalWeight > 0) {
        patched.combinedScore =
          Math.round((totalWeightedScore / totalWeight) * 100) / 100;
      }
    }

    // ── Master bypass: clear ALL rejections when bypass_all_entry_gates is on ──
    if (thresholdOverrides.bypass_all_entry_gates === true) {
      patched.passed = true;
      patched.rejectionGate = null;
      patched.rejectionReason = null;
      patched.rejectionDetails = null;
    }

    // ── Re-evaluate threshold gate ──
    // When use_fixed_threshold is on, use the base_threshold override as the
    // effective threshold (ignoring dynamic adjustments like ToD/transition).
    const useFixed = thresholdOverrides.use_fixed_threshold === true;
    const effectiveThreshold = useFixed
      ? (thresholdOverrides.base_threshold ?? patched.threshold)
      : (thresholdOverrides.base_threshold ?? patched.threshold);
    // When fixed threshold is on, also update the displayed threshold
    if (useFixed && thresholdOverrides.base_threshold != null) {
      patched.threshold = thresholdOverrides.base_threshold;
    }
    if (
      effectiveThreshold != null &&
      patched.combinedScore != null &&
      !thresholdOverrides.bypass_all_entry_gates
    ) {
      const scorePasses = patched.combinedScore >= effectiveThreshold;

      if (scorePasses && patched.rejectionGate === "threshold") {
        patched.passed = true;
        patched.rejectionGate = null;
        patched.rejectionReason = null;
        patched.rejectionDetails = null;
      } else if (!scorePasses && patched.passed !== false) {
        patched.passed = false;
        if (!patched.rejectionGate) {
          patched.rejectionGate = "threshold";
        }
      }
    }

    // Re-evaluate: confirming_sources vs. overridden min_confirming_sources
    if (
      thresholdOverrides.min_confirming_sources != null &&
      patched.confirmingSources != null
    ) {
      const required = thresholdOverrides.min_confirming_sources;
      patched.requiredConfirmingSources = required;
      const sourcesPasses = patched.confirmingSources >= required;

      if (sourcesPasses && patched.rejectionGate === "confirming_sources") {
        // Was rejected for confirming_sources but now passes with lowered threshold
        patched.passed = true;
        patched.rejectionGate = null;
        patched.rejectionReason = null;
        patched.rejectionDetails = null;
      } else if (
        !sourcesPasses &&
        patched.rejectionGate !== "confirming_sources"
      ) {
        // Doesn't pass with new higher requirement
        patched.passed = false;
        patched.rejectionGate = "confirming_sources";
      }
    }

    // Re-evaluate context risk: room_pct and effective_rr vs overridden minimums
    if (patched.contextRisk && typeof patched.contextRisk === "object") {
      const cr = { ...patched.contextRisk };
      const strategyFloor = resolveContextRiskStrategyFloor(patched.selectedStrategy);
      const overriddenMinRoom =
        typeof thresholdOverrides.context_risk_min_room_pct === "number" &&
        Number.isFinite(thresholdOverrides.context_risk_min_room_pct)
          ? Math.max(
              strategyFloor?.minRoomPct ?? 0,
              thresholdOverrides.context_risk_min_room_pct,
            )
          : null;
      const overriddenMinRr =
        typeof thresholdOverrides.context_risk_min_effective_rr === "number" &&
        Number.isFinite(thresholdOverrides.context_risk_min_effective_rr)
          ? Math.max(
              strategyFloor?.minEffectiveRr ?? 0,
              thresholdOverrides.context_risk_min_effective_rr,
            )
          : null;
      const roomPct = safeNum(cr.room_pct);
      const effectiveRr = safeNum(cr.effective_rr);

      let roomOk = true;
      let rrOk = true;

      if (overriddenMinRoom != null && roomPct != null) {
        roomOk = roomPct >= overriddenMinRoom;
        cr.configured_min_room_pct = overriddenMinRoom;
      }
      if (overriddenMinRr != null && effectiveRr != null) {
        rrOk = effectiveRr >= overriddenMinRr;
        cr.configured_min_effective_rr = overriddenMinRr;
      }

      // If both pass now with overrides, clear context_risk skip
      if (roomOk && rrOk && cr.skip === true) {
        cr.skip = false;
      }
      // If one fails and it wasn't skipping before, set skip
      if ((!roomOk || !rrOk) && cr.skip !== true) {
        cr.skip = true;
        cr.skip_reason = !roomOk ? "min_room_pct" : "min_effective_rr";
      }

      patched.contextRisk = cr;
    }

    // Re-evaluate pullback_quality gate
    if (
      patched.rejectionGate === "pullback_quality" &&
      patched.rejectionDetails
    ) {
      const details = patched.rejectionDetails.details || {};
      const reason =
        patched.rejectionDetails.reason || patched.rejectionReason || "";

      let cleared = false;
      // Morning window disabled → clear morning window rejection
      if (
        thresholdOverrides.pullback_morning_window_enabled === false &&
        reason.includes("morning_window")
      ) {
        cleared = true;
      }
      // Choppy macro disabled → clear choppy rejection
      if (
        thresholdOverrides.pullback_block_choppy_macro === false &&
        reason.includes("choppy_macro")
      ) {
        cleared = true;
      }
      // POC requirement disabled → clear POC rejection
      if (
        thresholdOverrides.pullback_require_poc_on_trade_side === false &&
        reason.includes("poc_on_trade_side")
      ) {
        cleared = true;
      }
      // Trend efficiency lowered → clear trend efficiency rejection
      if (
        thresholdOverrides.pullback_min_price_trend_efficiency != null &&
        reason.includes("trend_efficiency")
      ) {
        const actual = safeNum(details.trend_efficiency);
        if (
          actual != null &&
          actual >= thresholdOverrides.pullback_min_price_trend_efficiency
        ) {
          cleared = true;
        }
      }
      // Micro regime — check blocked_micro rejection
      // (not directly overridable but clears if regime changes)

      if (cleared) {
        patched.passed = true;
        patched.rejectionGate = null;
        patched.rejectionReason = null;
        patched.rejectionDetails = null;
      }
    }

    return patched;
  }, [rawData, thresholdOverrides, isThresholdInteractive]);

  const contextRiskStrategyFloor = useMemo(
    () => resolveContextRiskStrategyFloor(data?.selectedStrategy ?? rawData?.selectedStrategy),
    [data?.selectedStrategy, rawData?.selectedStrategy],
  );
  const displayContextRiskMinRoom = useMemo(() => {
    const rawOverride = thresholdOverrides?.context_risk_min_room_pct;
    if (typeof rawOverride !== "number" || !Number.isFinite(rawOverride)) {
      return rawOverride ?? null;
    }
    if (!contextRiskStrategyFloor) return rawOverride;
    return Math.max(contextRiskStrategyFloor.minRoomPct, rawOverride);
  }, [thresholdOverrides?.context_risk_min_room_pct, contextRiskStrategyFloor]);
  const displayContextRiskMinEffectiveRr = useMemo(() => {
    const rawOverride = thresholdOverrides?.context_risk_min_effective_rr;
    if (typeof rawOverride !== "number" || !Number.isFinite(rawOverride)) {
      return rawOverride ?? null;
    }
    if (!contextRiskStrategyFloor) return rawOverride;
    return Math.max(contextRiskStrategyFloor.minEffectiveRr, rawOverride);
  }, [thresholdOverrides?.context_risk_min_effective_rr, contextRiskStrategyFloor]);
  const contextRiskFloorClamped =
    (typeof thresholdOverrides?.context_risk_min_room_pct === "number" &&
      displayContextRiskMinRoom != null &&
      displayContextRiskMinRoom >
        thresholdOverrides.context_risk_min_room_pct + 1e-9) ||
    (typeof thresholdOverrides?.context_risk_min_effective_rr === "number" &&
      displayContextRiskMinEffectiveRr != null &&
      displayContextRiskMinEffectiveRr >
        thresholdOverrides.context_risk_min_effective_rr + 1e-9);

  const applyAutoActivationMinimums = () => {
    if (
      !data ||
      !isThresholdInteractive ||
      typeof onThresholdOverrideChange !== "function"
    )
      return;

    const detectionKey = [
      String(data.source || "").trim(),
      String(data.markerType || "").trim(),
      String(data.selectedStrategy || "")
        .trim()
        .toLowerCase() || "unknown",
      String(data.barTimestamp ?? ""),
      String(data.rejectionGate ?? ""),
      String(data.signalDirection ?? ""),
      data.combinedScore != null
        ? String(Number(data.combinedScore).toFixed(4))
        : "na",
    ].join("|");
    if (!detectionKey) return;
    if (lastAutoApplyKeyRef.current === detectionKey) return;

    let updated = false;
    if (thresholdOverrides?.use_fixed_threshold !== true) {
      onThresholdOverrideChange("use_fixed_threshold", true);
      updated = true;
    }

    const updates = resolveActivationMinimumUpdates({
      data,
      currentOverrides: thresholdOverrides,
    });
    for (const update of updates) {
      onThresholdOverrideChange(update.key, update.value);
      updated = true;
    }

    if (updated || updates.length === 0) {
      lastAutoApplyKeyRef.current = detectionKey;
    }
  };

  useEffect(() => {
    if (!autoSetActivationMinimums) {
      lastAutoApplyKeyRef.current = "";
    }
  }, [autoSetActivationMinimums]);

  useEffect(() => {
    if (!autoSetActivationMinimums) return;
    applyAutoActivationMinimums();
  }, [autoSetActivationMinimums, applyAutoActivationMinimums]);

  if (!data) {
    return <div className="sa-panel-empty">Waiting for bar data...</div>;
  }

  // Dovolime zobrazit layer scores vzdy, ked ich mame (odstranujeme hardcoded check na intrabarOnlyCheckpoint)
  const hasLayerScores =
    data.combinedScore != null ||
    data.strategyScore != null ||
    data.flowScore != null;

  const hasGates =
    data.passed != null ||
    data.l2HasCoverage != null ||
    data.tcbboPassed != null;

  const hasL2 =
    data.l2AggressionZ != null ||
    data.l2BookPressureZ != null ||
    data.signedAggression != null;
  const hasIntrabar =
    data.intrabarCoverage != null ||
    data.intrabarMovePct != null ||
    data.intrabarPushRatio != null ||
    data.intrabarSpreadBps != null ||
    data.intrabarHasCoverage != null;
  const intrabarOnlyCheckpoint = Boolean(data.intrabarOnlyCheckpoint);
  const selectedStrategyIsPullback =
    data.selectedStrategy?.toLowerCase().includes("pullback") ||
    data.rejectionGate === "pullback_quality" ||
    rawData?.rejectionGate === "pullback_quality";

  return (
    <div className="sa-panel">
      {/* ── Header: type + strategy + regime + timestamp ── */}
      <div className="sa-header">
        <span className="sa-pill is-neutral is-uppercase">
          {data.markerType.replace(/_/g, " ")}
        </span>
        {data.selectedStrategy && (
          <span className="sa-header__strategy">{data.selectedStrategy}</span>
        )}
        {data.signalDirection &&
          (() => {
            const dir = String(data.signalDirection).toLowerCase();
            const isLong = dir === "long" || dir === "bullish" || dir === "buy";
            const label = isLong ? "LONG" : "SHORT";
            return (
              <span
                className={cx("sa-pill", isLong ? "is-success" : "is-danger")}
              >
                {isLong ? "\u25B2" : "\u25BC"} {label}
              </span>
            );
          })()}
        {data.regime && (
          <span className="sa-header__regime">
            {data.regime}
            {data.microRegime && data.microRegime !== data.regime
              ? ` / ${data.microRegime}`
              : ""}
          </span>
        )}
        {/* Timestamp: shows current bar time — helps user see data updates when scrubbing */}
        {data.barTimestamp &&
          (() => {
            const raw = data.barTimestamp;
            const ts =
              typeof raw === "number" ? new Date(raw * 1000) : new Date(raw);
            if (isNaN(ts.getTime())) return null;
            return (
              <span className="sa-header__timestamp">
                {ts.toLocaleTimeString("en-US", {
                  hour: "2-digit",
                  minute: "2-digit",
                  second: "2-digit",
                  hour12: false,
                })}
              </span>
            );
          })()}
      </div>

      {/* ── Scores: single-column when interactive, 2-col otherwise ── */}
      {hasLayerScores && (
        <>
          <SectionLabel icon={<BarChart2 size={10} />}>
            Entry Scores
            {data.confirmingSources != null && (
              <span
                className={cx(
                  "sa-section-label__meta",
                  data.confirmingSources >=
                    (data.requiredConfirmingSources ?? 0)
                    ? "is-success"
                    : "is-danger",
                )}
              >
                {data.confirmingSources}/{data.requiredConfirmingSources ?? "?"}{" "}
                sources
              </span>
            )}
          </SectionLabel>
          <div
            className={cx(
              "sa-score-grid",
              isThresholdInteractive && "is-interactive",
            )}
          >
            <InteractiveMiniBar
              label="Combined"
              value={data.combinedScore}
              threshold={data.threshold}
              showThresholdLine
              interactive={isThresholdInteractive}
              thresholdOverride={thresholdOverrides?.base_threshold}
              onThresholdChange={(v) =>
                onThresholdOverrideChange?.("base_threshold", v)
              }
              thresholdMin={30}
              thresholdMax={90}
            />
            <InteractiveMiniBar
              label="Str-Only Thr"
              value={data.strategyScore}
              threshold={thresholdOverrides?.strategy_only_threshold ?? null}
              showThresholdLine={
                isThresholdInteractive ||
                thresholdOverrides?.strategy_only_threshold != null
              }
              interactive={isThresholdInteractive}
              thresholdOverride={thresholdOverrides?.strategy_only_threshold}
              onThresholdChange={(v) =>
                onThresholdOverrideChange?.("strategy_only_threshold", v)
              }
              thresholdMin={40}
              thresholdMax={95}
            />
            {data.flowScore != null ? (
              <InteractiveMiniBar
                label="Flow"
                value={data.flowScore}
                threshold={thresholdOverrides?.strategy_weight ?? null}
                showThresholdLine={
                  isThresholdInteractive ||
                  thresholdOverrides?.strategy_weight != null
                }
                interactive={isThresholdInteractive}
                thresholdOverride={thresholdOverrides?.strategy_weight}
                onThresholdChange={(v) =>
                  onThresholdOverrideChange?.("strategy_weight", v)
                }
                thresholdMin={10}
                thresholdMax={90}
              />
            ) : !isThresholdInteractive ? (
              <div />
            ) : null}
            {data.levelQuality != null && (
              <InteractiveMiniBar
                label="Level Qlty"
                value={data.levelQuality}
                threshold={
                  thresholdOverrides?.min_confirming_sources != null
                    ? (thresholdOverrides.min_confirming_sources / 5) * 100
                    : null
                }
                showThresholdLine={
                  isThresholdInteractive ||
                  thresholdOverrides?.min_confirming_sources != null
                }
                interactive={isThresholdInteractive}
                thresholdOverride={
                  thresholdOverrides?.min_confirming_sources != null
                    ? (thresholdOverrides.min_confirming_sources / 5) * 100
                    : null
                }
                onThresholdChange={(v) =>
                  onThresholdOverrideChange?.(
                    "min_confirming_sources",
                    Math.round((v / 100) * 5),
                  )
                }
                thresholdMin={20}
                thresholdMax={100}
              />
            )}
          </div>

          {/* Pending overrides indicator */}
          {isThresholdInteractive && hasPendingOverrides && (
            <div className="sa-note is-pending">
              Threshold changes apply on next Play/Step
            </div>
          )}
          {isThresholdInteractive && contextRiskStrategyFloor && (
            <div className="sa-note is-muted is-tight">
              Context Risk floor for {contextRiskStrategyFloor.strategyKey}: room{" "}
              {contextRiskStrategyFloor.minRoomPct.toFixed(2)}, RR{" "}
              {contextRiskStrategyFloor.minEffectiveRr.toFixed(2)}
              {contextRiskFloorClamped ? " (current override is clamped to this floor)" : ""}
            </div>
          )}

          {/* Threshold info - cleaned up (hidden when interactive to avoid clutter) */}
          {!isThresholdInteractive && data.threshold != null && (
            <div className="sa-note is-muted is-tight">
              Thr: {data.threshold.toFixed(0)}
              {data.todBoost != null && data.todBoost !== 0 && (
                <span>
                  {" "}
                  ToD{data.todBoost > 0 ? "+" : ""}
                  {data.todBoost.toFixed(0)}
                </span>
              )}
              {data.headwindBoost != null && data.headwindBoost !== 0 && (
                <span>
                  {" "}
                  HW{data.headwindBoost > 0 ? "+" : ""}
                  {data.headwindBoost.toFixed(0)}
                </span>
              )}
              {data.thresholdReason &&
                (() => {
                  // Parse dynamic(...) into readable components
                  const raw = data.thresholdReason;
                  const m = raw.match(/regime_conf=([\d.]+)/);
                  const regConf = m ? parseFloat(m[1]) : null;
                  const trans = raw.includes("is_trans=True");
                  const parts: string[] = [];
                  if (regConf != null && regConf < 0.6)
                    parts.push(`regime weak (${(regConf * 100).toFixed(0)}%)`);
                  if (trans) parts.push("transition");
                  return parts.length > 0 ? (
                    <span className="sa-note__emphasis">
                      {" "}
                      · {parts.join(", ")}
                    </span>
                  ) : null;
                })()}
            </div>
          )}

          {/* ── Extra Tuning controls (interactive mode only) ── */}
          {isThresholdInteractive && (
            <>
              <SectionLabel icon={<Crosshair size={10} />}>Tuning</SectionLabel>
              <div className="sa-grid-single">
                <InteractiveMiniBar
                  label="Min Margin Over Thr"
                  value={thresholdOverrides?.min_margin_over_threshold ?? 3}
                  threshold={null}
                  showThresholdLine={false}
                  interactive
                  thresholdOverride={
                    thresholdOverrides?.min_margin_over_threshold ?? null
                  }
                  onThresholdChange={(v) =>
                    onThresholdOverrideChange?.("min_margin_over_threshold", v)
                  }
                  thresholdMin={0}
                  thresholdMax={20}
                  max={20}
                />
                <InteractiveMiniBar
                  label="Single Source Min Margin"
                  value={thresholdOverrides?.single_source_min_margin ?? 8}
                  threshold={null}
                  showThresholdLine={false}
                  interactive
                  thresholdOverride={
                    thresholdOverrides?.single_source_min_margin ?? null
                  }
                  onThresholdChange={(v) =>
                    onThresholdOverrideChange?.("single_source_min_margin", v)
                  }
                  thresholdMin={0}
                  thresholdMax={25}
                  max={25}
                />
                <InteractiveMiniBar
                  label="Ctx Risk Min Room %"
                  value={displayContextRiskMinRoom ?? 0.15}
                  threshold={null}
                  showThresholdLine={false}
                  interactive
                  thresholdOverride={displayContextRiskMinRoom}
                  onThresholdChange={(v) =>
                    onThresholdOverrideChange?.("context_risk_min_room_pct", v)
                  }
                  thresholdMin={contextRiskStrategyFloor?.minRoomPct ?? 0}
                  thresholdMax={1}
                  max={1}
                  suffix="%"
                />
                <InteractiveMiniBar
                  label="Ctx Risk Min RR"
                  value={displayContextRiskMinEffectiveRr ?? 0.8}
                  threshold={null}
                  showThresholdLine={false}
                  interactive
                  thresholdOverride={displayContextRiskMinEffectiveRr}
                  onThresholdChange={(v) =>
                    onThresholdOverrideChange?.(
                      "context_risk_min_effective_rr",
                      v,
                    )
                  }
                  thresholdMin={contextRiskStrategyFloor?.minEffectiveRr ?? 0}
                  thresholdMax={3}
                  max={3}
                />
                <InteractiveMiniBar
                  label="Min Confirming Sources"
                  value={
                    thresholdOverrides?.min_confirming_sources ??
                    data.requiredConfirmingSources ??
                    1
                  }
                  threshold={null}
                  showThresholdLine={false}
                  interactive
                  thresholdOverride={
                    thresholdOverrides?.min_confirming_sources ?? null
                  }
                  onThresholdChange={(v) =>
                    onThresholdOverrideChange?.(
                      "min_confirming_sources",
                      Math.round(v),
                    )
                  }
                  thresholdMin={0}
                  thresholdMax={5}
                  max={5}
                />
                <InteractiveMiniBar
                  label="Min Confluence Score"
                  value={
                    thresholdOverrides?.intraday_levels_min_confluence_score ??
                    2
                  }
                  threshold={null}
                  showThresholdLine={false}
                  interactive
                  thresholdOverride={
                    thresholdOverrides?.intraday_levels_min_confluence_score ??
                    null
                  }
                  onThresholdChange={(v) =>
                    onThresholdOverrideChange?.(
                      "intraday_levels_min_confluence_score",
                      Math.round(v),
                    )
                  }
                  thresholdMin={0}
                  thresholdMax={10}
                  max={10}
                />
                <InteractiveMiniBar
                  label="RVOL Min Thr"
                  value={
                    thresholdOverrides?.intraday_levels_rvol_min_threshold ??
                    0.8
                  }
                  threshold={null}
                  showThresholdLine={false}
                  interactive
                  thresholdOverride={
                    thresholdOverrides?.intraday_levels_rvol_min_threshold ??
                    null
                  }
                  onThresholdChange={(v) =>
                    onThresholdOverrideChange?.(
                      "intraday_levels_rvol_min_threshold",
                      v,
                    )
                  }
                  thresholdMin={0}
                  thresholdMax={3}
                  max={3}
                />
                <InteractiveMiniBar
                  label="Pullback RVOL Min"
                  value={
                    thresholdOverrides?.intraday_levels_pullback_rvol_min_threshold ??
                    0.3
                  }
                  threshold={null}
                  showThresholdLine={false}
                  interactive
                  thresholdOverride={
                    thresholdOverrides?.intraday_levels_pullback_rvol_min_threshold ??
                    null
                  }
                  onThresholdChange={(v) =>
                    onThresholdOverrideChange?.(
                      "intraday_levels_pullback_rvol_min_threshold",
                      v,
                    )
                  }
                  thresholdMin={0}
                  thresholdMax={2}
                  max={2}
                />
                <InteractiveMiniBar
                  label="Cost Aware Min Risk %"
                  value={
                    thresholdOverrides?.cost_aware_sweep_min_risk_pct ?? 0.1
                  }
                  threshold={null}
                  showThresholdLine={false}
                  interactive
                  thresholdOverride={
                    thresholdOverrides?.cost_aware_sweep_min_risk_pct ?? null
                  }
                  onThresholdChange={(v) =>
                    onThresholdOverrideChange?.(
                      "cost_aware_sweep_min_risk_pct",
                      v,
                    )
                  }
                  thresholdMin={0}
                  thresholdMax={1}
                  max={1}
                  suffix="%"
                />
              </div>

              {/* Master bypass toggle */}
              {(() => {
                const bypassOn =
                  thresholdOverrides?.bypass_all_entry_gates === true;
                return (
                  <ModeToggleButton
                    active={bypassOn}
                    tone="danger"
                    label="Bypass All Gates"
                    activeLabel="BYPASS ALL GATES — ON"
                    icon="🔒"
                    activeIcon="⚡"
                    spaced
                    onClick={() =>
                      onThresholdOverrideChange?.(
                        "bypass_all_entry_gates",
                        !bypassOn,
                      )
                    }
                  />
                );
              })()}

              {/* Fixed threshold toggle — disables dynamic adjustments */}
              {(() => {
                const fixedOn =
                  thresholdOverrides?.use_fixed_threshold === true;
                return (
                  <ModeToggleButton
                    active={fixedOn}
                    tone="warning"
                    label="Fixed Threshold (disable dynamic adj.)"
                    activeLabel="FIXED THRESHOLD — ON (no ToD/transition adj.)"
                    icon="📊"
                    activeIcon="📌"
                    onClick={() =>
                      onThresholdOverrideChange?.(
                        "use_fixed_threshold",
                        !fixedOn,
                      )
                    }
                  />
                );
              })()}

              {(() => {
                const autoOn = autoSetActivationMinimums;
                return (
                  <ModeToggleButton
                    active={autoOn}
                    tone="success"
                    label="Auto-Set Min Activation"
                    activeLabel="AUTO MIN ACTIVATION — ON"
                    icon="↦"
                    activeIcon="↧"
                    title="When enabled, each detected strategy snapshot auto-sets threshold overrides to exact minimum activation values."
                    onClick={() => {
                      const next = !autoSetActivationMinimums;
                      setAutoSetActivationMinimums(next);
                      if (next) {
                        applyAutoActivationMinimums();
                      }
                    }}
                  />
                );
              })()}

              {/* Feature flag toggles */}
              <div className="sa-toggle-grid">
                {FEATURE_TOGGLE_OPTIONS.map(([key, label]) => {
                  const override = thresholdOverrides?.[key];
                  const isOn = override != null ? Boolean(override) : true; // default on
                  const isOverridden = override != null;
                  return (
                    <FeatureToggleButton
                      key={key}
                      label={label}
                      isOn={isOn}
                      isOverridden={isOverridden}
                      onClick={() => onThresholdOverrideChange?.(key, !isOn)}
                    />
                  );
                })}
              </div>

              {/* ── Pullback quality gate controls ── */}
              {selectedStrategyIsPullback && (
                <>
                  <SectionLabel icon={<Target size={10} />}>
                    Pullback Gate
                  </SectionLabel>
                  <div className="sa-toggle-grid is-spaced-md">
                    {PULLBACK_TOGGLE_OPTIONS.map(([key, label]) => {
                      const override = thresholdOverrides?.[key];
                      const isOn = override != null ? Boolean(override) : true;
                      const isOverridden = override != null;
                      return (
                        <FeatureToggleButton
                          key={key}
                          label={label}
                          isOn={isOn}
                          isOverridden={isOverridden}
                          onClick={() =>
                            onThresholdOverrideChange?.(key, !isOn)
                          }
                        />
                      );
                    })}
                  </div>
                  <div className="sa-grid-single">
                    <InteractiveMiniBar
                      label="Min Trend Efficiency"
                      value={
                        thresholdOverrides?.pullback_min_price_trend_efficiency ??
                        0.15
                      }
                      threshold={null}
                      showThresholdLine={false}
                      interactive
                      thresholdOverride={
                        thresholdOverrides?.pullback_min_price_trend_efficiency ??
                        null
                      }
                      onThresholdChange={(v) =>
                        onThresholdOverrideChange?.(
                          "pullback_min_price_trend_efficiency",
                          v,
                        )
                      }
                      thresholdMin={0}
                      thresholdMax={1}
                      max={1}
                    />
                  </div>
                </>
              )}
            </>
          )}

          {/* ── Evidence Source Breakdown ── */}
          {data.sourceContributions &&
            (() => {
              const contributions: Record<string, number> =
                data.sourceContributions;
              const weights: Record<string, number> = data.sourceWeights || {};
              const sourceLabels: Record<string, string> = {
                strategy: "Strategy",
                feature: "Feature",
                l2_flow: "L2 Flow",
                cross_asset: "Cross-Asset",
                regime: "Regime",
              };
              const nameLabels: Record<string, string> = {
                rsi_oversold: "RSI Oversold",
                rsi_overbought: "RSI Overbought",
                momentum_strong: "Momentum",
                vwap_below: "VWAP Below",
                vwap_above: "VWAP Above",
                volume_spike: "Volume Spike",
                aggression: "Aggression",
                delta_divergence: "Delta Div",
                absorption: "Absorption",
                index_context: "Index",
                regime_direction: "Regime Dir",
              };
              const entries = Object.entries(contributions)
                .filter(([, v]) => v != null && v > 0)
                .sort((a, b) => b[1] - a[1]);
              if (entries.length === 0) return null;
              // Max contribution for normalization
              const maxContrib = Math.max(...entries.map(([, v]) => v), 0.01);
              return (
                <>
                  <SectionLabel icon={<Activity size={10} />}>
                    Evidence Breakdown
                  </SectionLabel>
                  <div className="sa-grid-two">
                    {entries.map(([key, value]) => {
                      const [type, ...nameParts] = key.split(":");
                      const name = nameParts.join(":");
                      const label =
                        nameLabels[name] ||
                        sourceLabels[type] ||
                        name.replace(/_/g, " ");
                      const weight = weights[key];
                      const weightPct =
                        weight != null ? (weight * 100).toFixed(0) : null;
                      return (
                        <MiniBar
                          key={key}
                          label={`${label}${weightPct ? ` (${weightPct}%)` : ""}`}
                          value={value * 100}
                          max={maxContrib * 100}
                          suffix=""
                        />
                      );
                    })}
                  </div>

                  {/* Aligned source tags — shown inline with evidence */}
                  {data.alignedSourceKeys.length > 0 && (
                    <div className="sa-tag-row is-spaced">
                      {data.alignedSourceKeys.map((key: string) => (
                        <span key={key} className="sa-pill is-info is-compact">
                          {key.replace(/_/g, " ")}
                        </span>
                      ))}
                    </div>
                  )}
                </>
              );
            })()}
        </>
      )}

      {/* ── Gates + rejection: inline badges row ── */}
      {hasGates && (
        <>
          <SectionLabel icon={<AlertTriangle size={10} />}>
            Entry Gates
          </SectionLabel>
          <div className="sa-tag-row">
            <GateBadge label="Pass" passed={data.passed} />
            <GateBadge label="L2" passed={data.l2HasCoverage} />
            <GateBadge label="L2Q" passed={data.l2QualityOk} />
            <GateBadge label="TCBBO" passed={data.tcbboPassed} />
            {data.sweepDetected === true && (
              <GateBadge label="Sweep" passed={true} />
            )}
          </div>
          {data.rejectionGate &&
            (() => {
              const thresholdHeadline = thresholdHeadlineFromDetails(
                data.rejectionDetails,
              );
              const gateLabels: Record<string, string> = {
                threshold: thresholdHeadline,
                confirming_sources: "Málo potvrdzujúcich zdrojov",
                l2_confirmation: "L2 flow nepotvrdil smer",
                tcbbo_confirmation: "Options flow nepodporuje",
                mu_choppy_filter: "Trh je príliš volatilný (choppy)",
                cost_aware_sweep: "Riziko príliš nízke pre sweep",
                intraday_levels_entry_quality:
                  "Kvalita vstupu pri úrovniach nízka",
                level_quality: "Kvalita okolitých úrovní nízka",
                cross_asset_headwind: "Protivietor z indexu",
                pullback_quality: "Pullback kvalita nedostatočná",
              };
              const readableGate =
                gateLabels[data.rejectionGate] ||
                data.rejectionGate.replace(/_/g, " ");
              return (
                <div className="sa-surface is-danger">
                  <div className="sa-surface__title">✗ {readableGate}</div>
                  <RejectionDetail d={data.rejectionDetails} />
                </div>
              );
            })()}
        </>
      )}

      {/* ── Bar Outcome (why entry did/didn't happen) ── */}
      {data.barAction &&
        (() => {
          const action = data.barAction;
          const reason = data.barReason || "";
          // Skip displaying for 'no_signal' or empty actions
          if (action === "no_signal" || action === "warmup") return null;
          const isPositive = action === "position_opened";
          const isSkip =
            action.includes("skip") ||
            action.includes("cooldown") ||
            action.includes("failed") ||
            action.includes("dropped") ||
            action.includes("insufficient");
          const isPending = action.includes("pending");
          const actionLabels: Record<string, string> = {
            position_opened: "✓ Pozícia otvorená",
            context_risk_skip: "✗ Context Risk SKIP",
            consecutive_loss_cooldown: "✗ Cooldown po stratách",
            micro_confirmation_failed: "✗ Micro potvrdenie zlyhalo",
            intrabar_confirmation_failed: "✗ Intrabar potvrdenie zlyhalo",
            pending_micro_confirmation: "⏳ Čaká na micro potvrdenie",
            pending_intrabar_confirmation: "⏳ Čaká na intrabar potvrdenie",
            insufficient_fill: "✗ Nedostatočný fill",
          };
          const label = actionLabels[action] || action.replace(/_/g, " ");
          const toneClass = isPositive
            ? "is-success"
            : isSkip
              ? "is-danger"
              : isPending
                ? "is-warning"
                : "is-neutral";
          return (
            <div className={cx("sa-surface", toneClass)}>
              <div className={cx("sa-surface__title", toneClass)}>{label}</div>
              {reason && <div className="sa-surface__body">{reason}</div>}
            </div>
          );
        })()}
      {/* ── Context Risk (post-signal execution gate) ── */}
      {data.contextRisk &&
        data.contextRisk.skip === true &&
        (() => {
          const cr = data.contextRisk;
          const rawSkipReason = String(cr.skip_reason || "");
          const skipLabel = rawSkipReason.split(":")[0].replace(/_/g, " ");
          const roomPct = safeNum(cr.room_pct);
          const riskPct = safeNum(cr.risk_pct);
          const effectiveRr = safeNum(cr.effective_rr);
          const minRoomPct = safeNum(cr.configured_min_room_pct);
          const minRr = safeNum(cr.configured_min_effective_rr);
          const slReason = cr.sl_reason
            ? String(cr.sl_reason).replace(/_/g, " ")
            : null;
          const wallPx = safeNum(cr.opposing_wall_price);
          const adjSl = safeNum(cr.adjusted_stop_loss);
          const adjTp = safeNum(cr.adjusted_take_profit);

          const roomFailed =
            roomPct != null && minRoomPct != null && roomPct < minRoomPct;
          const rrFailed =
            effectiveRr != null && minRr != null && effectiveRr < minRr;

          return (
            <div className="sa-surface is-danger is-relaxed">
              <div className="sa-surface__title is-danger">
                Context Risk: {skipLabel}
              </div>
              {roomPct != null && minRoomPct != null && (
                <RequirementBar
                  label="Room to target"
                  current={roomPct}
                  minimum={minRoomPct}
                  failed={roomFailed}
                  currentLabel={`${(roomPct * 100).toFixed(2)}%`}
                  minimumLabel={`${(minRoomPct * 100).toFixed(1)}%`}
                />
              )}
              {effectiveRr != null && minRr != null && (
                <RequirementBar
                  label="Risk:Reward"
                  current={effectiveRr}
                  minimum={minRr}
                  failed={rrFailed}
                  currentLabel={effectiveRr.toFixed(2)}
                  minimumLabel={minRr.toFixed(1)}
                />
              )}
              <div className="sa-detail-kv-grid">
                {riskPct != null && <div>Risk: {riskPct.toFixed(3)}%</div>}
                {slReason && <div>SL: {slReason}</div>}
                {adjSl != null && <div>SL price: {adjSl.toFixed(2)}</div>}
                {adjTp != null && <div>TP price: {adjTp.toFixed(2)}</div>}
                {wallPx != null && <div>Wall: {wallPx.toFixed(2)}</div>}
              </div>
            </div>
          );
        })()}

      {/* ── L2 Flow ── */}
      {hasL2 && (
        <>
          <SectionLabel icon={<Zap size={10} />}>L2 Flow</SectionLabel>
          <div className="sa-grid-three">
            {data.signedAggression != null && (
              <MiniBar
                label="Aggr"
                value={data.signedAggression}
                max={1}
                suffix=""
              />
            )}
            {data.l2AggressionZ != null && (
              <MiniBar
                label="Aggr Z"
                value={data.l2AggressionZ}
                max={4}
                suffix=""
              />
            )}
            {data.l2BookPressureZ != null && (
              <MiniBar
                label="Book Z"
                value={data.l2BookPressureZ}
                max={4}
                suffix=""
              />
            )}
          </div>
        </>
      )}

      {/* ── Candidates: compact list ── */}
      {data.top3.length > 0 && (
        <div className="sa-block">
          <SectionLabel icon={<Target size={10} />}>Candidates</SectionLabel>
          <div className="sa-grid-single is-spaced-md">
            {data.top3.map((s: any, i: number) => {
              const name = String(s?.name || `#${i + 1}`);
              const score = safeNum(s?.score);
              const isWinner = i === 0;
              return (
                <MiniBar
                  key={name}
                  label={
                    isWinner
                      ? `★ ${name.replace(/_/g, " ")}`
                      : name.replace(/_/g, " ")
                  }
                  value={score}
                  max={Math.max(100, score || 100)}
                  suffix=""
                />
              );
            })}
          </div>
          {data.calibratedProbability != null && (
            <div className="sa-block-foot">
              <MiniBar
                label="Win Probability (Calibrated)"
                value={data.calibratedProbability * 100}
                max={100}
                threshold={50}
                suffix="%"
                showThresholdLine
              />
            </div>
          )}
        </div>
      )}

      {hasIntrabar && (
        <div className="sa-block">
          <SectionLabel icon={<Crosshair size={10} />}>
            Intrabar (Checkpoint)
          </SectionLabel>
          {intrabarOnlyCheckpoint && (
            <div className="sa-note is-muted">
              5s checkpoint view shows real intrabar metrics only (minute
              decision scores hidden).
            </div>
          )}
          <div className="sa-grid-single is-spaced-md">
            {data.intrabarCoverage != null && (
              <MiniBar
                label="Coverage"
                value={data.intrabarCoverage}
                max={100}
                suffix=""
              />
            )}
            {data.intrabarMovePct != null && (
              <MiniBar
                label="Move %"
                value={data.intrabarMovePct}
                max={0.5}
                threshold={0.1}
                suffix="%"
                showThresholdLine
              />
            )}
            {data.intrabarPushRatio != null && (
              <MiniBar
                label="Push Ratio"
                value={data.intrabarPushRatio}
                max={1}
                threshold={0.5}
                suffix=""
                showThresholdLine
              />
            )}
            {data.intrabarSpreadBps != null && (
              <MiniBar
                label="Spread (bps)"
                value={data.intrabarSpreadBps}
                max={10}
                suffix=" bps"
              />
            )}
          </div>
        </div>
      )}
    </div>
  );
}
