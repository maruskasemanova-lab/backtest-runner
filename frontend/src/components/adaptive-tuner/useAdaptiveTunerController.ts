import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  DEFAULT_ADAPTIVE_TUNER_FORM,
  buildAdaptiveTunerRunPayload,
  formatDurationCompact,
  getProfileCreatedMs,
  getProfileTrades,
  parseTimestampMs,
  upsertJobInHistory,
} from "./adaptiveTunerControllerHelpers";

interface UseAdaptiveTunerControllerArgs {
  selectedTicker?: string;
  onTickerChange?: (ticker: string) => void;
  strategyApiUrl?: string;
}

export type ResultsTab = "profiles" | "trials" | "analysis";
type ProfileSortField = "score" | "date" | "trades";
type SortDirection = "asc" | "desc";

export interface ProfileFilterState {
  version: "all" | "1" | "2";
  dateFrom: string;
  dateTo: string;
}

export interface ProfileSortState {
  field: ProfileSortField;
  direction: SortDirection;
}

export interface EtaEstimate {
  label: string;
  remainingMs: number | null;
  etaAt: string | null;
}

export const DEFAULT_FORM = DEFAULT_ADAPTIVE_TUNER_FORM;

export function useAdaptiveTunerController({
  selectedTicker,
  onTickerChange,
  strategyApiUrl,
}: UseAdaptiveTunerControllerArgs) {
  const lastUserTickerRef = useRef<string | null>(null);
  const [availableData, setAvailableData] = useState<Record<string, any> | null>(null);
  const [form, setForm] = useState(DEFAULT_FORM);
  const [tickerOptions, setTickerOptions] = useState<Record<string, any> | null>(null);
  const [jobHistory, setJobHistory] = useState<Record<string, any>[]>([]);
  const [loadingTickerOptions, setLoadingTickerOptions] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [applyingProfileId, setApplyingProfileId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [job, setJob] = useState<Record<string, any> | null>(null);
  const [selectedTrialIndex, setSelectedTrialIndex] = useState<number | null>(null);
  const [resultsTab, setResultsTab] = useState<ResultsTab>("profiles");
  const [profileFilter, setProfileFilter] = useState<ProfileFilterState>({
    version: "all",
    dateFrom: "",
    dateTo: "",
  });
  const [profileSort, setProfileSort] = useState<ProfileSortState>({
    field: "score",
    direction: "desc",
  });
  const [configPanelCollapsed, setConfigPanelCollapsed] = useState(false);

  const isV2 = Number(form.adaptive_version) === 2;

  const fetchJobHistory = useCallback(async () => {
    try {
      const resp = await fetch("/api/adaptive-tuner?limit=20");
      if (!resp.ok) {
        throw new Error(`Failed to fetch adaptive tuner jobs (HTTP ${resp.status})`);
      }
      const payload = await resp.json();
      const history = Array.isArray(payload) ? payload : [];
      setJobHistory(history);
      setSelectedJobId((prev) => {
        if (
          prev &&
          (history.some((item) => String(item?.job_id || "") === prev) || prev === activeJobId)
        ) {
          return prev;
        }
        if (activeJobId) return activeJobId;
        const firstJobId = String(history[0]?.job_id || "").trim();
        return firstJobId || prev;
      });
    } catch (err) {
      console.error("Failed to load adaptive tuner job history:", err);
    }
  }, [activeJobId]);

  const refreshTickerOptions = useCallback(async (ticker: string, { forceDates = false } = {}) => {
    const upper = String(ticker || "").toUpperCase().trim();
    if (!upper) return;

    setLoadingTickerOptions(true);
    try {
      const resp = await fetch(`/api/adaptive-tuner/options/${upper}`);
      if (!resp.ok) {
        throw new Error(`Failed to load tuner options for ${upper}`);
      }
      const payload = await resp.json();
      setTickerOptions(payload);

      setForm((prev) => {
        const hasDates = !!prev.date_from && !!prev.date_to;
        const nextFrom = payload?.default_date_from || prev.date_from;
        const nextTo = payload?.default_date_to || prev.date_to;
        return {
          ...prev,
          ticker: upper,
          date_from: forceDates || !hasDates ? nextFrom : prev.date_from,
          date_to: forceDates || !hasDates ? nextTo : prev.date_to,
        };
      });
    } catch (err: any) {
      setError(err.message || String(err));
    } finally {
      setLoadingTickerOptions(false);
    }
  }, []);

  useEffect(() => {
    const loadAvailableData = async () => {
      try {
        const resp = await fetch("/api/available-data?refresh=1");
        if (!resp.ok) return;
        const payload = await resp.json();
        setAvailableData(payload);

        const tickers = Array.isArray(payload?.tickers)
          ? payload.tickers.map((ticker: string) => String(ticker).toUpperCase())
          : [];
        if (!tickers.length) return;

        const fallbackTicker = selectedTicker || (tickers.includes("MU") ? "MU" : tickers[0]);
        let resolvedTicker = fallbackTicker;
        const lastUserTicker = String(lastUserTickerRef.current || "").toUpperCase().trim();

        if (!selectedTicker && lastUserTicker && tickers.includes(lastUserTicker)) {
          resolvedTicker = lastUserTicker;
        }

        setForm((prev) => {
          const prevTicker = String(prev.ticker || "").toUpperCase().trim();
          if (prevTicker && tickers.includes(prevTicker)) {
            resolvedTicker = prevTicker;
          }
          return { ...prev, ticker: resolvedTicker };
        });
        await refreshTickerOptions(resolvedTicker, { forceDates: true });

        if (!selectedTicker && onTickerChange) {
          onTickerChange(resolvedTicker);
        }
      } catch (err) {
        console.error("Failed to load available data for tuner:", err);
      }
    };

    loadAvailableData();
  }, [onTickerChange, refreshTickerOptions, selectedTicker]);

  useEffect(() => {
    fetchJobHistory();
  }, [fetchJobHistory]);

  useEffect(() => {
    if (!selectedTicker) return;
    const upper = String(selectedTicker).toUpperCase();
    lastUserTickerRef.current = upper;
    setForm((prev) => {
      if (upper === String(prev.ticker || "").toUpperCase()) {
        return prev;
      }
      return { ...prev, ticker: upper };
    });
    refreshTickerOptions(upper, { forceDates: true });
  }, [refreshTickerOptions, selectedTicker]);

  useEffect(() => {
    if (activeJobId) {
      setConfigPanelCollapsed(true);
    }
  }, [activeJobId]);

  useEffect(() => {
    if (!selectedJobId) return undefined;
    setSelectedTrialIndex(null);

    let cancelled = false;
    const loadSelectedJob = async () => {
      const historyMatch = jobHistory.find(
        (item) => String(item?.job_id || "") === selectedJobId,
      );
      if (historyMatch && !cancelled) {
        setJob(historyMatch);
      }

      try {
        const resp = await fetch(`/api/adaptive-tuner/${selectedJobId}`);
        if (!resp.ok) {
          throw new Error(`Failed to load tuner job ${selectedJobId}`);
        }
        const payload = await resp.json();
        if (cancelled) return;
        setJob(payload);

        const status = String(payload?.status || "").toLowerCase();
        if ((status === "running" || status === "queued") && !activeJobId) {
          setActiveJobId(selectedJobId);
        }
      } catch (err: any) {
        if (!cancelled) {
          setError(err.message || String(err));
        }
      }
    };

    loadSelectedJob();
    return () => {
      cancelled = true;
    };
  }, [activeJobId, selectedJobId]);

  useEffect(() => {
    if (!activeJobId) return undefined;

    let cancelled = false;
    const poll = async () => {
      try {
        const resp = await fetch(`/api/adaptive-tuner/${activeJobId}`);
        if (!resp.ok) {
          if (!cancelled) {
            setError(`Failed to fetch tuner job ${activeJobId}`);
          }
          return;
        }
        const payload = await resp.json();
        if (cancelled) return;
        setJobHistory((prev) => upsertJobInHistory(prev, payload));
        if (!selectedJobId || selectedJobId === activeJobId) {
          setJob(payload);
        }

        const status = String(payload?.status || "").toLowerCase();
        if (status === "completed") {
          setNotice("Adaptive tuning finished.");
          setSubmitting(false);
          setActiveJobId(null);
          setSelectedJobId((prev) => prev || activeJobId);
          const bestIndex = payload?.best_trial?.trial_index;
          if (Number.isFinite(bestIndex)) {
            setSelectedTrialIndex(bestIndex);
          }
          await Promise.all([
            refreshTickerOptions(form.ticker, { forceDates: false }),
            fetchJobHistory(),
          ]);
        } else if (status === "failed") {
          setSubmitting(false);
          setActiveJobId(null);
          setError(payload?.error || "Adaptive tuning failed.");
          await fetchJobHistory();
        }
      } catch (err: any) {
        if (!cancelled) {
          setError(`Tuner poll error: ${err.message}`);
          setSubmitting(false);
          setActiveJobId(null);
        }
      }
    };

    poll();
    const interval = setInterval(poll, 1000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [activeJobId, fetchJobHistory, form.ticker, refreshTickerOptions, selectedJobId]);

  const sortedTrials = useMemo(() => {
    const trials = Array.isArray(job?.trials) ? [...job.trials] : [];
    trials.sort((a, b) => Number(b?.score || 0) - Number(a?.score || 0));
    return trials;
  }, [job]);

  const selectedTrial = useMemo(() => {
    if (!Array.isArray(job?.trials) || !job.trials.length) return null;
    if (selectedTrialIndex === null || selectedTrialIndex === undefined) {
      return job?.best_trial || job.trials[0];
    }
    return job.trials.find((trial: Record<string, any>) => trial?.trial_index === selectedTrialIndex) || null;
  }, [job, selectedTrialIndex]);

  const progressPct = useMemo(() => {
    const completed = Number(job?.progress?.completed_trials || 0);
    const total = Number(job?.progress?.total_trials || 0);
    if (total <= 0) return 0;
    return Math.max(0, Math.min(100, (completed / total) * 100));
  }, [job]);

  const effectiveTrialBudgetPreview = useMemo(() => {
    const requested = Math.max(1, Number(form.n_trials || (isV2 ? 32 : 16)));
    const boost = form.quick_mode
      ? Math.max(1, Number(form.quick_trial_boost || 3))
      : 1;
    return {
      requested,
      boost,
      effective: Math.min(400, requested * boost),
    };
  }, [form.n_trials, form.quick_mode, form.quick_trial_boost, isV2]);

  const profileList = useMemo(() => {
    return Array.isArray(tickerOptions?.profiles) ? tickerOptions.profiles : [];
  }, [tickerOptions]);

  const filteredSortedProfiles = useMemo(() => {
    const filtered = profileList.filter((profile: Record<string, any>) => {
      const version = String(profile?.adaptive_version ?? "");
      if (profileFilter.version !== "all" && version !== profileFilter.version) {
        return false;
      }

      const createdMs = getProfileCreatedMs(profile);
      const createdDate =
        createdMs > 0 ? new Date(createdMs).toISOString().slice(0, 10) : "";
      if (profileFilter.dateFrom && (!createdDate || createdDate < profileFilter.dateFrom)) {
        return false;
      }
      if (profileFilter.dateTo && (!createdDate || createdDate > profileFilter.dateTo)) {
        return false;
      }
      return true;
    });

    const directionFactor = profileSort.direction === "asc" ? 1 : -1;
    filtered.sort((left: Record<string, any>, right: Record<string, any>) => {
      let compare = 0;
      if (profileSort.field === "score") {
        compare = Number(left?.score || 0) - Number(right?.score || 0);
      } else if (profileSort.field === "trades") {
        compare = getProfileTrades(left) - getProfileTrades(right);
      } else {
        compare = getProfileCreatedMs(left) - getProfileCreatedMs(right);
      }
      if (compare === 0) {
        compare = getProfileCreatedMs(left) - getProfileCreatedMs(right);
      }
      return compare * directionFactor;
    });
    return filtered;
  }, [profileFilter, profileList, profileSort]);

  const tickerOptionsList = useMemo(
    () =>
      Array.isArray(availableData?.tickers)
        ? availableData.tickers.map((ticker: string) => String(ticker).toUpperCase())
        : [],
    [availableData],
  );

  const bestTrial = useMemo(() => job?.best_trial || null, [job]);

  const jobVersion = Number(job?.adaptive_version || job?.request?.adaptive_version || form.adaptive_version || 1);
  const jobQuickMode = Boolean(job?.quick_mode || job?.summary?.quick_mode);
  const jobTrialBudget = job?.trial_budget;
  const vectorAnalysis = job?.vector_analysis || null;
  const etaEstimate = useMemo<EtaEstimate | null>(() => {
    if (!job) return null;
    const status = String(job?.status || "").toLowerCase();
    if (status === "queued") {
      return { label: "Queued", remainingMs: null, etaAt: null };
    }
    if (status !== "running") return null;

    const completed = Number(job?.progress?.completed_trials || 0);
    const total = Number(job?.progress?.total_trials || 0);
    if (total <= 0) {
      return { label: "Estimating...", remainingMs: null, etaAt: null };
    }
    if (completed >= total) {
      const nowIso = new Date().toISOString();
      return { label: "0s", remainingMs: 0, etaAt: nowIso };
    }

    const startedMs = parseTimestampMs(job?.started_at || job?.created_at);
    if (!startedMs || completed <= 0) {
      return { label: "Estimating...", remainingMs: null, etaAt: null };
    }

    const elapsedMs = Math.max(0, Date.now() - startedMs);
    if (elapsedMs <= 0) {
      return { label: "Estimating...", remainingMs: null, etaAt: null };
    }

    const remainingTrials = Math.max(0, total - completed);
    const msPerTrial = elapsedMs / Math.max(1, completed);
    const remainingMs = Math.round(remainingTrials * msPerTrial);
    return {
      label: formatDurationCompact(remainingMs),
      remainingMs,
      etaAt: new Date(Date.now() + remainingMs).toISOString(),
    };
  }, [job]);

  const handleStart = useCallback(async () => {
    setSubmitting(true);
    setError(null);
    setNotice(null);
    setJob(null);
    setSelectedTrialIndex(null);
    setResultsTab("trials");
    setConfigPanelCollapsed(true);

    try {
      if (!form.ticker) {
        throw new Error("Ticker is required.");
      }
      if (!form.date_from || !form.date_to) {
        throw new Error("Date range is required.");
      }

      const { version, payload } = buildAdaptiveTunerRunPayload({
        form,
        strategyApiUrl,
      });

      const resp = await fetch("/api/adaptive-tuner/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        throw new Error(data?.detail || `HTTP ${resp.status}`);
      }
      const data = await resp.json();
      setActiveJobId(data.job_id);
      setSelectedJobId(data.job_id);
      setNotice(
        `Adaptive tuner v${version} job queued: ${data.job_id} (${data.effective_days || 0} effective days)`,
      );
      await fetchJobHistory();
    } catch (err: any) {
      setSubmitting(false);
      setError(err.message || String(err));
    }
  }, [fetchJobHistory, form, strategyApiUrl]);

  const handleApplyProfile = useCallback(async (profileId: string) => {
    if (!form.ticker || !profileId) return;
    setApplyingProfileId(profileId);
    setError(null);
    setNotice(null);
    try {
      const resp = await fetch("/api/adaptive-tuner/profiles/apply", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ticker: form.ticker, profile_id: profileId }),
      });
      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        throw new Error(data?.detail || `HTTP ${resp.status}`);
      }
      setNotice(
        `Applied adaptive profile ${profileId} for ${form.ticker}. It will be used on next Backtest run start.`,
      );
      await refreshTickerOptions(form.ticker, { forceDates: false });
    } catch (err: any) {
      setError(err.message || String(err));
    } finally {
      setApplyingProfileId(null);
    }
  }, [form.ticker, refreshTickerOptions]);

  const handleTickerChange = useCallback(async (ticker: string) => {
    const upper = String(ticker || "").toUpperCase();
    lastUserTickerRef.current = upper;
    setForm((prev) => ({ ...prev, ticker: upper }));
    if (onTickerChange) {
      onTickerChange(upper);
    }
    await refreshTickerOptions(upper, { forceDates: true });
  }, [onTickerChange, refreshTickerOptions]);

  return {
    availableData,
    form,
    setForm,
    tickerOptions,
    jobHistory,
    loadingTickerOptions,
    submitting,
    applyingProfileId,
    error,
    setError,
    notice,
    setNotice,
    activeJobId,
    selectedJobId,
    setSelectedJobId,
    job,
    selectedTrialIndex,
    setSelectedTrialIndex,
    resultsTab,
    setResultsTab,
    profileFilter,
    setProfileFilter,
    profileSort,
    setProfileSort,
    filteredSortedProfiles,
    isV2,
    etaEstimate,
    configPanelCollapsed,
    setConfigPanelCollapsed,
    fetchJobHistory,
    refreshTickerOptions,
    sortedTrials,
    selectedTrial,
    progressPct,
    effectiveTrialBudgetPreview,
    profileList,
    tickerOptionsList,
    bestTrial,
    jobVersion,
    jobQuickMode,
    jobTrialBudget,
    vectorAnalysis,
    handleStart,
    handleApplyProfile,
    handleTickerChange,
  };
}

export type AdaptiveTunerControllerModel = ReturnType<typeof useAdaptiveTunerController>;
