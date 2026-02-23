import { useRef, useState, useCallback, useEffect, type RefObject } from "react";

/**
 * Transparent overlay for drag-to-select a time range on a lightweight-charts chart.
 *
 * Instead of relying on coordinateToTime (which has coordinate-system issues),
 * we use timeToCoordinate on every bar to find which bars fall within the
 * dragged pixel region.  This is robust against zoom/pan and coordinate offsets.
 */

interface ChartRangeSelectorProps {
  enabled: boolean;
  chartRef: RefObject<{ getChart: () => any; getChartContainer: () => HTMLElement | null } | null>;
  bars: Array<{ time: number }>;
  onRangeSelected: (fromDate: string, toDate: string) => void;
  onSelectionClear: () => void;
  selectedFrom: string | null;
  selectedTo: string | null;
}

/** Convert unix-seconds to YYYY-MM-DDTHH:mm (local time, for datetime-local inputs). */
const tsToDateTime = (ts: number): string => {
  const d = new Date(ts * 1000);
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  const hh = String(d.getHours()).padStart(2, "0");
  const min = String(d.getMinutes()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}T${hh}:${min}`;
};

export default function ChartRangeSelector({
  enabled,
  chartRef,
  bars,
  onRangeSelected,
  onSelectionClear,
  selectedFrom,
  selectedTo,
}: ChartRangeSelectorProps) {
  const overlayRef = useRef<HTMLDivElement>(null);
  const isDraggingRef = useRef(false);
  const startXRef = useRef(0);
  const [dragRect, setDragRect] = useState<{ left: number; width: number } | null>(null);
  const [highlight, setHighlight] = useState<{ left: number; width: number } | null>(null);

  /* ── core helper: get pixel-X for a bar time ───────────────────── */
  const timeToX = useCallback(
    (barTime: number): number | null => {
      const chart = chartRef.current?.getChart?.();
      if (!chart) return null;
      const x = chart.timeScale().timeToCoordinate(barTime);
      return x != null ? x : null;
    },
    [chartRef]
  );

  /* ── find bars whose pixel-X falls within [px1, px2] ───────────── */
  const findBarsInPixelRange = useCallback(
    (px1: number, px2: number): { firstBar: { time: number }; lastBar: { time: number } } | null => {
      const chart = chartRef.current?.getChart?.();
      if (!chart || !bars.length) return null;

      const lo = Math.min(px1, px2);
      const hi = Math.max(px1, px2);
      let firstBar: { time: number } | null = null;
      let lastBar: { time: number } | null = null;

      for (const bar of bars) {
        const bx = chart.timeScale().timeToCoordinate(bar.time);
        if (bx == null) continue;
        if (bx >= lo && bx <= hi) {
          if (!firstBar) firstBar = bar;
          lastBar = bar;
        }
      }

      if (firstBar && lastBar) return { firstBar, lastBar };
      return null;
    },
    [chartRef, bars]
  );

  /* ── find first/last bar times for a datetime range (for highlight) ── */
  const findBarTimesForDateRange = useCallback(
    (fromDt: string, toDt: string): { firstTime: number; lastTime: number } | null => {
      if (!bars.length) return null;
      // fromDt/toDt are either "YYYY-MM-DDTHH:mm" or "YYYY-MM-DD"
      const fromTs = Date.parse(fromDt.includes("T") ? fromDt : fromDt + "T00:00:00") / 1000;
      const toTs = Date.parse(toDt.includes("T") ? toDt : toDt + "T23:59:59") / 1000;
      let firstTime: number | null = null;
      let lastTime: number | null = null;
      for (const bar of bars) {
        if (bar.time >= fromTs && bar.time <= toTs) {
          if (firstTime === null) firstTime = bar.time;
          lastTime = bar.time;
        }
      }
      if (firstTime != null && lastTime != null) return { firstTime, lastTime };
      return null;
    },
    [bars]
  );

  /* ── recalculate persistent highlight when chart scrolls/zooms ── */
  useEffect(() => {
    if (!selectedFrom || !selectedTo) {
      setHighlight(null);
      return;
    }

    const chart = chartRef.current?.getChart?.();
    if (!chart) return;

    const recalc = () => {
      const range = findBarTimesForDateRange(selectedFrom, selectedTo);
      if (!range) {
        setHighlight(null);
        return;
      }
      const x1 = timeToX(range.firstTime);
      const x2 = timeToX(range.lastTime);
      if (x1 != null && x2 != null) {
        const left = Math.min(x1, x2);
        const width = Math.max(Math.abs(x2 - x1), 4);
        setHighlight({ left, width });
      } else {
        setHighlight(null);
      }
    };

    const timer = setTimeout(recalc, 50);
    const unsub = chart.timeScale().subscribeVisibleTimeRangeChange(recalc);
    return () => {
      clearTimeout(timer);
      if (typeof unsub === "function") unsub();
      else {
        try { chart.timeScale().unsubscribeVisibleTimeRangeChange(recalc); } catch {}
      }
    };
  }, [selectedFrom, selectedTo, chartRef, findBarTimesForDateRange, timeToX]);

  /* ── mouse coordinate helper ───────────────────────────────────── */
  const getLocalX = useCallback(
    (e: React.MouseEvent): number => {
      const rect = overlayRef.current?.getBoundingClientRect();
      return rect ? e.clientX - rect.left : 0;
    },
    []
  );

  /* ── mouse handlers ────────────────────────────────────────────── */
  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      if (!enabled) return;
      e.preventDefault();
      const x = getLocalX(e);
      startXRef.current = x;
      isDraggingRef.current = true;
      setDragRect({ left: x, width: 0 });
    },
    [enabled, getLocalX]
  );

  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      if (!isDraggingRef.current) return;
      const x = getLocalX(e);
      const left = Math.min(startXRef.current, x);
      const width = Math.abs(x - startXRef.current);
      setDragRect({ left, width });
    },
    [getLocalX]
  );

  const handleMouseUp = useCallback(
    (e: React.MouseEvent) => {
      if (!isDraggingRef.current) return;
      isDraggingRef.current = false;

      const x = getLocalX(e);
      const x1 = Math.min(startXRef.current, x);
      const x2 = Math.max(startXRef.current, x);
      setDragRect(null);

      if (x2 - x1 < 10) return;

      // Find bars whose pixel positions fall within the drag range.
      // This uses timeToCoordinate (bar → pixel) which is reliable,
      // unlike coordinateToTime (pixel → bar) which has offset issues.
      const result = findBarsInPixelRange(x1, x2);
      if (result) {
        const d1 = tsToDateTime(result.firstBar.time);
        const d2 = tsToDateTime(result.lastBar.time);
        if (d1 && d2) {
          onRangeSelected(d1 <= d2 ? d1 : d2, d1 <= d2 ? d2 : d1);
        }
      }
    },
    [getLocalX, findBarsInPixelRange, onRangeSelected]
  );

  const handleMouseLeave = useCallback(() => {
    if (isDraggingRef.current) {
      isDraggingRef.current = false;
      setDragRect(null);
    }
  }, []);

  /* ── render ────────────────────────────────────────────────────── */
  const overlayStyle: React.CSSProperties = {
    position: "absolute",
    inset: 0,
    zIndex: 10,
    cursor: enabled ? "crosshair" : "default",
    pointerEvents: enabled ? "all" : "none",
  };

  const highlightBase: React.CSSProperties = {
    position: "absolute",
    top: 0,
    bottom: 0,
    background: "rgba(29, 78, 216, 0.12)",
    borderLeft: "2px solid rgba(29, 78, 216, 0.45)",
    borderRight: "2px solid rgba(29, 78, 216, 0.45)",
    pointerEvents: "none",
  };

  const showPersistent = !dragRect && highlight;

  return (
    <div
      ref={overlayRef}
      style={overlayStyle}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseLeave}
    >
      {/* Drag-in-progress highlight */}
      {dragRect && dragRect.width > 3 && (
        <div style={{ ...highlightBase, left: dragRect.left, width: dragRect.width }} />
      )}

      {/* Persistent highlight for committed selection */}
      {showPersistent && (
        <div style={{ ...highlightBase, left: highlight.left, width: highlight.width }}>
          <button
            onClick={(e) => {
              e.stopPropagation();
              onSelectionClear();
            }}
            style={{
              position: "absolute",
              top: 6,
              right: 6,
              background: "var(--bg-card, #fff)",
              border: "1px solid var(--border-color, #ccc)",
              borderRadius: "var(--radius-sm, 4px)",
              color: "var(--text-secondary, #666)",
              cursor: "pointer",
              fontSize: "0.7rem",
              padding: "2px 8px",
              pointerEvents: "all",
              zIndex: 20,
              boxShadow: "0 1px 3px rgba(0,0,0,0.1)",
            }}
          >
            clear
          </button>
        </div>
      )}
    </div>
  );
}
