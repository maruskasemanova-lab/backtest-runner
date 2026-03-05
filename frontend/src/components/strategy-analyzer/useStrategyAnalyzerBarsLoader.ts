import { useCallback, useEffect, useRef, useState } from "react";
import { orderIsoDateRange, toChartBar } from "./utils";
import type { StrategyAnalyzerPreviewBar } from "./types";

type Params = {
  ticker: string;
  dateFrom: string;
  dateTo: string;
  setError: (value: string | null) => void;
  resetSelectionForNewData: () => void;
};

export function useStrategyAnalyzerBarsLoader({
  ticker,
  dateFrom,
  dateTo,
  setError,
  resetSelectionForNewData,
}: Params) {
  const [bars, setBars] = useState<StrategyAnalyzerPreviewBar[]>([]);
  const [loading, setLoading] = useState(false);
  const [barCount, setBarCount] = useState(0);
  const latestLoadRequestIdRef = useRef(0);
  const activeAbortControllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    return () => {
      activeAbortControllerRef.current?.abort();
      activeAbortControllerRef.current = null;
    };
  }, []);

  const resetBarsState = useCallback(() => {
    setBars([]);
    setBarCount(0);
  }, []);

  const loadBars = useCallback(async () => {
    if (!ticker || !dateFrom || !dateTo) return;
    const orderedRange = orderIsoDateRange(dateFrom, dateTo);
    const effectiveDateFrom = orderedRange.dateFrom;
    const effectiveDateTo = orderedRange.dateTo;
    if (!effectiveDateFrom || !effectiveDateTo) return;

    const requestId = latestLoadRequestIdRef.current + 1;
    latestLoadRequestIdRef.current = requestId;
    activeAbortControllerRef.current?.abort();
    const abortController = new AbortController();
    activeAbortControllerRef.current = abortController;

    setLoading(true);
    setError(null);
    resetBarsState();
    resetSelectionForNewData();
    try {
      const url = `/api/chart-preview/bars?ticker=${encodeURIComponent(ticker)}&date_from=${effectiveDateFrom}&date_to=${effectiveDateTo}`;
      const resp = await fetch(url, { signal: abortController.signal });
      if (!resp.ok) {
        const detail = await resp.json().catch(() => ({}));
        throw new Error(detail?.detail || `HTTP ${resp.status}`);
      }
      const data = (await resp.json()) as { bars?: unknown[]; bar_count?: number };
      if (latestLoadRequestIdRef.current !== requestId) return;
      const converted = (data.bars || []).map(toChartBar).filter(Boolean);
      setBars(converted as StrategyAnalyzerPreviewBar[]);
      setBarCount(data.bar_count || converted.length);
    } catch (e: unknown) {
      const isAbortError =
        (e instanceof DOMException && e.name === "AbortError") ||
        (typeof e === "object" && e !== null && "name" in e && (e as { name?: string }).name === "AbortError");
      if (isAbortError) return;
      if (latestLoadRequestIdRef.current !== requestId) return;
      setError(e instanceof Error ? e.message : "Failed to load bars");
    } finally {
      if (activeAbortControllerRef.current === abortController) {
        activeAbortControllerRef.current = null;
      }
      if (latestLoadRequestIdRef.current === requestId) {
        setLoading(false);
      }
    }
  }, [ticker, dateFrom, dateTo, setError, resetBarsState, resetSelectionForNewData]);

  return {
    bars,
    loading,
    barCount,
    loadBars,
    resetBarsState,
  };
}
