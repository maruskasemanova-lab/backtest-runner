function PlaybackControls({ 
  runState, 
  isPlaying, 
  speed, 
  onSpeedChange,
  onStep, 
  onPlay, 
  onPause, 
  onStop,
  onReset 
}) {
  const progress = runState?.progress_pct || 0;
  const currentBar = runState?.current_bar_index || 0;
  const totalBars = runState?.total_bars || 0;
  
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
            className="btn btn-danger btn-icon"
            onClick={onReset}
            title="Reset"
          >
            🔄
          </button>
        </div>
        
        {/* Speed Control */}
        <div className="speed-control">
          <label>
            <span>Speed</span>
            <span>{speed}ms / bar</span>
          </label>
          <input
            type="range"
            className="speed-slider"
            min="50"
            max="1000"
            step="50"
            value={speed}
            onChange={(e) => onSpeedChange(Number(e.target.value))}
          />
        </div>
      </div>
    </div>
  );
}

export default PlaybackControls;
