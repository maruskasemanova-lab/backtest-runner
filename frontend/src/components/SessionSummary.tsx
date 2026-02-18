function SessionSummary({ runState, markers }: { runState?: any; markers?: any[] }) {
  // Deduplicate markers by id to avoid double-counting
  const uniqueMarkers: any[] = Object.values(
    (markers || []).reduce((acc: Record<string, any>, m: any) => {
      if (m.id && acc[m.id]) return acc;
      if (m.id) acc[m.id] = m;
      else acc[Math.random()] = m; // fallback
      return acc;
    }, {})
  );

  // Calculate stats from unique markers
  const trades = uniqueMarkers.filter(m => 
    m.marker_type === 'exit_executed' || 
    m.marker_type === 'stop_loss_hit' || 
    m.marker_type === 'take_profit_hit'
  );
  
  // Count wins by gross PnL if available, else net
  const getScore = (t) => t.details?.gross_pnl_pct ?? t.details?.pnl_pct ?? 0;
  const winningTrades = trades.filter(t => getScore(t) > 0);
  const losingTrades = trades.filter(t => getScore(t) <= 0);
  
  const totalPnl = trades.reduce((sum, t) => sum + (t.details?.pnl_pct || 0), 0);
  const winRate = trades.length > 0 ? (winningTrades.length / trades.length) * 100 : 0;
  
  // Get latest regime/strategy marker (for multi-day runs)
  const regimeMarker = [...uniqueMarkers].reverse().find(m => m.marker_type === 'regime_detected');
  const strategyMarker = [...uniqueMarkers].reverse().find(m => m.marker_type === 'strategy_selected');
  const selectionWarnings: string[] = (() => {
    const rows: string[] = [];
    const seen = new Set<string>();
    const pushAll = (raw: any) => {
      if (!Array.isArray(raw)) return;
      raw.forEach((item) => {
        const text = String(item || '').trim();
        if (!text || seen.has(text)) return;
        seen.add(text);
        rows.push(text);
      });
    };

    pushAll(runState?.selection_warnings);
    pushAll(runState?.session_summary?.selection_warnings);

    const regimeHistory = Array.isArray(runState?.regime_history) ? runState.regime_history : [];
    if (regimeHistory.length > 0) {
      const latest = regimeHistory[regimeHistory.length - 1];
      pushAll(latest?.selection_warnings);
    }

    return rows;
  })();
  
  return (
    <div className="card">
      <div className="card-header">
        <span className="card-title">Session Summary</span>
      </div>
      <div className="card-body">
        {/* Phase & Regime */}
        <div className="phase-indicator">
          {runState?.phase && (
            <span className={`phase-badge ${runState.phase.toLowerCase()}`}>
              {runState.phase.replace('_', ' ')}
            </span>
          )}
          {regimeMarker?.regime && (
            <span className={`regime-badge ${regimeMarker.regime.toLowerCase()}`}>
              {regimeMarker.regime}
            </span>
          )}
        </div>
        
        {/* Strategy */}
        {strategyMarker?.strategy && (
          <div style={{ 
            padding: 'var(--spacing-sm) var(--spacing-md)',
            background: 'var(--bg-tertiary)',
            borderRadius: 'var(--border-radius-sm)',
            marginBottom: 'var(--spacing-md)'
          }}>
            <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>Strategy: </span>
            <span style={{ fontWeight: 500 }}>{strategyMarker.strategy}</span>
          </div>
        )}

        {selectionWarnings.length > 0 && (
          <div className="summary-warning-stack">
            <div className="summary-warning-title">Selection Warnings</div>
            {selectionWarnings.map((warning, index) => (
              <div
                key={`${warning}-${index}`}
                className="summary-warning-item"
              >
                {warning}
              </div>
            ))}
          </div>
        )}
        
        {/* Stats Grid */}
        <div className="stats-grid">
          <div className="stat-item">
            <div className={`stat-value ${totalPnl >= 0 ? 'positive' : 'negative'}`}>
              {totalPnl >= 0 ? '+' : ''}{totalPnl.toFixed(2)}%
            </div>
            <div className="stat-label">Total PnL</div>
          </div>
          
          <div className="stat-item">
            <div className="stat-value">{trades.length}</div>
            <div className="stat-label">Trades</div>
          </div>
          
          <div className="stat-item">
            <div className={`stat-value ${winRate >= 50 ? 'positive' : 'negative'}`}>
              {winRate.toFixed(0)}%
            </div>
            <div className="stat-label">Win Rate</div>
          </div>
          
          <div className="stat-item">
            <div className="stat-value">
              <span style={{ color: 'var(--accent-green)' }}>{winningTrades.length}</span>
              {' / '}
              <span style={{ color: 'var(--accent-red)' }}>{losingTrades.length}</span>
            </div>
            <div className="stat-label">W / L</div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default SessionSummary;
