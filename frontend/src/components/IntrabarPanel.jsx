import { useCallback, useEffect, useMemo, useState } from "react";

/**
 * IntrabarPanel - Displays 1-second intrabar data for a selected minute bar.
 * Shows sparklines for imbalance, delta, pressure, and quality metrics.
 */
function IntrabarPanel({ 
  runId, 
  ticker, 
  date, 
  selectedBar, 
  onClose,
  apiBase = "http://localhost:8000" 
}) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [data, setData] = useState(null);

  // Fetch bar details when selectedBar changes
  useEffect(() => {
    if (!selectedBar || !runId || !ticker || !date) {
      setData(null);
      return;
    }

    const minuteKey = Math.floor(selectedBar.time);
    
    const fetchData = async () => {
      setLoading(true);
      setError(null);
      
      try {
        const url = `${apiBase}/api/run/${runId}/${ticker}/${date}/bar-details/${minuteKey}`;
        const response = await fetch(url);
        
        if (!response.ok) {
          throw new Error(`Failed to fetch: ${response.status}`);
        }
        
        const json = await response.json();
        setData(json);
      } catch (err) {
        console.error("IntrabarPanel fetch error:", err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [selectedBar, runId, ticker, date, apiBase]);

  // Extract series data for sparklines
  const series = useMemo(() => {
    if (!data?.frames?.length) return null;
    
    const frames = data.frames;
    return {
      delta: frames.map(f => f.delta_sec || 0),
      cumDelta: frames.map(f => f.cum_delta_sec || 0),
      imbalance: frames.map(f => f.imbalance_sec || 0),
      pressure: frames.map(f => f.book_pressure_sec || 0),
      spreadBps: frames.map(f => f.spread_bps || 0),
    };
  }, [data]);

  // Simple SVG sparkline component
  const Sparkline = useCallback(({ values, color = "#3b82f6", height = 30 }) => {
    if (!values || values.length === 0) return null;
    
    const width = 200;
    const padding = 2;
    const min = Math.min(...values);
    const max = Math.max(...values);
    const range = max - min || 1;
    
    const points = values.map((v, i) => {
      const x = padding + (i / (values.length - 1 || 1)) * (width - 2 * padding);
      const y = height - padding - ((v - min) / range) * (height - 2 * padding);
      return `${x},${y}`;
    }).join(" ");

    return (
      <svg width={width} height={height} style={{ display: "block" }}>
        <polyline
          points={points}
          fill="none"
          stroke={color}
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    );
  }, []);

  if (!selectedBar) {
    return null;
  }

  const barTime = new Date(selectedBar.time * 1000).toISOString().substring(11, 19);

  return (
    <div className="intrabar-panel">
      <div className="intrabar-panel__header">
        <span className="intrabar-panel__title">
          Intrabar Details – {barTime}
        </span>
        <button className="intrabar-panel__close" onClick={onClose}>×</button>
      </div>

      <div className="intrabar-panel__content">
        {loading && (
          <div className="intrabar-panel__loading">Loading...</div>
        )}

        {error && (
          <div className="intrabar-panel__error">Error: {error}</div>
        )}

        {data && !loading && (
          <>
            {/* Stats Row */}
            <div className="intrabar-panel__stats">
              <div className="intrabar-panel__stat">
                <span className="intrabar-panel__stat-label">Coverage</span>
                <span className="intrabar-panel__stat-value">
                  {((data.stats?.coverage_ratio || 0) * 100).toFixed(0)}%
                </span>
              </div>
              <div className="intrabar-panel__stat">
                <span className="intrabar-panel__stat-label">Trades</span>
                <span className="intrabar-panel__stat-value">
                  {data.stats?.total_trade_ticks || 0}
                </span>
              </div>
              <div className="intrabar-panel__stat">
                <span className="intrabar-panel__stat-label">Book Updates</span>
                <span className="intrabar-panel__stat-value">
                  {data.stats?.total_book_updates || 0}
                </span>
              </div>
              <div className="intrabar-panel__stat">
                <span className="intrabar-panel__stat-label">Seconds</span>
                <span className="intrabar-panel__stat-value">
                  {data.stats?.seconds || 0}
                </span>
              </div>
            </div>

            {/* Sparklines */}
            {series && (
              <div className="intrabar-panel__sparklines">
                <div className="intrabar-panel__sparkline">
                  <span className="intrabar-panel__sparkline-label">Cum Delta</span>
                  <Sparkline values={series.cumDelta} color="#22c55e" />
                </div>
                <div className="intrabar-panel__sparkline">
                  <span className="intrabar-panel__sparkline-label">Imbalance</span>
                  <Sparkline values={series.imbalance} color="#3b82f6" />
                </div>
                <div className="intrabar-panel__sparkline">
                  <span className="intrabar-panel__sparkline-label">Pressure</span>
                  <Sparkline values={series.pressure} color="#f59e0b" />
                </div>
                <div className="intrabar-panel__sparkline">
                  <span className="intrabar-panel__sparkline-label">Spread (bps)</span>
                  <Sparkline values={series.spreadBps} color="#8b5cf6" />
                </div>
              </div>
            )}

            {/* No data message */}
            {!data.stats?.has_data && (
              <div className="intrabar-panel__empty">
                No L2 data available for this bar
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

export default IntrabarPanel;
