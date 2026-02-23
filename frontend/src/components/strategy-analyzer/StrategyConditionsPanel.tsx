import { useMemo } from "react";

/* ── helpers ──────────────────────────────────────────────────────── */

const safeNum = (v: unknown, fallback: number | null = null): number | null => {
  if (v == null) return fallback;
  const n = Number(v);
  return Number.isFinite(n) ? n : fallback;
};

const barColor = (value: number, max: number, threshold?: number | null): string => {
  const ratio = max > 0 ? value / max : 0;
  if (threshold != null && max > 0) {
    const tRatio = threshold / max;
    if (ratio >= tRatio) return "var(--accent-green, #22c55e)";
    if (ratio >= tRatio * 0.7) return "var(--accent-yellow, #eab308)";
    return "var(--accent-red, #ef4444)";
  }
  if (ratio >= 0.7) return "var(--accent-green, #22c55e)";
  if (ratio >= 0.4) return "var(--accent-yellow, #eab308)";
  return "var(--accent-red, #ef4444)";
};

/* ── compact progress bar ────────────────────────────────────────── */

interface MiniBarProps {
  label: string;
  value: number | null;
  max?: number;
  threshold?: number | null;
  suffix?: string;
  showThresholdLine?: boolean;
}

function MiniBar({ label, value, max = 100, threshold, suffix = "%", showThresholdLine }: MiniBarProps) {
  const displayVal = value ?? 0;
  const widthPct = max > 0 ? Math.min(100, Math.max(0, (displayVal / max) * 100)) : 0;
  const thresholdPct = threshold != null && max > 0 ? Math.min(100, (threshold / max) * 100) : null;

  return (
    <div style={{ marginBottom: 3 }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.65rem", lineHeight: 1.2, marginBottom: 1 }}>
        <span style={{ color: "var(--text-secondary)", fontWeight: 500 }}>{label}</span>
        <span style={{ color: "var(--text-primary)", fontWeight: 600, fontVariantNumeric: "tabular-nums" }}>
          {value != null ? `${displayVal.toFixed(1)}${suffix}` : "—"}
        </span>
      </div>
      <div
        style={{
          position: "relative",
          height: 4,
          borderRadius: 2,
          background: "var(--bg-tertiary, rgba(255,255,255,0.06))",
          overflow: "visible",
        }}
      >
        <div
          style={{
            height: "100%",
            width: `${widthPct}%`,
            borderRadius: 2,
            background: value != null ? barColor(displayVal, max, threshold) : "var(--bg-tertiary)",
            transition: "width 0.08s ease-out",
          }}
        />
        {showThresholdLine && thresholdPct != null && (
          <div
            style={{
              position: "absolute",
              top: -1,
              bottom: -1,
              left: `${thresholdPct}%`,
              width: 1.5,
              background: "var(--text-muted, #888)",
              borderRadius: 1,
              opacity: 0.6,
            }}
            title={`Threshold: ${threshold?.toFixed(1)}`}
          />
        )}
      </div>
    </div>
  );
}

/* ── gate badge (compact) ────────────────────────────────────────── */

function GateBadge({ label, passed }: { label: string; passed: boolean | null }) {
  if (passed == null) return null;
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 2,
        padding: "1px 5px",
        borderRadius: 3,
        fontSize: "0.6rem",
        fontWeight: 600,
        lineHeight: 1.3,
        background: passed ? "rgba(34, 197, 94, 0.1)" : "rgba(239, 68, 68, 0.1)",
        color: passed ? "var(--accent-green, #22c55e)" : "var(--accent-red, #ef4444)",
        border: `1px solid ${passed ? "rgba(34, 197, 94, 0.2)" : "rgba(239, 68, 68, 0.2)"}`,
      }}
    >
      <span style={{ fontSize: "0.55rem" }}>{passed ? "\u2713" : "\u2717"}</span>
      {label}
    </span>
  );
}

/* ── tiny section label (inline) ─────────────────────────────────── */

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        fontSize: "0.6rem",
        fontWeight: 700,
        textTransform: "uppercase",
        letterSpacing: "0.05em",
        color: "var(--text-muted)",
        marginTop: 5,
        marginBottom: 2,
      }}
    >
      {children}
    </div>
  );
}

/* ── rejection detail renderer ────────────────────────────────────── */

function RejectionDetail({ d }: { d: any }) {
  if (!d || typeof d !== "object" || !d.gate) return null;
  const gate = String(d.gate);
  const strategy = d.strategy ? String(d.strategy).replace(/_/g, " ") : null;

  if (gate === "confirming_sources") {
    const actual = safeNum(d.actual_confirming_sources) ?? 0;
    const required = safeNum(d.required_confirming_sources) ?? 0;
    const pct = required > 0 ? Math.min(100, (actual / required) * 100) : 0;
    const missing = Math.max(0, required - actual);
    const alignedKeys: string[] = Array.isArray(d.aligned_source_keys) ? d.aligned_source_keys : [];
    const nonAlignedSources: any[] = Array.isArray(d.non_aligned_source_keys) ? d.non_aligned_source_keys : [];
    const signalDir = typeof d.signal_direction === "string" ? d.signal_direction.toLowerCase() : null;

    return (
      <div style={{ marginTop: 3 }}>
        {/* header line: strategy + fraction */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", fontSize: "0.6rem", lineHeight: 1.2, marginBottom: 2 }}>
          <span style={{ color: "var(--text-secondary)" }}>
            {strategy && <span style={{ fontWeight: 600 }}>{strategy}</span>}
          </span>
          <span style={{ fontWeight: 700, fontVariantNumeric: "tabular-nums", color: "var(--accent-red, #ef4444)" }}>
            {actual}/{required} ({pct.toFixed(0)}%)
          </span>
        </div>
        {/* progress bar */}
        <div style={{ position: "relative", height: 5, borderRadius: 3, background: "var(--bg-tertiary, rgba(255,255,255,0.06))", overflow: "visible" }}>
          <div style={{ height: "100%", width: `${pct}%`, borderRadius: 3, background: pct >= 100 ? "var(--accent-green, #22c55e)" : "var(--accent-red, #ef4444)", opacity: 0.8, transition: "width 0.08s ease-out" }} />
          <div style={{ position: "absolute", top: -1, bottom: -1, left: "100%", width: 1.5, background: "var(--text-muted, #888)", borderRadius: 1, opacity: 0.5 }} title={`Required: ${required}`} />
        </div>
        {/* all evaluated sources */}
        {(alignedKeys.length > 0 || nonAlignedSources.length > 0) && (
          <div style={{ display: "flex", gap: 3, flexWrap: "wrap", marginTop: 4 }}>
            {alignedKeys.map((key: string) => (
              <span key={key} style={{
                display: "inline-flex", alignItems: "center", gap: 2,
                padding: "0px 4px", borderRadius: 2, fontSize: "0.52rem", lineHeight: 1.5,
                background: "rgba(34, 197, 94, 0.08)", color: "var(--accent-green, #22c55e)",
                border: "1px solid rgba(34, 197, 94, 0.18)",
              }}>
                <span style={{ fontSize: "0.48rem" }}>{"\u2713"}</span>
                {key.replace(/_/g, " ")}
              </span>
            ))}
            {nonAlignedSources.map((src: any) => {
              const key = String(src?.key || "");
              const dir = String(src?.direction || "").toLowerCase();
              const isOpposing = dir && signalDir && dir !== signalDir && dir !== "neutral";
              return (
                <span key={key} style={{
                  display: "inline-flex", alignItems: "center", gap: 2,
                  padding: "0px 4px", borderRadius: 2, fontSize: "0.52rem", lineHeight: 1.5,
                  background: isOpposing ? "rgba(239, 68, 68, 0.06)" : "rgba(148, 163, 184, 0.06)",
                  color: isOpposing ? "var(--accent-red, #ef4444)" : "var(--text-muted, #94a3b8)",
                  border: `1px solid ${isOpposing ? "rgba(239, 68, 68, 0.15)" : "rgba(148, 163, 184, 0.12)"}`,
                }}>
                  <span style={{ fontSize: "0.48rem" }}>{isOpposing ? "\u2717" : "\u2013"}</span>
                  {key.replace(/_/g, " ")}
                  {dir && <span style={{ opacity: 0.7, marginLeft: 1 }}>({dir})</span>}
                </span>
              );
            })}
          </div>
        )}
      </div>
    );
  }

  if (gate === "l2_confirmation") {
    const lm = d.l2_metrics;
    const reason = (lm && typeof lm === "object" && typeof lm.reason === "string") ? lm.reason : null;
    return (
      <div style={{ marginTop: 2, fontSize: "0.58rem", color: "var(--text-secondary)" }}>
        {strategy && <><span style={{ fontWeight: 600 }}>{strategy}</span> · </>}
        L2 flow not confirming{reason ? `: ${reason}` : ""}
      </div>
    );
  }

  if (gate === "tcbbo_confirmation") {
    const tm = d.tcbbo_metrics;
    const reason = (tm && typeof tm === "object" && typeof tm.reason === "string") ? tm.reason : null;
    return (
      <div style={{ marginTop: 2, fontSize: "0.58rem", color: "var(--text-secondary)" }}>
        {strategy && <><span style={{ fontWeight: 600 }}>{strategy}</span> · </>}
        TCBBO options flow not aligned{reason ? `: ${reason}` : ""}
      </div>
    );
  }

  if (gate === "mu_choppy_filter") {
    return (
      <div style={{ marginTop: 2, fontSize: "0.58rem", color: "var(--text-secondary)" }}>
        Choppy regime block{d.micro_regime ? ` (${d.micro_regime})` : ""}
      </div>
    );
  }

  if (gate === "cost_aware_sweep") {
    const risk = safeNum(d.risk_pct);
    const min = safeNum(d.min_required);
    return (
      <div style={{ marginTop: 2, fontSize: "0.58rem", color: "var(--text-secondary)" }}>
        Sweep risk too low{risk != null ? `: ${(risk * 100).toFixed(2)}%` : ""}{min != null ? ` (min ${(min * 100).toFixed(0)}%)` : ""}
      </div>
    );
  }

  if (gate === "intraday_levels_entry_quality" || gate === "level_quality") {
    const lc = (d.level_context && typeof d.level_context === "object") ? d.level_context : d;
    const stats = (lc.stats && typeof lc.stats === "object") ? lc.stats : {};
    const cfg = (lc.config && typeof lc.config === "object") ? lc.config : {};
    const checks = (lc.checks && typeof lc.checks === "object") ? lc.checks : {};
    const reasons: string[] = Array.isArray(lc.reasons) ? lc.reasons : (lc.reason ? [String(lc.reason)] : []);
    const softReasons: string[] = Array.isArray(lc.soft_reasons) ? lc.soft_reasons : [];
    const softFailedSet = new Set<string>(Array.isArray(lc.soft_failed_checks) ? lc.soft_failed_checks : []);
    const hasSoftWarnings = Boolean(lc.has_soft_warnings);

    const confluence = safeNum(stats.near_confluence_score);
    const minConfluence = safeNum(cfg.min_confluence_score ?? lc.min_confluence_score);
    const pct = (confluence != null && minConfluence != null && minConfluence > 0)
      ? Math.min(100, (confluence / minConfluence) * 100) : null;

    const hardFailedChecks = Object.entries(checks).filter(([k, v]) => v === false && !softFailedSet.has(k)).map(([k]) => k);
    const softFailedChecks = Object.entries(checks).filter(([k, v]) => v === false && softFailedSet.has(k)).map(([k]) => k);
    const passedChecks = Object.entries(checks).filter(([, v]) => v === true).map(([k]) => k);

    const isHardReject = hardFailedChecks.length > 0;
    const headerColor = isHardReject ? "var(--accent-red, #ef4444)" : hasSoftWarnings ? "var(--accent-yellow, #eab308)" : "var(--accent-green, #22c55e)";

    return (
      <div style={{ marginTop: 3 }}>
        {/* header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", fontSize: "0.6rem", lineHeight: 1.2, marginBottom: 2 }}>
          <span style={{ color: "var(--text-secondary)" }}>
            {strategy && <span style={{ fontWeight: 600 }}>{strategy}</span>}
          </span>
          {confluence != null && minConfluence != null && (
            <span style={{ fontWeight: 700, fontVariantNumeric: "tabular-nums", color: headerColor }}>
              confluence {confluence}/{minConfluence} ({pct != null ? pct.toFixed(0) : "?"}%)
            </span>
          )}
        </div>
        {/* confluence bar */}
        {pct != null && (
          <div style={{ position: "relative", height: 5, borderRadius: 3, background: "var(--bg-tertiary, rgba(255,255,255,0.06))", overflow: "visible", marginBottom: 4 }}>
            <div style={{ height: "100%", width: `${pct}%`, borderRadius: 3, background: pct >= 100 ? "var(--accent-green, #22c55e)" : "var(--accent-red, #ef4444)", opacity: 0.8 }} />
            <div style={{ position: "absolute", top: -1, bottom: -1, left: "100%", width: 1.5, background: "var(--text-muted, #888)", borderRadius: 1, opacity: 0.5 }} />
          </div>
        )}
        {/* hard failed checks -- these directly block entry */}
        {hardFailedChecks.length > 0 && (
          <div style={{ display: "flex", gap: 3, flexWrap: "wrap", marginBottom: 3 }}>
            {hardFailedChecks.map((k) => (
              <span key={k} style={{
                display: "inline-flex", alignItems: "center", gap: 2,
                padding: "1px 5px", borderRadius: 2, fontSize: "0.55rem", lineHeight: 1.5, fontWeight: 600,
                background: "rgba(239, 68, 68, 0.1)", color: "var(--accent-red, #ef4444)",
                border: "1px solid rgba(239, 68, 68, 0.25)",
              }}>
                <span>{"\u2717"}</span>
                {k.replace(/_/g, " ")}
              </span>
            ))}
          </div>
        )}
        {/* soft failed checks -- warnings, don't block entry */}
        {softFailedChecks.length > 0 && (
          <div style={{ display: "flex", gap: 3, flexWrap: "wrap", marginBottom: 3 }}>
            {softFailedChecks.map((k) => (
              <span key={k} style={{
                display: "inline-flex", alignItems: "center", gap: 2,
                padding: "1px 5px", borderRadius: 2, fontSize: "0.52rem", lineHeight: 1.5,
                background: "rgba(234, 179, 8, 0.1)", color: "var(--accent-yellow, #eab308)",
                border: "1px solid rgba(234, 179, 8, 0.25)",
              }}>
                <span>{"\u26A0"}</span>
                {k.replace(/_/g, " ")}
              </span>
            ))}
          </div>
        )}
        {/* passed strategy checks -- context only, shown smaller */}
        {passedChecks.length > 0 && (
          <div style={{ display: "flex", gap: 2, flexWrap: "wrap", opacity: 0.6 }}>
            {passedChecks.map((k) => (
              <span key={k} style={{
                display: "inline-flex", alignItems: "center", gap: 2,
                padding: "0px 3px", borderRadius: 2, fontSize: "0.48rem", lineHeight: 1.5,
                color: "var(--accent-green, #22c55e)",
              }}>
                <span>{"\u2713"}</span>
                {k.replace(/_/g, " ")}
              </span>
            ))}
          </div>
        )}
      </div>
    );
  }

  if (gate === "threshold" || gate === "cross_asset_headwind") {
    const score = safeNum(d.combined_score) ?? safeNum(d.combined_norm_0_100);
    const thr = safeNum(d.threshold_used) ?? safeNum(d.trade_gate_threshold);
    const stratScore = safeNum(d.strategy_score);
    const reasoning = typeof d.reasoning === "string" ? d.reasoning : null;
    const todBoost = safeNum(d.tod_threshold_boost);
    const hwBoost = safeNum(d.headwind_threshold_boost);
    const thrReason = typeof d.threshold_used_reason === "string" ? d.threshold_used_reason : null;
    const isHeadwind = gate === "cross_asset_headwind";

    const scorePct = (score != null && thr != null && thr > 0) ? Math.min(100, (score / thr) * 100) : null;
    const gap = (score != null && thr != null) ? thr - score : null;

    return (
      <div style={{ marginTop: 3 }}>
        {/* score vs threshold bar */}
        {score != null && thr != null && (
          <div style={{ marginBottom: 4 }}>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.55rem", marginBottom: 1 }}>
              <span style={{ color: "var(--text-secondary)" }}>
                {isHeadwind ? "Score (headwind adjusted)" : "Combined score"}
              </span>
              <span style={{ fontWeight: 700, fontVariantNumeric: "tabular-nums", color: "var(--accent-red, #ef4444)" }}>
                {score.toFixed(1)} / {thr.toFixed(0)} req
                {gap != null && gap > 0 && <span style={{ opacity: 0.7 }}> ({gap.toFixed(1)} short)</span>}
              </span>
            </div>
            <div style={{ position: "relative", height: 5, borderRadius: 3, background: "var(--bg-tertiary, rgba(255,255,255,0.06))", overflow: "visible" }}>
              <div style={{
                height: "100%",
                width: `${scorePct ?? 0}%`,
                borderRadius: 3,
                background: "var(--accent-red, #ef4444)",
                opacity: 0.8,
                transition: "width 0.08s ease-out",
              }} />
              <div style={{ position: "absolute", top: -1, bottom: -1, left: "100%", width: 1.5, background: "var(--text-muted, #888)", borderRadius: 1, opacity: 0.5 }} title={`Threshold: ${thr}`} />
            </div>
          </div>
        )}
        {/* threshold breakdown */}
        <div style={{ display: "flex", gap: 3, flexWrap: "wrap", fontSize: "0.52rem", color: "var(--text-muted)", marginBottom: 2 }}>
          {stratScore != null && (
            <span>Strategy: {stratScore.toFixed(1)}</span>
          )}
          {todBoost != null && todBoost !== 0 && (
            <span style={{ color: todBoost > 0 ? "var(--accent-red, #ef4444)" : "var(--accent-green, #22c55e)" }}>
              ToD {todBoost > 0 ? "+" : ""}{todBoost.toFixed(0)}
            </span>
          )}
          {hwBoost != null && hwBoost !== 0 && (
            <span style={{ color: "var(--accent-red, #ef4444)" }}>
              HW +{hwBoost.toFixed(1)}
            </span>
          )}
          {thrReason && <span style={{ fontStyle: "italic" }}>{thrReason}</span>}
        </div>
        {/* reasoning */}
        {reasoning && (
          <div style={{ fontSize: "0.52rem", color: "var(--text-muted)", fontStyle: "italic", lineHeight: 1.4, marginTop: 2 }}>
            {reasoning}
          </div>
        )}
      </div>
    );
  }

  const fallbackParts: string[] = [];
  if (strategy) fallbackParts.push(strategy);
  if (typeof d.reason === "string") fallbackParts.push(d.reason);
  if (!fallbackParts.length) return null;
  return (
    <div style={{ marginTop: 2, fontSize: "0.58rem", color: "var(--text-secondary)" }}>
      {fallbackParts.join(" · ")}
    </div>
  );
}

/* ── main panel ───────────────────────────────────────────────────── */

interface StrategyConditionsPanelProps {
  marker: any;
  liveAnalysis?: any;
}

/** Extract the unified data shape from either a decision marker or live bar analysis. */
function extractData(marker: any, liveAnalysis: any) {
  // ── From a decision marker ──
  if (marker) {
    const details = marker?.details || {};
    const metadata = details?.metadata || details?.signal_metadata || {};
    const ls =
      metadata?.layer_scores ||
      details?.layer_scores ||
      details?.signal_metadata?.layer_scores ||
      {};
    const cd =
      metadata?.candidate_diagnostics ||
      details?.candidate_diagnostics ||
      details?.signal_metadata?.candidate_diagnostics ||
      {};
    const flowSnapshot =
      details?.flow_snapshot ||
      metadata?.order_flow ||
      details?.signal_metadata?.order_flow ||
      {};
    const signalRejected = details?.signal_rejected || {};
    const intrabarSnapshot =
      details?.intrabar_1s ||
      metadata?.intrabar_1s ||
      details?.signal_metadata?.intrabar_1s ||
      {};
    const tcbbo =
      details?.tcbbo_confirmation ||
      metadata?.tcbbo_confirmation ||
      details?.signal_metadata?.tcbbo_confirmation ||
      {};
    const levelCtx =
      details?.level_context ||
      metadata?.level_context ||
      details?.signal_metadata?.level_context ||
      {};

    return {
      source: "marker" as const,
      combinedScore: safeNum(ls.combined_score ?? ls.combined_norm_0_100),
      strategyScore: safeNum(ls.strategy_score),
      flowScore: safeNum(ls.flow_score ?? flowSnapshot?.flow_score),
      threshold: safeNum(ls.threshold_used ?? ls.threshold ?? ls.trade_gate_threshold),
      thresholdReason: ls.threshold_used_reason || null,
      passed: typeof ls.passed === "boolean" ? ls.passed : null,
      confirmingSources: safeNum(ls.confirming_sources ?? ls.aligned_evidence_sources),
      requiredConfirmingSources: safeNum(ls.required_confirming_sources),
      alignedSourceKeys: Array.isArray(ls.aligned_source_keys) ? ls.aligned_source_keys : [],
      l2HasCoverage: typeof ls.l2_has_coverage === "boolean" ? ls.l2_has_coverage : null,
      l2QualityOk: typeof ls.l2_quality_ok === "boolean" ? ls.l2_quality_ok : null,
      l2AggressionZ: safeNum(ls.l2_aggression_z ?? flowSnapshot?.l2_aggression_z),
      l2BookPressureZ: safeNum(ls.l2_book_pressure_z ?? flowSnapshot?.l2_book_pressure_z),
      signedAggression: safeNum(flowSnapshot?.signed_aggression ?? ls.signed_aggression),
      microRegime: ls.micro_regime || null,
      regime: marker?.regime || null,
      todBoost: safeNum(ls.tod_threshold_boost),
      headwindBoost: safeNum(ls.headwind_threshold_boost),
      top3: Array.isArray(cd.top3) ? cd.top3 : [],
      activeStrategies: Array.isArray(cd.active_strategies) ? cd.active_strategies : [],
      selectedStrategy: cd.strategy_name || marker?.strategy || null,
      sweepDetected: typeof ls.sweep_detected === "boolean" ? ls.sweep_detected : null,
      tcbboPassed: typeof tcbbo?.passed === "boolean" ? tcbbo.passed : null,
      signalDirection: signalRejected?.signal_type || marker?.side || details?.side || cd?.signal_type || null,
      rejectionGate: signalRejected?.gate || null,
      rejectionReason: signalRejected?.reason || null,
      rejectionDetails: (signalRejected && typeof signalRejected === "object" && signalRejected.gate) ? signalRejected : null,
      contextRisk: (details?.context_risk && typeof details.context_risk === "object") ? details.context_risk : null,
      levelQuality: safeNum(levelCtx?.quality_score ?? levelCtx?.entry_quality),
      intrabarCoverage: safeNum(intrabarSnapshot?.coverage_points),
      intrabarMovePct: safeNum(intrabarSnapshot?.mid_move_pct),
      intrabarPushRatio: safeNum(intrabarSnapshot?.push_ratio),
      intrabarSpreadBps: safeNum(intrabarSnapshot?.spread_bps_avg),
      intrabarHasCoverage:
        typeof intrabarSnapshot?.has_intrabar_coverage === "boolean"
          ? intrabarSnapshot.has_intrabar_coverage
          : null,
      markerType: String(marker?.marker_type || "").trim(),
    };
  }

  // ── From live bar analysis (streamed with each bar) ──
  if (liveAnalysis) {
    const ls = liveAnalysis?.layer_scores || {};
    const sr = liveAnalysis?.signal_rejected || {};
    const cd = liveAnalysis?.candidate_diagnostics || {};
    const intrabar = liveAnalysis?.intrabar_1s || {};
    const tcbbo = liveAnalysis?.tcbbo_confirmation || {};
    const intrabarOnlyCheckpoint = Boolean(liveAnalysis?.checkpoint_mode && liveAnalysis?.intrabar_only_checkpoint);

    return {
      source: "live" as const,
      combinedScore: safeNum(ls.combined_score ?? ls.combined_norm_0_100),
      strategyScore: safeNum(ls.strategy_score),
      flowScore: safeNum(ls.flow_score),
      threshold: safeNum(ls.threshold_used ?? ls.threshold ?? ls.trade_gate_threshold),
      thresholdReason: ls.threshold_used_reason || null,
      passed: typeof ls.passed === "boolean" ? ls.passed : null,
      confirmingSources: safeNum(ls.confirming_sources ?? ls.aligned_evidence_sources),
      requiredConfirmingSources: safeNum(ls.required_confirming_sources),
      alignedSourceKeys: Array.isArray(ls.aligned_source_keys) ? ls.aligned_source_keys : [],
      l2HasCoverage: typeof ls.l2_has_coverage === "boolean" ? ls.l2_has_coverage : null,
      l2QualityOk: typeof ls.l2_quality_ok === "boolean" ? ls.l2_quality_ok : null,
      l2AggressionZ: safeNum(ls.l2_aggression_z),
      l2BookPressureZ: safeNum(ls.l2_book_pressure_z),
      signedAggression: safeNum(ls.signed_aggression),
      microRegime: ls.micro_regime || null,
      regime: null,
      todBoost: safeNum(ls.tod_threshold_boost),
      headwindBoost: safeNum(ls.headwind_threshold_boost),
      top3: Array.isArray(cd.top3) ? cd.top3 : [],
      activeStrategies: Array.isArray(cd.active_strategies) ? cd.active_strategies : [],
      selectedStrategy: cd.strategy_name || null,
      sweepDetected: typeof ls.sweep_detected === "boolean" ? ls.sweep_detected : null,
      tcbboPassed: (tcbbo?.enabled === true)
        ? (typeof tcbbo?.passed === "boolean" ? tcbbo.passed : null)
        : null,
      signalDirection: sr?.signal_type || cd?.signal_type || null,
      rejectionGate: sr?.gate || null,
      rejectionReason: sr?.reason || null,
      rejectionDetails: (sr && typeof sr === "object" && sr.gate) ? sr : null,
      contextRisk: (liveAnalysis?.context_risk && typeof liveAnalysis.context_risk === "object") ? liveAnalysis.context_risk : null,
      levelQuality: null,
      intrabarCoverage: safeNum(intrabar?.coverage_points),
      intrabarMovePct: safeNum(intrabar?.mid_move_pct),
      intrabarPushRatio: safeNum(intrabar?.push_ratio),
      intrabarSpreadBps: safeNum(intrabar?.spread_bps_avg),
      intrabarHasCoverage:
        typeof intrabar?.has_intrabar_coverage === "boolean" ? intrabar.has_intrabar_coverage : null,
      markerType: intrabarOnlyCheckpoint ? "5s checkpoint" : (liveAnalysis?.warmup_only ? "warmup" : "live bar"),
      intrabarOnlyCheckpoint,
      liveAnalysisSource: liveAnalysis,
    };
  }

  return null;
}

export default function StrategyConditionsPanel({ marker, liveAnalysis }: StrategyConditionsPanelProps) {
  const data = useMemo(() => extractData(marker, liveAnalysis), [marker, liveAnalysis]);

  if (!data) {
    return (
      <div style={{ padding: "0.5rem", color: "var(--text-muted)", fontSize: "0.72rem", textAlign: "center" }}>
        Waiting for bar data...
      </div>
    );
  }

  // Dovolime zobrazit layer scores vzdy, ked ich mame (odstranujeme hardcoded check na intrabarOnlyCheckpoint)
  const hasLayerScores =
    data.combinedScore != null || data.strategyScore != null || data.flowScore != null;

  const hasGates =
    data.passed != null || data.l2HasCoverage != null || data.tcbboPassed != null;

  const hasL2 =
    data.l2AggressionZ != null || data.l2BookPressureZ != null || data.signedAggression != null;
  const hasIntrabar =
    data.intrabarCoverage != null ||
    data.intrabarMovePct != null ||
    data.intrabarPushRatio != null ||
    data.intrabarSpreadBps != null ||
    data.intrabarHasCoverage != null;
  const intrabarOnlyCheckpoint = Boolean((data as any)?.intrabarOnlyCheckpoint);

  return (
    <div style={{ padding: "4px 8px", fontSize: "0.72rem" }}>
      {/* ── Header: type + strategy + regime (single compact line) ── */}
      <div style={{ display: "flex", alignItems: "center", gap: 4, marginBottom: 4, flexWrap: "wrap" }}>
        <span
          style={{
            padding: "1px 5px",
            borderRadius: 3,
            fontSize: "0.6rem",
            fontWeight: 700,
            textTransform: "uppercase",
            background: "var(--bg-tertiary, rgba(255,255,255,0.06))",
            color: "var(--text-secondary)",
          }}
        >
          {data.markerType.replace(/_/g, " ")}
        </span>
        {data.selectedStrategy && (
          <span style={{ fontWeight: 700, fontSize: "0.68rem", color: "var(--accent-blue, #3b82f6)" }}>
            {data.selectedStrategy}
          </span>
        )}
        {data.signalDirection && (() => {
          const dir = String(data.signalDirection).toLowerCase();
          const isLong = dir === "long" || dir === "bullish" || dir === "buy";
          const label = isLong ? "LONG" : "SHORT";
          return (
            <span style={{
              padding: "1px 5px", borderRadius: 3, fontSize: "0.58rem", fontWeight: 700,
              background: isLong ? "rgba(34, 197, 94, 0.12)" : "rgba(239, 68, 68, 0.12)",
              color: isLong ? "var(--accent-green, #22c55e)" : "var(--accent-red, #ef4444)",
              border: `1px solid ${isLong ? "rgba(34, 197, 94, 0.25)" : "rgba(239, 68, 68, 0.25)"}`,
            }}>
              {isLong ? "\u25B2" : "\u25BC"} {label}
            </span>
          );
        })()}
        {data.regime && (
          <span style={{ fontSize: "0.6rem", color: "var(--text-muted)" }}>
            {data.regime}
            {data.microRegime && data.microRegime !== data.regime ? ` / ${data.microRegime}` : ""}
          </span>
        )}
      </div>

      {/* ── Scores: 2-column grid ── */}
      {hasLayerScores && (
        <>
          <SectionLabel>Entry Scores</SectionLabel>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0 8px" }}>
            <MiniBar label="Combined" value={data.combinedScore} threshold={data.threshold} showThresholdLine />
            <MiniBar label="Strategy" value={data.strategyScore} />
            {data.flowScore != null ? (
              <MiniBar label="Flow" value={data.flowScore} />
            ) : (
              <div />
            )}
            {data.levelQuality != null && (
              <MiniBar label="Level Qlty" value={data.levelQuality} />
            )}
          </div>

          {/* Threshold info - single compact line */}
          {data.threshold != null && (
            <div style={{ fontSize: "0.58rem", color: "var(--text-muted)", marginTop: 1, marginBottom: 2, lineHeight: 1.3 }}>
              Thr: {data.threshold.toFixed(0)}
              {data.todBoost != null && data.todBoost !== 0 && (
                <span> ToD{data.todBoost > 0 ? "+" : ""}{data.todBoost.toFixed(0)}</span>
              )}
              {data.headwindBoost != null && data.headwindBoost !== 0 && (
                <span> HW{data.headwindBoost > 0 ? "+" : ""}{data.headwindBoost.toFixed(0)}</span>
              )}
              {data.thresholdReason && (
                <span style={{ fontStyle: "italic" }}> {data.thresholdReason}</span>
              )}
            </div>
          )}
        </>
      )}

      {/* ── Gates + rejection: inline badges row ── */}
      {hasGates && (
        <>
          <SectionLabel>Entry Gates</SectionLabel>
          <div style={{ display: "flex", gap: 3, flexWrap: "wrap", marginBottom: 3 }}>
            <GateBadge label="Pass" passed={data.passed} />
            <GateBadge label="L2" passed={data.l2HasCoverage} />
            <GateBadge label="L2Q" passed={data.l2QualityOk} />
            <GateBadge label="TCBBO" passed={data.tcbboPassed} />
            {data.sweepDetected === true && <GateBadge label="Sweep" passed={true} />}
          </div>
          {data.rejectionGate && (
            <div style={{
              fontSize: "0.58rem",
              color: "var(--accent-red, #ef4444)",
              background: "rgba(239, 68, 68, 0.06)",
              padding: "3px 6px",
              borderRadius: 3,
              marginBottom: 2,
              lineHeight: 1.4,
            }}>
              <div style={{ fontWeight: 600, fontSize: "0.6rem" }}>
                Rejected: {data.rejectionGate.replace(/_/g, " ")}
              </div>
              <RejectionDetail d={data.rejectionDetails} />
            </div>
          )}
        </>
      )}

      {/* ── Context Risk (post-signal execution gate) ── */}
      {data.contextRisk && data.contextRisk.skip === true && (() => {
        const cr = data.contextRisk;
        const rawSkipReason = String(cr.skip_reason || "");
        const skipLabel = rawSkipReason.split(":")[0].replace(/_/g, " ");
        const roomPct = safeNum(cr.room_pct);
        const riskPct = safeNum(cr.risk_pct);
        const effectiveRr = safeNum(cr.effective_rr);
        const minRoomPct = safeNum(cr.configured_min_room_pct);
        const minRr = safeNum(cr.configured_min_effective_rr);
        const slReason = cr.sl_reason ? String(cr.sl_reason).replace(/_/g, " ") : null;
        const wallPx = safeNum(cr.opposing_wall_price);
        const adjSl = safeNum(cr.adjusted_stop_loss);
        const adjTp = safeNum(cr.adjusted_take_profit);

        const roomFailed = roomPct != null && minRoomPct != null && roomPct < minRoomPct;
        const rrFailed = effectiveRr != null && minRr != null && effectiveRr < minRr;

        return (
          <div style={{
            fontSize: "0.58rem",
            background: "rgba(239, 68, 68, 0.06)",
            padding: "4px 6px",
            borderRadius: 3,
            marginBottom: 3,
            lineHeight: 1.5,
          }}>
            <div style={{ fontWeight: 600, fontSize: "0.6rem", color: "var(--accent-red, #ef4444)", marginBottom: 3 }}>
              Context Risk: {skipLabel}
            </div>
            {/* Room bar */}
            {roomPct != null && minRoomPct != null && (
              <div style={{ marginBottom: 4 }}>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.55rem", marginBottom: 1 }}>
                  <span style={{ color: "var(--text-secondary)" }}>Room to target</span>
                  <span style={{ fontWeight: 700, fontVariantNumeric: "tabular-nums", color: roomFailed ? "var(--accent-red, #ef4444)" : "var(--accent-green, #22c55e)" }}>
                    {(roomPct * 100).toFixed(2)}% / {(minRoomPct * 100).toFixed(1)}% min
                  </span>
                </div>
                <div style={{ position: "relative", height: 5, borderRadius: 3, background: "var(--bg-tertiary, rgba(255,255,255,0.06))", overflow: "visible" }}>
                  <div style={{ height: "100%", width: `${Math.min(100, (roomPct / minRoomPct) * 100)}%`, borderRadius: 3, background: roomFailed ? "var(--accent-red, #ef4444)" : "var(--accent-green, #22c55e)", opacity: 0.8 }} />
                  <div style={{ position: "absolute", top: -1, bottom: -1, left: "100%", width: 1.5, background: "var(--text-muted, #888)", borderRadius: 1, opacity: 0.5 }} />
                </div>
              </div>
            )}
            {/* R:R bar */}
            {effectiveRr != null && minRr != null && (
              <div style={{ marginBottom: 4 }}>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.55rem", marginBottom: 1 }}>
                  <span style={{ color: "var(--text-secondary)" }}>Risk:Reward</span>
                  <span style={{ fontWeight: 700, fontVariantNumeric: "tabular-nums", color: rrFailed ? "var(--accent-red, #ef4444)" : "var(--accent-green, #22c55e)" }}>
                    {effectiveRr.toFixed(2)} / {minRr.toFixed(1)} min
                  </span>
                </div>
                <div style={{ position: "relative", height: 5, borderRadius: 3, background: "var(--bg-tertiary, rgba(255,255,255,0.06))", overflow: "visible" }}>
                  <div style={{ height: "100%", width: `${Math.min(100, (effectiveRr / minRr) * 100)}%`, borderRadius: 3, background: rrFailed ? "var(--accent-red, #ef4444)" : "var(--accent-green, #22c55e)", opacity: 0.8 }} />
                  <div style={{ position: "absolute", top: -1, bottom: -1, left: "100%", width: 1.5, background: "var(--text-muted, #888)", borderRadius: 1, opacity: 0.5 }} />
                </div>
              </div>
            )}
            {/* Details grid */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1px 10px", fontSize: "0.52rem", color: "var(--text-muted)" }}>
              {riskPct != null && <div>Risk: {riskPct.toFixed(3)}%</div>}
              {slReason && <div>SL: {slReason}</div>}
              {adjSl != null && <div>SL price: {adjSl.toFixed(2)}</div>}
              {adjTp != null && <div>TP price: {adjTp.toFixed(2)}</div>}
              {wallPx != null && <div>Wall: {wallPx.toFixed(2)}</div>}
            </div>
          </div>
        );
      })()}

      {/* ── Evidence + L2: side by side in 2 cols ── */}
      {(data.confirmingSources != null || hasL2) && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0 8px", marginTop: 2 }}>
          {/* Left: Evidence */}
          <div>
            {data.confirmingSources != null && (
              <>
                <SectionLabel>Evidence</SectionLabel>
                <MiniBar
                  label="Sources"
                  value={data.confirmingSources}
                  max={Math.max(data.requiredConfirmingSources ?? 5, data.confirmingSources, 5)}
                  threshold={data.requiredConfirmingSources}
                  suffix=""
                  showThresholdLine
                />
              </>
            )}
          </div>
          {/* Right: L2 */}
          <div>
      {hasL2 && (
        <>
                <SectionLabel>L2 Flow</SectionLabel>
                {data.signedAggression != null && (
                  <MiniBar label="Aggr" value={data.signedAggression} max={1} suffix="" />
                )}
                {data.l2AggressionZ != null && (
                  <MiniBar label="Aggr Z" value={data.l2AggressionZ} max={4} suffix="" />
                )}
                {data.l2BookPressureZ != null && (
                  <MiniBar label="Book Z" value={data.l2BookPressureZ} max={4} suffix="" />
                )}
              </>
            )}
          </div>
        </div>
      )}

      {/* Aligned source tags */}
      {data.alignedSourceKeys.length > 0 && (
        <div style={{ display: "flex", gap: 2, flexWrap: "wrap", marginTop: 2, marginBottom: 2 }}>
          {data.alignedSourceKeys.map((key: string) => (
            <span
              key={key}
              style={{
                padding: "0px 4px",
                borderRadius: 2,
                fontSize: "0.55rem",
                lineHeight: 1.5,
                background: "rgba(59, 130, 246, 0.08)",
                color: "var(--accent-blue, #3b82f6)",
                border: "1px solid rgba(59, 130, 246, 0.15)",
              }}
            >
              {key.replace(/_/g, " ")}
            </span>
          ))}
        </div>
      )}

      {/* ── Candidates: compact list ── */}
      {data.top3.length > 0 && (
        <>
          <SectionLabel>Candidates</SectionLabel>
          {data.top3.map((s: any, i: number) => {
            const name = String(s?.name || `#${i + 1}`);
            const score = safeNum(s?.score);
            const isWinner = i === 0;
            return (
              <div key={name} style={{ marginBottom: 2 }}>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.6rem", lineHeight: 1.2, marginBottom: 1 }}>
                  <span style={{
                    color: isWinner ? "var(--accent-green, #22c55e)" : "var(--text-secondary)",
                    fontWeight: isWinner ? 700 : 500,
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                    maxWidth: "65%",
                  }}>
                    {isWinner ? "\u2605 " : ""}{name.replace(/_/g, " ")}
                  </span>
                  <span style={{ color: "var(--text-primary)", fontWeight: 600, fontVariantNumeric: "tabular-nums" }}>
                    {score != null ? score.toFixed(0) : "—"}
                  </span>
                </div>
                <div style={{ height: 3, borderRadius: 1.5, background: "var(--bg-tertiary, rgba(255,255,255,0.06))", overflow: "hidden" }}>
                  <div
                    style={{
                      height: "100%",
                      width: `${score != null ? Math.min(100, Math.max(0, score)) : 0}%`,
                      borderRadius: 1.5,
                      background: isWinner ? "var(--accent-green, #22c55e)" : "var(--accent-blue, #3b82f6)",
                      opacity: isWinner ? 1 : 0.6,
                      transition: "width 0.08s ease-out",
                    }}
                  />
                </div>
              </div>
            );
          })}
        </>
      )}

      {hasIntrabar && (
        <>
          <SectionLabel>Intrabar (Checkpoint)</SectionLabel>
          {intrabarOnlyCheckpoint && (
            <div style={{ fontSize: "0.58rem", color: "var(--text-muted)", marginBottom: 3 }}>
              5s checkpoint view shows real intrabar metrics only (minute decision scores hidden).
            </div>
          )}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 1fr",
              gap: "0 8px",
              fontSize: "0.62rem",
              color: "var(--text-secondary)",
              lineHeight: 1.4,
              marginBottom: 4,
            }}
          >
            <div>Coverage: {data.intrabarCoverage != null ? Math.round(data.intrabarCoverage) : "-"}</div>
            <div>Spread: {data.intrabarSpreadBps != null ? `${data.intrabarSpreadBps.toFixed(1)} bps` : "-"}</div>
            <div>Move: {data.intrabarMovePct != null ? `${data.intrabarMovePct.toFixed(3)}%` : "-"}</div>
            <div>Push: {data.intrabarPushRatio != null ? data.intrabarPushRatio.toFixed(2) : "-"}</div>
          </div>
        </>
      )}
    </div>
  );
}
