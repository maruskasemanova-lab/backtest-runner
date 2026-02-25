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
    setLoadingTickers(true);
    fetch("/api/available-data")
      .then((r) => r.json())
      .then((data) => {
        if (cancelled) return;
        const ranges = data?.date_ranges || {};
        const list: AvailableTicker[] = Object.entries(ranges).map(([t, r]: [string, any]) => ({
          ticker: t,
          start_date: r?.ohlcv_start || r?.start || "",
          end_date: r?.ohlcv_end || r?.end || "",
        }));
        list.sort((a, b) => a.ticker.localeCompare(b.ticker));
        setTickers(list);

        const match = list.find((row) => row.ticker === (selectedTicker || "MU"));
        if (match) {
          setDateFrom(match.start_date);
          setDateTo(match.end_date);
        }
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) {
          setLoadingTickers(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

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
