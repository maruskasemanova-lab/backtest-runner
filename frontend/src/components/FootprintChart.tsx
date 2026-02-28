import { useEffect, useRef, useState, useCallback, useMemo } from "react";
import { createChart, ColorType } from "lightweight-charts";
import { toUnixSeconds } from "../utils";
import FootprintChartToolbar from "./FootprintChartToolbar";
import {
  buildChartMarkers,
  buildCvdData,
  buildMarkersByTime,
  buildValidChartBars,
  findFirstBarIndex,
  normalizeDecisionMarkers,
  normalizeIcebergMarkers,
  resolveClickedMarkerCandidate,
  resolveMarkerFocusedVisibleRange,
} from "./footprintChartUtils";


function FootprintChart({ bars, markers, icebergs, onMarkerClick, selectedMarker, l2Data, chartState, onChartStateChange, priceRange, onPriceRangeChange }) {
  const chartContainerRef = useRef(null);
  const chartRef = useRef(null);
  const candleSeriesRef = useRef(null);
  const cvdSeriesRef = useRef(null);
  const canvasRef = useRef(null);
  
  const [showCVD, setShowCVD] = useState(false);
  
  // Use refs for data to access latest in callbacks without re-binding
  const dataRef = useRef({ bars: [], l2Data: null });
  // Cache L2 Map to avoid rebuilding on every draw
  const l2MapRef = useRef(new Map());
  const lastL2DataRef = useRef(null);
  
  // Update refs when props change
  useEffect(() => {
    dataRef.current.bars = bars || [];
    dataRef.current.l2Data = l2Data;
    
    // Rebuild L2 map only when l2Data changes
    if (l2Data !== lastL2DataRef.current) {
      lastL2DataRef.current = l2Data;
      l2MapRef.current.clear();
      if (l2Data && l2Data.bars) {
        l2Data.bars.forEach(b => l2MapRef.current.set(Math.round(b.time), b));
      }
    }
  }, [bars, l2Data]);

  const normalizedDecisionMarkers = useMemo(() => {
    return normalizeDecisionMarkers(markers || []);
  }, [markers]);

  const normalizedIcebergMarkers = useMemo(() => {
    return normalizeIcebergMarkers(icebergs || []);
  }, [icebergs]);

  const clickableMarkers = useMemo(
    () => [...normalizedDecisionMarkers, ...normalizedIcebergMarkers],
    [normalizedDecisionMarkers, normalizedIcebergMarkers]
  );

  // Draw function definition - OPTIMIZED
  const drawFootprint = useCallback(() => {
      if(!chartRef.current || !candleSeriesRef.current || !canvasRef.current) return;
      
      const ctx = canvasRef.current.getContext('2d');
      const canvas = canvasRef.current;
      
      // Clear canvas
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      
      const bars = dataRef.current.bars;
      const l2Map = l2MapRef.current;
      
      if (!bars || bars.length === 0) return;

      // Get visible range
      const timeScale = chartRef.current.timeScale();
      const visibleRange = timeScale.getVisibleRange();
      if(!visibleRange) return;
      
      // Calculate bar width/spacing
      const barSpacing = timeScale.options().barSpacing;
      const series = candleSeriesRef.current;
      
      // Use binary search to find visible bar window
      const startIdx = Math.max(0, findFirstBarIndex(bars, visibleRange.from) - 1);
      const endIdx = Math.min(bars.length, findFirstBarIndex(bars, visibleRange.to) + 2);
      
      // Pre-calculate common values
      const drawWidth = Math.max(24, Math.min(barSpacing * 0.9, 120));
      const halfWidth = drawWidth / 2;
      const quarterWidth = drawWidth / 4;
      const fontSize = Math.max(10, Math.min(14, drawWidth / 3.5));
      const boxHeight = Math.max(14, fontSize + 4);
      const halfBoxHeight = boxHeight / 2;
      const showText = drawWidth >= 24;
      
      // Set font once for all text
      if (showText) {
        ctx.font = `bold ${Math.floor(fontSize)}px sans-serif`;
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
      }
      
      // Iterate only visible bars
      for (let i = startIdx; i < endIdx; i++) {
        const bar = bars[i];
        if (bar.time < visibleRange.from || bar.time > visibleRange.to) continue;
        
        const x = timeScale.timeToCoordinate(bar.time);
        if (x === null) continue;
        
        // Match L2 data
        let levels = bar.levels;
        if (!levels) {
          const tInt = Math.round(bar.time);
          const l2Bar = l2Map.get(tInt);
          if (l2Bar) levels = l2Bar.levels;
        }
        
        if (!levels) continue;
        
        // Draw footprint for this bar - INLINE for performance
        const levelKeys = Object.keys(levels);
        for (let j = 0; j < levelKeys.length; j++) {
          const price = levelKeys[j];
          const vol = levels[price];
          const y = series.priceToCoordinate(parseFloat(price));
          if (y === null) continue;
          
          // Sell background (Left) - red
          ctx.fillStyle = "rgba(220, 38, 38, 0.5)";
          ctx.fillRect(x - halfWidth, y - halfBoxHeight, halfWidth, boxHeight);
          
          // Buy background (Right) - green
          ctx.fillStyle = "rgba(22, 163, 74, 0.5)";
          ctx.fillRect(x, y - halfBoxHeight, halfWidth, boxHeight);
          
          // Text (no shadow for performance)
          if (showText) {
            ctx.fillStyle = "#ffffff";
            ctx.fillText(vol.sell || 0, x - quarterWidth, y);
            ctx.fillText(vol.buy || 0, x + quarterWidth, y);
          }
        }
      }
  }, []); // Stable callback

  // Initialize Chart
  useEffect(() => {
    if (!chartContainerRef.current) return;

    const chart = createChart(chartContainerRef.current, {
      width: chartContainerRef.current.clientWidth,
      height: chartContainerRef.current.clientHeight,
      layout: {
        background: { type: ColorType.Solid, color: "#1a1a1a" },
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
                lastEmittedRangeRef.current = range;
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

    // Hide canvas during interaction to prevent shaking
    // Show and redraw only after interaction stops
    let interactionTimeout = null;
    let rafId = null;
    
    const hideCanvas = () => {
        if (canvasRef.current) {
            canvasRef.current.style.opacity = '0';
        }
    };
    
    const showAndRedraw = () => {
        if (rafId) cancelAnimationFrame(rafId);
        rafId = requestAnimationFrame(() => {
            rafId = null;
            drawFootprint();
            if (canvasRef.current) {
                canvasRef.current.style.opacity = '1';
            }
        });
    };
    
    const onInteraction = () => {
        // Hide canvas immediately
        hideCanvas();
        // Clear any pending show
        if (interactionTimeout) clearTimeout(interactionTimeout);
        // Schedule show after interaction stops
        interactionTimeout = setTimeout(showAndRedraw, 75);
    };
    
    // Subscribe to chart events
    chart.timeScale().subscribeVisibleLogicalRangeChange(onInteraction);
    
    const handleResize = () => {
        if(chartContainerRef.current) {
            chart.applyOptions({
                width: chartContainerRef.current.clientWidth,
                height: chartContainerRef.current.clientHeight
            });
            if(canvasRef.current) {
                canvasRef.current.width = chartContainerRef.current.clientWidth;
                canvasRef.current.height = chartContainerRef.current.clientHeight;
            }
            onInteraction();
        }
    };
    window.addEventListener("resize", handleResize);

    // Cmd+Scroll for vertical price scale zoom
    const handleWheel = (e) => {
        // Track wheel interaction
        isUserInteracting.current = true;
        if (interactionTimeoutRef.current) clearTimeout(interactionTimeoutRef.current);
        interactionTimeoutRef.current = setTimeout(() => {
             isUserInteracting.current = false;
        }, 200);

        if (e.metaKey || e.ctrlKey) {
            e.preventDefault();
            const priceScale = chart.priceScale('right');
            const currentMargins = priceScale.options().scaleMargins || { top: 0.1, bottom: 0.1 };
            const delta = e.deltaY > 0 ? 0.02 : -0.02; // Zoom out / in
            const newTop = Math.max(0.02, Math.min(0.45, currentMargins.top + delta));
            const newBottom = Math.max(0.02, Math.min(0.45, currentMargins.bottom + delta));
            priceScale.applyOptions({
                scaleMargins: { top: newTop, bottom: newBottom }
            });
            if (onPriceRangeChange) {
                onPriceRangeChange({ top: newTop, bottom: newBottom });
            }
            onInteraction(); // Also trigger hide/show for vertical zoom
        }
    };
    chartContainerRef.current.addEventListener('wheel', handleWheel, { passive: false });

    // Interaction handlers
    const handleMouseDown = () => { isUserInteracting.current = true; };
    const handleMouseUp = () => { isUserInteracting.current = false; };
    const handleTouchStart = () => { isUserInteracting.current = true; };
    const handleTouchEnd = () => { isUserInteracting.current = false; };

    chartContainerRef.current.addEventListener('mousedown', handleMouseDown);
    chartContainerRef.current.addEventListener('mouseup', handleMouseUp);
    chartContainerRef.current.addEventListener('mouseleave', handleMouseUp);
    chartContainerRef.current.addEventListener('touchstart', handleTouchStart, { passive: true });
    chartContainerRef.current.addEventListener('touchend', handleTouchEnd);


    // Initial canvas setup
     if(canvasRef.current) {
         canvasRef.current.width = chartContainerRef.current.clientWidth;
         canvasRef.current.height = chartContainerRef.current.clientHeight;
         // REMOVED TRANSITION to prevent ghosting
         canvasRef.current.style.transition = 'none';
     }
     
    // Initial draw
    showAndRedraw();

    return () => {
        if (rafId) cancelAnimationFrame(rafId);
        if (interactionTimeout) clearTimeout(interactionTimeout);
        window.removeEventListener("resize", handleResize);
        if (chartContainerRef.current) {
            chartContainerRef.current.removeEventListener('wheel', handleWheel);
            chartContainerRef.current.removeEventListener('mousedown', handleMouseDown);
            chartContainerRef.current.removeEventListener('mouseup', handleMouseUp);
            chartContainerRef.current.removeEventListener('mouseleave', handleMouseUp);
            chartContainerRef.current.removeEventListener('touchstart', handleTouchStart);
            chartContainerRef.current.removeEventListener('touchend', handleTouchEnd);
        }
        chart.remove();
    };
  }, [drawFootprint, onPriceRangeChange]); // drawFootprint is stable

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

    // Use a ref to track the last range we emitted to avoid processing our own echo
    const lastEmittedRangeRef = useRef(null);
    // Track user interaction
    const isUserInteracting = useRef(false);
    const interactionTimeoutRef = useRef(null);

  // Sync external chart state
  useEffect(() => {
      if (chartRef.current && chartState) {
          // Check if this update is just an echo of what we just sent
          if (lastEmittedRangeRef.current) {
               const emitted = lastEmittedRangeRef.current;
               const isEcho = Math.abs(chartState.from - emitted.from) < 0.001 && 
                              Math.abs(chartState.to - emitted.to) < 0.001;
               if (isEcho) return;
          }

          const api = chartRef.current.timeScale();
          const current = api.getVisibleRange();
          
          
          const isSame = current && 
                         Math.abs(current.from - chartState.from) < 0.001 && 
                         Math.abs(current.to - chartState.to) < 0.001;
            
          // If we are interacting, we ignore external updates (Leader mode)
          if (!isSame && !isUserInteracting.current) {
              isSyncingRef.current = true;
              try {
                  api.setVisibleRange(chartState);
                  lastEmittedRangeRef.current = chartState;
              } catch(e) { /* ignore */ }
              finally {
                  isSyncingRef.current = false;
              }
          }
      }
  }, [chartState]);

  useEffect(() => {
      if (!chartRef.current || !priceRange) return;
      const top = Number(priceRange.top);
      const bottom = Number(priceRange.bottom);
      if (!Number.isFinite(top) || !Number.isFinite(bottom)) return;
      chartRef.current.priceScale('right').applyOptions({
          scaleMargins: { top, bottom }
      });
  }, [priceRange]);

  // Update Chart Data
  useEffect(() => {
      if(!candleSeriesRef.current || !bars) return;
      const validBars = buildValidChartBars(bars);

      if(validBars.length === 0) return;
      
      candleSeriesRef.current.setData(validBars);
      
      // Calculate and Set CVD Data
      if (cvdSeriesRef.current) {
          cvdSeriesRef.current.setData(buildCvdData(l2Data));
      }
      
      requestAnimationFrame(drawFootprint);
      
  }, [bars, l2Data, drawFootprint]);

  // Re-draw when l2Data changes
  useEffect(() => {
      requestAnimationFrame(drawFootprint);
  }, [l2Data, drawFootprint]);

  // Focus chart when a marker is selected from decisions.
  useEffect(() => {
      if (!chartRef.current || !selectedMarker || !bars || bars.length === 0) {
          return;
      }

      const visibleRange = resolveMarkerFocusedVisibleRange(bars, selectedMarker);
      if (!visibleRange) return;
      chartRef.current.timeScale().setVisibleRange(visibleRange);
  }, [selectedMarker, bars]);

  // Click marker in footprint chart -> select corresponding decision detail.
  useEffect(() => {
      if (!chartRef.current) return;

      const markersByTime = buildMarkersByTime(clickableMarkers);

      const handleClick = (param) => {
          if (!param?.time || markersByTime.size === 0) return;
          const clickedTime = toUnixSeconds(param.time);
          if (!Number.isFinite(clickedTime)) return;
          const candidates = markersByTime.get(Math.floor(clickedTime)) || [];
          const clickedPrice = param?.point && candleSeriesRef.current?.coordinateToPrice
              ? candleSeriesRef.current.coordinateToPrice(param.point.y)
              : null;
          const marker = resolveClickedMarkerCandidate(candidates, Number.isFinite(clickedPrice) ? clickedPrice : null);
          if (!marker) return;
          if (onMarkerClick) {
              onMarkerClick(marker);
          }
      };

      chartRef.current.subscribeClick(handleClick);
      return () => {
          try {
              if (chartRef.current) {
                  chartRef.current.unsubscribeClick(handleClick);
              }
          } catch (e) {
              // Ignore cleanup errors
          }
      };
  }, [clickableMarkers, onMarkerClick]);

  // Update markers
  useEffect(() => {
      if(!candleSeriesRef.current) return;
      try {
      candleSeriesRef.current.setMarkers(buildChartMarkers(clickableMarkers));
    } catch (err) {
      console.error("Chart markers update error:", err);
    }
  }, [clickableMarkers]);


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
            style={{ 
                position: 'absolute', 
                top: 0, 
                left: 0, 
                pointerEvents: 'none', 
                zIndex: 10,
                willChange: 'transform'
            }}
        />
        <FootprintChartToolbar
            showCVD={showCVD}
            onToggleCvd={() => setShowCVD((current) => !current)}
            onToggleFullscreen={toggleFullScreen}
        />
    </div>
  );
}

export default FootprintChart;
