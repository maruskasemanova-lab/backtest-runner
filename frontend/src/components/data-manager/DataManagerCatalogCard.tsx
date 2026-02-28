import type { Dispatch, SetStateAction } from "react";
import { formatRows, formatSize, schemaIcon, schemaLabel } from "./dataManagerUtils";

interface DataManagerCatalogCardProps {
  loading: boolean;
  scanning: boolean;
  catalogWithFormats: any[];
  filteredCatalog: any[];
  filters: Record<string, string>;
  setFilters: Dispatch<SetStateAction<Record<string, string>>>;
  tickerOptions: string[];
  schemaOptions: string[];
  sourceOptions: string[];
  confirmDelete: number | null;
  setConfirmDelete: Dispatch<SetStateAction<number | null>>;
  onDelete: (entry: any) => void;
  onScan: () => void;
  onRefresh: () => void;
}

export default function DataManagerCatalogCard({
  loading,
  scanning,
  catalogWithFormats,
  filteredCatalog,
  filters,
  setFilters,
  tickerOptions,
  schemaOptions,
  sourceOptions,
  confirmDelete,
  setConfirmDelete,
  onDelete,
  onScan,
  onRefresh,
}: DataManagerCatalogCardProps) {
  return (
    <div className="card dm-catalog-card">
      <div className="card-header">
        <span className="card-title">📁 Data Catalog</span>
        <div className="dm-header-actions">
          <button className="btn btn-secondary btn-sm" onClick={onScan} disabled={scanning}>
            {scanning ? "⏳" : "🔍"} Scan
          </button>
          <button className="btn btn-secondary btn-sm" onClick={onRefresh} disabled={loading}>
            ↻ Refresh
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
            <div className="dm-empty-icon">📭</div>
            <div>
              No data found. Click &quot;Scan&quot; to detect existing files or download new data.
            </div>
          </div>
        ) : !loading && filteredCatalog.length === 0 ? (
          <div className="dm-empty">No rows match current filters.</div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Ticker</th>
                <th>Schema</th>
                <th>Date Range</th>
                <th>Format</th>
                <th>Size</th>
                <th>Rows</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr>
                  <td className="dm-loading-cell" colSpan={8}>
                    {catalogWithFormats.length === 0 ? "Loading catalog..." : "Refreshing..."}
                  </td>
                </tr>
              )}
              {filteredCatalog.map((entry, i) => (
                <tr key={`${entry.ticker}-${entry.schema}-${entry.start_date}-${entry.end_date}-${i}`}>
                  <td className="dm-ticker">{entry.ticker}</td>
                  <td>
                    <span className="schema-badge">
                      {schemaIcon(entry.schema)} {schemaLabel(entry.schema)}
                    </span>
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
                  <td>{formatSize(entry.size_bytes)}</td>
                  <td>{formatRows(entry.row_count)}</td>
                  <td>
                    <span className={`status-badge ${entry.status}`}>{entry.status}</span>
                  </td>
                  <td>
                    {entry.managed === false ? (
                      <span className="dm-readonly-tag">External</span>
                    ) : confirmDelete === i ? (
                      <div className="dm-confirm-delete">
                        <button className="btn btn-danger btn-sm" onClick={() => onDelete(entry)}>
                          Confirm
                        </button>
                        <button className="btn btn-secondary btn-sm" onClick={() => setConfirmDelete(null)}>
                          ✕
                        </button>
                      </div>
                    ) : (
                      <button className="btn btn-danger btn-sm" onClick={() => setConfirmDelete(i)}>
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
  );
}
