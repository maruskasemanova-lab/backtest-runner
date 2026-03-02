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
  const shownCount = filteredCatalog.length;
  const totalCount = catalogWithFormats.length;

  return (
    <div className="card dm-catalog-card">
      <div className="card-header">
        <span className="card-title">📁 Data Catalog</span>
        <div className="dm-header-actions">
          <button type="button" className="btn btn-secondary btn-sm" onClick={onScan} disabled={scanning}>
            {scanning ? "Scanning..." : "Scan Storage"}
          </button>
          <button type="button" className="btn btn-secondary btn-sm" onClick={onRefresh} disabled={loading}>
            Refresh
          </button>
        </div>
      </div>

      <div className="card-body dm-filter-bar">
        <div className="dm-filter-meta" role="status" aria-live="polite">
          <strong>{shownCount}</strong> of <strong>{totalCount}</strong> datasets visible
        </div>
        <div className="form-group">
          <label htmlFor="dm_catalog_filter_ticker">Ticker</label>
          <select
            id="dm_catalog_filter_ticker"
            name="catalog_ticker"
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
          <label htmlFor="dm_catalog_filter_schema">Schema</label>
          <select
            id="dm_catalog_filter_schema"
            name="catalog_schema"
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
          <label htmlFor="dm_catalog_filter_format">Format</label>
          <select
            id="dm_catalog_filter_format"
            name="catalog_format"
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
          <label htmlFor="dm_catalog_filter_source">Source</label>
          <select
            id="dm_catalog_filter_source"
            name="catalog_source"
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
          <label htmlFor="dm_catalog_filter_managed">Ownership</label>
          <select
            id="dm_catalog_filter_managed"
            name="catalog_managed"
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
            <caption className="sr-only">
              Data catalog entries filtered by ticker, schema, format, source and ownership.
            </caption>
            <thead>
              <tr>
                <th scope="col">Ticker</th>
                <th scope="col">Schema</th>
                <th scope="col">Date Range</th>
                <th scope="col">Format</th>
                <th scope="col">Size</th>
                <th scope="col">Rows</th>
                <th scope="col">Status</th>
                <th scope="col">Actions</th>
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
                        <button
                          type="button"
                          className="btn btn-danger btn-sm"
                          onClick={() => onDelete(entry)}
                          aria-label={`Confirm delete for ${entry.ticker} ${entry.start_date} to ${entry.end_date}`}
                        >
                          Confirm
                        </button>
                        <button
                          type="button"
                          className="btn btn-secondary btn-sm"
                          onClick={() => setConfirmDelete(null)}
                          aria-label="Cancel delete"
                        >
                          ✕
                        </button>
                      </div>
                    ) : (
                      <button
                        type="button"
                        className="btn btn-danger btn-sm"
                        onClick={() => setConfirmDelete(i)}
                        aria-label={`Delete ${entry.ticker} ${entry.start_date} to ${entry.end_date}`}
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
  );
}
