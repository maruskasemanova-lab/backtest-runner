import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createChart } from "lightweight-charts";
import ChartTooltip from "./ChartTooltip";

const MAX_SNAP_SECONDS = 120;

const toUnixSeconds = (value) => {
  if (value === null || value === undefined) return null;
  if (typeof value === "number" && Number.isFinite(value)) {
    return value > 1e12 ? value / 1000 : value;
  }
  if (typeof value === "string") {
    const numeric = Number(value);
    if (Number.isFinite(numeric)) {
      return numeric > 1e12 ? numeric / 1000 : numeric;
    }
    const normalized = value.replace(/(\.\d{3})\d+/, "$1");
    const parsed = Date.parse(normalized);
    if (!Number.isNaN(parsed)) return parsed / 1000;
  }
  if (typeof value === "object" && value !== null) {
    if (typeof value.timestamp === "number") return value.timestamp;
    if (
      Number.isFinite(value.year) &&
      Number.isFinite(value.month) &&
      Number.isFinite(value.day)
    ) {
      return Date.UTC(value.year, value.month - 1, value.day) / 1000;
    }
  }
  return null;
};

const toIsoTimestamp = (value) => {
  const seconds = toUnixSeconds(value);
  if (!Number.isFinite(seconds)) return null;
  return new Date(seconds * 1000).toISOString();
};

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
          // Track wheel interaction for leader/follower sync
          // We don't have a clean 'wheel end' event, so we use a timeout
          isUserInteracting.current = true;
          if (interactionTimeoutRef.current) clearTimeout(interactionTimeoutRef.current);
          interactionTimeoutRef.current = setTimeout(() => {
               isUserInteracting.current = false;
          }, 200);

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


      // Interaction handlers to detect when we are the "Leader"
      const handleMouseDown = () => { isUserInteracting.current = true; };
      const handleMouseUp = () => { isUserInteracting.current = false; };
      const handleTouchStart = () => { isUserInteracting.current = true; };
      const handleTouchEnd = () => { isUserInteracting.current = false; };

      chartContainerRef.current.addEventListener('mousedown', handleMouseDown);
      chartContainerRef.current.addEventListener('mouseup', handleMouseUp);
      chartContainerRef.current.addEventListener('mouseleave', handleMouseUp);
      chartContainerRef.current.addEventListener('touchstart', handleTouchStart, { passive: true });
      chartContainerRef.current.addEventListener('touchend', handleTouchEnd);
      chartContainerRef.current.addEventListener('wheel', handleWheel, { passive: false });

      return () => {
        window.removeEventListener("resize", handleResize);
        if (chartContainerRef.current) {
             chartContainerRef.current.removeEventListener('wheel', handleWheel);
             chartContainerRef.current.removeEventListener('mousedown', handleMouseDown);
             chartContainerRef.current.removeEventListener('mouseup', handleMouseUp);
             chartContainerRef.current.removeEventListener('mouseleave', handleMouseUp);
             chartContainerRef.current.removeEventListener('touchstart', handleTouchStart);
             chartContainerRef.current.removeEventListener('touchend', handleTouchEnd);
        }
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

    // Use a ref to track if we are currently syncing from props to prevent loop
    const isSyncingRef = useRef(false);
    // Use a ref to track the last range we emitted to avoid processing our own echo
    const lastEmittedRangeRef = useRef(null);
    // Track if user is interacting to decouple state
    const isUserInteracting = useRef(false);
    const interactionTimeoutRef = useRef(null);

  const avgVolume = useMemo(
    () => bars.reduce((acc, bar) => acc + (bar?.volume || 0), 0) / (bars.length || 1),
    [bars]
  );

  const sortedBarTimes = useMemo(() => {
    if (!bars || bars.length === 0) return [];
    return bars
      .map((bar) => bar?.time)
      .filter((time) => Number.isFinite(time))
      .sort((a, b) => a - b);
  }, [bars]);

  const snapToleranceSeconds = useMemo(() => {
    if (sortedBarTimes.length < 2) return MAX_SNAP_SECONDS;
    let minSpacing = Number.POSITIVE_INFINITY;
    for (let i = 1; i < sortedBarTimes.length; i += 1) {
      const spacing = sortedBarTimes[i] - sortedBarTimes[i - 1];
      if (spacing > 0 && spacing < minSpacing) {
        minSpacing = spacing;
      }
    }
    if (!Number.isFinite(minSpacing)) return MAX_SNAP_SECONDS;
    return Math.max(MAX_SNAP_SECONDS, minSpacing);
  }, [sortedBarTimes]);

  const findClosestBarTime = useCallback((targetTime) => {
    if (!Number.isFinite(targetTime)) return null;
    if (!sortedBarTimes.length) return targetTime;

    let left = 0;
    let right = sortedBarTimes.length - 1;
    let closest = sortedBarTimes[0];
    let minDiff = Math.abs(targetTime - closest);

    while (left <= right) {
      const middle = Math.floor((left + right) / 2);
      const value = sortedBarTimes[middle];
      const diff = Math.abs(targetTime - value);
      if (diff < minDiff) {
        minDiff = diff;
        closest = value;
      }
      if (value < targetTime) {
        left = middle + 1;
      } else if (value > targetTime) {
        right = middle - 1;
      } else {
        return value;
      }
    }

    if (minDiff > snapToleranceSeconds) return null;
    return closest;
  }, [sortedBarTimes, snapToleranceSeconds]);

  const normalizeDecisionMarker = useCallback((marker, index) => {
    if (!marker) return null;

    const rawTime = toUnixSeconds(marker.time ?? marker.timestamp);
    if (!Number.isFinite(rawTime)) return null;

    const snappedTime = findClosestBarTime(rawTime);
    if (!Number.isFinite(snappedTime)) return null;

    return {
      ...marker,
      id: marker.id || `${marker.marker_type || "marker"}-${snappedTime}-${index}`,
      time: snappedTime,
      timestamp: marker.timestamp || toIsoTimestamp(rawTime) || toIsoTimestamp(snappedTime),
    };
  }, [findClosestBarTime]);

  const normalizedIcebergs = useMemo(() => {
    return (icebergs || [])
      .map((iceberg, index) => {
        const rawTime = toUnixSeconds(iceberg.time ?? iceberg.timestamp);
        if (!Number.isFinite(rawTime)) return null;

        const snappedTime = findClosestBarTime(rawTime);
        if (!Number.isFinite(snappedTime)) return null;

        const tradeSize = Number(iceberg.trade_size ?? 0);
        const hiddenSize = Number(iceberg.hidden_size ?? 0);
        const totalSize = tradeSize + hiddenSize;
        const price = Number(iceberg.price);
        const side = typeof iceberg.side === "string" ? iceberg.side.toLowerCase() : null;

        return {
          ...iceberg,
          id: iceberg.id || `iceberg-${snappedTime}-${index}`,
          marker_type: "iceberg_detected",
          time: snappedTime,
          timestamp: iceberg.timestamp || toIsoTimestamp(rawTime) || toIsoTimestamp(snappedTime),
          side,
          price: Number.isFinite(price) ? price : null,
          total_size: Number.isFinite(totalSize) ? totalSize : 0,
          title: iceberg.title || `Iceberg ${side ? side.toUpperCase() : "UNKNOWN"}`,
          description: iceberg.description || `Detected ${side || "unknown"} iceberg`,
          details: {
            ...(iceberg.details || {}),
            iceberg_side: side,
            iceberg_price: Number.isFinite(price) ? price : null,
            trade_size: tradeSize,
            hidden_size: hiddenSize,
            total_size: Number.isFinite(totalSize) ? totalSize : 0,
          },
        };
      })
      .filter(Boolean);
  }, [icebergs, findClosestBarTime]);

  const filteredIcebergMarkers = useMemo(() => {
    if (!normalizedIcebergs.length) return [];
    const minSize = avgVolume * 0.05;
    const byTime = new Map();

    normalizedIcebergs
      .filter((iceberg) => Number(iceberg.total_size || 0) > minSize)
      .forEach((iceberg) => {
        const current = byTime.get(iceberg.time);
        if (!current || Number(iceberg.total_size || 0) > Number(current.total_size || 0)) {
          byTime.set(iceberg.time, iceberg);
        }
      });

    return Array.from(byTime.values());
  }, [normalizedIcebergs, avgVolume]);

  const clickableMarkers = useMemo(() => {
    const decisions = (markers || [])
      .map((marker, index) => normalizeDecisionMarker(marker, index))
      .filter(Boolean);
    return [...decisions, ...filteredIcebergMarkers];
  }, [markers, normalizeDecisionMarker, filteredIcebergMarkers]);

  // Sync external chart state
  useEffect(() => {
      if (chartRef.current && chartState) {

          // If user is interacting, we are the LEADER. Ignore updates from followers.
          if (isUserInteracting.current) return;

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

    const targetTime = toUnixSeconds(selectedMarker.time ?? selectedMarker.timestamp);
    if (!Number.isFinite(targetTime)) return;

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
      const price = Number(selectedMarker.price);
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

    const markerTimeMap = new Map();
    clickableMarkers.forEach((marker) => {
      const key = Math.floor(Number(marker.time));
      if (!Number.isFinite(key)) return;
      const existing = markerTimeMap.get(key) || [];
      existing.push(marker);
      markerTimeMap.set(key, existing);
    });

    const resolveMarkerForClick = (param) => {
      const clickedTime = toUnixSeconds(param?.time);
      if (!Number.isFinite(clickedTime)) return null;

      const candidates = markerTimeMap.get(Math.floor(clickedTime));
      if (!candidates || candidates.length === 0) return null;
      if (candidates.length === 1) return candidates[0];

      const clickedPrice = param?.point && candleSeriesRef.current?.coordinateToPrice
        ? candleSeriesRef.current.coordinateToPrice(param.point.y)
        : null;

      if (!Number.isFinite(clickedPrice)) return candidates[0];

      const pricedCandidates = candidates.filter((candidate) => Number.isFinite(Number(candidate.price)));
      if (!pricedCandidates.length) return candidates[0];

      return pricedCandidates.reduce((best, candidate) => {
        const bestDiff = Math.abs(Number(best.price) - clickedPrice);
        const candidateDiff = Math.abs(Number(candidate.price) - clickedPrice);
        return candidateDiff < bestDiff ? candidate : best;
      }, pricedCandidates[0]);
    };

    const handleClick = (param) => {
      setTooltip((prev) => ({ ...prev, visible: false }));

      if (!param?.time || markerTimeMap.size === 0) return;

      const marker = resolveMarkerForClick(param);
      if (!marker) return;

      if (onMarkerClick) {
        onMarkerClick(marker);
      }

      const point = param.point;
      if (point && chartContainerRef.current) {
        const rect = chartContainerRef.current.getBoundingClientRect();
        setTooltip({
          visible: true,
          marker,
          x: point.x + rect.left,
          y: point.y + rect.top,
        });
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

      const validMarkerTypes = [
        "entry_executed",
        "exit_executed",
        "stop_loss_hit",
        "take_profit_hit",
        "regime_detected",
        "strategy_selected",
        "iceberg_detected",
      ];

      const finalMarkers = clickableMarkers
        .filter((m) => m && validMarkerTypes.includes(m.marker_type))
        .map((m) => {
          const time = m.time;
          let position = "aboveBar";
          let color = "#3b82f6";
          let shape = "circle";
          let text = "";

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
              const isMega = Number(m.total_size || 0) > (avgVolume * 3);
              
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
            size: 2,
          };
        })
        .sort((a, b) => a.time - b.time);

      candleSeriesRef.current.setMarkers(finalMarkers);
    } catch (err) {
      console.error("Chart markers update error:", err);
    }
  }, [clickableMarkers, bars, avgVolume]);


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
