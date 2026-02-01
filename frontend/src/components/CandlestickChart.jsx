import { useEffect, useRef, useState } from 'react';
import { createChart } from 'lightweight-charts';

function CandlestickChart({ bars, markers, onMarkerClick }) {
  const chartContainerRef = useRef(null);
  const chartRef = useRef(null);
  const candleSeriesRef = useRef(null);
  const volumeSeriesRef = useRef(null);
  const [error, setError] = useState(null);
  
  // Initialize chart
  useEffect(() => {
    if (!chartContainerRef.current) return;
    
    try {
      const chart = createChart(chartContainerRef.current, {
        width: chartContainerRef.current.clientWidth,
        height: chartContainerRef.current.clientHeight,
        layout: {
          background: { type: 'solid', color: '#1e2128' },
          textColor: '#9aa0a6',
        },
        grid: {
          vertLines: { color: '#2a2e39' },
          horzLines: { color: '#2a2e39' },
        },
        crosshair: {
          mode: 1,
          vertLine: {
            color: '#5f6368',
            width: 1,
            style: 2,
            labelBackgroundColor: '#3b82f6',
          },
          horzLine: {
            color: '#5f6368',
            width: 1,
            style: 2,
            labelBackgroundColor: '#3b82f6',
          },
        },
        rightPriceScale: {
          borderColor: '#2a2e39',
          scaleMargins: {
            top: 0.1,
            bottom: 0.2,
          },
        },
        timeScale: {
          borderColor: '#2a2e39',
          timeVisible: true,
          secondsVisible: false,
        },
      });
      
      // Candlestick series
      const candleSeries = chart.addCandlestickSeries({
        upColor: '#22c55e',
        downColor: '#ef4444',
        borderUpColor: '#22c55e',
        borderDownColor: '#ef4444',
        wickUpColor: '#22c55e',
        wickDownColor: '#ef4444',
      });
      
      // Volume series
      const volumeSeries = chart.addHistogramSeries({
        color: '#3b82f6',
        priceFormat: {
          type: 'volume',
        },
        priceScaleId: 'volume',
        scaleMargins: {
          top: 0.85,
          bottom: 0,
        },
      });
      
      // Configure volume price scale
      chart.priceScale('volume').applyOptions({
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
      
      window.addEventListener('resize', handleResize);
      
      return () => {
        window.removeEventListener('resize', handleResize);
        if (chartRef.current) {
          chartRef.current.remove();
          chartRef.current = null;
        }
      };
    } catch (err) {
      console.error('Chart initialization error:', err);
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
      const validBars = bars.filter(bar => {
        if (!bar || typeof bar.time !== 'number' || isNaN(bar.time)) return false;
        if (seenTimes.has(bar.time)) return false;
        seenTimes.add(bar.time);
        return true;
      });
      
      if (validBars.length === 0) return;
      
      // Sort by time
      validBars.sort((a, b) => a.time - b.time);
      
      // Format bars for chart
      const candleData = validBars.map(bar => ({
        time: bar.time,
        open: bar.open || 0,
        high: bar.high || 0,
        low: bar.low || 0,
        close: bar.close || 0,
      }));
      
      const volumeData = validBars.map(bar => ({
        time: bar.time,
        value: bar.volume || 0,
        color: (bar.close || 0) >= (bar.open || 0) 
          ? 'rgba(34, 197, 94, 0.5)' 
          : 'rgba(239, 68, 68, 0.5)',
      }));
      
      candleSeriesRef.current.setData(candleData);
      volumeSeriesRef.current.setData(volumeData);
      
      // Auto-scroll to latest bar
      if (chartRef.current) {
        chartRef.current.timeScale().scrollToPosition(0, false);
      }
    } catch (err) {
      console.error('Chart data update error:', err);
      setError(err.message);
    }
  }, [bars]);
  
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
      const validMarkerTypes = [
        'entry_executed', 'exit_executed', 'stop_loss_hit', 
        'take_profit_hit', 'regime_detected', 'strategy_selected'
      ];
      
      const chartMarkers = markers
        .filter(m => m && validMarkerTypes.includes(m.marker_type))
        .map(m => {
          const time = Math.floor(new Date(m.timestamp).getTime() / 1000);
          
          let position = 'aboveBar';
          let color = '#3b82f6';
          let shape = 'circle';
          let text = '';
          
          switch (m.marker_type) {
            case 'entry_executed':
              position = m.side === 'long' ? 'belowBar' : 'aboveBar';
              color = '#22c55e';
              shape = 'arrowUp';
              text = 'BUY';
              break;
            case 'exit_executed':
            case 'stop_loss_hit':
              position = m.side === 'long' ? 'aboveBar' : 'belowBar';
              color = m.marker_type === 'stop_loss_hit' ? '#ef4444' : '#64748b';
              shape = 'arrowDown';
              text = m.marker_type === 'stop_loss_hit' ? 'SL' : 'EXIT';
              break;
            case 'take_profit_hit':
              position = m.side === 'long' ? 'aboveBar' : 'belowBar';
              color = '#22c55e';
              shape = 'arrowDown';
              text = 'TP';
              break;
            case 'regime_detected':
              position = 'aboveBar';
              color = '#3b82f6';
              shape = 'circle';
              text = m.regime || 'R';
              break;
            case 'strategy_selected':
              position = 'belowBar';
              color = '#8b5cf6';
              shape = 'square';
              text = m.strategy?.substring(0, 3).toUpperCase() || 'S';
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
        .filter(m => m.time && !isNaN(m.time))
        .sort((a, b) => a.time - b.time);
      
      candleSeriesRef.current.setMarkers(chartMarkers);
    } catch (err) {
      console.error('Chart markers update error:', err);
    }
  }, [markers]);
  
  if (error) {
    return (
      <div style={{ 
        width: '100%', 
        height: '100%', 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'center',
        color: 'var(--accent-red)',
        flexDirection: 'column',
        gap: '1rem'
      }}>
        <span>⚠️ Chart Error</span>
        <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{error}</span>
      </div>
    );
  }
  
  return (
    <div 
      ref={chartContainerRef} 
      style={{ width: '100%', height: '100%' }}
    />
  );
}

export default CandlestickChart;
