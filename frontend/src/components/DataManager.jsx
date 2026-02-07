import { useState, useEffect, useCallback, useMemo } from 'react';

function DataManager({ downloadProgress }) {
    const [catalog, setCatalog] = useState([]);
    const [settings, setSettings] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [downloading, setDownloading] = useState(false);
    const [costEstimate, setCostEstimate] = useState(null);
    const [estimating, setEstimating] = useState(false);
    const [scanning, setScanning] = useState(false);
    const [confirmDelete, setConfirmDelete] = useState(null);
    const [savingApiKey, setSavingApiKey] = useState(false);
    const [savingRoots, setSavingRoots] = useState(false);

    const [apiKeyInput, setApiKeyInput] = useState('');
    const [rootsForm, setRootsForm] = useState({
        ohlcv_data_dirs: '',
        l2_data_dirs: '',
    });

    const [filters, setFilters] = useState({
        ticker: '',
        schema: 'all',
        format: 'all',
        source: 'all',
        managed: 'all',
    });

    const [form, setForm] = useState({
        ticker: 'MU',
        schema: 'mbp-10',
        start_date: '',
        end_date: '',
        dataset: 'XNAS.ITCH',
        convert_to_parquet: true,
    });

    // Set default dates (yesterday)
    useEffect(() => {
        const today = new Date();
        const yesterday = new Date(today);
        yesterday.setDate(yesterday.getDate() - 1);
        const twoDaysAgo = new Date(today);
        twoDaysAgo.setDate(twoDaysAgo.getDate() - 2);

        const fmt = (d) => d.toISOString().split('T')[0];
        setForm((prev) => ({
            ...prev,
            start_date: prev.start_date || fmt(twoDaysAgo),
            end_date: prev.end_date || fmt(yesterday),
        }));
    }, []);

    const fetchCatalog = useCallback(async (refresh = false) => {
        try {
            setLoading(true);
            const query = refresh ? '?refresh=true' : '';
            const resp = await fetch(`/api/data-loader/catalog${query}`);
            if (resp.ok) {
                const data = await resp.json();
                setCatalog(Array.isArray(data) ? data : []);
            } else {
                setError('Failed to fetch catalog');
            }
        } catch (e) {
            setError(`Fetch error: ${e.message}`);
        } finally {
            setLoading(false);
        }
    }, []);

    const fetchSettings = useCallback(async () => {
        try {
            const resp = await fetch('/api/data-loader/settings');
            if (!resp.ok) {
                setError('Failed to fetch data settings');
                return;
            }
            const data = await resp.json();
            setSettings(data);
            setRootsForm({
                ohlcv_data_dirs: (data.ohlcv_data_dirs || []).join('\n'),
                l2_data_dirs: (data.l2_data_dirs || []).join('\n'),
            });
        } catch (e) {
            setError(`Settings error: ${e.message}`);
        }
    }, []);

    useEffect(() => {
        fetchCatalog();
        fetchSettings();
    }, [fetchCatalog, fetchSettings]);

    // Refresh catalog when download completes
    useEffect(() => {
        if (downloadProgress?.status === 'ready' || downloadProgress?.status === 'error') {
            fetchCatalog();
            setDownloading(false);
        }
    }, [downloadProgress, fetchCatalog]);

    // Map frontend form to API payload (schema -> data_schema)
    const toApiPayload = (f) => ({
        ticker: f.ticker,
        data_schema: f.schema,
        start_date: f.start_date,
        end_date: f.end_date,
        dataset: f.dataset,
        convert_to_parquet: f.convert_to_parquet,
    });

    const handleEstimateCost = async () => {
        setEstimating(true);
        setCostEstimate(null);
        setError(null);
        try {
            const resp = await fetch('/api/data-loader/cost-estimate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(toApiPayload(form)),
            });
            if (resp.ok) {
                const data = await resp.json();
                setCostEstimate(data);
            } else {
                const err = await resp.json();
                setError(err.detail || 'Cost estimate failed');
            }
        } catch (e) {
            setError(`Estimate error: ${e.message}`);
        } finally {
            setEstimating(false);
        }
    };

    const handleDownload = async () => {
        setDownloading(true);
        setError(null);
        setCostEstimate(null);
        try {
            const resp = await fetch('/api/data-loader/download', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(toApiPayload(form)),
            });
            if (resp.ok) {
                const data = await resp.json();
                if (data.status === 'already_exists') {
                    setError('Data already exists in catalog');
                    setDownloading(false);
                }
                // Otherwise, download started - wait for WS updates.
            } else {
                const err = await resp.json();
                setError(err.detail || 'Download failed');
                setDownloading(false);
            }
        } catch (e) {
            setError(`Download error: ${e.message}`);
            setDownloading(false);
        }
    };

    const handleDelete = async (entry) => {
        try {
            const resp = await fetch('/api/data-loader/entry', {
                method: 'DELETE',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    ticker: entry.ticker,
                    data_schema: entry.schema,
                    start_date: entry.start_date,
                    end_date: entry.end_date,
                }),
            });
            if (resp.ok) {
                setConfirmDelete(null);
                fetchCatalog();
            } else {
                const err = await resp.json();
                setError(err.detail || 'Delete failed');
            }
        } catch (e) {
            setError(`Delete error: ${e.message}`);
        }
    };

    const handleScan = async () => {
        setScanning(true);
        setError(null);
        try {
            const resp = await fetch('/api/data-loader/scan', { method: 'POST' });
            if (resp.ok) {
                await fetchCatalog(true);
            } else {
                const err = await resp.json();
                setError(err.detail || 'Scan failed');
            }
        } catch (e) {
            setError(`Scan error: ${e.message}`);
        } finally {
            setScanning(false);
        }
    };

    const handleSaveApiKey = async () => {
        setSavingApiKey(true);
        setError(null);
        try {
            const resp = await fetch('/api/data-loader/api-key', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ api_key: apiKeyInput }),
            });
            if (!resp.ok) {
                const err = await resp.json();
                throw new Error(err.detail || 'Failed to save API key');
            }
            const data = await resp.json();
            setSettings(data);
            setApiKeyInput('');
        } catch (e) {
            setError(`API key error: ${e.message}`);
        } finally {
            setSavingApiKey(false);
        }
    };

    const handleSaveRoots = async () => {
        setSavingRoots(true);
        setError(null);
        try {
            const parseLines = (value) =>
                value
                    .split('\n')
                    .map((line) => line.trim())
                    .filter(Boolean);

            const payload = {
                ohlcv_data_dirs: parseLines(rootsForm.ohlcv_data_dirs),
                l2_data_dirs: parseLines(rootsForm.l2_data_dirs),
            };

            const resp = await fetch('/api/data-loader/settings', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            if (!resp.ok) {
                const err = await resp.json();
                throw new Error(err.detail || 'Failed to update data roots');
            }

            const data = await resp.json();
            setSettings(data);
            setRootsForm({
                ohlcv_data_dirs: (data.ohlcv_data_dirs || []).join('\n'),
                l2_data_dirs: (data.l2_data_dirs || []).join('\n'),
            });
            await fetchCatalog(true);
        } catch (e) {
            setError(`Root settings error: ${e.message}`);
        } finally {
            setSavingRoots(false);
        }
    };

    const formatSize = (bytes) => {
        if (!bytes) return '-';
        const mb = bytes / (1024 * 1024);
        return mb >= 1000 ? `${(mb / 1024).toFixed(1)} GB` : `${mb.toFixed(1)} MB`;
    };

    const formatRows = (count) => {
        if (!count) return '-';
        if (count >= 1_000_000) return `${(count / 1_000_000).toFixed(1)}M`;
        if (count >= 1_000) return `${(count / 1_000).toFixed(1)}K`;
        return count.toLocaleString();
    };

    const schemaLabel = (schema) => {
        const labels = {
            'mbp-10': 'L2 Depth',
            'ohlcv-1m': 'OHLCV 1m',
            trades: 'Trades',
        };
        return labels[schema] || schema;
    };

    const catalogWithFormats = useMemo(
        () =>
            catalog.map((entry) => ({
                ...entry,
                managed: entry.managed !== false,
                formats:
                    entry.formats ||
                    [
                        entry.file_mbn ? 'mbn' : null,
                        entry.file_parquet ? 'parquet' : null,
                        entry.file_csv ? 'csv' : null,
                    ].filter(Boolean),
            })),
        [catalog]
    );

    const sourceOptions = useMemo(() => {
        const values = new Set(
            catalogWithFormats.map((entry) => entry.source_root).filter(Boolean)
        );
        return Array.from(values).sort();
    }, [catalogWithFormats]);

    const filteredCatalog = useMemo(() => {
        return catalogWithFormats.filter((entry) => {
            if (filters.ticker && entry.ticker !== filters.ticker) return false;
            if (filters.schema !== 'all' && entry.schema !== filters.schema) return false;
            if (filters.format !== 'all' && !entry.formats.includes(filters.format)) return false;
            if (filters.source !== 'all' && entry.source_root !== filters.source) return false;
            if (filters.managed !== 'all') {
                if (filters.managed === 'managed' && entry.managed === false) return false;
                if (filters.managed === 'external' && entry.managed !== false) return false;
            }
            return true;
        });
    }, [catalogWithFormats, filters]);

    const tickerOptions = useMemo(
        () => Array.from(new Set(catalogWithFormats.map((entry) => entry.ticker))).sort(),
        [catalogWithFormats]
    );

    const schemaOptions = useMemo(
        () => Array.from(new Set(catalogWithFormats.map((entry) => entry.schema))).sort(),
        [catalogWithFormats]
    );

    return (
        <div className="data-manager">
            <div className="dm-main-row">
                {/* Download + Settings */}
                <div className="card dm-download-card">
                    <div className="card-header">
                        <span className="card-title">Data Hub</span>
                    </div>
                    <div className="card-body">
                        <div className="dm-section-title">Databento API Key</div>
                        <div className="form-group">
                            <label>Stored Key</label>
                            <div className="dm-hint-row">
                                {settings?.databento_api_key_set
                                    ? `${settings.databento_api_key_hint} (${settings.databento_api_key_source})`
                                    : 'Not configured'}
                            </div>
                        </div>
                        <div className="form-group">
                            <label>API Key</label>
                            <input
                                type="password"
                                value={apiKeyInput}
                                onChange={(e) => setApiKeyInput(e.target.value)}
                                placeholder="db-..."
                            />
                        </div>
                        <div className="dm-btn-row">
                            <button
                                className="btn btn-secondary"
                                onClick={handleSaveApiKey}
                                disabled={savingApiKey}
                            >
                                {savingApiKey ? 'Saving...' : 'Save API Key'}
                            </button>
                        </div>

                        <div className="dm-section-title">Data Roots (One Place)</div>
                        <div className="form-group">
                            <label>OHLCV Roots (one path per line)</label>
                            <textarea
                                className="dm-textarea"
                                value={rootsForm.ohlcv_data_dirs}
                                onChange={(e) =>
                                    setRootsForm((prev) => ({ ...prev, ohlcv_data_dirs: e.target.value }))
                                }
                                rows={3}
                            />
                        </div>
                        <div className="form-group">
                            <label>L2 Roots (one path per line)</label>
                            <textarea
                                className="dm-textarea"
                                value={rootsForm.l2_data_dirs}
                                onChange={(e) =>
                                    setRootsForm((prev) => ({ ...prev, l2_data_dirs: e.target.value }))
                                }
                                rows={3}
                            />
                        </div>
                        <div className="dm-btn-row">
                            <button
                                className="btn btn-secondary"
                                onClick={handleSaveRoots}
                                disabled={savingRoots}
                            >
                                {savingRoots ? 'Saving...' : 'Save Roots'}
                            </button>
                        </div>

                        <div className="dm-section-title">Download Data</div>
                        <div className="form-group">
                            <label>Ticker</label>
                            <input
                                type="text"
                                value={form.ticker}
                                onChange={(e) => setForm({ ...form, ticker: e.target.value.toUpperCase() })}
                                placeholder="MU"
                            />
                        </div>
                        <div className="form-group">
                            <label>Schema</label>
                            <select
                                value={form.schema}
                                onChange={(e) => setForm({ ...form, schema: e.target.value })}
                            >
                                <option value="mbp-10">L2 Depth (MBP-10)</option>
                                <option value="ohlcv-1m">OHLCV 1-Min</option>
                                <option value="trades">Raw Trades</option>
                            </select>
                        </div>
                        <div className="form-group">
                            <label>Dataset</label>
                            <select
                                value={form.dataset}
                                onChange={(e) => setForm({ ...form, dataset: e.target.value })}
                            >
                                <option value="XNAS.ITCH">XNAS.ITCH (Nasdaq TotalView)</option>
                                <option value="XNAS.BASIC">XNAS.BASIC (Nasdaq Basic + NLS)</option>
                            </select>
                        </div>
                        <div className="dm-date-row">
                            <div className="form-group">
                                <label>Start Date</label>
                                <input
                                    type="date"
                                    value={form.start_date}
                                    onChange={(e) => setForm({ ...form, start_date: e.target.value })}
                                />
                            </div>
                            <div className="form-group">
                                <label>End Date</label>
                                <input
                                    type="date"
                                    value={form.end_date}
                                    onChange={(e) => setForm({ ...form, end_date: e.target.value })}
                                />
                            </div>
                        </div>
                        {form.schema !== 'ohlcv-1m' && (
                            <div className="form-group dm-checkbox">
                                <label>
                                    <input
                                        type="checkbox"
                                        checked={form.convert_to_parquet}
                                        onChange={(e) => setForm({ ...form, convert_to_parquet: e.target.checked })}
                                    />
                                    Convert to Parquet
                                </label>
                            </div>
                        )}

                        {error && <div className="dm-error">{error}</div>}

                        {costEstimate && (
                            <div className="dm-cost-box">
                                <span>Estimated Cost:</span>
                                <strong>${costEstimate.estimated_cost_usd?.toFixed(4)}</strong>
                            </div>
                        )}

                        {downloading && downloadProgress && (
                            <div className="dm-progress-box">
                                <div className="dm-progress-text">{downloadProgress.message}</div>
                                <div className="dm-progress-bar">
                                    <div
                                        className="dm-progress-fill"
                                        style={{ width: `${downloadProgress.status === 'downloading' ? 50 : 100}%` }}
                                    />
                                </div>
                            </div>
                        )}

                        <div className="dm-btn-row">
                            <button
                                className="btn btn-secondary"
                                onClick={handleEstimateCost}
                                disabled={estimating || downloading || !form.start_date || !form.end_date}
                            >
                                {estimating ? 'Estimating...' : 'Cost Estimate'}
                            </button>
                            <button
                                className="btn"
                                onClick={handleDownload}
                                disabled={downloading || !form.start_date || !form.end_date}
                            >
                                {downloading ? 'Downloading...' : 'Download'}
                            </button>
                        </div>
                    </div>
                </div>

                {/* Catalog Table */}
                <div className="card dm-catalog-card">
                    <div className="card-header">
                        <span className="card-title">Unified Data Catalog</span>
                        <div className="dm-header-actions">
                            <button
                                className="btn btn-secondary btn-sm"
                                onClick={handleScan}
                                disabled={scanning}
                            >
                                {scanning ? 'Scanning...' : 'Scan Files'}
                            </button>
                            <button
                                className="btn btn-secondary btn-sm"
                                onClick={() => fetchCatalog()}
                                disabled={loading}
                            >
                                Refresh
                            </button>
                        </div>
                    </div>

                    <div className="card-body dm-filter-bar">
                        <div className="form-group">
                            <label>Ticker</label>
                            <select
                                value={filters.ticker}
                                onChange={(e) => setFilters((prev) => ({ ...prev, ticker: e.target.value }))}
                            >
                                <option value="">All</option>
                                {tickerOptions.map((ticker) => (
                                    <option key={ticker} value={ticker}>
                                        {ticker}
                                    </option>
                                ))}
                            </select>
                        </div>
                        <div className="form-group">
                            <label>Schema</label>
                            <select
                                value={filters.schema}
                                onChange={(e) => setFilters((prev) => ({ ...prev, schema: e.target.value }))}
                            >
                                <option value="all">All</option>
                                {schemaOptions.map((schema) => (
                                    <option key={schema} value={schema}>
                                        {schemaLabel(schema)}
                                    </option>
                                ))}
                            </select>
                        </div>
                        <div className="form-group">
                            <label>Format</label>
                            <select
                                value={filters.format}
                                onChange={(e) => setFilters((prev) => ({ ...prev, format: e.target.value }))}
                            >
                                <option value="all">All</option>
                                <option value="mbn">MBN</option>
                                <option value="parquet">Parquet</option>
                                <option value="csv">CSV</option>
                            </select>
                        </div>
                        <div className="form-group">
                            <label>Source</label>
                            <select
                                value={filters.source}
                                onChange={(e) => setFilters((prev) => ({ ...prev, source: e.target.value }))}
                            >
                                <option value="all">All</option>
                                {sourceOptions.map((source) => (
                                    <option key={source} value={source}>
                                        {source}
                                    </option>
                                ))}
                            </select>
                        </div>
                        <div className="form-group">
                            <label>Ownership</label>
                            <select
                                value={filters.managed}
                                onChange={(e) => setFilters((prev) => ({ ...prev, managed: e.target.value }))}
                            >
                                <option value="all">All</option>
                                <option value="managed">Managed</option>
                                <option value="external">External</option>
                            </select>
                        </div>
                    </div>

                    <div className="card-body dm-table-container">
                        {!loading && catalogWithFormats.length === 0 ? (
                            <div className="dm-empty">
                                No data found. Click &quot;Scan Files&quot; to detect existing files or download new data.
                            </div>
                        ) : !loading && filteredCatalog.length === 0 ? (
                            <div className="dm-empty">
                                No rows match current filters.
                            </div>
                        ) : (
                            <table className="data-table">
                                <thead>
                                    <tr>
                                        <th>Ticker</th>
                                        <th>Schema</th>
                                        <th>Date Range</th>
                                        <th>Format</th>
                                        <th>Source</th>
                                        <th>Size</th>
                                        <th>Rows</th>
                                        <th>Status</th>
                                        <th>Actions</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {loading && (
                                        <tr>
                                            <td className="dm-loading-cell" colSpan={9}>
                                                {catalogWithFormats.length === 0 ? 'Loading catalog...' : 'Refreshing catalog...'}
                                            </td>
                                        </tr>
                                    )}
                                    {filteredCatalog.map((entry, i) => (
                                        <tr key={`${entry.ticker}-${entry.schema}-${entry.start_date}-${entry.end_date}-${i}`}>
                                            <td className="dm-ticker">{entry.ticker}</td>
                                            <td>
                                                <span className="schema-badge">{schemaLabel(entry.schema)}</span>
                                            </td>
                                            <td className="dm-dates">
                                                {entry.start_date}
                                                <span className="dm-date-arrow">&rarr;</span>
                                                {entry.end_date}
                                            </td>
                                            <td className="dm-files">
                                                {entry.file_mbn && <span className="file-badge mbn">MBN</span>}
                                                {entry.file_parquet && <span className="file-badge parquet">PQ</span>}
                                                {entry.file_csv && <span className="file-badge csv">CSV</span>}
                                            </td>
                                            <td className="dm-source">{entry.source_root || '-'}</td>
                                            <td>{formatSize(entry.size_bytes)}</td>
                                            <td>{formatRows(entry.row_count)}</td>
                                            <td>
                                                <span className={`status-badge ${entry.status}`}>
                                                    {entry.status}
                                                </span>
                                            </td>
                                            <td>
                                                {entry.managed === false ? (
                                                    <span className="dm-readonly-tag">External</span>
                                                ) : confirmDelete === i ? (
                                                    <div className="dm-confirm-delete">
                                                        <button
                                                            className="btn btn-danger btn-sm"
                                                            onClick={() => handleDelete(entry)}
                                                        >
                                                            Confirm
                                                        </button>
                                                        <button
                                                            className="btn btn-secondary btn-sm"
                                                            onClick={() => setConfirmDelete(null)}
                                                        >
                                                            Cancel
                                                        </button>
                                                    </div>
                                                ) : (
                                                    <button
                                                        className="btn btn-danger btn-sm"
                                                        onClick={() => setConfirmDelete(i)}
                                                    >
                                                        Delete
                                                    </button>
                                                )}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}

export default DataManager;
