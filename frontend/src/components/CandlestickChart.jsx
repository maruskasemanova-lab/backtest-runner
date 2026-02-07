import { useEffect, useRef, useState } from "react";
import { createChart } from "lightweight-charts";
import ChartTooltip from "./ChartTooltip";

function CandlestickChart({ bars, markers, icebergs, onMarkerClick, selectedMarker, chartState, onChartStateChange, l2Data, priceRange, onPriceRangeChange }) {
  const chartContainerRef = useRef(null);
  const chartRef = useRef(null);
  const candleSeriesRef = useRef(null);
  const volumeSeriesRef = useRef(null);
  const [error, setError] = useState(null);
  
  // Tooltip state
  const [tooltip, setTooltip] = useState({
    visible: false,
    marker: null,
    x: 0,
    y: 0
  });

  // Initialize chart
  useEffect(() => {
    if (!chartContainerRef.current) return;

    try {
      const getCssVar = (name, fallback) => {
        const value = getComputedStyle(document.documentElement)
          .getPropertyValue(name)
          .trim();
        return value || fallback;
      };

      const colors = {
        bg: getCssVar("--bg-card", "#ffffff"),
        grid: getCssVar("--border-color", "#e5e7eb"),
        text: getCssVar("--text-secondary", "#6b7280"),
        up: getCssVar("--candle-up", "#0f766e"),
        down: getCssVar("--candle-down", "#dc2626"),
        wick: getCssVar("--candle-wick", "#7c756b"),
        accent: getCssVar("--accent-blue", "#1d4ed8"),
      };

      const chart = createChart(chartContainerRef.current, {
        width: chartContainerRef.current.clientWidth,
        height: chartContainerRef.current.clientHeight,
        layout: {
          background: { type: "solid", color: colors.bg },
          textColor: colors.text,
        },
        grid: {
          vertLines: { color: colors.grid },
          horzLines: { color: colors.grid },
        },
        crosshair: {
          mode: 1,
          vertLine: {
            color: colors.text,
            width: 1,
            style: 2,
            labelBackgroundColor: colors.accent,
          },
          horzLine: {
            color: colors.text,
            width: 1,
            style: 2,
            labelBackgroundColor: colors.accent,
          },
        },
        rightPriceScale: {
          borderColor: colors.grid,
          scaleMargins: {
            top: 0.1,
            bottom: 0.2,
          },
        },
        timeScale: {
          borderColor: colors.grid,
          timeVisible: true,
          secondsVisible: false,
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

      // Candlestick series
      const candleSeries = chart.addCandlestickSeries({
        upColor: colors.up,
        downColor: colors.down,
        borderUpColor: colors.up,
        borderDownColor: colors.down,
        wickUpColor: colors.up,
        wickDownColor: colors.down,
      });

      // Volume series
      const volumeSeries = chart.addHistogramSeries({
        color: colors.accent,
        priceFormat: {
          type: "volume",
        },
        priceScaleId: "volume",
        scaleMargins: {
          top: 0.85,
          bottom: 0,
        },
      });

      // Configure volume price scale
      chart.priceScale("volume").applyOptions({
        scaleMargins: {
          top: 0.85,
          bottom: 0,
        },
        borderVisible: false,
      });

      chartRef.current = chart;
      candleSeriesRef.current = candleSeries;
      volumeSeriesRef.current = volumeSeries;

      // Handle resize
      const handleResize = () => {
        if (chartContainerRef.current && chartRef.current) {
          chartRef.current.applyOptions({
            width: chartContainerRef.current.clientWidth,
            height: chartContainerRef.current.clientHeight,
          });
        }
      };

      window.addEventListener("resize", handleResize);

      // Cmd+Scroll for vertical price scale zoom
      const handleWheel = (e) => {
          if (e.metaKey || e.ctrlKey) {
              e.preventDefault();
              const priceScale = chart.priceScale('right');
              const currentMargins = priceScale.options().scaleMargins || { top: 0.1, bottom: 0.2 };
              const delta = e.deltaY > 0 ? 0.02 : -0.02; // Zoom out / in
              const newTop = Math.max(0.02, Math.min(0.45, currentMargins.top + delta));
              const newBottom = Math.max(0.02, Math.min(0.45, currentMargins.bottom + delta));
              priceScale.applyOptions({
                  scaleMargins: { top: newTop, bottom: newBottom }
              });
              if (onPriceRangeChange) {
                  onPriceRangeChange({ top: newTop, bottom: newBottom });
              }
          }
      };
      chartContainerRef.current.addEventListener('wheel', handleWheel, { passive: false });

      return () => {
        window.removeEventListener("resize", handleResize);
        chartContainerRef.current?.removeEventListener('wheel', handleWheel);
        if (chartRef.current) {
          chartRef.current.remove();
          chartRef.current = null;
        }
      };

    } catch (err) {
      console.error("Chart initialization error:", err);
      setError(err.message);
    }
  }, []);

    // Keep a ref to bars for the event listener to access latest data without re-binding
    const barsRef = useRef(bars);
    useEffect(() => {
        barsRef.current = bars;
    }, [bars]);

    // Use a ref to track if we are currently syncing from props to prevent loop
    const isSyncingRef = useRef(false);
    // Use a ref to track the last range we emitted to avoid processing our own echo
    const lastEmittedRangeRef = useRef(null);

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
          
          // Basic equality check to avoid redundant sets
          const isSame = current && 
                         Math.abs(current.from - chartState.from) < 0.001 && 
                         Math.abs(current.to - chartState.to) < 0.001;

          if (!isSame) {
              isSyncingRef.current = true;
              try {
                  api.setVisibleRange(chartState);
                  // Update our last known state to match what we just set
                  // This prevents us from thinking the next user action is a jump if we just moved it
                  lastEmittedRangeRef.current = chartState;
              } catch(e) { 
                  // ignore errors if data not ready
              } finally {
                  // Reset flag immediately after
                  isSyncingRef.current = false;
              }
          }
      }
  }, [chartState]);

  // Update data when bars change
  useEffect(() => {
    if (!candleSeriesRef.current || !volumeSeriesRef.current) return;
    if (!bars || bars.length === 0) return;

    try {
      // Validate and deduplicate bars by time
      const seenTimes = new Set();
      const validBars = bars.filter((bar) => {
        if (!bar || typeof bar.time !== "number" || isNaN(bar.time))
          return false;
        if (seenTimes.has(bar.time)) return false;
        seenTimes.add(bar.time);
        return true;
      });

      if (validBars.length === 0) return;

      // Sort by time
      validBars.sort((a, b) => a.time - b.time);

      // Format bars for chart
      const candleData = validBars.map((bar) => ({
        time: bar.time,
        open: bar.open || 0,
        high: bar.high || 0,
        low: bar.low || 0,
        close: bar.close || 0,
      }));

      const volumeData = validBars.map((bar) => ({
        time: bar.time,
        value: bar.volume || 0,
        color:
          (bar.close || 0) >= (bar.open || 0)
            ? "rgba(34, 197, 94, 0.5)"
            : "rgba(239, 68, 68, 0.5)",
      }));

      candleSeriesRef.current.setData(candleData);
      volumeSeriesRef.current.setData(volumeData);

      // Auto-scroll to latest bar if no explicit state
      if (chartRef.current && !chartState) {
        chartRef.current.timeScale().scrollToPosition(0, false);
      }
    } catch (err) {
      console.error("Chart data update error:", err);
      setError(err.message);
    }
  }, [bars]);

  // Focus chart when a marker is selected from the decision list
  useEffect(() => {
    if (!chartRef.current || !selectedMarker || !bars || bars.length === 0) {
      return;
    }

    const targetTime = Math.floor(new Date(selectedMarker.timestamp).getTime() / 1000);
    if (!targetTime || Number.isNaN(targetTime)) return;

    // Find closest bar index to the selected marker time
    let closestIndex = -1;
    let closestDiff = Number.POSITIVE_INFINITY;
    for (let i = 0; i < bars.length; i += 1) {
      const barTime = bars[i]?.time;
      if (typeof barTime !== "number" || Number.isNaN(barTime)) continue;
      const diff = Math.abs(barTime - targetTime);
      if (diff < closestDiff) {
        closestDiff = diff;
        closestIndex = i;
      }
    }

    if (closestIndex === -1) return;

    const windowSize = 40;
    const fromIndex = Math.max(0, closestIndex - windowSize);
    const toIndex = Math.min(bars.length - 1, closestIndex + windowSize);
    const fromTime = bars[fromIndex]?.time;
    const toTime = bars[toIndex]?.time;

    if (fromTime && toTime && chartRef.current) {
      chartRef.current.timeScale().setVisibleRange({
        from: fromTime,
        to: toTime,
      });
    }

    // Show tooltip for the selected marker if coordinates are available
    try {
      const timeScale = chartRef.current.timeScale();
      const x = timeScale.timeToCoordinate
        ? timeScale.timeToCoordinate(targetTime)
        : null;
      const price = selectedMarker.price;
      const y = candleSeriesRef.current?.priceToCoordinate
        ? candleSeriesRef.current.priceToCoordinate(price)
        : null;
      if (
        x !== null &&
        y !== null &&
        chartContainerRef.current &&
        Number.isFinite(x) &&
        Number.isFinite(y)
      ) {
        const rect = chartContainerRef.current.getBoundingClientRect();
        setTooltip({
          visible: true,
          marker: selectedMarker,
          x: x + rect.left,
          y: y + rect.top,
        });
      }
    } catch (e) {
      // Ignore tooltip errors, focus is the priority
    }
  }, [selectedMarker, bars]);

  // Handle chart clicks and hover for tooltips
  useEffect(() => {
    if (!chartRef.current) return;

    // Build a marker lookup map ONCE per markers change (O(n) once, O(1) lookups)
    const markerTimeMap = new Map();
    if (markers && markers.length > 0) {
      markers.forEach(m => {
        const mTime = Math.floor(new Date(m.timestamp).getTime() / 1000);
        markerTimeMap.set(mTime, m);
      });
    }

    const handleClick = (param) => {
      if (!param.time || markerTimeMap.size === 0) return;
      const marker = markerTimeMap.get(param.time);
      if (marker && onMarkerClick) {
        onMarkerClick(marker.id);
      }
    };

    // Handle mouse move for tooltips - OPTIMIZED
    const handleCrosshairMove = (param) => {
      if (!param.time || markerTimeMap.size === 0) {
        setTooltip(prev => prev.visible ? { ...prev, visible: false } : prev);
        return;
      }

      const point = param.point;
      if (!point) {
        setTooltip(prev => prev.visible ? { ...prev, visible: false } : prev);
        return;
      }

      const marker = markerTimeMap.get(param.time);
      if (marker) {
        // Get rect ONCE, not twice
        const rect = chartContainerRef.current.getBoundingClientRect();
        setTooltip({
          visible: true,
          marker: marker,
          x: point.x + rect.left,
          y: point.y + rect.top
        });
      } else {
        setTooltip(prev => prev.visible ? { ...prev, visible: false } : prev);
      }
    };

    chartRef.current.subscribeClick(handleClick);
    chartRef.current.subscribeCrosshairMove(handleCrosshairMove);

    return () => {
      try {
        if (chartRef.current) {
          chartRef.current.unsubscribeClick(handleClick);
          chartRef.current.unsubscribeCrosshairMove(handleCrosshairMove);
        }
      } catch (e) {
        // Ignore cleanup errors
      }
    };
  }, [markers, onMarkerClick]);

  // Update markers (Decisions + Delta/CVD + Icebergs)
  useEffect(() => {
    if (!candleSeriesRef.current || !bars || bars.length === 0) return;

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
        ice_buy: "#00dbe3", // Svetlo modrá pre Support (Buy Iceberg)
        ice_sell: "#ff00d4", // Fialová/Magenta pre Rezistenciu (Sell Iceberg) - pre lepší kontrast
      };

      // 1. Calculate Dynamic Threshold for Icebergs
      // Zistíme priemerný volume z viditeľných barov, aby sme filtrovali šum.
      // Ak nemáme bars, použijeme hardcoded fallback.
      const avgVolume = bars.reduce((acc, bar) => acc + (bar.volume || 0), 0) / (bars.length || 1);
      // Iceberg musí byť aspoň 5% z priemerného volume sviečky (pôvodne 1.5x bolo príliš veľa)
      // avgVolume * 1.5 means iceberg > 150% of total candle volume -> IMPOSSIBLE
      // avgVolume * 0.05 means iceberg > 5% of total candle volume -> REASONABLE
      const ICEBERG_MIN_SIZE = avgVolume * 0.05; 
      
 

      const validMarkerTypes = [
        "entry_executed",
        "exit_executed",
        "stop_loss_hit",
        "take_profit_hit",
        "regime_detected",
        "strategy_selected",
        "iceberg_detected",
      ];
      
      // 2. Helper to snap timestamps to bars
      const barTimes = bars.map(b => b.time).sort((a,b) => a-b);
      const findClosestBarTime = (targetTime) => {
          if (!barTimes.length) return targetTime;
          // Binary search for speed
          let l = 0, r = barTimes.length - 1;
          let closest = barTimes[0];
          let minDiff = Math.abs(targetTime - closest);
          while (l <= r) {
              const m = Math.floor((l + r) / 2);
              const t = barTimes[m];
              const diff = Math.abs(targetTime - t);
              if (diff < minDiff) { minDiff = diff; closest = t; }
              if (t < targetTime) l = m + 1;
              else if (t > targetTime) r = m - 1;
              else return t;
          }
          // Ak je rozdiel väčší ako 2 minúty (120s), pravdepodobne to nepatrí k tejto sviečke
          if (minDiff > 120) return null;
          return closest;
      };

      // 3. Process Icebergs
      const processedIcebergs = (icebergs || []).map(ice => {
          let ts = ice.time;
          if (typeof ts === 'string') {
               // Fix pre formáty ako "2023-10-10T10:00:00.123456"
               const cleanIso = ts.replace(/(\.\d{3})\d+/, '$1'); 
               const parsed = Date.parse(cleanIso);
               if (!isNaN(parsed)) ts = parsed / 1000;
               else return null;
          } else if (!ts && ice.timestamp) {
              ts = new Date(ice.timestamp).getTime() / 1000;
          }
          if (!ts) return null;
          
          const time = findClosestBarTime(ts);
          if (time === null) return null;
          
          return { 
              ...ice, 
              time, 
              marker_type: "iceberg_detected",
              total_size: (ice.trade_size || 0) + (ice.hidden_size || 0)
          };
      })
      .filter(i => i !== null)
      // FILTER: Zobraz len významné icebergy (väčšie ako threshold)
      .filter(i => i.total_size > ICEBERG_MIN_SIZE);

      // Deduplicate: Ak je na jednej sviečke viac icebergov, zober ten najväčší
      const uniqueIcebergsMap = new Map();
      processedIcebergs.forEach(ice => {
          const existing = uniqueIcebergsMap.get(ice.time);
          if (!existing || (ice.total_size > existing.total_size)) {
              uniqueIcebergsMap.set(ice.time, ice);
          }
      });
      const uniqueIcebergs = Array.from(uniqueIcebergsMap.values());

      // 4. Merge Standard Markers
      const standardMarkers = (markers || []).map(m => {
           let ts = m.time;
           if (!ts && m.timestamp) ts = new Date(m.timestamp).getTime() / 1000;
           if (ts) {
               const snapped = findClosestBarTime(ts);
               if (snapped !== null) return { ...m, time: snapped };
           }
           return m;
      }).filter(m => m && m.time);

      const allMarkers = [...standardMarkers, ...uniqueIcebergs];

      // 5. Build Final Markers for Chart
      const finalMarkers = allMarkers
        .filter((m) => m && validMarkerTypes.includes(m.marker_type))
        .map((m) => {
          const time = m.time;
          let position = "aboveBar";
          let color = "#3b82f6";
          let shape = "circle";
          let text = "";
          let size = 1; // Default size multiplier if needed (chart lib handles shape size via text usually)

          switch (m.marker_type) {
            case "entry_executed":
              if (m.side === "long") {
                position = "belowBar"; color = palette.long; shape = "arrowUp"; text = "L";
              } else {
                position = "aboveBar"; color = palette.short; shape = "arrowDown"; text = "S";
              }
              break;
            case "exit_executed":
              position = m.side === "long" ? "aboveBar" : "belowBar";
              color = palette.neutral; shape = "circle"; text = "X";
              break;
            case "stop_loss_hit":
              position = m.side === "long" ? "belowBar" : "aboveBar"; // SL hit pre Long je sell order pod cenou? Zvycajne sa vizualizuje pri cene exitu.
              color = palette.short; shape = "circle"; text = "SL";
              break;
            case "take_profit_hit":
              position = m.side === "long" ? "aboveBar" : "belowBar";
              color = palette.long; shape = "circle"; text = "TP";
              break;
            
            // --- ICEBERG VISUALIZATION ---
            case "iceberg_detected":
              const isMega = m.total_size > (avgVolume * 3); // Extra veľký iceberg
              
              if (m.side === "buy") { 
                  // BUY ICEBERG = SUPPORT = POD SVIEČKOU
                  position = "belowBar"; 
                  color = palette.ice_buy;
                  shape = "arrowUp"; 
                  text = isMega ? "❄️" : "▲"; // Vločka len pre obrovské, inak šípka
              } else { 
                  // SELL ICEBERG = RESISTANCE = NAD SVIEČKOU
                  position = "aboveBar"; 
                  color = palette.ice_sell;
                  shape = "arrowDown"; 
                  text = isMega ? "❄️" : "▼"; 
              }
              break;
            case "regime_detected":
              position = "aboveBar";
              color = palette.blue;
              shape = "circle";
              text = m.regime || "R";
              break;
            case "strategy_selected":
              position = "belowBar";
              color = palette.amber;
              shape = "square";
              text = m.strategy?.substring(0, 3).toUpperCase() || "S";
              break;
          }

          return {
            time,
            position,
            color,
            shape,
            text,
            id: m.id || `${m.time}-${m.marker_type}`,
            size: 2, // Lightweight charts uses size differently based on version, usually text handles visual size
          };
        })
        .sort((a, b) => a.time - b.time);

      candleSeriesRef.current.setMarkers(finalMarkers);
    } catch (err) {
      console.error("Chart markers update error:", err);
    }
  }, [markers, icebergs, bars, l2Data]); // Added l2Data potentially but user provided bars.


  if (error) {
    return (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "var(--accent-red)",
          flexDirection: "column",
          gap: "1rem",
        }}
      >
        <span>⚠️ Chart Error</span>
        <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
          {error}
        </span>
      </div>
    );
  }

  return (
    <>
      <div ref={chartContainerRef} style={{ width: "100%", height: "100%" }} />
      <ChartTooltip
        marker={tooltip.marker}
        visible={tooltip.visible}
        x={tooltip.x}
        y={tooltip.y}
      />
    </>
  );
}

export default CandlestickChart;
