import type {
  StrategyAnalyzerWfoGridConfig,
  StrategyAnalyzerWfoVariantResult,
} from "./types";

type Props = {
  selectedRangeFrom: string | null;
  selectedRangeTo: string | null;
  setSelectedRangeFrom: (value: string | null) => void;
  setSelectedRangeTo: (value: string | null) => void;
  onClearRange: () => void;
  onOpenStrategyEditor: () => void;
  onStartTest: () => void;
  onRunWfo: () => void;
  runLoading: boolean;
  wfoEnabled: boolean;
  onWfoEnabledChange: (value: boolean) => void;
  wfoGridConfig: StrategyAnalyzerWfoGridConfig;
  onWfoGridConfigChange: (patch: Partial<StrategyAnalyzerWfoGridConfig>) => void;
  wfoEstimatedCombinations: number;
  wfoIsRunning: boolean;
  wfoProgressLabel: string;
  rankedWfoResults: StrategyAnalyzerWfoVariantResult[];
  selectedWfoVariantId: string | null;
  bestWfoVariantId: string | null;
  onSelectWfoVariant: (variantId: string) => void;
};

export default function StrategyAnalyzerRangeActions({
  selectedRangeFrom,
  selectedRangeTo,
  setSelectedRangeFrom,
  setSelectedRangeTo,
  onClearRange,
  onOpenStrategyEditor,
  onStartTest,
  onRunWfo,
  runLoading,
  wfoEnabled,
  onWfoEnabledChange,
  wfoGridConfig,
  onWfoGridConfigChange,
  wfoEstimatedCombinations,
  wfoIsRunning,
  wfoProgressLabel,
  rankedWfoResults,
  selectedWfoVariantId,
  bestWfoVariantId,
  onSelectWfoVariant,
}: Props) {
  const busy = runLoading || wfoIsRunning;

  return (
    <div className="card sa-range-card">
      <div className="sa-range-toolbar">
        <div className="sa-range-header">
          <div className="sa-section-kicker">Playback Window</div>
          <div className="sa-section-title">Test Range</div>
        </div>

        <label className="sa-control-field sa-control-field-tight">
          <span className="sa-control-label">From</span>
          <input
            className="sa-control-input"
            type="datetime-local"
            value={selectedRangeFrom || ""}
            onChange={(e) => setSelectedRangeFrom(e.target.value)}
            step="60"
          />
        </label>

        <label className="sa-control-field sa-control-field-tight">
          <span className="sa-control-label">To</span>
          <input
            className="sa-control-input"
            type="datetime-local"
            value={selectedRangeTo || ""}
            onChange={(e) => setSelectedRangeTo(e.target.value)}
            step="60"
          />
        </label>

        {selectedRangeFrom && selectedRangeTo ? (
          <button type="button" className="sa-text-btn" onClick={onClearRange}>
            Clear range
          </button>
        ) : null}
      </div>

      <div className="sa-action-row">
        <button type="button" className="btn btn-secondary" onClick={onOpenStrategyEditor}>
          Edit Strategy
        </button>

        <button
          type="button"
          className="btn btn-primary"
          onClick={wfoEnabled ? onRunWfo : onStartTest}
          disabled={!selectedRangeFrom || !selectedRangeTo || busy}
        >
          {busy
            ? wfoEnabled
              ? "Running WFO..."
              : "Starting..."
            : wfoEnabled
              ? "Run WFO"
              : "Start Test"}
        </button>
      </div>

      <div className="sa-wfo-panel">
        <label className="sa-check-row">
          <input
            type="checkbox"
            checked={wfoEnabled}
            onChange={(event) => onWfoEnabledChange(event.target.checked)}
            disabled={busy}
          />
          <span>Enable WFO Combo Sweep Before Playback</span>
        </label>

        {wfoEnabled ? (
          <>
            <div className="sa-wfo-grid">
              <label className="sa-control-field">
                <span className="sa-control-label">
                  Min SL % (`context_risk_min_sl_pct`)
                </span>
                <input
                  className="sa-control-input"
                  type="text"
                  value={wfoGridConfig.contextRiskMinSlValues}
                  onChange={(event) =>
                    onWfoGridConfigChange({ contextRiskMinSlValues: event.target.value })
                  }
                  disabled={busy}
                  placeholder="0.30, 0.50"
                />
              </label>

              <label className="sa-control-field">
                <span className="sa-control-label">Time Exit Bars (`time_exit_bars`)</span>
                <input
                  className="sa-control-input"
                  type="text"
                  value={wfoGridConfig.timeExitBarsValues}
                  onChange={(event) =>
                    onWfoGridConfigChange({ timeExitBarsValues: event.target.value })
                  }
                  disabled={busy}
                  placeholder="7, 12"
                />
              </label>

              <label className="sa-control-field">
                <span className="sa-control-label">
                  Break-even Min R (`break_even_activation_min_r`)
                </span>
                <input
                  className="sa-control-input"
                  type="text"
                  value={wfoGridConfig.breakEvenMinRValues}
                  onChange={(event) =>
                    onWfoGridConfigChange({ breakEvenMinRValues: event.target.value })
                  }
                  disabled={busy}
                  placeholder="0.40, 0.60"
                />
              </label>

              <label className="sa-control-field">
                <span className="sa-control-label">
                  BE L2 Proof (`break_even_l2_proof_book_pressure_threshold`)
                </span>
                <input
                  className="sa-control-input"
                  type="text"
                  value={wfoGridConfig.breakEvenProofBookPressureValues}
                  onChange={(event) =>
                    onWfoGridConfigChange({
                      breakEvenProofBookPressureValues: event.target.value,
                    })
                  }
                  disabled={busy}
                  placeholder="0.03, 0.06"
                />
              </label>

              <label className="sa-control-field">
                <span className="sa-control-label">
                  EV Relaxation Threshold (`ev_relaxation_threshold`)
                </span>
                <input
                  className="sa-control-input"
                  type="text"
                  value={wfoGridConfig.evRelaxationThresholdValues}
                  onChange={(event) =>
                    onWfoGridConfigChange({ evRelaxationThresholdValues: event.target.value })
                  }
                  disabled={busy}
                  placeholder="7, 10"
                />
              </label>

              <label className="sa-control-field">
                <span className="sa-control-label">
                  Aggression Block Z (`signed_aggression_block_z_threshold`)
                </span>
                <input
                  className="sa-control-input"
                  type="text"
                  value={wfoGridConfig.signedAggressionBlockZValues}
                  onChange={(event) =>
                    onWfoGridConfigChange({
                      signedAggressionBlockZValues: event.target.value,
                    })
                  }
                  disabled={busy}
                  placeholder="1.65, 1.20"
                />
              </label>
            </div>

            <div className="sa-inline-meta">
              <label className="sa-check-row sa-check-row-compact">
                <input
                  type="checkbox"
                  checked={wfoGridConfig.includeBaseline}
                  onChange={(event) =>
                    onWfoGridConfigChange({ includeBaseline: event.target.checked })
                  }
                  disabled={busy}
                />
                <span>Include baseline</span>
              </label>

              <label className="sa-inline-field">
                <span className="sa-control-label">Max combos</span>
                <input
                  className="sa-control-input"
                  type="number"
                  min={1}
                  max={128}
                  value={wfoGridConfig.maxCombinations}
                  onChange={(event) =>
                    onWfoGridConfigChange({
                      maxCombinations: Math.max(1, Math.trunc(Number(event.target.value) || 1)),
                    })
                  }
                  disabled={busy}
                />
              </label>

              <label className="sa-inline-field">
                <span className="sa-control-label">Parallel workers</span>
                <input
                  className="sa-control-input"
                  type="number"
                  min={1}
                  max={8}
                  value={wfoGridConfig.parallelWorkers}
                  onChange={(event) =>
                    onWfoGridConfigChange({
                      parallelWorkers: Math.max(
                        1,
                        Math.min(8, Math.trunc(Number(event.target.value) || 1)),
                      ),
                    })
                  }
                  disabled={busy}
                />
              </label>

              <span className="sa-meta-pill">
                Estimated combinations: {wfoEstimatedCombinations}
              </span>
            </div>
          </>
        ) : null}

        {wfoIsRunning ? <div className="sa-status-note">{wfoProgressLabel}</div> : null}

        {rankedWfoResults.length > 0 ? (
          <div className="sa-results-box">
            <div className="sa-results-title">WFO Results</div>
            <label className="sa-control-field">
              <span className="sa-control-label">Playback variant</span>
              <select
                className="sa-control-input"
                value={selectedWfoVariantId || bestWfoVariantId || rankedWfoResults[0]?.id || ""}
                onChange={(event) => onSelectWfoVariant(event.target.value)}
              >
                {rankedWfoResults.map((variant) => {
                  const metrics = variant.metrics;
                  const suffix = metrics
                    ? ` | PnL $${Number(metrics.totalPnlDollars || 0).toFixed(2)} | WR ${Number(
                        metrics.winRate || 0,
                      ).toFixed(1)}%`
                    : "";
                  const bestMark = variant.id === bestWfoVariantId ? " ★ BEST" : "";
                  return (
                    <option key={variant.id} value={variant.id}>
                      {variant.label}
                      {suffix}
                      {bestMark}
                    </option>
                  );
                })}
              </select>
            </label>
          </div>
        ) : null}
      </div>
    </div>
  );
}
