import { useCallback, useEffect, useRef, useState } from "react";
import { defaultStrategyApiUrl } from "../../utils";
import { dateTimeLocalToUtcIso } from "./utils";
import type {
  StrategyAnalyzerOnClearRun,
  StrategyAnalyzerOnStartRun,
  StrategyAnalyzerRangePlaybackMeta,
  StrategyAnalyzerStartRunPayload,
  StrategyAnalyzerStartRunResult,
  StrategyAnalyzerTradeEvalMode,
} from "./types";

type Params = {
  selectedRangeFrom: string | null;
  selectedRangeTo: string | null;
  ticker: string;
  strategyApiUrl: string;
  analyzerTradeEvalMode: StrategyAnalyzerTradeEvalMode;
  rangePlaybackMeta: StrategyAnalyzerRangePlaybackMeta;
  onStartRun?: StrategyAnalyzerOnStartRun;
  onSwitchToBacktest?: () => void;
  onClearRun?: StrategyAnalyzerOnClearRun;
  isAnalyzerAttachedRun: boolean;
  setError: (value: string | null) => void;
  setRangeScrubOffset: (value: number) => void;
  setAnalyzerRunKey: (value: string | null) => void;
};

/** Ensure data for the given date range is cached on the backend.
 *  If already cached or in-flight, returns immediately.
 *  Otherwise fires /api/run/prewarm and waits for it. */
async function ensurePrewarmed(
  ticker: string,
  dateFrom: string,
  dateTo: string,
): Promise<void> {
  const payload = {
    ticker,
    date_from: dateFrom,
    date_to: dateTo,
    prewarm_scope: "range",
    allow_mock_data: false,
    include_extended_hours: true,
  };
  try {
    const statusResp = await fetch("/api/run/prewarm/status", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const statusData = await statusResp.json().catch(() => ({}));
    if (statusResp.ok && statusData?.ready) return;
  } catch {
    // Status check failed — fall through to fire prewarm
  }
  try {
    await fetch("/api/run/prewarm", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch {
    // Prewarm failure is non-critical; /api/run/start will load data itself
  }
}

export function useStrategyAnalyzerRunOrchestration({
  selectedRangeFrom,
  selectedRangeTo,
  ticker,
  strategyApiUrl,
  analyzerTradeEvalMode,
  rangePlaybackMeta,
  onStartRun,
  onSwitchToBacktest,
  onClearRun,
  isAnalyzerAttachedRun,
  setError,
  setRangeScrubOffset,
  setAnalyzerRunKey,
}: Params) {
  const [runLoading, setRunLoading] = useState(false);
  const lastPrewarmKeyRef = useRef("");

  // Eagerly pre-warm backend data cache when the selected range changes.
  // Even if user clicks Start before this finishes, handleStartTest also
  // calls ensurePrewarmed (which deduplicates via the inflight mechanism).
  useEffect(() => {
    if (!selectedRangeFrom || !selectedRangeTo || !ticker) return;
    if (!rangePlaybackMeta) return;

    const effectiveStartLocal = rangePlaybackMeta.warmupStartLocal || selectedRangeFrom;
    const effectiveEndLocal = rangePlaybackMeta.tradeEndLocal || selectedRangeTo;
    const dateFrom = effectiveStartLocal.slice(0, 10);
    const dateTo = effectiveEndLocal.slice(0, 10);

    const prewarmKey = `${ticker}:${dateFrom}:${dateTo}`;
    if (prewarmKey === lastPrewarmKeyRef.current) return;

    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      if (controller.signal.aborted) return;
      try {
        await ensurePrewarmed(ticker, dateFrom, dateTo);
        lastPrewarmKeyRef.current = prewarmKey;
      } catch {
        // Non-critical
      }
    }, 250);

    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [selectedRangeFrom, selectedRangeTo, ticker, rangePlaybackMeta]);

  const handleStartTest = useCallback(async () => {
    if (!selectedRangeFrom || !selectedRangeTo || !ticker) return;
    setRunLoading(true);
    setError(null);
    try {
      const effectiveStartLocal = rangePlaybackMeta?.warmupStartLocal || selectedRangeFrom;
      const effectiveEndLocal = rangePlaybackMeta?.tradeEndLocal || selectedRangeTo;
      const effectiveTradeStartLocal = rangePlaybackMeta?.tradeStartLocal || selectedRangeFrom;
      const effectiveTradeEndLocal = rangePlaybackMeta?.tradeEndLocal || selectedRangeTo;
      const dateFrom = effectiveStartLocal.slice(0, 10);
      const dateTo = effectiveEndLocal.slice(0, 10);

      // Ensure bars are cached before /api/run/start.
      // If background prewarm already completed, this returns instantly (cache hit).
      // If prewarm is still in-flight, this joins the existing request (dedup).
      await ensurePrewarmed(ticker, dateFrom, dateTo);
      lastPrewarmKeyRef.current = `${ticker}:${dateFrom}:${dateTo}`;

      const payload: StrategyAnalyzerStartRunPayload = {
        run_id: `analyzer-${Date.now()}`,
        ticker,
        date_from: dateFrom,
        date_to: dateTo,
        start_time: dateTimeLocalToUtcIso(effectiveStartLocal),
        end_time: dateTimeLocalToUtcIso(effectiveEndLocal),
        trade_start_time: dateTimeLocalToUtcIso(effectiveTradeStartLocal),
        trade_end_time: dateTimeLocalToUtcIso(effectiveTradeEndLocal),
        strategy_api_url: strategyApiUrl || defaultStrategyApiUrl,
        include_extended_hours: true,
        trade_eval_mode: analyzerTradeEvalMode,
        // Hint for frontend start handler: analyzer should start immediately
        // (skip queued v2 orchestration path and use direct /api/run/start).
        __client_hint: "strategy_analyzer",
      };
      if (typeof onStartRun === "function") {
        const result = await onStartRun(payload);
        const nextRunKey = String(result?.run_key || "").trim();
        setRangeScrubOffset(0);
        setAnalyzerRunKey(nextRunKey || null);
      } else {
        const resp = await fetch("/api/run/start", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        if (!resp.ok) {
          const detail = await resp.json().catch(() => ({}));
          throw new Error(detail?.detail || `HTTP ${resp.status}`);
        }
        const data = (await resp.json().catch(() => ({}))) as StrategyAnalyzerStartRunResult;
        const nextRunKey = String(data?.run_key || "").trim();
        setRangeScrubOffset(0);
        setAnalyzerRunKey(nextRunKey || null);
        onSwitchToBacktest?.();
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to start test");
    } finally {
      setRunLoading(false);
    }
  }, [
    selectedRangeFrom,
    selectedRangeTo,
    ticker,
    strategyApiUrl,
    analyzerTradeEvalMode,
    rangePlaybackMeta,
    onStartRun,
    onSwitchToBacktest,
    setError,
    setRangeScrubOffset,
    setAnalyzerRunKey,
  ]);

  const handleClearAnalyzerRun = useCallback(async () => {
    if (!isAnalyzerAttachedRun) return;
    setError(null);
    try {
      await onClearRun?.();
      setAnalyzerRunKey(null);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to clear run");
    }
  }, [isAnalyzerAttachedRun, onClearRun, setAnalyzerRunKey, setError]);

  return {
    runLoading,
    handleStartTest,
    handleClearAnalyzerRun,
  };
}
