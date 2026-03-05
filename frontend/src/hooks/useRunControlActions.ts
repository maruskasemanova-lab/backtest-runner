import {
  useCallback,
  useEffect,
  type Dispatch,
  type MutableRefObject,
  type SetStateAction,
} from 'react';
import type { CandlestickChartBar } from '../components/CandlestickChart';
import { upsertStreamChartBar } from '../app/appRunStateCollectionShared';

const RUN_STATE_POLL_VISIBLE_MS = 1000;
const RUN_STATE_POLL_HIDDEN_MS = 5000;

type UseRunControlActionsArgs = {
  activeRunApiBase: string | null;
  runState: any;
  speed: string | number;
  tradeEvaluationMode: string;
  isPlaying: boolean;
  isPageVisible: boolean;
  isPollingFallback: boolean;
  isPageVisibleRef: MutableRefObject<boolean>;
  barsLengthRef: MutableRefObject<number>;
  clearActiveRunState: (notice?: string) => void;
  refreshActiveRuns: () => void;
  handleNewBar: (bar: any) => void;
  toChartBar: (bar: any) => CandlestickChartBar | null;
  setRuntimeNotice: Dispatch<SetStateAction<string>>;
  setIsPlaying: Dispatch<SetStateAction<boolean>>;
  setTradeEvaluationMode: Dispatch<SetStateAction<string>>;
  setRunState: Dispatch<SetStateAction<any>>;
  setBars: Dispatch<SetStateAction<CandlestickChartBar[]>>;
  setCurrentBar: Dispatch<SetStateAction<any>>;
};

export const useRunControlActions = ({
  activeRunApiBase,
  runState,
  speed,
  tradeEvaluationMode,
  isPlaying,
  isPageVisible,
  isPollingFallback,
  isPageVisibleRef,
  barsLengthRef,
  clearActiveRunState,
  refreshActiveRuns,
  handleNewBar,
  toChartBar,
  setRuntimeNotice,
  setIsPlaying,
  setTradeEvaluationMode,
  setRunState,
  setBars,
  setCurrentBar,
}: UseRunControlActionsArgs) => {
  const isSnapshot = Boolean(runState?.is_snapshot);

  const handleStep = useCallback(
    async (stepOptions = null) => {
      if (!activeRunApiBase) return;
      if (isSnapshot) {
        setRuntimeNotice(
          'Stored run snapshot is read-only. Start a new test to replay interactively.',
        );
        return;
      }

      try {
        const rawStepOptions =
          stepOptions && typeof stepOptions === 'object' ? stepOptions : {};
        const overrideTradeEvalMode = String(stepOptions?.trade_eval_mode || '')
          .trim()
          .toLowerCase();
        const requestedTradeEvalMode =
          overrideTradeEvalMode === 'intrabar_5s' ||
          overrideTradeEvalMode === 'intrabar_1s' ||
          overrideTradeEvalMode === 'standard'
            ? overrideTradeEvalMode
            : tradeEvaluationMode;

        const response = await fetch(`${activeRunApiBase}/step`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            ...rawStepOptions,
            trade_eval_mode: requestedTradeEvalMode,
          }),
        });
        const data = await response.json();

        if (data.success && data.bar) {
          handleNewBar(data.bar);
          setRunState((prev: any) => {
            if (!prev) return prev;
            const totalBars = Number(prev.total_bars || 0);
            const rawCurrent = Number(data.bar_index || 0) + 1;
            const current =
              totalBars > 0
                ? Math.min(totalBars, Math.max(0, rawCurrent))
                : Math.max(0, rawCurrent);
            const progress =
              totalBars > 0
                ? Math.min(100, Math.max(0, (current / totalBars) * 100))
                : Number(data.progress_pct || 0);
            return {
              ...prev,
              current_bar_index: current,
              phase: data.phase,
              progress_pct: progress,
            };
          });
        }

        const effectiveTradeMode = String(data?.trade_eval_mode || '').trim().toLowerCase();
        if (
          effectiveTradeMode === 'intrabar_5s' ||
          effectiveTradeMode === 'intrabar_1s' ||
          effectiveTradeMode === 'standard'
        ) {
          setTradeEvaluationMode(effectiveTradeMode);
        }

        return data;
      } catch (error) {
        console.error('Step error:', error);
      }
    },
    [
      activeRunApiBase,
      handleNewBar,
      isSnapshot,
      setRunState,
      setRuntimeNotice,
      setTradeEvaluationMode,
      tradeEvaluationMode,
    ],
  );

  const handlePlay = useCallback(
    async (playOptions = null) => {
      if (!activeRunApiBase) return;
      if (isSnapshot) {
        setRuntimeNotice(
          'Stored run snapshot is read-only. Start a new test to replay interactively.',
        );
        setIsPlaying(false);
        return;
      }

      try {
        const rawPlayOptions =
          playOptions && typeof playOptions === 'object' ? playOptions : {};
        const overrideSpeedRaw = playOptions?.speed_ms;
        const hasSpeedOverride =
          overrideSpeedRaw !== undefined &&
          overrideSpeedRaw !== null &&
          String(overrideSpeedRaw).trim() !== '';

        let speedParam: string | number;
        if (hasSpeedOverride) {
          speedParam =
            typeof overrideSpeedRaw === 'string'
              ? overrideSpeedRaw.trim()
              : overrideSpeedRaw;
        } else if (typeof speed === 'string') {
          speedParam = speed;
        } else if (speed === 0) {
          speedParam = 'max';
        } else {
          speedParam = speed;
        }

        const overrideTradeEvalMode = String(playOptions?.trade_eval_mode || '')
          .trim()
          .toLowerCase();
        const requestedTradeEvalMode =
          overrideTradeEvalMode === 'intrabar_5s' ||
          overrideTradeEvalMode === 'intrabar_1s' ||
          overrideTradeEvalMode === 'standard'
            ? overrideTradeEvalMode
            : tradeEvaluationMode;

        const response = await fetch(`${activeRunApiBase}/play`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            ...rawPlayOptions,
            speed_ms: speedParam,
            trade_eval_mode: requestedTradeEvalMode,
          }),
        });
        if (!response.ok) {
          let detailMessage = `HTTP ${response.status}`;
          try {
            const detail = await response.json();
            if (detail?.detail) detailMessage = String(detail.detail);
            else if (detail?.error) detailMessage = String(detail.error);
          } catch (_error) {
            // Ignore detail parse issues and keep HTTP fallback.
          }
          if (response.status === 404) {
            refreshActiveRuns();
            setRuntimeNotice(
              'Active run is no longer in backend memory. Replay controls are disabled for this snapshot; start/reload run to continue interactively.',
            );
            setIsPlaying(false);
            return;
          }
          setRuntimeNotice(`Play failed: ${detailMessage}`);
          setIsPlaying(false);
          console.error('Play request failed:', response.status, detailMessage);
          return;
        }
        const playPayload = await response.json().catch(() => ({}));
        if (playPayload?.success === false) {
          const detailMessage = String(playPayload?.error || 'Play failed').trim();
          const runAlreadyInProgress = /already in progress/i.test(detailMessage);
          if (runAlreadyInProgress) {
            setRuntimeNotice('');
            setIsPlaying(true);
            return;
          }
          setRuntimeNotice(`Play failed: ${detailMessage}`);
          setIsPlaying(false);
          console.error('Play response rejected:', detailMessage, playPayload);
          return;
        }
        const effectiveTradeMode = String(playPayload?.trade_eval_mode || '').trim().toLowerCase();
        if (
          effectiveTradeMode === 'intrabar_5s' ||
          effectiveTradeMode === 'intrabar_1s' ||
          effectiveTradeMode === 'standard'
        ) {
          setTradeEvaluationMode(effectiveTradeMode);
        }
        setRuntimeNotice('');
        setIsPlaying(true);
      } catch (error) {
        const detailMessage = error instanceof Error ? error.message : 'Unknown error';
        setRuntimeNotice(`Play error: ${detailMessage}`);
        setIsPlaying(false);
        console.error('Play error:', error);
      }
    },
    [
      activeRunApiBase,
      clearActiveRunState,
      isSnapshot,
      setIsPlaying,
      setRuntimeNotice,
      setTradeEvaluationMode,
      speed,
      tradeEvaluationMode,
    ],
  );

  const handlePause = useCallback(async () => {
    if (!activeRunApiBase) return;
    if (isSnapshot) {
      setIsPlaying(false);
      return;
    }

    try {
      await fetch(`${activeRunApiBase}/pause`, {
        method: 'POST',
      });
      setIsPlaying(false);
    } catch (error) {
      console.error('Pause error:', error);
    }
  }, [activeRunApiBase, isSnapshot, setIsPlaying]);

  useEffect(() => {
    if (!activeRunApiBase || !isPlaying) return undefined;

    let cancelled = false;
    const pollState = async () => {
      if (cancelled) return;
      try {
        const response = await fetch(`${activeRunApiBase}/state`);
        if (!response.ok) {
          if (response.status === 404) {
            if (!cancelled) {
              cancelled = true;
              setIsPlaying(false);
              setRunState((prev: any) => {
                if (!prev) return prev;
                return {
                  ...prev,
                  is_running: false,
                };
              });
            }
            return;
          }
          console.warn('State poll failed:', response.status, response.statusText);
          return;
        }

        const state = await response.json();
        if (cancelled) return;

        if (isPageVisibleRef.current) {
          setRunState(state);
        }

        const processedCount = Number(state?.current_bar_index || 0);
        const localBarsCount = Number(barsLengthRef.current || 0);
        const barsBehindCount = Math.max(0, processedCount - localBarsCount);
        const barsAheadCount = Math.max(0, localBarsCount - processedCount);
        const preferDeltaSync = Boolean(isPollingFallback || barsBehindCount > 0);
        const shouldSyncBars =
          (processedCount > 0 || localBarsCount > 0) &&
          (barsBehindCount > 0 || barsAheadCount > 0);

        if (shouldSyncBars) {
          try {
            const requestedSinceIndex = Math.max(0, localBarsCount);
            const barsUrl =
              preferDeltaSync && barsBehindCount > 0
                ? `${activeRunApiBase}/bars?since_index=${requestedSinceIndex}`
                : `${activeRunApiBase}/bars`;
            const barsResponse = await fetch(barsUrl);
            if (barsResponse.ok) {
              const barsPayload = await barsResponse.json();
              const rawBars = Array.isArray(barsPayload?.bars) ? barsPayload.bars : [];
              const payloadMode = String(barsPayload?.mode || '').trim().toLowerCase();
              const payloadSinceIndex = Number(barsPayload?.since_index);
              const canApplyDelta =
                barsBehindCount > 0 &&
                preferDeltaSync &&
                payloadMode === 'delta' &&
                Number.isFinite(payloadSinceIndex) &&
                payloadSinceIndex === requestedSinceIndex;

              if (canApplyDelta) {
                const nextChartBars = rawBars
                  .map((bar: any) => toChartBar(bar))
                  .filter(Boolean) as CandlestickChartBar[];
                if (nextChartBars.length > 0) {
                  setBars((prev) => {
                    let next = prev;
                    for (const chartBar of nextChartBars) {
                      next = upsertStreamChartBar(next, chartBar);
                    }
                    return next;
                  });
                }
              } else {
                const chartBars = rawBars
                  .map((bar: any) => toChartBar(bar))
                  .filter(Boolean)
                  .sort((a: CandlestickChartBar, b: CandlestickChartBar) => a.time - b.time);
                setBars(chartBars);
              }
              setCurrentBar(rawBars[rawBars.length - 1] || null);
            }
          } catch (barsError) {
            console.debug('Bars poll sync failed:', barsError);
          }
        }

        if (!state?.is_running) {
          setIsPlaying(false);
        }
      } catch (error) {
        if (!cancelled) {
          setIsPlaying(false);
        }
        console.error('State poll error:', error);
      }
    };

    pollState();
    const interval = setInterval(
      pollState,
      isPageVisible ? RUN_STATE_POLL_VISIBLE_MS : RUN_STATE_POLL_HIDDEN_MS,
    );
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [
    activeRunApiBase,
    barsLengthRef,
    isPageVisible,
    isPageVisibleRef,
    isPlaying,
    isPollingFallback,
    setBars,
    setCurrentBar,
    setIsPlaying,
    setRunState,
    toChartBar,
  ]);

  const handleStop = useCallback(async () => {
    if (!activeRunApiBase) return;
    if (isSnapshot) {
      setIsPlaying(false);
      return;
    }

    try {
      await fetch(`${activeRunApiBase}/stop`, {
        method: 'POST',
      });
      setIsPlaying(false);
      refreshActiveRuns();
    } catch (error) {
      console.error('Stop error:', error);
    }
  }, [activeRunApiBase, isSnapshot, refreshActiveRuns, setIsPlaying]);

  const handleReset = useCallback(async () => {
    if (!activeRunApiBase) return;

    if (isSnapshot) {
      clearActiveRunState('');
      setRuntimeNotice('');
      return;
    }

    try {
      await fetch(activeRunApiBase, {
        method: 'DELETE',
      });
      clearActiveRunState('');
      setRuntimeNotice('');
      refreshActiveRuns();
    } catch (error) {
      console.error('Reset error:', error);
    }
  }, [
    activeRunApiBase,
    clearActiveRunState,
    isSnapshot,
    refreshActiveRuns,
    setRuntimeNotice,
  ]);

  return {
    handleStep,
    handlePlay,
    handlePause,
    handleStop,
    handleReset,
  };
};
