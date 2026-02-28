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
  return (
    <div className="card dm-download-card">
      <div className="card-header">
        <span className="card-title">⬇ Download Data</span>
      </div>
      <div className="card-body">
        <div className="dm-form-grid">
          <div className="dm-form-field dm-field-full">
            <label>Ticker</label>
            <input
              type="text"
              value={form.ticker}
              onChange={(e) => setForm({ ...form, ticker: e.target.value.toUpperCase() })}
              placeholder="MU"
            />
          </div>
          <div className="dm-form-field">
            <label>Schema</label>
            <select
              value={form.schema}
              onChange={(e) => setForm({ ...form, schema: e.target.value })}
            >
              <option value="mbp-10">📊 L2 Depth (MBP-10)</option>
              <option value="ohlcv-1m">📈 OHLCV 1-Min</option>
              <option value="tcbbo">🧩 Options TCBBO (OPRA)</option>
              <option value="trades">⚡ Raw Trades</option>
            </select>
          </div>
          <div className="dm-form-field">
            <label>Dataset</label>
            <select
              value={form.dataset}
              onChange={(e) => setForm({ ...form, dataset: e.target.value })}
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
          </div>
          <div className="dm-form-field">
            <label>Start Date</label>
            <input
              type="date"
              value={form.start_date}
              onChange={(e) => setForm({ ...form, start_date: e.target.value })}
            />
          </div>
          <div className="dm-form-field">
            <label>End Date</label>
            <input
              type="date"
              value={form.end_date}
              onChange={(e) => setForm({ ...form, end_date: e.target.value })}
            />
          </div>
        </div>

        {form.schema !== "ohlcv-1m" && form.schema !== "tcbbo" && (
          <div className="dm-checkbox-row">
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
            className="btn btn-secondary"
            onClick={onEstimateCost}
            disabled={estimating || downloading || !form.start_date || !form.end_date}
          >
            {estimating ? "Estimating..." : "💲 Estimate"}
          </button>
          <button
            className="btn"
            onClick={onDownload}
            disabled={downloading || !form.start_date || !form.end_date}
          >
            {downloading ? "⏳ Downloading..." : "⬇ Download"}
          </button>
        </div>
      </div>
    </div>
  );
}
