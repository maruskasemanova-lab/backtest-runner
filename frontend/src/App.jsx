import { useState, useEffect, useRef, useCallback } from 'react';
import { createChart } from 'lightweight-charts';
import CandlestickChart from './components/CandlestickChart';
import PlaybackControls from './components/PlaybackControls';
import DecisionPanel from './components/DecisionPanel';
import SessionSummary from './components/SessionSummary';
import RunConfig from './components/RunConfig';
import StrategySettings from './components/StrategySettings';
import AOSOptimizations from './components/AOSOptimizations';

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
  
  // Playback
  const [isPlaying, setIsPlaying] = useState(false);
  const [speed, setSpeed] = useState('10hz'); // Default: 10 updates per second (string for hz, number for ms)
  
  // WebSocket
  const wsRef = useRef(null);
  
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
  
  // Start a new run
  const handleStartRun = async (config) => {
    try {
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
  
  return (
    <div className="app-container">
      {/* Header */}
      <header className="app-header">
        <h1>
          <span className="logo">📊</span>
          Backtest Runner
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
          </div>
          <div className="chart-wrapper">
            <CandlestickChart 
              bars={bars} 
              markers={markers}
              onMarkerClick={handleMarkerClick}
              selectedMarker={selectedMarker}
            />
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
