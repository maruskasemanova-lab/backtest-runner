import type { Dispatch, SetStateAction } from "react";

type RootsFormState = { ohlcv_data_dirs: string; l2_data_dirs: string };

interface DataManagerSettingsCardProps {
  settingsOpen: boolean;
  setSettingsOpen: Dispatch<SetStateAction<boolean>>;
  settings: any;
  apiKeyInput: string;
  setApiKeyInput: Dispatch<SetStateAction<string>>;
  rootsForm: RootsFormState;
  setRootsForm: Dispatch<SetStateAction<RootsFormState>>;
  savingApiKey: boolean;
  savingRoots: boolean;
  onSaveApiKey: () => void;
  onSaveRoots: () => void;
}

export default function DataManagerSettingsCard({
  settingsOpen,
  setSettingsOpen,
  settings,
  apiKeyInput,
  setApiKeyInput,
  rootsForm,
  setRootsForm,
  savingApiKey,
  savingRoots,
  onSaveApiKey,
  onSaveRoots,
}: DataManagerSettingsCardProps) {
  return (
    <div className={`card dm-settings-card ${settingsOpen ? "open" : ""}`}>
      <div className="card-header dm-settings-toggle" onClick={() => setSettingsOpen(!settingsOpen)}>
        <span className="card-title">⚙ Settings</span>
        <span className={`dm-chevron ${settingsOpen ? "open" : ""}`}>▸</span>
      </div>
      {settingsOpen && (
        <div className="card-body">
          <div className="dm-settings-section">
            <div className="dm-settings-label">Databento API Key</div>
            <div className="dm-api-status">
              <span className={`dm-status-dot ${settings?.databento_api_key_set ? "active" : ""}`} />
              <span className="dm-api-hint">
                {settings?.databento_api_key_set
                  ? `${settings.databento_api_key_hint} (${settings.databento_api_key_source})`
                  : "Not configured"}
              </span>
            </div>
            <div className="dm-inline-form">
              <input
                type="password"
                value={apiKeyInput}
                onChange={(e) => setApiKeyInput(e.target.value)}
                placeholder="db-..."
              />
              <button
                className="btn btn-secondary btn-sm"
                onClick={onSaveApiKey}
                disabled={savingApiKey}
              >
                {savingApiKey ? "..." : "Save"}
              </button>
            </div>
          </div>

          <div className="dm-settings-section">
            <div className="dm-settings-label">OHLCV Data Roots</div>
            <textarea
              className="dm-textarea"
              value={rootsForm.ohlcv_data_dirs}
              onChange={(e) =>
                setRootsForm((prev) => ({ ...prev, ohlcv_data_dirs: e.target.value }))
              }
              rows={2}
              placeholder="One path per line"
            />
          </div>

          <div className="dm-settings-section">
            <div className="dm-settings-label">L2 Data Roots</div>
            <textarea
              className="dm-textarea"
              value={rootsForm.l2_data_dirs}
              onChange={(e) =>
                setRootsForm((prev) => ({ ...prev, l2_data_dirs: e.target.value }))
              }
              rows={2}
              placeholder="One path per line"
            />
          </div>

          <div className="dm-btn-row">
            <button
              className="btn btn-secondary"
              onClick={onSaveRoots}
              disabled={savingRoots}
            >
              {savingRoots ? "Saving..." : "💾 Save Roots"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
