interface StrategyConditionsPanelFormattedReasoningProps {
  reasoning: string;
}

export function StrategyConditionsPanelFormattedReasoning({
  reasoning,
}: StrategyConditionsPanelFormattedReasoningProps) {
  // Parse backend reasoning format:
  // "Evidence: [type:name(dir,str→cal), ...] | Ensemble: score=X thresh=Y confirming=A/B | EXECUTE/SKIP"
  const parts = reasoning.split(" | ");
  const evidencePart = parts.find((p) => p.startsWith("Evidence:"));
  const ensemblePart = parts.find((p) => p.startsWith("Ensemble:"));
  const verdict = parts.find(
    (p) => p === "EXECUTE" || p === "SKIP" || p.startsWith("SKIP") || p.startsWith("EXECUTE"),
  );

  // Parse evidence sources from "[type:name(dir,str→cal), ...]"
  const evidenceItems: Array<{ type: string; name: string; dir: string; strength: string; cal: string }> = [];
  if (evidencePart) {
    const bracketContent = evidencePart.match(/\[(.+)\]/)?.[1];
    if (bracketContent) {
      // Match patterns like: feature:rsi_oversold(b,70→0.57)
      const itemRegex = /(\w+):(\w+)\(([^,]+),([^→]+)→([^)]+)\)/g;
      let m: RegExpExecArray | null;
      while ((m = itemRegex.exec(bracketContent)) !== null) {
        evidenceItems.push({
          type: m[1],
          name: m[2].replace(/_/g, " "),
          dir: m[3],
          strength: m[4],
          cal: m[5],
        });
      }
    }
  }

  const dirLabel = (d: string) => {
    if (d === "b" || d === "bullish") return { arrow: "▲", color: "var(--accent-green, #22c55e)", label: "BUY" };
    if (d === "s" || d === "bearish") return { arrow: "▼", color: "var(--accent-red, #ef4444)", label: "SELL" };
    return { arrow: "●", color: "var(--text-muted)", label: "—" };
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

      {ensemblePart && (
        <div style={{ fontSize: "0.50rem", color: "var(--text-muted)", lineHeight: 1.4 }}>{ensemblePart}</div>
      )}
    </div>
  );
}
