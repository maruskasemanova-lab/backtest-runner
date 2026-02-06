import { useState, useEffect } from "react";

function RunConfig({ onStart, isRunning, onTickerChange }) {
  const [availableData, setAvailableData] = useState(null);
  const [config, setConfig] = useState({
    run_id: `backtest-${Date.now()}`,
    ticker: "",
    date: "",
    date_from: "",
    date_to: "",
    data_file: null, // Auto-discovered from available data
    strategy_api_url: `http://${window.location.hostname}:8001`,
    regime_detection_minutes: 15,
    trailing_stop_pct: 0.3,
    account_size_usd: 10000,
    l2_only: true, // User requested L2 default
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
            // Default to MU if available, otherwise first ticker
            const targetTicker = data.tickers.includes("MU") ? "MU" : data.tickers[0];
            const range = data.date_ranges[targetTicker];
            
            // Default date to 2026-02-03 if available for MU, otherwise range end
            let defaultDate = range?.end || new Date().toISOString().split("T")[0];
            if (targetTicker === "MU") {
                defaultDate = "2026-02-03";
            }
            
            setConfig((prev) => ({
              ...prev,
              ticker: targetTicker,
              date: defaultDate,
              date_from: defaultDate,
              date_to: defaultDate,
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
    // Update date to last available date for this ticker
    const range = availableData?.date_ranges[ticker];
    setConfig((prev) => ({
      ...prev,
      ticker,
      date: range?.end || prev.date,
      date_from: range?.start || prev.date_from,
      date_to: range?.end || prev.date_to,
    }));
    // Notify parent about ticker change for strategy preset application
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
            <label>Global Trailing Stop</label>
            <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
              {config.trailing_stop_pct != null ? `${config.trailing_stop_pct}%` : "Default"}
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
            <label htmlFor="ticker">
                Ticker
                <div style={{ float: "right", display: "flex", alignItems: "center", gap: "6px" }}>
                    <span style={{ fontSize: "0.75rem", fontWeight: "normal", color: "var(--text-muted)" }}>L2 Only</span>
                    <input 
                        type="checkbox" 
                        checked={config.l2_only || false}
                        onChange={(e) => {
                            const checked = e.target.checked;
                            
                            // If enabling L2 only, check if current ticker is valid
                            if (checked && availableData?.l2_tickers) {
                                const isCurrentTickerL2 = availableData.l2_tickers.includes(config.ticker);
                                if (!isCurrentTickerL2 && availableData.l2_tickers.length > 0) {
                                    // Switch to first available L2 ticker
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
                    .filter(t => !config.l2_only || availableData.l2_tickers?.includes(t)) // Assuming availableData has l2_tickers
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
                onChange={(e) =>
                  handleChange("ticker", e.target.value.toUpperCase())
                }
                placeholder="Loading..."
                required
              />
            )}
          </div>

          <div className="form-group">
            <label htmlFor="date_from">
              Date From
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
              onChange={(e) =>
                handleChange("regime_detection_minutes", Number(e.target.value))
              }
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
              onChange={(e) =>
                handleChange("account_size_usd", Number(e.target.value))
              }
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
                handleChange("trailing_stop_pct", Number(e.target.value))
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
            disabled={loading || !config.ticker || !config.date_from || !config.date_to}
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
