import { useEffect, useMemo, useState } from 'react';

const STREAM_OPTIONS = [
  { value: 'decisions', label: 'Decisions' },
  { value: 'signals', label: 'Signals' },
  { value: 'orders', label: 'Orders' },
  { value: 'runtime', label: 'Runtime' },
];

const formatTs = (value) => {
  if (!value) return '-';
  const parsed = Date.parse(String(value));
  if (Number.isNaN(parsed)) return String(value);
  return new Date(parsed).toLocaleString();
};

const parseJsonSafe = (text) => {
  const payloadText = String(text || '').trim();
  if (!payloadText) return {};
  try {
    return JSON.parse(payloadText);
  } catch {
    return {};
  }
};

const readJsonPayload = async (resp) => {
  const text = await resp.text();
  return parseJsonSafe(text);
};

function LiveTraderMonitor() {
  const [runs, setRuns] = useState([]);
  const [selectedRunId, setSelectedRunId] = useState('');
  const [activeOnly, setActiveOnly] = useState(false);
  const [stream, setStream] = useState('decisions');
  const [limit, setLimit] = useState(120);
  const [events, setEvents] = useState([]);
  const [snapshot, setSnapshot] = useState(null);
  const [loadingRuns, setLoadingRuns] = useState(false);
  const [loadingData, setLoadingData] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;

    const fetchRuns = async () => {
      setLoadingRuns(true);
      try {
        const runsUrl = `/api/live-trader/runs?limit=40&active_only=${activeOnly ? 'true' : 'false'}`;
        const resp = await fetch(runsUrl);
        const payload = await readJsonPayload(resp);
        if (!resp.ok) {
          throw new Error(payload?.detail || `HTTP ${resp.status}`);
        }
        if (cancelled) return;
        const nextRuns = Array.isArray(payload?.runs) ? payload.runs : [];
        setRuns(nextRuns);
        setSelectedRunId((prev) => {
          if (prev && nextRuns.some((item) => item.run_id === prev)) {
            return prev;
          }
          return nextRuns[0]?.run_id || '';
        });
      } catch (err) {
        if (!cancelled) {
          setError(`Failed to fetch live runs: ${err.message}`);
        }
      } finally {
        if (!cancelled) setLoadingRuns(false);
      }
    };

    fetchRuns();
    const timer = setInterval(fetchRuns, 4000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [activeOnly]);

  useEffect(() => {
    if (!selectedRunId) {
      setEvents([]);
      setSnapshot(null);
      return;
    }

    let cancelled = false;

    const fetchData = async () => {
      setLoadingData(true);
      setError(null);
      try {
        const [snapshotResp, eventsResp] = await Promise.all([
          fetch(`/api/live-trader/snapshot/${encodeURIComponent(selectedRunId)}?tail_limit=${Math.max(50, Number(limit) || 120)}`),
          fetch(`/api/live-trader/events/${encodeURIComponent(selectedRunId)}?stream=${encodeURIComponent(stream)}&limit=${Math.max(1, Number(limit) || 120)}`),
        ]);

        const [snapshotPayload, eventsPayload] = await Promise.all([
          readJsonPayload(snapshotResp),
          readJsonPayload(eventsResp),
        ]);

        if (!snapshotResp.ok) {
          throw new Error(snapshotPayload?.detail || `Snapshot HTTP ${snapshotResp.status}`);
        }
        if (!eventsResp.ok && eventsResp.status !== 404) {
          throw new Error(eventsPayload?.detail || `Events HTTP ${eventsResp.status}`);
        }

        if (cancelled) return;
        setSnapshot(snapshotPayload);
        setEvents(eventsResp.status === 404 ? [] : (Array.isArray(eventsPayload?.events) ? eventsPayload.events : []));
      } catch (err) {
        if (!cancelled) {
          setError(`Failed to fetch live stream: ${err.message}`);
        }
      } finally {
        if (!cancelled) setLoadingData(false);
      }
    };

    fetchData();
    const timer = setInterval(fetchData, 2000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [selectedRunId, stream, limit]);

  const selectedRunMeta = useMemo(
    () => runs.find((row) => row.run_id === selectedRunId) || null,
    [runs, selectedRunId]
  );

  const runtimeLatest = snapshot?.runtime || snapshot?.streams?.runtime?.latest || null;
  const executionConfig = runtimeLatest?.execution_config || {};
  const latestDecision = snapshot?.streams?.decisions?.latest || null;
  const latestOrder = snapshot?.streams?.orders?.latest || null;

  return (
    <main className="live-monitor-layout">
      <section className="card live-monitor-card">
        <div className="card-header">
          <span className="card-title">Live Trader Stream</span>
          <span className="live-monitor-muted">
            {loadingRuns ? 'Loading runs...' : `${runs.length} runs discovered (artifact history)`}
          </span>
        </div>
        <div className="card-body live-monitor-controls">
          <div className="form-group">
            <label htmlFor="live_run_id">Run ID</label>
            <select
              id="live_run_id"
              value={selectedRunId}
              onChange={(e) => setSelectedRunId(e.target.value)}
              disabled={!runs.length}
            >
              {!runs.length ? <option value="">No runs found</option> : null}
              {runs.map((run) => (
                <option key={run.run_id} value={run.run_id}>
                  {run.run_id} [{run.status || 'unknown'}]{run.ticker ? ` ${run.ticker}` : ''}
                </option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label htmlFor="live_stream">Stream</label>
            <select id="live_stream" value={stream} onChange={(e) => setStream(e.target.value)}>
              {STREAM_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label htmlFor="live_limit">Rows</label>
            <input
              id="live_limit"
              type="number"
              min={20}
              max={500}
              value={limit}
              onChange={(e) => setLimit(Number(e.target.value || 120))}
            />
          </div>

          <div className="form-group">
            <label htmlFor="live_active_only">Run Filter</label>
            <label className="live-checkbox" htmlFor="live_active_only">
              <input
                id="live_active_only"
                type="checkbox"
                checked={activeOnly}
                onChange={(e) => setActiveOnly(Boolean(e.target.checked))}
              />
              Active only
            </label>
          </div>
        </div>
      </section>

      <section className="card live-monitor-card">
        <div className="card-header">
          <span className="card-title">Runtime Snapshot</span>
          <span className="live-monitor-muted">{loadingData ? 'Refreshing...' : formatTs(snapshot?.updated_at || selectedRunMeta?.updated_at)}</span>
        </div>
        <div className="card-body live-monitor-grid">
          <div className="live-stat">
            <div className="live-stat-value">{snapshot?.streams?.runtime?.count ?? 0}</div>
            <div className="live-stat-label">Runtime Rows</div>
          </div>
          <div className="live-stat">
            <div className="live-stat-value">{snapshot?.streams?.decisions?.count ?? 0}</div>
            <div className="live-stat-label">Decisions</div>
          </div>
          <div className="live-stat">
            <div className="live-stat-value">{snapshot?.streams?.signals?.count ?? 0}</div>
            <div className="live-stat-label">Signals</div>
          </div>
          <div className="live-stat">
            <div className="live-stat-value">{snapshot?.streams?.orders?.count ?? 0}</div>
            <div className="live-stat-label">Orders</div>
          </div>

          <div className="live-meta">
            <strong>Status:</strong>{' '}
            {snapshot?.status || selectedRunMeta?.status || '-'}
          </div>
          <div className="live-meta">
            <strong>Profile:</strong>{' '}
            {runtimeLatest?.active_profile_id || '-'} (selected: {runtimeLatest?.profile_id || '-'})
          </div>
          <div className="live-meta">
            <strong>L2 Source:</strong>{' '}
            {executionConfig?.market_data_source || '-'} / {executionConfig?.source_mode || '-'} /{' '}
            {executionConfig?.databento_dataset || '-'}:{executionConfig?.databento_schema || '-'}
          </div>
          <div className="live-meta">
            <strong>Latest decision:</strong>{' '}
            {latestDecision?.decision?.action || latestDecision?.decision?.phase || '-'}
          </div>
          <div className="live-meta">
            <strong>Latest order:</strong>{' '}
            {latestOrder?.action || '-'} ({latestOrder?.side || '-'})
          </div>
        </div>
      </section>

      <section className="card live-monitor-card live-monitor-table-card">
        <div className="card-header">
          <span className="card-title">{stream} stream</span>
          <span className="live-monitor-muted">{events.length} rows</span>
        </div>
        <div className="card-body live-monitor-table-wrap">
          {error ? <div className="live-monitor-error">{error}</div> : null}
          {!error && !events.length ? <div className="live-monitor-muted">No rows yet.</div> : null}
          {events.length ? (
            <table className="live-monitor-table">
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Action</th>
                  <th>Details</th>
                </tr>
              </thead>
              <tbody>
                {events
                  .slice()
                  .reverse()
                  .map((row, idx) => {
                    const timestamp =
                      row?.timestamp ||
                      row?.decision?.timestamp ||
                      row?.decision?.position_closed?.exit_time ||
                      row?.decision?.position_opened?.entry_time ||
                      row?.bar?.timestamp;
                    const action =
                      row?.action ||
                      row?.decision?.action ||
                      row?.decision?.phase ||
                      row?.signal?.signal ||
                      '-';
                    const detailObj =
                      row?.decision || row?.signal || row?.execution_config || row;
                    return (
                      <tr key={`${idx}-${action}`}>
                        <td>{formatTs(timestamp)}</td>
                        <td>{String(action)}</td>
                        <td>
                          <pre>{JSON.stringify(detailObj, null, 2)}</pre>
                        </td>
                      </tr>
                    );
                  })}
              </tbody>
            </table>
          ) : null}
        </div>
      </section>
    </main>
  );
}

export default LiveTraderMonitor;
