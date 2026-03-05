import { toUnixSeconds } from "../../utils";
import type { StrategyAnalyzerAnyObject, StrategyAnalyzerPreviewBar } from "./types";

export const toChartBar = (
  bar: StrategyAnalyzerAnyObject | null | undefined
): StrategyAnalyzerPreviewBar | null => {
  if (!bar || typeof bar !== "object") return null;
  const time = toUnixSeconds(bar.timestamp ?? bar.time);
  const open = Number(bar.open);
  const high = Number(bar.high);
  const low = Number(bar.low);
  const close = Number(bar.close);
  const volume = Number(bar.volume);
  if (!Number.isFinite(time)) return null;
  if (
    !Number.isFinite(open) ||
    !Number.isFinite(high) ||
    !Number.isFinite(low) ||
    !Number.isFinite(close)
  ) {
    return null;
  }
  return {
    time,
    open,
    high,
    low,
    close,
    volume: Number.isFinite(volume) ? volume : 0,
  };
};

export const dateTimeLocalToUtcIso = (value: string | null | undefined): string | null => {
  const raw = String(value || "").trim();
  if (!raw) return null;
  const ms = Date.parse(raw);
  if (!Number.isFinite(ms)) return null;
  return new Date(ms).toISOString();
};

export const orderIsoDateRange = (
  dateFrom: string | null | undefined,
  dateTo: string | null | undefined,
): { dateFrom: string; dateTo: string } => {
  const from = String(dateFrom || "").trim();
  const to = String(dateTo || "").trim();

  if (!from && !to) return { dateFrom: "", dateTo: "" };
  if (!from) return { dateFrom: to, dateTo: to };
  if (!to) return { dateFrom: from, dateTo: from };

  if (/^\d{4}-\d{2}-\d{2}$/.test(from) && /^\d{4}-\d{2}-\d{2}$/.test(to)) {
    return from <= to
      ? { dateFrom: from, dateTo: to }
      : { dateFrom: to, dateTo: from };
  }

  return { dateFrom: from, dateTo: to };
};

export const unixSecondsToDateTimeLocal = (ts: number): string => {
  const d = new Date(ts * 1000);
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  const hh = String(d.getHours()).padStart(2, "0");
  const min = String(d.getMinutes()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}T${hh}:${min}`;
};

export const unixSecondsToLabel = (ts: number, includeSeconds = false): string => {
  const d = new Date(ts * 1000);
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  const hh = String(d.getHours()).padStart(2, "0");
  const min = String(d.getMinutes()).padStart(2, "0");
  const ss = String(d.getSeconds()).padStart(2, "0");
  return includeSeconds ? `${yyyy}-${mm}-${dd}T${hh}:${min}:${ss}` : `${yyyy}-${mm}-${dd}T${hh}:${min}`;
};
