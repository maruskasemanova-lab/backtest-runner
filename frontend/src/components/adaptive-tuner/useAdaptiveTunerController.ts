import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { defaultStrategyApiUrl } from "../../utils";

interface UseAdaptiveTunerControllerArgs {
  selectedTicker?: string;
  onTickerChange?: (ticker: string) => void;
  strategyApiUrl?: string;
}

type ResultsTab = "profiles" | "trials" | "analysis";
type ProfileSortField = "score" | "date" | "trades";
type SortDirection = "asc" | "desc";

interface ProfileFilterState {
  version: "all" | "1" | "2";
  dateFrom: string;
  dateTo: string;
}

interface ProfileSortState {
  field: ProfileSortField;
  direction: SortDirection;
}

interface EtaEstimate {
  label: string;
  remainingMs: number | null;
  etaAt: string | null;
}

export const DEFAULT_FORM = {
  ticker: "",
  date_from: "",
  date_to: "",
  method: "grid",
  adaptive_version: 1,
  n_trials: 16,
  score_metric: "pnl_pct",
  seed: 42,
  persist_best: false,
  l2_required: true,
  l2_only: false,
  quick_mode: false,
  quick_max_days: 2,
  quick_trial_boost: 3,
  selection_modes: "adaptive_top_n,all_enabled",
  max_active_options: "1,2,3,4,5",
  min_active_bars_options: "0,2,4,8,12",
  switch_cooldown_bars_options: "0,1,2,4,8",
  flow_bias_options: "true,false",
  ohlcv_fallback_options: "true,false",
  v2_strategy_sets: "",
  v2_l2_min_imbalance: "0.05,0.12,0.25",
  v2_l2_min_delta: "",
  v2_regime_filter_sets: "",
  v2_base_threshold: "45,55,65",
  v2_min_confirming_sources: "2,3",
  v2_min_confidence: "50,55,60,65",
  v2_atr_stop_multiplier: "0.7,1.0,1.3,1.8",
  v2_rr_ratio: "1.5,2.0,2.5,3.0",
  v2_time_windows: "9,10;9,10,11,12;9,10,11,12,13,14,15",
  v2_adverse_flow_consistency: "0.35,0.45,0.55",
  v2_adverse_book_pressure: "0.10,0.15,0.22",
  v2_time_exit_bars: "15,25,35,50",
  v2_trailing_stop_pct: "0.4,0.6,0.8,1.0,1.3",
  neighborhood_search: true,
};

const parseIntCsv = (value: unknown, { min = 0, max = 1000 } = {}) => {
  const source = String(value || "").trim();
  if (!source) return null;
  const out: number[] = [];
  const seen = new Set<number>();
  source
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
    .forEach((token) => {
      const parsed = Number(token);
      if (!Number.isFinite(parsed) || !Number.isInteger(parsed)) {
        throw new Error(`Invalid integer list value: ${token}`);
      }
      const clamped = Math.max(min, Math.min(max, parsed));
      if (seen.has(clamped)) return;
      seen.add(clamped);
      out.push(clamped);
    });
  return out.length ? out : null;
};

const parseFloatCsv = (value: unknown, { min = 0, max = 1000 } = {}) => {
  const source = String(value || "").trim();
  if (!source) return null;
  const out: number[] = [];
  const seen = new Set<number>();
  source
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
    .forEach((token) => {
      const parsed = Number(token);
      if (!Number.isFinite(parsed)) {
        throw new Error(`Invalid float list value: ${token}`);
      }
      const clamped = Math.max(min, Math.min(max, parsed));
      const rounded = Math.round(clamped * 10000) / 10000;
      if (seen.has(rounded)) return;
      seen.add(rounded);
      out.push(rounded);
    });
  return out.length ? out : null;
};

const parseBoolCsv = (value: unknown) => {
  const source = String(value || "").trim();
  if (!source) return null;
  const out: boolean[] = [];
  const seen = new Set<boolean>();
  source
    .split(",")
    .map((item) => item.trim().toLowerCase())
    .filter(Boolean)
    .forEach((token) => {
      let current: boolean;
      if (["true", "1", "yes", "on"].includes(token)) {
        current = true;
      } else if (["false", "0", "no", "off"].includes(token)) {
        current = false;
      } else {
        throw new Error(`Invalid boolean list value: ${token}`);
      }
      if (seen.has(current)) return;
      seen.add(current);
      out.push(current);
    });
  return out.length ? out : null;
};

const parseModeCsv = (value: unknown) => {
  const source = String(value || "").trim();
  if (!source) return null;
  const out: string[] = [];
  const seen = new Set<string>();
  source
    .split(",")
    .map((item) => item.trim().toLowerCase())
    .filter(Boolean)
    .forEach((token) => {
      const current = token === "all_enabled" ? "all_enabled" : "adaptive_top_n";
      if (seen.has(current)) return;
      seen.add(current);
      out.push(current);
    });
  return out.length ? out : null;
};

const parseStrategySets = (value: unknown) => {
  const source = String(value || "").trim();
  if (!source) return null;
  const sets = source
    .split(";")
    .map((group) =>
      group
        .split(",")
        .map((s) => s.trim().toLowerCase())
        .filter(Boolean),
    )
    .filter((group) => group.length > 0);
  return sets.length > 0 ? sets : null;
};

const parseRegimeFilterSets = (value: unknown) => {
  const source = String(value || "").trim();
  if (!source) return null;
  const valid = new Set(["TRENDING", "CHOPPY", "MIXED"]);
  const sets = source
    .split(";")
    .map((group) =>
      group
        .split(",")
        .map((s) => s.trim().toUpperCase())
        .filter((s) => valid.has(s)),
    )
    .filter((group) => group.length > 0);
  return sets.length > 0 ? sets : null;
};

const parseTimestampMs = (value: unknown) => {
  if (value === null || value === undefined) return null;
  const parsed = Date.parse(String(value));
  if (Number.isNaN(parsed)) return null;
  return parsed;
};

const formatDurationCompact = (ms: number) => {
  const totalSeconds = Math.max(0, Math.round(ms / 1000));
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  if (hours > 0) return `${hours}h ${minutes}m`;
  if (minutes > 0) return `${minutes}m ${seconds}s`;
  return `${seconds}s`;
};

const upsertJobInHistory = (history: Record<string, any>[], job: Record<string, any>) => {
  const nextJobId = String(job?.job_id || "").trim();
  if (!nextJobId) return history;
  const merged = [job, ...history.filter((row) => String(row?.job_id || "") !== nextJobId)];
  merged.sort((a, b) => {
    const left = parseTimestampMs(a?.created_at) || 0;
    const right = parseTimestampMs(b?.created_at) || 0;
    return right - left;
  });
  return merged.slice(0, 20);
};

const getProfileTrades = (profile: Record<string, any>) =>
  Number(profile?.metrics?.total_trades ?? profile?.metrics?.trades ?? 0);

const getProfileCreatedMs = (profile: Record<string, any>) =>
  parseTimestampMs(profile?.created_at) ?? 0;

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

      const version = Number(form.adaptive_version || 1);

      const payload: Record<string, any> = {
        ticker: form.ticker,
        date_from: form.date_from,
        date_to: form.date_to,
        strategy_api_url: strategyApiUrl || defaultStrategyApiUrl,
        method: version === 2 ? (form.method === "grid" ? "random" : form.method) : form.method,
        adaptive_version: version,
        n_trials: Number(form.n_trials || (version === 2 ? 32 : 16)),
        score_metric: form.score_metric,
        seed: Number(form.seed || 42),
        persist_best: !!form.persist_best,
        l2_required: !!form.l2_required,
        l2_confirm_enabled: true,
        l2_only: !!form.l2_only,
        quick_mode: !!form.quick_mode,
        quick_max_days: Math.max(1, Math.min(30, Number(form.quick_max_days || 2))),
        quick_trial_boost: Math.max(1, Math.min(10, Number(form.quick_trial_boost || 3))),
      };

      if (version === 1) {
        payload.selection_modes = parseModeCsv(form.selection_modes);
        payload.max_active_options = parseIntCsv(form.max_active_options, { min: 1, max: 20 });
        payload.min_active_bars_options = parseIntCsv(form.min_active_bars_options, { min: 0, max: 500 });
        payload.switch_cooldown_bars_options = parseIntCsv(form.switch_cooldown_bars_options, { min: 0, max: 500 });
        payload.flow_bias_options = parseBoolCsv(form.flow_bias_options);
        payload.ohlcv_fallback_options = parseBoolCsv(form.ohlcv_fallback_options);
      } else {
        const strategySets = parseStrategySets(form.v2_strategy_sets);
        if (strategySets) payload.strategy_sets = strategySets;

        const l2Imb = parseFloatCsv(form.v2_l2_min_imbalance, { min: 0, max: 1 });
        if (l2Imb) payload.l2_min_imbalance_options = l2Imb;

        const l2Delta = parseFloatCsv(form.v2_l2_min_delta, { min: 0, max: 10000 });
        if (l2Delta) payload.l2_min_delta_options = l2Delta;

        const regimeSets = parseRegimeFilterSets(form.v2_regime_filter_sets);
        if (regimeSets) payload.regime_filter_sets = regimeSets;

        const baseThr = parseIntCsv(form.v2_base_threshold, { min: 0, max: 100 });
        if (baseThr) payload.base_threshold_options = baseThr;

        const minSrc = parseIntCsv(form.v2_min_confirming_sources, { min: 1, max: 10 });
        if (minSrc) payload.min_confirming_sources_options = minSrc;

        const minConf = parseFloatCsv(form.v2_min_confidence, { min: 30, max: 90 });
        if (minConf) payload.min_confidence_options = minConf;

        const atrStop = parseFloatCsv(form.v2_atr_stop_multiplier, { min: 0.3, max: 4 });
        if (atrStop) payload.atr_stop_multiplier_options = atrStop;

        const rrRatio = parseFloatCsv(form.v2_rr_ratio, { min: 1, max: 5 });
        if (rrRatio) payload.rr_ratio_options = rrRatio;

        const rawTW = String(form.v2_time_windows || "").trim();
        if (rawTW) {
          const twSets = rawTW
            .split(";")
            .map((s) => {
              const hours = s
                .split(",")
                .map((h) => parseInt(h.trim(), 10))
                .filter((h) => !Number.isNaN(h) && h >= 0 && h <= 23);
              return hours;
            })
            .filter((h) => h.length > 0);
          if (twSets.length) payload.time_window_sets = twSets;
        }

        const afConsistency = parseFloatCsv(form.v2_adverse_flow_consistency, { min: 0.1, max: 0.9 });
        if (afConsistency) payload.adverse_flow_consistency_options = afConsistency;
        const abPressure = parseFloatCsv(form.v2_adverse_book_pressure, { min: 0.05, max: 0.5 });
        if (abPressure) payload.adverse_book_pressure_options = abPressure;

        const teBarsParsed = parseIntCsv(form.v2_time_exit_bars, { min: 5, max: 120 });
        if (teBarsParsed) payload.time_exit_bars_options = teBarsParsed;
        const tsPctParsed = parseFloatCsv(form.v2_trailing_stop_pct, { min: 0.1, max: 3.0 });
        if (tsPctParsed) payload.trailing_stop_pct_options = tsPctParsed;

        if (form.neighborhood_search) {
          payload.neighborhood_search = true;
        }

        payload.selection_modes = parseModeCsv(form.selection_modes);
        payload.max_active_options = parseIntCsv(form.max_active_options, { min: 1, max: 20 });
      }

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
