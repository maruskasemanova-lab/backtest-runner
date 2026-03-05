import { useCallback, useRef, useState, type ReactNode } from "react";

export const safeNum = (
  v: unknown,
  fallback: number | null = null,
): number | null => {
  if (v == null) return fallback;
  const n = Number(v);
  return Number.isFinite(n) ? n : fallback;
};

export function cx(...tokens: Array<string | false | null | undefined>) {
  return tokens.filter(Boolean).join(" ");
}

type AnalyzerTone = "success" | "warning" | "danger";

const barTone = (
  value: number,
  max: number,
  threshold?: number | null,
): AnalyzerTone => {
  const ratio = max > 0 ? value / max : 0;
  if (threshold != null && max > 0) {
    const thresholdRatio = threshold / max;
    if (ratio >= thresholdRatio) return "success";
    if (ratio >= thresholdRatio * 0.7) return "warning";
    return "danger";
  }
  if (ratio >= 0.7) return "success";
  if (ratio >= 0.4) return "warning";
  return "danger";
};

export interface MiniBarProps {
  label: string;
  value: number | null;
  max?: number;
  threshold?: number | null;
  suffix?: string;
  showThresholdLine?: boolean;
}

export function MiniBar({
  label,
  value,
  max = 100,
  threshold,
  suffix = "%",
  showThresholdLine,
}: MiniBarProps) {
  const displayVal = value ?? 0;
  const widthPct =
    max > 0 ? Math.min(100, Math.max(0, (displayVal / max) * 100)) : 0;
  const thresholdPct =
    threshold != null && max > 0
      ? Math.min(100, (threshold / max) * 100)
      : null;

  return (
    <div className="sa-mini-bar">
      <div className="sa-mini-bar__header">
        <span className="sa-mini-bar__label">{label}</span>
        <span className="sa-mini-bar__value">
          {value != null ? `${displayVal.toFixed(1)}${suffix}` : "—"}
        </span>
      </div>
      <div className="sa-track">
        <div
          className={cx(
            "sa-track__fill",
            value == null
              ? "is-empty"
              : `is-${barTone(displayVal, max, threshold)}`,
          )}
          style={{ width: `${widthPct}%` }}
        />
        {showThresholdLine && thresholdPct != null && (
          <div
            className="sa-track__threshold"
            style={{ left: `${thresholdPct}%` }}
            title={`Threshold: ${threshold?.toFixed(1)}`}
          />
        )}
      </div>
    </div>
  );
}

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
      const ratio = Math.max(
        0,
        Math.min(1, (clientX - rect.left) / rect.width),
      );
      const raw = ratio * max;
      return (
        Math.round(Math.max(thresholdMin, Math.min(thresholdMax, raw)) * 10) /
        10
      );
    },
    [effectiveThreshold, max, thresholdMax, thresholdMin],
  );

  const onPointerDown = useCallback(
    (e: React.PointerEvent) => {
      if (!interactive || !onThresholdChange) return;
      e.preventDefault();
      (e.target as HTMLElement).setPointerCapture(e.pointerId);
      setDragging(true);
      const nextValue = calcValueFromPointer(e.clientX);
      setDragValue(nextValue);
      onThresholdChange(nextValue);
    },
    [calcValueFromPointer, interactive, onThresholdChange],
  );

  const onPointerMove = useCallback(
    (e: React.PointerEvent) => {
      if (!dragging || !onThresholdChange) return;
      const nextValue = calcValueFromPointer(e.clientX);
      setDragValue(nextValue);
      onThresholdChange(nextValue);
    },
    [calcValueFromPointer, dragging, onThresholdChange],
  );

  const onPointerUp = useCallback(() => {
    setDragging(false);
    setDragValue(null);
  }, []);

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
  const widthPct =
    max > 0 ? Math.min(100, Math.max(0, (displayVal / max) * 100)) : 0;
  const thresholdPct =
    effectiveThreshold != null && max > 0
      ? Math.min(100, (effectiveThreshold / max) * 100)
      : null;

  return (
    <div className="sa-mini-bar is-interactive">
      <div className="sa-mini-bar__header">
        <span className="sa-mini-bar__label">{label}</span>
        <span className="sa-mini-bar__value">
          {value != null ? `${displayVal.toFixed(1)}${suffix}` : "—"}
          {effectiveThreshold != null && (
            <span className="sa-mini-bar__threshold-label">
              thr:{effectiveThreshold.toFixed(0)}
            </span>
          )}
        </span>
      </div>
      <div
        ref={barRef}
        className="sa-track is-interactive"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
      >
        <div
          className={cx(
            "sa-track__fill",
            "is-dimmed",
            value == null
              ? "is-empty"
              : `is-${barTone(displayVal, max, effectiveThreshold)}`,
          )}
          style={{ width: `${widthPct}%` }}
        />
        {showThresholdLine && thresholdPct != null && (
          <div
            className={cx("sa-track__handle", dragging && "is-dragging")}
            style={{ left: `${thresholdPct}%` }}
            title={`Threshold: ${effectiveThreshold?.toFixed(1)}`}
          />
        )}
        {dragging && dragValue != null && thresholdPct != null && (
          <div
            className="sa-track__tooltip"
            style={{ left: `${thresholdPct}%` }}
          >
            {dragValue.toFixed(1)}
          </div>
        )}
      </div>
    </div>
  );
}

export function SectionLabel({
  children,
  icon,
}: {
  children: ReactNode;
  icon?: ReactNode;
}) {
  void icon;
  return <div className="sa-section-label">{children}</div>;
}
