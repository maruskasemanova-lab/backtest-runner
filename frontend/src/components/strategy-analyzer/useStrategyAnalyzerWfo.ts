import { useCallback, useMemo, useState } from "react";
import { buildRunApiBase, parseRunKey, readErrorDetail } from "../../app/appShared";
import { defaultStrategyApiUrl } from "../../utils";
import { dateTimeLocalToUtcIso } from "./utils";
import type {
  StrategyAnalyzerRangePlaybackMeta,
  StrategyAnalyzerStartRunPayload,
  StrategyAnalyzerStartRunResult,
  StrategyAnalyzerTradeEvalMode,
  StrategyAnalyzerWfoGridConfig,
  StrategyAnalyzerWfoMetrics,
  StrategyAnalyzerWfoVariantResult,
} from "./types";

type Params = {
  selectedRangeFrom: string | null;
  selectedRangeTo: string | null;
  ticker: string;
  strategyApiUrl: string;
  analyzerTradeEvalMode: StrategyAnalyzerTradeEvalMode;
  rangePlaybackMeta: StrategyAnalyzerRangePlaybackMeta;
  onOpenStoredRunSnapshot?: (runKey: string) => Promise<boolean>;
  setError: (value: string | null) => void;
  setRangeScrubOffset: (value: number) => void;
  setAnalyzerRunKey: (value: string | null) => void;
};

type VariantDefinition = {
  id: string;
  label: string;
  overrides: Record<string, number>;
};

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

const DEFAULT_WFO_GRID: StrategyAnalyzerWfoGridConfig = {
  contextRiskMinSlValues: "0.30, 0.40, 0.50",
  timeExitBarsValues: "6, 8, 12",
  breakEvenMinRValues: "0.35, 0.45, 0.60",
  breakEvenProofBookPressureValues: "0.02, 0.03, 0.06",
  evRelaxationThresholdValues: "",
  signedAggressionBlockZValues: "",
  includeBaseline: true,
  maxCombinations: 96,
  parallelWorkers: 3,
};

const extractMetricsFromSummary = (summaryPayload: any): StrategyAnalyzerWfoMetrics => {
  const summary =
    summaryPayload?.session_summary && typeof summaryPayload.session_summary === "object"
      ? summaryPayload.session_summary
      : {};
  const profitFactorRaw = summary?.profit_factor_dollars;
  let profitFactor: number | null = null;
  if (typeof profitFactorRaw === "number" && Number.isFinite(profitFactorRaw)) {
    profitFactor = profitFactorRaw;
  } else if (typeof profitFactorRaw === "string") {
    const normalized = profitFactorRaw.trim().toLowerCase();
    if (normalized && normalized !== "inf" && normalized !== "infinity") {
      const parsed = Number(normalized);
      if (Number.isFinite(parsed)) profitFactor = parsed;
    }
  }

  return {
    totalTrades: Math.max(0, Number(summary?.total_trades || 0) || 0),
    winRate: Number(summary?.win_rate || 0) || 0,
    totalPnlDollars: Number(summary?.total_pnl_dollars || 0) || 0,
    maxDrawdownDollars: Number(summary?.max_drawdown_dollars || 0) || 0,
    profitFactor,
  };
};

const parseNumericList = (
  raw: string,
  options: { intOnly?: boolean; min?: number; max?: number } = {},
): number[] => {
  const text = String(raw || "").trim();
  if (!text) return [];
  const out: number[] = [];
  const seen = new Set<string>();
  const tokens = text
    .split(/[\s,;]+/)
    .map((token) => token.trim())
    .filter(Boolean);

  for (const token of tokens) {
    const parsed = Number(token);
    if (!Number.isFinite(parsed)) continue;
    let next = parsed;
    if (options.intOnly) next = Math.trunc(next);
    if (typeof options.min === "number") next = Math.max(options.min, next);
    if (typeof options.max === "number") next = Math.min(options.max, next);
    const key = options.intOnly ? String(Math.trunc(next)) : next.toFixed(6);
    if (!seen.has(key)) {
      seen.add(key);
      out.push(next);
    }
  }
  return out;
};

const buildLabelFromOverrides = (overrides: Record<string, number>): string => {
  const chunks: string[] = [];
  if (typeof overrides.context_risk_min_sl_pct === "number") {
    chunks.push(`SL ${overrides.context_risk_min_sl_pct.toFixed(2)}%`);
  }
  if (typeof overrides.time_exit_bars === "number") {
    chunks.push(`Time ${Math.trunc(overrides.time_exit_bars)}b`);
  }
  if (typeof overrides.break_even_activation_min_r === "number") {
    chunks.push(`BE-R ${overrides.break_even_activation_min_r.toFixed(2)}`);
  }
  if (typeof overrides.break_even_l2_proof_book_pressure_threshold === "number") {
    chunks.push(`BE-L2 ${overrides.break_even_l2_proof_book_pressure_threshold.toFixed(2)}`);
  }
  if (typeof overrides.ev_relaxation_threshold === "number") {
    chunks.push(`EV ${overrides.ev_relaxation_threshold.toFixed(1)}`);
  }
  if (typeof overrides.signed_aggression_block_z_threshold === "number") {
    chunks.push(`AggZ ${overrides.signed_aggression_block_z_threshold.toFixed(2)}`);
  }
  return chunks.length ? chunks.join(" | ") : "Baseline (current defaults)";
};

const buildVariantDefinitions = (config: StrategyAnalyzerWfoGridConfig): VariantDefinition[] => {
  const dimensions: Array<{ key: string; values: number[] }> = [
    {
      key: "context_risk_min_sl_pct",
      values: parseNumericList(config.contextRiskMinSlValues, { min: 0.05, max: 5.0 }),
    },
    {
      key: "time_exit_bars",
      values: parseNumericList(config.timeExitBarsValues, { intOnly: true, min: 1, max: 240 }),
    },
    {
      key: "break_even_activation_min_r",
      values: parseNumericList(config.breakEvenMinRValues, { min: 0.0, max: 5.0 }),
    },
    {
      key: "break_even_l2_proof_book_pressure_threshold",
      values: parseNumericList(config.breakEvenProofBookPressureValues, { min: 0.0, max: 2.0 }),
    },
    {
      key: "ev_relaxation_threshold",
      values: parseNumericList(config.evRelaxationThresholdValues, { min: 0.0, max: 200.0 }),
    },
    {
      key: "signed_aggression_block_z_threshold",
      values: parseNumericList(config.signedAggressionBlockZValues, { min: -10.0, max: 10.0 }),
    },
  ].filter((dimension) => dimension.values.length > 0);

  let combinations: Array<Record<string, number>> = [{}];
  for (const dimension of dimensions) {
    const next: Array<Record<string, number>> = [];
    for (const combo of combinations) {
      for (const value of dimension.values) {
        next.push({
          ...combo,
          [dimension.key]: value,
        });
      }
    }
    combinations = next;
  }

  const deduped: Array<Record<string, number>> = [];
  const seen = new Set<string>();
  for (const combo of combinations) {
    const serialized = JSON.stringify(
      Object.keys(combo)
        .sort()
        .reduce<Record<string, number>>((acc, key) => {
          acc[key] = combo[key];
          return acc;
        }, {}),
    );
    if (!seen.has(serialized)) {
      seen.add(serialized);
      deduped.push(combo);
    }
  }

  const variants: VariantDefinition[] = [];
  if (config.includeBaseline) {
    variants.push({ id: "baseline", label: "Baseline (current defaults)", overrides: {} });
  }
  for (let index = 0; index < deduped.length; index += 1) {
    const combo = deduped[index];
    variants.push({
      id: `combo-${index + 1}`,
      label: buildLabelFromOverrides(combo),
      overrides: combo,
    });
  }
  return variants;
};

const sortWfoVariantsBySuccess = (
  left: StrategyAnalyzerWfoVariantResult,
  right: StrategyAnalyzerWfoVariantResult,
): number => {
  const leftScore = Number(left.objectiveScore || 0);
  const rightScore = Number(right.objectiveScore || 0);
  if (rightScore !== leftScore) return rightScore - leftScore;

  const leftWin = Number(left.metrics?.winRate || 0);
  const rightWin = Number(right.metrics?.winRate || 0);
  if (rightWin !== leftWin) return rightWin - leftWin;

  const leftTrades = Number(left.metrics?.totalTrades || 0);
  const rightTrades = Number(right.metrics?.totalTrades || 0);
  return rightTrades - leftTrades;
};

export function useStrategyAnalyzerWfo({
  selectedRangeFrom,
  selectedRangeTo,
  ticker,
  strategyApiUrl,
  analyzerTradeEvalMode,
  rangePlaybackMeta,
  onOpenStoredRunSnapshot,
  setError,
  setRangeScrubOffset,
  setAnalyzerRunKey,
}: Params) {
  const [wfoEnabled, setWfoEnabled] = useState(false);
  const [wfoGridConfig, setWfoGridConfig] =
    useState<StrategyAnalyzerWfoGridConfig>(DEFAULT_WFO_GRID);
  const [wfoIsRunning, setWfoIsRunning] = useState(false);
  const [wfoProgressLabel, setWfoProgressLabel] = useState("");
  const [wfoResults, setWfoResults] = useState<StrategyAnalyzerWfoVariantResult[]>([]);
  const [selectedWfoVariantId, setSelectedWfoVariantId] = useState<string | null>(null);

  const wfoVariantDefinitions = useMemo(() => buildVariantDefinitions(wfoGridConfig), [wfoGridConfig]);

  const estimatedCombinationCount = useMemo(
    () => wfoVariantDefinitions.length,
    [wfoVariantDefinitions],
  );

  const rankedWfoResults = useMemo(() => {
    const completed = wfoResults.filter((variant) => variant.status === "completed");
    return [...completed].sort(sortWfoVariantsBySuccess);
  }, [wfoResults]);

  const bestWfoVariantId = rankedWfoResults[0]?.id || null;

  const updateWfoGridConfig = useCallback((patch: Partial<StrategyAnalyzerWfoGridConfig>) => {
    setWfoGridConfig((previous) => ({ ...previous, ...patch }));
  }, []);

  const buildStartPayload = useCallback(
    (overrides: Record<string, number>, runId: string): StrategyAnalyzerStartRunPayload & Record<string, any> => {
      const effectiveStartLocal = rangePlaybackMeta?.warmupStartLocal || selectedRangeFrom;
      const effectiveEndLocal = rangePlaybackMeta?.tradeEndLocal || selectedRangeTo;
      const effectiveTradeStartLocal = rangePlaybackMeta?.tradeStartLocal || selectedRangeFrom;
      const effectiveTradeEndLocal = rangePlaybackMeta?.tradeEndLocal || selectedRangeTo;

      const payload: StrategyAnalyzerStartRunPayload & Record<string, any> = {
        run_id: runId,
        ticker,
        date_from: String(effectiveStartLocal || "").slice(0, 10),
        date_to: String(effectiveEndLocal || "").slice(0, 10),
        start_time: dateTimeLocalToUtcIso(effectiveStartLocal),
        end_time: dateTimeLocalToUtcIso(effectiveEndLocal),
        trade_start_time: dateTimeLocalToUtcIso(effectiveTradeStartLocal),
        trade_end_time: dateTimeLocalToUtcIso(effectiveTradeEndLocal),
        strategy_api_url: strategyApiUrl || defaultStrategyApiUrl,
        include_extended_hours: true,
        trade_eval_mode: analyzerTradeEvalMode,
      };
      return {
        ...payload,
        ...overrides,
      };
    },
    [
      rangePlaybackMeta,
      selectedRangeFrom,
      selectedRangeTo,
      ticker,
      strategyApiUrl,
      analyzerTradeEvalMode,
    ],
  );

  const waitForRunCompletion = useCallback(
    async (runKey: string) => {
      const runParts = parseRunKey(runKey);
      const runApiBase = buildRunApiBase(runParts);
      if (!runApiBase) {
        throw new Error("Unable to resolve run API base.");
      }

      const playResp = await fetch(`${runApiBase}/play`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          speed_ms: "max",
          trade_eval_mode: analyzerTradeEvalMode,
        }),
      });
      if (!playResp.ok) {
        throw new Error(await readErrorDetail(playResp, `Failed to play run (${playResp.status})`));
      }

      const startedAt = Date.now();
      const timeoutMs = 20 * 60 * 1000;
      while (true) {
        const stateResp = await fetch(`${runApiBase}/state`);
        if (!stateResp.ok) {
          throw new Error(await readErrorDetail(stateResp, `Failed to fetch state (${stateResp.status})`));
        }
        const state = await stateResp.json().catch(() => ({}));
        const phase = String(state?.phase || "").trim().toUpperCase();
        const totalBars = Number(state?.total_bars || 0);
        const currentBar = Number(state?.current_bar_index || 0);
        const isRunning = Boolean(state?.is_running);
        const completed =
          phase === "COMPLETED" ||
          (!isRunning && totalBars > 0 && currentBar >= totalBars);
        if (completed) {
          break;
        }
        if (Date.now() - startedAt > timeoutMs) {
          throw new Error("Timed out waiting for run completion.");
        }
        await sleep(500);
      }

      const summaryResp = await fetch(`${runApiBase}/summary`);
      if (!summaryResp.ok) {
        throw new Error(await readErrorDetail(summaryResp, `Failed to fetch summary (${summaryResp.status})`));
      }
      return summaryResp.json().catch(() => ({}));
    },
    [analyzerTradeEvalMode],
  );

  const startWfoRun = useCallback(async (payload: StrategyAnalyzerStartRunPayload & Record<string, any>) => {
    const resp = await fetch("/api/run/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!resp.ok) {
      throw new Error(await readErrorDetail(resp, `Failed to start run (${resp.status})`));
    }
    return (await resp.json().catch(() => ({}))) as StrategyAnalyzerStartRunResult;
  }, []);

  const handleRunWfo = useCallback(async () => {
    if (wfoIsRunning) return;
    if (!selectedRangeFrom || !selectedRangeTo || !ticker) return;

    setError(null);

    const variants = buildVariantDefinitions(wfoGridConfig);
    if (variants.length <= 0) {
      setError("No valid WFO combinations were generated.");
      return;
    }
    if (variants.length > Math.max(1, Number(wfoGridConfig.maxCombinations || 24))) {
      setError(
        `Generated ${variants.length} combinations, but max is ${wfoGridConfig.maxCombinations}. Reduce value lists or increase limit.`,
      );
      return;
    }

    setWfoIsRunning(true);
    setWfoProgressLabel(`Preparing ${variants.length} combinations...`);
    setSelectedWfoVariantId(null);

    const workingResults: StrategyAnalyzerWfoVariantResult[] = variants.map((variant) => ({
      id: variant.id,
      label: variant.label,
      status: "pending",
      overrides: variant.overrides,
      runKey: null,
      metrics: null,
      objectiveScore: Number.NEGATIVE_INFINITY,
      error: null,
    }));
    setWfoResults(workingResults);

    const setVariant = (index: number, patch: Partial<StrategyAnalyzerWfoVariantResult>) => {
      const next = { ...workingResults[index], ...patch };
      workingResults[index] = next;
      setWfoResults([...workingResults]);
    };

    const totalCount = variants.length;
    const maxWorkers = 8;
    const configuredWorkers = Math.trunc(Number(wfoGridConfig.parallelWorkers || 1));
    const workerCount = Math.min(totalCount, Math.max(1, Math.min(maxWorkers, configuredWorkers)));
    const shouldLiveAttachRunningVariant =
      workerCount === 1 && typeof onOpenStoredRunSnapshot === "function";
    let completedCount = 0;
    let runningCount = 0;
    const setProgress = (suffix?: string) => {
      const done = completedCount;
      const base = `WFO ${done}/${totalCount} done | active ${runningCount} | workers ${workerCount}`;
      setWfoProgressLabel(suffix ? `${base} | ${suffix}` : base);
    };

    setProgress(
      shouldLiveAttachRunningVariant
        ? "starting"
        : "starting (live chart disabled for workers > 1)",
    );

    try {
      let nextIndex = 0;
      const runVariantByIndex = async (index: number) => {
        const variant = variants[index];
        runningCount += 1;
        setVariant(index, { status: "running", error: null });
        setProgress(`running ${index + 1}/${totalCount}`);
        try {
          const runId = `analyzer-wfo-${Date.now()}-${index + 1}-${Math.random().toString(36).slice(2, 8)}`;
          const payload = buildStartPayload(variant.overrides, runId);
          const startResult = await startWfoRun(payload);
          const runKey = String(startResult?.run_key || "").trim();
          if (!runKey) {
            throw new Error("Run did not return a run_key.");
          }
          if (shouldLiveAttachRunningVariant) {
            setAnalyzerRunKey(runKey);
            setRangeScrubOffset(0);
            await onOpenStoredRunSnapshot?.(runKey).catch(() => false);
          }

          const summaryPayload = await waitForRunCompletion(runKey);
          const metrics = extractMetricsFromSummary(summaryPayload);
          setVariant(index, {
            status: "completed",
            runKey,
            metrics,
            objectiveScore: Number(metrics.totalPnlDollars || 0),
            error: null,
          });
        } catch (error: unknown) {
          const message = error instanceof Error ? error.message : "WFO run failed.";
          setVariant(index, {
            status: "failed",
            objectiveScore: Number.NEGATIVE_INFINITY,
            error: message,
          });
        } finally {
          runningCount = Math.max(0, runningCount - 1);
          completedCount += 1;
          setProgress();
        }
      };

      const worker = async () => {
        while (true) {
          const index = nextIndex;
          nextIndex += 1;
          if (index >= totalCount) break;
          await runVariantByIndex(index);
        }
      };

      const workerPromises: Array<Promise<void>> = [];
      for (let workerIndex = 0; workerIndex < workerCount; workerIndex += 1) {
        workerPromises.push(worker());
      }
      await Promise.all(workerPromises);

      const ranked = [...workingResults]
        .filter((variant) => variant.status === "completed" && Boolean(variant.runKey))
        .sort(sortWfoVariantsBySuccess);
      const best = ranked[0] || null;
      if (best?.id) {
        setSelectedWfoVariantId(best.id);
      }
      if (best?.runKey) {
        setWfoProgressLabel(`Completed. Best: ${best.label}`);
        setAnalyzerRunKey(best.runKey);
        setRangeScrubOffset(0);
        if (typeof onOpenStoredRunSnapshot === "function") {
          await onOpenStoredRunSnapshot(best.runKey).catch(() => false);
        }
      } else {
        setWfoProgressLabel("Completed. No successful combination.");
      }
    } finally {
      setWfoIsRunning(false);
    }
  }, [
    wfoIsRunning,
    selectedRangeFrom,
    selectedRangeTo,
    ticker,
    wfoGridConfig,
    setError,
    buildStartPayload,
    startWfoRun,
    waitForRunCompletion,
    setAnalyzerRunKey,
    setRangeScrubOffset,
    onOpenStoredRunSnapshot,
  ]);

  const handleSelectWfoVariant = useCallback(
    async (variantId: string) => {
      setSelectedWfoVariantId(variantId);
      const variant = wfoResults.find((item) => item.id === variantId);
      const runKey = String(variant?.runKey || "").trim();
      if (!runKey) return;
      setAnalyzerRunKey(runKey);
      setRangeScrubOffset(0);
      if (typeof onOpenStoredRunSnapshot === "function") {
        await onOpenStoredRunSnapshot(runKey).catch(() => false);
      }
    },
    [wfoResults, onOpenStoredRunSnapshot, setAnalyzerRunKey, setRangeScrubOffset],
  );

  return {
    wfoEnabled,
    setWfoEnabled,
    wfoGridConfig,
    updateWfoGridConfig,
    estimatedCombinationCount,
    wfoIsRunning,
    wfoProgressLabel,
    wfoResults,
    rankedWfoResults,
    selectedWfoVariantId,
    bestWfoVariantId,
    handleRunWfo,
    handleSelectWfoVariant,
  };
}
