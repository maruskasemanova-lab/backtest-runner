function SessionSummary({ runState, markers }: { runState?: any; markers?: any[] }) {
  const DEFAULT_ACCOUNT_SIZE = 10_000;

  const toNetPnlUsd = (trade: any): number | null => {
    const value = Number(trade?.details?.pnl_usd ?? trade?.details?.pnl_dollars);
    return Number.isFinite(value) ? value : null;
  };

  const pctFromDollars = (pnlUsd: number, accountSize: number): number => {
    if (!Number.isFinite(pnlUsd) || !Number.isFinite(accountSize) || accountSize <= 0) return 0;
    return (pnlUsd / accountSize) * 100;
  };

  const resolveAccountSize = (): number => {
    const candidate = Number(runState?.execution_config?.account_size_usd);
    if (Number.isFinite(candidate) && candidate > 0) return candidate;
    return DEFAULT_ACCOUNT_SIZE;
  };

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
  
  const winningTrades = trades.filter((t) => {
    const pnlUsd = toNetPnlUsd(t);
    if (pnlUsd != null) return pnlUsd > 0;
    return Number(t?.details?.pnl_pct ?? 0) > 0;
  });
  const losingTrades = trades.filter((t) => {
    const pnlUsd = toNetPnlUsd(t);
    if (pnlUsd != null) return pnlUsd <= 0;
    return Number(t?.details?.pnl_pct ?? 0) <= 0;
  });

  const accountSize = resolveAccountSize();
  const fallbackTotalPnlUsd = trades.reduce((sum, t) => sum + (toNetPnlUsd(t) ?? 0), 0);
  const summaryTotalPnlUsd = Number(runState?.session_summary?.total_pnl_dollars);
  const totalPnlUsd = Number.isFinite(summaryTotalPnlUsd) ? summaryTotalPnlUsd : fallbackTotalPnlUsd;
  const totalPnl = pctFromDollars(totalPnlUsd, accountSize);
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

  const dataCoverage = (() => {
    const l2Applied =
      runState?.l2_applied && typeof runState.l2_applied === "object" ? runState.l2_applied : null;
    if (!l2Applied) return null;

    const asFiniteInt = (value: any, fallback = 0) => {
      const parsed = Number(value);
      if (!Number.isFinite(parsed)) return fallback;
      return Math.trunc(parsed);
    };

    const l2Required = Boolean(
      l2Applied.effective_l2_confirm_enabled ||
      l2Applied.l2_requested
    );
    const l2MissingDaysCount = asFiniteInt(
      l2Applied.missing_l2_days_count,
      Array.isArray(l2Applied.missing_l2_days) ? l2Applied.missing_l2_days.length : 0,
    );
    const l2HasData = l2Applied.has_l2 === true;
    const l2Status = !l2Required
      ? "disabled"
      : (l2HasData && l2MissingDaysCount === 0 ? "ready" : "missing");

    const tcbboEnabled = l2Applied.tcbbo_gate_enabled === true;
    const tcbboAvailable = l2Applied.tcbbo_available === true;
    const tcbboBarsEnriched = asFiniteInt(l2Applied.tcbbo_bars_enriched);
    const tcbboStatus = !tcbboEnabled
      ? "disabled"
      : (tcbboAvailable && tcbboBarsEnriched > 0 ? "ready" : "missing");

    const notes: string[] = [];
    if (l2Status === "missing" && l2MissingDaysCount > 0) {
      const preview = Array.isArray(l2Applied.missing_l2_days)
        ? l2Applied.missing_l2_days.slice(0, 3).join(", ")
        : "";
      notes.push(
        `L2 missing ${l2MissingDaysCount} day(s)${preview ? `: ${preview}` : ""}`,
      );
    } else if (l2Status === "missing") {
      notes.push("L2 requested but not loaded");
    }
    if (tcbboStatus === "missing") {
      const reason = String(l2Applied.tcbbo_missing_reason || "").trim();
      const reasonLabelMap: Record<string, string> = {
        tcbbo_file_not_found: "TCBBO parquet not found",
        tcbbo_build_failed: "TCBBO parse/build failed",
        tcbbo_no_feature_rows: "TCBBO produced no feature rows",
        tcbbo_no_bar_overlap: "TCBBO has no overlap with bars",
      };
      notes.push(reasonLabelMap[reason] || "TCBBO data missing");
    }

    return {
      l2: {
        status: l2Status,
        label:
          l2Status === "ready" ? "Ready" : l2Status === "missing" ? "Missing" : "Disabled",
        detail:
          l2Status === "ready"
            ? `${asFiniteInt(l2Applied.bars_with_l2)}/${asFiniteInt(l2Applied.bars_total)} bars`
            : undefined,
      },
      tcbbo: {
        status: tcbboStatus,
        label:
          tcbboStatus === "ready"
            ? "Ready"
            : tcbboStatus === "missing"
              ? "Missing"
              : "Disabled",
        detail:
          tcbboStatus === "ready"
            ? `${tcbboBarsEnriched}/${asFiniteInt(l2Applied.tcbbo_bars_total)} bars`
            : undefined,
      },
      notes,
    };
  })();

  const statusBadgeStyle = (status: string) => {
    if (status === "ready") {
      return {
        color: "var(--accent-green)",
        background: "rgba(34, 197, 94, 0.12)",
        border: "1px solid rgba(34, 197, 94, 0.25)",
      };
    }
    if (status === "missing") {
      return {
        color: "var(--accent-red)",
        background: "rgba(239, 68, 68, 0.12)",
        border: "1px solid rgba(239, 68, 68, 0.25)",
      };
    }
    return {
      color: "var(--text-muted)",
      background: "var(--bg-tertiary)",
      border: "1px solid var(--border-color)",
    };
  };
  
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

        {dataCoverage && (
          <div
            style={{
              padding: "var(--spacing-sm) var(--spacing-md)",
              background: "var(--bg-tertiary)",
              borderRadius: "var(--border-radius-sm)",
              marginBottom: "var(--spacing-md)",
              border: "1px solid var(--border-color)",
            }}
          >
            <div style={{ color: "var(--text-muted)", fontSize: "0.75rem", marginBottom: "6px" }}>
              Data Coverage (L2 + TCBBO)
            </div>
            {(["l2", "tcbbo"] as const).map((key) => {
              const row = dataCoverage[key];
              return (
                <div
                  key={key}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    gap: "8px",
                    marginTop: key === "l2" ? 0 : "6px",
                  }}
                >
                  <div style={{ display: "flex", flexDirection: "column" }}>
                    <span style={{ fontWeight: 500 }}>{key.toUpperCase()}</span>
                    {row.detail ? (
                      <span style={{ color: "var(--text-muted)", fontSize: "0.72rem" }}>
                        {row.detail}
                      </span>
                    ) : null}
                  </div>
                  <span
                    style={{
                      padding: "2px 8px",
                      borderRadius: 999,
                      fontSize: "0.72rem",
                      fontWeight: 600,
                      ...statusBadgeStyle(row.status),
                    }}
                  >
                    {row.label}
                  </span>
                </div>
              );
            })}
            {dataCoverage.notes.length > 0 && (
              <div style={{ marginTop: "8px", display: "flex", flexDirection: "column", gap: "4px" }}>
                {dataCoverage.notes.map((note, idx) => (
                  <div key={`${note}-${idx}`} style={{ color: "var(--accent-red)", fontSize: "0.75rem" }}>
                    {note}
                  </div>
                ))}
              </div>
            )}
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
