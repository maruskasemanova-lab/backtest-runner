import type {
  StrategyAnalyzerAttachedRunState,
  StrategyAnalyzerContextRiskPresetKey,
  StrategyAnalyzerOnPauseRun,
  StrategyAnalyzerOnRunControl,
  StrategyAnalyzerPlaybackProgress,
  StrategyAnalyzerOnClearRun,
  StrategyAnalyzerTradeEvalMode,
  StrategyAnalyzerWfoVariantResult,
} from "./types";
import { STRATEGY_ANALYZER_CONTEXT_RISK_PRESET_OPTIONS } from "./strategyAnalyzerContextRiskPresets";

type Props = {
  tickers: Array<{ ticker: string }>;
  ticker: string;
  onTickerChange: (ticker: string) => void;
  dateFrom: string;
  dateTo: string;
  setDateFrom: (value: string) => void;
  setDateTo: (value: string) => void;
  loadBars: () => void;
  loading: boolean;
  barCount: number;
  warmupBars: number;
  onWarmupBarsChange: (value: number) => void;
  includeExtendedHours: boolean;
  onIncludeExtendedHoursChange: (value: boolean) => void;
  comparableMode: boolean;
  onComparableModeChange: (value: boolean) => void;
  coldStartEachDay: boolean;
  onColdStartEachDayChange: (value: boolean) => void;
  contextRiskPresetKey: StrategyAnalyzerContextRiskPresetKey;
  onContextRiskPresetChange: (value: StrategyAnalyzerContextRiskPresetKey) => void;
  isAnalyzerAttachedRun: boolean;
  analyzerTradeEvalMode: StrategyAnalyzerTradeEvalMode;
  onAnalyzerTradeEvalModeChange: (value: StrategyAnalyzerTradeEvalMode) => void;
  runLoading: boolean;
  isPlayingRun: boolean;
  analyzerRunTerminal: boolean;
  onPlayRun?: StrategyAnalyzerOnRunControl;
  onPauseRun?: StrategyAnalyzerOnPauseRun;
  onStepRun?: StrategyAnalyzerOnRunControl;
  onClearAnalyzerRun: StrategyAnalyzerOnClearRun;
  analyzerPlaybackProgress: StrategyAnalyzerPlaybackProgress;
  attachedRunState: StrategyAnalyzerAttachedRunState | null | undefined;
  rankedWfoResults: StrategyAnalyzerWfoVariantResult[];
  selectedWfoVariantId: string | null;
  bestWfoVariantId: string | null;
  onSelectWfoVariant: (variantId: string) => void;
};

export default function StrategyAnalyzerHeaderControls({
  tickers,
  ticker,
  onTickerChange,
  dateFrom,
  dateTo,
  setDateFrom,
  setDateTo,
  loadBars,
  loading,
  barCount,
  warmupBars,
  onWarmupBarsChange,
  includeExtendedHours,
  onIncludeExtendedHoursChange,
  comparableMode,
  onComparableModeChange,
  coldStartEachDay,
  onColdStartEachDayChange,
  contextRiskPresetKey,
  onContextRiskPresetChange,
  isAnalyzerAttachedRun,
  analyzerTradeEvalMode,
  onAnalyzerTradeEvalModeChange,
  runLoading,
  isPlayingRun,
  analyzerRunTerminal,
  onPlayRun,
  onPauseRun,
  onStepRun,
  onClearAnalyzerRun,
  analyzerPlaybackProgress,
  attachedRunState,
  rankedWfoResults,
  selectedWfoVariantId,
  bestWfoVariantId,
  onSelectWfoVariant,
}: Props) {
  return (
    <div className="card sa-command-deck">
      <div className="sa-toolbar">
        <label className="sa-control-field sa-control-field-tight">
          <span className="sa-control-label">Ticker</span>
          <select
            className="chart-timeframe sa-control-input"
            value={ticker}
            onChange={(e) => onTickerChange(e.target.value)}
          >
            {tickers.map((t) => (
              <option key={t.ticker} value={t.ticker}>
                {t.ticker}
              </option>
            ))}
            {tickers.length === 0 && <option value={ticker}>{ticker}</option>}
          </select>
        </label>

        <label className="sa-control-field sa-control-field-tight">
          <span className="sa-control-label">From</span>
          <input
            className="sa-control-input"
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
          />
        </label>

        <label className="sa-control-field sa-control-field-tight">
          <span className="sa-control-label">To</span>
          <input
            className="sa-control-input"
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
          />
        </label>

        <label className="sa-control-field sa-control-field-tight sa-control-field-small">
          <span className="sa-control-label">Warmup</span>
          <input
            className="sa-control-input"
            type="number"
            min={0}
            step={1}
            value={warmupBars}
            onChange={(e) => {
              const raw = Number(e.target.value);
              onWarmupBarsChange(Number.isFinite(raw) ? Math.max(0, Math.trunc(raw)) : 0);
            }}
            title="How many bars before the selected range to preload for warmup"
          />
        </label>

        <label
          className="sa-control-field sa-control-field-tight"
          style={{ minWidth: "auto" }}
          title="Include pre/post market hours in analyzer run"
        >
          <span className="sa-control-label">Ext Hours</span>
          <input
            type="checkbox"
            checked={includeExtendedHours}
            onChange={(e) => onIncludeExtendedHoursChange(Boolean(e.target.checked))}
            disabled={runLoading || isPlayingRun}
          />
        </label>

        <label
          className="sa-control-field sa-control-field-tight"
          style={{ minWidth: "auto" }}
          title="Comparable mode: deterministic cold-start behavior for reproducible runs"
        >
          <span className="sa-control-label">Comparable</span>
          <input
            type="checkbox"
            checked={comparableMode}
            onChange={(e) => onComparableModeChange(Boolean(e.target.checked))}
            disabled={runLoading || isPlayingRun}
          />
        </label>

        <label
          className="sa-control-field sa-control-field-tight"
          style={{ minWidth: "auto" }}
          title="Reset strategy state at each market day start"
        >
          <span className="sa-control-label">Cold/Day</span>
          <input
            type="checkbox"
            checked={coldStartEachDay || comparableMode}
            onChange={(e) => onColdStartEachDayChange(Boolean(e.target.checked))}
            disabled={runLoading || isPlayingRun || comparableMode}
          />
        </label>

        <label className="sa-control-field sa-control-field-tight sa-control-field-wide">
          <span className="sa-control-label">Config</span>
          <select
            className="chart-timeframe sa-control-input"
            value={contextRiskPresetKey}
            onChange={(e) =>
              onContextRiskPresetChange(e.target.value as StrategyAnalyzerContextRiskPresetKey)
            }
            disabled={runLoading || isPlayingRun}
            title="Context-risk preset used for new Strategy Analyzer runs"
          >
            {STRATEGY_ANALYZER_CONTEXT_RISK_PRESET_OPTIONS.map((option) => (
              <option key={option.key} value={option.key}>
                {option.label}
              </option>
            ))}
          </select>
        </label>

        <button
          type="button"
          className="btn btn-primary"
          onClick={loadBars}
          disabled={loading || !ticker || !dateFrom || !dateTo}
        >
          {loading ? "Loading..." : "Load Chart"}
        </button>

        {barCount > 0 ? (
          <span className="sa-meta-pill">{barCount.toLocaleString()} bars</span>
        ) : null}

        {isAnalyzerAttachedRun ? (
          <>
            <span className="sa-toolbar-divider" aria-hidden="true" />

            <label className="sa-control-field sa-control-field-tight">
              <span className="sa-control-label">Eval</span>
              <select
                className="chart-timeframe sa-control-input"
                value={analyzerTradeEvalMode}
                onChange={(e) =>
                  onAnalyzerTradeEvalModeChange(e.target.value as StrategyAnalyzerTradeEvalMode)
                }
                disabled={runLoading || isPlayingRun}
                title="Walking-forward evaluation mode for Play"
              >
                <option value="standard">1m (standard)</option>
                <option value="intrabar_1s">Intrabar 1s</option>
                <option value="intrabar_5s">Intrabar 5s</option>
              </select>
            </label>

            <button
              type="button"
              className="btn btn-primary"
              onClick={() =>
                void onPlayRun?.({
                  trade_eval_mode: analyzerTradeEvalMode,
                  speed_ms: "max",
                })
              }
              disabled={runLoading || isPlayingRun || analyzerRunTerminal}
              title="Play analyzer run"
            >
              ▶ Play
            </button>

            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => void onPauseRun?.()}
              disabled={runLoading || !isPlayingRun}
              title="Pause analyzer run"
            >
              ⏸ Pause
            </button>

            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => void onStepRun?.({ trade_eval_mode: analyzerTradeEvalMode })}
              disabled={runLoading || isPlayingRun || analyzerRunTerminal}
              title="Step one bar"
            >
              Step
            </button>

            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => void onClearAnalyzerRun()}
              disabled={runLoading}
              title="Clear analyzer run"
            >
              Clear
            </button>

            {rankedWfoResults.length > 0 ? (
              <label className="sa-control-field sa-control-field-tight sa-control-field-wide">
                <span className="sa-control-label">WFO</span>
                <select
                  className="chart-timeframe sa-control-input"
                  value={
                    selectedWfoVariantId || bestWfoVariantId || rankedWfoResults[0]?.id || ""
                  }
                  onChange={(e) => void onSelectWfoVariant(e.target.value)}
                  disabled={runLoading || isPlayingRun}
                  title="Select evaluated WFO variant"
                >
                  {rankedWfoResults.map((variant) => {
                    const pnl = Number(variant.metrics?.totalPnlDollars || 0);
                    const wr = Number(variant.metrics?.winRate || 0);
                    const suffix = ` | $${pnl.toFixed(2)} | ${wr.toFixed(1)}%`;
                    const best = variant.id === bestWfoVariantId ? " ★" : "";
                    return (
                      <option key={variant.id} value={variant.id}>
                        {variant.label}
                        {suffix}
                        {best}
                      </option>
                    );
                  })}
                </select>
              </label>
            ) : null}

            {analyzerPlaybackProgress ? (
              <span className="sa-meta-inline">
                {analyzerPlaybackProgress.isInitializing ? (
                  <span>
                    Initializing warmup {analyzerPlaybackProgress.warmupDone}/
                    {analyzerPlaybackProgress.warmupTotal}
                  </span>
                ) : analyzerPlaybackProgress.warmupTotal > 0 ? (
                  <span>
                    Warmup done {analyzerPlaybackProgress.warmupTotal}/
                    {analyzerPlaybackProgress.warmupTotal}
                  </span>
                ) : null}
                <span>
                  Trade {analyzerPlaybackProgress.tradeDone}/{analyzerPlaybackProgress.tradeTotal} (
                  {Number(analyzerPlaybackProgress.tradeProgressPct || 0).toFixed(1)}%)
                </span>
              </span>
            ) : attachedRunState ? (
              <span className="sa-meta-inline">
                {Number(attachedRunState.current_bar_index || 0)}/
                {Number(attachedRunState.total_bars || 0)} (
                {Number(attachedRunState.progress_pct || 0).toFixed(1)}%)
              </span>
            ) : null}
          </>
        ) : null}
      </div>
    </div>
  );
}
