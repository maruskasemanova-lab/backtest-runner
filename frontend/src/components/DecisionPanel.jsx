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
  
  // Get marker icon
  const getMarkerIcon = (markerType) => {
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
        {[...markers].reverse().map((marker) => (
          <div
            key={marker.id}
            className={`decision-item ${marker.marker_type} ${selectedMarker?.id === marker.id ? 'selected' : ''}`}
            onClick={() => onSelectMarker(marker)}
          >
            <div className="decision-header">
              <span className="decision-title">
                {getMarkerIcon(marker.marker_type)} {marker.title}
              </span>
              <span className="decision-time">{formatTime(marker.timestamp)}</span>
            </div>
            <div className="decision-description">
              {marker.description}
            </div>
          </div>
        ))}
      </div>
      
      {/* Detail Panel */}
      {selectedMarker && (
        <div className="decision-detail">
          <h4>
            {getMarkerIcon(selectedMarker.marker_type)} {selectedMarker.title}
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
              <span className="detail-value">${selectedMarker.price?.toFixed(2)}</span>
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
            {selectedMarker.confidence && (
              <div className="detail-item">
                <span className="detail-label">Confidence</span>
                <span className="detail-value">{selectedMarker.confidence.toFixed(0)}%</span>
              </div>
            )}
            {selectedMarker.details?.pnl_pct !== undefined && (
              <div className="detail-item">
                <span className="detail-label">PnL</span>
                <span className={`detail-value ${selectedMarker.details.pnl_pct >= 0 ? 'positive' : 'negative'}`}>
                  {selectedMarker.details.pnl_pct >= 0 ? '+' : ''}{selectedMarker.details.pnl_pct.toFixed(2)}%
                </span>
              </div>
            )}
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
