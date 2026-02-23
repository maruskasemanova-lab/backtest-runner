import { useEffect, useState } from "react";
import type { Dispatch, SetStateAction } from "react";
import { normalizeIsoDay } from "../../utils";
import {
  applyMuMomentumDefaults,
  resolveDateRangeWithFallback,
  resolveTickerCoverageRange,
} from "./runConfigHelpers";

type UseRunConfigAvailableDataArgs = {
  setConfig: Dispatch<SetStateAction<Record<string, any>>>;
  onTickerChange?: (ticker: string) => void;
};

export const useRunConfigAvailableData = ({
  setConfig,
  onTickerChange,
}: UseRunConfigAvailableDataArgs) => {
  const [availableData, setAvailableData] = useState<Record<string, any> | null>(null);
  const [availableDataError, setAvailableDataError] = useState<string | null>(null);

  useEffect(() => {
    const applyAvailableData = (data: Record<string, any>) => {
      setAvailableData(data);

      if (!data?.tickers || data.tickers.length === 0) {
        setAvailableDataError("No tickers available from R2 manifest catalog.");
        return;
      }
      setAvailableDataError(null);

      let changedTickerToNotify = "";
      setConfig((prev) => {
        const prevTicker = String(prev.ticker || "").trim().toUpperCase();
        const hasPrevTicker = !!prevTicker;
        const hasPrevTickerInCatalog = hasPrevTicker && data.tickers.includes(prevTicker);
        const targetTicker = hasPrevTicker ? prevTicker : data.tickers[0];
        if (!hasPrevTicker && targetTicker && targetTicker !== prevTicker) {
          changedTickerToNotify = targetTicker;
        }
        const coverage = resolveTickerCoverageRange({
          availableData: data,
          ticker: targetTicker,
          l2Only: !!prev.l2_only,
        });
        const range = coverage.effectiveRange;
        const defaultDate = normalizeIsoDay(range?.end) || new Date().toISOString().split("T")[0];
        const dateSeed = hasPrevTicker
          ? resolveDateRangeWithFallback({
              range,
              from: prev.date_from,
              to: prev.date_to,
              fallbackDate: defaultDate,
            })
          : resolveDateRangeWithFallback({
              range,
              from: defaultDate,
              to: defaultDate,
              fallbackDate: defaultDate,
            });
        if (hasPrevTicker && !hasPrevTickerInCatalog) {
          dateSeed.date = normalizeIsoDay(prev.date) || dateSeed.date;
          dateSeed.date_from = normalizeIsoDay(prev.date_from) || dateSeed.date_from;
          dateSeed.date_to = normalizeIsoDay(prev.date_to) || dateSeed.date_to;
        }
        const next = applyMuMomentumDefaults(
          {
            ...prev,
            ticker: targetTicker,
            ...dateSeed,
          },
          targetTicker,
          prev.ticker,
        );
        return next;
      });

      if (onTickerChange && changedTickerToNotify) {
        onTickerChange(changedTickerToNotify);
      }
    };

    const fetchAvailableData = async () => {
      const retryDelaysMs = [0, 400, 1200];
      let lastErrorMessage = "";

      for (let attempt = 0; attempt < retryDelaysMs.length; attempt += 1) {
        const delayMs = retryDelaysMs[attempt];
        if (delayMs > 0) {
          // Strict R2 mode: retry transient backend/edge failures, no local fallback.
          await new Promise((resolve) => setTimeout(resolve, delayMs));
        }

        try {
          const resp = await fetch("/api/available-data?refresh=1");
          if (!resp.ok) {
            const payload = await resp.json().catch(() => ({}));
            const detail = String(payload?.detail || "").trim();
            lastErrorMessage = detail
              ? `Failed to load available data: ${detail}`
              : `Failed to load available data (HTTP ${resp.status}).`;
            if (attempt < retryDelaysMs.length - 1) {
              continue;
            }
            setAvailableData(null);
            setAvailableDataError(lastErrorMessage);
            return;
          }

          const data = await resp.json();
          applyAvailableData(data);
          return;
        } catch (err) {
          console.error("Failed to fetch available data:", err);
          lastErrorMessage = "Failed to load available data from backend.";
          if (attempt < retryDelaysMs.length - 1) {
            continue;
          }
          setAvailableData(null);
          setAvailableDataError(lastErrorMessage);
          return;
        }
      }

      setAvailableData(null);
      setAvailableDataError(lastErrorMessage || "Failed to load available data from backend.");
    };

    fetchAvailableData();
  }, [onTickerChange, setConfig]);

  return {
    availableData,
    availableDataError,
  };
};
