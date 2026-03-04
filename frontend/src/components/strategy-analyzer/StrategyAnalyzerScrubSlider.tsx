import type { StrategyAnalyzerRangeScrubMeta } from "./types";

type Props = {
  rangeScrubMeta: StrategyAnalyzerRangeScrubMeta;
  focusSelectedRangeOffset: (nextOffset: number) => void;
  moveSelectedRangeByStep: (direction: -1 | 1) => void;
};

export default function StrategyAnalyzerScrubSlider({
  rangeScrubMeta,
  focusSelectedRangeOffset,
  moveSelectedRangeByStep,
}: Props) {
  if (!rangeScrubMeta || Number(rangeScrubMeta.progressedPoints || 0) <= 0) return null;

  return (
    <div
      data-webmcp="strategy-analyzer-scrub-slider"
      style={{
        borderTop: "1px solid var(--border-color)",
        padding: "0.65rem 0.85rem 0.75rem",
        display: "flex",
        flexDirection: "column",
        gap: "0.5rem",
        background:
          "linear-gradient(180deg, color-mix(in srgb, var(--bg-card) 92%, var(--accent-blue) 8%), var(--bg-card))",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: "0.75rem",
          flexWrap: "wrap",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", flexWrap: "wrap" }}>
          <span style={{ fontSize: "0.78rem", fontWeight: 700, color: "var(--text-secondary)" }}>
            WF progress slider
          </span>
          <span style={{ fontSize: "0.76rem", color: "var(--text-muted)" }}>
            {rangeScrubMeta.startLocal.replace("T", " ")} &rarr; {rangeScrubMeta.endLocal.replace("T", " ")}
          </span>
        </div>
        <div style={{ display: "inline-flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          <span style={{ fontSize: "0.76rem", color: "var(--text-muted)" }}>
            {rangeScrubMeta.targetLocal
              ? `${rangeScrubMeta.targetLocal.replace("T", " ")} (${Number(rangeScrubMeta.progressedPoints || 0) > 0 ? rangeScrubMeta.clampedOffset + 1 : 0}/${rangeScrubMeta.progressedPoints || 0} pts)`
              : `${rangeScrubMeta.progressedPoints || 0}/${rangeScrubMeta.progressedPoints || 0} pts`}
          </span>
          <span style={{ fontSize: "0.76rem", color: "var(--text-muted)" }}>
            Progress {Math.min(rangeScrubMeta.tradeTotalBars || 0, rangeScrubMeta.progressedBars)}/
            {rangeScrubMeta.tradeTotalBars || 0} ({Number(rangeScrubMeta.progressPct || 0).toFixed(1)}%)
          </span>
          {Number(rangeScrubMeta.estimatedPointsPerBar || 1) > 1 ? (
            <span style={{ fontSize: "0.76rem", color: "var(--text-muted)" }}>
              ~{Number(rangeScrubMeta.estimatedPointsPerBar || 1)} pts/bar
            </span>
          ) : null}
          {Number(rangeScrubMeta.sliderStepSeconds || 0) > 0 &&
          Number(rangeScrubMeta.sliderStepSeconds || 0) <= 6 ? (
            <span style={{ fontSize: "0.76rem", color: "var(--text-muted)" }}>
              Step ~{Number(rangeScrubMeta.sliderStepSeconds || 5).toFixed(0)}s
            </span>
          ) : null}
          <button
            type="button"
            className="btn btn-secondary"
            data-webmcp="strategy-analyzer-scrub-latest"
            onClick={() => focusSelectedRangeOffset(rangeScrubMeta.progressedMaxOffset)}
            disabled={rangeScrubMeta.clampedOffset >= rangeScrubMeta.progressedMaxOffset}
            style={{ padding: "2px 8px", fontSize: "0.72rem", fontWeight: 700 }}
            title="Jump slider to latest processed walking-forward bar"
          >
            Latest
          </button>
        </div>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
        <button
          type="button"
          className="btn btn-secondary"
          data-webmcp="strategy-analyzer-scrub-prev"
          onClick={() => moveSelectedRangeByStep(-1)}
          disabled={rangeScrubMeta.clampedOffset <= 0}
          style={{ padding: "4px 10px", fontSize: "0.78rem", fontWeight: 700 }}
          title={`Previous executed ${Number(rangeScrubMeta.sliderStepSeconds || 0) > 0 ? `~${Number(rangeScrubMeta.sliderStepSeconds).toFixed(0)}s` : "bar"} in selected range`}
        >
          ◀
        </button>
        <input
          type="range"
          data-webmcp="strategy-analyzer-scrub-range"
          min={0}
          max={rangeScrubMeta.fullMaxOffset}
          step={Math.max(1, Math.trunc(Number(rangeScrubMeta.sliderStepBars) || 1))}
          value={rangeScrubMeta.clampedOffset}
          onChange={(e) => focusSelectedRangeOffset(Number(e.target.value))}
          style={{
            flex: 1,
            minWidth: 120,
            accentColor: "var(--accent-blue, #3b82f6)",
            borderRadius: 999,
            background: `linear-gradient(to right,
              color-mix(in srgb, var(--accent-blue, #3b82f6) 88%, white 12%) 0%,
              color-mix(in srgb, var(--accent-blue, #3b82f6) 88%, white 12%) ${Number(rangeScrubMeta.enabledTrackPct || 0).toFixed(2)}%,
              color-mix(in srgb, var(--text-muted, #94a3b8) 24%, transparent) ${Number(rangeScrubMeta.enabledTrackPct || 0).toFixed(2)}%,
              color-mix(in srgb, var(--text-muted, #94a3b8) 24%, transparent) 100%)`,
          }}
          aria-label="Navigate walking-forward progress in selected range"
        />
        <button
          type="button"
          className="btn btn-secondary"
          data-webmcp="strategy-analyzer-scrub-next"
          onClick={() => moveSelectedRangeByStep(1)}
          disabled={rangeScrubMeta.clampedOffset >= rangeScrubMeta.progressedMaxOffset}
          style={{ padding: "4px 10px", fontSize: "0.78rem", fontWeight: 700 }}
          title={`Next executed ${Number(rangeScrubMeta.sliderStepSeconds || 0) > 0 ? `~${Number(rangeScrubMeta.sliderStepSeconds).toFixed(0)}s` : "bar"} in selected range`}
        >
          ▶
        </button>
      </div>
    </div>
  );
}
