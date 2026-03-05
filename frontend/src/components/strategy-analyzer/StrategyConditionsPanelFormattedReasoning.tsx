import { cx } from "./StrategyConditionsPanelShared";

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

type ToneClass = "is-success" | "is-danger" | "is-muted";

function parseFiniteNumber(raw: string): number | null {
  const n = Number(String(raw).trim());
  return Number.isFinite(n) ? n : null;
}

function parseEvidenceItems(evidencePart: string | undefined): EvidenceItem[] {
  const items: EvidenceItem[] = [];
  if (!evidencePart) return items;

  const bracketContent = evidencePart.match(/\[(.+)\]/)?.[1];
  if (!bracketContent) return items;

  const itemRegex = /(\w+):(\w+)\(([^,]+),([^→]+)→([^)]+)\)/g;
  let match: RegExpExecArray | null;
  while ((match = itemRegex.exec(bracketContent)) !== null) {
    const strengthNum = parseFiniteNumber(match[4]);
    const calNum = parseFiniteNumber(match[5]);
    items.push({
      type: match[1],
      name: match[2].replace(/_/g, " "),
      dir: match[3],
      strength: match[4],
      cal: match[5],
      strengthNum,
      calNum,
      points: calNum != null ? calNum * 100 : null,
    });
  }

  return items;
}

function parseEnsembleMetric(
  ensemblePart: string | undefined,
  key: "score" | "thresh",
): number | null {
  if (!ensemblePart) return null;
  const match = ensemblePart.match(
    new RegExp(`${key}=([-+]?\\d+(?:\\.\\d+)?)`, "i"),
  );
  if (!match) return null;
  return parseFiniteNumber(match[1]);
}

function directionMeta(direction: string): {
  arrow: string;
  toneClass: ToneClass;
} {
  if (direction === "b" || direction === "bullish")
    return { arrow: "▲", toneClass: "is-success" };
  if (direction === "s" || direction === "bearish")
    return { arrow: "▼", toneClass: "is-danger" };
  return { arrow: "●", toneClass: "is-muted" };
}

export function StrategyConditionsPanelFormattedReasoning({
  reasoning,
}: StrategyConditionsPanelFormattedReasoningProps) {
  const parts = reasoning.split(" | ");
  const evidencePart = parts.find((part) => part.startsWith("Evidence:"));
  const ensemblePart = parts.find((part) => part.startsWith("Ensemble:"));
  const verdict = parts.find(
    (part) =>
      part === "EXECUTE" ||
      part === "SKIP" ||
      part.startsWith("SKIP") ||
      part.startsWith("EXECUTE"),
  );

  const evidenceItems = parseEvidenceItems(evidencePart);
  const pointsItems = evidenceItems.filter(
    (item): item is EvidenceItem & { points: number } => item.points != null,
  );
  const scoreFromEnsemble = parseEnsembleMetric(ensemblePart, "score");
  const thresholdFromEnsemble = parseEnsembleMetric(ensemblePart, "thresh");
  const pointsAverage =
    pointsItems.length > 0
      ? pointsItems.reduce((total, item) => total + item.points, 0) /
        pointsItems.length
      : null;

  const isExecute = verdict?.startsWith("EXECUTE");

  return (
    <div className="sa-reasoning">
      {verdict && (
        <div
          className={cx(
            "sa-pill",
            isExecute ? "is-success" : "is-danger",
            "is-wide",
          )}
        >
          {isExecute ? "✓ EXECUTE" : "✗ SKIP"}
          {verdict.includes("no aligned strategy signal") && (
            <span className="sa-pill__subtle">(no aligned signal)</span>
          )}
        </div>
      )}

      {evidenceItems.length > 0 && (
        <div className="sa-tag-row">
          {evidenceItems.map((item, index) => {
            const direction = directionMeta(item.dir);
            return (
              <span
                key={`${item.type}-${item.name}-${index}`}
                className="sa-pill is-neutral is-compact"
                title={`${item.type}: ${item.name} | dir: ${item.dir} | strength: ${item.strength} | calibrated: ${item.cal}`}
              >
                <span className={cx("sa-pill__icon", direction.toneClass)}>
                  {direction.arrow}
                </span>
                <span className="sa-pill__label">{item.name}</span>
                <span className="sa-pill__meta-inline">
                  {item.strength}→{item.cal}
                </span>
              </span>
            );
          })}
        </div>
      )}

      {pointsItems.length > 0 && (
        <div className="sa-reasoning-card">
          <div className="sa-reasoning-card__title">Skladba Skore</div>
          <div className="sa-reasoning-list">
            {pointsItems.map((item, index) => {
              const direction = directionMeta(item.dir);
              const width = Math.max(0, Math.min(100, item.points));
              return (
                <div
                  key={`breakdown-${item.type}-${item.name}-${index}`}
                  className="sa-reasoning-item"
                >
                  <div className="sa-reasoning-item__header">
                    <span className="sa-reasoning-item__label">
                      <span
                        className={cx("sa-pill__icon", direction.toneClass)}
                      >
                        {direction.arrow}
                      </span>
                      <span className="sa-truncate">{item.name}</span>
                    </span>
                    <span className="sa-value-primary">
                      {item.points.toFixed(1)}
                    </span>
                  </div>
                  <div
                    className="sa-track"
                    title={`${item.name}: raw=${item.strengthNum ?? item.strength}, calibrated=${item.calNum ?? item.cal}, points=${item.points.toFixed(1)}`}
                  >
                    <div
                      className={cx("sa-track__fill", direction.toneClass)}
                      style={{ width: `${width}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>

          {(pointsAverage != null ||
            scoreFromEnsemble != null ||
            thresholdFromEnsemble != null) && (
            <div className="sa-reasoning-card__summary">
              {pointsAverage != null && (
                <span>
                  Priemer komponentov:{" "}
                  <span className="sa-value-primary">
                    {pointsAverage.toFixed(1)}
                  </span>
                </span>
              )}
              {scoreFromEnsemble != null && (
                <span>
                  Ensemble score:{" "}
                  <span className="sa-value-primary">
                    {scoreFromEnsemble.toFixed(1)}
                  </span>
                </span>
              )}
              {thresholdFromEnsemble != null && (
                <span>
                  Threshold:{" "}
                  <span className="sa-value-primary">
                    {thresholdFromEnsemble.toFixed(1)}
                  </span>
                </span>
              )}
            </div>
          )}
        </div>
      )}

      {ensemblePart && (
        <div className="sa-reasoning__ensemble">{ensemblePart}</div>
      )}
    </div>
  );
}
