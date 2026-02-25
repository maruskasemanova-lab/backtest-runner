type Props = {
  selectedRangeFrom: string | null;
  selectedRangeTo: string | null;
  setSelectedRangeFrom: (value: string | null) => void;
  setSelectedRangeTo: (value: string | null) => void;
  onClearRange: () => void;
  onOpenStrategyEditor: () => void;
  onStartTest: () => void;
  runLoading: boolean;
};

export default function StrategyAnalyzerRangeActions({
  selectedRangeFrom,
  selectedRangeTo,
  setSelectedRangeFrom,
  setSelectedRangeTo,
  onClearRange,
  onOpenStrategyEditor,
  onStartTest,
  runLoading,
}: Props) {
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
          onClick={onStartTest}
          disabled={!selectedRangeFrom || !selectedRangeTo || runLoading}
          style={{ padding: "6px 16px", fontSize: "0.85rem", fontWeight: 600 }}
        >
          {runLoading ? "Starting..." : "Start Test"}
        </button>
      </div>
    </div>
  );
}
