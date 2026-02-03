import { useEffect, useRef, useState } from "react";
import { createChart } from "lightweight-charts";
import ChartTooltip from "./ChartTooltip";

function CandlestickChart({ bars, markers, onMarkerClick, selectedMarker }) {
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

      return () => {
        window.removeEventListener("resize", handleResize);
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

      // Auto-scroll to latest bar
      if (chartRef.current) {
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

    const handleClick = (param) => {
      if (!param.time || !markers || markers.length === 0) return;

      const clickedTime = param.time;

      // Find marker at this time
      const marker = markers.find((m) => {
        const mTime = Math.floor(new Date(m.timestamp).getTime() / 1000);
        return mTime === clickedTime;
      });

      if (marker && onMarkerClick) {
        onMarkerClick(marker.id);
      }
    };

    // Handle mouse move for tooltips
    const handleCrosshairMove = (param) => {
      if (!param.time || !markers || markers.length === 0) {
        setTooltip(prev => ({ ...prev, visible: false }));
        return;
      }

      const hoveredTime = param.time;
      const point = param.point;
      
      if (!point) {
        setTooltip(prev => ({ ...prev, visible: false }));
        return;
      }

      // Find marker at this time
      const marker = markers.find((m) => {
        const mTime = Math.floor(new Date(m.timestamp).getTime() / 1000);
        return mTime === hoveredTime;
      });

      if (marker) {
        setTooltip({
          visible: true,
          marker: marker,
          x: point.x + chartContainerRef.current.getBoundingClientRect().left,
          y: point.y + chartContainerRef.current.getBoundingClientRect().top
        });
      } else {
        setTooltip(prev => ({ ...prev, visible: false }));
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

  // Update markers
  useEffect(() => {
    if (!candleSeriesRef.current) return;
    if (!markers || markers.length === 0) {
      try {
        candleSeriesRef.current.setMarkers([]);
      } catch (e) {}
      return;
    }

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
      };

      const validMarkerTypes = [
        "entry_executed",
        "exit_executed",
        "stop_loss_hit",
        "take_profit_hit",
        "regime_detected",
        "strategy_selected",
      ];

      const chartMarkers = markers
        .filter((m) => m && validMarkerTypes.includes(m.marker_type))
        .map((m) => {
          const time = Math.floor(new Date(m.timestamp).getTime() / 1000);

          let position = "aboveBar";
          let color = "#3b82f6";
          let shape = "circle";
          let text = "";

          switch (m.marker_type) {
            case "entry_executed":
              // Entry: Long = BUY (below bar, green), Short = SELL (above bar, red)
              if (m.side === "long") {
                position = "belowBar";
                color = palette.long;
                shape = "arrowUp";
                text = "BUY";
              } else {
                position = "aboveBar";
                color = palette.short;
                shape = "arrowDown";
                text = "SELL";
              }
              break;
            case "exit_executed":
            case "stop_loss_hit":
              // Exit: Long position closed = SELL (above bar), Short position closed = BUY (below bar)
              if (m.side === "long") {
                position = "aboveBar";
                color = m.marker_type === "stop_loss_hit" ? palette.short : palette.neutral;
                shape = "arrowDown";
                text = m.marker_type === "stop_loss_hit" ? "SL" : "SELL";
              } else {
                position = "belowBar";
                color = m.marker_type === "stop_loss_hit" ? palette.short : palette.neutral;
                shape = "arrowUp";
                text = m.marker_type === "stop_loss_hit" ? "SL" : "BUY";
              }
              break;
            case "take_profit_hit":
              // Take profit: Long position = SELL (above bar), Short position = BUY (below bar)
              if (m.side === "long") {
                position = "aboveBar";
                color = palette.long;
                shape = "arrowDown";
                text = "TP";
              } else {
                position = "belowBar";
                color = palette.long;
                shape = "arrowUp";
                text = "TP";
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
            id: m.id,
          };
        })
        .filter((m) => m.time && !isNaN(m.time))
        .sort((a, b) => a.time - b.time);

      candleSeriesRef.current.setMarkers(chartMarkers);
    } catch (err) {
      console.error("Chart markers update error:", err);
    }
  }, [markers]);

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
