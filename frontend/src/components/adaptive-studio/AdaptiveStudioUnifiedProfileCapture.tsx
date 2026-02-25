type Props = {
  draftName: string;
  activeTicker: string;
  onDraftNameChange: (value: string) => void;
  onCapture: () => void;
  captureDisabled: boolean;
  captureLoading: boolean;
};

export default function AdaptiveStudioUnifiedProfileCapture({
  draftName,
  activeTicker,
  onDraftNameChange,
  onCapture,
  captureDisabled,
  captureLoading,
}: Props) {
  return (
    <div className="adaptive-section">
      <h3>Unified Profiles</h3>
      <div style={{ display: "flex", gap: 8, alignItems: "end" }}>
        <div className="form-group" style={{ flex: 1 }}>
          <label htmlFor="unified_profile_name">Profile name</label>
          <input
            id="unified_profile_name"
            type="text"
            value={draftName}
            onChange={(e) => onDraftNameChange(e.target.value)}
            placeholder={`${activeTicker || "TICKER"}-profile`}
          />
        </div>
        <button
          type="button"
          className="btn btn-primary btn-sm"
          onClick={onCapture}
          disabled={captureDisabled}
        >
          {captureLoading ? "Saving..." : "Capture"}
        </button>
      </div>
      <div className="adaptive-empty" style={{ marginTop: 6 }}>
        Jeden profil obsahuje sekcie Strategy profile + Execution profile.
      </div>
    </div>
  );
}
