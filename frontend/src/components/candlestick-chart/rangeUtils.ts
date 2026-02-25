import type { CandlestickChartVisibleRange } from "../CandlestickChart";

const RANGE_EPSILON = 0.001;

export const normalizeVisibleRange = (range: unknown): CandlestickChartVisibleRange | null => {
  const value =
    range && typeof range === "object" ? (range as { from?: unknown; to?: unknown }) : null;
  const from = Number(value?.from);
  const to = Number(value?.to);
  if (!Number.isFinite(from) || !Number.isFinite(to)) return null;
  if (from <= to) return { from, to };
  return { from: to, to: from };
};

export const rangesEqual = (left: unknown, right: unknown): boolean => {
  const a = normalizeVisibleRange(left);
  const b = normalizeVisibleRange(right);
  if (!a || !b) return false;
  return Math.abs(a.from - b.from) < RANGE_EPSILON && Math.abs(a.to - b.to) < RANGE_EPSILON;
};
