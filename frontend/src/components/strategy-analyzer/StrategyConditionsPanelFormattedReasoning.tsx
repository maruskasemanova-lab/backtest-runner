interface StrategyConditionsPanelFormattedReasoningProps {
  reasoning: string;
}

interface EvidenceItem {
  type: string;
  name: string;
  dir: string;
  strength: string;
  cal: string;
  strengthNum: number | null;
  calNum: number | null;
  points: number | null;
}

function parseFiniteNumber(raw: string): number | null {
  const n = Number(String(raw).trim());
  return Number.isFinite(n) ? n : null;
}

function parseEvidenceItems(evidencePart: string | undefined): EvidenceItem[] {
  const items: EvidenceItem[] = [];
  if (!evidencePart) return items;

  const bracketContent = evidencePart.match(/\[(.+)\]/)?.[1];
  if (!bracketContent) return items;

  // Example: feature:rsi_oversold(b,70→0.57)
  const itemRegex = /(\w+):(\w+)\(([^,]+),([^→]+)→([^)]+)\)/g;
  let m: RegExpExecArray | null;
  while ((m = itemRegex.exec(bracketContent)) !== null) {
    const strengthNum = parseFiniteNumber(m[4]);
    const calNum = parseFiniteNumber(m[5]);
    items.push({
      type: m[1],
      name: m[2].replace(/_/g, " "),
      dir: m[3],
      strength: m[4],
      cal: m[5],
      strengthNum,
      calNum,
      points: calNum != null ? calNum * 100 : null,
    });
  }

  return items;
}

function parseEnsembleMetric(ensemblePart: string | undefined, key: "score" | "thresh"): number | null {
  if (!ensemblePart) return null;
  const m = ensemblePart.match(new RegExp(`${key}=([-+]?\\d+(?:\\.\\d+)?)`, "i"));
  if (!m) return null;
  return parseFiniteNumber(m[1]);
}

export function StrategyConditionsPanelFormattedReasoning({
  reasoning,
}: StrategyConditionsPanelFormattedReasoningProps) {
  // Backend format:
  // "Evidence: [type:name(dir,str→cal), ...] | Ensemble: score=X thresh=Y confirming=A/B | EXECUTE/SKIP"
  const parts = reasoning.split(" | ");
  const evidencePart = parts.find((p) => p.startsWith("Evidence:"));
  const ensemblePart = parts.find((p) => p.startsWith("Ensemble:"));
  const verdict = parts.find(
    (p) => p === "EXECUTE" || p === "SKIP" || p.startsWith("SKIP") || p.startsWith("EXECUTE"),
  );

  const evidenceItems = parseEvidenceItems(evidencePart);
  const pointsItems = evidenceItems.filter((ev): ev is EvidenceItem & { points: number } => ev.points != null);
  const scoreFromEnsemble = parseEnsembleMetric(ensemblePart, "score");
  const thresholdFromEnsemble = parseEnsembleMetric(ensemblePart, "thresh");
  const pointsAverage =
    pointsItems.length > 0
      ? pointsItems.reduce((acc, ev) => acc + ev.points, 0) / pointsItems.length
      : null;

  const dirLabel = (d: string) => {
    if (d === "b" || d === "bullish") return { arrow: "▲", color: "var(--accent-green, #22c55e)" };
    if (d === "s" || d === "bearish") return { arrow: "▼", color: "var(--accent-red, #ef4444)" };
    return { arrow: "●", color: "var(--text-muted)" };
  };

  const isExecute = verdict?.startsWith("EXECUTE");

  return (
    <div style={{ marginTop: 3 }}>
      {verdict && (
        <div
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 3,
            padding: "1px 6px",
            borderRadius: 3,
            fontSize: "0.58rem",
            fontWeight: 700,
            background: isExecute ? "rgba(34, 197, 94, 0.12)" : "rgba(239, 68, 68, 0.08)",
            color: isExecute ? "var(--accent-green, #22c55e)" : "var(--accent-red, #ef4444)",
            border: `1px solid ${isExecute ? "rgba(34, 197, 94, 0.25)" : "rgba(239, 68, 68, 0.2)"}`,
            marginBottom: 3,
          }}
        >
          {isExecute ? "✓ EXECUTE" : "✗ SKIP"}
          {verdict.includes("no aligned strategy signal") && (
            <span style={{ fontWeight: 500, opacity: 0.8 }}> (no aligned signal)</span>
          )}
        </div>
      )}

      {evidenceItems.length > 0 && (
        <div style={{ display: "flex", gap: 3, flexWrap: "wrap", marginBottom: 2 }}>
          {evidenceItems.map((ev, i) => {
            const d = dirLabel(ev.dir);
            return (
              <span
                key={`${ev.type}-${ev.name}-${i}`}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 2,
                  padding: "1px 4px",
                  borderRadius: 2,
                  fontSize: "0.50rem",
                  lineHeight: 1.5,
                  background: "rgba(148, 163, 184, 0.06)",
                  border: "1px solid rgba(148, 163, 184, 0.12)",
                  color: "var(--text-secondary)",
                }}
                title={`${ev.type}: ${ev.name} | dir: ${ev.dir} | strength: ${ev.strength} | calibrated: ${ev.cal}`}
              >
                <span style={{ color: d.color, fontSize: "0.48rem" }}>{d.arrow}</span>
                <span style={{ fontWeight: 600 }}>{ev.name}</span>
                <span style={{ opacity: 0.6 }}>
                  {ev.strength}→{ev.cal}
                </span>
              </span>
            );
          })}
        </div>
      )}

      {pointsItems.length > 0 && (
        <div
          style={{
            marginTop: 4,
            marginBottom: 4,
            padding: "5px 6px",
            borderRadius: 4,
            border: "1px solid rgba(148, 163, 184, 0.18)",
            background: "rgba(148, 163, 184, 0.06)",
          }}
        >
          <div
            style={{
              fontSize: "0.52rem",
              color: "var(--text-secondary)",
              fontWeight: 700,
              marginBottom: 4,
              textTransform: "uppercase",
              letterSpacing: "0.03em",
            }}
          >
            Skladba Skore
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: 4 }}>
            {pointsItems.map((ev, i) => {
              const d = dirLabel(ev.dir);
              const width = Math.max(0, Math.min(100, ev.points));
              return (
                <div key={`breakdown-${ev.type}-${ev.name}-${i}`}>
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      gap: 6,
                      marginBottom: 2,
                    }}
                  >
                    <span
                      style={{
                        fontSize: "0.52rem",
                        color: "var(--text-secondary)",
                        display: "inline-flex",
                        alignItems: "center",
                        gap: 3,
                        minWidth: 0,
                        flex: 1,
                      }}
                    >
                      <span style={{ color: d.color, fontSize: "0.5rem" }}>{d.arrow}</span>
                      <span style={{ whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                        {ev.name}
                      </span>
                    </span>
                    <span
                      style={{
                        fontSize: "0.52rem",
                        color: "var(--text-primary)",
                        fontWeight: 700,
                        fontVariantNumeric: "tabular-nums",
                      }}
                    >
                      {ev.points.toFixed(1)}
                    </span>
                  </div>

                  <div
                    style={{
                      position: "relative",
                      height: 5,
                      borderRadius: 3,
                      overflow: "hidden",
                      background: "var(--bg-tertiary, rgba(255,255,255,0.06))",
                    }}
                    title={`${ev.name}: raw=${ev.strengthNum ?? ev.strength}, calibrated=${ev.calNum ?? ev.cal}, points=${ev.points.toFixed(1)}`}
                  >
                    <div
                      style={{
                        width: `${width}%`,
                        height: "100%",
                        borderRadius: 3,
                        background: d.color,
                        opacity: 0.85,
                      }}
                    />
                  </div>
                </div>
              );
            })}
          </div>

          {(pointsAverage != null || scoreFromEnsemble != null || thresholdFromEnsemble != null) && (
            <div
              style={{
                marginTop: 5,
                display: "flex",
                gap: 8,
                flexWrap: "wrap",
                fontSize: "0.5rem",
                color: "var(--text-muted)",
              }}
            >
              {pointsAverage != null && (
                <span>
                  Priemer komponentov:{" "}
                  <span style={{ color: "var(--text-primary)", fontVariantNumeric: "tabular-nums" }}>
                    {pointsAverage.toFixed(1)}
                  </span>
                </span>
              )}
              {scoreFromEnsemble != null && (
                <span>
                  Ensemble score:{" "}
                  <span style={{ color: "var(--text-primary)", fontVariantNumeric: "tabular-nums" }}>
                    {scoreFromEnsemble.toFixed(1)}
                  </span>
                </span>
              )}
              {thresholdFromEnsemble != null && (
                <span>
                  Threshold:{" "}
                  <span style={{ color: "var(--text-primary)", fontVariantNumeric: "tabular-nums" }}>
                    {thresholdFromEnsemble.toFixed(1)}
                  </span>
                </span>
              )}
            </div>
          )}
        </div>
      )}

      {ensemblePart && (
        <div style={{ fontSize: "0.50rem", color: "var(--text-muted)", lineHeight: 1.4 }}>{ensemblePart}</div>
      )}
    </div>
  );
}
