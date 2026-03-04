import * as Slider from "@radix-ui/react-slider";
import { motion } from "framer-motion";
import { useCallback, useMemo, type PointerEvent as ReactPointerEvent } from "react";
import type { StrategyAnalyzerRangeScrubMeta } from "./types";

type Props = {
  rangeScrubMeta: StrategyAnalyzerRangeScrubMeta;
  focusSelectedRangeOffset: (nextOffset: number) => void;
  moveSelectedRangeByStep: (direction: -1 | 1) => void;
};

/**
 * Compact glass-morphism scrub slider bar.
 * Sits below the chart viewport with pointer isolation so
 * lightweight-charts gestures don't steal slider interactions.
 */
export default function StrategyAnalyzerScrubSlider({
  rangeScrubMeta,
  focusSelectedRangeOffset,
  moveSelectedRangeByStep,
}: Props) {
  if (!rangeScrubMeta || Number(rangeScrubMeta.progressedPoints || 0) <= 0) return null;

  const progressedBars = Math.max(0, Math.trunc(Number(rangeScrubMeta.progressedBars) || 0));
  const tradeTotalBarsRaw = Math.max(0, Math.trunc(Number(rangeScrubMeta.tradeTotalBars) || 0));
  const tradeTotalBars = tradeTotalBarsRaw > 0 ? tradeTotalBarsRaw : progressedBars;
  const progressedBarMaxOffset = Math.max(0, progressedBars - 1);
  const interactiveMax = Math.max(0, tradeTotalBars - 1);
  const progressPct = Math.max(0, Math.min(100, Number(rangeScrubMeta.progressPct) || 0));

  const { timelineOffsetByBarOffset, barOffsetByBarTime } = useMemo(() => {
    const lastTimelineOffsetByBarTime = new Map<number, number>();
    const timelinePoints = Array.isArray(rangeScrubMeta.timelinePoints) ? rangeScrubMeta.timelinePoints : [];
    for (let timelineOffset = 0; timelineOffset < timelinePoints.length; timelineOffset += 1) {
      const point = timelinePoints[timelineOffset];
      const barTime = Number(point?.runBar?.time ?? point?.barTime ?? point?.time);
      if (!Number.isFinite(barTime)) continue;
      // Overwrite with latest timeline point in the bar so scrubbing bar lands on its latest checkpoint.
      lastTimelineOffsetByBarTime.set(barTime, timelineOffset);
    }

    const timelineOffsetByBarOffsetNext = new Map<number, number>();
    const barOffsetByBarTimeNext = new Map<number, number>();
    const progressedTradeBars = Array.isArray(rangeScrubMeta.progressedTradeBars)
      ? rangeScrubMeta.progressedTradeBars
      : [];
    let fallbackTimelineOffset = 0;

    for (let barOffset = 0; barOffset <= progressedBarMaxOffset; barOffset += 1) {
      const bar = progressedTradeBars[barOffset];
      const barTime = Number(bar?.time);
      if (Number.isFinite(barTime)) {
        barOffsetByBarTimeNext.set(barTime, barOffset);
      }
      const exactTimelineOffset =
        Number.isFinite(barTime) && lastTimelineOffsetByBarTime.has(barTime)
          ? Number(lastTimelineOffsetByBarTime.get(barTime))
          : null;
      if (Number.isFinite(exactTimelineOffset)) {
        fallbackTimelineOffset = Math.max(0, Math.trunc(exactTimelineOffset as number));
      }
      timelineOffsetByBarOffsetNext.set(barOffset, fallbackTimelineOffset);
    }

    return {
      timelineOffsetByBarOffset: timelineOffsetByBarOffsetNext,
      barOffsetByBarTime: barOffsetByBarTimeNext,
    };
  }, [rangeScrubMeta.progressedTradeBars, rangeScrubMeta.timelinePoints, progressedBarMaxOffset]);

  const targetBarTime = Number(rangeScrubMeta.targetBar?.time);
  const interactiveValue = Number.isFinite(targetBarTime) && barOffsetByBarTime.has(targetBarTime)
    ? Math.max(0, Math.min(Number(barOffsetByBarTime.get(targetBarTime)), progressedBarMaxOffset))
    : Math.max(0, Math.min(progressedBarMaxOffset, Math.trunc(Number(rangeScrubMeta.clampedOffset) || 0)));

  const toProgressedOffset = useCallback(
    (rawBarOffset: number) => {
      if (progressedBars <= 0) return 0;
      const clampedBarOffset = Math.max(0, Math.min(Math.trunc(rawBarOffset), progressedBarMaxOffset));
      if (!timelineOffsetByBarOffset.has(clampedBarOffset)) {
        return Math.max(0, Math.trunc(Number(rangeScrubMeta.progressedMaxOffset) || 0));
      }
      return Math.max(0, Math.trunc(Number(timelineOffsetByBarOffset.get(clampedBarOffset)) || 0));
    },
    [progressedBars, progressedBarMaxOffset, rangeScrubMeta.progressedMaxOffset, timelineOffsetByBarOffset],
  );

  const handleSliderInput = (rawValue: string) => {
    focusSelectedRangeOffset(toProgressedOffset(Number(rawValue)));
  };

  const handleRadixValueChange = (values: number[]) => {
    handleSliderInput(String(Array.isArray(values) ? values[0] : 0));
  };

  const scrubLabel = "Navigate walking-forward progress in selected range";

  // Block pointer events from reaching the chart canvas below
  const isolatePointer = useCallback((e: ReactPointerEvent) => {
    e.stopPropagation();
  }, []);

  const pointLabel = tradeTotalBars > 0 ? `${interactiveValue + 1}/${tradeTotalBars}` : "";
  const pctLabel = `${Number(rangeScrubMeta.progressPct || 0).toFixed(0)}%`;

  const handleStepByBar = (direction: -1 | 1) => {
    if (progressedBars <= 0) {
      moveSelectedRangeByStep(direction);
      return;
    }
    const nextBarOffset = interactiveValue + direction;
    focusSelectedRangeOffset(toProgressedOffset(nextBarOffset));
  };
  const atLatestProcessed = interactiveValue >= progressedBarMaxOffset;

  return (
    <div
      data-webmcp="strategy-analyzer-scrub-slider"
      className="sa-scrub-overlay"
      onPointerDown={isolatePointer}
      onPointerMove={isolatePointer}
      onPointerUp={isolatePointer}
    >
      {/* Row: Prev | slider + progress | Next | Latest */}
      <div className="sa-scrub-overlay-row">
        <button
          type="button"
          className="sa-scrub-overlay-btn"
          data-webmcp="strategy-analyzer-scrub-prev"
          onClick={() => handleStepByBar(-1)}
          disabled={interactiveValue <= 0}
          title="Previous bar"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="15 18 9 12 15 6" />
          </svg>
        </button>

        <div className="sa-scrub-overlay-track-area">
          <Slider.Root
            data-webmcp="strategy-analyzer-scrub-range-radix"
            className="sa-scrub-overlay-slider"
            min={0}
            max={interactiveMax}
            step={1}
            value={[interactiveValue]}
            onValueChange={handleRadixValueChange}
            disabled={progressedBars <= 0}
          >
            <Slider.Track className="sa-scrub-overlay-slider-track">
              <Slider.Range className="sa-scrub-overlay-slider-range" />
            </Slider.Track>
            <Slider.Thumb className="sa-scrub-overlay-thumb-anchor" asChild aria-label={scrubLabel}>
              <motion.div
                initial={false}
                whileHover={{ scale: 1.3 }}
                whileTap={{ scale: 1.1 }}
                transition={{ type: "spring", stiffness: 500, damping: 28 }}
                className="sa-scrub-overlay-thumb"
              />
            </Slider.Thumb>
          </Slider.Root>
        </div>

        <button
          type="button"
          className="sa-scrub-overlay-btn"
          data-webmcp="strategy-analyzer-scrub-next"
          onClick={() => handleStepByBar(1)}
          disabled={atLatestProcessed}
          title="Next bar"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="9 18 15 12 9 6" />
          </svg>
        </button>

        <span className="sa-scrub-overlay-label">{pointLabel}</span>
        <span className="sa-scrub-overlay-pct">{pctLabel}</span>

        <button
          type="button"
          className="sa-scrub-overlay-btn sa-scrub-overlay-btn--latest"
          data-webmcp="strategy-analyzer-scrub-latest"
          onClick={() => focusSelectedRangeOffset(rangeScrubMeta.progressedMaxOffset)}
          disabled={atLatestProcessed}
          title="Jump to latest"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="13 17 18 12 13 7" />
            <polyline points="6 17 11 12 6 7" />
          </svg>
        </button>
      </div>

      {/* Hidden native range for programmatic/test access */}
      <input
        type="range"
        data-webmcp="strategy-analyzer-scrub-range"
        min={0}
        max={interactiveMax}
        step={1}
        value={interactiveValue}
        onInput={(e) => handleSliderInput(e.currentTarget.value)}
        onChange={(e) => handleSliderInput(e.currentTarget.value)}
        disabled={progressedBars <= 0}
        aria-label={scrubLabel}
        tabIndex={-1}
        aria-hidden="true"
        style={{
          position: "absolute",
          left: -9999,
          width: 1,
          height: 1,
          opacity: 0,
          pointerEvents: "none",
        }}
      />
    </div>
  );
}
