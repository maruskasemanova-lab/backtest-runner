import {
  useCallback,
  useEffect,
  type Dispatch,
  type MutableRefObject,
  type SetStateAction,
} from 'react';
import type {
  CandlestickChartBar,
  CandlestickChartPriceRange,
  CandlestickChartVisibleRange,
} from '../components/CandlestickChart';

type UseRunSnapshotActionsArgs = {
  runKey: string | null;
  activeRunApiBase: string | null;
  isPageVisible: boolean;
  clearActiveRunState: (notice?: string) => void;
  refreshActiveRuns: () => void;
  pendingVisibilitySyncRef: MutableRefObject<boolean>;
  readErrorDetail: (response: Response, fallback: string) => Promise<string>;
  parseRunKey: (value: any) => { runId: string; ticker: string; date: string } | null;
  buildRunApiBase: (runParts: { runId: string; ticker: string; date: string } | null) => string | null;
  toChartBar: (bar: any) => CandlestickChartBar | null;
  buildEffectiveExecutionConfigSnapshot: (payload: any) => any;
  resolveTradeModeFromExecutionConfig: (executionConfig: any, fallbackMode?: string) => string;
  runIdCollisionPattern: RegExp;
  defaultStrategyApiUrl: string;
  setRunKey: Dispatch<SetStateAction<string | null>>;
  setRunState: Dispatch<SetStateAction<any>>;
  setEffectiveExecutionConfig: Dispatch<SetStateAction<any>>;
  setChartState: Dispatch<SetStateAction<CandlestickChartVisibleRange | null>>;
  setPriceRange: Dispatch<SetStateAction<CandlestickChartPriceRange>>;
  setBars: Dispatch<SetStateAction<CandlestickChartBar[]>>;
  setMarkers: Dispatch<SetStateAction<any[]>>;
  setSelectedMarker: Dispatch<SetStateAction<any>>;
  setCurrentBar: Dispatch<SetStateAction<any>>;
  setSelectedIntrabar: Dispatch<SetStateAction<any>>;
  setSelectedIntradayLevels: Dispatch<SetStateAction<any>>;
  setSelectedTicker: Dispatch<SetStateAction<string | null>>;
  setStrategyApiUrl: Dispatch<SetStateAction<string>>;
  setIsPlaying: Dispatch<SetStateAction<boolean>>;
  setIsReloadingSnapshot: Dispatch<SetStateAction<boolean>>;
  setTradeEvaluationMode: Dispatch<SetStateAction<string>>;
  setRuntimeNotice: Dispatch<SetStateAction<string>>;
};

export const useRunSnapshotActions = ({
  runKey,
  activeRunApiBase,
  isPageVisible,
  clearActiveRunState,
  refreshActiveRuns,
  pendingVisibilitySyncRef,
  readErrorDetail,
  parseRunKey,
  buildRunApiBase,
  toChartBar,
  buildEffectiveExecutionConfigSnapshot,
  resolveTradeModeFromExecutionConfig,
  runIdCollisionPattern,
  defaultStrategyApiUrl,
  setRunKey,
  setRunState,
  setEffectiveExecutionConfig,
  setChartState,
  setPriceRange,
  setBars,
  setMarkers,
  setSelectedMarker,
  setCurrentBar,
  setSelectedIntrabar,
  setSelectedIntradayLevels,
  setSelectedTicker,
  setStrategyApiUrl,
  setIsPlaying,
  setIsReloadingSnapshot,
  setTradeEvaluationMode,
  setRuntimeNotice,
}: UseRunSnapshotActionsArgs) => {
  const hydrateRunSnapshot = useCallback(
    async (targetRunKey: string, options: { showBusy?: boolean } = {}) => {
      const { showBusy = true } = options;
      const parsed = parseRunKey(targetRunKey);
      if (!parsed) return false;

      if (showBusy) {
        setIsReloadingSnapshot(true);
      }

      try {
        const runApiBase = buildRunApiBase(parsed);
        if (!runApiBase) return false;

        const [stateResp, barsResp, markersResp, summaryResp] = await Promise.all([
          fetch(`${runApiBase}/state`),
          fetch(`${runApiBase}/bars`),
          fetch(`${runApiBase}/markers`),
          fetch(`${runApiBase}/summary`),
        ]);

        if (!stateResp.ok || !barsResp.ok) {
          return false;
        }

        const statePayload = await stateResp.json();
        const barsPayload = await barsResp.json();
        const markersPayload = markersResp.ok ? await markersResp.json() : [];
        const summaryPayload = summaryResp.ok ? await summaryResp.json() : null;
        const nextExecutionConfig = buildEffectiveExecutionConfigSnapshot(summaryPayload);

        const rawBars = Array.isArray(barsPayload?.bars) ? barsPayload.bars : [];
        const chartBars = rawBars
          .map((bar: any) => toChartBar(bar))
          .filter(Boolean)
          .sort((a: CandlestickChartBar, b: CandlestickChartBar) => a.time - b.time);
        const nextMarkers = Array.isArray(markersPayload) ? markersPayload : [];

        setRunKey(targetRunKey);
        setRunState(statePayload && typeof statePayload === 'object' ? statePayload : null);
        setEffectiveExecutionConfig(nextExecutionConfig);
        setChartState(null);
        setPriceRange(null);
        setBars(chartBars);
        setMarkers(nextMarkers);
        setCurrentBar(rawBars.length ? rawBars[rawBars.length - 1] : null);
        setSelectedIntrabar(null);
        setSelectedIntradayLevels(null);
        setSelectedMarker((prevSelected: any) => {
          if (!prevSelected?.id) return null;
          return nextMarkers.find((candidate: any) => candidate?.id === prevSelected.id) || null;
        });
        setSelectedTicker(parsed.ticker || null);
        setIsPlaying(Boolean(statePayload?.is_running && !statePayload?.is_paused));
        setTradeEvaluationMode((prev) => resolveTradeModeFromExecutionConfig(nextExecutionConfig, prev));
        return true;
      } catch (error) {
        console.error('Snapshot reload failed:', error);
        return false;
      } finally {
        if (showBusy) {
          setIsReloadingSnapshot(false);
        }
      }
    },
    [
      buildEffectiveExecutionConfigSnapshot,
      buildRunApiBase,
      parseRunKey,
      resolveTradeModeFromExecutionConfig,
      setBars,
      setChartState,
      setCurrentBar,
      setEffectiveExecutionConfig,
      setIsPlaying,
      setIsReloadingSnapshot,
      setMarkers,
      setPriceRange,
      setRunKey,
      setRunState,
      setSelectedIntrabar,
      setSelectedIntradayLevels,
      setSelectedMarker,
      setSelectedTicker,
      setTradeEvaluationMode,
      toChartBar,
    ],
  );

  useEffect(() => {
    if (!isPageVisible || !runKey) return;
    if (!pendingVisibilitySyncRef.current) return;
    pendingVisibilitySyncRef.current = false;
    hydrateRunSnapshot(runKey, { showBusy: false }).catch((error) => {
      console.warn('Snapshot refresh after tab visibility change failed:', error);
    });
  }, [hydrateRunSnapshot, isPageVisible, pendingVisibilitySyncRef, runKey]);

  const handleStartRun = useCallback(
    async (config: any) => {
      try {
        setRuntimeNotice('');
        setSelectedTicker(config.ticker || null);
        setStrategyApiUrl(config.strategy_api_url || defaultStrategyApiUrl);
        const response = await fetch('/api/run/start', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(config),
        });

        if (!response.ok) {
          const detail = await readErrorDetail(response, `HTTP ${response.status}`);
          throw new Error(detail || 'Failed to start run');
        }

        const data = await response.json();
        const key = String(data.run_key || '');
        const parsedRun = parseRunKey(key);
        if (!parsedRun) {
          throw new Error('Invalid run key returned by backend.');
        }

        setRunKey(key);
        refreshActiveRuns();
        const nextExecutionConfig = buildEffectiveExecutionConfigSnapshot(data);
        setEffectiveExecutionConfig(nextExecutionConfig);
        setTradeEvaluationMode((prev) => resolveTradeModeFromExecutionConfig(nextExecutionConfig, prev));

        setChartState(null);
        setPriceRange(null);
        setBars([]);
        setMarkers([]);
        setSelectedMarker(null);
        setCurrentBar(null);
        setSelectedIntrabar(null);
        setSelectedIntradayLevels(null);
        setIsPlaying(false);
        pendingVisibilitySyncRef.current = false;

        const runApiBase = buildRunApiBase(parsedRun);
        const stateResp = await fetch(`${runApiBase}/state`);
        if (!stateResp.ok) {
          const detail = await readErrorDetail(stateResp, `HTTP ${stateResp.status}`);
          throw new Error(`Failed to load run state: ${detail}`);
        }
        const state = await stateResp.json();
        setRunState(state);

        try {
          const barsResp = await fetch(`${runApiBase}/bars`);
          if (barsResp.ok) {
            const barsPayload = await barsResp.json();
            const rawBars = Array.isArray(barsPayload?.bars) ? barsPayload.bars : [];
            const chartBars = rawBars
              .map((bar: any) => toChartBar(bar))
              .filter(Boolean)
              .sort((a: CandlestickChartBar, b: CandlestickChartBar) => a.time - b.time);
            if (chartBars.length > 0) {
              setBars(chartBars);
              setCurrentBar(rawBars[rawBars.length - 1] || null);
            }
          }
        } catch (barsError) {
          console.debug('Initial bars snapshot load failed:', barsError);
        }

        return data;
      } catch (error) {
        const message = String(error instanceof Error ? error.message : '');
        if (!runIdCollisionPattern.test(message)) {
          console.error('Start run error:', error);
        }
        throw error;
      }
    },
    [
      buildEffectiveExecutionConfigSnapshot,
      buildRunApiBase,
      defaultStrategyApiUrl,
      parseRunKey,
      pendingVisibilitySyncRef,
      readErrorDetail,
      refreshActiveRuns,
      resolveTradeModeFromExecutionConfig,
      runIdCollisionPattern,
      setBars,
      setChartState,
      setCurrentBar,
      setEffectiveExecutionConfig,
      setIsPlaying,
      setMarkers,
      setPriceRange,
      setRunKey,
      setRunState,
      setRuntimeNotice,
      setSelectedIntrabar,
      setSelectedIntradayLevels,
      setSelectedMarker,
      setSelectedTicker,
      setStrategyApiUrl,
      setTradeEvaluationMode,
      toChartBar,
    ],
  );

  const handleKillAndDeleteRun = useCallback(
    async (targetRunKey: string) => {
      const normalizedRunKey = String(targetRunKey || '').trim();
      const parsed = parseRunKey(normalizedRunKey);
      if (!parsed) {
        throw new Error('Invalid run key.');
      }
      const runApiBase = buildRunApiBase(parsed);
      if (!runApiBase) {
        throw new Error('Invalid run path.');
      }

      setRuntimeNotice('');
      try {
        const stopResp = await fetch(`${runApiBase}/stop`, { method: 'POST' });
        if (!stopResp.ok && stopResp.status !== 404) {
          const stopDetail = await readErrorDetail(stopResp, `HTTP ${stopResp.status}`);
          console.warn('Stop before delete returned error:', stopDetail);
        }
      } catch (stopError) {
        console.warn('Stop before delete failed:', stopError);
      }

      const deleteResp = await fetch(runApiBase, { method: 'DELETE' });
      if (!deleteResp.ok) {
        const detail = await readErrorDetail(deleteResp, `HTTP ${deleteResp.status}`);
        throw new Error(detail || 'Failed to delete run.');
      }

      if (normalizedRunKey === String(runKey || '').trim()) {
        clearActiveRunState('');
      }
      refreshActiveRuns();
    },
    [
      buildRunApiBase,
      clearActiveRunState,
      parseRunKey,
      readErrorDetail,
      refreshActiveRuns,
      runKey,
      setRuntimeNotice,
    ],
  );

  const handleReloadBacktest = useCallback(async () => {
    if (!runKey || !activeRunApiBase) return;

    setIsReloadingSnapshot(true);
    try {
      const restartResp = await fetch(`${activeRunApiBase}/restart`, { method: 'POST' });
      if (!restartResp.ok) {
        const fallbackReloaded = await hydrateRunSnapshot(runKey, { showBusy: false });
        if (!fallbackReloaded) {
          const detail = await restartResp.json().catch(() => ({}));
          throw new Error(detail?.detail || `HTTP ${restartResp.status}`);
        }
        return;
      }

      const reloaded = await hydrateRunSnapshot(runKey, { showBusy: false });
      if (!reloaded) {
        console.warn('Backtest restart completed, but snapshot refresh failed.');
      }
    } catch (error) {
      console.error('Backtest restart failed:', error);
    } finally {
      setIsReloadingSnapshot(false);
    }
  }, [activeRunApiBase, hydrateRunSnapshot, runKey, setIsReloadingSnapshot]);

  const handleAttachActiveRun = useCallback(
    async (targetRunKey: string) => {
      const ok = await hydrateRunSnapshot(targetRunKey, { showBusy: true });
      if (!ok) {
        setRuntimeNotice('Failed to attach selected run snapshot.');
        return;
      }
      setRuntimeNotice('');
    },
    [hydrateRunSnapshot, setRuntimeNotice],
  );

  const handleOpenStoredRunSnapshot = useCallback(
    async (targetRunKey: string) => {
      const normalizedRunKey = String(targetRunKey || '').trim();
      if (!normalizedRunKey) return false;

      const alreadyActive = await hydrateRunSnapshot(normalizedRunKey, { showBusy: true });
      if (alreadyActive) {
        setRuntimeNotice('');
        return true;
      }

      setIsReloadingSnapshot(true);
      try {
        const params = new URLSearchParams({ run_key: normalizedRunKey });
        const response = await fetch(`/api/reports/run-snapshot?${params.toString()}`);
        if (!response.ok) {
          const detail = await readErrorDetail(response, `HTTP ${response.status}`);
          setRuntimeNotice(`Failed to load stored snapshot: ${detail}`);
          return false;
        }

        const payload = await response.json().catch(() => ({}));
        const summaryPayload =
          payload?.summary && typeof payload.summary === 'object' ? payload.summary : {};
        const statePayload = payload?.state && typeof payload.state === 'object' ? payload.state : {};
        const rawBars = Array.isArray(payload?.bars) ? payload.bars : [];
        const rawMarkers = Array.isArray(payload?.markers) ? payload.markers : [];
        const chartBars = rawBars
          .map((bar: any) => toChartBar(bar))
          .filter(Boolean)
          .sort((a: CandlestickChartBar, b: CandlestickChartBar) => a.time - b.time);

        const nextRunKey = String(payload?.run_key || normalizedRunKey).trim() || normalizedRunKey;
        const parsedRun = parseRunKey(nextRunKey) || parseRunKey(normalizedRunKey);
        const snapshotState = {
          ...statePayload,
          is_running: false,
          is_paused: false,
          phase: statePayload?.phase || 'COMPLETED',
          current_bar_index: Number.isFinite(Number(statePayload?.current_bar_index))
            ? Number(statePayload.current_bar_index)
            : rawBars.length,
          total_bars: Number.isFinite(Number(statePayload?.total_bars))
            ? Number(statePayload.total_bars)
            : rawBars.length,
        };
        const totalBars = Number(snapshotState.total_bars || 0);
        const currentBars = Number(snapshotState.current_bar_index || 0);
        snapshotState.progress_pct =
          totalBars > 0
            ? Math.min(100, Math.max(0, (currentBars / totalBars) * 100))
            : Number(snapshotState.progress_pct || 0);

        const nextExecutionConfig = buildEffectiveExecutionConfigSnapshot(summaryPayload);

        setRunKey(nextRunKey);
        setRunState(snapshotState);
        setEffectiveExecutionConfig(nextExecutionConfig);
        setTradeEvaluationMode((prev) => resolveTradeModeFromExecutionConfig(nextExecutionConfig, prev));
        setChartState(null);
        setPriceRange(null);
        setBars(chartBars);
        setMarkers(rawMarkers);
        setSelectedMarker(null);
        setCurrentBar(rawBars.length ? rawBars[rawBars.length - 1] : null);
        setSelectedIntrabar(null);
        setSelectedIntradayLevels(null);
        setIsPlaying(false);
        pendingVisibilitySyncRef.current = false;
        if (parsedRun?.ticker) {
          setSelectedTicker(parsedRun.ticker);
        }
        refreshActiveRuns();
        setRuntimeNotice('');
        return true;
      } catch (error) {
        console.error('Stored snapshot load failed:', error);
        setRuntimeNotice('Stored snapshot load failed.');
        return false;
      } finally {
        setIsReloadingSnapshot(false);
      }
    },
    [
      buildEffectiveExecutionConfigSnapshot,
      hydrateRunSnapshot,
      parseRunKey,
      pendingVisibilitySyncRef,
      readErrorDetail,
      refreshActiveRuns,
      resolveTradeModeFromExecutionConfig,
      setBars,
      setChartState,
      setCurrentBar,
      setEffectiveExecutionConfig,
      setIsPlaying,
      setIsReloadingSnapshot,
      setMarkers,
      setPriceRange,
      setRunKey,
      setRunState,
      setRuntimeNotice,
      setSelectedIntrabar,
      setSelectedIntradayLevels,
      setSelectedMarker,
      setSelectedTicker,
      setTradeEvaluationMode,
      toChartBar,
    ],
  );

  return {
    hydrateRunSnapshot,
    handleStartRun,
    handleKillAndDeleteRun,
    handleReloadBacktest,
    handleAttachActiveRun,
    handleOpenStoredRunSnapshot,
  };
};
