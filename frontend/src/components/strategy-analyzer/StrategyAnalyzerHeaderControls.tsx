import type {
  StrategyAnalyzerAttachedRunState,
  StrategyAnalyzerOnPauseRun,
  StrategyAnalyzerOnRunControl,
  StrategyAnalyzerPlaybackProgress,
  StrategyAnalyzerOnClearRun,
  StrategyAnalyzerTradeEvalMode,
} from "./types";

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
  isAnalyzerAttachedRun: boolean;
  analyzerTradeEvalMode: StrategyAnalyzerTradeEvalMode;
  onAnalyzerTradeEvalModeChange: (value: StrategyAnalyzerTradeEvalMode) => void;
  runLoading: boolean;
  isPlayingRun: boolean;
  analyzerRunFinished: boolean;
  onPlayRun?: StrategyAnalyzerOnRunControl;
  onPauseRun?: StrategyAnalyzerOnPauseRun;
  onStepRun?: StrategyAnalyzerOnRunControl;
  onClearAnalyzerRun: StrategyAnalyzerOnClearRun;
  analyzerPlaybackProgress: StrategyAnalyzerPlaybackProgress;
  attachedRunState: StrategyAnalyzerAttachedRunState | null | undefined;
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
  isAnalyzerAttachedRun,
  analyzerTradeEvalMode,
  onAnalyzerTradeEvalModeChange,
  runLoading,
  isPlayingRun,
  analyzerRunFinished,
  onPlayRun,
  onPauseRun,
  onStepRun,
  onClearAnalyzerRun,
  analyzerPlaybackProgress,
  attachedRunState,
}: Props) {
  return (
    <div className="card" style={{ padding: "0.75rem 1rem" }}>
      <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", flexWrap: "wrap" }}>
        <label style={{ fontWeight: 600, fontSize: "0.85rem", color: "var(--text-secondary)" }}>
          Ticker
        </label>
        <select
          className="chart-timeframe"
          value={ticker}
          onChange={(e) => onTickerChange(e.target.value)}
          style={{ minWidth: 90 }}
        >
          {tickers.map((t) => (
            <option key={t.ticker} value={t.ticker}>
              {t.ticker}
            </option>
          ))}
          {tickers.length === 0 && <option value={ticker}>{ticker}</option>}
        </select>

        <label style={{ fontWeight: 600, fontSize: "0.85rem", color: "var(--text-secondary)" }}>
          From
        </label>
        <input
          type="date"
          value={dateFrom}
          onChange={(e) => setDateFrom(e.target.value)}
          style={{
            padding: "4px 8px",
            borderRadius: "var(--radius-sm)",
            border: "1px solid var(--border-color)",
            background: "var(--bg-secondary)",
            color: "var(--text-primary)",
            fontSize: "0.85rem",
          }}
        />

        <label style={{ fontWeight: 600, fontSize: "0.85rem", color: "var(--text-secondary)" }}>
          To
        </label>
        <input
          type="date"
          value={dateTo}
          onChange={(e) => setDateTo(e.target.value)}
          style={{
            padding: "4px 8px",
            borderRadius: "var(--radius-sm)",
            border: "1px solid var(--border-color)",
            background: "var(--bg-secondary)",
            color: "var(--text-primary)",
            fontSize: "0.85rem",
          }}
        />

        <button
          className="btn btn-primary"
          onClick={loadBars}
          disabled={loading || !ticker || !dateFrom || !dateTo}
          style={{ padding: "6px 16px", fontSize: "0.85rem", fontWeight: 600 }}
        >
          {loading ? "Loading..." : "Load Chart"}
        </button>

        {barCount > 0 && (
          <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
            {barCount.toLocaleString()} bars
          </span>
        )}

        <label style={{ fontWeight: 600, fontSize: "0.8rem", color: "var(--text-secondary)" }}>
          Warmup bars
        </label>
        <input
          type="number"
          min={0}
          step={1}
          value={warmupBars}
          onChange={(e) => {
            const raw = Number(e.target.value);
            onWarmupBarsChange(Number.isFinite(raw) ? Math.max(0, Math.trunc(raw)) : 0);
          }}
          style={{
            width: 84,
            padding: "4px 8px",
            borderRadius: "var(--radius-sm)",
            border: "1px solid var(--border-color)",
            background: "var(--bg-secondary)",
            color: "var(--text-primary)",
            fontSize: "0.8rem",
          }}
          title="How many bars before the selected range to preload for warmup"
        />

        {isAnalyzerAttachedRun ? (
          <>
            <div style={{ width: 1, alignSelf: "stretch", background: "var(--border-color)" }} />
            <label style={{ fontWeight: 600, fontSize: "0.78rem", color: "var(--text-secondary)" }}>
              Eval
            </label>
            <select
              className="chart-timeframe"
              value={analyzerTradeEvalMode}
              onChange={(e) => onAnalyzerTradeEvalModeChange(e.target.value as StrategyAnalyzerTradeEvalMode)}
              disabled={runLoading || isPlayingRun}
              style={{ minWidth: 118, fontSize: "0.78rem", padding: "4px 8px" }}
              title="Walking-forward evaluation mode for Play"
            >
              <option value="standard">1m (standard)</option>
              <option value="intrabar_1s">Intrabar 1s</option>
              <option value="intrabar_5s">Intrabar 5s</option>
            </select>
            <button
              className="btn btn-primary"
              onClick={() => void onPlayRun?.({ trade_eval_mode: analyzerTradeEvalMode })}
              disabled={runLoading || isPlayingRun || analyzerRunFinished}
              style={{ padding: "6px 12px", fontSize: "0.8rem", fontWeight: 700 }}
              title="Play analyzer run"
            >
              ▶ Play
            </button>
            <button
              className="btn btn-secondary"
              onClick={() => void onPauseRun?.()}
              disabled={runLoading || !isPlayingRun}
              style={{ padding: "6px 12px", fontSize: "0.8rem", fontWeight: 700 }}
              title="Pause analyzer run"
            >
              ⏸ Pause
            </button>
            <button
              className="btn btn-secondary"
              onClick={() => void onStepRun?.({ trade_eval_mode: analyzerTradeEvalMode })}
              disabled={runLoading || isPlayingRun || analyzerRunFinished}
              style={{ padding: "6px 12px", fontSize: "0.8rem", fontWeight: 700 }}
              title="Step one bar"
            >
              Step
            </button>
            <button
              className="btn btn-secondary"
              onClick={() => void onClearAnalyzerRun()}
              disabled={runLoading}
              style={{ padding: "6px 12px", fontSize: "0.8rem", fontWeight: 700 }}
              title="Clear analyzer run"
            >
              Clear
            </button>
            {analyzerPlaybackProgress ? (
              <span
                style={{
                  fontSize: "0.78rem",
                  color: "var(--text-muted)",
                  display: "inline-flex",
                  gap: 8,
                  alignItems: "center",
                  flexWrap: "wrap",
                }}
              >
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
              <span style={{ fontSize: "0.78rem", color: "var(--text-muted)" }}>
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
