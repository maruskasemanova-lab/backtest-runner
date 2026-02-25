import { useCallback, useState } from "react";
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

  const handleStartTest = useCallback(async () => {
    if (!selectedRangeFrom || !selectedRangeTo || !ticker) return;
    setRunLoading(true);
    setError(null);
    try {
      const effectiveStartLocal = rangePlaybackMeta?.warmupStartLocal || selectedRangeFrom;
      const effectiveEndLocal = rangePlaybackMeta?.tradeEndLocal || selectedRangeTo;
      const effectiveTradeStartLocal = rangePlaybackMeta?.tradeStartLocal || selectedRangeFrom;
      const effectiveTradeEndLocal = rangePlaybackMeta?.tradeEndLocal || selectedRangeTo;

      const payload: StrategyAnalyzerStartRunPayload = {
        run_id: `analyzer-${Date.now()}`,
        ticker,
        date_from: effectiveStartLocal.slice(0, 10),
        date_to: effectiveEndLocal.slice(0, 10),
        start_time: dateTimeLocalToUtcIso(effectiveStartLocal),
        end_time: dateTimeLocalToUtcIso(effectiveEndLocal),
        trade_start_time: dateTimeLocalToUtcIso(effectiveTradeStartLocal),
        trade_end_time: dateTimeLocalToUtcIso(effectiveTradeEndLocal),
        strategy_api_url: strategyApiUrl || defaultStrategyApiUrl,
        include_extended_hours: true,
        trade_eval_mode: analyzerTradeEvalMode,
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
