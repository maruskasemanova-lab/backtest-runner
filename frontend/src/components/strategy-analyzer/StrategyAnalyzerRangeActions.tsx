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
    <div className="card" style={{ padding: "0.75rem 1rem" }}>
      <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", flexWrap: "wrap" }}>
        <label style={{ fontWeight: 600, fontSize: "0.85rem", color: "var(--text-secondary)" }}>
          Test Range
        </label>

        <input
          type="datetime-local"
          value={selectedRangeFrom || ""}
          onChange={(e) => setSelectedRangeFrom(e.target.value)}
          step="60"
          style={{
            padding: "4px 8px",
            borderRadius: "var(--radius-sm)",
            border: "1px solid var(--border-color)",
            background: "var(--bg-secondary)",
            color: "var(--text-primary)",
            fontSize: "0.85rem",
          }}
        />
        <span style={{ color: "var(--text-muted)" }}>&rarr;</span>
        <input
          type="datetime-local"
          value={selectedRangeTo || ""}
          onChange={(e) => setSelectedRangeTo(e.target.value)}
          step="60"
          style={{
            padding: "4px 8px",
            borderRadius: "var(--radius-sm)",
            border: "1px solid var(--border-color)",
            background: "var(--bg-secondary)",
            color: "var(--text-primary)",
            fontSize: "0.85rem",
          }}
        />

        {selectedRangeFrom && selectedRangeTo ? (
          <button
            onClick={onClearRange}
            style={{
              background: "none",
              border: "none",
              color: "var(--text-muted)",
              cursor: "pointer",
              fontSize: "0.8rem",
            }}
          >
            clear
          </button>
        ) : null}

        <div style={{ flex: 1 }} />

        <button
          className="btn"
          onClick={onOpenStrategyEditor}
          style={{ padding: "6px 16px", fontSize: "0.85rem", fontWeight: 600 }}
        >
          Edit Strategy
        </button>

        <button
          className="btn btn-primary"
          onClick={wfoEnabled ? onRunWfo : onStartTest}
          disabled={!selectedRangeFrom || !selectedRangeTo || busy}
          style={{ padding: "6px 16px", fontSize: "0.85rem", fontWeight: 600 }}
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

      <div
        style={{
          marginTop: "0.75rem",
          borderTop: "1px solid var(--border-color)",
          paddingTop: "0.75rem",
          display: "flex",
          flexDirection: "column",
          gap: "0.55rem",
        }}
      >
        <label style={{ display: "inline-flex", alignItems: "center", gap: 8, fontSize: "0.8rem", color: "var(--text-secondary)" }}>
          <input
            type="checkbox"
            checked={wfoEnabled}
            onChange={(event) => onWfoEnabledChange(event.target.checked)}
            disabled={busy}
          />
          Enable WFO Combo Sweep Before Playback
        </label>

        {wfoEnabled ? (
          <>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))", gap: "8px 10px" }}>
              <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                Min SL % (`context_risk_min_sl_pct`)
                <input
                  type="text"
                  value={wfoGridConfig.contextRiskMinSlValues}
                  onChange={(event) =>
                    onWfoGridConfigChange({ contextRiskMinSlValues: event.target.value })
                  }
                  disabled={busy}
                  placeholder="0.30, 0.50"
                  style={{
                    padding: "4px 8px",
                    borderRadius: "var(--radius-sm)",
                    border: "1px solid var(--border-color)",
                    background: "var(--bg-secondary)",
                    color: "var(--text-primary)",
                    fontSize: "0.78rem",
                  }}
                />
              </label>

              <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                Time Exit Bars (`time_exit_bars`)
                <input
                  type="text"
                  value={wfoGridConfig.timeExitBarsValues}
                  onChange={(event) => onWfoGridConfigChange({ timeExitBarsValues: event.target.value })}
                  disabled={busy}
                  placeholder="7, 12"
                  style={{
                    padding: "4px 8px",
                    borderRadius: "var(--radius-sm)",
                    border: "1px solid var(--border-color)",
                    background: "var(--bg-secondary)",
                    color: "var(--text-primary)",
                    fontSize: "0.78rem",
                  }}
                />
              </label>

              <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                Break-even Min R (`break_even_activation_min_r`)
                <input
                  type="text"
                  value={wfoGridConfig.breakEvenMinRValues}
                  onChange={(event) => onWfoGridConfigChange({ breakEvenMinRValues: event.target.value })}
                  disabled={busy}
                  placeholder="0.40, 0.60"
                  style={{
                    padding: "4px 8px",
                    borderRadius: "var(--radius-sm)",
                    border: "1px solid var(--border-color)",
                    background: "var(--bg-secondary)",
                    color: "var(--text-primary)",
                    fontSize: "0.78rem",
                  }}
                />
              </label>

              <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                BE L2 Proof (`break_even_l2_proof_book_pressure_threshold`)
                <input
                  type="text"
                  value={wfoGridConfig.breakEvenProofBookPressureValues}
                  onChange={(event) =>
                    onWfoGridConfigChange({ breakEvenProofBookPressureValues: event.target.value })
                  }
                  disabled={busy}
                  placeholder="0.03, 0.06"
                  style={{
                    padding: "4px 8px",
                    borderRadius: "var(--radius-sm)",
                    border: "1px solid var(--border-color)",
                    background: "var(--bg-secondary)",
                    color: "var(--text-primary)",
                    fontSize: "0.78rem",
                  }}
                />
              </label>

              <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                EV Relaxation Threshold (`ev_relaxation_threshold`)
                <input
                  type="text"
                  value={wfoGridConfig.evRelaxationThresholdValues}
                  onChange={(event) =>
                    onWfoGridConfigChange({ evRelaxationThresholdValues: event.target.value })
                  }
                  disabled={busy}
                  placeholder="7, 10"
                  style={{
                    padding: "4px 8px",
                    borderRadius: "var(--radius-sm)",
                    border: "1px solid var(--border-color)",
                    background: "var(--bg-secondary)",
                    color: "var(--text-primary)",
                    fontSize: "0.78rem",
                  }}
                />
              </label>

              <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                Aggression Block Z (`signed_aggression_block_z_threshold`)
                <input
                  type="text"
                  value={wfoGridConfig.signedAggressionBlockZValues}
                  onChange={(event) =>
                    onWfoGridConfigChange({ signedAggressionBlockZValues: event.target.value })
                  }
                  disabled={busy}
                  placeholder="1.65, 1.20"
                  style={{
                    padding: "4px 8px",
                    borderRadius: "var(--radius-sm)",
                    border: "1px solid var(--border-color)",
                    background: "var(--bg-secondary)",
                    color: "var(--text-primary)",
                    fontSize: "0.78rem",
                  }}
                />
              </label>
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
              <label style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                <input
                  type="checkbox"
                  checked={wfoGridConfig.includeBaseline}
                  onChange={(event) => onWfoGridConfigChange({ includeBaseline: event.target.checked })}
                  disabled={busy}
                />
                Include baseline
              </label>

              <label style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                Max combos
                <input
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
                  style={{
                    width: 72,
                    padding: "4px 8px",
                    borderRadius: "var(--radius-sm)",
                    border: "1px solid var(--border-color)",
                    background: "var(--bg-secondary)",
                    color: "var(--text-primary)",
                    fontSize: "0.75rem",
                  }}
                />
              </label>

              <label style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                Parallel workers
                <input
                  type="number"
                  min={1}
                  max={8}
                  value={wfoGridConfig.parallelWorkers}
                  onChange={(event) =>
                    onWfoGridConfigChange({
                      parallelWorkers: Math.max(1, Math.min(8, Math.trunc(Number(event.target.value) || 1))),
                    })
                  }
                  disabled={busy}
                  style={{
                    width: 72,
                    padding: "4px 8px",
                    borderRadius: "var(--radius-sm)",
                    border: "1px solid var(--border-color)",
                    background: "var(--bg-secondary)",
                    color: "var(--text-primary)",
                    fontSize: "0.75rem",
                  }}
                />
              </label>

              <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                Estimated combinations: {wfoEstimatedCombinations}
              </span>
            </div>
          </>
        ) : null}

        {wfoIsRunning ? (
          <div style={{ fontSize: "0.78rem", color: "var(--accent-blue)" }}>{wfoProgressLabel}</div>
        ) : null}

        {rankedWfoResults.length > 0 ? (
          <div
            style={{
              marginTop: "0.25rem",
              border: "1px solid var(--border-color)",
              borderRadius: "var(--radius-sm)",
              padding: "8px",
              background: "var(--bg-secondary)",
              display: "flex",
              flexDirection: "column",
              gap: "6px",
            }}
          >
            <div style={{ fontSize: "0.76rem", color: "var(--text-secondary)", fontWeight: 700 }}>
              WFO Results
            </div>
            <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: "0.74rem", color: "var(--text-secondary)" }}>
              Playback variant
              <select
                value={selectedWfoVariantId || bestWfoVariantId || rankedWfoResults[0]?.id || ""}
                onChange={(event) => onSelectWfoVariant(event.target.value)}
                style={{
                  padding: "4px 8px",
                  borderRadius: "var(--radius-sm)",
                  border: "1px solid var(--border-color)",
                  background: "var(--bg-primary)",
                  color: "var(--text-primary)",
                  fontSize: "0.75rem",
                }}
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
