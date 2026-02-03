function DecisionPanel({ markers, selectedMarker, onSelectMarker }) {
  // Format time
  const formatTime = (timestamp) => {
    const date = new Date(timestamp);
    return date.toLocaleTimeString('en-US', { 
      hour: '2-digit', 
      minute: '2-digit',
      hour12: false 
    });
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
      entry_executed: '🟢',
      exit_executed: '⚪',
      stop_loss_hit: '🔴',
      take_profit_hit: '💰',
      trailing_stop_updated: '📍',
      session_started: '🏁',
      session_ended: '🏆',
    };
    return icons[markerType] || '📌';
  };

  const renderTitle = (marker) => {
    if (marker.marker_type === 'take_profit_hit' && marker.details?.pnl_pct !== undefined && marker.details.pnl_pct <= 0) {
      return `${marker.title} (net loss)`;
    }
    return marker.title;
  };
  
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
  
  return (
    <>
      <div className="decision-list">
        {[...markers].reverse().map((marker, idx) => {
          const pnl = marker.details?.pnl_pct;
          const isLoss = pnl !== undefined && pnl < 0;
          return (
          <div
            key={marker.id || `${marker.marker_type}-${marker.timestamp}-${idx}`}
            className={`decision-item ${marker.marker_type} ${selectedMarker?.id === marker.id ? 'selected' : ''}`}
            onClick={() => onSelectMarker(marker)}
          >
            <div className="decision-header">
              <span className="decision-title">
                {getMarkerIcon(marker)} {renderTitle(marker)}
              </span>
              <span className="decision-time">{formatTime(marker.timestamp)}</span>
            </div>
            <div className="decision-description">
              {marker.description}
              {pnl != null && (
                <span style={{ marginLeft: 8, color: isLoss ? 'var(--accent-red)' : 'var(--accent-green)', fontWeight: 600 }}>
                  ({pnl >= 0 ? '+' : ''}{pnl.toFixed(2)}%)
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
          <div className="detail-grid">
            <div className="detail-item">
              <span className="detail-label">Time</span>
              <span className="detail-value">
                {new Date(selectedMarker.timestamp).toLocaleString()}
              </span>
            </div>
            <div className="detail-item">
              <span className="detail-label">Price</span>
              <span className="detail-value">
                {selectedMarker.price != null ? `$${selectedMarker.price.toFixed(2)}` : 'N/A'}
              </span>
            </div>
            {selectedMarker.strategy && (
              <div className="detail-item">
                <span className="detail-label">Strategy</span>
                <span className="detail-value">{selectedMarker.strategy}</span>
              </div>
            )}
            {selectedMarker.regime && (
              <div className="detail-item">
                <span className="detail-label">Regime</span>
                <span className={`regime-badge ${selectedMarker.regime.toLowerCase()}`}>
                  {selectedMarker.regime}
                </span>
              </div>
            )}
            {selectedMarker.confidence !== undefined && selectedMarker.confidence !== null && (
              <div className="detail-item">
                <span className="detail-label">Confidence</span>
                <span className="detail-value">{selectedMarker.confidence.toFixed(0)}%</span>
              </div>
            )}
            {selectedMarker.details?.pnl_pct !== undefined && selectedMarker.details?.pnl_pct !== null && (
              <div className="detail-item">
                <span className="detail-label">PnL</span>
                <span className={`detail-value ${(selectedMarker.details.pnl_pct || 0) >= 0 ? 'positive' : 'negative'}`}>
                  {(selectedMarker.details.pnl_pct || 0) >= 0 ? '+' : ''}{Number(selectedMarker.details.pnl_pct || 0).toFixed(2)}%
                </span>
              </div>
            )}
            {selectedMarker.details?.gross_pnl_pct !== undefined && selectedMarker.details?.gross_pnl_pct !== null && (
              <div className="detail-item">
                <span className="detail-label">Gross PnL</span>
                <span className={`detail-value ${(selectedMarker.details.gross_pnl_pct || 0) >= 0 ? 'positive' : 'negative'}`}>
                  {(selectedMarker.details.gross_pnl_pct || 0) >= 0 ? '+' : ''}{Number(selectedMarker.details.gross_pnl_pct || 0).toFixed(2)}%
                </span>
              </div>
            )}
            {/* Dynamic Details Rendering */}
            {selectedMarker.details && Object.entries(selectedMarker.details).map(([key, value]) => {
              // Skip fields already handled or internal
              if (['pnl_pct', 'pnl_dollars', 'stop_loss', 'take_profit', 'exit_reason', 'signal_type', 'ticker', 'run_id'].includes(key)) return null;
              if (value === null || value === undefined) return null;
              
              // Format labels
              const label = key.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
              
              // Format values
              let displayValue = value;
              if (typeof value === 'number') {
                if (key.includes('pct') || key.includes('ratio')) displayValue = value.toFixed(2) + (key.includes('pct') ? '%' : '');
                else if (key.includes('price') || key.includes('vwap') || key.includes('atr')) displayValue = value.toFixed(2);
                else displayValue = value.toFixed(2);
              } else if (typeof value === 'object') {
                // Render objects (e.g., costs) as a compact string
                displayValue = Object.entries(value)
                  .map(([k, v]) => `${k}: ${typeof v === 'number' ? v.toFixed(4) : v}`)
                  .join(', ');
              }
              
              return (
                <div className="detail-item" key={key}>
                  <span className="detail-label">{label}</span>
                  <span className="detail-value">{displayValue}</span>
                </div>
              );
            })}
            
            {selectedMarker.details?.stop_loss && (
              <div className="detail-item">
                <span className="detail-label">Stop Loss</span>
                <span className="detail-value">${selectedMarker.details.stop_loss.toFixed(2)}</span>
              </div>
            )}
            {selectedMarker.details?.take_profit && (
              <div className="detail-item">
                <span className="detail-label">Take Profit</span>
                <span className="detail-value">${selectedMarker.details.take_profit.toFixed(2)}</span>
              </div>
            )}
           </div>
          <p style={{ marginTop: 'var(--spacing-md)', color: 'var(--text-secondary)' }}>
            {selectedMarker.description}
          </p>
        </div>
      )}
    </>
  );
}

export default DecisionPanel;
