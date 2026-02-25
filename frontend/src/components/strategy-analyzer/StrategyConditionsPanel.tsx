import { useMemo } from "react";
import { Activity, BarChart2, Target, Layers, Crosshair, Zap, AlertTriangle } from "lucide-react";
import { extractStrategyConditionsPanelData } from "./StrategyConditionsPanelData";
import { StrategyConditionsPanelRejectionDetail as RejectionDetail } from "./StrategyConditionsPanelRejectionDetail";
import { MiniBar, SectionLabel, safeNum } from "./StrategyConditionsPanelShared";

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

/* ── rejection detail renderer ────────────────────────────────────── */

/* ── main panel ───────────────────────────────────────────────────── */

interface StrategyConditionsPanelProps {
  marker: any;
  liveAnalysis?: any;
}

export default function StrategyConditionsPanel({ marker, liveAnalysis }: StrategyConditionsPanelProps) {
  const data = useMemo(() => extractStrategyConditionsPanelData(marker, liveAnalysis), [marker, liveAnalysis]);

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
  const intrabarOnlyCheckpoint = Boolean(data.intrabarOnlyCheckpoint);

  return (
    <div style={{ padding: "4px 8px", fontSize: "0.72rem" }}>
      {/* ── Header: type + strategy + regime + timestamp ── */}
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
        {/* Timestamp: shows current bar time — helps user see data updates when scrubbing */}
        {data.barTimestamp && (() => {
          const raw = data.barTimestamp;
          const ts = typeof raw === "number" ? new Date(raw * 1000) : new Date(raw);
          if (isNaN(ts.getTime())) return null;
          return (
            <span style={{ fontSize: "0.55rem", color: "var(--text-muted)", marginLeft: "auto", fontVariantNumeric: "tabular-nums" }}>
              {ts.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false })}
            </span>
          );
        })()}
      </div>

      {/* ── Scores: 2-column grid ── */}
      {hasLayerScores && (
        <>
          <SectionLabel icon={<BarChart2 size={10} />}>Entry Scores</SectionLabel>
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

          {/* Threshold info - cleaned up */}
          {data.threshold != null && (
            <div style={{ fontSize: "0.58rem", color: "var(--text-muted)", marginTop: 1, marginBottom: 2, lineHeight: 1.3 }}>
              Thr: {data.threshold.toFixed(0)}
              {data.todBoost != null && data.todBoost !== 0 && (
                <span> ToD{data.todBoost > 0 ? "+" : ""}{data.todBoost.toFixed(0)}</span>
              )}
              {data.headwindBoost != null && data.headwindBoost !== 0 && (
                <span> HW{data.headwindBoost > 0 ? "+" : ""}{data.headwindBoost.toFixed(0)}</span>
              )}
              {data.thresholdReason && (() => {
                // Parse dynamic(...) into readable components
                const raw = data.thresholdReason;
                const m = raw.match(/regime_conf=([\d.]+)/);
                const regConf = m ? parseFloat(m[1]) : null;
                const trans = raw.includes("is_trans=True");
                const parts: string[] = [];
                if (regConf != null && regConf < 0.6) parts.push(`regime weak (${(regConf * 100).toFixed(0)}%)`);
                if (trans) parts.push("transition");
                return parts.length > 0 ? (
                  <span style={{ fontStyle: "italic" }}> · {parts.join(", ")}</span>
                ) : null;
              })()}
            </div>
          )}

          {/* ── Evidence Source Breakdown ── */}
          {data.sourceContributions && (() => {
            const contributions: Record<string, number> = data.sourceContributions;
            const weights: Record<string, number> = data.sourceWeights || {};
            const sourceLabels: Record<string, string> = {
              "strategy": "Strategy",
              "feature": "Feature",
              "l2_flow": "L2 Flow",
              "cross_asset": "Cross-Asset",
              "regime": "Regime",
            };
            const nameLabels: Record<string, string> = {
              "rsi_oversold": "RSI Oversold",
              "rsi_overbought": "RSI Overbought",
              "momentum_strong": "Momentum",
              "vwap_below": "VWAP Below",
              "vwap_above": "VWAP Above",
              "volume_spike": "Volume Spike",
              "aggression": "Aggression",
              "delta_divergence": "Delta Div",
              "absorption": "Absorption",
              "index_context": "Index",
              "regime_direction": "Regime Dir",
            };
            const entries = Object.entries(contributions)
              .filter(([, v]) => v != null && v > 0)
              .sort((a, b) => b[1] - a[1]);
            if (entries.length === 0) return null;
            // Max contribution for normalization
            const maxContrib = Math.max(...entries.map(([, v]) => v), 0.01);
            return (
              <>
                <SectionLabel icon={<Activity size={10} />}>Evidence Breakdown</SectionLabel>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0 8px" }}>
                  {entries.map(([key, value]) => {
                    const [type, ...nameParts] = key.split(":");
                    const name = nameParts.join(":");
                    const label = nameLabels[name] || sourceLabels[type] || name.replace(/_/g, " ");
                    const weight = weights[key];
                    const weightPct = weight != null ? (weight * 100).toFixed(0) : null;
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
              </>
            );
          })()}
        </>
      )}

      {/* ── Gates + rejection: inline badges row ── */}
      {hasGates && (
        <>
          <SectionLabel icon={<AlertTriangle size={10} />}>Entry Gates</SectionLabel>
          <div style={{ display: "flex", gap: 3, flexWrap: "wrap", marginBottom: 3 }}>
            <GateBadge label="Pass" passed={data.passed} />
            <GateBadge label="L2" passed={data.l2HasCoverage} />
            <GateBadge label="L2Q" passed={data.l2QualityOk} />
            <GateBadge label="TCBBO" passed={data.tcbboPassed} />
            {data.sweepDetected === true && <GateBadge label="Sweep" passed={true} />}
          </div>
          {data.rejectionGate && (() => {
            const gateLabels: Record<string, string> = {
              threshold: "Score príliš nízky na vstup",
              confirming_sources: "Málo potvrdzujúcich zdrojov",
              l2_confirmation: "L2 flow nepotvrdil smer",
              tcbbo_confirmation: "Options flow nepodporuje",
              mu_choppy_filter: "Trh je príliš volatilný (choppy)",
              cost_aware_sweep: "Riziko príliš nízke pre sweep",
              intraday_levels_entry_quality: "Kvalita vstupu pri úrovniach nízka",
              level_quality: "Kvalita okolitých úrovní nízka",
              cross_asset_headwind: "Protivietor z indexu",
            };
            const readableGate = gateLabels[data.rejectionGate] || data.rejectionGate.replace(/_/g, " ");
            return (
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
                  ✗ {readableGate}
                </div>
                <RejectionDetail d={data.rejectionDetails} />
              </div>
            );
          })()}
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
                <SectionLabel icon={<Layers size={10} />}>Evidence</SectionLabel>
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
                <SectionLabel icon={<Zap size={10} />}>L2 Flow</SectionLabel>
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
        <div style={{ marginTop: 4 }}>
          <SectionLabel icon={<Target size={10} />}>Candidates</SectionLabel>
          <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: "2px 0", marginBottom: 4 }}>
            {data.top3.map((s: any, i: number) => {
              const name = String(s?.name || `#${i + 1}`);
              const score = safeNum(s?.score);
              const isWinner = i === 0;
              return (
                <MiniBar 
                  key={name}
                  label={isWinner ? `★ ${name.replace(/_/g, " ")}` : name.replace(/_/g, " ")} 
                  value={score} 
                  max={Math.max(100, score || 100)} 
                  suffix="" 
                />
              );
            })}
          </div>
          {data.calibratedProbability != null && (
            <div style={{ marginTop: 2, marginBottom: 4 }}>
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
        <div style={{ marginTop: 4 }}>
          <SectionLabel icon={<Crosshair size={10} />}>Intrabar (Checkpoint)</SectionLabel>
          {intrabarOnlyCheckpoint && (
            <div style={{ fontSize: "0.58rem", color: "var(--text-muted)", marginBottom: 3 }}>
              5s checkpoint view shows real intrabar metrics only (minute decision scores hidden).
            </div>
          )}
          <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: "2px 0", marginBottom: 4 }}>
            {data.intrabarCoverage != null && (
              <MiniBar label="Coverage" value={data.intrabarCoverage} max={100} suffix="" />
            )}
            {data.intrabarMovePct != null && (
              <MiniBar label="Move %" value={data.intrabarMovePct} max={0.5} threshold={0.1} suffix="%" showThresholdLine />
            )}
            {data.intrabarPushRatio != null && (
              <MiniBar label="Push Ratio" value={data.intrabarPushRatio} max={1} threshold={0.5} suffix="" showThresholdLine />
            )}
            {data.intrabarSpreadBps != null && (
              <MiniBar label="Spread (bps)" value={data.intrabarSpreadBps} max={10} suffix=" bps" />
            )}
          </div>
        </div>
      )}
    </div>
  );
}
