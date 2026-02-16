function PlaybackControls({ 
  runState, 
  isPlaying, 
  speed, 
  tradeEvaluationMode,
  isReloading,
  onSpeedChange,
  onTradeEvaluationModeChange,
  onStep, 
  onPlay, 
  onPause, 
  onStop,
  onReload,
  onReset 
}) {
  const progress = runState?.progress_pct || 0;
  const currentBar = runState?.current_bar_index || 0;
  const totalBars = runState?.total_bars || 0;
  
  // Helper to get label for speed
  const getSpeedLabel = (s) => {
    if (s === 'max' || s === 0) return 'instant';
    if (s === '10hz') return '10/sec';
    if (s === '5hz') return '5/sec';
    if (s === '2hz') return '2/sec';
    if (s === '1hz') return '1/sec';
    return `${s}ms`;
  };

  const getTradeModeLabel = (mode) => {
    if (mode === 'intrabar_5s') return '5s intrabar';
    if (mode === 'intrabar_1s') return '1s intrabar';
    return 'standard bars';
  };
  
  return (
    <div className="card">
      <div className="card-header">
        <span className="card-title">Playback</span>
        {isPlaying && (
          <span style={{ color: 'var(--accent-green)', fontSize: '0.8rem' }}>
            ▶ Running
          </span>
        )}
      </div>
      <div className="card-body playback-controls">
        {/* Progress */}
        <div className="progress-container">
          <div className="progress-bar">
            <div 
              className="progress-fill" 
              style={{ width: `${progress}%` }}
            />
          </div>
          <div className="progress-text">
            <span>Bar {currentBar} / {totalBars}</span>
            <span>{progress.toFixed(1)}%</span>
          </div>
        </div>
        
        {/* Control Buttons */}
        <div className="playback-buttons">
          <button 
            className="btn btn-primary btn-icon"
            onClick={onStep}
            disabled={isPlaying || currentBar >= totalBars}
            title="Step forward"
          >
            ⏭
          </button>
          {!isPlaying ? (
            <button 
              className="btn btn-success btn-icon"
              onClick={onPlay}
              disabled={currentBar >= totalBars}
              title="Play"
            >
              ▶
            </button>
          ) : (
            <button 
              className="btn btn-secondary btn-icon"
              onClick={onPause}
              title="Pause"
            >
              ⏸
            </button>
          )}
          <button 
            className="btn btn-secondary btn-icon"
            onClick={onStop}
            disabled={!isPlaying}
            title="Stop"
          >
            ⏹
          </button>
          <button
            className="btn btn-secondary btn-icon"
            onClick={onReload}
            disabled={!!isReloading || isPlaying}
            title="Restart from first bar using already loaded run data"
          >
            {isReloading ? '⟳' : '↻'}
          </button>
          <button 
            className="btn btn-danger btn-icon"
            onClick={onReset}
            title="Reset"
          >
            🔄
          </button>
        </div>
        
        {/* Simple Speed Control */}
        <div style={{ marginTop: '10px' }}>
          <div style={{ 
            display: 'flex', 
            justifyContent: 'space-between', 
            fontSize: '0.8rem',
            color: 'var(--text-secondary)',
            marginBottom: '8px'
          }}>
            <span>Speed</span>
            <span>{getSpeedLabel(speed)}</span>
          </div>
          
          <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
            <button 
              style={{
                padding: '4px 8px',
                fontSize: '0.7rem',
                border: '1px solid var(--border-color)',
                borderRadius: '4px',
                background: speed === 'max' ? 'var(--accent-blue)' : 'transparent',
                color: speed === 'max' ? 'white' : 'var(--text-secondary)',
                cursor: 'pointer'
              }}
              onClick={() => onSpeedChange('max')}
            >
              MAX
            </button>
            <button 
              style={{
                padding: '4px 8px',
                fontSize: '0.7rem',
                border: '1px solid var(--border-color)',
                borderRadius: '4px',
                background: speed === '10hz' ? 'var(--accent-blue)' : 'transparent',
                color: speed === '10hz' ? 'white' : 'var(--text-secondary)',
                cursor: 'pointer'
              }}
              onClick={() => onSpeedChange('10hz')}
            >
              10/s
            </button>
            <button 
              style={{
                padding: '4px 8px',
                fontSize: '0.7rem',
                border: '1px solid var(--border-color)',
                borderRadius: '4px',
                background: speed === '5hz' ? 'var(--accent-blue)' : 'transparent',
                color: speed === '5hz' ? 'white' : 'var(--text-secondary)',
                cursor: 'pointer'
              }}
              onClick={() => onSpeedChange('5hz')}
            >
              5/s
            </button>
            <button 
              style={{
                padding: '4px 8px',
                fontSize: '0.7rem',
                border: '1px solid var(--border-color)',
                borderRadius: '4px',
                background: speed === '1hz' ? 'var(--accent-blue)' : 'transparent',
                color: speed === '1hz' ? 'white' : 'var(--text-secondary)',
                cursor: 'pointer'
              }}
              onClick={() => onSpeedChange('1hz')}
            >
              1/s
            </button>
            <button 
              style={{
                padding: '4px 8px',
                fontSize: '0.7rem',
                border: '1px solid var(--border-color)',
                borderRadius: '4px',
                background: speed === 200 ? 'var(--accent-blue)' : 'transparent',
                color: speed === 200 ? 'white' : 'var(--text-secondary)',
                cursor: 'pointer'
              }}
              onClick={() => onSpeedChange(200)}
            >
              0.2s
            </button>
          </div>
        </div>

        <div style={{ marginTop: '10px' }}>
          <div style={{ 
            display: 'flex',
            justifyContent: 'space-between',
            fontSize: '0.8rem',
            color: 'var(--text-secondary)',
            marginBottom: '8px'
          }}>
            <span>Trade Eval</span>
            <span>{getTradeModeLabel(tradeEvaluationMode)}</span>
          </div>
          <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
            <button
              style={{
                padding: '4px 8px',
                fontSize: '0.7rem',
                border: '1px solid var(--border-color)',
                borderRadius: '4px',
                background: tradeEvaluationMode === 'intrabar_5s' ? 'var(--accent-blue)' : 'transparent',
                color: tradeEvaluationMode === 'intrabar_5s' ? 'white' : 'var(--text-secondary)',
                cursor: 'pointer'
              }}
              onClick={() => onTradeEvaluationModeChange('intrabar_5s')}
            >
              5s Intrabar
            </button>
            <button
              style={{
                padding: '4px 8px',
                fontSize: '0.7rem',
                border: '1px solid var(--border-color)',
                borderRadius: '4px',
                background: tradeEvaluationMode === 'standard' ? 'var(--accent-blue)' : 'transparent',
                color: tradeEvaluationMode === 'standard' ? 'white' : 'var(--text-secondary)',
                cursor: 'pointer'
              }}
              onClick={() => onTradeEvaluationModeChange('standard')}
            >
              Fast (bar)
            </button>
            <button
              style={{
                padding: '4px 8px',
                fontSize: '0.7rem',
                border: '1px solid var(--border-color)',
                borderRadius: '4px',
                background: tradeEvaluationMode === 'intrabar_1s' ? 'var(--accent-blue)' : 'transparent',
                color: tradeEvaluationMode === 'intrabar_1s' ? 'white' : 'var(--text-secondary)',
                cursor: 'pointer'
              }}
              onClick={() => onTradeEvaluationModeChange('intrabar_1s')}
            >
              1s Intrabar
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default PlaybackControls;
