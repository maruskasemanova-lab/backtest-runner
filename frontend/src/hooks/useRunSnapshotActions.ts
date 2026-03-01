import {
  useCallback,
  useEffect,
  useMemo,
  type Dispatch,
  type MutableRefObject,
  type SetStateAction,
} from 'react';
import type {
  CandlestickChartBar,
  CandlestickChartPriceRange,
  CandlestickChartVisibleRange,
} from '../components/CandlestickChart';
import {
  applyFetchedRunSnapshotState,
  applyStoredRunSnapshotState,
  buildQueuedRunResultPayload,
  buildStoredSnapshotState,
  mapSnapshotChartBars,
  normalizeToken,
  primeStartedRunState,
  waitForQueuedV2RunJob,
} from './runSnapshotActionShared';

type UseRunSnapshotActionsArgs = {
  runKey: string | null;
  activeRunApiBase: string | null;
  authToken: string;
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
  authToken,
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
  const normalizedAuthToken = normalizeToken(authToken);
  const runSnapshotStateSetters = useMemo(
    () => ({
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
      setIsPlaying,
      setTradeEvaluationMode,
    }),
    [
      setBars,
      setChartState,
      setCurrentBar,
      setEffectiveExecutionConfig,
      setIsPlaying,
      setMarkers,
      setPriceRange,
      setRunKey,
      setRunState,
      setSelectedIntrabar,
      setSelectedIntradayLevels,
      setSelectedMarker,
      setSelectedTicker,
      setTradeEvaluationMode,
    ],
  );
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
        const chartBars = mapSnapshotChartBars(rawBars, toChartBar);
        const nextMarkers = Array.isArray(markersPayload) ? markersPayload : [];
        applyFetchedRunSnapshotState({
          targetRunKey,
          statePayload,
          nextExecutionConfig,
          rawBars,
          chartBars,
          nextMarkers,
          parsedTicker: parsed.ticker || null,
          resolveTradeModeFromExecutionConfig,
          setters: runSnapshotStateSetters,
        });
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
      setIsReloadingSnapshot,
      runSnapshotStateSetters,
      toChartBar,
    ],
  );

  const applyStartedRun = useCallback(
    async (data: any, config: any) => {
      const key = String(data?.run_key || '').trim();
      const parsedRun = parseRunKey(key);
      if (!parsedRun) {
        throw new Error('Invalid run key returned by backend.');
      }

      const nextExecutionConfig = buildEffectiveExecutionConfigSnapshot(data);
      primeStartedRunState({
        key,
        nextExecutionConfig,
        pendingVisibilitySyncRef,
        refreshActiveRuns,
        resolveTradeModeFromExecutionConfig,
        setters: runSnapshotStateSetters,
      });

      const runApiBase = buildRunApiBase(parsedRun);
      if (!runApiBase) {
        throw new Error('Invalid run path returned by backend.');
      }
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
          const chartBars = mapSnapshotChartBars(rawBars, toChartBar);
          if (chartBars.length > 0) {
            setBars(chartBars);
            setCurrentBar(rawBars[rawBars.length - 1] || null);
          }
        }
      } catch (barsError) {
        console.debug('Initial bars snapshot load failed:', barsError);
      }

      if (String(config?.ticker || '').trim()) {
        setSelectedTicker(String(config.ticker || '').trim().toUpperCase());
      }
      return data;
    },
    [
      buildEffectiveExecutionConfigSnapshot,
      buildRunApiBase,
      parseRunKey,
      pendingVisibilitySyncRef,
      readErrorDetail,
      refreshActiveRuns,
      resolveTradeModeFromExecutionConfig,
      runSnapshotStateSetters,
      setBars,
      setCurrentBar,
      setRunState,
      setSelectedTicker,
      toChartBar,
    ],
  );

  const waitForV2RunJob = useCallback(
    async (jobId: string) =>
      waitForQueuedV2RunJob({
        jobId,
        normalizedAuthToken,
        readErrorDetail,
        setRuntimeNotice,
      }),
    [normalizedAuthToken, readErrorDetail, setRuntimeNotice],
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
        const clientHint = String(config?.__client_hint || "")
          .trim()
          .toLowerCase();
        const preferDirectStart = clientHint === "strategy_analyzer";
        const requestPayload = { ...(config || {}) };
        delete requestPayload.__client_hint;

        setRuntimeNotice('');
        setSelectedTicker(requestPayload.ticker || null);
        setStrategyApiUrl(requestPayload.strategy_api_url || defaultStrategyApiUrl);
        if (normalizedAuthToken && !preferDirectStart) {
          const queuedResponse = await fetch('/api/v2/runs', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              Authorization: `Bearer ${normalizedAuthToken}`,
            },
            body: JSON.stringify(requestPayload),
          });

          if (!queuedResponse.ok) {
            const detail = await readErrorDetail(queuedResponse, `HTTP ${queuedResponse.status}`);
            throw new Error(detail || 'Failed to queue run');
          }

          const queuedPayload = await queuedResponse.json();
          const jobId = String(queuedPayload?.job_id || '').trim();
          if (!jobId) {
            throw new Error('Missing v2 job id returned by backend.');
          }
          setRuntimeNotice(`Backtest queued (${jobId.slice(0, 8)}). Waiting for worker slot...`);
          const job = await waitForV2RunJob(jobId);
          const resultPayload = buildQueuedRunResultPayload(job);
          return await applyStartedRun(resultPayload, requestPayload);
        }

        const response = await fetch('/api/run/start', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(requestPayload),
        });

        if (!response.ok) {
          const detail = await readErrorDetail(response, `HTTP ${response.status}`);
          throw new Error(detail || 'Failed to start run');
        }

        const data = await response.json();
        return await applyStartedRun(data, requestPayload);
      } catch (error) {
        const message = String(error instanceof Error ? error.message : '');
        if (!runIdCollisionPattern.test(message)) {
          console.error('Start run error:', error);
        }
        throw error;
      }
    },
    [
      applyStartedRun,
      defaultStrategyApiUrl,
      normalizedAuthToken,
      readErrorDetail,
      runIdCollisionPattern,
      setRuntimeNotice,
      setSelectedTicker,
      setStrategyApiUrl,
      waitForV2RunJob,
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
        const chartBars = mapSnapshotChartBars(rawBars, toChartBar);

        const nextRunKey = String(payload?.run_key || normalizedRunKey).trim() || normalizedRunKey;
        const parsedRun = parseRunKey(nextRunKey) || parseRunKey(normalizedRunKey);
        const snapshotState = buildStoredSnapshotState(statePayload, rawBars);

        const nextExecutionConfig = buildEffectiveExecutionConfigSnapshot(summaryPayload);
        applyStoredRunSnapshotState({
          nextRunKey,
          snapshotState,
          nextExecutionConfig,
          rawBars,
          chartBars,
          rawMarkers,
          parsedTicker: parsedRun?.ticker || null,
          pendingVisibilitySyncRef,
          resolveTradeModeFromExecutionConfig,
          setters: runSnapshotStateSetters,
        });
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
      setIsReloadingSnapshot,
      setRuntimeNotice,
      runSnapshotStateSetters,
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
