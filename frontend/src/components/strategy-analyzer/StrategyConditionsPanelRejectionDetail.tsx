import { BarChart2, Layers } from "lucide-react";

import { StrategyConditionsPanelFormattedReasoning as FormattedReasoning } from "./StrategyConditionsPanelFormattedReasoning";
import { MiniBar, SectionLabel, safeNum } from "./StrategyConditionsPanelShared";

const CHECK_EXPLANATIONS: Record<string, string> = {
  rvol_minimum: "Relatívny objem (RVOL) presahuje minimálnu hranicu pre vstup",
  near_tested_level: "Cena je optimálne blízko testovanej úrovne (level)",
  minimum_confluence_score: "Dostatočná súhra viacerých indikátorov (confluence)",
  rotation_level_tests_range: "Počet otestovaní rotačnej úrovne je v norme",
  rotation_level_unbroken: "Rotačná úroveň nebola trvalo prelomená",
  tracker_enabled: "Sledovanie úrovní (Level tracker) je aktívne",
  entry_quality_enabled: "Filtrovanie kvality vstupu je zapnuté",
  valid_direction: "Smer signálu je v súlade s celkovým trendom",
  minimum_levels_context: "Dostatok kontextových údajov z okolitých úrovní",
  rvol_filter_enabled: "RVOL filter je zapnutý a aktívny",
  rvol_available: "Dáta o relatívnom objeme sú dostupné",
  adaptive_window_enabled: "Adaptívne časové okno je aktívne",
  adaptive_window_ready: "Adaptívne okno nazbieralo dostatok údajov",
  rotation_volume_ratio_available: "Pomer objemov pre rotáciu je dostupný",
  rotation_volume_exhaustion: "Vyčerpanie objemu ukazuje na možný obrat",
  no_recent_volume_break: "Žiadne nedávne silné prelomenia s vysokým objemom",
  rotation_prefers_non_trending_poc_migration: "Presun POC (Point of Control) nenaznačuje silný trend proti rotácii",
  gap_fill_bias_aligned: "Smerovanie k vyplneniu gapu súhlasí so signálom",
};

function resolveDirectionToken(raw: unknown): "bullish" | "bearish" | null {
  if (raw == null) return null;
  const token = String(raw).trim().toLowerCase();
  if (!token) return null;
  if (token === "buy" || token === "long" || token === "bullish" || token.includes("bullish")) return "bullish";
  if (token === "sell" || token === "short" || token === "bearish" || token.includes("bearish")) return "bearish";
  return null;
}

function resolveDirectionFromRejection(d: any): "bullish" | "bearish" | null {
  return (
    resolveDirectionToken(d?.resolved_signal_direction) ||
    resolveDirectionToken(d?.signal_type) ||
    resolveDirectionToken(d?.signal_direction) ||
    resolveDirectionToken(d?.direction) ||
    resolveDirectionToken(d?.decision_direction) ||
    resolveDirectionToken(d?.cross_asset_headwind?.decision_direction) ||
    resolveDirectionToken(d?.reasoning) ||
    null
  );
}

export function StrategyConditionsPanelRejectionDetail({ d }: { d: any }) {
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
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", fontSize: "0.6rem", lineHeight: 1.2, marginBottom: 2 }}>
          <span style={{ color: "var(--text-secondary)" }}>
            {strategy && <span style={{ fontWeight: 600 }}>{strategy}</span>}
          </span>
          <span style={{ fontWeight: 700, fontVariantNumeric: "tabular-nums", color: "var(--accent-red, #ef4444)" }}>
            {actual}/{required} ({pct.toFixed(0)}%)
          </span>
        </div>
        <div style={{ position: "relative", height: 5, borderRadius: 3, background: "var(--bg-tertiary, rgba(255,255,255,0.06))", overflow: "visible" }}>
          <div style={{ height: "100%", width: `${pct}%`, borderRadius: 3, background: pct >= 100 ? "var(--accent-green, #22c55e)" : "var(--accent-red, #ef4444)", opacity: 0.8, transition: "width 0.08s ease-out" }} />
          <div style={{ position: "absolute", top: -1, bottom: -1, left: "100%", width: 1.5, background: "var(--text-muted, #888)", borderRadius: 1, opacity: 0.5 }} title={`Required: ${required}`} />
        </div>
        {(alignedKeys.length > 0 || nonAlignedSources.length > 0) && (
          <div style={{ display: "flex", gap: 3, flexWrap: "wrap", marginTop: 4 }}>
            {alignedKeys.map((key: string) => (
              <span
                key={key}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 2,
                  padding: "0px 4px",
                  borderRadius: 2,
                  fontSize: "0.52rem",
                  lineHeight: 1.5,
                  background: "rgba(34, 197, 94, 0.08)",
                  color: "var(--accent-green, #22c55e)",
                  border: "1px solid rgba(34, 197, 94, 0.18)",
                }}
              >
                <span style={{ fontSize: "0.48rem" }}>{"\u2713"}</span>
                {key.replace(/_/g, " ")}
              </span>
            ))}
            {nonAlignedSources.map((src: any) => {
              const key = String(src?.key || "");
              const dir = String(src?.direction || "").toLowerCase();
              const isOpposing = dir && signalDir && dir !== signalDir && dir !== "neutral";
              return (
                <span
                  key={key}
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 2,
                    padding: "0px 4px",
                    borderRadius: 2,
                    fontSize: "0.52rem",
                    lineHeight: 1.5,
                    background: isOpposing ? "rgba(239, 68, 68, 0.06)" : "rgba(148, 163, 184, 0.06)",
                    color: isOpposing ? "var(--accent-red, #ef4444)" : "var(--text-muted, #94a3b8)",
                    border: `1px solid ${isOpposing ? "rgba(239, 68, 68, 0.15)" : "rgba(148, 163, 184, 0.12)"}`,
                  }}
                >
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
    const reason = lm && typeof lm === "object" && typeof lm.reason === "string" ? lm.reason : null;
    return (
      <div style={{ marginTop: 2, fontSize: "0.58rem", color: "var(--text-secondary)" }}>
        {strategy && (
          <>
            <span style={{ fontWeight: 600 }}>{strategy}</span> ·{" "}
          </>
        )}
        L2 flow not confirming{reason ? `: ${reason}` : ""}
      </div>
    );
  }

  if (gate === "tcbbo_confirmation") {
    const tm = d.tcbbo_metrics;
    const reason = tm && typeof tm === "object" && typeof tm.reason === "string" ? tm.reason : null;
    return (
      <div style={{ marginTop: 2, fontSize: "0.58rem", color: "var(--text-secondary)" }}>
        {strategy && (
          <>
            <span style={{ fontWeight: 600 }}>{strategy}</span> ·{" "}
          </>
        )}
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
        Sweep risk too low{risk != null ? `: ${(risk * 100).toFixed(2)}%` : ""}
        {min != null ? ` (min ${(min * 100).toFixed(0)}%)` : ""}
      </div>
    );
  }

  if (gate === "intraday_levels_entry_quality" || gate === "level_quality") {
    const lc = d.level_context && typeof d.level_context === "object" ? d.level_context : d;
    const stats = lc.stats && typeof lc.stats === "object" ? lc.stats : {};
    const cfg = lc.config && typeof lc.config === "object" ? lc.config : {};
    const checks = lc.checks && typeof lc.checks === "object" ? lc.checks : {};
    const softFailedSet = new Set<string>(Array.isArray(lc.soft_failed_checks) ? lc.soft_failed_checks : []);

    const confluence = safeNum(stats.near_confluence_score);
    const minConfluence = safeNum(cfg.min_confluence_score ?? lc.min_confluence_score);

    const checkItems = Object.entries(checks).map(([k, v]) => ({
      key: k,
      label: k.replace(/_/g, " "),
      passed: v === true,
      warning: v === false && softFailedSet.has(k),
      tooltip: CHECK_EXPLANATIONS[k] || "No detailed description available",
    }));
    checkItems.sort((a, b) => {
      const sortOrder = (item: any) => (!item.passed && !item.warning ? 0 : !item.passed && item.warning ? 1 : 2);
      if (sortOrder(a) !== sortOrder(b)) return sortOrder(a) - sortOrder(b);
      return a.label.localeCompare(b.label);
    });

    return (
      <div style={{ marginTop: 4 }}>
        <SectionLabel icon={<Layers size={10} />}>Kontext & Úrovne</SectionLabel>

        {strategy && (
          <div style={{ fontSize: "0.6rem", color: "var(--text-secondary)", marginBottom: 4, fontWeight: 600 }}>
            {strategy}
          </div>
        )}

        <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: "2px 0", marginBottom: 6 }}>
          {confluence != null && (
            <MiniBar
              label="Confluence Score"
              value={confluence}
              max={Math.max(confluence, minConfluence || 1, 2)}
              threshold={minConfluence}
              suffix=""
              showThresholdLine
            />
          )}
          {stats.volume_ratio != null && (
            <MiniBar
              label="Volume Ratio"
              value={safeNum(stats.volume_ratio)}
              max={Math.max(safeNum(stats.volume_ratio) || 0, 1.5)}
              threshold={safeNum(cfg.min_volume_ratio)}
              suffix="x"
              showThresholdLine
            />
          )}
          {stats.recent_touches != null && <MiniBar label="Recent Touches" value={safeNum(stats.recent_touches)} max={10} suffix="" />}
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "3px 6px" }}>
          {checkItems.map((item) => {
            const color = item.passed ? "var(--accent-green, #22c55e)" : item.warning ? "var(--accent-yellow, #eab308)" : "var(--accent-red, #ef4444)";
            const bg = item.passed ? "rgba(34, 197, 94, 0.08)" : item.warning ? "rgba(234, 179, 8, 0.08)" : "rgba(239, 68, 68, 0.08)";
            const border = item.passed ? "rgba(34, 197, 94, 0.18)" : item.warning ? "rgba(234, 179, 8, 0.18)" : "rgba(239, 68, 68, 0.18)";
            const icon = item.passed ? "\u2713" : item.warning ? "\u26A0" : "\u2717";

            return (
              <div
                key={item.key}
                title={item.tooltip}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 3,
                  padding: "3px 5px",
                  borderRadius: 3,
                  fontSize: "0.52rem",
                  lineHeight: 1.2,
                  background: bg,
                  color,
                  border: `1px solid ${border}`,
                  cursor: "help",
                }}
              >
                <span style={{ fontSize: "0.55rem", fontWeight: 700 }}>{icon}</span>
                <span style={{ whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", fontWeight: item.passed ? 500 : 600 }}>
                  {item.label}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  if (gate === "threshold" || gate === "cross_asset_headwind") {
    const score = safeNum(d.combined_score) ?? safeNum(d.combined_norm_0_100);
    const thr = safeNum(d.threshold_used) ?? safeNum(d.trade_gate_threshold);
    const stratScore = safeNum(d.strategy_score);
    const flowScore = safeNum(d.flow_score);
    const reasoning = typeof d.reasoning === "string" ? d.reasoning : null;
    const todBoost = safeNum(d.tod_threshold_boost);
    const hwBoost = safeNum(d.headwind_threshold_boost);
    const thrReason = typeof d.threshold_used_reason === "string" ? d.threshold_used_reason : null;
    const isHeadwind = gate === "cross_asset_headwind";
    const direction = resolveDirectionFromRejection(d);
    const isLong = direction === "bullish";
    const scoreGap = score != null && thr != null ? score - thr : null;
    const gapAbs = scoreGap != null ? Math.abs(scoreGap) : null;
    const progressPct = score != null && thr != null && thr > 0 ? Math.max(0, Math.min(120, (score / thr) * 100)) : null;

    const scorePassed = score != null && thr != null && score >= thr;
    const scoreColor = scorePassed ? "var(--accent-green, #22c55e)" : "var(--accent-red, #ef4444)";

    return (
      <div style={{ marginTop: 4 }}>
        <SectionLabel icon={<BarChart2 size={10} />}>Bodové Hodnotenie (Score)</SectionLabel>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: 6, marginBottom: 6 }}>
          <div style={{ background: "rgba(148, 163, 184, 0.08)", border: "1px solid rgba(148, 163, 184, 0.2)", borderRadius: 4, padding: "4px 6px" }}>
            <div style={{ fontSize: "0.5rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.04em" }}>Potrebné</div>
            <div style={{ fontSize: "0.72rem", fontWeight: 700, color: "var(--text-primary)", fontVariantNumeric: "tabular-nums" }}>
              {thr != null ? thr.toFixed(1) : "—"}
            </div>
          </div>
          <div style={{ background: "rgba(148, 163, 184, 0.08)", border: "1px solid rgba(148, 163, 184, 0.2)", borderRadius: 4, padding: "4px 6px" }}>
            <div style={{ fontSize: "0.5rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.04em" }}>Mal som</div>
            <div style={{ fontSize: "0.72rem", fontWeight: 700, color: scoreColor, fontVariantNumeric: "tabular-nums" }}>
              {score != null ? score.toFixed(1) : "—"}
            </div>
          </div>
          <div style={{ background: "rgba(148, 163, 184, 0.08)", border: "1px solid rgba(148, 163, 184, 0.2)", borderRadius: 4, padding: "4px 6px" }}>
            <div style={{ fontSize: "0.5rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.04em" }}>{scoreGap != null && scoreGap >= 0 ? "Nad prahom" : "Chýba"}</div>
            <div style={{ fontSize: "0.72rem", fontWeight: 700, color: scoreGap != null && scoreGap >= 0 ? "var(--accent-green, #22c55e)" : "var(--accent-red, #ef4444)", fontVariantNumeric: "tabular-nums" }}>
              {gapAbs != null ? `${scoreGap != null && scoreGap >= 0 ? "+" : "-"}${gapAbs.toFixed(1)}` : "—"}
            </div>
          </div>
        </div>
        {(progressPct != null || direction != null) && (
          <div style={{ marginBottom: 6 }}>
            {progressPct != null && (
              <div style={{ position: "relative", height: 6, borderRadius: 4, background: "var(--bg-tertiary, rgba(255,255,255,0.06))", overflow: "hidden", marginBottom: 4 }}>
                <div
                  style={{
                    height: "100%",
                    width: `${Math.min(100, progressPct)}%`,
                    background: scorePassed ? "var(--accent-green, #22c55e)" : "var(--accent-red, #ef4444)",
                    opacity: 0.85,
                  }}
                />
              </div>
            )}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 6 }}>
              <span style={{ fontSize: "0.52rem", color: "var(--text-muted)" }}>
                Plnenie vstupného prahu: {progressPct != null ? `${progressPct.toFixed(0)}%` : "—"}
              </span>
              {direction && (
                <span
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 4,
                    padding: "1px 6px",
                    borderRadius: 3,
                    fontSize: "0.55rem",
                    fontWeight: 700,
                    background: isLong ? "rgba(34, 197, 94, 0.12)" : "rgba(239, 68, 68, 0.12)",
                    color: isLong ? "var(--accent-green, #22c55e)" : "var(--accent-red, #ef4444)",
                    border: `1px solid ${isLong ? "rgba(34, 197, 94, 0.25)" : "rgba(239, 68, 68, 0.25)"}`,
                  }}
                >
                  {isLong ? "▲ LONG" : "▼ SHORT"}
                </span>
              )}
            </div>
          </div>
        )}
        <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: "2px 0", marginBottom: 6 }}>
          {score != null && thr != null && (
            <MiniBar
              label={isHeadwind ? "Skóre po korekcii" : "Celkové skóre (Combined)"}
              value={score}
              max={Math.max(score, thr, 100)}
              threshold={thr}
              suffix=""
              showThresholdLine
            />
          )}
          {stratScore != null && <MiniBar label="Stratégia (Strategy Score)" value={stratScore} max={100} suffix="" />}
          {flowScore != null && <MiniBar label="Order Flow Score" value={flowScore} max={100} suffix="" />}
        </div>

        {(todBoost != null || hwBoost != null || thrReason) && (
          <div style={{ display: "flex", gap: "6px", flexWrap: "wrap", fontSize: "0.52rem", color: "var(--text-muted)", marginBottom: 4, background: "rgba(0,0,0,0.1)", padding: "4px 6px", borderRadius: 4 }}>
            <span style={{ fontWeight: 600 }}>Úpravy Tresholdov:</span>
            {todBoost != null && todBoost !== 0 && (
              <span title="Úprava kvôli času obchodovania (Time of Day)" style={{ color: todBoost > 0 ? "var(--accent-red, #ef4444)" : "var(--accent-green, #22c55e)", cursor: "help" }}>
                ToD {todBoost > 0 ? "+" : ""}
                {todBoost.toFixed(0)}
              </span>
            )}
            {hwBoost != null && hwBoost !== 0 && (
              <span title="Korekcia kvôli protivetru (Headwind)" style={{ color: "var(--accent-red, #ef4444)", cursor: "help" }}>
                Headwind +{hwBoost.toFixed(1)}
              </span>
            )}
            {thrReason && <span style={{ fontStyle: "italic" }}>({thrReason})</span>}
          </div>
        )}

        {reasoning && <FormattedReasoning reasoning={reasoning} />}
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
