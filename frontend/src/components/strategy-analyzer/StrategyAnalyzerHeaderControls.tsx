import type {
  StrategyAnalyzerAttachedRunState,
  StrategyAnalyzerContextRiskPresetKey,
  StrategyAnalyzerOnClearRun,
  StrategyAnalyzerOnPauseRun,
  StrategyAnalyzerOnRunControl,
  StrategyAnalyzerPlaybackProgress,
  StrategyAnalyzerTradeEvalMode,
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
  layout?: "deck" | "rail";
};

const TRADE_EVAL_MODE_LABELS: Record<StrategyAnalyzerTradeEvalMode, string> = {
  standard: "1m standard",
  intrabar_1s: "Intrabar 1s",
  intrabar_5s: "Intrabar 5s",
};

const clampPct = (value: number): number => Math.max(0, Math.min(100, value));

function buildPlaybackSummary(
  analyzerPlaybackProgress: StrategyAnalyzerPlaybackProgress,
  attachedRunState: StrategyAnalyzerAttachedRunState | null | undefined,
) {
  if (analyzerPlaybackProgress) {
    const progressPct = clampPct(Number(analyzerPlaybackProgress.tradeProgressPct || 0));
    if (analyzerPlaybackProgress.isInitializing) {
      return {
        progressPct,
        phaseLabel: "Initializing",
        summaryLabel: `Warmup ${analyzerPlaybackProgress.warmupDone}/${analyzerPlaybackProgress.warmupTotal}`,
        detailLabel:
          analyzerPlaybackProgress.tradeTotal > 0
            ? `Replay queue ${analyzerPlaybackProgress.tradeDone}/${analyzerPlaybackProgress.tradeTotal}`
            : "Preparing replay window",
      };
    }

    return {
      progressPct,
      phaseLabel: "Replay progress",
      summaryLabel: `Trade ${analyzerPlaybackProgress.tradeDone}/${analyzerPlaybackProgress.tradeTotal}`,
      detailLabel:
        analyzerPlaybackProgress.warmupTotal > 0
          ? `Warmup locked ${analyzerPlaybackProgress.warmupTotal}/${analyzerPlaybackProgress.warmupTotal}`
          : "Warmup skipped",
    };
  }

  const fallbackPct = clampPct(Number(attachedRunState?.progress_pct || 0));
  return {
    progressPct: fallbackPct,
    phaseLabel: "Replay progress",
    summaryLabel: `${Number(attachedRunState?.current_bar_index || 0)}/${Number(attachedRunState?.total_bars || 0)} bars`,
    detailLabel: attachedRunState?.phase ? `Phase ${String(attachedRunState.phase)}` : "Waiting for runner state",
  };
}

function StrategyToggleCard({
  label,
  description,
  checked,
  disabled = false,
  onChange,
}: {
  label: string;
  description: string;
  checked: boolean;
  disabled?: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <label className={`sa-toggle-card ${checked ? "is-active" : ""} ${disabled ? "is-disabled" : ""}`}>
      <span className="sa-toggle-card__copy">
        <span className="sa-toggle-card__title">{label}</span>
        <span className="sa-toggle-card__description">{description}</span>
      </span>
      <input
        className="sa-toggle-card__input"
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(Boolean(event.target.checked))}
        disabled={disabled}
      />
      <span className="sa-toggle-card__switch" aria-hidden="true">
        <span className="sa-toggle-card__thumb" />
      </span>
    </label>
  );
}

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
  layout = "deck",
}: Props) {
  const commandDeckClassName =
    layout === "rail" ? "card sa-command-deck sa-command-deck-rail" : "card sa-command-deck";
  const contextRiskPresetLabel =
    STRATEGY_ANALYZER_CONTEXT_RISK_PRESET_OPTIONS.find((option) => option.key === contextRiskPresetKey)?.label ||
    contextRiskPresetKey;
  const playbackStateLabel = isAnalyzerAttachedRun
    ? isPlayingRun
      ? "Replay live"
      : analyzerRunTerminal
        ? "Replay complete"
        : "Replay paused"
    : barCount > 0
      ? "Tape ready"
      : loading
        ? "Loading tape"
        : "Awaiting tape";
  const playbackSummary = buildPlaybackSummary(analyzerPlaybackProgress, attachedRunState);

  return (
    <div className={commandDeckClassName}>
      <div className="sa-command-deck-head">
        <div className="sa-command-deck-copy">
          <div className="sa-section-kicker">Replay Controls</div>
          <h3 className="sa-command-deck-title">{ticker} control stack</h3>
          <p className="sa-command-deck-description">
            Keep session scope, execution resolution and reset behavior explicit before you start comparing tweaks.
          </p>
        </div>
        <div className="sa-command-deck-status">
          <span className={`sa-state-pill ${isAnalyzerAttachedRun ? "is-live" : "is-ready"}`}>{playbackStateLabel}</span>
          <span className="sa-meta-pill">{barCount > 0 ? `${barCount.toLocaleString()} bars` : "No tape loaded"}</span>
        </div>
      </div>

      <div className="sa-control-groups">
        <section className="sa-group-card">
          <div className="sa-group-card__head">
            <div>
              <div className="sa-group-card__eyebrow">Market Tape</div>
              <div className="sa-group-card__title">Choose the session to inspect</div>
            </div>
            <button
              type="button"
              className="btn btn-primary"
              onClick={loadBars}
              disabled={loading || !ticker || !dateFrom || !dateTo}
            >
              {loading ? "Loading tape..." : "Load market tape"}
            </button>
          </div>

          <div className="sa-form-grid">
            <label className="sa-control-field sa-control-field-tight">
              <span className="sa-control-label">Ticker</span>
              <select
                className="chart-timeframe sa-control-input"
                value={ticker}
                onChange={(event) => onTickerChange(event.target.value)}
              >
                {tickers.map((entry) => (
                  <option key={entry.ticker} value={entry.ticker}>
                    {entry.ticker}
                  </option>
                ))}
                {tickers.length === 0 ? <option value={ticker}>{ticker}</option> : null}
              </select>
            </label>

            <label className="sa-control-field sa-control-field-tight">
              <span className="sa-control-label">From</span>
              <input
                className="sa-control-input"
                type="date"
                value={dateFrom}
                onChange={(event) => setDateFrom(event.target.value)}
              />
            </label>

            <label className="sa-control-field sa-control-field-tight">
              <span className="sa-control-label">To</span>
              <input
                className="sa-control-input"
                type="date"
                value={dateTo}
                onChange={(event) => setDateTo(event.target.value)}
              />
            </label>
          </div>
        </section>

        <section className="sa-group-card">
          <div className="sa-group-card__head">
            <div>
              <div className="sa-group-card__eyebrow">Execution Model</div>
              <div className="sa-group-card__title">Replay fidelity and risk template</div>
            </div>
            <span className="sa-group-card__meta">{TRADE_EVAL_MODE_LABELS[analyzerTradeEvalMode]}</span>
          </div>

          <div className="sa-form-grid sa-form-grid-compact">
            <label className="sa-control-field sa-control-field-small">
              <span className="sa-control-label">Warmup bars</span>
              <input
                className="sa-control-input"
                type="number"
                min={0}
                step={1}
                value={warmupBars}
                onChange={(event) => {
                  const raw = Number(event.target.value);
                  onWarmupBarsChange(Number.isFinite(raw) ? Math.max(0, Math.trunc(raw)) : 0);
                }}
                title="How many bars before the selected range to preload for warmup"
              />
            </label>

            <label className="sa-control-field sa-control-field-tight">
              <span className="sa-control-label">Execution resolution</span>
              <select
                className="chart-timeframe sa-control-input"
                value={analyzerTradeEvalMode}
                onChange={(event) =>
                  onAnalyzerTradeEvalModeChange(event.target.value as StrategyAnalyzerTradeEvalMode)
                }
                disabled={runLoading || isPlayingRun}
                title="Walking-forward evaluation mode used during replay"
              >
                <option value="standard">1m standard</option>
                <option value="intrabar_1s">Intrabar 1s</option>
                <option value="intrabar_5s">Intrabar 5s</option>
              </select>
            </label>

            <label className="sa-control-field sa-control-field-wide">
              <span className="sa-control-label">Risk profile</span>
              <select
                className="chart-timeframe sa-control-input"
                value={contextRiskPresetKey}
                onChange={(event) =>
                  onContextRiskPresetChange(event.target.value as StrategyAnalyzerContextRiskPresetKey)
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
              <span className="sa-field-help">Current template: {contextRiskPresetLabel}</span>
            </label>
          </div>
        </section>

        <section className="sa-group-card">
          <div className="sa-group-card__head">
            <div>
              <div className="sa-group-card__eyebrow">Run Discipline</div>
              <div className="sa-group-card__title">Keep comparisons clean</div>
            </div>
          </div>

          <div className="sa-toggle-grid">
            <StrategyToggleCard
              label="Extended hours"
              description="Include pre-market and post-market bars in the replay tape."
              checked={includeExtendedHours}
              disabled={runLoading || isPlayingRun}
              onChange={onIncludeExtendedHoursChange}
            />
            <StrategyToggleCard
              label="Repro mode"
              description="Force deterministic cold start behavior for fair A/B comparisons."
              checked={comparableMode}
              disabled={runLoading || isPlayingRun}
              onChange={onComparableModeChange}
            />
            <StrategyToggleCard
              label="Reset each day"
              description="Restart strategy state on every new market day."
              checked={coldStartEachDay || comparableMode}
              disabled={runLoading || isPlayingRun || comparableMode}
              onChange={onColdStartEachDayChange}
            />
          </div>
        </section>

        <section className="sa-group-card">
          <div className="sa-group-card__head">
            <div>
              <div className="sa-group-card__eyebrow">Playback</div>
              <div className="sa-group-card__title">
                {isAnalyzerAttachedRun ? "Drive the active replay" : "Playback activates after replay start"}
              </div>
            </div>
            {isAnalyzerAttachedRun ? (
              <span className={`sa-state-pill ${analyzerRunTerminal ? "is-success" : isPlayingRun ? "is-live" : "is-idle"}`}>
                {attachedRunState?.phase ? String(attachedRunState.phase) : playbackStateLabel}
              </span>
            ) : null}
          </div>

          {isAnalyzerAttachedRun ? (
            <>
              <div className="sa-playback-progress">
                <div className="sa-playback-progress__head">
                  <span>{playbackSummary.phaseLabel}</span>
                  <strong>{playbackSummary.progressPct.toFixed(1)}%</strong>
                </div>
                <div className="sa-playback-progress__track">
                  <div
                    className="sa-playback-progress__fill"
                    style={{ width: `${playbackSummary.progressPct}%` }}
                  />
                </div>
                <div className="sa-playback-progress__meta">
                  <span>{playbackSummary.summaryLabel}</span>
                  <span>{playbackSummary.detailLabel}</span>
                </div>
              </div>

              <div className="sa-action-row sa-action-row-compact">
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={() =>
                    void onPlayRun?.({
                      trade_eval_mode: analyzerTradeEvalMode,
                      speed_ms: "max",
                    })
                  }
                  disabled={runLoading || isPlayingRun}
                  title="Play analyzer run"
                >
                  Play replay
                </button>

                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => void onPauseRun?.()}
                  disabled={runLoading || !isPlayingRun}
                  title="Pause analyzer run"
                >
                  Pause
                </button>

                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => void onStepRun?.({ trade_eval_mode: analyzerTradeEvalMode })}
                  disabled={runLoading || isPlayingRun}
                  title="Step one bar"
                >
                  Step bar
                </button>

                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => void onClearAnalyzerRun()}
                  disabled={runLoading}
                  title="Clear analyzer run"
                >
                  Clear replay
                </button>
              </div>
            </>
          ) : (
            <div className="sa-muted-panel">
              <p className="sa-muted-panel__title">No replay attached yet.</p>
              <p className="sa-muted-panel__body">
                Load the tape, define a replay window, then start the run from the action card below. Once attached, run/pause/step stays here.
              </p>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
