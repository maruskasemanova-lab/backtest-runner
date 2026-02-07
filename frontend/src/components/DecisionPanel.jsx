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
      pattern_detected: '🕯️',
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

  const asNumber = (value, fallback = null) => {
    if (value === null || value === undefined) {
      return fallback;
    }
    const num = Number(value);
    return Number.isFinite(num) ? num : fallback;
  };

  const resolveEffectiveStrategyWeight = (layerScores) => {
    if (!layerScores) {
      return null;
    }
    const direct = layerScores.effective_strategy_weight;
    if (direct !== undefined && direct !== null) {
      return asNumber(direct, null);
    }
    const snapshot = layerScores.weights_snapshot;
    if (snapshot && snapshot.strategy_weight !== undefined && snapshot.strategy_weight !== null) {
      return asNumber(snapshot.strategy_weight, null);
    }
    if (layerScores.strategy_weight !== undefined && layerScores.strategy_weight !== null) {
      return asNumber(layerScores.strategy_weight, null);
    }
    return null;
  };

  const resolveStrategyWeightSource = (layerScores, effectiveWeight) => {
    if (!layerScores) {
      return null;
    }
    if (layerScores.strategy_weight_source) {
      return layerScores.strategy_weight_source;
    }
    return effectiveWeight === null ? null : "legacy";
  };

  const formatPatternScore = (layerScores, fallbackDirection) => {
    const patternScore = asNumber(layerScores?.pattern_score, 0) || 0;
    const patternThreshold = asNumber(
      layerScores?.pattern_threshold ?? layerScores?.threshold,
      65
    ) || 65;
    const patternConfirmation = layerScores?.pattern_confirmation ?? patternScore > 0;
    const thresholdReason = layerScores?.threshold_used_reason;
    const patternDirection = layerScores?.pattern_direction || fallbackDirection;
    const isNeutralForced = !patternConfirmation
      && patternScore === 0
      && (patternDirection === "neutral" || thresholdReason === "no_pattern_confirmation");

    if (isNeutralForced) {
      return `score=0.0 (neutral forced, th=${patternThreshold.toFixed(1)})`;
    }
    const operator = patternScore >= patternThreshold ? ">=" : "<";
    const status = patternConfirmation ? "confirm" : "no_confirm";
    return `score=${patternScore.toFixed(1)} ${operator} ${patternThreshold.toFixed(1)} (${status})`;
  };

  const renderLayerScoresDetails = (layerScores, fallbackDirection) => {
    if (!layerScores) {
      return null;
    }

    const strategyScore = asNumber(layerScores.strategy_score, 0) || 0;
    const combinedRaw = asNumber(layerScores.combined_raw ?? layerScores.combined_score, 0) || 0;
    const thresholdUsed = asNumber(layerScores.threshold_used ?? layerScores.threshold, 65) || 65;
    const patternThreshold = asNumber(layerScores.pattern_threshold ?? layerScores.threshold, 65) || 65;
    const tradeGateThreshold = asNumber(layerScores.trade_gate_threshold ?? layerScores.threshold, 65) || 65;
    const combinedNorm = asNumber(layerScores.combined_norm_0_100, null);
    const thresholdReason = layerScores.threshold_used_reason;
    const effectiveWeight = resolveEffectiveStrategyWeight(layerScores);
    const weightSource = resolveStrategyWeightSource(layerScores, effectiveWeight);
    const l2Coverage = asNumber(layerScores.l2_coverage_ratio, null);

    return (
      <>
        <div className="detail-item" style={{ gridColumn: '1 / -1', borderTop: '1px solid var(--border-color)', paddingTop: 'var(--spacing-sm)', marginTop: 'var(--spacing-xs)' }}>
          <span className="detail-label" style={{ fontWeight: 600 }}>Multi-Layer Scores</span>
        </div>
        <div className="detail-item">
          <span className="detail-label">Pattern Score</span>
          <span className="detail-value">{formatPatternScore(layerScores, fallbackDirection)}</span>
        </div>
        <div className="detail-item">
          <span className="detail-label">Strategy Score</span>
          <span className="detail-value">{strategyScore.toFixed(1)}</span>
        </div>
        <div className="detail-item">
          <span className="detail-label">Combined</span>
          <span className={`detail-value ${combinedRaw >= thresholdUsed ? 'positive' : 'negative'}`}>
            {`raw=${combinedRaw.toFixed(1)} | gate=${thresholdUsed.toFixed(1)}`}
          </span>
        </div>
        {combinedNorm !== null && (
          <div className="detail-item">
            <span className="detail-label">Combined Norm</span>
            <span className="detail-value">{`norm=${combinedNorm.toFixed(1)}/100`}</span>
          </div>
        )}
        <div className="detail-item">
          <span className="detail-label">Pattern Th</span>
          <span className="detail-value">{patternThreshold.toFixed(1)}</span>
        </div>
        <div className="detail-item">
          <span className="detail-label">Trade Gate Th</span>
          <span className="detail-value">{tradeGateThreshold.toFixed(1)}</span>
        </div>
        <div className="detail-item">
          <span className="detail-label">Gate Used</span>
          <span className="detail-value">{thresholdUsed.toFixed(1)}</span>
        </div>
        {thresholdReason && (
          <div className="detail-item">
            <span className="detail-label">Threshold Reason</span>
            <span className="detail-value">{thresholdReason}</span>
          </div>
        )}
        {effectiveWeight !== null && (
          <div className="detail-item">
            <span className="detail-label">Effective Strat W</span>
            <span className="detail-value">{effectiveWeight.toFixed(2)}</span>
          </div>
        )}
        {weightSource && (
          <div className="detail-item">
            <span className="detail-label">Weight Source</span>
            <span className="detail-value">{weightSource}</span>
          </div>
        )}
        {l2Coverage !== null && (
          <div className="detail-item">
            <span className="detail-label">L2 Coverage</span>
            <span className="detail-value">{l2Coverage.toFixed(2)}</span>
          </div>
        )}
      </>
    );
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
          const exitMetrics = formatExitMetrics(marker);
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
              {exitMetrics ? `Reason: ${marker.details?.exit_reason || 'n/a'}` : marker.description}
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
            {renderLayerScoresDetails(
              selectedMarker.details?.layer_scores || selectedMarker.details?.metadata?.layer_scores,
              selectedMarker.details?.direction
            )}
            {/* Patterns list */}
            {selectedMarker.details?.patterns && selectedMarker.details.patterns.length > 0 && (
              <>
                <div className="detail-item" style={{ gridColumn: '1 / -1', borderTop: '1px solid var(--border-color)', paddingTop: 'var(--spacing-sm)', marginTop: 'var(--spacing-xs)' }}>
                  <span className="detail-label" style={{ fontWeight: 600 }}>Candlestick Patterns</span>
                </div>
                {selectedMarker.details.patterns.map((pattern, pidx) => (
                  <div className="detail-item" key={pidx} style={{ gridColumn: '1 / -1' }}>
                    <span className="detail-label">
                      {pattern.direction === 'bullish' ? '▲' : pattern.direction === 'bearish' ? '▼' : '◆'} {pattern.name}
                    </span>
                    <span className="detail-value">
                      Strength: {Number(pattern.strength || 0).toFixed(0)}
                      {pattern.metadata?.volume_confirmed ? ' | Vol ✓' : ''}
                      {pattern.metadata?.trend_aligned ? ' | Trend ✓' : ''}
                    </span>
                  </div>
                ))}
              </>
            )}
            {/* Patterns from metadata (for entry markers) */}
            {selectedMarker.details?.metadata?.patterns && selectedMarker.details.metadata.patterns.length > 0 && !selectedMarker.details?.patterns && (
              <>
                <div className="detail-item" style={{ gridColumn: '1 / -1', borderTop: '1px solid var(--border-color)', paddingTop: 'var(--spacing-sm)', marginTop: 'var(--spacing-xs)' }}>
                  <span className="detail-label" style={{ fontWeight: 600 }}>Triggering Patterns</span>
                </div>
                {selectedMarker.details.metadata.patterns.map((pattern, pidx) => (
                  <div className="detail-item" key={pidx} style={{ gridColumn: '1 / -1' }}>
                    <span className="detail-label">
                      {pattern.direction === 'bullish' ? '▲' : pattern.direction === 'bearish' ? '▼' : '◆'} {pattern.name}
                    </span>
                    <span className="detail-value">Strength: {Number(pattern.strength || 0).toFixed(0)}</span>
                  </div>
                ))}
              </>
            )}
            {selectedMarker.details?.pnl_pct !== undefined && selectedMarker.details?.pnl_pct !== null && (
              <div className="detail-item">
                <span className="detail-label">PnL</span>
                <span className={`detail-value ${(selectedMarker.details.pnl_pct || 0) >= 0 ? 'positive' : 'negative'}`}>
                  {(selectedMarker.details.pnl_pct || 0) >= 0 ? '+' : ''}{Number(selectedMarker.details.pnl_pct || 0).toFixed(2)}%
                </span>
              </div>
            )}
            {selectedMarker.details?.pnl_usd !== undefined && selectedMarker.details?.pnl_usd !== null && (
              <div className="detail-item">
                <span className="detail-label">PnL $</span>
                <span className={`detail-value ${(selectedMarker.details.pnl_usd || 0) >= 0 ? 'positive' : 'negative'}`}>
                  {(selectedMarker.details.pnl_usd || 0) >= 0 ? '+' : ''}${Number(selectedMarker.details.pnl_usd || 0).toFixed(2)}
                </span>
              </div>
            )}
            {selectedMarker.details?.cost_usd !== undefined && selectedMarker.details?.cost_usd !== null && (
              <div className="detail-item">
                <span className="detail-label">Costs</span>
                <span className="detail-value">
                  ${Number(selectedMarker.details.cost_usd || 0).toFixed(2)}
                  {selectedMarker.details.cost_pct !== undefined && selectedMarker.details.cost_pct !== null
                    ? ` (${Number(selectedMarker.details.cost_pct).toFixed(2)}%)`
                    : ''}
                </span>
              </div>
            )}
            {selectedMarker.details?.position_notional_usd !== undefined && selectedMarker.details?.position_notional_usd !== null && (
              <div className="detail-item">
                <span className="detail-label">Notional</span>
                <span className="detail-value">${Number(selectedMarker.details.position_notional_usd || 0).toFixed(2)}</span>
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
              if ([
                'schema_version',
                'pnl_pct',
                'pnl_dollars',
                'pnl_usd',
                'gross_pnl_pct',
                'gross_pnl_dollars',
                'cost_usd',
                'cost_pct',
                'position_notional_usd',
                'costs',
                'patterns',
                'direction',
                'layer_scores',
                'metadata',
                'stop_loss',
                'take_profit',
                'exit_reason',
                'signal_type',
                'ticker',
                'run_id'
              ].includes(key)) return null;
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
