import { useMemo } from "react";
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

type RangeWindowState = {
  canStart: boolean;
  durationLabel: string;
  statusLabel: string;
  helperLabel: string;
};

function formatRangeDateTime(value: string | null): string {
  if (!value) return "Not set";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Invalid";
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function describeRangeWindow(from: string | null, to: string | null): RangeWindowState {
  if (!from || !to) {
    return {
      canStart: false,
      durationLabel: "Not ready",
      statusLabel: "Window not set",
      helperLabel: "Choose exact start and end timestamps for the replay segment.",
    };
  }

  const fromDate = new Date(from);
  const toDate = new Date(to);
  const fromMs = fromDate.getTime();
  const toMs = toDate.getTime();
  if (Number.isNaN(fromMs) || Number.isNaN(toMs)) {
    return {
      canStart: false,
      durationLabel: "Invalid",
      statusLabel: "Check timestamps",
      helperLabel: "One of the replay timestamps is invalid.",
    };
  }
  if (toMs < fromMs) {
    return {
      canStart: false,
      durationLabel: "Reversed",
      statusLabel: "End precedes start",
      helperLabel: "Replay end must be after replay start.",
    };
  }

  const totalMinutes = Math.max(0, Math.round((toMs - fromMs) / 60000));
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  const durationParts = [];
  if (hours > 0) durationParts.push(`${hours}h`);
  durationParts.push(`${minutes}m`);
  return {
    canStart: true,
    durationLabel: durationParts.join(" "),
    statusLabel: "Replay ready",
    helperLabel: `${formatRangeDateTime(from)} -> ${formatRangeDateTime(to)}`,
  };
}

function WfoField({
  label,
  hint,
  value,
  onChange,
  disabled,
  placeholder,
}: {
  label: string;
  hint: string;
  value: string;
  onChange: (value: string) => void;
  disabled: boolean;
  placeholder: string;
}) {
  return (
    <label className="sa-control-field">
      <span className="sa-control-label">{label}</span>
      <input
        className="sa-control-input"
        type="text"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        disabled={disabled}
        placeholder={placeholder}
      />
      <span className="sa-field-help">{hint}</span>
    </label>
  );
}

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
  const rangeWindow = useMemo(
    () => describeRangeWindow(selectedRangeFrom, selectedRangeTo),
    [selectedRangeFrom, selectedRangeTo],
  );
  const activeVariant = useMemo(
    () =>
      rankedWfoResults.find(
        (variant) => variant.id === (selectedWfoVariantId || bestWfoVariantId || rankedWfoResults[0]?.id),
      ) || null,
    [bestWfoVariantId, rankedWfoResults, selectedWfoVariantId],
  );
  const activeVariantMetrics = activeVariant?.metrics || null;

  return (
    <div className="card sa-range-card">
      <div className="sa-range-card__hero">
        <div className="sa-range-header">
          <div className="sa-section-kicker">Replay Window</div>
          <div className="sa-section-title">Define the exact market segment</div>
          <p className="sa-section-description">
            Focus on the regime transition, failed entry cluster or breakout leg you actually want to stress test.
          </p>
        </div>

        <div className="sa-range-hero-metrics">
          <div className="sa-mini-stat">
            <span className="sa-mini-stat__label">Window</span>
            <strong className="sa-mini-stat__value">{rangeWindow.statusLabel}</strong>
            <span className="sa-mini-stat__meta">{rangeWindow.helperLabel}</span>
          </div>
          <div className="sa-mini-stat">
            <span className="sa-mini-stat__label">Duration</span>
            <strong className="sa-mini-stat__value">{rangeWindow.durationLabel}</strong>
            <span className="sa-mini-stat__meta">
              {wfoEnabled ? "Sweep executes before replay" : "Replay starts immediately"}
            </span>
          </div>
        </div>
      </div>

      <div className="sa-form-grid">
        <label className="sa-control-field sa-control-field-tight">
          <span className="sa-control-label">Replay start</span>
          <input
            className="sa-control-input"
            type="datetime-local"
            value={selectedRangeFrom || ""}
            onChange={(event) => setSelectedRangeFrom(event.target.value)}
            step="60"
          />
        </label>

        <label className="sa-control-field sa-control-field-tight">
          <span className="sa-control-label">Replay end</span>
          <input
            className="sa-control-input"
            type="datetime-local"
            value={selectedRangeTo || ""}
            onChange={(event) => setSelectedRangeTo(event.target.value)}
            step="60"
          />
        </label>
      </div>

      <div className="sa-action-row">
        <button type="button" className="btn btn-secondary" onClick={onOpenStrategyEditor}>
          Tune strategy
        </button>

        <button
          type="button"
          className="btn btn-primary"
          onClick={wfoEnabled ? onRunWfo : onStartTest}
          disabled={!rangeWindow.canStart || busy}
        >
          {busy ? (wfoEnabled ? "Running sweep..." : "Starting replay...") : wfoEnabled ? "Run sweep + replay" : "Start replay"}
        </button>
      </div>

      <div className="sa-inline-meta sa-inline-meta-spread">
        {selectedRangeFrom && selectedRangeTo ? (
          <button type="button" className="sa-text-btn" onClick={onClearRange}>
            Clear replay window
          </button>
        ) : null}
        <span className={`sa-state-pill ${rangeWindow.canStart ? "is-ready" : "is-idle"}`}>
          {rangeWindow.statusLabel}
        </span>
      </div>

      <div className="sa-wfo-panel">
        <div className="sa-wfo-panel__head">
          <label className="sa-check-row">
            <input
              type="checkbox"
              checked={wfoEnabled}
              onChange={(event) => onWfoEnabledChange(event.target.checked)}
              disabled={busy}
            />
            <span>Run optimization sweep before replay</span>
          </label>
          <span className="sa-meta-pill">Est. {wfoEstimatedCombinations} combos</span>
        </div>

        {wfoEnabled ? (
          <>
            <div className="sa-muted-panel">
              <p className="sa-muted-panel__title">Use sweep mode only for deliberate what-if work.</p>
              <p className="sa-muted-panel__body">
                Keep the grid narrow, compare only a few ideas and then inspect the winning variant through the exact same replay window.
              </p>
            </div>

            <div className="sa-wfo-grid">
              <WfoField
                label="Stop floor %"
                hint="context_risk_min_sl_pct"
                value={wfoGridConfig.contextRiskMinSlValues}
                onChange={(value) => onWfoGridConfigChange({ contextRiskMinSlValues: value })}
                disabled={busy}
                placeholder="0.30, 0.50"
              />
              <WfoField
                label="Time stop (bars)"
                hint="time_exit_bars"
                value={wfoGridConfig.timeExitBarsValues}
                onChange={(value) => onWfoGridConfigChange({ timeExitBarsValues: value })}
                disabled={busy}
                placeholder="7, 12"
              />
              <WfoField
                label="Break-even min R"
                hint="break_even_activation_min_r"
                value={wfoGridConfig.breakEvenMinRValues}
                onChange={(value) => onWfoGridConfigChange({ breakEvenMinRValues: value })}
                disabled={busy}
                placeholder="0.40, 0.60"
              />
              <WfoField
                label="Book proof threshold"
                hint="break_even_l2_proof_book_pressure_threshold"
                value={wfoGridConfig.breakEvenProofBookPressureValues}
                onChange={(value) =>
                  onWfoGridConfigChange({ breakEvenProofBookPressureValues: value })
                }
                disabled={busy}
                placeholder="0.03, 0.06"
              />
              <WfoField
                label="EV relaxation"
                hint="ev_relaxation_threshold"
                value={wfoGridConfig.evRelaxationThresholdValues}
                onChange={(value) => onWfoGridConfigChange({ evRelaxationThresholdValues: value })}
                disabled={busy}
                placeholder="7, 10"
              />
              <WfoField
                label="Aggression block z"
                hint="signed_aggression_block_z_threshold"
                value={wfoGridConfig.signedAggressionBlockZValues}
                onChange={(value) =>
                  onWfoGridConfigChange({ signedAggressionBlockZValues: value })
                }
                disabled={busy}
                placeholder="1.65, 1.20"
              />
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
                <span>Include baseline variant</span>
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
                <span className="sa-control-label">Workers</span>
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
            </div>
          </>
        ) : null}

        {wfoIsRunning ? <div className="sa-status-note">{wfoProgressLabel}</div> : null}

        {rankedWfoResults.length > 0 ? (
          <div className="sa-results-box">
            <div className="sa-results-box__head">
              <div className="sa-results-title">Sweep results</div>
              {activeVariant ? (
                <span className="sa-state-pill is-success">
                  {activeVariant.id === bestWfoVariantId ? "Best variant selected" : "Replay variant loaded"}
                </span>
              ) : null}
            </div>

            {activeVariant && activeVariantMetrics ? (
              <div className="sa-results-summary">
                <div className="sa-mini-stat">
                  <span className="sa-mini-stat__label">Variant</span>
                  <strong className="sa-mini-stat__value">{activeVariant.label}</strong>
                  <span className="sa-mini-stat__meta">
                    {activeVariant.id === bestWfoVariantId ? "Top-ranked sweep result" : "Selected playback variant"}
                  </span>
                </div>
                <div className="sa-mini-stat">
                  <span className="sa-mini-stat__label">PnL</span>
                  <strong className="sa-mini-stat__value">
                    ${Number(activeVariantMetrics.totalPnlDollars || 0).toFixed(2)}
                  </strong>
                  <span className="sa-mini-stat__meta">
                    WR {Number(activeVariantMetrics.winRate || 0).toFixed(1)}%
                  </span>
                </div>
              </div>
            ) : null}

            <label className="sa-control-field">
              <span className="sa-control-label">Replay variant</span>
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
