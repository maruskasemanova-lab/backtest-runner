import { useState, useEffect, useRef } from 'react';
const DEFAULT_ACCOUNT_SIZE = 10_000;

/**
 * ChartTooltip - A tooltip component for chart markers
 * Shows detailed trade information on hover
 */
function ChartTooltip({ marker, visible, x, y }) {
  const tooltipRef = useRef(null);
  const [position, setPosition] = useState({ x, y });
  
  // Adjust position to keep tooltip on screen
  useEffect(() => {
    if (!tooltipRef.current || !visible) return;
    
    const rect = tooltipRef.current.getBoundingClientRect();
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;
    
    let newX = x;
    let newY = y - rect.height - 10; // Default above the marker
    
    // Adjust if going off right edge
    if (newX + rect.width > viewportWidth) {
      newX = viewportWidth - rect.width - 10;
    }
    
    // Adjust if going off left edge
    if (newX < 10) {
      newX = 10;
    }
    
    // Adjust if going off top (show below instead)
    if (newY < 10) {
      newY = y + 20;
    }
    
    setPosition({ x: newX, y: newY });
  }, [marker, visible, x, y]);
  
  if (!visible || !marker) return null;
  
  const { marker_type, price, side, strategy, confidence, details } = marker;
  const pnlPctFromDollars = (pnlDollars) => {
    const dollars = Number(pnlDollars);
    if (!Number.isFinite(dollars)) return null;
    return (dollars / DEFAULT_ACCOUNT_SIZE) * 100;
  };
  
  // Format timestamp
  const formatTime = (timestamp) => {
    if (!timestamp) return 'N/A';
    const date = new Date(timestamp);
    return date.toLocaleTimeString('en-US', { 
      hour: '2-digit', 
      minute: '2-digit',
      second: '2-digit',
      hour12: false 
    });
  };
  
  // Get marker color based on type
  const getMarkerColor = () => {
    switch (marker_type) {
      case 'entry_executed':
        return '#22c55e';
      case 'stop_loss_hit':
        return '#ef4444';
      case 'take_profit_hit':
        return '#22c55e';
      case 'exit_executed':
        return '#64748b';
      default:
        return '#3b82f6';
    }
  };
  
  // Recursive function to render values
  const renderValue = (val, keyPrefix = '') => {
    if (val === null || val === undefined) return 'N/A';
    
    if (typeof val === 'object' && !Array.isArray(val)) {
      if (Object.keys(val).length === 0) return '{}';
      
      return (
        <div className="object-container">
          {Object.entries(val).map(([k, v]) => (
            <div key={`${keyPrefix}-${k}`} className="object-row">
              <span className="object-key">{k}:</span>
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
        <div className="object-container">
          {val.map((v, i) => (
             <div key={`${keyPrefix}-${i}`} className="object-row">
              <span className="object-key">[{i}]:</span>
               <div className="nested-object">
                 {renderValue(v, `${keyPrefix}-${i}`)}
               </div>
             </div>
          ))}
        </div>
      );
    }
    
    if (typeof val === 'number') {
      return Math.abs(val) < 0.01 ? val.toFixed(6) : val.toFixed(4);
    }
    
    return String(val);
  };

  // Render entry marker details
  const renderEntryDetails = () => {
    if (!details) return null;
    
    // Get all signal data from metadata
    const metadata = details.metadata || {};
    
    return (
      <>
        <div className="tooltip-row">
          <span className="tooltip-label">Strategy:</span>
          <span className="tooltip-value">{strategy || metadata.strategy || 'Unknown'}</span>
        </div>
        <div className="tooltip-row">
          <span className="tooltip-label">Confidence:</span>
          <span className="tooltip-value">
            {confidence != null
              ? confidence.toFixed(0)
              : details?.confidence != null
              ? Number(details.confidence).toFixed(0)
              : 'N/A'}%
          </span>
        </div>
        {details.stop_loss != null && (
          <div className="tooltip-row">
            <span className="tooltip-label">Stop Loss:</span>
            <span className="tooltip-value">${details.stop_loss.toFixed(2)}</span>
          </div>
        )}
        {details.take_profit != null && (
          <div className="tooltip-row">
            <span className="tooltip-label">Take Profit:</span>
            <span className="tooltip-value">${details.take_profit.toFixed(2)}</span>
          </div>
        )}
        {details.risk_reward && (
          <div className="tooltip-row">
            <span className="tooltip-label">R:R Ratio:</span>
            <span className="tooltip-value">{details.risk_reward.toFixed(2)}</span>
          </div>
        )}
        
        {/* Show all signal metadata */}
        {Object.keys(metadata).length > 0 && (
          <div className="tooltip-section">
            <div className="tooltip-label">Signal Data (All Indicators):</div>
            <div className="tooltip-metadata">
              {Object.entries(metadata)
                .filter(([key]) => key !== 'strategy') // Skip strategy as it's shown above
                .map(([key, value]) => (
                <div key={key} className="tooltip-meta-row">
                  <span className="tooltip-meta-key">{key}:</span>
                  <span className="tooltip-meta-value">
                    {renderValue(value, key)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
        
        {details.reasoning && (
          <div className="tooltip-section">
            <div className="tooltip-label">Reasoning:</div>
            <div className="tooltip-reasoning">{details.reasoning}</div>
          </div>
        )}
      </>
    );
  };
  
  // Render exit marker details
  const renderExitDetails = () => {
    if (!details) return null;
    
    return (
      <>
        <div className="tooltip-row">
          <span className="tooltip-label">Exit Reason:</span>
          <span className="tooltip-value">{details.exit_reason || 'Unknown'}</span>
        </div>
        {details.pnl_dollars != null && (
          <div className="tooltip-row">
            <span className="tooltip-label">PnL:</span>
            {(() => {
              const pnlPct = pnlPctFromDollars(details.pnl_dollars);
              if (pnlPct == null) return <span className="tooltip-value">n/a</span>;
              return (
                <span className={`tooltip-value ${pnlPct >= 0 ? 'positive' : 'negative'}`}>
                  {pnlPct >= 0 ? '+' : ''}{pnlPct.toFixed(2)}%
                </span>
              );
            })()}
          </div>
        )}
        {details.pnl_dollars != null && (
          <div className="tooltip-row">
            <span className="tooltip-label">PnL $:</span>
            <span className={`tooltip-value ${details.pnl_dollars >= 0 ? 'positive' : 'negative'}`}>
              {details.pnl_dollars >= 0 ? '+' : ''}${details.pnl_dollars.toFixed(2)}
            </span>
          </div>
        )}
        {details.entry_price && (
          <div className="tooltip-row">
            <span className="tooltip-label">Entry Price:</span>
            <span className="tooltip-value">${details.entry_price.toFixed(2)}</span>
          </div>
        )}
        {details.bars_held && (
          <div className="tooltip-row">
            <span className="tooltip-label">Bars Held:</span>
            <span className="tooltip-value">{details.bars_held}</span>
          </div>
        )}
        {details.costs && details.costs.total > 0 && (
          <div className="tooltip-section">
            <div className="tooltip-label">Trading Costs:</div>
            <div className="tooltip-costs">
              <div className="tooltip-meta-row">
                <span className="tooltip-meta-key">Slippage:</span>
                <span className="tooltip-meta-value">
                  ${details.costs.slippage != null ? details.costs.slippage.toFixed(4) : '0.0000'}
                </span>
              </div>
              <div className="tooltip-meta-row">
                <span className="tooltip-meta-key">Commission:</span>
                <span className="tooltip-meta-value">${details.costs.commission?.toFixed(2) || '0.00'}</span>
              </div>
              <div className="tooltip-meta-row">
                <span className="tooltip-meta-key">SEC Fee:</span>
                <span className="tooltip-meta-value">${details.costs.sec_fee?.toFixed(6) || '0.000000'}</span>
              </div>
              <div className="tooltip-meta-row">
                <span className="tooltip-meta-key">Reg. Fees:</span>
                <span className="tooltip-meta-value">
                  ${details.costs.reg_fee != null ? details.costs.reg_fee.toFixed(4) : '0.0000'}
                </span>
              </div>
              <div className="tooltip-meta-row">
                <span className="tooltip-meta-key">FINRA Fee:</span>
                <span className="tooltip-meta-value">${details.costs.finra_fee?.toFixed(6) || '0.000000'}</span>
              </div>
              <div className="tooltip-meta-row total">
                <span className="tooltip-meta-key">Total:</span>
                <span className="tooltip-meta-value">${details.costs.total?.toFixed(4) || '0.0000'}</span>
              </div>
            </div>
          </div>
        )}
      </>
    );
  };
  
  return (
    <div 
      ref={tooltipRef}
      className="chart-tooltip"
      style={{
        left: position.x,
        top: position.y,
        borderLeft: `4px solid ${getMarkerColor()}`
      }}
    >
      <div className="tooltip-header">
        <span className="tooltip-title">{marker.title || marker_type}</span>
        <span className="tooltip-time">{formatTime(marker.timestamp)}</span>
      </div>
      
      <div className="tooltip-content">
        <div className="tooltip-row">
          <span className="tooltip-label">Price:</span>
          <span className="tooltip-value">${price?.toFixed(2) || 'N/A'}</span>
        </div>
        {side && (
          <div className="tooltip-row">
            <span className="tooltip-label">Side:</span>
            <span className={`tooltip-value side-${side}`}>{side.toUpperCase()}</span>
          </div>
        )}
        
        {marker_type === 'entry_executed' && renderEntryDetails()}
        {(marker_type === 'exit_executed' || marker_type === 'stop_loss_hit' || marker_type === 'take_profit_hit') && renderExitDetails()}
      </div>
      
      <style>{`
        .chart-tooltip {
          position: fixed;
          background: rgba(255, 255, 255, 0.95);
          border: 1px solid rgba(15, 23, 42, 0.12);
          border-radius: 8px;
          padding: 12px;
          min-width: 320px;
          max-width: 400px;
          max-height: 500px;
          overflow-y: auto;
          box-shadow: 0 12px 30px rgba(15, 23, 42, 0.18);
          z-index: 1000;
          font-size: 13px;
          color: #1b1a19;
          backdrop-filter: blur(10px);
          overscroll-behavior: contain;
        }

        /* Scrollbar styling */
        .chart-tooltip::-webkit-scrollbar {
          width: 6px;
        }
        
        .chart-tooltip::-webkit-scrollbar-track {
          background: rgba(0, 0, 0, 0.05);
          border-radius: 3px;
        }
        
        .chart-tooltip::-webkit-scrollbar-thumb {
          background: rgba(0, 0, 0, 0.2);
          border-radius: 3px;
        }
        
        .chart-tooltip::-webkit-scrollbar-thumb:hover {
          background: rgba(0, 0, 0, 0.3);
        }
        
        .tooltip-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 10px;
          padding-bottom: 8px;
          border-bottom: 1px solid rgba(15, 23, 42, 0.08);
          position: sticky;
          top: -12px;
          background: rgba(255, 255, 255, 0.95);
          z-index: 1;
          margin-top: -12px;
          padding-top: 12px;
        }
        
        .tooltip-title {
          font-weight: 600;
          font-size: 14px;
          color: #1b1a19;
        }
        
        .tooltip-time {
          font-size: 11px;
          color: #8b857b;
          font-family: var(--font-mono);
        }
        
        .tooltip-content {
          display: flex;
          flex-direction: column;
          gap: 6px;
        }
        
        .tooltip-row {
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          gap: 10px;
        }
        
        .tooltip-label {
          color: #6b655c;
          font-size: 12px;
          white-space: nowrap;
          flex-shrink: 0;
        }
        
        .tooltip-value {
          color: #1b1a19;
          font-weight: 500;
          font-family: var(--font-mono);
          text-align: right;
          word-break: break-word;
        }
        
        .tooltip-value.positive {
          color: #0f766e;
        }
        
        .tooltip-value.negative {
          color: #dc2626;
        }
        
        .tooltip-value.side-long {
          color: #0f766e;
        }
        
        .tooltip-value.side-short {
          color: #dc2626;
        }
        
        .tooltip-section {
          margin-top: 10px;
          padding-top: 10px;
          border-top: 1px solid rgba(15, 23, 42, 0.08);
        }
        
        .tooltip-section-title {
          font-weight: 600;
          color: #4b5563;
          margin-bottom: 5px;
          font-size: 12px;
        }
        
        .tooltip-reasoning {
          margin-top: 6px;
          padding: 8px;
          background: rgba(15, 23, 42, 0.04);
          border-radius: 4px;
          font-size: 11px;
          line-height: 1.4;
          color: #5c574f;
        }
        
        .object-container {
          display: flex;
          flex-direction: column;
          gap: 4px;
          width: 100%;
        }

        .object-row {
          display: flex;
          flex-direction: column;
          border-left: 2px solid rgba(15, 23, 42, 0.1);
          padding-left: 8px;
          margin-bottom: 4px;
        }

        .object-key {
          font-size: 11px;
          color: #6b7280;
          font-weight: 500;
        }

        .object-value {
          font-family: var(--font-mono);
          font-size: 11px;
          color: #374151;
        }

        .nested-object {
          margin-left: 4px;
        }
        
        .tooltip-metadata {
          margin-top: 6px;
          display: flex;
          flex-direction: column;
          gap: 3px;
        }
        
        .tooltip-meta-row {
          display: flex;
          justify-content: space-between;
          font-size: 11px;
        }
        
        .tooltip-meta-key {
          color: #7a736a;
        }
        
        .tooltip-meta-value {
          color: #5c574f;
          font-family: var(--font-mono);
        }
        
        .tooltip-meta-row.total {
          margin-top: 4px;
          padding-top: 4px;
          border-top: 1px solid rgba(15, 23, 42, 0.12);
        }
        
        .tooltip-meta-row.total .tooltip-meta-key,
        .tooltip-meta-row.total .tooltip-meta-value {
          font-weight: 600;
          color: #1b1a19;
        }
        
        .tooltip-costs {
          margin-top: 6px;
          display: flex;
          flex-direction: column;
          gap: 3px;
        }
      `}</style>
    </div>
  );
}

export default ChartTooltip;
