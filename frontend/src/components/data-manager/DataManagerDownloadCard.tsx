import type { Dispatch, SetStateAction } from "react";

interface DataManagerDownloadCardProps {
  form: Record<string, any>;
  setForm: Dispatch<SetStateAction<Record<string, any>>>;
  error: string | null;
  costEstimate: any;
  downloading: boolean;
  downloadProgress: any;
  estimating: boolean;
  onEstimateCost: () => void;
  onDownload: () => void;
}

export default function DataManagerDownloadCard({
  form,
  setForm,
  error,
  costEstimate,
  downloading,
  downloadProgress,
  estimating,
  onEstimateCost,
  onDownload,
}: DataManagerDownloadCardProps) {
  const isParquetEligible = form.schema !== "ohlcv-1m" && form.schema !== "tcbbo";

  return (
    <div className="card dm-download-card">
      <div className="card-header">
        <span className="card-title">⬇ Download Data</span>
      </div>
      <div className="card-body">
        <div className="dm-card-intro">
          Pick the market feed, date coverage and output format first. High-signal inputs stay on
          top, so the download intent is clear before you launch a job.
        </div>

        <div className="dm-form-grid">
          <div className="dm-form-field dm-field-full">
            <label htmlFor="dm_download_ticker">Ticker</label>
            <input
              id="dm_download_ticker"
              name="ticker"
              type="text"
              value={form.ticker}
              onChange={(e) => setForm({ ...form, ticker: e.target.value.toUpperCase() })}
              placeholder="MU"
              aria-describedby="dm_download_ticker_hint"
            />
            <div className="dm-field-hint" id="dm_download_ticker_hint">
              Use a single symbol per request. The value is normalized to uppercase.
            </div>
          </div>
          <div className="dm-form-field">
            <label htmlFor="dm_download_schema">Schema</label>
            <select
              id="dm_download_schema"
              name="schema"
              value={form.schema}
              onChange={(e) => setForm({ ...form, schema: e.target.value })}
              aria-describedby="dm_download_schema_hint"
            >
              <option value="mbp-10">📊 L2 Depth (MBP-10)</option>
              <option value="ohlcv-1m">📈 OHLCV 1-Min</option>
              <option value="tcbbo">🧩 Options TCBBO (OPRA)</option>
              <option value="trades">⚡ Raw Trades</option>
            </select>
            <div className="dm-field-hint" id="dm_download_schema_hint">
              Choose the data shape first. It controls dataset availability and export options.
            </div>
          </div>
          <div className="dm-form-field">
            <label htmlFor="dm_download_dataset">Dataset</label>
            <select
              id="dm_download_dataset"
              name="dataset"
              value={form.dataset}
              onChange={(e) => setForm({ ...form, dataset: e.target.value })}
              aria-describedby="dm_download_dataset_hint"
            >
              {form.schema === "tcbbo" ? (
                <option value="OPRA.PILLAR">OPRA Pillar</option>
              ) : (
                <>
                  <option value="XNAS.ITCH">Nasdaq TotalView</option>
                  <option value="XNAS.BASIC">Nasdaq Basic</option>
                </>
              )}
            </select>
            <div className="dm-field-hint" id="dm_download_dataset_hint">
              Match the venue to the selected schema so downstream storage stays consistent.
            </div>
          </div>
          <div className="dm-form-field">
            <label htmlFor="dm_download_start_date">Start Date</label>
            <input
              id="dm_download_start_date"
              name="start_date"
              type="date"
              value={form.start_date}
              onChange={(e) => setForm({ ...form, start_date: e.target.value })}
            />
          </div>
          <div className="dm-form-field">
            <label htmlFor="dm_download_end_date">End Date</label>
            <input
              id="dm_download_end_date"
              name="end_date"
              type="date"
              value={form.end_date}
              onChange={(e) => setForm({ ...form, end_date: e.target.value })}
            />
          </div>
        </div>

        {isParquetEligible && (
          <div className="dm-checkbox-row dm-toggle-card">
            <label htmlFor="dm_download_convert_to_parquet">
              <span className="dm-toggle-copy">
                <strong>Convert to Parquet</strong>
                <span className="dm-field-hint">
                  Keep a faster analytics-ready copy next to the raw download.
                </span>
              </span>
              <input
                id="dm_download_convert_to_parquet"
                name="convert_to_parquet"
                type="checkbox"
                checked={form.convert_to_parquet}
                onChange={(e) => setForm({ ...form, convert_to_parquet: e.target.checked })}
              />
            </label>
          </div>
        )}

        {error && <div className="dm-error">{error}</div>}

        {costEstimate && (
          <div className="dm-cost-box">
            <span>Estimated Cost</span>
            <strong>${costEstimate.estimated_cost_usd?.toFixed(4)}</strong>
          </div>
        )}

        {downloading && downloadProgress && (
          <div className="dm-progress-box">
            <div className="dm-progress-text">{downloadProgress.message}</div>
            <div className="dm-progress-bar">
              <div
                className="dm-progress-fill"
                style={{ width: `${downloadProgress.status === "downloading" ? 50 : 100}%` }}
              />
            </div>
          </div>
        )}

        <div className="dm-btn-row">
          <button
            type="button"
            className="btn btn-secondary"
            onClick={onEstimateCost}
            disabled={estimating || downloading || !form.start_date || !form.end_date}
          >
            {estimating ? "Estimating..." : "Estimate Cost"}
          </button>
          <button
            type="button"
            className="btn btn-primary"
            onClick={onDownload}
            disabled={downloading || !form.start_date || !form.end_date}
          >
            {downloading ? "Downloading..." : "Start Download"}
          </button>
        </div>
      </div>
    </div>
  );
}
