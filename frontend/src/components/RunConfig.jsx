import { useState, useEffect } from "react";

const MU_FLOW_PRESET = {
  // Keep FE defaults aligned with AOS tuning:
  // zeros/nulls below intentionally defer to AOS values in backend.
  regime_detection_minutes: 15,
  trailing_stop_pct: null,
  account_size_usd: 10000,
  l2_only: false,
  l2_confirm_enabled: true,
  l2_min_delta: 0,
  l2_min_imbalance: 0.0,
  l2_min_iceberg_bias: 0.0,
  l2_lookback_bars: 3,
  l2_min_participation_ratio: 0.0,
  l2_min_directional_consistency: 0.0,
  l2_min_signed_aggression: 0.0,
};

function RunConfig({ onStart, isRunning, onTickerChange }) {
  const [availableData, setAvailableData] = useState(null);
  const [config, setConfig] = useState({
    run_id: `backtest-${Date.now()}`,
    ticker: "",
    date: "",
    date_from: "",
    date_to: "",
    data_file: null,
    strategy_api_url: `http://${window.location.hostname}:8001`,
    ...MU_FLOW_PRESET,
    checkpoint_path: null,
    auto_save_checkpoint: true,
  });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [useWarmStart, setUseWarmStart] = useState(false);
  const [checkpointCatalog, setCheckpointCatalog] = useState([]);
  const [checkpointLoading, setCheckpointLoading] = useState(false);
  const [checkpointSaving, setCheckpointSaving] = useState(false);
  const [checkpointMessage, setCheckpointMessage] = useState(null);

  const strategyApiBase = (config.strategy_api_url || "").replace(/\/+$/, "");

  const formatCheckpointLabel = (item) => {
    const path = item?.path || "";
    const file = path.split(/[\\/]/).pop() || path || "(unknown)";
    const created = item?.created_at ? new Date(item.created_at).toLocaleString() : "unknown time";
    const trades = Number(item?.source?.total_trades || 0);
    const wr = item?.source?.win_rate;
    const wrText = typeof wr === "number" ? `${(wr * 100).toFixed(1)}%` : "n/a";
    return `${file} | ${trades} trades | WR ${wrText} | ${created}`;
  };

  const fetchCheckpoints = async (preferredPath = null) => {
    if (!strategyApiBase) {
      return;
    }

    setCheckpointLoading(true);
    setCheckpointMessage(null);
    try {
      const resp = await fetch(`${strategyApiBase}/api/orchestrator/checkpoints`);
      if (!resp.ok) {
        throw new Error(`HTTP ${resp.status}`);
      }

      const payload = await resp.json();
      const catalog = Array.isArray(payload) ? payload : [];
      setCheckpointCatalog(catalog);

      if (preferredPath) {
        setConfig((prev) => ({ ...prev, checkpoint_path: preferredPath }));
      } else if (useWarmStart && !config.checkpoint_path && catalog.length > 0) {
        setConfig((prev) => ({ ...prev, checkpoint_path: catalog[0].path || null }));
      }
    } catch (err) {
      console.error("Checkpoint catalog load failed:", err);
      setCheckpointMessage("Checkpoint API is not reachable right now.");
    } finally {
      setCheckpointLoading(false);
    }
  };

  const handleSaveCheckpointNow = async () => {
    if (!strategyApiBase) {
      setCheckpointMessage("Strategy API URL is missing.");
      return;
    }

    setCheckpointSaving(true);
    setCheckpointMessage(null);
    try {
      const params = new URLSearchParams();
      if (config.run_id) params.set("run_id", config.run_id);
      if (config.ticker) params.set("ticker", config.ticker);
      if (config.date_from) params.set("date_from", config.date_from);
      if (config.date_to) params.set("date_to", config.date_to);
      const query = params.toString();
      const saveUrl = `${strategyApiBase}/api/orchestrator/checkpoint/save${query ? `?${query}` : ""}`;

      const resp = await fetch(saveUrl, { method: "POST" });
      if (!resp.ok) {
        throw new Error(`HTTP ${resp.status}`);
      }

      const payload = await resp.json();
      const savedPath = payload?.path || null;
      if (savedPath) {
        setUseWarmStart(true);
        setConfig((prev) => ({ ...prev, checkpoint_path: savedPath }));
        await fetchCheckpoints(savedPath);
      }
      setCheckpointMessage(savedPath ? `Checkpoint saved: ${savedPath}` : "Checkpoint saved.");
    } catch (err) {
      console.error("Checkpoint save failed:", err);
      setCheckpointMessage("Checkpoint save failed.");
    } finally {
      setCheckpointSaving(false);
    }
  };

  const applyMuPreset = (date = "2026-02-03") => {
    setConfig((prev) => ({
      ...prev,
      ticker: "MU",
      date,
      date_from: date,
      date_to: date,
      ...MU_FLOW_PRESET,
    }));
    if (onTickerChange) {
      onTickerChange("MU");
    }
  };

  useEffect(() => {
    const fetchAvailableData = async () => {
      try {
        const resp = await fetch("/api/available-data");
        if (!resp.ok) {
          return;
        }

        const data = await resp.json();
        setAvailableData(data);

        if (!data.tickers || data.tickers.length === 0) {
          return;
        }

        const targetTicker = data.tickers.includes("MU") ? "MU" : data.tickers[0];
        const range = data.date_ranges[targetTicker];
        const defaultDate = targetTicker === "MU"
          ? "2026-02-03"
          : range?.end || new Date().toISOString().split("T")[0];

        setConfig((prev) => ({
          ...prev,
          ticker: targetTicker,
          date: defaultDate,
          date_from: defaultDate,
          date_to: defaultDate,
          ...(targetTicker === "MU" ? MU_FLOW_PRESET : {}),
        }));

        if (onTickerChange) {
          onTickerChange(targetTicker);
        }
      } catch (err) {
        console.error("Failed to fetch available data:", err);
      }
    };

    fetchAvailableData();
  }, [onTickerChange]);

  useEffect(() => {
    fetchCheckpoints();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [strategyApiBase]);

  const getDateRange = () => {
    if (!availableData || !config.ticker) {
      return { min: null, max: null };
    }
    const range = availableData.date_ranges[config.ticker];
    return {
      min: range?.start || null,
      max: range?.end || null,
    };
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const payload = {
        ...config,
        checkpoint_path: useWarmStart ? (config.checkpoint_path || "").trim() || null : null,
        auto_save_checkpoint: !!config.auto_save_checkpoint,
      };
      if (useWarmStart && !payload.checkpoint_path) {
        throw new Error("Warm start is enabled, but no checkpoint is selected.");
      }
      await onStart(payload);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (field, value) => {
    setConfig((prev) => ({ ...prev, [field]: value }));
  };

  const handleDateFromChange = (value) => {
    setConfig((prev) => {
      const nextTo = prev.date_to && value > prev.date_to ? value : prev.date_to;
      return {
        ...prev,
        date_from: value,
        date: value,
        date_to: nextTo,
      };
    });
  };

  const handleDateToChange = (value) => {
    setConfig((prev) => {
      const nextFrom = prev.date_from && value < prev.date_from ? value : prev.date_from;
      return {
        ...prev,
        date_to: value,
        date: nextFrom || prev.date,
        date_from: nextFrom,
      };
    });
  };

  const handleTickerChange = (ticker) => {
    const range = availableData?.date_ranges[ticker];
    const defaultDate = ticker === "MU" ? "2026-02-03" : range?.end;

    setConfig((prev) => ({
      ...prev,
      ticker,
      date: defaultDate || prev.date,
      date_from: defaultDate || range?.start || prev.date_from,
      date_to: defaultDate || range?.end || prev.date_to,
      ...(ticker === "MU" ? MU_FLOW_PRESET : {}),
    }));

    if (onTickerChange) {
      onTickerChange(ticker);
    }
  };

  const dateRange = getDateRange();

  if (isRunning) {
    return (
      <div className="card">
        <div className="card-header">
          <span className="card-title">Run Info</span>
        </div>
        <div className="card-body">
          <div className="form-group">
            <label>Run ID</label>
            <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>{config.run_id}</div>
          </div>
          <div className="form-group">
            <label>Ticker</label>
            <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>{config.ticker}</div>
          </div>
          <div className="form-group">
            <label>Date Range</label>
            <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
              {config.date_from && config.date_to
                ? `${config.date_from} → ${config.date_to}`
                : config.date}
            </div>
          </div>
          <div className="form-group">
            <label>Account Size</label>
            <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
              ${Number(config.account_size_usd || 0).toLocaleString()}
            </div>
          </div>
          <div className="form-group">
            <label>L2 Confirmation</label>
            <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
              {config.l2_confirm_enabled ? "Enabled" : "Disabled"}
            </div>
          </div>
          <div className="form-group">
            <label>Start Mode</label>
            <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
              {useWarmStart ? "Warm Start" : "Cold Start"}
            </div>
          </div>
          <div className="form-group">
            <label>Checkpoint Auto-save</label>
            <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
              {config.auto_save_checkpoint ? "Enabled" : "Disabled"}
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="card">
      <div className="card-header">
        <span className="card-title">New Backtest Run</span>
      </div>
      <div className="card-body">
        <form className="run-config-form" onSubmit={handleSubmit}>
          <div className="preset-box">
            <div className="preset-header">
              <span className="preset-title">MU Flow Preset</span>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => applyMuPreset()}
                style={{ padding: "6px 10px", fontSize: "0.78rem" }}
              >
                Apply
              </button>
            </div>
            <div className="preset-copy">
              Strategies: momentum_flow, absorption_reversal, exhaustion_fade. L2 confirm + depth thresholds are prefilled.
            </div>
          </div>

          <div className="form-group">
            <label htmlFor="run_id">Run ID</label>
            <input
              id="run_id"
              type="text"
              value={config.run_id}
              onChange={(e) => handleChange("run_id", e.target.value)}
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="ticker">
              Ticker
              <div className="inline-toggle">
                <span>L2 Only</span>
                <input
                  type="checkbox"
                  checked={config.l2_only || false}
                  onChange={(e) => {
                    const checked = e.target.checked;
                    if (checked && availableData?.l2_tickers) {
                      const isCurrentTickerL2 = availableData.l2_tickers.includes(config.ticker);
                      if (!isCurrentTickerL2 && availableData.l2_tickers.length > 0) {
                        handleTickerChange(availableData.l2_tickers[0]);
                      }
                    }
                    handleChange("l2_only", checked);
                  }}
                />
              </div>
            </label>
            {availableData?.tickers ? (
              <select
                id="ticker"
                value={config.ticker}
                onChange={(e) => handleTickerChange(e.target.value)}
                required
              >
                {availableData.tickers
                  .filter((t) => !config.l2_only || availableData.l2_tickers?.includes(t))
                  .map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
              </select>
            ) : (
              <input
                id="ticker"
                type="text"
                value={config.ticker}
                onChange={(e) => handleChange("ticker", e.target.value.toUpperCase())}
                placeholder="Loading..."
                required
              />
            )}
          </div>

          <div className="form-group">
            <label htmlFor="date_from">
              Date From
              {dateRange.min && dateRange.max && (
                <span style={{ color: "var(--text-muted)", fontWeight: "normal", fontSize: "0.75rem" }}>
                  {` (${dateRange.min} to ${dateRange.max})`}
                </span>
              )}
            </label>
            <input
              id="date_from"
              type="date"
              value={config.date_from}
              min={dateRange.min || undefined}
              max={dateRange.max || undefined}
              onChange={(e) => handleDateFromChange(e.target.value)}
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="date_to">Date To</label>
            <input
              id="date_to"
              type="date"
              value={config.date_to}
              min={dateRange.min || undefined}
              max={dateRange.max || undefined}
              onChange={(e) => handleDateToChange(e.target.value)}
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="regime_minutes">Regime Detection (min)</label>
            <input
              id="regime_minutes"
              type="number"
              min="5"
              value={config.regime_detection_minutes}
              onChange={(e) => handleChange("regime_detection_minutes", Number(e.target.value))}
            />
          </div>

          <div className="form-group">
            <label htmlFor="account_size_usd">Account Size (USD)</label>
            <input
              id="account_size_usd"
              type="number"
              min="100"
              step="100"
              value={config.account_size_usd}
              onChange={(e) => handleChange("account_size_usd", Number(e.target.value))}
            />
          </div>

          <div className="form-group">
            <label htmlFor="trailing_stop_pct">Global Trailing Stop (%)</label>
            <input
              id="trailing_stop_pct"
              type="number"
              min="0.1"
              max="5"
              step="0.1"
              value={config.trailing_stop_pct ?? ""}
              onChange={(e) =>
                handleChange(
                  "trailing_stop_pct",
                  e.target.value === "" ? null : Number(e.target.value)
                )
              }
            />
          </div>

          <div className="preset-box">
            <div className="preset-header">
              <span className="preset-title">Warm Start Checkpoints</span>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => fetchCheckpoints()}
                disabled={checkpointLoading}
                style={{ padding: "6px 10px", fontSize: "0.78rem" }}
              >
                {checkpointLoading ? "Refreshing..." : "Refresh"}
              </button>
            </div>
            <div className="preset-copy">
              Choose how each run should initialize learning state.
            </div>

            <div className="form-group" style={{ marginBottom: "var(--spacing-sm)" }}>
              <label style={{ marginBottom: "8px" }}>Start Mode</label>
              <div style={{ display: "grid", gap: "8px" }}>
                <label className="field-row">
                  <span>Cold Start (reset learning state)</span>
                  <input
                    type="radio"
                    name="start_mode"
                    checked={!useWarmStart}
                    onChange={() => setUseWarmStart(false)}
                  />
                </label>
                <label className="field-row">
                  <span>Warm Start (load checkpoint)</span>
                  <input
                    type="radio"
                    name="start_mode"
                    checked={useWarmStart}
                    onChange={() => {
                      setUseWarmStart(true);
                      if (!config.checkpoint_path && checkpointCatalog.length > 0) {
                        handleChange("checkpoint_path", checkpointCatalog[0].path || null);
                      }
                    }}
                  />
                </label>
              </div>
            </div>

            <label className="field-row">
              <span>Auto-save Checkpoint After Run</span>
              <input
                type="checkbox"
                checked={!!config.auto_save_checkpoint}
                onChange={(e) => handleChange("auto_save_checkpoint", e.target.checked)}
              />
            </label>

            {useWarmStart && (
              <div className="form-group">
                <label htmlFor="checkpoint_path">Checkpoint</label>
                <select
                  id="checkpoint_path"
                  value={config.checkpoint_path || ""}
                  onChange={(e) => handleChange("checkpoint_path", e.target.value || null)}
                >
                  <option value="">Select checkpoint...</option>
                  {checkpointCatalog.map((cp) => (
                    <option key={cp.path} value={cp.path}>
                      {formatCheckpointLabel(cp)}
                    </option>
                  ))}
                </select>
              </div>
            )}

            {useWarmStart && (
              <div className="form-group">
                <label htmlFor="checkpoint_path_custom">Custom Checkpoint Path</label>
                <input
                  id="checkpoint_path_custom"
                  type="text"
                  value={config.checkpoint_path || ""}
                  onChange={(e) => handleChange("checkpoint_path", e.target.value || null)}
                  placeholder="data/checkpoints/checkpoint_YYYYMMDD_HHMMSS.json"
                />
              </div>
            )}

            <button
              type="button"
              className="btn btn-secondary"
              onClick={handleSaveCheckpointNow}
              disabled={checkpointSaving}
              style={{ width: "100%" }}
            >
              {checkpointSaving ? "Saving checkpoint..." : "Save Checkpoint Now"}
            </button>

            {checkpointMessage && (
              <div
                style={{
                  fontSize: "0.8rem",
                  color: "var(--text-secondary)",
                  lineHeight: 1.4,
                }}
              >
                {checkpointMessage}
              </div>
            )}
          </div>

          <div className="form-group">
            <label className="field-row" htmlFor="l2_confirm_enabled">
              <span>L2 Confirmation Gate</span>
              <input
                id="l2_confirm_enabled"
                type="checkbox"
                checked={config.l2_confirm_enabled || false}
                onChange={(e) => handleChange("l2_confirm_enabled", e.target.checked)}
              />
            </label>
          </div>

          {config.l2_confirm_enabled && (
            <>
              <div className="form-group">
                <label htmlFor="l2_min_delta">L2 Min Delta</label>
                <input
                  id="l2_min_delta"
                  type="number"
                  step="100"
                  value={config.l2_min_delta}
                  onChange={(e) => handleChange("l2_min_delta", Number(e.target.value))}
                />
              </div>
              <div className="form-group">
                <label htmlFor="l2_min_imbalance">L2 Min Imbalance</label>
                <input
                  id="l2_min_imbalance"
                  type="number"
                  step="0.01"
                  value={config.l2_min_imbalance}
                  onChange={(e) => handleChange("l2_min_imbalance", Number(e.target.value))}
                />
              </div>
              <div className="form-group">
                <label htmlFor="l2_min_signed_aggression">L2 Min Signed Aggression</label>
                <input
                  id="l2_min_signed_aggression"
                  type="number"
                  step="0.01"
                  value={config.l2_min_signed_aggression}
                  onChange={(e) => handleChange("l2_min_signed_aggression", Number(e.target.value))}
                />
              </div>
              <div className="form-group">
                <label htmlFor="l2_min_directional_consistency">L2 Min Directional Consistency</label>
                <input
                  id="l2_min_directional_consistency"
                  type="number"
                  step="0.01"
                  value={config.l2_min_directional_consistency}
                  onChange={(e) =>
                    handleChange("l2_min_directional_consistency", Number(e.target.value))
                  }
                />
              </div>
              <div className="form-group">
                <label htmlFor="l2_min_participation_ratio">L2 Min Participation Ratio</label>
                <input
                  id="l2_min_participation_ratio"
                  type="number"
                  step="0.01"
                  value={config.l2_min_participation_ratio}
                  onChange={(e) =>
                    handleChange("l2_min_participation_ratio", Number(e.target.value))
                  }
                />
              </div>
              <div className="form-group">
                <label htmlFor="l2_min_iceberg_bias">L2 Min Iceberg Bias</label>
                <input
                  id="l2_min_iceberg_bias"
                  type="number"
                  step="0.01"
                  value={config.l2_min_iceberg_bias}
                  onChange={(e) => handleChange("l2_min_iceberg_bias", Number(e.target.value))}
                />
              </div>
              <div className="form-group">
                <label htmlFor="l2_lookback_bars">L2 Lookback Bars</label>
                <input
                  id="l2_lookback_bars"
                  type="number"
                  min="1"
                  step="1"
                  value={config.l2_lookback_bars}
                  onChange={(e) => handleChange("l2_lookback_bars", Number(e.target.value))}
                />
              </div>
            </>
          )}

          {error && (
            <div
              style={{
                color: "var(--accent-red)",
                fontSize: "0.85rem",
                padding: "var(--spacing-sm)",
                background: "rgba(239, 68, 68, 0.1)",
                borderRadius: "var(--border-radius-sm)",
              }}
            >
              {error}
            </div>
          )}

          <button
            type="submit"
            className="btn btn-primary"
            disabled={loading || !config.ticker || !config.date_from || !config.date_to}
            style={{ width: "100%", marginTop: "var(--spacing-sm)" }}
          >
            {loading ? "Starting..." : "Start Backtest"}
          </button>
        </form>
      </div>
    </div>
  );
}

export default RunConfig;
