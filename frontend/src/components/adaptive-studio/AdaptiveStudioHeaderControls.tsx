type AdaptiveStudioHeaderControlsProps = {
  activeTicker: string;
  availableTickers: string[];
  hasTickers: boolean;
  onTickerChange?: (ticker: string) => void;
  onReload: () => void;
  onSave: () => void;
  reloadDisabled: boolean;
  saveDisabled: boolean;
  reloadLoading: boolean;
  saveLoading: boolean;
};

export default function AdaptiveStudioHeaderControls({
  activeTicker,
  availableTickers,
  hasTickers,
  onTickerChange,
  onReload,
  onSave,
  reloadDisabled,
  saveDisabled,
  reloadLoading,
  saveLoading,
}: AdaptiveStudioHeaderControlsProps) {
  return (
    <div className="card-header">
      <span className="card-title">Adaptive Strategy Studio</span>
      <div className="adaptive-toolbar">
        <select
          className="studio-header-ticker"
          value={activeTicker}
          onChange={(e) => {
            if (onTickerChange) onTickerChange(e.target.value);
          }}
          disabled={!hasTickers}
          title="Active ticker"
        >
          {!hasTickers && <option value="">No ticker</option>}
          {availableTickers.map((ticker) => (
            <option key={ticker} value={ticker}>
              {ticker}
            </option>
          ))}
        </select>
        <button
          type="button"
          className="btn btn-secondary"
          onClick={onReload}
          disabled={reloadDisabled}
        >
          {reloadLoading ? "Loading..." : "Reload"}
        </button>
        <button
          type="button"
          className="btn btn-primary"
          onClick={onSave}
          disabled={saveDisabled}
        >
          {saveLoading ? "Saving..." : "Save"}
        </button>
      </div>
    </div>
  );
}
