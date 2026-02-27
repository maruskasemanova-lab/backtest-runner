import { memo } from "react";

type Props = {
  title: string;
  regimeKey: string;
  selectedStrategies: string[];
  strategyUniverse: string[];
  strategyLabel: (name: string) => string;
  onMoveItem: (index: number, direction: number) => void;
  onToggleStrategy: (strategy: string) => void;
};

function AdaptiveStudioPriorityEditor({
  title,
  regimeKey,
  selectedStrategies,
  strategyUniverse,
  strategyLabel,
  onMoveItem,
  onToggleStrategy,
}: Props) {
  return (
    <div className="adaptive-priority-editor">
      <div className="adaptive-priority-header">
        <span>{title}</span>
        <span className="adaptive-priority-count">{selectedStrategies.length} selected</span>
      </div>

      <div className="adaptive-priority-list">
        {selectedStrategies.length === 0 && (
          <div className="adaptive-empty">No strategies selected.</div>
        )}
        {selectedStrategies.map((name, index) => (
          <div className="adaptive-priority-item" key={`${regimeKey}-${name}`}>
            <div className="adaptive-priority-item-title">
              <span className="adaptive-priority-rank">#{index + 1}</span>
              <span>{strategyLabel(name)}</span>
            </div>
            <div className="adaptive-priority-item-actions">
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => onMoveItem(index, -1)}
                disabled={index === 0}
              >
                Up
              </button>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => onMoveItem(index, 1)}
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
              key={`${regimeKey}-chip-${name}`}
              className={`adaptive-chip ${active ? "active" : ""}`}
              onClick={() => onToggleStrategy(name)}
            >
              {strategyLabel(name)}
            </button>
          );
        })}
      </div>
    </div>
  );
}

export default memo(AdaptiveStudioPriorityEditor);
