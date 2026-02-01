import { useState, useEffect } from "react";

function RunConfig({ onStart, isRunning }) {
  const [availableData, setAvailableData] = useState(null);
  const [config, setConfig] = useState({
    run_id: `backtest-${Date.now()}`,
    ticker: "",
    date: "",
    data_file: null, // Auto-discovered from available data
    strategy_api_url: "http://localhost:8001",
    regime_detection_minutes: 15,
  });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Fetch available data on mount
  useEffect(() => {
    const fetchAvailableData = async () => {
      try {
        const resp = await fetch("/api/available-data");
        if (resp.ok) {
          const data = await resp.json();
          setAvailableData(data);

          // Set default ticker and date if available
          if (data.tickers && data.tickers.length > 0) {
            const defaultTicker = data.tickers[0];
            const range = data.date_ranges[defaultTicker];
            setConfig((prev) => ({
              ...prev,
              ticker: defaultTicker,
              date: range?.end || new Date().toISOString().split("T")[0],
            }));
          }
        }
      } catch (err) {
        console.error("Failed to fetch available data:", err);
      }
    };

    fetchAvailableData();
  }, []);

  // Get date range for current ticker
  const getDateRange = () => {
    if (!availableData || !config.ticker) return { min: null, max: null };
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
      await onStart(config);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (field, value) => {
    setConfig((prev) => ({ ...prev, [field]: value }));
  };

  const handleTickerChange = (ticker) => {
    // Update date to last available date for this ticker
    const range = availableData?.date_ranges[ticker];
    setConfig((prev) => ({
      ...prev,
      ticker,
      date: range?.end || prev.date,
    }));
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
            <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
              {config.run_id}
            </div>
          </div>
          <div className="form-group">
            <label>Ticker</label>
            <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
              {config.ticker}
            </div>
          </div>
          <div className="form-group">
            <label>Date</label>
            <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
              {config.date}
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
            <label htmlFor="ticker">Ticker</label>
            {availableData?.tickers ? (
              <select
                id="ticker"
                value={config.ticker}
                onChange={(e) => handleTickerChange(e.target.value)}
                required
              >
                {availableData.tickers.map((t) => (
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
                onChange={(e) =>
                  handleChange("ticker", e.target.value.toUpperCase())
                }
                placeholder="Loading..."
                required
              />
            )}
          </div>

          <div className="form-group">
            <label htmlFor="date">
              Date
              {dateRange.min && dateRange.max && (
                <span
                  style={{
                    color: "var(--text-muted)",
                    fontWeight: "normal",
                    fontSize: "0.75rem",
                  }}
                >
                  {" "}
                  ({dateRange.min} to {dateRange.max})
                </span>
              )}
            </label>
            <input
              id="date"
              type="date"
              value={config.date}
              min={dateRange.min || undefined}
              max={dateRange.max || undefined}
              onChange={(e) => handleChange("date", e.target.value)}
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="regime_minutes">Regime Detection (min)</label>
            <input
              id="regime_minutes"
              type="number"
              min="5"
              max="60"
              value={config.regime_detection_minutes}
              onChange={(e) =>
                handleChange("regime_detection_minutes", Number(e.target.value))
              }
            />
          </div>

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
            disabled={loading || !config.ticker || !config.date}
            style={{ width: "100%", marginTop: "var(--spacing-sm)" }}
          >
            {loading ? "⏳ Starting..." : "🚀 Start Backtest"}
          </button>
        </form>
      </div>
    </div>
  );
}

export default RunConfig;
