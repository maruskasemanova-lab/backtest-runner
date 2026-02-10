import { useState, useEffect, useCallback } from "react";

const resolveRunnerUrl = (apiUrl) => {
  const base = (apiUrl || "").trim();
  if (base) {
    return base.includes("8001") ? base.replace("8001", "8002") : base;
  }
  return `http://${window.location.hostname}:8002`;
};

const safeObject = (value) => {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return {};
  }
  return value;
};

function AOSOptimizations({ apiUrl, selectedTicker, onOptimizationChange }) {
  const [aosConfig, setAosConfig] = useState({ tickers: {} });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [rawConfigText, setRawConfigText] = useState("");
  const [rawConfigError, setRawConfigError] = useState(null);
  const [rawConfigSaving, setRawConfigSaving] = useState(false);
  const [rawConfigDirty, setRawConfigDirty] = useState(false);

  const selectedTickerKey = (selectedTicker || "").toUpperCase();

  const fetchAOSConfig = useCallback(async () => {
    setLoading(true);
    setError(null);
    const runnerUrl = resolveRunnerUrl(apiUrl);

    try {
      const resp = await fetch(`${runnerUrl}/api/aos-config`);
      if (!resp.ok) {
        throw new Error(`HTTP ${resp.status}`);
      }
      const payload = await resp.json();
      const normalized = safeObject(payload);
      normalized.tickers = safeObject(normalized.tickers);
      setAosConfig(normalized);
    } catch (err) {
      console.log("AOS config API unavailable", err);
      setError("AOS config API is unavailable.");
      setAosConfig({ tickers: {} });
    } finally {
      setLoading(false);
    }
  }, [apiUrl]);

  useEffect(() => {
    fetchAOSConfig();
  }, [fetchAOSConfig]);

  useEffect(() => {
    if (!selectedTickerKey) {
      setRawConfigText("");
      setRawConfigError(null);
      setRawConfigDirty(false);
      return;
    }

    const tickerConfig = safeObject(aosConfig?.tickers?.[selectedTickerKey]);
    setRawConfigText(JSON.stringify(tickerConfig, null, 2));
    setRawConfigError(null);
    setRawConfigDirty(false);
  }, [selectedTickerKey, aosConfig]);

  const persistConfig = useCallback(async (tickerKey, configValue) => {
    if (!tickerKey) return;
    const runnerUrl = resolveRunnerUrl(apiUrl);

    const resp = await fetch(`${runnerUrl}/api/aos-config/update`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ticker: tickerKey,
        config: configValue,
      }),
    });

    if (!resp.ok) {
      throw new Error(`HTTP ${resp.status}`);
    }
  }, [apiUrl]);

  const applyRawConfig = async () => {
    if (!selectedTickerKey) return;

    let parsed;
    try {
      parsed = JSON.parse(rawConfigText || "{}");
    } catch (err) {
      setRawConfigError(`Invalid JSON: ${err.message}`);
      return;
    }

    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      setRawConfigError("Ticker config JSON must be an object.");
      return;
    }

    const nextConfig = safeObject(parsed);
    setRawConfigSaving(true);
    setRawConfigError(null);

    try {
      await persistConfig(selectedTickerKey, nextConfig);

      setAosConfig((prev) => ({
        ...safeObject(prev),
        tickers: {
          ...safeObject(prev?.tickers),
          [selectedTickerKey]: nextConfig,
        },
      }));

      setRawConfigText(JSON.stringify(nextConfig, null, 2));
      setRawConfigDirty(false);
      setError(null);

      if (onOptimizationChange) {
        onOptimizationChange(selectedTickerKey, nextConfig);
      }
    } catch (err) {
      console.log("Could not save AOS config to server", err);
      setError("Could not save AOS config to server. Changes are local only.");
    } finally {
      setRawConfigSaving(false);
    }
  };

  const resetRawConfig = () => {
    if (!selectedTickerKey) return;
    const tickerConfig = safeObject(aosConfig?.tickers?.[selectedTickerKey]);
    setRawConfigText(JSON.stringify(tickerConfig, null, 2));
    setRawConfigError(null);
    setRawConfigDirty(false);
  };

  const hasTickerConfig =
    !!selectedTickerKey && Object.prototype.hasOwnProperty.call(safeObject(aosConfig?.tickers), selectedTickerKey);

  if (!selectedTickerKey) {
    return (
      <div className="card">
        <div className="card-header">
          <span className="card-title">AOS Config</span>
        </div>
        <div className="card-body" style={{ color: "var(--text-muted)" }}>
          Select a ticker to edit AOS configuration from file.
        </div>
      </div>
    );
  }

  return (
    <div className="card">
      <div className="card-header">
        <span className="card-title">AOS Config - {selectedTickerKey}</span>
        <button className="btn btn-secondary" onClick={fetchAOSConfig} disabled={loading || rawConfigSaving}>
          Reload
        </button>
      </div>

      <div className="card-body" style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
        {loading && <div style={{ color: "var(--text-muted)" }}>Loading config...</div>}
        {error && <div style={{ color: "var(--accent-red)" }}>{error}</div>}

        <div
          style={{
            border: "1px solid var(--border-color)",
            borderRadius: "6px",
            padding: "12px",
            fontSize: "0.8rem",
            color: "var(--text-muted)",
          }}
        >
          Source of truth: <code>aos_optimization/aos_config.json</code> via <code>/api/aos-config</code>.
          Saved changes are applied on the next <code>/api/run/start</code>.
        </div>

        {!hasTickerConfig && (
          <div style={{ color: "var(--accent-yellow)", fontSize: "0.8rem" }}>
            No existing config for {selectedTickerKey} in file. Editing starts from an empty object.
          </div>
        )}

        <textarea
          value={rawConfigText}
          onChange={(e) => {
            setRawConfigText(e.target.value);
            setRawConfigDirty(true);
            setRawConfigError(null);
          }}
          style={{
            width: "100%",
            minHeight: "260px",
            fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
            fontSize: "0.75rem",
            padding: "8px",
            borderRadius: "4px",
            border: "1px solid var(--border-color)",
            backgroundColor: "var(--bg-primary)",
            color: "var(--text-primary)",
          }}
        />

        {rawConfigError && (
          <div style={{ color: "var(--accent-red)", fontSize: "0.8rem" }}>
            {rawConfigError}
          </div>
        )}

        <div style={{ display: "flex", gap: "8px" }}>
          <button
            className="btn btn-primary"
            onClick={applyRawConfig}
            disabled={rawConfigSaving || !rawConfigDirty}
          >
            {rawConfigSaving ? "Saving..." : "Apply JSON"}
          </button>
          <button
            className="btn btn-secondary"
            onClick={resetRawConfig}
            disabled={rawConfigSaving}
          >
            Reset
          </button>
        </div>
      </div>
    </div>
  );
}

export default AOSOptimizations;
