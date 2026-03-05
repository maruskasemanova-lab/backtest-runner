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
  const speedOptions = [
    { value: 'max', label: 'MAX' },
    { value: '10hz', label: '10/s' },
    { value: '5hz', label: '5/s' },
    { value: '1hz', label: '1/s' },
    { value: 200, label: '0.2s' },
  ];
  const tradeModeOptions = [
    { value: 'intrabar_5s', label: '5s Intrabar' },
    { value: 'standard', label: 'Fast (bar)' },
    { value: 'intrabar_1s', label: '1s Intrabar' },
  ];
  
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
    <div className="card playback-card">
      <div className="card-header">
        <span className="card-title">Playback</span>
        {isPlaying && (
          <span className="playback-status">
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
        <div className="playback-control-group">
          <div className="playback-control-meta">
            <span className="playback-control-label">Speed</span>
            <span className="playback-control-value">{getSpeedLabel(speed)}</span>
          </div>
          <div className="ui-segmented playback-segmented" role="group" aria-label="Playback speed">
            {speedOptions.map((option) => (
              <button
                key={String(option.value)}
                type="button"
                className={`ui-segmented-option${speed === option.value ? ' is-active' : ''}`}
                onClick={() => onSpeedChange(option.value)}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>

        <div className="playback-control-group">
          <div className="playback-control-meta">
            <span className="playback-control-label">Trade Eval</span>
            <span className="playback-control-value">{getTradeModeLabel(tradeEvaluationMode)}</span>
          </div>
          <div className="ui-segmented playback-segmented" role="group" aria-label="Trade evaluation mode">
            {tradeModeOptions.map((option) => (
              <button
                key={option.value}
                type="button"
                className={`ui-segmented-option${tradeEvaluationMode === option.value ? ' is-active' : ''}`}
                onClick={() => onTradeEvaluationModeChange(option.value)}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

export default PlaybackControls;
