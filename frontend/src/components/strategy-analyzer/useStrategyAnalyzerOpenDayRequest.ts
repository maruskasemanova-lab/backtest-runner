import { useEffect, useRef, useState } from "react";
import type { StrategyAnalyzerContextRiskPresetKey, StrategyAnalyzerTradeEvalMode } from "./types";
import {
  resolveContextRiskPresetFromRunKey,
  resolveContextRiskPresetFromVariantKey,
} from "./strategyAnalyzerContextRiskPresets";

const handledOpenDayAutoLoadRequestIds = new Set<number>();

export type StrategyAnalyzerOpenDayRequest = {
  requestId: number;
  ticker: string;
  isoDate: string;
  runKey?: string | null;
  variantKey?: string | null;
  /** Original run date-range start (from multi-day run_key). */
  dateFrom?: string | null;
  /** Original run date-range end (from multi-day run_key). */
  dateTo?: string | null;
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
  setContextRiskPresetKey: (value: StrategyAnalyzerContextRiskPresetKey) => void;
  setComparableMode: (value: boolean) => void;
  setAnalyzerTradeEvalMode: (value: StrategyAnalyzerTradeEvalMode) => void;
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
  setContextRiskPresetKey,
  setComparableMode,
  setAnalyzerTradeEvalMode,
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
    const requestedVariantKey = String(openDayRequest.variantKey || "").trim().toLowerCase();
    // Use the original multi-day range when available so the user can re-run
    // with the same warm-start state that produced the Diagnostics results.
    const effectiveDateFrom = String(openDayRequest.dateFrom || "").trim() || targetDate;
    const effectiveDateTo = String(openDayRequest.dateTo || "").trim() || targetDate;
    const isMultiDayRange = effectiveDateFrom !== effectiveDateTo;

    const inferredContextRiskPreset = resolveContextRiskPresetFromVariantKey(requestedVariantKey)
      || resolveContextRiskPresetFromRunKey(requestedRunKey);
    if (inferredContextRiskPreset) {
      setContextRiskPresetKey(inferredContextRiskPreset);
    }

    // Match the run settings that produced the Diagnostics results:
    // - comparable_mode ensures cold-start + no checkpoint loading
    // - standard eval mode avoids slow intrabar 5s evaluation
    setComparableMode(true);
    setAnalyzerTradeEvalMode("standard");

    const applyPreviewSelection = () => {
      setError(null);
      if (targetTicker !== ticker) {
        setTicker(targetTicker);
        onTickerChange(targetTicker);
        resetForTickerChange();
      } else {
        resetSelectionForNewData();
      }
      setDateFrom(effectiveDateFrom);
      setDateTo(effectiveDateTo);
      setRangeSelectMode(isMultiDayRange);
      setPendingOpenDayAutoLoad({
        requestId: openDayRequest.requestId,
        ticker: targetTicker,
        isoDate: targetDate,
        dateFrom: isMultiDayRange ? effectiveDateFrom : null,
        dateTo: isMultiDayRange ? effectiveDateTo : null,
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
          setDateFrom(effectiveDateFrom);
          setDateTo(effectiveDateTo);
          setRangeSelectMode(isMultiDayRange);
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
    setContextRiskPresetKey,
    setComparableMode,
    setAnalyzerTradeEvalMode,
  ]);

  useEffect(() => {
    if (!pendingOpenDayAutoLoad) return;
    const targetDate = String(pendingOpenDayAutoLoad.isoDate || "").trim();
    const targetTicker = String(pendingOpenDayAutoLoad.ticker || "").trim().toUpperCase();
    const requestId = pendingOpenDayAutoLoad.requestId;
    // When opened from Diagnostics with a multi-day range, expect the full range
    const expectedDateFrom = String(pendingOpenDayAutoLoad.dateFrom || targetDate).trim();
    const expectedDateTo = String(pendingOpenDayAutoLoad.dateTo || targetDate).trim();
    if (!targetDate) {
      setPendingOpenDayAutoLoad(null);
      return;
    }
    if (loading) return;
    if (targetTicker && String(ticker || "").trim().toUpperCase() !== targetTicker) return;
    if (dateFrom !== expectedDateFrom || dateTo !== expectedDateTo) return;

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
