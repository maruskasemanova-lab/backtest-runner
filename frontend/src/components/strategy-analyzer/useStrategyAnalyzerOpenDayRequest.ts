import { useEffect, useRef, useState } from "react";

const handledOpenDayAutoLoadRequestIds = new Set<number>();

export type StrategyAnalyzerOpenDayRequest = {
  requestId: number;
  ticker: string;
  isoDate: string;
  runKey?: string | null;
};

type UseStrategyAnalyzerOpenDayRequestArgs = {
  openDayRequest?: StrategyAnalyzerOpenDayRequest | null;
  onOpenDayRequestHandled?: (requestId: number) => void;
  onOpenStoredRunSnapshot?: (runKey: string) => Promise<boolean>;
  loadingTickers: boolean;
  tickersLength: number;
  selectedTicker: string | null;
  ticker: string;
  onTickerChange: (ticker: string) => void;
  setTicker: (ticker: string) => void;
  setDateFrom: (value: string) => void;
  setDateTo: (value: string) => void;
  setError: (value: string | null) => void;
  setRangeSelectMode: (value: boolean) => void;
  setSelectedRangeFrom: (value: string | null) => void;
  setSelectedRangeTo: (value: string | null) => void;
  setRangeScrubOffset: (value: number) => void;
  setAnalyzerRunKey: (value: string | null) => void;
  resetForTickerChange: () => void;
  resetSelectionForNewData: () => void;
  loading: boolean;
  dateFrom: string;
  dateTo: string;
  loadBars: () => Promise<any>;
};

export const useStrategyAnalyzerOpenDayRequest = ({
  openDayRequest = null,
  onOpenDayRequestHandled,
  onOpenStoredRunSnapshot,
  loadingTickers,
  tickersLength,
  selectedTicker,
  ticker,
  onTickerChange,
  setTicker,
  setDateFrom,
  setDateTo,
  setError,
  setRangeSelectMode,
  setSelectedRangeFrom,
  setSelectedRangeTo,
  setRangeScrubOffset,
  setAnalyzerRunKey,
  resetForTickerChange,
  resetSelectionForNewData,
  loading,
  dateFrom,
  dateTo,
  loadBars,
}: UseStrategyAnalyzerOpenDayRequestArgs) => {
  const [pendingOpenDayAutoLoad, setPendingOpenDayAutoLoad] =
    useState<StrategyAnalyzerOpenDayRequest | null>(null);
  const tickerCatalogLoadStartedRef = useRef(false);
  const openDayAutoLoadInFlightRef = useRef<number | null>(null);
  const openDayStoredSnapshotInFlightRef = useRef<number | null>(null);
  const consumedOpenDayAutoLoadRequestIdRef = useRef<number | null>(null);

  useEffect(() => {
    if (loadingTickers) {
      tickerCatalogLoadStartedRef.current = true;
    }
  }, [loadingTickers]);

  useEffect(() => {
    if (!openDayRequest) return;

    const targetDate = String(openDayRequest.isoDate || "").trim();
    if (!/^\d{4}-\d{2}-\d{2}$/.test(targetDate)) {
      onOpenDayRequestHandled?.(openDayRequest.requestId);
      return;
    }

    const catalogLoadStarted = tickerCatalogLoadStartedRef.current;
    if (!catalogLoadStarted && tickersLength === 0) return;
    if (loadingTickers) return;

    const requestedTicker = String(openDayRequest.ticker || selectedTicker || ticker || "MU")
      .trim()
      .toUpperCase();
    const targetTicker = requestedTicker || "MU";
    const requestedRunKey = String(openDayRequest.runKey || "").trim();

    const applyPreviewSelection = () => {
      setError(null);
      if (targetTicker !== ticker) {
        setTicker(targetTicker);
        onTickerChange(targetTicker);
        resetForTickerChange();
      } else {
        resetSelectionForNewData();
      }
      setDateFrom(targetDate);
      setDateTo(targetDate);
      setRangeSelectMode(false);
      setPendingOpenDayAutoLoad({
        requestId: openDayRequest.requestId,
        ticker: targetTicker,
        isoDate: targetDate,
      });
      onOpenDayRequestHandled?.(openDayRequest.requestId);
    };

    if (requestedRunKey && typeof onOpenStoredRunSnapshot === "function") {
      if (openDayStoredSnapshotInFlightRef.current === openDayRequest.requestId) return;
      let cancelled = false;
      openDayStoredSnapshotInFlightRef.current = openDayRequest.requestId;
      void onOpenStoredRunSnapshot(requestedRunKey)
        .then((loaded) => {
          if (cancelled) return;
          if (!loaded) {
            applyPreviewSelection();
            return;
          }
          setError(null);
          if (targetTicker !== ticker) {
            setTicker(targetTicker);
            onTickerChange(targetTicker);
          }
          setDateFrom(targetDate);
          setDateTo(targetDate);
          setRangeSelectMode(false);
          setSelectedRangeFrom(`${targetDate}T00:00`);
          setSelectedRangeTo(`${targetDate}T23:59`);
          setRangeScrubOffset(0);
          setAnalyzerRunKey(requestedRunKey);
          onOpenDayRequestHandled?.(openDayRequest.requestId);
        })
        .catch(() => {
          if (cancelled) return;
          applyPreviewSelection();
        })
        .finally(() => {
          if (openDayStoredSnapshotInFlightRef.current === openDayRequest.requestId) {
            openDayStoredSnapshotInFlightRef.current = null;
          }
        });
      return () => {
        cancelled = true;
      };
    }

    applyPreviewSelection();
  }, [
    openDayRequest,
    onOpenDayRequestHandled,
    onOpenStoredRunSnapshot,
    loadingTickers,
    tickersLength,
    selectedTicker,
    ticker,
    onTickerChange,
    resetForTickerChange,
    resetSelectionForNewData,
    setAnalyzerRunKey,
    setDateFrom,
    setDateTo,
    setError,
    setRangeScrubOffset,
    setRangeSelectMode,
    setSelectedRangeFrom,
    setSelectedRangeTo,
    setTicker,
  ]);

  useEffect(() => {
    if (!pendingOpenDayAutoLoad) return;
    const targetDate = String(pendingOpenDayAutoLoad.isoDate || "").trim();
    const targetTicker = String(pendingOpenDayAutoLoad.ticker || "").trim().toUpperCase();
    const requestId = pendingOpenDayAutoLoad.requestId;
    if (!targetDate) {
      setPendingOpenDayAutoLoad(null);
      return;
    }
    if (loading) return;
    if (targetTicker && String(ticker || "").trim().toUpperCase() !== targetTicker) return;
    if (dateFrom !== targetDate || dateTo !== targetDate) return;

    let cancelled = false;
    if (handledOpenDayAutoLoadRequestIds.has(requestId)) {
      setPendingOpenDayAutoLoad(null);
      return;
    }
    handledOpenDayAutoLoadRequestIds.add(requestId);
    if (consumedOpenDayAutoLoadRequestIdRef.current === requestId) return;
    consumedOpenDayAutoLoadRequestIdRef.current = requestId;
    setPendingOpenDayAutoLoad(null);
    if (openDayAutoLoadInFlightRef.current === requestId) return;
    openDayAutoLoadInFlightRef.current = requestId;
    void loadBars().finally(() => {
      if (openDayAutoLoadInFlightRef.current === requestId) {
        openDayAutoLoadInFlightRef.current = null;
      }
      if (cancelled) return;
      setSelectedRangeFrom(`${targetDate}T00:00`);
      setSelectedRangeTo(`${targetDate}T23:59`);
      setRangeScrubOffset(0);
    });
    return () => {
      cancelled = true;
    };
  }, [
    pendingOpenDayAutoLoad,
    loading,
    ticker,
    dateFrom,
    dateTo,
    loadBars,
    setRangeScrubOffset,
    setSelectedRangeFrom,
    setSelectedRangeTo,
  ]);
};
