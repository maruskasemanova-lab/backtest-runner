import { useEffect, useRef, useState, useCallback } from "react";
import { createChart } from "lightweight-charts";

function FootprintChart({ bars, markers, icebergs, onMarkerClick, selectedMarker, l2Data, chartState, onChartStateChange, priceRange, onPriceRangeChange }) {
  const chartContainerRef = useRef(null);
  const chartRef = useRef(null);
  const candleSeriesRef = useRef(null);
  const cvdSeriesRef = useRef(null);
  const canvasRef = useRef(null);
  
  const [showCVD, setShowCVD] = useState(false);
  
  // Use refs for data to access latest in callbacks without re-binding
  const dataRef = useRef({ bars: [], l2Data: null });
  
  // Update refs when props change
  useEffect(() => {
    dataRef.current.bars = bars || [];
    dataRef.current.l2Data = l2Data;
  }, [bars, l2Data]);

  // Draw function definition
  const drawFootprint = useCallback(() => {
      if(!chartRef.current || !candleSeriesRef.current || !canvasRef.current) return;
      
      const ctx = canvasRef.current.getContext('2d');
      const canvas = canvasRef.current;
      
      // Clear canvas
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      
      const bars = dataRef.current.bars;
      const l2 = dataRef.current.l2Data;
      
      if (!bars || bars.length === 0) return;

      // Get visible range
      const timeScale = chartRef.current.timeScale();
      const visibleRange = timeScale.getVisibleRange();
      if(!visibleRange) return;
      
      // Calculate bar width/spacing
      const barSpacing = timeScale.options().barSpacing;
      
      // L2 Lookup Map (Integer keys for stability)
      const l2Map = new Map();
      if (l2 && l2.bars) {
          l2.bars.forEach(b => l2Map.set(Math.round(b.time), b));
      }
      
      // Iterate visible bars
      bars.forEach((bar) => {
          if (bar.time < visibleRange.from || bar.time > visibleRange.to) return;
          
          const x = timeScale.timeToCoordinate(bar.time);
          if (x === null) return;
          
          // Match L2 data
          let levels = bar.levels;
          if (!levels) {
             const tInt = Math.round(bar.time);
             if (l2Map.has(tInt)) {
                 levels = l2Map.get(tInt).levels;
             }
          }
          
          if(levels) {
               drawBarFootprint(ctx, x, { ...bar, levels }, barSpacing, candleSeriesRef.current);
          }
      });
  }, []); // Stable callback

  const drawBarFootprint = (ctx, x, bar, barWidth, series) => {
      // Dynamic width, allow growth up to 120px for better readability on zoom
      const drawWidth = Math.max(24, Math.min(barWidth * 0.9, 120));
      
      // Font size scaling
      const fontSize = Math.max(10, Math.min(14, drawWidth / 3.5));
      
      Object.entries(bar.levels).forEach(([price, vol]) => {
          const y = series.priceToCoordinate(parseFloat(price));
          if(y === null) return;
          
          const boxHeight = Math.max(14, fontSize + 4); 
          
          // Backgrounds
          // Sell (Left)
          ctx.fillStyle = "rgba(220, 38, 38, 0.5)"; 
          ctx.fillRect(x - drawWidth/2, y - boxHeight/2, drawWidth/2, boxHeight);
          
          // Buy (Right)
          ctx.fillStyle = "rgba(22, 163, 74, 0.5)"; 
          ctx.fillRect(x, y - boxHeight/2, drawWidth/2, boxHeight);
          
          // Text
          // Always draw text if width permits (threshold 24px)
          if (drawWidth >= 24) {
              ctx.fillStyle = "#ffffff";
              ctx.font = `bold ${Math.floor(fontSize)}px sans-serif`;
              ctx.textAlign = "center";
              ctx.textBaseline = "middle";
              // Shadow for readability
              ctx.shadowColor = "rgba(0,0,0,0.8)";
              ctx.shadowBlur = 2;
              
              const sellVol = vol.sell || 0;
              const buyVol = vol.buy || 0;
              
              ctx.fillText(sellVol, x - drawWidth/4, y);
              ctx.fillText(buyVol, x + drawWidth/4, y);
              
              // Reset shadow
              ctx.shadowBlur = 0;
          }
      });
  };

  // Initialize Chart
  useEffect(() => {
    if (!chartContainerRef.current) return;

    const chart = createChart(chartContainerRef.current, {
      width: chartContainerRef.current.clientWidth,
      height: chartContainerRef.current.clientHeight,
      layout: {
        background: { type: "solid", color: "#1a1a1a" },
        textColor: "#d1d5db",
      },
      grid: {
        vertLines: { color: "#333", visible: false }, 
        horzLines: { color: "#333", visible: false },
      },
      timeScale: {
        timeVisible: true,
        secondsVisible: false,
      },
      rightPriceScale: {
          scaleMargins: {
              top: 0.1,
              bottom: 0.1,
          },
      },
    });

    // Subscribe to range changes
    if (onChartStateChange) {
        chart.timeScale().subscribeVisibleTimeRangeChange((range) => {
            if (range && !isSyncingRef.current) {
                onChartStateChange(range);
            }
        });
    }

    const candleSeries = chart.addCandlestickSeries({
      upColor: "rgba(0,0,0,0)", // Transparent candles
      downColor: "rgba(0,0,0,0)", 
      borderVisible: true,
      wickVisible: true,
      borderUpColor: "#26a69a",
      borderDownColor: "#ef5350",
      wickUpColor: "#26a69a",
      wickDownColor: "#ef5350", 
    });

    // Add CVD Series (Histogram) - Initially invisible if needed, or we toggle visibility
    const cvdSeries = chart.addHistogramSeries({
        color: '#26a69a',
        priceFormat: {
            type: 'volume',
        },
        priceScaleId: 'cvd', // Separate scale
    });
    
    // Configure CVD Scale (Overlay or bottom pane?)
    // Let's put it on the left or just overlay with transparency at bottom
    chart.priceScale('cvd').applyOptions({
        scaleMargins: {
            top: 0.7, // Push to bottom 30%
            bottom: 0,
        },
        visible: false, // Hide axis
    });

    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;
    cvdSeriesRef.current = cvdSeries;

    // React to time scale changes (scroll/zoom)
    let frameId;
    const renderLoop = () => {
        drawFootprint();
        frameId = requestAnimationFrame(renderLoop);
    };
    frameId = requestAnimationFrame(renderLoop);
    
    const handleResize = () => {
        if(chartContainerRef.current) {
            chart.applyOptions({
                width: chartContainerRef.current.clientWidth,
                height: chartContainerRef.current.clientHeight
            });
            if(canvasRef.current) {
                canvasRef.current.width = chartContainerRef.current.clientWidth;
                canvasRef.current.height = chartContainerRef.current.clientHeight;
                // drawFootprint handled by loop
            }
        }
    };
    window.addEventListener("resize", handleResize);

    // Initial canvas setup
     if(canvasRef.current) {
         canvasRef.current.width = chartContainerRef.current.clientWidth;
         canvasRef.current.height = chartContainerRef.current.clientHeight;
     }

    return () => {
        cancelAnimationFrame(frameId);
        window.removeEventListener("resize", handleResize);
        chart.remove();
    };
  }, [drawFootprint]); // drawFootprint is stable

  // Update CVD Visibility
  useEffect(() => {
      if (cvdSeriesRef.current) {
          cvdSeriesRef.current.applyOptions({
              visible: showCVD
          });
      }
  }, [showCVD]);

    // Use a ref to track if we are currently syncing from props to prevent loop
    const isSyncingRef = useRef(false);

  // Sync external chart state
  useEffect(() => {
      if (chartRef.current && chartState) {
          const api = chartRef.current.timeScale();
          const current = api.getVisibleRange();
          
          const isSame = current && 
                         Math.abs(current.from - chartState.from) < 0.001 && 
                         Math.abs(current.to - chartState.to) < 0.001;

          if (!isSame) {
              isSyncingRef.current = true;
              try {
                  api.setVisibleRange(chartState);
              } catch(e) { /* ignore */ }
              finally {
                  isSyncingRef.current = false;
              }
          }
      }
  }, [chartState]);

  // Update Chart Data
  useEffect(() => {
      if(!candleSeriesRef.current || !bars) return;
      
      // Dedupe and sort
      const seenTimes = new Set();
      const validBars = bars.filter((bar) => {
        if (!bar || typeof bar.time !== "number" || isNaN(bar.time)) return false;
        if (seenTimes.has(bar.time)) return false;
        seenTimes.add(bar.time);
        return true;
      }).sort((a, b) => a.time - b.time);

      if(validBars.length === 0) return;
      
      candleSeriesRef.current.setData(validBars);
      
      // Calculate and Set CVD Data
      if (cvdSeriesRef.current && l2Data && l2Data.bars) {
          let cumDelta = 0;
          // Sort L2 bars
          const sortedL2 = [...l2Data.bars].sort((a,b) => a.time - b.time);
          
          const cvdData = sortedL2.map(b => {
             cumDelta += (b.delta || 0);
             return {
                 time: b.time,
                 value: cumDelta,
                 color: cumDelta >= 0 ? 'rgba(38, 166, 154, 0.4)' : 'rgba(239, 83, 80, 0.4)'
             };
          });
          
          cvdSeriesRef.current.setData(cvdData);
      }
      
      requestAnimationFrame(drawFootprint);
      
  }, [bars, l2Data, drawFootprint]);

  // Re-draw when l2Data changes
  useEffect(() => {
      requestAnimationFrame(drawFootprint);
  }, [l2Data, drawFootprint]);

  // Update markers
  useEffect(() => {
      if(!candleSeriesRef.current) return;
      try {
      const getCssVar = (name, fallback) => {
        const value = getComputedStyle(document.documentElement)
          .getPropertyValue(name)
          .trim();
        return value || fallback;
      };
      const palette = {
        long: getCssVar("--accent-green", "#0f766e"),
        short: getCssVar("--accent-red", "#dc2626"),
        neutral: "#475569",
        blue: getCssVar("--accent-blue", "#1d4ed8"),
        amber: getCssVar("--accent-amber", "#f59e0b"),
        ice: "#00dbe3", // Iceberg Cyan
      };
      
       const validMarkerTypes = [
        "entry_executed", "exit_executed", "stop_loss_hit", "take_profit_hit", "regime_detected", "strategy_selected", "iceberg_detected"
      ];

      // Merge standard markers and icebergs (if any)
      // Icebergs need to be formatted to resemble markers if they aren't already
      const icebergMarkers = (icebergs || []).map(ice => ({
          ...ice,
          marker_type: "iceberg_detected",
          timestamp: ice.time // ensure timestamp field
      }));
      
      const allMarkers = [...(markers || []), ...icebergMarkers];

      const chartMarkers = allMarkers
        .filter((m) => m && validMarkerTypes.includes(m.marker_type))
        .map((m) => {
          // Robust timestamp handling
          let ts = m.time;
          if (!ts && m.timestamp) {
              ts = new Date(m.timestamp).getTime() / 1000;
          }
          if (!ts) return null;
          
          const time = Math.floor(ts);
          let position = "aboveBar", color = "#3b82f6", shape = "circle", text = "";
          
            switch (m.marker_type) {
            case "entry_executed":
              if (m.side === "long") { position = "belowBar"; color = palette.long; shape = "arrowUp"; text = "BUY"; } 
              else { position = "aboveBar"; color = palette.short; shape = "arrowDown"; text = "SELL"; }
              break;
            case "exit_executed":
            case "stop_loss_hit":
              if (m.side === "long") { position = "aboveBar"; color = m.marker_type === "stop_loss_hit" ? palette.short : palette.neutral; shape = "arrowDown"; text = m.marker_type === "stop_loss_hit" ? "SL" : "SELL"; } 
              else { position = "belowBar"; color = m.marker_type === "stop_loss_hit" ? palette.short : palette.neutral; shape = "arrowUp"; text = m.marker_type === "stop_loss_hit" ? "SL" : "BUY"; }
              break;
            case "take_profit_hit":
               position = m.side === "long" ? "aboveBar" : "belowBar"; color = palette.long; shape = m.side === "long" ? "arrowDown" : "arrowUp"; text = "TP";
              break;
            case "regime_detected":
              position = "aboveBar"; color = palette.blue; shape = "circle"; text = m.regime || "R";
              break;
            case "strategy_selected":
              position = "belowBar"; shape = "square"; text = (m.strategy || "UNK").substring(0,3).toUpperCase();
               const hash = (m.strategy || "").split("").reduce((a,c)=>a+c.charCodeAt(0),0);
               color = `hsl(${hash % 360}, 70%, 50%)`;
              break;
            case "iceberg_detected":
              // Icebergs: Show near price. LightWeightCharts markers are 'aboveBar', 'belowBar', or 'inBar'.
              // 'inBar' is not standard.
              // We'll use above/below based on side.
              // Buying Iceberg (Aggressor Buy hidden?) - Wait, logic:
              // Side A (Ask) -> Buyer hit Sell Iceberg.
              // Side B (Bid) -> Seller hit Buy Iceberg.
              
              if (m.side === "buy") { 
                  // Buyer hit Ask. Iceberg was on Ask (Sell side).
                  position = "aboveBar"; 
                  color = palette.ice; 
                  shape = "arrowDown"; 
                  text = "❄️"; 
              } else { 
                  // Seller hit Bid. Iceberg was on Bid (Buy side).
                  position = "belowBar"; 
                  color = palette.ice; 
                  shape = "arrowUp"; 
                  text = "❄️"; 
              }
              break;
          }
           return { time, position, color, shape, text, id: m.id || `${m.time}-${m.price}` };
        })
        .filter((m) => m && m.time && !isNaN(m.time))
        .sort((a, b) => a.time - b.time);

      candleSeriesRef.current.setMarkers(chartMarkers);
    } catch (err) {
      console.error("Chart markers update error:", err);
    }
  }, [markers, icebergs]);


  // Fullscreen Logic
  const containerRef = useRef(null); // Wrapper div
  
  const toggleFullScreen = () => {
      if (!containerRef.current) return;
      if (!document.fullscreenElement) {
          containerRef.current.requestFullscreen().catch(err => {
              console.error(`Error attempting to enable full-screen mode: ${err.message} (${err.name})`);
          });
      } else {
          document.exitFullscreen();
      }
  };

  return (
    <div ref={containerRef} style={{ position: 'relative', width: '100%', height: '100%', background: '#1a1a1a' }}>
        <div ref={chartContainerRef} style={{ width: '100%', height: '100%' }} />
        <canvas 
            ref={canvasRef} 
            style={{ position: 'absolute', top: 0, left: 0, pointerEvents: 'none', zIndex: 10 }}
        />
        <div style={{
            position: 'absolute',
            top: '10px',
            right: '60px',
            zIndex: 20,
            display: 'flex',
            gap: '8px'
        }}>
             <button
                onClick={() => setShowCVD(!showCVD)}
                style={{
                    background: showCVD ? 'rgba(38, 166, 154, 0.6)' : 'rgba(255, 255, 255, 0.1)',
                    border: '1px solid rgba(255, 255, 255, 0.2)',
                    color: '#fff',
                    borderRadius: '4px',
                    padding: '4px 8px',
                    cursor: 'pointer',
                    fontSize: '12px',
                    fontWeight: 'bold'
                }}
                title="Toggle Accum. Delta (CVD)"
            >
                CVD
            </button>
            <button
                onClick={toggleFullScreen}
                style={{
                    background: 'rgba(255, 255, 255, 0.1)',
                    border: '1px solid rgba(255, 255, 255, 0.2)',
                    color: '#fff',
                    borderRadius: '4px',
                    padding: '4px 8px',
                    cursor: 'pointer',
                    fontSize: '16px',
                }}
                title="Toggle Fullscreen"
            >
                ⛶
            </button>
        </div>
    </div>
  );
}

export default FootprintChart;
