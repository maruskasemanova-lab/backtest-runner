import { useCallback, useRef, useState, type ReactNode } from "react";

export const safeNum = (v: unknown, fallback: number | null = null): number | null => {
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

export interface MiniBarProps {
  label: string;
  value: number | null;
  max?: number;
  threshold?: number | null;
  suffix?: string;
  showThresholdLine?: boolean;
}

export function MiniBar({ label, value, max = 100, threshold, suffix = "%", showThresholdLine }: MiniBarProps) {
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

/* ── Interactive MiniBar with draggable threshold handle ────────── */

export interface InteractiveMiniBarProps extends MiniBarProps {
  interactive?: boolean;
  thresholdOverride?: number | null;
  onThresholdChange?: (newValue: number) => void;
  thresholdMin?: number;
  thresholdMax?: number;
}

export function InteractiveMiniBar({
  label,
  value,
  max = 100,
  threshold,
  suffix = "%",
  showThresholdLine,
  interactive,
  thresholdOverride,
  onThresholdChange,
  thresholdMin = 0,
  thresholdMax = 100,
}: InteractiveMiniBarProps) {
  const barRef = useRef<HTMLDivElement>(null);
  const [dragging, setDragging] = useState(false);
  const [dragValue, setDragValue] = useState<number | null>(null);

  const effectiveThreshold = thresholdOverride ?? threshold;

  const calcValueFromPointer = useCallback(
    (clientX: number) => {
      const el = barRef.current;
      if (!el) return effectiveThreshold ?? 50;
      const rect = el.getBoundingClientRect();
      const ratio = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
      const raw = ratio * max;
      return Math.round(Math.max(thresholdMin, Math.min(thresholdMax, raw)) * 10) / 10;
    },
    [max, thresholdMin, thresholdMax, effectiveThreshold],
  );

  const onPointerDown = useCallback(
    (e: React.PointerEvent) => {
      if (!interactive || !onThresholdChange) return;
      e.preventDefault();
      (e.target as HTMLElement).setPointerCapture(e.pointerId);
      setDragging(true);
      const v = calcValueFromPointer(e.clientX);
      setDragValue(v);
      onThresholdChange(v);
    },
    [interactive, onThresholdChange, calcValueFromPointer],
  );

  const onPointerMove = useCallback(
    (e: React.PointerEvent) => {
      if (!dragging || !onThresholdChange) return;
      const v = calcValueFromPointer(e.clientX);
      setDragValue(v);
      onThresholdChange(v);
    },
    [dragging, onThresholdChange, calcValueFromPointer],
  );

  const onPointerUp = useCallback(() => {
    setDragging(false);
    setDragValue(null);
  }, []);

  // Non-interactive → delegate to plain MiniBar
  if (!interactive) {
    return (
      <MiniBar
        label={label}
        value={value}
        max={max}
        threshold={effectiveThreshold}
        suffix={suffix}
        showThresholdLine={showThresholdLine}
      />
    );
  }

  const displayVal = value ?? 0;
  const widthPct = max > 0 ? Math.min(100, Math.max(0, (displayVal / max) * 100)) : 0;
  const thr = effectiveThreshold;
  const thresholdPct = thr != null && max > 0 ? Math.min(100, (thr / max) * 100) : null;
  const barHeight = 14;

  return (
    <div style={{ marginBottom: 5 }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.65rem", lineHeight: 1.2, marginBottom: 2 }}>
        <span style={{ color: "var(--text-secondary)", fontWeight: 500 }}>{label}</span>
        <span style={{ color: "var(--text-primary)", fontWeight: 600, fontVariantNumeric: "tabular-nums" }}>
          {value != null ? `${displayVal.toFixed(1)}${suffix}` : "\u2014"}
          {thr != null && (
            <span style={{ color: "var(--accent-blue, #3b82f6)", marginLeft: 4, fontSize: "0.58rem" }}>
              thr:{thr.toFixed(0)}
            </span>
          )}
        </span>
      </div>
      <div
        ref={barRef}
        style={{
          position: "relative",
          height: barHeight,
          borderRadius: 3,
          background: "var(--bg-tertiary, rgba(255,255,255,0.06))",
          overflow: "visible",
          cursor: "pointer",
          transition: "height 0.15s ease-out",
        }}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
      >
        {/* Score fill */}
        <div
          style={{
            height: "100%",
            width: `${widthPct}%`,
            borderRadius: 3,
            background: value != null ? barColor(displayVal, max, thr) : "var(--bg-tertiary)",
            transition: "width 0.08s ease-out",
            opacity: 0.7,
          }}
        />
        {/* Draggable threshold handle */}
        {thresholdPct != null && (
          <div
            className="sa-threshold-handle"
            style={{
              position: "absolute",
              top: -3,
              bottom: -3,
              left: `${thresholdPct}%`,
              width: 6,
              marginLeft: -3,
              borderRadius: 3,
              background: dragging
                ? "var(--accent-blue, #3b82f6)"
                : "var(--accent-blue, #3b82f6)",
              opacity: dragging ? 1.0 : 0.8,
              boxShadow: dragging ? "0 0 6px rgba(59,130,246,0.5)" : "none",
              cursor: "ew-resize",
              touchAction: "none",
              transition: dragging ? "none" : "left 0.08s ease-out, opacity 0.1s",
            }}
            title={`Threshold: ${thr?.toFixed(1)}`}
          />
        )}
        {/* Drag tooltip */}
        {dragging && dragValue != null && thresholdPct != null && (
          <div
            style={{
              position: "absolute",
              bottom: barHeight + 4,
              left: `${thresholdPct}%`,
              transform: "translateX(-50%)",
              padding: "1px 5px",
              borderRadius: 3,
              fontSize: "0.58rem",
              fontWeight: 700,
              background: "var(--accent-blue, #3b82f6)",
              color: "#fff",
              whiteSpace: "nowrap",
              pointerEvents: "none",
              zIndex: 10,
            }}
          >
            {dragValue.toFixed(1)}
          </div>
        )}
      </div>
    </div>
  );
}

export function SectionLabel({ children, icon }: { children: ReactNode; icon?: ReactNode }) {
  void icon;
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 4,
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
