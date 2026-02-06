import { useState, useEffect, useRef, useCallback } from 'react';
import { createChart } from 'lightweight-charts';
import CandlestickChart from './components/CandlestickChart';
import FootprintChart from './components/FootprintChart';
import PlaybackControls from './components/PlaybackControls';
import DecisionPanel from './components/DecisionPanel';
import SessionSummary from './components/SessionSummary';
import RunConfig from './components/RunConfig';
import StrategySettings from './components/StrategySettings';
import AOSOptimizations from './components/AOSOptimizations';
import MultiLayerSettings from './components/MultiLayerSettings';

function App() {
  // Run state
  const [runKey, setRunKey] = useState(null);
  const [runState, setRunState] = useState(null);
  const [isConnected, setIsConnected] = useState(false);
  
  // Data
  const [bars, setBars] = useState([]);
  const [markers, setMarkers] = useState([]);
  const [selectedMarker, setSelectedMarker] = useState(null);
  const [currentBar, setCurrentBar] = useState(null);
  const [selectedTicker, setSelectedTicker] = useState(null);
  const [strategyApiUrl, setStrategyApiUrl] = useState("http://localhost:8001");
  const [aosOptimizations, setAosOptimizations] = useState({});
  
  // L2 Data
  const [activeTab, setActiveTab] = useState("l2"); // "standard" or "l2"
  const [l2Data, setL2Data] = useState(null);
  const [icebergs, setIcebergs] = useState([]);
  const [timeframe, setTimeframe] = useState("1min");
  
  // Chart Synchronization State
  const [chartState, setChartState] = useState(null); // { from: number, to: number } (Time Range)
  const [priceRange, setPriceRange] = useState(null); // { from: number, to: number } (Price Range)

  // ...

  const [isPlaying, setIsPlaying] = useState(false);
  const [speed, setSpeed] = useState('10hz'); // Default: 10 updates per second (string for hz, number for ms)
  
  // WebSocket
  const wsRef = useRef(null);

  // Debug
  const [debugMsg, setDebugMsg] = useState("Initializing...");
  
  // Connect WebSocket
  useEffect(() => {
    const connectWs = () => {
      const ws = new WebSocket(`ws://${window.location.hostname}:8002/ws/live`);
      
      ws.onopen = () => {
        console.log('WebSocket connected');
        setIsConnected(true);
        if (runKey) {
          ws.send(JSON.stringify({ type: 'subscribe', run_id: runKey }));
        }
      };
      
      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        
        if (data.type === 'bar') {
          handleNewBar(data.bar);
        } else if (data.type === 'decision') {
          handleNewDecision(data.marker);
        }
      };
      
      ws.onclose = () => {
        console.log('WebSocket disconnected');
        setIsConnected(false);
        // Reconnect after 3 seconds
        setTimeout(connectWs, 3000);
      };
      
      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
      };
      
      wsRef.current = ws;
    };
    
    connectWs();
    
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [runKey]);
  
  // Handle new bar from WebSocket
  const handleNewBar = useCallback((bar) => {
    const chartBar = {
      time: new Date(bar.timestamp).getTime() / 1000,
      open: bar.open,
      high: bar.high,
      low: bar.low,
      close: bar.close,
      volume: bar.volume
    };
    
    setBars(prev => [...prev, chartBar]);
    setCurrentBar(bar);
    setRunState(prev => prev ? {
      ...prev,
      current_bar_index: (bar.index || bar.bar_index || 0) + 1,
      progress_pct: (((bar.index || bar.bar_index || 0) + 1) / prev.total_bars) * 100
    } : null);
  }, []);
  
  // Handle new decision from WebSocket
  const handleNewDecision = useCallback((marker) => {
    setMarkers(prev => {
      const idx = prev.findIndex(m => m.id === marker.id);
      if (idx !== -1) {
        // Merge/update existing marker to avoid duplicates and keep latest info
        const next = [...prev];
        next[idx] = { ...prev[idx], ...marker };
        return next;
      }
      return [...prev, marker];
    });
  }, []);

  // Resample bars based on timeframe
  const aggregatedBars = useCallback(() => {
      if (timeframe === '1min') return bars;
      if (!bars.length) return [];

      const tfMinutes = parseInt(timeframe);
      if (isNaN(tfMinutes)) return bars;
      
      const interval = tfMinutes * 60; // seconds
      const groups = new Map();

      bars.forEach(bar => {
          const time = bar.time; // seconds
          // quantize time to interval start
          const bucket = Math.floor(time / interval) * interval;
           
          if (!groups.has(bucket)) {
              groups.set(bucket, {
                  time: bucket,
                  open: bar.open,
                  high: bar.high,
                  low: bar.low,
                  close: bar.close,
                  volume: bar.volume,
                  count: 1
              });
          } else {
              const b = groups.get(bucket);
              b.high = Math.max(b.high, bar.high);
              b.low = Math.min(b.low, bar.low);
              b.close = bar.close;
              b.volume += bar.volume;
              b.count++;
          }
      });
      
      return Array.from(groups.values()).sort((a,b) => a.time - b.time);
  }, [bars, timeframe]);

  const displayedBars = aggregatedBars();

  // Fetch L2 Data - Updated to run for Standard tab too (for Delta display)
  useEffect(() => {
      // Fetch if we have run info
      if (!runState || !runKey) return;
      
      const fetchL2 = async () => {
          try {
              if (!runState.date) return;

              const date = runState.date.split('_')[0]; 
              const ticker = runState.ticker;
              const start = `${date}T04:00:00Z`; 
              const end = `${date}T20:00:00Z`; 
              
              setDebugMsg(`Fetching L2 & Icebergs... ${ticker} ${date}`);

              // Parallel fetch
              const [l2Res, iceRes] = await Promise.all([
                  fetch(`/api/l2/footprint/${ticker}?start_time=${start}&end_time=${end}&timeframe=${timeframe}`),
                  fetch(`/api/l2/icebergs/${ticker}?start_time=${start}&end_time=${end}`)
              ]);
              
              if (l2Res.ok) {
                  const data = await l2Res.json();
                  setL2Data({...data, date, timeframe});
                  setDebugMsg(prev => `${prev} L2: ${data.bars?.length}`);
              } else {
                  console.error("L2 fetch failed", l2Res.status);
              }
              
              if (iceRes.ok) {
                  const iceData = await iceRes.json();
                  setIcebergs(iceData);
                  setDebugMsg(prev => `${prev} Ice: ${iceData?.length}`);
              } else {
                  console.error("Iceberg fetch failed", iceRes.status);
              }

          } catch (e) {
              setDebugMsg(`Fetch Error: ${e.message}`);
              console.error("Fetch error:", e);
          }
      };
      
      fetchL2();
  }, [runKey, runState?.ticker, runState?.date, timeframe]); // Removed activeTab dependency so it fetches for Standard too
  
  // Start a new run
  const handleStartRun = async (config) => {
    try {
      setSelectedTicker(config.ticker || null);
      setStrategyApiUrl(config.strategy_api_url || "http://localhost:8001");
      const resp = await fetch('/api/run/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config)
      });
      
      if (!resp.ok) {
        const error = await resp.json();
        throw new Error(error.detail || 'Failed to start run');
      }
      
      const data = await resp.json();
      const key = data.run_key;
      setRunKey(key);
      
      // Reset state
      setBars([]);
      setMarkers([]);
      setSelectedMarker(null);
      setCurrentBar(null);
      
      // Fetch initial state
      const parts = key.split(':');
      const stateResp = await fetch(`/api/run/${parts[0]}/${parts[1]}/${parts[2]}/state`);
      const state = await stateResp.json();
      setRunState(state);
      
      // Subscribe WebSocket
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: 'subscribe', run_id: config.run_id }));
      }
      
      return data;
    } catch (error) {
      console.error('Start run error:', error);
      throw error;
    }
  };
  
  // Step forward one bar
  const handleStep = async () => {
    if (!runKey) return;
    
    const parts = runKey.split(':');
    try {
      const resp = await fetch(`/api/run/${parts[0]}/${parts[1]}/${parts[2]}/step`, {
        method: 'POST'
      });
      const data = await resp.json();
      
      if (data.success && data.bar) {
        handleNewBar(data.bar);
        
        // Update state
        setRunState(prev => ({
          ...prev,
          current_bar_index: data.bar_index,
          phase: data.phase,
          progress_pct: data.progress_pct
        }));
      }
      
      return data;
    } catch (error) {
      console.error('Step error:', error);
    }
  };
  
  // Play/auto-advance
  const handlePlay = async () => {
    if (!runKey) return;
    
    const parts = runKey.split(':');
    try {
      // Support both hz (string) and ms (number) formats
      let speedParam;
      if (typeof speed === 'string') {
        // 'max', '10hz', '5hz', etc.
        speedParam = speed;
      } else if (speed === 0) {
        speedParam = 'max';
      } else {
        speedParam = speed;
      }
      
      await fetch(`/api/run/${parts[0]}/${parts[1]}/${parts[2]}/play`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ speed_ms: speedParam })
      });
      setIsPlaying(true);
    } catch (error) {
      console.error('Play error:', error);
    }
  };
  
  // Pause
  const handlePause = async () => {
    if (!runKey) return;
    
    const parts = runKey.split(':');
    try {
      await fetch(`/api/run/${parts[0]}/${parts[1]}/${parts[2]}/pause`, {
        method: 'POST'
      });
      setIsPlaying(false);
    } catch (error) {
      console.error('Pause error:', error);
    }
  };
  
  // Stop
  const handleStop = async () => {
    if (!runKey) return;
    
    const parts = runKey.split(':');
    try {
      await fetch(`/api/run/${parts[0]}/${parts[1]}/${parts[2]}/stop`, {
        method: 'POST'
      });
      setIsPlaying(false);
    } catch (error) {
      console.error('Stop error:', error);
    }
  };
  
  // Reset run
  const handleReset = async () => {
    if (!runKey) return;
    
    const parts = runKey.split(':');
    try {
      await fetch(`/api/run/${parts[0]}/${parts[1]}/${parts[2]}`, {
        method: 'DELETE'
      });
      setRunKey(null);
      setRunState(null);
      setBars([]);
      setMarkers([]);
      setSelectedMarker(null);
      setCurrentBar(null);
      setIsPlaying(false);
    } catch (error) {
      console.error('Reset error:', error);
    }
  };
  
  // Click marker on chart
  const handleMarkerClick = (markerId) => {
    const marker = markers.find(m => m.id === markerId);
    setSelectedMarker(marker);
  };
  
  // Debug state moved to top level
  
  return (
    <div className="app-container">
      {/* Header */}
      <header className="app-header">
        <h1 style={{ display: 'flex', flexDirection: 'column' }}>
          <div>
            <span className="logo">📊</span>
            Backtest Runner
          </div>
          <span style={{ fontSize: '10px', color: 'orange' }}>DEBUG: {debugMsg}</span>
        </h1>
        <div className="connection-status">
          <span className={`status-dot ${isConnected ? 'connected' : ''}`}></span>
          <span>{isConnected ? 'Connected' : 'Disconnected'}</span>
        </div>
      </header>
      
      {/* Main Content */}
      <main className="app-content">
        {/* Left Sidebar */}
        <aside className="sidebar">
          {/* Run Config */}
          <RunConfig 
            onStart={handleStartRun} 
            isRunning={!!runKey}
            onTickerChange={setSelectedTicker}
          />

          {/* Strategy Settings */}
          <StrategySettings apiUrl={strategyApiUrl} selectedTicker={selectedTicker} />

          {/* Multi-Layer Decision Engine */}
          <MultiLayerSettings apiUrl={strategyApiUrl} />

          {/* AOS Optimizations */}
          <AOSOptimizations 
            apiUrl={strategyApiUrl}
            selectedTicker={selectedTicker}
            onOptimizationChange={(ticker, config) => {
              setAosOptimizations(prev => ({...prev, [ticker]: config}));
            }}
          />
          
          {/* Playback Controls */}
          {runKey && (
            <PlaybackControls
              runState={runState}
              isPlaying={isPlaying}
              speed={speed}
              onSpeedChange={setSpeed}
              onStep={handleStep}
              onPlay={handlePlay}
              onPause={handlePause}
              onStop={handleStop}
              onReset={handleReset}
            />
          )}
          
          {/* Session Summary */}
          {runState && (
            <SessionSummary runState={runState} markers={markers} />
          )}
        </aside>
        
        {/* Chart */}
        <section className="card chart-container">
          <div className="card-header">
            <span className="card-title">
              {runState
                ? `${runState.ticker} - ${
                    runState.date_from && runState.date_to
                      ? `${runState.date_from} → ${runState.date_to}`
                      : runState.date
                  }`
                : 'Price Chart'}
            </span>
            {runState && (
              <span className={`phase-badge ${runState.phase?.toLowerCase()}`}>
                {runState.phase}
              </span>
            )}
            <div className="tab-switcher" style={{ marginLeft: "auto", display: "flex", gap: "10px", alignItems: "center" }}>
                <select 
                    value={timeframe} 
                    onChange={(e) => setTimeframe(e.target.value)}
                    style={{
                        background: '#333',
                        color: '#fff',
                        border: '1px solid #555',
                        borderRadius: '4px',
                        padding: '4px',
                        marginRight: '10px',
                        cursor: 'pointer'
                    }}
                >
                    <option value="1min">1 Min</option>
                    <option value="5min">5 Min</option>
                    <option value="15min">15 Min</option>
                    <option value="30min">30 Min</option>
                    <option value="1h">1 Hour</option>
                </select>
                <button 
                    className={`tab-btn ${activeTab === 'standard' ? 'active' : ''}`}
                    onClick={() => setActiveTab('standard')}
                    style={{ 
                        background: activeTab === 'standard' ? 'var(--accent-blue)' : 'transparent',
                        color: activeTab === 'standard' ? '#fff' : 'var(--text-secondary)',
                        border: '1px solid var(--border-color)',
                        padding: '4px 8px',
                        cursor: 'pointer',
                        borderRadius: '4px'
                    }}
                >
                    Standard
                </button>
                <button 
                    className={`tab-btn ${activeTab === 'l2' ? 'active' : ''}`}
                    onClick={() => setActiveTab('l2')}
                     style={{ 
                        background: activeTab === 'l2' ? 'var(--accent-blue)' : 'transparent',
                        color: activeTab === 'l2' ? '#fff' : 'var(--text-secondary)',
                        border: '1px solid var(--border-color)',
                        padding: '4px 8px',
                        cursor: 'pointer',
                        borderRadius: '4px'
                    }}
                >
                    L2 Footprint
                </button>
            </div>
          </div>
          <div className="chart-wrapper">
            {activeTab === 'standard' ? (
                <CandlestickChart 
                  bars={displayedBars} 
                  markers={markers}
                  icebergs={icebergs}
                  onMarkerClick={handleMarkerClick}
                  selectedMarker={selectedMarker}
                  chartState={chartState}
                  onChartStateChange={(newState) => {
                    setChartState(prev => {
                        if (prev && newState && 
                            Math.abs(prev.from - newState.from) < 0.001 && 
                            Math.abs(prev.to - newState.to) < 0.001) {
                            return prev;
                        }
                        return newState;
                    });
                  }}
                  priceRange={priceRange}
                  onPriceRangeChange={setPriceRange}
                  l2Data={l2Data} 
                />
            ) : (
                <FootprintChart 
                  bars={displayedBars} 
                  markers={markers}
                  icebergs={icebergs}
                  onMarkerClick={handleMarkerClick}
                  selectedMarker={selectedMarker}
                  l2Data={l2Data}
                  chartState={chartState}
                  onChartStateChange={(newState) => {
                    setChartState(prev => {
                        if (prev && newState && 
                            Math.abs(prev.from - newState.from) < 0.001 && 
                            Math.abs(prev.to - newState.to) < 0.001) {
                            return prev;
                        }
                        return newState;
                    });
                  }}
                  priceRange={priceRange}
                  onPriceRangeChange={setPriceRange}
                />
            )}
          </div>
          {currentBar && (
            <div className="current-bar-info">
              <div className="bar-stat">
                <div className="bar-stat-value">${currentBar.open?.toFixed(2)}</div>
                <div className="bar-stat-label">Open</div>
              </div>
              <div className="bar-stat">
                <div className="bar-stat-value up">${currentBar.high?.toFixed(2)}</div>
                <div className="bar-stat-label">High</div>
              </div>
              <div className="bar-stat">
                <div className="bar-stat-value down">${currentBar.low?.toFixed(2)}</div>
                <div className="bar-stat-label">Low</div>
              </div>
              <div className="bar-stat">
                <div className={`bar-stat-value ${currentBar.close >= currentBar.open ? 'up' : 'down'}`}>
                  ${currentBar.close?.toFixed(2)}
                </div>
                <div className="bar-stat-label">Close</div>
              </div>
            </div>
          )}
        </section>
        
        {/* Right Panel - Decisions */}
        <aside className="card decision-panel">
          <div className="card-header">
            <span className="card-title">Decisions</span>
            <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>
              {markers.length} total
            </span>
          </div>
          <div className="card-body">
            <DecisionPanel 
              markers={markers}
              selectedMarker={selectedMarker}
              onSelectMarker={setSelectedMarker}
            />
          </div>
        </aside>
      </main>
    </div>
  );
}

export default App;
