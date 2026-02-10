import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import CandlestickChart from './components/CandlestickChart';
import FootprintChart from './components/FootprintChart';
import PlaybackControls from './components/PlaybackControls';
import DecisionPanel from './components/DecisionPanel';
import SessionSummary from './components/SessionSummary';
import RunConfig from './components/RunConfig';
import StrategySettings from './components/StrategySettings';
import DataManager from './components/DataManager';
import IntrabarPanel from './components/IntrabarPanel';
import AdaptiveStrategyStudio from './components/AdaptiveStrategyStudio';
import AdaptiveTuner from './components/AdaptiveTuner';

const toUnixSeconds = (value) => {
  if (value === null || value === undefined) return null;
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value > 1e12 ? value / 1000 : value;
  }
  if (typeof value === 'string') {
    const numeric = Number(value);
    if (Number.isFinite(numeric)) {
      return numeric > 1e12 ? numeric / 1000 : numeric;
    }
    const normalized = value.replace(/(\.\d{3})\d+/, '$1');
    const parsed = Date.parse(normalized);
    if (!Number.isNaN(parsed)) return parsed / 1000;
  }
  return null;
};

const toIsoTimestamp = (value) => {
  const seconds = toUnixSeconds(value);
  if (!Number.isFinite(seconds)) return null;
  return new Date(seconds * 1000).toISOString();
};

const normalizeText = (value) => {
  if (value === null || value === undefined) return '';
  return String(value).trim().toLowerCase();
};

const scoreMarkerMatch = (candidate, target) => {
  if (!candidate || !target) return Number.NEGATIVE_INFINITY;

  const candidateId = normalizeText(candidate.id);
  const targetId = normalizeText(target.id);
  if (candidateId && targetId && candidateId === targetId) {
    return Number.POSITIVE_INFINITY;
  }

  let score = 0;

  const candidateType = normalizeText(candidate.marker_type);
  const targetType = normalizeText(target.marker_type);
  if (candidateType && targetType) {
    score += candidateType === targetType ? 500 : -200;
  }

  const candidateSide = normalizeText(candidate.side ?? candidate.details?.side);
  const targetSide = normalizeText(target.side ?? target.details?.side);
  if (candidateSide && targetSide && candidateSide === targetSide) {
    score += 180;
  }

  const candidateStrategy = normalizeText(candidate.strategy);
  const targetStrategy = normalizeText(target.strategy);
  if (candidateStrategy && targetStrategy && candidateStrategy === targetStrategy) {
    score += 140;
  }

  const candidateRegime = normalizeText(candidate.regime);
  const targetRegime = normalizeText(target.regime);
  if (candidateRegime && targetRegime && candidateRegime === targetRegime) {
    score += 120;
  }

  const candidateSignal = normalizeText(candidate.details?.signal_type);
  const targetSignal = normalizeText(target.details?.signal_type);
  if (candidateSignal && targetSignal && candidateSignal === targetSignal) {
    score += 80;
  }

  const candidateRun = normalizeText(candidate.run_id ?? candidate.details?.run_id);
  const targetRun = normalizeText(target.run_id ?? target.details?.run_id);
  if (candidateRun && targetRun && candidateRun === targetRun) {
    score += 90;
  }

  const candidateTicker = normalizeText(candidate.ticker ?? candidate.details?.ticker);
  const targetTicker = normalizeText(target.ticker ?? target.details?.ticker);
  if (candidateTicker && targetTicker && candidateTicker === targetTicker) {
    score += 60;
  }

  const candidateTitle = normalizeText(candidate.title);
  const targetTitle = normalizeText(target.title);
  if (candidateTitle && targetTitle && candidateTitle === targetTitle) {
    score += 40;
  }

  const candidateTs = toUnixSeconds(candidate.time ?? candidate.timestamp);
  const targetTs = toUnixSeconds(target.time ?? target.timestamp);
  if (Number.isFinite(candidateTs) && Number.isFinite(targetTs)) {
    const diff = Math.abs(candidateTs - targetTs);
    if (diff <= 1) score += 220;
    else if (diff <= 5) score += 170;
    else if (diff <= 60) score += 120;
    else if (diff <= 300) score += 70;
    else if (diff <= 1800) score += 20;
    else score -= Math.min(220, diff / 20);
  }

  const candidatePrice = Number(candidate.price);
  const targetPrice = Number(target.price);
  if (Number.isFinite(candidatePrice) && Number.isFinite(targetPrice)) {
    const diff = Math.abs(candidatePrice - targetPrice);
    score += 120 / (1 + diff);
  }

  return score;
};

function App() {
  // Run state
  const [runKey, setRunKey] = useState(null);
  const [runState, setRunState] = useState(null);
  const [effectiveExecutionConfig, setEffectiveExecutionConfig] = useState(null);
  const [isConnected, setIsConnected] = useState(false);
  
  // Data
  const [bars, setBars] = useState([]);
  const [markers, setMarkers] = useState([]);
  const [selectedMarker, setSelectedMarker] = useState(null);
  const [currentBar, setCurrentBar] = useState(null);
  const [selectedIntrabar, setSelectedIntrabar] = useState(null);
  const [selectedTicker, setSelectedTicker] = useState(null);
  const [strategyApiUrl, setStrategyApiUrl] = useState("http://localhost:8001");
  
  // View navigation
  const [activeView, setActiveView] = useState("backtest"); // "backtest" | "data-manager" | "adaptive-studio" | "adaptive-tuner"
  const [downloadProgress, setDownloadProgress] = useState(null);

  // L2 Data
  const [activeTab, setActiveTab] = useState("standard"); // "standard" or "l2"
  const [l2Data, setL2Data] = useState(null);
  const [icebergs, setIcebergs] = useState([]);
  const [timeframe, setTimeframe] = useState("1min");
  
  // Chart Synchronization State
  const [chartState, setChartState] = useState(null); // { from: number, to: number } (Time Range)
  const [priceRange, setPriceRange] = useState(null); // { from: number, to: number } (Price Range)

  // Marker visibility toggles
  const [markerVisibility, setMarkerVisibility] = useState({
    entries: true,
    exits: true,
    icebergs: true,
    regime: true,
    strategy: true
  });

  // ...

  const [isPlaying, setIsPlaying] = useState(false);
  const [speed, setSpeed] = useState('10hz'); // Default: 10 updates per second (string for hz, number for ms)
  
  // WebSocket
  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const isMountedRef = useRef(true); // Track mount status
  const activeRunId = runKey ? String(runKey).split(':')[0] : null;
  const activeRunTicker = runKey ? String(runKey).split(':')[1] : null;

  // Track mount status
  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  // Connect WebSocket - dependent only on hostname
  useEffect(() => {
    const connectWs = () => {
      // Avoid multiple connections
      if (wsRef.current && (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING)) {
        return;
      }

      console.log('Connecting WebSocket...');
      // Clean up existing closed/closing socket just in case
      if (wsRef.current) {
        try { wsRef.current.close(); } catch(e) {}
        wsRef.current = null;
      }

      const ws = new WebSocket(`ws://${window.location.hostname}:8002/ws/live`);
      wsRef.current = ws;
      
      ws.onopen = () => {
        if (!isMountedRef.current) {
            ws.close();
            return;
        }
        console.log('WebSocket connected');
        setIsConnected(true);
        // Subscription will be handled by the other useEffect
      };
      
      ws.onmessage = (event) => {
        if (!isMountedRef.current) return;
        try {
            const data = JSON.parse(event.data);
            handleWsMessage(data);
        } catch (err) {
            console.error("Failed to parse WS message:", err);
        }
      };
      
      ws.onclose = () => {
        if (!isMountedRef.current) return;
        console.log('WebSocket disconnected');
        setIsConnected(false);
        wsRef.current = null;
        
        // Reconnect after 3 seconds
        if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = setTimeout(connectWs, 3000);
      };
      
      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        // Do not agressively close here, let onclose handle it or browser handle it
      };
    };
    
    connectWs();
    
    return () => {
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      // In Strict Mode, we DO NOT want to close the socket immediately if we just opened it.
      // But we must clean up if we are truly unmounting.
      // We can check if we are unmounting by using the ref, but the ref cleanup runs after this?
      // Actually, simple ref-based protection in onopen/onmessage is enough for safety.
      // For the socket itself:
      if (wsRef.current && isMountedRef.current === false) { 
         // Only close if we are sure we are unmounting (ref should be false by now? No, ref cleanup runs before or same time?)
         // React effects cleanup runs before the next effect or on unmount.
         // Let's just rely on the fact that if we re-run, we check readyState.
         wsRef.current.close();
         wsRef.current = null;
      }
    };
  }, []); // Empty dependency array - connect once on mount

  // Handle subscriptions when activeRunId changes or socket connects
  useEffect(() => {
     const subscribe = () => {
        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN && activeRunId) {
            console.log(`Subscribing to run: ${activeRunId}`);
            wsRef.current.send(JSON.stringify({ type: 'subscribe', run_id: activeRunId }));
        }
     };

     // Subscribe immediately if open, or wait for connection
     if (isConnected) {
         subscribe();
     } else {
         // The onopen handler in the connection effect could handle this, 
         // but since we split them, we can just watch isConnected here.
     }
  }, [activeRunId, isConnected]);

  const handleWsMessage = useCallback((data) => {
    const msgRunId = data?.run_id ? String(data.run_id) : null;
    const msgTicker = data?.ticker ? String(data.ticker).toUpperCase() : null;
    const currentTicker = activeRunTicker ? String(activeRunTicker).toUpperCase() : null;

    // Backend broadcasts all runs; ignore frames that do not belong to the active run.
    if (activeRunId && msgRunId && msgRunId !== activeRunId) return;
    if (currentTicker && msgTicker && msgTicker !== currentTicker) return;
    
    if (data.type === 'bar') {
      handleNewBar(data.bar);
    } else if (data.type === 'decision') {
      handleNewDecision(data.marker);
    } else if (data.type === 'download_progress') {
      setDownloadProgress(data);
    }
  }, [activeRunId, activeRunTicker]);
  
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
    setRunState(prev => {
      if (!prev) return null;

      const totalBars = Number(prev.total_bars || 0);
      const streamIndex = Number(bar?.bar_index);
      const legacyIndex = Number(bar?.index);

      const rawCurrent = Number.isFinite(streamIndex)
        ? streamIndex + 1
        : (Number.isFinite(legacyIndex)
            ? legacyIndex + 1
            : Number(prev.current_bar_index || 0) + 1);

      const current = totalBars > 0
        ? Math.min(totalBars, Math.max(0, rawCurrent))
        : Math.max(0, rawCurrent);
      const progress = totalBars > 0
        ? Math.min(100, Math.max(0, (current / totalBars) * 100))
        : 0;

      return {
        ...prev,
        current_bar_index: current,
        progress_pct: progress,
      };
    });
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

  const displayedBars = useMemo(() => {
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

  // Stable chart state change handler
  const handleChartStateChange = useCallback((newState) => {
      setChartState(prev => {
          if (prev && newState && 
              Math.abs(prev.from - newState.from) < 0.001 && 
              Math.abs(prev.to - newState.to) < 0.001) {
              return prev;
          }
          return newState;
      });
  }, []);

  // Filter markers based on visibility toggles
  const filteredMarkers = useMemo(() => {
      if (!markers || markers.length === 0) return [];
      return markers.filter(m => {
          const type = m.marker_type;
          if (type === 'entry_executed' && !markerVisibility.entries) return false;
          if ((type === 'exit_executed' || type === 'stop_loss_hit' || type === 'take_profit_hit') && !markerVisibility.exits) return false;
          if (type === 'regime_detected' && !markerVisibility.regime) return false;
          if (type === 'strategy_selected' && !markerVisibility.strategy) return false;
          return true;
      });
  }, [markers, markerVisibility]);

  const filteredIcebergs = useMemo(() => {
      if (!markerVisibility.icebergs) return [];
      return icebergs;
  }, [icebergs, markerVisibility.icebergs]);

  const icebergDecisionMarkers = useMemo(() => {
    if (!icebergs || icebergs.length === 0) return [];

    return icebergs
      .map((iceberg, idx) => {
        const rawTime = toUnixSeconds(iceberg?.time ?? iceberg?.timestamp);
        const timestamp = iceberg?.timestamp || toIsoTimestamp(rawTime);
        if (!timestamp) return null;

        const tradeSize = Number(iceberg?.trade_size ?? 0);
        const hiddenSize = Number(iceberg?.hidden_size ?? 0);
        const totalSize = tradeSize + hiddenSize;
        const side = typeof iceberg?.side === 'string' ? iceberg.side.toLowerCase() : null;
        const price = Number(iceberg?.price);
        const normalizedPrice = Number.isFinite(price) ? price : null;
        const sideLabel = side ? side.toUpperCase() : 'UNKNOWN';
        const readableSide = side === 'buy' ? 'BUY support' : side === 'sell' ? 'SELL resistance' : 'unknown side';

        return {
          ...iceberg,
          id: iceberg.id || `iceberg-${timestamp}-${normalizedPrice ?? 'na'}-${idx}`,
          marker_type: 'iceberg_detected',
          title: iceberg.title || `Iceberg ${sideLabel}`,
          description: iceberg.description || `Detected ${readableSide} iceberg`,
          timestamp,
          time: rawTime,
          side,
          price: normalizedPrice,
          details: {
            ...(iceberg.details || {}),
            iceberg_side: side,
            iceberg_price: normalizedPrice,
            trade_size: tradeSize,
            hidden_size: hiddenSize,
            total_size: totalSize,
          },
        };
      })
      .filter(Boolean);
  }, [icebergs]);

  const decisionEvents = useMemo(
    () => [...markers, ...icebergDecisionMarkers],
    [markers, icebergDecisionMarkers]
  );

  // Toggle marker visibility helper
  const toggleMarkerVisibility = useCallback((key) => {
      setMarkerVisibility(prev => ({ ...prev, [key]: !prev[key] }));
  }, []);

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

              // Parallel fetch
              const [l2Res, iceRes] = await Promise.all([
                  fetch(`/api/l2/footprint/${ticker}?start_time=${start}&end_time=${end}&timeframe=${timeframe}`),
                  fetch(`/api/l2/icebergs/${ticker}?start_time=${start}&end_time=${end}`)
              ]);
              
              if (l2Res.ok) {
                  const data = await l2Res.json();
                  setL2Data({...data, date, timeframe});
              } else {
                  console.error("L2 fetch failed", l2Res.status);
              }
              
              if (iceRes.ok) {
                  const iceData = await iceRes.json();
                  setIcebergs(iceData);
              } else {
                  console.error("Iceberg fetch failed", iceRes.status);
              }

          } catch (e) {
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
      setEffectiveExecutionConfig(data.execution_config || null);
      
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
        setRunState(prev => {
          if (!prev) return prev;
          const totalBars = Number(prev.total_bars || 0);
          const rawCurrent = Number(data.bar_index || 0) + 1;
          const current = totalBars > 0
            ? Math.min(totalBars, Math.max(0, rawCurrent))
            : Math.max(0, rawCurrent);
          const progress = totalBars > 0
            ? Math.min(100, Math.max(0, (current / totalBars) * 100))
            : Number(data.progress_pct || 0);
          return {
            ...prev,
            current_bar_index: current,
            phase: data.phase,
            progress_pct: progress
          };
        });
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
      
      const response = await fetch(`/api/run/${parts[0]}/${parts[1]}/${parts[2]}/play`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ speed_ms: speedParam })
      });
      if (!response.ok) {
        setIsPlaying(false);
        console.error('Play request failed:', response.status, response.statusText);
        return;
      }
      setIsPlaying(true);
    } catch (error) {
      setIsPlaying(false);
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

  // Poll run state while playing so phase/progress stay in sync in range runs.
  useEffect(() => {
    if (!runKey || !isPlaying) return undefined;

    const parts = runKey.split(':');
    if (parts.length !== 3) return undefined;

    let cancelled = false;
    const pollState = async () => {
      if (cancelled) return;
      try {
        const resp = await fetch(`/api/run/${parts[0]}/${parts[1]}/${parts[2]}/state`);
        if (!resp.ok) {
          if (resp.status === 404) {
            if (!cancelled) {
              cancelled = true;
              setIsPlaying(false);
              setRunState((prev) => {
                if (!prev) return prev;
                return {
                  ...prev,
                  is_running: false
                };
              });
            }
            return;
          }
          console.warn('State poll failed:', resp.status, resp.statusText);
          return;
        }
        const state = await resp.json();
        if (cancelled) return;
        setRunState(state);
        if (!state?.is_running) {
          setIsPlaying(false);
        }
      } catch (error) {
        if (!cancelled) {
          setIsPlaying(false);
        }
        console.error('State poll error:', error);
      }
    };

    pollState();
    const interval = setInterval(pollState, 1000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [runKey, isPlaying]);
  
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
      setEffectiveExecutionConfig(null);
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
  const handleMarkerClick = useCallback((markerOrId) => {
    if (!markerOrId) return;

    if (typeof markerOrId !== 'object') {
      const marker = decisionEvents.find((eventMarker) => eventMarker.id === markerOrId);
      if (marker) {
        setSelectedMarker(marker);
      }
      return;
    }

    let bestMatch = null;
    let bestScore = Number.NEGATIVE_INFINITY;
    decisionEvents.forEach((eventMarker) => {
      const score = scoreMarkerMatch(eventMarker, markerOrId);
      if (score > bestScore) {
        bestScore = score;
        bestMatch = eventMarker;
      }
    });

    if (bestMatch && bestScore > 100) {
      setSelectedMarker(bestMatch);
      return;
    }

    setSelectedMarker(markerOrId);
  }, [decisionEvents]);
  
  // Debug state moved to top level
  
  return (
    <div className="app-container">
      {/* Header */}
      <header className="app-header">
        <h1>Backtest Runner</h1>
        <nav className="app-nav">
          <button
            className={`nav-tab ${activeView === 'backtest' ? 'active' : ''}`}
            onClick={() => setActiveView('backtest')}
          >
            Backtest
          </button>
          <button
            className={`nav-tab ${activeView === 'data-manager' ? 'active' : ''}`}
            onClick={() => setActiveView('data-manager')}
          >
            Data Manager
          </button>
          <button
            className={`nav-tab ${activeView === 'adaptive-studio' ? 'active' : ''}`}
            onClick={() => setActiveView('adaptive-studio')}
          >
            Adaptive Studio
          </button>
          <button
            className={`nav-tab ${activeView === 'adaptive-tuner' ? 'active' : ''}`}
            onClick={() => setActiveView('adaptive-tuner')}
          >
            Adaptive Tuner
          </button>
        </nav>
        <div className="connection-status">
          <span className={`status-dot ${isConnected ? 'connected' : ''}`}></span>
          <span>{isConnected ? 'Connected' : 'Disconnected'}</span>
        </div>
      </header>

      {/* Main Content */}
      {activeView === 'data-manager' ? (
        <DataManager downloadProgress={downloadProgress} />
      ) : activeView === 'adaptive-studio' ? (
        <AdaptiveStrategyStudio
          selectedTicker={selectedTicker}
          onTickerChange={setSelectedTicker}
          strategyApiUrl={strategyApiUrl}
        />
      ) : activeView === 'adaptive-tuner' ? (
        <AdaptiveTuner
          selectedTicker={selectedTicker}
          onTickerChange={setSelectedTicker}
          strategyApiUrl={strategyApiUrl}
        />
      ) : (
      <main className="app-content">
        {/* Left Sidebar */}
        <aside className="sidebar">
          {/* Run Config */}
          <RunConfig 
            onStart={handleStartRun} 
            isRunning={!!runKey}
            onTickerChange={setSelectedTicker}
            effectiveExecutionConfig={effectiveExecutionConfig}
          />

          {/* Strategy Settings */}
          <StrategySettings apiUrl={strategyApiUrl} selectedTicker={selectedTicker} />

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
            <div className="chart-toolbar">
                <select
                    className="chart-timeframe"
                    value={timeframe}
                    onChange={(e) => setTimeframe(e.target.value)}
                >
                    <option value="1min">1 Min</option>
                    <option value="5min">5 Min</option>
                    <option value="15min">15 Min</option>
                    <option value="30min">30 Min</option>
                    <option value="1h">1 Hour</option>
                </select>
                
                {/* Marker Visibility Toggles */}
                <div className="marker-toggles">
                    <button
                        className={`toggle-btn ${markerVisibility.entries ? 'active' : ''}`}
                        onClick={() => toggleMarkerVisibility('entries')}
                        title="Toggle Entry Markers"
                    >
                        E
                    </button>
                    <button
                        className={`toggle-btn ${markerVisibility.exits ? 'active' : ''}`}
                        onClick={() => toggleMarkerVisibility('exits')}
                        title="Toggle Exit/SL/TP Markers"
                    >
                        X
                    </button>
                    <button
                        className={`toggle-btn ${markerVisibility.icebergs ? 'active' : ''}`}
                        onClick={() => toggleMarkerVisibility('icebergs')}
                        title="Toggle Iceberg Markers"
                    >
                        ❄️
                    </button>
                    <button
                        className={`toggle-btn ${markerVisibility.regime ? 'active' : ''}`}
                        onClick={() => toggleMarkerVisibility('regime')}
                        title="Toggle Regime Markers"
                    >
                        R
                    </button>
                    <button
                        className={`toggle-btn ${markerVisibility.strategy ? 'active' : ''}`}
                        onClick={() => toggleMarkerVisibility('strategy')}
                        title="Toggle Strategy Markers"
                    >
                        S
                    </button>
                </div>
                
                <button
                    className={`chart-tab ${activeTab === 'standard' ? 'active' : ''}`}
                    onClick={() => setActiveTab('standard')}
                >
                    Candles
                </button>
                <button
                    className={`chart-tab ${activeTab === 'l2' ? 'active' : ''}`}
                    onClick={() => setActiveTab('l2')}
                >
                    L2 Footprint
                </button>
            </div>
          </div>
          <div className="chart-wrapper">
            {activeTab === 'standard' ? (
                <CandlestickChart 
                  bars={displayedBars} 
                  markers={filteredMarkers}
                  icebergs={filteredIcebergs}
                  onMarkerClick={handleMarkerClick}
                  onBarClick={setSelectedIntrabar}
                  selectedMarker={selectedMarker}
                  chartState={chartState}
                  onChartStateChange={handleChartStateChange}
                  priceRange={priceRange}
                  onPriceRangeChange={setPriceRange}
                  l2Data={l2Data} 
                />
            ) : (
                <FootprintChart 
                  bars={displayedBars} 
                  markers={filteredMarkers}
                  icebergs={filteredIcebergs}
                  onMarkerClick={handleMarkerClick}
                  selectedMarker={selectedMarker}
                  l2Data={l2Data}
                  chartState={chartState}
                  onChartStateChange={handleChartStateChange}
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
          {/* Intrabar Panel - shown when a bar is clicked */}
          {selectedIntrabar && runKey && (
            <IntrabarPanel
              runId={runKey.split(':')[0]}
              ticker={runKey.split(':')[1]}
              date={runKey.split(':')[2]}
              selectedBar={selectedIntrabar}
              onClose={() => setSelectedIntrabar(null)}
            />
          )}
        </section>
        
        {/* Right Panel - Decisions */}
        <aside className="card decision-panel">
          <div className="card-header">
            <span className="card-title">Decisions</span>
            <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>
              {decisionEvents.length} total
            </span>
          </div>
          <div className="card-body">
            <DecisionPanel 
              markers={decisionEvents}
              selectedMarker={selectedMarker}
              onSelectMarker={setSelectedMarker}
            />
          </div>
        </aside>
      </main>
      )}
    </div>
  );
}

export default App;
