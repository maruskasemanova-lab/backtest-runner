import { useState, useEffect, useCallback } from "react";

/**
 * AOS Optimization Panel
 * 
 * Displays and controls the AOS optimizations:
 * - Time-based filtering (15:00 only vs all hours)
 * - Long-only mode for NVDA
 * - Trailing stop width
 * - Expected improvements based on backtests
 */
function AOSOptimizations({ apiUrl, selectedTicker, onOptimizationChange }) {
  const [aosConfig, setAosConfig] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [localConfig, setLocalConfig] = useState({});
  const [simulatedResults, setSimulatedResults] = useState(null);

  const resolvedUrl = apiUrl || `http://${window.location.hostname}:8002`;

  // Default optimized values from backtest analysis
  const optimizedDefaults = {
    NVDA: {
      time_filter_enabled: true,
      trading_hours: [15],
      long_only: true,
      trailing_stop_pct: 2.0,
      expected_improvement: "+$253.91",
      original_pnl: "-$78.87",
      optimized_pnl: "+$175.04",
      win_rate: "81.8%"
    },
    TSLA: {
      time_filter_enabled: true,
      trading_hours: [15],
      long_only: false, // TSLA may work differently
      trailing_stop_pct: 2.0,
      expected_improvement: "TBD",
      original_pnl: "N/A",
      optimized_pnl: "N/A",
      win_rate: "N/A"
    },
    AAPL: {
      time_filter_enabled: true,
      trading_hours: [15, 16],
      long_only: false,
      trailing_stop_pct: 1.0,
      expected_improvement: "TBD",
      original_pnl: "N/A",
      optimized_pnl: "N/A",
      win_rate: "N/A"
    }
  };

  const fetchAOSConfig = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // AOS Config is served by the runner API (port 8002), not the strategy API (8001)
      // If apiUrl is passed as 8001, we need to override it here or use relative path if proxied.
      // Assuming we are running locally, hardcode 8002 fallback or derive.
      const runnerUrl = apiUrl && apiUrl.includes("8001") ? apiUrl.replace("8001", "8002") : "http://localhost:8002";
      const resp = await fetch(`${runnerUrl}/api/aos-config`);
      if (resp.ok) {
        const data = await resp.json();
        setAosConfig(data);
        // Initialize local config with server values
        if (selectedTicker && data.tickers?.[selectedTicker]) {
          setLocalConfig(data.tickers[selectedTicker]);
        }
      } else {
        // Create default config if not found
        setAosConfig({ tickers: optimizedDefaults });
        if (selectedTicker && optimizedDefaults[selectedTicker]) {
          setLocalConfig(optimizedDefaults[selectedTicker]);
        }
      }
    } catch (err) {
      console.log("AOS config not available, using defaults");
      setAosConfig({ tickers: optimizedDefaults });
      if (selectedTicker && optimizedDefaults[selectedTicker]) {
        setLocalConfig(optimizedDefaults[selectedTicker]);
      }
    } finally {
      setLoading(false);
    }
  }, [resolvedUrl, selectedTicker]);

  useEffect(() => {
    fetchAOSConfig();
  }, [fetchAOSConfig]);

  // Update local config when ticker changes
  useEffect(() => {
    if (selectedTicker) {
      const tickerConfig = aosConfig?.tickers?.[selectedTicker] || optimizedDefaults[selectedTicker] || {};
      setLocalConfig(tickerConfig);
    }
  }, [selectedTicker, aosConfig]);

  const updateConfig = async (field, value) => {
    const newConfig = { ...localConfig, [field]: value };
    setLocalConfig(newConfig);

    // Simulate expected results
    simulateResults(newConfig);

    // Notify parent component
    if (onOptimizationChange) {
      onOptimizationChange(selectedTicker, newConfig);
    }

    // Try to save to server
    try {
      const runnerUrl = resolvedUrl && resolvedUrl.includes("8001") ? resolvedUrl.replace("8001", "8002") : "http://localhost:8002";
      await fetch(`${runnerUrl}/api/aos-config/update`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ticker: selectedTicker,
          config: newConfig
        })
      });
    } catch (err) {
      console.log("Could not save to server, using local only");
    }
  };

  const simulateResults = (config) => {
    // Based on actual backtest data for NVDA
    if (selectedTicker === "NVDA") {
      let expectedPnl = -78.87; // Original

      if (config.time_filter_enabled) {
        expectedPnl += 212.29; // Time filter improvement
      }
      if (config.long_only) {
        expectedPnl += 41.64; // Long-only additional improvement
      }

      setSimulatedResults({
        expected_pnl: expectedPnl.toFixed(2),
        trades_reduction: config.time_filter_enabled ? "25 trades saved" : "0",
        win_rate: config.long_only && config.time_filter_enabled ? "81.8%" : 
                  config.time_filter_enabled ? "50%" : "50%"
      });
    }
  };

  const applyOptimizedDefaults = () => {
    if (selectedTicker && optimizedDefaults[selectedTicker]) {
      const optimized = optimizedDefaults[selectedTicker];
      setLocalConfig(optimized);
      simulateResults(optimized);
      if (onOptimizationChange) {
        onOptimizationChange(selectedTicker, optimized);
      }
    }
  };

  const trading_hours_options = [
    { value: [9, 10], label: "Morning (9:00-10:59)" },
    { value: [11, 12], label: "Late Morning (11:00-12:59)" },
    { value: [13, 14], label: "Early Afternoon (13:00-14:59)" },
    { value: [15], label: "Late Afternoon (15:00-15:59) ⭐ Best" },
    { value: [15, 16], label: "Power Hour (15:00-16:59)" }
  ];

  if (!selectedTicker) {
    return (
      <div className="card">
        <div className="card-header">
          <span className="card-title">🤖 AOS Optimizations</span>
        </div>
        <div className="card-body" style={{ color: "var(--text-muted)" }}>
          Select a ticker to configure AOS optimizations
        </div>
      </div>
    );
  }

  return (
    <div className="card">
      <div className="card-header">
        <span className="card-title">🤖 AOS Optimizations - {selectedTicker}</span>
        <button className="btn btn-primary" onClick={applyOptimizedDefaults}>
          Apply Optimized ✨
        </button>
      </div>
      <div className="card-body" style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
        {loading && <div style={{ color: "var(--text-muted)" }}>Loading...</div>}
        {error && <div style={{ color: "var(--accent-red)" }}>{error}</div>}

        {/* Expected Results Banner */}
        {optimizedDefaults[selectedTicker] && (
          <div style={{
            background: "linear-gradient(135deg, rgba(34, 197, 94, 0.1), rgba(16, 185, 129, 0.1))",
            border: "1px solid rgba(34, 197, 94, 0.3)",
            borderRadius: "8px",
            padding: "12px",
            marginBottom: "8px"
          }}>
            <div style={{ fontWeight: 600, color: "var(--accent-green)", marginBottom: "8px" }}>
              📊 Backtest Results for {selectedTicker}
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "8px", fontSize: "0.85rem" }}>
              <div>
                <div style={{ color: "var(--text-muted)" }}>Original</div>
                <div style={{ color: "var(--accent-red)", fontWeight: 600 }}>
                  {optimizedDefaults[selectedTicker].original_pnl}
                </div>
              </div>
              <div>
                <div style={{ color: "var(--text-muted)" }}>Optimized</div>
                <div style={{ color: "var(--accent-green)", fontWeight: 600 }}>
                  {optimizedDefaults[selectedTicker].optimized_pnl}
                </div>
              </div>
              <div>
                <div style={{ color: "var(--text-muted)" }}>Win Rate</div>
                <div style={{ color: "var(--accent-green)", fontWeight: 600 }}>
                  {optimizedDefaults[selectedTicker].win_rate}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Time Filter */}
        <div style={{
          border: "1px solid var(--border-color)",
          borderRadius: "6px",
          padding: "12px"
        }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "8px" }}>
            <span style={{ fontWeight: 600 }}>⏰ Time Filter</span>
            <label className="switch">
              <input
                type="checkbox"
                checked={localConfig.time_filter_enabled || false}
                onChange={(e) => updateConfig("time_filter_enabled", e.target.checked)}
              />
              <span className="slider" />
            </label>
          </div>
          <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginBottom: "8px" }}>
            14:00 loses $158/day, 15:00 earns $133/day
          </div>
          {localConfig.time_filter_enabled && (
            <select
              value={JSON.stringify(localConfig.trading_hours || [15])}
              onChange={(e) => updateConfig("trading_hours", JSON.parse(e.target.value))}
              style={{ width: "100%", padding: "6px", borderRadius: "4px" }}
            >
              {trading_hours_options.map((opt) => (
                <option key={opt.label} value={JSON.stringify(opt.value)}>
                  {opt.label}
                </option>
              ))}
            </select>
          )}
        </div>

        {/* Long Only Mode */}
        <div style={{
          border: "1px solid var(--border-color)",
          borderRadius: "6px",
          padding: "12px"
        }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "8px" }}>
            <span style={{ fontWeight: 600 }}>📈 Long Only Mode</span>
            <label className="switch">
              <input
                type="checkbox"
                checked={localConfig.long_only || false}
                onChange={(e) => updateConfig("long_only", e.target.checked)}
              />
              <span className="slider" />
            </label>
          </div>
          <div style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
            Shorts lose $233 with 20% win rate. Longs profit $154 with 68.8% win rate.
          </div>
        </div>

        {/* Trailing Stop */}
        <div style={{
          border: "1px solid var(--border-color)",
          borderRadius: "6px",
          padding: "12px"
        }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "8px" }}>
            <span style={{ fontWeight: 600 }}>📏 Trailing Stop %</span>
            <input
              type="number"
              step="0.1"
              min="0.5"
              max="5.0"
              value={localConfig.trailing_stop_pct || 1.0}
              onChange={(e) => updateConfig("trailing_stop_pct", parseFloat(e.target.value))}
              style={{ width: "80px", padding: "4px", textAlign: "right" }}
            />
          </div>
          <div style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
            Wider stops (2.0%+) let winners run. Default 0.6% exits too early.
          </div>
          <input
            type="range"
            min="0.5"
            max="3.0"
            step="0.1"
            value={localConfig.trailing_stop_pct || 1.0}
            onChange={(e) => updateConfig("trailing_stop_pct", parseFloat(e.target.value))}
            style={{ width: "100%", marginTop: "8px" }}
          />
        </div>

        {/* Simulated Results */}
        {simulatedResults && (
          <div style={{
            background: "rgba(99, 102, 241, 0.1)",
            border: "1px solid rgba(99, 102, 241, 0.3)",
            borderRadius: "8px",
            padding: "12px"
          }}>
            <div style={{ fontWeight: 600, color: "var(--accent-purple)", marginBottom: "8px" }}>
              🔮 Simulated Results
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "8px", fontSize: "0.85rem" }}>
              <div>
                <div style={{ color: "var(--text-muted)" }}>Expected PnL</div>
                <div style={{ 
                  color: parseFloat(simulatedResults.expected_pnl) >= 0 ? "var(--accent-green)" : "var(--accent-red)",
                  fontWeight: 600 
                }}>
                  ${simulatedResults.expected_pnl}
                </div>
              </div>
              <div>
                <div style={{ color: "var(--text-muted)" }}>Trades Saved</div>
                <div style={{ fontWeight: 600 }}>{simulatedResults.trades_reduction}</div>
              </div>
              <div>
                <div style={{ color: "var(--text-muted)" }}>Est. Win Rate</div>
                <div style={{ fontWeight: 600 }}>{simulatedResults.win_rate}</div>
              </div>
            </div>
          </div>
        )}

        {/* Quick Tips */}
        <div style={{
          background: "rgba(245, 158, 11, 0.1)",
          border: "1px solid rgba(245, 158, 11, 0.3)",
          borderRadius: "8px",
          padding: "12px",
          fontSize: "0.8rem"
        }}>
          <div style={{ fontWeight: 600, color: "var(--accent-yellow)", marginBottom: "4px" }}>
            💡 Optimization Tips
          </div>
          <ul style={{ margin: 0, paddingLeft: "16px", color: "var(--text-secondary)" }}>
            <li>Skip 14:00 hour - loses $158 daily</li>
            <li>Trade 15:00 hour - best profits (+$133)</li>
            <li>Use long-only for NVDA - shorts fail</li>
            <li>Wider trailing stops let winners run</li>
          </ul>
        </div>
      </div>
    </div>
  );
}

export default AOSOptimizations;
