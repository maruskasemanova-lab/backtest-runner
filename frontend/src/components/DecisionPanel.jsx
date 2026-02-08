import { useEffect, useMemo, useRef, useState } from "react";

const DECISION_MARKER_TYPES = new Set([
  'entry_executed',
  'exit_executed',
  'stop_loss_hit',
  'take_profit_hit',
  'signal_generated',
  'pattern_detected',
  'trailing_stop_updated',
]);

const isDecisionMarker = (marker) => DECISION_MARKER_TYPES.has(marker?.marker_type);

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
    const parsed = Date.parse(value);
    if (!Number.isNaN(parsed)) return parsed / 1000;
  }
  return null;
};

const formatGenericValue = (value) => {
  if (value === null || value === undefined) return 'n/a';
  if (typeof value === 'number') {
    if (!Number.isFinite(value)) return 'n/a';
    return Number.isInteger(value) ? String(value) : value.toFixed(4);
  }
  if (typeof value === 'boolean') return value ? 'true' : 'false';
  if (Array.isArray(value)) {
    if (!value.length) return '[]';
    return value.map((item) => {
      if (typeof item === 'object' && item !== null) return JSON.stringify(item);
      return String(item);
    }).join(', ');
  }
  if (typeof value === 'object') {
    const entries = Object.entries(value);
    if (!entries.length) return '{}';
    return entries
      .slice(0, 10)
      .map(([k, v]) => `${k}: ${formatGenericValue(v)}`)
      .join(' | ');
  }
  return String(value);
};

// Recursive function to render values (from ChartTooltip)
const renderValue = (val, keyPrefix = '') => {
  if (val === null || val === undefined) return 'N/A';
  
  if (typeof val === 'object' && !Array.isArray(val)) {
    if (Object.keys(val).length === 0) return '{}';
    
    return (
      <div className="object-container" style={{ marginLeft: '10px', borderLeft: '2px solid rgba(15, 23, 42, 0.1)', paddingLeft: '8px' }}>
        {Object.entries(val).map(([k, v]) => (
          <div key={`${keyPrefix}-${k}`} className="object-row" style={{ marginTop: '4px' }}>
            <span className="object-key" style={{ fontWeight: 500, color: 'var(--text-secondary)', fontSize: '0.85em' }}>{k}:</span>
            <div className="nested-object">
              {renderValue(v, `${keyPrefix}-${k}`)}
            </div>
          </div>
        ))}
      </div>
    );
  }
  
  if (Array.isArray(val)) {
    if (val.length === 0) return '[]';
    return (
      <div className="object-container" style={{ marginLeft: '10px', borderLeft: '2px solid rgba(15, 23, 42, 0.1)', paddingLeft: '8px' }}>
        {val.map((v, i) => (
           <div key={`${keyPrefix}-${i}`} className="object-row" style={{ marginTop: '4px' }}>
            <span className="object-key" style={{ fontWeight: 500, color: 'var(--text-secondary)', fontSize: '0.85em' }}>[{i}]:</span>
             <div className="nested-object">
               {renderValue(v, `${keyPrefix}-${i}`)}
             </div>
           </div>
        ))}
      </div>
    );
  }
  
  if (typeof val === 'number') {
    return <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.9em' }}>{Math.abs(val) < 0.01 ? val.toFixed(6) : val.toFixed(4)}</span>;
  }
  
  return <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.9em' }}>{String(val)}</span>;
};

function DecisionPanel({ markers, selectedMarker, onSelectMarker }) {
  const [detailTab, setDetailTab] = useState('details');
  const [listTab, setListTab] = useState('decisions');
  const itemRefs = useRef(new Map());

  useEffect(() => {
    setDetailTab('details');
  }, [selectedMarker?.id, selectedMarker?.timestamp, selectedMarker?.time]);

  useEffect(() => {
    if (!selectedMarker) return;
    setListTab(isDecisionMarker(selectedMarker) ? 'decisions' : 'events');
  }, [selectedMarker?.id, selectedMarker?.timestamp, selectedMarker?.time, selectedMarker?.marker_type]);

  // Format time
  const formatTime = (timestamp) => {
    if (!timestamp) return 'N/A';
    const date = new Date(timestamp);
    if (Number.isNaN(date.getTime())) return 'N/A';
    return date.toLocaleTimeString('en-US', { 
      hour: '2-digit', 
      minute: '2-digit',
      second: '2-digit',
      hour12: false 
    });
  };

  const formatPrice = (value) => {
    const number = Number(value);
    return Number.isFinite(number) ? `$${number.toFixed(2)}` : 'N/A';
  };

  const getMarkerKey = (marker, idx = 0) => {
    return marker.id || `${marker.marker_type || 'marker'}-${marker.timestamp || marker.time || 'na'}-${idx}`;
  };

  const isSameMarker = (a, b) => {
    if (!a || !b) return false;
    if (a.id && b.id && a.id === b.id) return true;
    return (
      String(a.marker_type || '') === String(b.marker_type || '') &&
      String(a.timestamp || '') === String(b.timestamp || '') &&
      String(a.time || '') === String(b.time || '') &&
      Number(a.price ?? NaN) === Number(b.price ?? NaN)
    );
  };
  
  // Get marker icon (context-aware: TP with net loss shows red)
  const getMarkerIcon = (marker) => {
    const markerType = marker.marker_type;
    // If take-profit but after costs it's a loss, show red icon
    if (markerType === 'take_profit_hit' && marker.details?.pnl_pct !== undefined && marker.details.pnl_pct <= 0) {
      return '🔴';
    }
    const icons = {
      regime_detected: '🎯',
      strategy_selected: '📋',
      signal_generated: '📊',
      pattern_detected: '🕯️',
      entry_executed: '🟢',
      exit_executed: '⚪',
      stop_loss_hit: '🔴',
      take_profit_hit: '💰',
      iceberg_detected: '❄️',
      trailing_stop_updated: '📍',
      session_started: '🏁',
      session_ended: '🏆',
    };
    return icons[markerType] || '📌';
  };

  const renderTitle = (marker) => {
    if (marker.marker_type === 'take_profit_hit' && marker.details?.pnl_pct !== undefined && marker.details.pnl_pct <= 0) {
      return `${marker.title || 'Take Profit'} (net loss)`;
    }
    return marker.title || marker.marker_type || 'Decision';
  };

  const formatExitMetrics = (marker) => {
    if (!['exit_executed', 'stop_loss_hit', 'take_profit_hit'].includes(marker.marker_type)) {
      return null;
    }
    const details = marker.details || {};
    const pnlPct = details.pnl_pct;
    const pnlUsd = details.pnl_usd ?? details.pnl_dollars;
    const costUsd = details.cost_usd ?? details.costs?.total;
    const costPct = details.cost_pct;
    const barsHeld = details.bars_held;

    const parts = [];
    if (pnlPct != null || pnlUsd != null) {
      const pctText = pnlPct != null ? `${pnlPct >= 0 ? '+' : ''}${Number(pnlPct).toFixed(2)}%` : "n/a";
      const usdText = pnlUsd != null ? `${Number(pnlUsd) >= 0 ? '+' : ''}$${Number(pnlUsd).toFixed(2)}` : "n/a";
      parts.push(`PnL: ${pctText} (${usdText})`);
    }
    if (costUsd != null) {
      const costUsdText = `$${Number(costUsd).toFixed(2)}`;
      const costPctText = costPct != null ? ` (${Number(costPct).toFixed(2)}%)` : '';
      parts.push(`Costs: ${costUsdText}${costPctText}`);
    }
    if (barsHeld != null) {
      parts.push(`Held: ${Number(barsHeld)}`);
    }
    return parts.length ? parts.join(" | ") : null;
  };

  const decisionMarkers = (markers || []).filter(isDecisionMarker);
  const eventMarkers = (markers || []).filter((marker) => !isDecisionMarker(marker));
  const visibleMarkers = listTab === 'decisions' ? decisionMarkers : eventMarkers;
  const renderedMarkers = useMemo(() => [...visibleMarkers].reverse(), [visibleMarkers]);

  useEffect(() => {
    if (!selectedMarker) return;
    for (let idx = 0; idx < renderedMarkers.length; idx += 1) {
      const marker = renderedMarkers[idx];
      if (!isSameMarker(selectedMarker, marker)) continue;
      const key = getMarkerKey(marker, idx);
      const node = itemRefs.current.get(key);
      if (node && node.scrollIntoView) {
        node.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
      }
      break;
    }
  }, [selectedMarker, renderedMarkers, listTab]);

  if (!markers || markers.length === 0) {
    return (
      <div className="decision-list">
        <div className="empty-state">
          <div className="icon">📭</div>
          <p>No decisions yet. Start the backtest to see trading decisions appear here.</p>
        </div>
      </div>
    );
  }

  const selectedEventTime = toUnixSeconds(selectedMarker?.time ?? selectedMarker?.timestamp);
  const selectedTicker = selectedMarker?.ticker ?? selectedMarker?.details?.ticker;
  const selectedRunId = selectedMarker?.run_id ?? selectedMarker?.details?.run_id;
  
  // Prepare metadata for rendering
  const details = selectedMarker?.details || {};
  const metadata = details.metadata || {};
  
  // Helper to render sections
  const renderSectionHeader = (title) => (
    <div className="detail-item" style={{ gridColumn: '1 / -1', borderTop: '1px solid var(--border-color)', paddingTop: 'var(--spacing-sm)', marginTop: 'var(--spacing-xs)', marginBottom: 'var(--spacing-xs)' }}>
      <span className="detail-label" style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{title}</span>
    </div>
  );

  return (
    <>
      <div className="decision-list-tabs">
        <button
          className={`decision-list-tab ${listTab === 'decisions' ? 'active' : ''}`}
          onClick={() => setListTab('decisions')}
        >
          Decisions ({decisionMarkers.length})
        </button>
        <button
          className={`decision-list-tab ${listTab === 'events' ? 'active' : ''}`}
          onClick={() => setListTab('events')}
        >
          Events ({eventMarkers.length})
        </button>
      </div>
      <div className="decision-list">
        {visibleMarkers.length === 0 && (
          <div className="empty-state">
            <div className="icon">🗂️</div>
            <p>{listTab === 'decisions' ? 'No trading decisions in this run yet.' : 'No non-decision events in this run yet.'}</p>
          </div>
        )}
        {renderedMarkers.map((marker, idx) => {
          const exitMetrics = formatExitMetrics(marker);
          const markerKey = getMarkerKey(marker, idx);
          const selected = isSameMarker(selectedMarker, marker);
          return (
          <div
            key={markerKey}
            ref={(node) => {
              if (node) itemRefs.current.set(markerKey, node);
              else itemRefs.current.delete(markerKey);
            }}
            className={`decision-item ${marker.marker_type} ${selected ? 'selected' : ''}`}
            onClick={() => onSelectMarker(marker)}
          >
            <div className="decision-header">
              <span className="decision-title">
                {getMarkerIcon(marker)} {renderTitle(marker)}
              </span>
              <span className="decision-time">{formatTime(marker.timestamp)}</span>
            </div>
            <div className="decision-description">
              {exitMetrics ? `Reason: ${marker.details?.exit_reason || 'n/a'}` : (marker.description || 'No description')}
              {exitMetrics && (
                <div style={{ marginTop: 4, color: 'var(--text-muted)', fontSize: '0.78rem', fontWeight: 600 }}>
                  {exitMetrics}
                </div>
              )}
              {marker.marker_type === 'pattern_detected' && marker.details?.direction && (
                <span style={{
                  marginLeft: 8,
                  padding: '1px 6px',
                  borderRadius: 3,
                  fontSize: '0.75em',
                  fontWeight: 600,
                  background: marker.details.direction === 'bullish' ? 'rgba(34,197,94,0.15)' : marker.details.direction === 'bearish' ? 'rgba(239,68,68,0.15)' : 'rgba(100,116,139,0.15)',
                  color: marker.details.direction === 'bullish' ? 'var(--accent-green)' : marker.details.direction === 'bearish' ? 'var(--accent-red)' : 'var(--text-secondary)',
                }}>
                  {marker.details.direction === 'bullish' ? '▲ BULL' : marker.details.direction === 'bearish' ? '▼ BEAR' : '◆ NEUTRAL'}
                </span>
              )}
            </div>
          </div>
        );})}
      </div>
      
      {/* Detail Panel */}
      {selectedMarker && (
        <div className="decision-detail">
          <h4>
            {getMarkerIcon(selectedMarker)} {renderTitle(selectedMarker)}
          </h4>
          <div className="decision-detail-tabs">
            <button
              className={`decision-detail-tab ${detailTab === 'details' ? 'active' : ''}`}
              onClick={() => setDetailTab('details')}
            >
              Details
            </button>
            <button
              className={`decision-detail-tab ${detailTab === 'raw' ? 'active' : ''}`}
              onClick={() => setDetailTab('raw')}
            >
              Raw
            </button>
          </div>
          {detailTab === 'details' && (
            <>
              <div className="detail-grid">
                {/* Basic Info */}
                <div className="detail-item">
                  <span className="detail-label">Event Type</span>
                  <span className="detail-value">{selectedMarker.marker_type || 'n/a'}</span>
                </div>
                <div className="detail-item">
                  <span className="detail-label">Time</span>
                  <span className="detail-value">
                    {formatTime(selectedMarker.timestamp)}
                  </span>
                </div>
                <div className="detail-item">
                  <span className="detail-label">Price</span>
                  <span className="detail-value">
                    {formatPrice(selectedMarker.price)}
                  </span>
                </div>
                {selectedMarker.side && (
                  <div className="detail-item">
                    <span className="detail-label">Side</span>
                    <span className="detail-value" style={{ 
                      color: selectedMarker.side === 'long' ? 'var(--accent-green)' : 'var(--accent-red)',
                      fontWeight: 700 
                    }}>
                      {String(selectedMarker.side).toUpperCase()}
                    </span>
                  </div>
                )}
                
                {/* Entry Specifics */}
                {selectedMarker.marker_type === 'entry_executed' && (
                  <>
                    <div className="detail-item">
                      <span className="detail-label">Strategy</span>
                      <span className="detail-value">{selectedMarker.strategy || metadata.strategy || 'Unknown'}</span>
                    </div>
                    <div className="detail-item">
                      <span className="detail-label">Confidence</span>
                      <span className="detail-value">
                        {selectedMarker.confidence != null ? Number(selectedMarker.confidence).toFixed(0) : 'N/A'}%
                      </span>
                    </div>
                    {details.stop_loss && (
                       <div className="detail-item">
                        <span className="detail-label">Stop Loss</span>
                        <span className="detail-value">${details.stop_loss.toFixed(2)}</span>
                      </div>
                    )}
                    {details.take_profit && (
                       <div className="detail-item">
                        <span className="detail-label">Take Profit</span>
                        <span className="detail-value">${details.take_profit.toFixed(2)}</span>
                      </div>
                    )}
                    {details.risk_reward && (
                       <div className="detail-item">
                        <span className="detail-label">R:R Ratio</span>
                        <span className="detail-value">{details.risk_reward.toFixed(2)}</span>
                      </div>
                    )}
                  </>
                )}

                {/* Exit Specifics */}
                {['exit_executed', 'stop_loss_hit', 'take_profit_hit'].includes(selectedMarker.marker_type) && (
                   <>
                    <div className="detail-item">
                      <span className="detail-label">Exit Reason</span>
                      <span className="detail-value">{details.exit_reason || 'Unknown'}</span>
                    </div>
                    {details.pnl_pct != null && (
                      <div className="detail-item">
                        <span className="detail-label">PnL</span>
                        <span className={`detail-value ${details.pnl_pct >= 0 ? 'positive' : 'negative'}`}>
                          {details.pnl_pct >= 0 ? '+' : ''}{details.pnl_pct.toFixed(2)}%
                        </span>
                      </div>
                    )}
                    {(details.pnl_dollars != null || details.pnl_usd != null) && (
                      <div className="detail-item">
                        <span className="detail-label">PnL $</span>
                        <span className={`detail-value ${(details.pnl_dollars ?? details.pnl_usd) >= 0 ? 'positive' : 'negative'}`}>
                          {(details.pnl_dollars ?? details.pnl_usd) >= 0 ? '+' : ''}${Number(details.pnl_dollars ?? details.pnl_usd).toFixed(2)}
                        </span>
                      </div>
                    )}
                    {details.bars_held && (
                      <div className="detail-item">
                        <span className="detail-label">Bars Held</span>
                        <span className="detail-value">{details.bars_held}</span>
                      </div>
                    )}
                   </>
                )}

                {/* Reasoning Section */}
                {details.reasoning && (
                   <div style={{ gridColumn: '1 / -1', marginTop: '10px', padding: '10px', background: 'rgba(15, 23, 42, 0.04)', borderRadius: '4px' }}>
                     <div className="detail-label" style={{ fontWeight: 600, marginBottom: '5px' }}>Reasoning</div>
                     <div className="detail-value" style={{ whiteSpace: 'normal', fontSize: '0.9em', lineHeight: '1.4' }}>{details.reasoning}</div>
                   </div>
                )}

                {/* Costs Breakdown */}
                {details.costs && (
                  <>
                    {renderSectionHeader("Trading Costs")}
                     {Object.entries(details.costs).map(([k, v]) => (
                      <div className="detail-item" key={`cost-${k}`}>
                        <span className="detail-label">{k.charAt(0).toUpperCase() + k.slice(1).replace('_', ' ')}</span>
                        <span className="detail-value">${Number(v).toFixed(4)}</span>
                      </div>
                    ))}
                  </>
                )}

                {/* Signal Data (Recursive) */}
                {Object.keys(metadata).length > 0 && (
                  <>
                     {renderSectionHeader("Signal Data (All Indicators)")}
                     <div style={{ gridColumn: '1 / -1' }}>
                       {Object.entries(metadata)
                        .filter(([key]) => key !== 'strategy')
                        .map(([key, value]) => (
                          <div key={key} style={{ marginBottom: '8px' }}>
                            <span style={{ fontWeight: 600, fontSize: '0.9em', color: 'var(--text-primary)' }}>{key}:</span>
                            <div style={{ marginTop: '2px' }}>
                              {renderValue(value, key)}
                            </div>
                          </div>
                       ))}
                     </div>
                  </>
                )}

                {/* Fallback for other details */}
                {Object.entries(details).length > 0 && !details.metadata && !details.costs && (
                   <>
                    {renderSectionHeader("Additional Details")}
                    {Object.entries(details).map(([key, value]) => {
                      if (['metadata', 'costs', 'reasoning', 'pnl_pct', 'pnl_usd', 'pnl_dollars', 'stop_loss', 'take_profit', 'exit_reason', 'risk_reward'].includes(key)) return null;
                      return (
                        <div className="detail-item" key={key}>
                          <span className="detail-label">{key}</span>
                          <span className="detail-value">{formatGenericValue(value)}</span>
                        </div>
                      );
                    })}
                   </>
                )}
               </div>
            </>
          )}
          {detailTab === 'raw' && (
            <pre className="decision-raw-json">{JSON.stringify(selectedMarker, null, 2)}</pre>
          )}
        </div>
      )}
    </>
  );
}

export default DecisionPanel;
