type Props = {
  selectedStrategies: string[];
  strategyUniverse: string[];
  strategyLabel: (name: string) => string;
  onMoveStrategy: (index: number, direction: number) => void;
  onToggleStrategy: (name: string) => void;
};

export default function AdaptiveStudioFlowBiasPriorityEditor({
  selectedStrategies,
  strategyUniverse,
  strategyLabel,
  onMoveStrategy,
  onToggleStrategy,
}: Props) {
  return (
    <div className="adaptive-section">
      <div className="adaptive-priority-editor">
        <div className="adaptive-priority-header">
          <span>Flow bias strategy order</span>
          <span className="adaptive-priority-count">{selectedStrategies.length} selected</span>
        </div>

        <div className="adaptive-priority-list">
          {selectedStrategies.length === 0 && (
            <div className="adaptive-empty">No flow-bias strategies selected.</div>
          )}
          {selectedStrategies.map((name, index) => (
            <div className="adaptive-priority-item" key={`flow-bias-${name}`}>
              <div className="adaptive-priority-item-title">
                <span className="adaptive-priority-rank">#{index + 1}</span>
                <span>{strategyLabel(name)}</span>
              </div>
              <div className="adaptive-priority-item-actions">
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={() => onMoveStrategy(index, -1)}
                  disabled={index === 0}
                >
                  Up
                </button>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={() => onMoveStrategy(index, 1)}
                  disabled={index === selectedStrategies.length - 1}
                >
                  Down
                </button>
                <button
                  type="button"
                  className="btn btn-danger btn-sm"
                  onClick={() => onToggleStrategy(name)}
                >
                  Remove
                </button>
              </div>
            </div>
          ))}
        </div>

        <div className="adaptive-chip-grid">
          {strategyUniverse.map((name) => {
            const active = selectedStrategies.includes(name);
            return (
              <button
                type="button"
                key={`flow-chip-${name}`}
                className={`adaptive-chip ${active ? "active" : ""}`}
                onClick={() => onToggleStrategy(name)}
              >
                {strategyLabel(name)}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
