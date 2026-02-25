import { useCallback, useState } from "react";
import { toChartBar } from "./utils";
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

  const resetBarsState = useCallback(() => {
    setBars([]);
    setBarCount(0);
  }, []);

  const loadBars = useCallback(async () => {
    if (!ticker || !dateFrom || !dateTo) return;
    setLoading(true);
    setError(null);
    resetBarsState();
    resetSelectionForNewData();
    try {
      const url = `/api/chart-preview/bars?ticker=${encodeURIComponent(ticker)}&date_from=${dateFrom}&date_to=${dateTo}`;
      const resp = await fetch(url);
      if (!resp.ok) {
        const detail = await resp.json().catch(() => ({}));
        throw new Error(detail?.detail || `HTTP ${resp.status}`);
      }
      const data = (await resp.json()) as { bars?: unknown[]; bar_count?: number };
      const converted = (data.bars || []).map(toChartBar).filter(Boolean);
      setBars(converted as StrategyAnalyzerPreviewBar[]);
      setBarCount(data.bar_count || converted.length);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load bars");
    } finally {
      setLoading(false);
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
