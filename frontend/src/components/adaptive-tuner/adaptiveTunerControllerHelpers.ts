import { defaultStrategyApiUrl } from "../../utils";

export const DEFAULT_ADAPTIVE_TUNER_FORM = {
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

export type AdaptiveTunerFormState = typeof DEFAULT_ADAPTIVE_TUNER_FORM;

export const parseIntCsv = (value: unknown, { min = 0, max = 1000 } = {}) => {
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

export const parseFloatCsv = (value: unknown, { min = 0, max = 1000 } = {}) => {
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

export const parseBoolCsv = (value: unknown) => {
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

export const parseModeCsv = (value: unknown) => {
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

export const parseStrategySets = (value: unknown) => {
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

export const parseRegimeFilterSets = (value: unknown) => {
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

export const parseTimestampMs = (value: unknown) => {
  if (value === null || value === undefined) return null;
  const parsed = Date.parse(String(value));
  if (Number.isNaN(parsed)) return null;
  return parsed;
};

export const formatDurationCompact = (ms: number) => {
  const totalSeconds = Math.max(0, Math.round(ms / 1000));
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  if (hours > 0) return `${hours}h ${minutes}m`;
  if (minutes > 0) return `${minutes}m ${seconds}s`;
  return `${seconds}s`;
};

export const upsertJobInHistory = (history: Record<string, any>[], job: Record<string, any>) => {
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

export const getProfileTrades = (profile: Record<string, any>) =>
  Number(profile?.metrics?.total_trades ?? profile?.metrics?.trades ?? 0);

export const getProfileCreatedMs = (profile: Record<string, any>) =>
  parseTimestampMs(profile?.created_at) ?? 0;

interface BuildAdaptiveTunerRunPayloadArgs {
  form: AdaptiveTunerFormState;
  strategyApiUrl?: string;
}

export const buildAdaptiveTunerRunPayload = ({
  form,
  strategyApiUrl,
}: BuildAdaptiveTunerRunPayloadArgs) => {
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

  return { version, payload };
};
