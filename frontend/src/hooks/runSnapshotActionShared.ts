import type {
  Dispatch,
  MutableRefObject,
  SetStateAction,
} from 'react';
import type {
  CandlestickChartBar,
  CandlestickChartPriceRange,
  CandlestickChartVisibleRange,
} from '../components/CandlestickChart';
import { getSupabaseClient } from '../auth/supabaseAuth';

export const V2_JOB_POLL_MS = 1000;

export const normalizeToken = (value: unknown): string => String(value ?? '').trim();

export const readV2JobErrorMessage = (job: any): string => {
  const raw = String(job?.error || '').trim();
  if (!raw) return 'Backtest job failed.';
  try {
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed === 'object') {
      const detail = String(parsed.message || parsed.detail || parsed.error || '').trim();
      if (detail) {
        return detail;
      }
    }
  } catch (_error) {
    // Keep raw payload when the job error is plain text.
  }
  return raw;
};

type RunSnapshotStateSetters = {
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
  setIsPlaying: Dispatch<SetStateAction<boolean>>;
  setTradeEvaluationMode: Dispatch<SetStateAction<string>>;
};

type ResolveTradeMode = (executionConfig: any, fallbackMode?: string) => string;

const resetRunViewportState = (setters: RunSnapshotStateSetters) => {
  setters.setChartState(null);
  setters.setPriceRange(null);
  setters.setSelectedIntrabar(null);
  setters.setSelectedIntradayLevels(null);
};

export const mapSnapshotChartBars = (
  rawBars: any[],
  toChartBar: (bar: any) => CandlestickChartBar | null,
): CandlestickChartBar[] =>
  rawBars
    .map((bar: any) => toChartBar(bar))
    .filter(Boolean)
    .sort((a: CandlestickChartBar, b: CandlestickChartBar) => a.time - b.time) as CandlestickChartBar[];

export const primeStartedRunState = (args: {
  key: string;
  nextExecutionConfig: any;
  pendingVisibilitySyncRef: MutableRefObject<boolean>;
  refreshActiveRuns: () => void;
  resolveTradeModeFromExecutionConfig: ResolveTradeMode;
  setters: RunSnapshotStateSetters;
}) => {
  const {
    key,
    nextExecutionConfig,
    pendingVisibilitySyncRef,
    refreshActiveRuns,
    resolveTradeModeFromExecutionConfig,
    setters,
  } = args;

  setters.setRunKey(key);
  refreshActiveRuns();
  setters.setEffectiveExecutionConfig(nextExecutionConfig);
  setters.setTradeEvaluationMode((prev) =>
    resolveTradeModeFromExecutionConfig(nextExecutionConfig, prev),
  );
  resetRunViewportState(setters);
  setters.setBars([]);
  setters.setMarkers([]);
  setters.setSelectedMarker(null);
  setters.setCurrentBar(null);
  setters.setIsPlaying(false);
  pendingVisibilitySyncRef.current = false;
};

export const applyFetchedRunSnapshotState = (args: {
  targetRunKey: string;
  statePayload: any;
  nextExecutionConfig: any;
  rawBars: any[];
  chartBars: CandlestickChartBar[];
  nextMarkers: any[];
  parsedTicker: string | null;
  resolveTradeModeFromExecutionConfig: ResolveTradeMode;
  setters: RunSnapshotStateSetters;
}) => {
  const {
    targetRunKey,
    statePayload,
    nextExecutionConfig,
    rawBars,
    chartBars,
    nextMarkers,
    parsedTicker,
    resolveTradeModeFromExecutionConfig,
    setters,
  } = args;

  setters.setRunKey(targetRunKey);
  setters.setRunState(statePayload && typeof statePayload === 'object' ? statePayload : null);
  setters.setEffectiveExecutionConfig(nextExecutionConfig);
  resetRunViewportState(setters);
  setters.setBars(chartBars);
  setters.setMarkers(nextMarkers);
  setters.setCurrentBar(rawBars.length ? rawBars[rawBars.length - 1] : null);
  setters.setSelectedMarker((prevSelected: any) => {
    if (!prevSelected?.id) return null;
    return nextMarkers.find((candidate: any) => candidate?.id === prevSelected.id) || null;
  });
  setters.setSelectedTicker(parsedTicker || null);
  setters.setIsPlaying(Boolean(statePayload?.is_running && !statePayload?.is_paused));
  setters.setTradeEvaluationMode((prev) =>
    resolveTradeModeFromExecutionConfig(nextExecutionConfig, prev),
  );
};

export const buildStoredSnapshotState = (statePayload: any, rawBars: any[]) => {
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
  return snapshotState;
};

export const applyStoredRunSnapshotState = (args: {
  nextRunKey: string;
  snapshotState: any;
  nextExecutionConfig: any;
  rawBars: any[];
  chartBars: CandlestickChartBar[];
  rawMarkers: any[];
  parsedTicker: string | null;
  pendingVisibilitySyncRef: MutableRefObject<boolean>;
  resolveTradeModeFromExecutionConfig: ResolveTradeMode;
  setters: RunSnapshotStateSetters;
}) => {
  const {
    nextRunKey,
    snapshotState,
    nextExecutionConfig,
    rawBars,
    chartBars,
    rawMarkers,
    parsedTicker,
    pendingVisibilitySyncRef,
    resolveTradeModeFromExecutionConfig,
    setters,
  } = args;

  setters.setRunKey(nextRunKey);
  setters.setRunState(snapshotState);
  setters.setEffectiveExecutionConfig(nextExecutionConfig);
  setters.setTradeEvaluationMode((prev) =>
    resolveTradeModeFromExecutionConfig(nextExecutionConfig, prev),
  );
  resetRunViewportState(setters);
  setters.setBars(chartBars);
  setters.setMarkers(rawMarkers);
  setters.setSelectedMarker(null);
  setters.setCurrentBar(rawBars.length ? rawBars[rawBars.length - 1] : null);
  setters.setIsPlaying(false);
  pendingVisibilitySyncRef.current = false;
  if (parsedTicker) {
    setters.setSelectedTicker(parsedTicker);
  }
};

export const buildQueuedRunResultPayload = (job: any) =>
  job?.result && typeof job.result === 'object'
    ? { ...job.result, run_key: job.run_key || job.result.run_key }
    : { run_key: job?.run_key || '' };

export const waitForQueuedV2RunJob = (args: {
  jobId: string;
  normalizedAuthToken: string;
  readErrorDetail: (response: Response, fallback: string) => Promise<string>;
  setRuntimeNotice: Dispatch<SetStateAction<string>>;
}) =>
  new Promise<any>((resolve, reject) => {
    const { jobId, normalizedAuthToken, readErrorDetail, setRuntimeNotice } = args;
    const normalizedJobId = String(jobId || '').trim();
    if (!normalizedJobId) {
      reject(new Error('Missing v2 job id.'));
      return;
    }
    if (!normalizedAuthToken) {
      reject(new Error('Missing auth token for v2 run start.'));
      return;
    }

    let settled = false;
    let intervalId: number | null = null;
    let activeChannel: any = null;

    const cleanup = () => {
      if (intervalId !== null && typeof window !== 'undefined') {
        window.clearInterval(intervalId);
        intervalId = null;
      }
      if (activeChannel) {
        const supabase = getSupabaseClient();
        if (supabase) {
          void supabase.removeChannel(activeChannel);
        }
        activeChannel = null;
      }
    };

    const resolveOnce = (payload: any) => {
      if (settled) return;
      settled = true;
      cleanup();
      resolve(payload);
    };

    const rejectOnce = (error: Error) => {
      if (settled) return;
      settled = true;
      cleanup();
      reject(error);
    };

    const handleJobPayload = (jobPayload: any) => {
      const job = jobPayload && typeof jobPayload === 'object' ? jobPayload : {};
      const status = String(job?.status || '').trim().toLowerCase();
      if (status === 'queued') {
        setRuntimeNotice(
          `Backtest queued (${normalizedJobId.slice(0, 8)}). Waiting for worker slot...`,
        );
        return;
      }
      if (status === 'running') {
        setRuntimeNotice(
          `Backtest starting (${normalizedJobId.slice(0, 8)}). Loading run state...`,
        );
        return;
      }
      if (status === 'completed') {
        setRuntimeNotice('');
        resolveOnce(job);
        return;
      }
      if (status === 'failed') {
        rejectOnce(new Error(readV2JobErrorMessage(job)));
      }
    };

    const fetchJob = async () => {
      if (settled) return;
      try {
        const response = await fetch(`/api/v2/jobs/${normalizedJobId}`, {
          headers: {
            Authorization: `Bearer ${normalizedAuthToken}`,
          },
        });
        if (!response.ok) {
          const detail = await readErrorDetail(response, `HTTP ${response.status}`);
          throw new Error(detail || `Failed to load run job ${normalizedJobId}`);
        }
        const payload = await response.json();
        handleJobPayload(payload?.job);
      } catch (error) {
        rejectOnce(
          error instanceof Error ? error : new Error('Failed to load v2 run job state.'),
        );
      }
    };

    const supabase = getSupabaseClient();
    if (supabase) {
      activeChannel = supabase
        .channel(`backtest-run-job:${normalizedJobId}:${Date.now()}`)
        .on(
          'postgres_changes',
          {
            event: '*',
            schema: 'public',
            table: 'run_jobs',
            filter: `id=eq.${normalizedJobId}`,
          },
          (message: any) => {
            const row =
              message?.new && typeof message.new === 'object'
                ? message.new
                : message?.record && typeof message.record === 'object'
                  ? message.record
                  : null;
            if (!row) return;
            handleJobPayload({
              status: row.status,
              error: row.error,
              run_key: row.run_key,
              result: row.result,
            });
          },
        )
        .subscribe();
    }

    void fetchJob();
    if (typeof window !== 'undefined') {
      intervalId = window.setInterval(() => {
        void fetchJob();
      }, V2_JOB_POLL_MS);
    }
  });
