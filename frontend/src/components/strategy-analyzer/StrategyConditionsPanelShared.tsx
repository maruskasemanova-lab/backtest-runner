import type { ReactNode } from "react";

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
