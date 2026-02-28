import { normalizeIsoDay } from "../../utils";
import { AUTO_PREWARM_CHUNK_DAYS } from "./runConfigCore";

export const parseRunKeyIdentity = (value) => {
  const raw = String(value || "").trim();
  if (!raw) return null;
  const parts = raw.split(":");
  if (parts.length < 3) return null;
  const date = String(parts.pop() || "").trim();
  const ticker = String(parts.pop() || "").trim().toUpperCase();
  const runId = String(parts.join(":") || "").trim();
  if (!runId || !ticker || !date) return null;
  return { run_id: runId, ticker, date };
};

export const RUN_RANGE_LABEL_PATTERN = /^(\d{4}-\d{2}-\d{2})_to_(\d{4}-\d{2}-\d{2})$/;

export const parseRunRangeLabel = (value) => {
  const token = String(value || "").trim();
  const match = token.match(RUN_RANGE_LABEL_PATTERN);
  if (!match) return null;
  const from = normalizeIsoDay(match[1]);
  const to = normalizeIsoDay(match[2]);
  if (!from || !to || from > to) return null;
  return { from, to };
};

export const resolveRunDateLabel = (payload) => {
  const rawDate = normalizeIsoDay(payload?.date);
  const rawDateFrom = normalizeIsoDay(payload?.date_from);
  const rawDateTo = normalizeIsoDay(payload?.date_to);
  const from = rawDateFrom || rawDate;
  const to = rawDateTo || rawDateFrom || rawDate;
  if (!from || !to) return "";
  // Keep parity with backend: explicit date_from/date_to always produces range label.
  if (rawDateFrom || rawDateTo || from !== to) {
    return `${from}_to_${to}`;
  }
  return from;
};

export const buildRunKeyFromStartPayload = (payload) => {
  const runId = String(payload?.run_id || "").trim();
  const ticker = String(payload?.ticker || "").trim().toUpperCase();
  const dateLabel = resolveRunDateLabel(payload);
  if (!runId || !ticker || !dateLabel) return "";
  return `${runId}:${ticker}:${dateLabel}`;
};

export const resolveAttachedRunDates = (runRow) => {
  const rawDate = String(runRow?.date || "").trim();
  const parsedRange = parseRunRangeLabel(rawDate);
  const from = normalizeIsoDay(runRow?.date_from) || parsedRange?.from || normalizeIsoDay(rawDate) || "";
  const to = normalizeIsoDay(runRow?.date_to) || parsedRange?.to || from || "";
  const singleDay = normalizeIsoDay(rawDate);
  return {
    date: singleDay || from || to || "",
    date_from: from,
    date_to: to,
  };
};

export const AVAILABLE_RANGE_HINT_PATTERN =
  /Available OHLCV range:\s*(\d{4}-\d{2}-\d{2})\s*to\s*(\d{4}-\d{2}-\d{2})/i;

export const parseIsoDayUtc = (value) => {
  const normalized = normalizeIsoDay(value);
  if (!normalized) return null;
  const parsed = new Date(`${normalized}T00:00:00Z`);
  if (Number.isNaN(parsed.getTime())) return null;
  return parsed;
};

export const formatIsoDayUtc = (date) => {
  if (!(date instanceof Date) || Number.isNaN(date.getTime())) return "";
  return date.toISOString().slice(0, 10);
};

export const buildIsoDayChunks = (rangeStart, rangeEnd, chunkDays = AUTO_PREWARM_CHUNK_DAYS) => {
  const startDate = parseIsoDayUtc(rangeStart);
  const endDate = parseIsoDayUtc(rangeEnd);
  if (!startDate || !endDate || startDate > endDate) {
    return [];
  }

  const daysPerChunk = Math.max(1, Math.trunc(Number(chunkDays) || 1));
  const chunks = [];
  let cursor = new Date(startDate.getTime());

  while (cursor <= endDate) {
    const chunkStart = new Date(cursor.getTime());
    const chunkEnd = new Date(cursor.getTime());
    chunkEnd.setUTCDate(chunkEnd.getUTCDate() + daysPerChunk - 1);
    if (chunkEnd > endDate) {
      chunkEnd.setTime(endDate.getTime());
    }
    chunks.push({
      date_from: formatIsoDayUtc(chunkStart),
      date_to: formatIsoDayUtc(chunkEnd),
    });
    cursor = new Date(chunkEnd.getTime());
    cursor.setUTCDate(cursor.getUTCDate() + 1);
  }

  return chunks;
};

export const clampIsoDayToRange = (day, range) => {
  const normalized = normalizeIsoDay(day);
  if (!normalized) return "";
  const min = normalizeIsoDay(range?.start);
  const max = normalizeIsoDay(range?.end);
  if (min && normalized < min) return min;
  if (max && normalized > max) return max;
  return normalized;
};

export const resolveDateRangeWithFallback = ({ range, from, to, fallbackDate }) => {
  const fallback = clampIsoDayToRange(fallbackDate, range) || normalizeIsoDay(fallbackDate);
  let nextFrom = clampIsoDayToRange(from, range) || fallback;
  let nextTo = clampIsoDayToRange(to, range) || fallback || nextFrom;
  if (nextFrom && nextTo && nextTo < nextFrom) {
    nextTo = nextFrom;
  }
  if (!nextFrom && nextTo) {
    nextFrom = nextTo;
  }
  if (!nextTo && nextFrom) {
    nextTo = nextFrom;
  }
  return {
    date_from: nextFrom || "",
    date_to: nextTo || "",
    date: nextFrom || nextTo || fallback || "",
  };
};

export const normalizeCoverageRange = (range) => {
  const start = normalizeIsoDay(range?.start);
  const end = normalizeIsoDay(range?.end);
  if (!start || !end || start > end) return null;
  return { start, end };
};

export const buildOverlapCoverageRange = (leftRange, rightRange) => {
  const left = normalizeCoverageRange(leftRange);
  const right = normalizeCoverageRange(rightRange);
  if (!left || !right) return null;
  const start = left.start > right.start ? left.start : right.start;
  const end = left.end < right.end ? left.end : right.end;
  if (!start || !end || start > end) return null;
  return { start, end };
};

export const resolveTickerCoverageRange = ({ availableData, ticker, l2Only = false }) => {
  const safeTicker = String(ticker || "").trim().toUpperCase();
  if (!availableData || !safeTicker) {
    return {
      effectiveRange: null,
      ohlcvRange: null,
      l2Range: null,
      overlapRange: null,
    };
  }

  const ohlcvRange = normalizeCoverageRange(availableData?.date_ranges?.[safeTicker]);
  const l2Range = normalizeCoverageRange(availableData?.l2_date_ranges?.[safeTicker]);
  const overlapRange =
    normalizeCoverageRange(availableData?.l2_overlap_date_ranges?.[safeTicker]) ||
    buildOverlapCoverageRange(ohlcvRange, l2Range);

  const effectiveRange = l2Only
    ? overlapRange || l2Range || ohlcvRange
    : ohlcvRange || overlapRange || l2Range;
  return {
    effectiveRange,
    ohlcvRange,
    l2Range,
    overlapRange,
  };
};
