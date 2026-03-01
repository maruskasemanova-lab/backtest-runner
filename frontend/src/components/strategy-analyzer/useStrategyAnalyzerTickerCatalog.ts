import { useCallback, useEffect, useState } from "react";

type AvailableTicker = {
  ticker: string;
  start_date: string;
  end_date: string;
};

type Params = {
  selectedTicker: string | null;
  onTickerChange: (ticker: string) => void;
  setTicker: (value: string) => void;
  setDateFrom: (value: string) => void;
  setDateTo: (value: string) => void;
  resetForTickerChange: () => void;
};

export function useStrategyAnalyzerTickerCatalog({
  selectedTicker,
  onTickerChange,
  setTicker,
  setDateFrom,
  setDateTo,
  resetForTickerChange,
}: Params) {
  const [tickers, setTickers] = useState<AvailableTicker[]>([]);
  const [loadingTickers, setLoadingTickers] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let retryTimer: number | null = null;
    const maxAttempts = 6;

    const loadCatalog = async (attempt: number) => {
      if (cancelled) return;
      if (attempt === 1) {
        setLoadingTickers(true);
      }
      let retryScheduled = false;

      try {
        const endpoint = attempt >= 2 ? "/api/available-data?refresh=1" : "/api/available-data";
        const response = await fetch(endpoint, { cache: "no-store" });
        if (!response.ok) {
          throw new Error(`available-data request failed: ${response.status}`);
        }
        const data = await response.json();
        if (cancelled) return;
        const ranges = data?.date_ranges || {};
        const list: AvailableTicker[] = Object.entries(ranges).map(([t, r]: [string, any]) => ({
          ticker: t,
          start_date: r?.ohlcv_start || r?.start || "",
          end_date: r?.ohlcv_end || r?.end || "",
        }));
        list.sort((a, b) => a.ticker.localeCompare(b.ticker));

        if (list.length === 0 && attempt < maxAttempts) {
          retryScheduled = true;
          retryTimer = window.setTimeout(() => {
            void loadCatalog(attempt + 1);
          }, 800 * attempt);
          return;
        }

        setTickers(list);

        const preferredTicker = String(selectedTicker || "MU").trim().toUpperCase();
        const exactMatch =
          list.find((row) => String(row.ticker || "").trim().toUpperCase() === preferredTicker) ||
          null;
        const fallbackWithDates =
          list.find((row) => Boolean(String(row.start_date || "").trim() && String(row.end_date || "").trim())) ||
          null;
        const match = exactMatch || fallbackWithDates || list[0] || null;
        if (match) {
          const normalizedMatchTicker = String(match.ticker || "").trim().toUpperCase();
          const normalizedSelectedTicker = String(selectedTicker || "").trim().toUpperCase();
          if (normalizedMatchTicker && normalizedMatchTicker !== normalizedSelectedTicker) {
            setTicker(normalizedMatchTicker);
            onTickerChange(normalizedMatchTicker);
          }
          setDateFrom(String(match.start_date || ""));
          setDateTo(String(match.end_date || ""));
        }
      } catch {
        if (cancelled) return;
        if (attempt < maxAttempts) {
          retryScheduled = true;
          retryTimer = window.setTimeout(() => {
            void loadCatalog(attempt + 1);
          }, 800 * attempt);
          return;
        }
      } finally {
        if (!cancelled && !retryScheduled) {
          setLoadingTickers(false);
        }
      }
    };

    void loadCatalog(1);

    return () => {
      cancelled = true;
      if (retryTimer !== null) {
        window.clearTimeout(retryTimer);
      }
    };
  }, [onTickerChange, selectedTicker, setDateFrom, setDateTo, setTicker]);

  const handleTickerChange = useCallback(
    (newTicker: string) => {
      setTicker(newTicker);
      onTickerChange(newTicker);
      const match = tickers.find((row) => row.ticker === newTicker);
      if (match) {
        setDateFrom(match.start_date);
        setDateTo(match.end_date);
      }
      resetForTickerChange();
    },
    [onTickerChange, resetForTickerChange, setDateFrom, setDateTo, tickers]
  );

  return {
    tickers,
    loadingTickers,
    handleTickerChange,
  };
}
