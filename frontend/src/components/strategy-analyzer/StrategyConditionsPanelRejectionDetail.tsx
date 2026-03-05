import type { ReactNode } from "react";
import { Layers } from "lucide-react";

import { StrategyConditionsPanelFormattedReasoning as FormattedReasoning } from "./StrategyConditionsPanelFormattedReasoning";
import {
  MiniBar,
  SectionLabel,
  cx,
  safeNum,
} from "./StrategyConditionsPanelShared";

const CHECK_EXPLANATIONS: Record<string, string> = {
  rvol_minimum: "Relatívny objem (RVOL) presahuje minimálnu hranicu pre vstup",
  near_tested_level: "Cena je optimálne blízko testovanej úrovne (level)",
  minimum_confluence_score:
    "Dostatočná súhra viacerých indikátorov (confluence)",
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
  rotation_prefers_non_trending_poc_migration:
    "Presun POC (Point of Control) nenaznačuje silný trend proti rotácii",
  gap_fill_bias_aligned: "Smerovanie k vyplneniu gapu súhlasí so signálom",
};

function resolveDirectionToken(raw: unknown): "bullish" | "bearish" | null {
  if (raw == null) return null;
  const token = String(raw).trim().toLowerCase();
  if (!token) return null;
  if (
    token === "buy" ||
    token === "long" ||
    token === "bullish" ||
    token.includes("bullish")
  ) {
    return "bullish";
  }
  if (
    token === "sell" ||
    token === "short" ||
    token === "bearish" ||
    token.includes("bearish")
  ) {
    return "bearish";
  }
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

function ToneNote({
  strategy,
  children,
}: {
  strategy?: string | null;
  children: ReactNode;
}) {
  return (
    <div className="sa-detail-note">
      {strategy && <span className="sa-detail-note__strong">{strategy}</span>}
      {strategy && " · "}
      {children}
    </div>
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
    const alignedKeys: string[] = Array.isArray(d.aligned_source_keys)
      ? d.aligned_source_keys
      : [];
    const nonAlignedSources: any[] = Array.isArray(d.non_aligned_source_keys)
      ? d.non_aligned_source_keys
      : [];
    const signalDir =
      typeof d.signal_direction === "string"
        ? d.signal_direction.toLowerCase()
        : null;

    return (
      <div className="sa-detail-block">
        <div className="sa-detail-row">
          <span className="sa-detail-meta">
            {strategy && (
              <span className="sa-detail-note__strong">{strategy}</span>
            )}
          </span>
          <span className="sa-detail-value is-danger">
            {actual}/{required} ({pct.toFixed(0)}%)
          </span>
        </div>
        <div className="sa-track">
          <div
            className={cx(
              "sa-track__fill",
              pct >= 100 ? "is-success" : "is-danger",
            )}
            style={{ width: `${pct}%` }}
          />
          <div
            className="sa-track__threshold is-end"
            title={`Required: ${required}`}
          />
        </div>
        {(alignedKeys.length > 0 || nonAlignedSources.length > 0) && (
          <div className="sa-tag-row is-spaced">
            {alignedKeys.map((key) => (
              <span key={key} className="sa-pill is-success is-compact">
                <span className="sa-pill__icon">✓</span>
                {key.replace(/_/g, " ")}
              </span>
            ))}
            {nonAlignedSources.map((source) => {
              const key = String(source?.key || "");
              const direction = String(source?.direction || "").toLowerCase();
              const isOpposing = Boolean(
                direction &&
                signalDir &&
                direction !== signalDir &&
                direction !== "neutral",
              );
              return (
                <span
                  key={key}
                  className={cx(
                    "sa-pill",
                    isOpposing ? "is-danger" : "is-neutral",
                    "is-compact",
                  )}
                >
                  <span className="sa-pill__icon">
                    {isOpposing ? "✗" : "–"}
                  </span>
                  {key.replace(/_/g, " ")}
                  {direction && (
                    <span className="sa-pill__meta-inline">({direction})</span>
                  )}
                </span>
              );
            })}
          </div>
        )}
      </div>
    );
  }

  if (gate === "l2_confirmation") {
    const metrics = d.l2_metrics;
    const reason =
      metrics &&
      typeof metrics === "object" &&
      typeof metrics.reason === "string"
        ? metrics.reason
        : null;
    return (
      <ToneNote strategy={strategy}>
        L2 flow not confirming{reason ? `: ${reason}` : ""}
      </ToneNote>
    );
  }

  if (gate === "tcbbo_confirmation") {
    const metrics = d.tcbbo_metrics;
    const reason =
      metrics &&
      typeof metrics === "object" &&
      typeof metrics.reason === "string"
        ? metrics.reason
        : null;
    return (
      <ToneNote strategy={strategy}>
        TCBBO options flow not aligned{reason ? `: ${reason}` : ""}
      </ToneNote>
    );
  }

  if (gate === "mu_choppy_filter") {
    return (
      <ToneNote>
        Choppy regime block{d.micro_regime ? ` (${d.micro_regime})` : ""}
      </ToneNote>
    );
  }

  if (gate === "cost_aware_sweep") {
    const risk = safeNum(d.risk_pct);
    const min = safeNum(d.min_required);
    return (
      <ToneNote>
        Sweep risk too low{risk != null ? `: ${(risk * 100).toFixed(2)}%` : ""}
        {min != null ? ` (min ${(min * 100).toFixed(0)}%)` : ""}
      </ToneNote>
    );
  }

  if (gate === "intraday_levels_entry_quality" || gate === "level_quality") {
    const levelContext =
      d.level_context && typeof d.level_context === "object"
        ? d.level_context
        : d;
    const stats =
      levelContext.stats && typeof levelContext.stats === "object"
        ? levelContext.stats
        : {};
    const config =
      levelContext.config && typeof levelContext.config === "object"
        ? levelContext.config
        : {};
    const checks =
      levelContext.checks && typeof levelContext.checks === "object"
        ? levelContext.checks
        : {};
    const softFailedSet = new Set<string>(
      Array.isArray(levelContext.soft_failed_checks)
        ? levelContext.soft_failed_checks
        : [],
    );

    const confluence = safeNum(stats.near_confluence_score);
    const minConfluence = safeNum(
      config.min_confluence_score ?? levelContext.min_confluence_score,
    );

    const checkItems = Object.entries(checks).map(([key, value]) => ({
      key,
      label: key.replace(/_/g, " "),
      passed: value === true,
      warning: value === false && softFailedSet.has(key),
      tooltip: CHECK_EXPLANATIONS[key] || "No detailed description available",
    }));

    checkItems.sort((a, b) => {
      const sortOrder = (item: { passed: boolean; warning: boolean }) =>
        !item.passed && !item.warning
          ? 0
          : !item.passed && item.warning
            ? 1
            : 2;
      if (sortOrder(a) !== sortOrder(b)) return sortOrder(a) - sortOrder(b);
      return a.label.localeCompare(b.label);
    });

    return (
      <div className="sa-detail-block is-top-spaced">
        <SectionLabel icon={<Layers size={10} />}>
          Kontext & Úrovne
        </SectionLabel>

        {strategy && <div className="sa-detail-heading">{strategy}</div>}

        <div className="sa-grid-single is-spaced-lg">
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
              threshold={safeNum(config.min_volume_ratio)}
              suffix="x"
              showThresholdLine
            />
          )}
          {stats.recent_touches != null && (
            <MiniBar
              label="Recent Touches"
              value={safeNum(stats.recent_touches)}
              max={10}
              suffix=""
            />
          )}
        </div>

        <div className="sa-detail-grid">
          {checkItems.map((item) => {
            const toneClass = item.passed
              ? "is-success"
              : item.warning
                ? "is-warning"
                : "is-danger";
            const icon = item.passed ? "✓" : item.warning ? "⚠" : "✗";

            return (
              <div
                key={item.key}
                title={item.tooltip}
                className={cx("sa-detail-card", toneClass)}
              >
                <span className="sa-detail-card__icon">{icon}</span>
                <span
                  className={cx(
                    "sa-detail-card__label",
                    !item.passed && "is-strong",
                  )}
                >
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
    const threshold =
      safeNum(d.threshold_used) ?? safeNum(d.trade_gate_threshold);
    const reasoning = typeof d.reasoning === "string" ? d.reasoning : null;
    const todBoost = safeNum(d.tod_threshold_boost);
    const headwindBoost = safeNum(d.headwind_threshold_boost);
    const thresholdReason =
      typeof d.threshold_used_reason === "string"
        ? d.threshold_used_reason
        : null;
    const fixedThresholdMode = Boolean(
      thresholdReason && thresholdReason.toLowerCase().startsWith("fixed("),
    );
    const isHeadwind = gate === "cross_asset_headwind";
    const direction = resolveDirectionFromRejection(d);
    const isLong = direction === "bullish";
    const scoreGap =
      score != null && threshold != null ? score - threshold : null;
    const scorePassed =
      score != null && threshold != null && score >= threshold;

    return (
      <div className="sa-detail-block is-top-spaced">
        <div className="sa-inline-wrap is-spaced-md">
          {direction && (
            <span
              className={cx("sa-pill", isLong ? "is-success" : "is-danger")}
            >
              {isLong ? "▲ LONG" : "▼ SHORT"}
            </span>
          )}
          {score != null && threshold != null && (
            <span
              className={cx(
                "sa-detail-value",
                scorePassed ? "is-success" : "is-danger",
              )}
            >
              {score.toFixed(1)} / {threshold.toFixed(0)} thr
              {scoreGap != null &&
                ` (${scoreGap >= 0 ? "+" : ""}${scoreGap.toFixed(1)})`}
            </span>
          )}
          {isHeadwind && (
            <span className="sa-detail-hint">headwind adjusted</span>
          )}
        </div>

        {(todBoost != null || headwindBoost != null || thresholdReason) && (
          <div className="sa-adjustment-row">
            <span className="sa-adjustment-row__title">Thr adjustments:</span>
            {!fixedThresholdMode && todBoost != null && todBoost !== 0 && (
              <span
                title="Time of Day adjustment"
                className={cx(
                  "sa-adjustment-row__item",
                  todBoost > 0 ? "is-danger" : "is-success",
                )}
              >
                ToD {todBoost > 0 ? "+" : ""}
                {todBoost.toFixed(0)}
              </span>
            )}
            {!fixedThresholdMode &&
              headwindBoost != null &&
              headwindBoost !== 0 && (
                <span
                  title="Headwind correction"
                  className="sa-adjustment-row__item is-danger"
                >
                  HW +{headwindBoost.toFixed(1)}
                </span>
              )}
            {fixedThresholdMode && (
              <span className="sa-adjustment-row__item is-success">
                fixed threshold active
              </span>
            )}
            {thresholdReason && (
              <span className="sa-adjustment-row__meta">
                ({thresholdReason})
              </span>
            )}
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
  return <div className="sa-detail-note">{fallbackParts.join(" · ")}</div>;
}
