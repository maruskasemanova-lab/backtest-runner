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
      <button
        type="button"
        className="card-header dm-settings-toggle"
        onClick={() => setSettingsOpen(!settingsOpen)}
        aria-expanded={settingsOpen}
        aria-controls="dm_settings_panel"
      >
        <span className="card-title">⚙ Settings</span>
        <span className={`dm-chevron ${settingsOpen ? "open" : ""}`}>▸</span>
      </button>
      {settingsOpen && (
        <div className="card-body" id="dm_settings_panel">
          <div className="dm-card-intro">
            Keep credentials and storage roots explicit. Each field is labeled directly so changes
            are easier to audit before saving.
          </div>

          <div className="dm-settings-section">
            <label className="dm-settings-label" htmlFor="dm_settings_api_key">
              Databento API Key
            </label>
            <div className="dm-api-status">
              <span className={`dm-status-dot ${settings?.databento_api_key_set ? "active" : ""}`} />
              <span className="dm-api-hint">
                {settings?.databento_api_key_set
                  ? `${settings.databento_api_key_hint} (${settings.databento_api_key_source})`
                  : "Not configured"}
              </span>
            </div>
            <form
              className="dm-inline-form"
              onSubmit={(event) => {
                event.preventDefault();
                onSaveApiKey();
              }}
            >
              <input
                id="dm_settings_api_key"
                name="databento_api_key"
                type="password"
                value={apiKeyInput}
                onChange={(e) => setApiKeyInput(e.target.value)}
                placeholder="db-..."
                autoComplete="off"
                aria-describedby="dm_settings_api_key_hint"
              />
              <button
                type="submit"
                className="btn btn-secondary btn-sm"
                disabled={savingApiKey}
              >
                {savingApiKey ? "..." : "Save"}
              </button>
            </form>
            <div className="dm-field-hint" id="dm_settings_api_key_hint">
              Store a single active API key. Existing source information remains visible above.
            </div>
          </div>

          <form
            className="dm-settings-form"
            onSubmit={(event) => {
              event.preventDefault();
              onSaveRoots();
            }}
          >
            <div className="dm-settings-section">
              <label className="dm-settings-label" htmlFor="dm_settings_ohlcv_roots">
                OHLCV Data Roots
              </label>
              <textarea
                id="dm_settings_ohlcv_roots"
                name="ohlcv_data_dirs"
                className="dm-textarea"
                value={rootsForm.ohlcv_data_dirs}
                onChange={(e) =>
                  setRootsForm((prev) => ({ ...prev, ohlcv_data_dirs: e.target.value }))
                }
                rows={2}
                placeholder="One path per line"
              />
              <div className="dm-field-hint">One directory per line for bar-based market data.</div>
            </div>

            <div className="dm-settings-section">
              <label className="dm-settings-label" htmlFor="dm_settings_l2_roots">
                L2 Data Roots
              </label>
              <textarea
                id="dm_settings_l2_roots"
                name="l2_data_dirs"
                className="dm-textarea"
                value={rootsForm.l2_data_dirs}
                onChange={(e) =>
                  setRootsForm((prev) => ({ ...prev, l2_data_dirs: e.target.value }))
                }
                rows={2}
                placeholder="One path per line"
              />
              <div className="dm-field-hint">Use dedicated paths for depth files to keep scans fast.</div>
            </div>

            <div className="dm-btn-row">
              <button
                type="submit"
                className="btn btn-secondary"
                disabled={savingRoots}
              >
                {savingRoots ? "Saving..." : "Save Roots"}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
