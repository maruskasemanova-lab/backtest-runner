import { useState, useEffect, useCallback, useMemo } from "react";
import DataManagerCatalogCard from "./data-manager/DataManagerCatalogCard";
import DataManagerDownloadCard from "./data-manager/DataManagerDownloadCard";
import DataManagerSettingsCard from "./data-manager/DataManagerSettingsCard";
import {
  DEFAULT_DOWNLOAD_FORM,
  DEFAULT_FILTERS,
  DEFAULT_ROOTS_FORM,
  buildCatalogStats,
  buildCatalogWithFormats,
  buildSchemaOptions,
  buildSourceOptions,
  buildTickerOptions,
  filterCatalogEntries,
  getRecentIsoDateRange,
  parseRootLines,
  readStoredAuthToken,
  toApiPayload,
} from "./data-manager/dataManagerUtils";

function DataManager({ downloadProgress }: { downloadProgress: any }) {
  const [catalog, setCatalog] = useState<any[]>([]);
  const [settings, setSettings] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState(false);
  const [costEstimate, setCostEstimate] = useState<any>(null);
  const [estimating, setEstimating] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState<number | null>(null);
  const [savingApiKey, setSavingApiKey] = useState(false);
  const [savingRoots, setSavingRoots] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);

  const [apiKeyInput, setApiKeyInput] = useState("");
  const [rootsForm, setRootsForm] = useState(DEFAULT_ROOTS_FORM);
  const [filters, setFilters] = useState(DEFAULT_FILTERS);
  const [form, setForm] = useState(DEFAULT_DOWNLOAD_FORM);

  useEffect(() => {
    const { startDate, endDate } = getRecentIsoDateRange();
    setForm((prev) => ({
      ...prev,
      start_date: prev.start_date || startDate,
      end_date: prev.end_date || endDate,
    }));
  }, []);

  const fetchCatalog = useCallback(async (refresh = false) => {
    try {
      setLoading(true);
      const query = refresh ? "?refresh=true" : "";
      const resp = await fetch(`/api/data-loader/catalog${query}`);
      if (resp.ok) {
        const data = await resp.json();
        setCatalog(Array.isArray(data) ? data : []);
      } else {
        setError("Failed to fetch catalog");
      }
    } catch (e: any) {
      setError(`Fetch error: ${e.message}`);
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchSettings = useCallback(async () => {
    try {
      const resp = await fetch("/api/data-loader/settings");
      if (!resp.ok) {
        setError("Failed to fetch data settings");
        return;
      }
      const data = await resp.json();
      setSettings(data);
      setRootsForm({
        ohlcv_data_dirs: (data.ohlcv_data_dirs || []).join("\n"),
        l2_data_dirs: (data.l2_data_dirs || []).join("\n"),
      });
    } catch (e: any) {
      setError(`Settings error: ${e.message}`);
    }
  }, []);

  useEffect(() => {
    fetchCatalog();
    fetchSettings();
  }, [fetchCatalog, fetchSettings]);

  useEffect(() => {
    setForm((prev) => {
      if (prev.schema === "tcbbo") {
        if (prev.dataset === "OPRA.PILLAR") return prev;
        return { ...prev, dataset: "OPRA.PILLAR" };
      }
      if (prev.dataset === "OPRA.PILLAR") {
        return { ...prev, dataset: "XNAS.ITCH" };
      }
      return prev;
    });
  }, [form.schema]);

  useEffect(() => {
    if (downloadProgress?.status === "ready" || downloadProgress?.status === "error") {
      fetchCatalog();
      setDownloading(false);
    }
  }, [downloadProgress, fetchCatalog]);

  const handleEstimateCost = async () => {
    setEstimating(true);
    setCostEstimate(null);
    setError(null);
    try {
      const resp = await fetch("/api/data-loader/cost-estimate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(toApiPayload(form)),
      });
      if (resp.ok) {
        const data = await resp.json();
        setCostEstimate(data);
      } else {
        const err = await resp.json();
        setError(err.detail || "Cost estimate failed");
      }
    } catch (e: any) {
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
      const resp = await fetch("/api/data-loader/download", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(toApiPayload(form)),
      });
      if (resp.ok) {
        const data = await resp.json();
        if (data.status === "already_exists") {
          setError("Data already exists in catalog");
          setDownloading(false);
        }
      } else {
        const err = await resp.json();
        setError(err.detail || "Download failed");
        setDownloading(false);
      }
    } catch (e: any) {
      setError(`Download error: ${e.message}`);
      setDownloading(false);
    }
  };

  const handleDelete = async (entry: any) => {
    try {
      const resp = await fetch("/api/data-loader/entry", {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
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
        setError(err.detail || "Delete failed");
      }
    } catch (e: any) {
      setError(`Delete error: ${e.message}`);
    }
  };

  const handleScan = async () => {
    setScanning(true);
    setError(null);
    try {
      const resp = await fetch("/api/data-loader/scan", { method: "POST" });
      if (resp.ok) {
        await fetchCatalog(true);
      } else {
        const err = await resp.json();
        setError(err.detail || "Scan failed");
      }
    } catch (e: any) {
      setError(`Scan error: ${e.message}`);
    } finally {
      setScanning(false);
    }
  };

  const handleSaveApiKey = async () => {
    setSavingApiKey(true);
    setError(null);
    try {
      const token = readStoredAuthToken();
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (token) {
        headers.Authorization = `Bearer ${token}`;
      }
      const resp = await fetch("/api/data-loader/api-key", {
        method: "PUT",
        headers,
        body: JSON.stringify({ api_key: apiKeyInput }),
      });
      if (!resp.ok) {
        const err = await resp.json();
        throw new Error(err.detail || "Failed to save API key");
      }
      const data = await resp.json();
      setSettings(data);
      setApiKeyInput("");
    } catch (e: any) {
      setError(`API key error: ${e.message}`);
    } finally {
      setSavingApiKey(false);
    }
  };

  const handleSaveRoots = async () => {
    setSavingRoots(true);
    setError(null);
    try {
      const payload = {
        ohlcv_data_dirs: parseRootLines(rootsForm.ohlcv_data_dirs),
        l2_data_dirs: parseRootLines(rootsForm.l2_data_dirs),
      };

      const resp = await fetch("/api/data-loader/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!resp.ok) {
        const err = await resp.json();
        throw new Error(err.detail || "Failed to update data roots");
      }

      const data = await resp.json();
      setSettings(data);
      setRootsForm({
        ohlcv_data_dirs: (data.ohlcv_data_dirs || []).join("\n"),
        l2_data_dirs: (data.l2_data_dirs || []).join("\n"),
      });
      await fetchCatalog(true);
    } catch (e: any) {
      setError(`Root settings error: ${e.message}`);
    } finally {
      setSavingRoots(false);
    }
  };

  const catalogWithFormats = useMemo(() => buildCatalogWithFormats(catalog), [catalog]);
  const sourceOptions = useMemo(() => buildSourceOptions(catalogWithFormats), [catalogWithFormats]);
  const filteredCatalog = useMemo(
    () => filterCatalogEntries(catalogWithFormats, filters),
    [catalogWithFormats, filters],
  );
  const tickerOptions = useMemo(() => buildTickerOptions(catalogWithFormats), [catalogWithFormats]);
  const schemaOptions = useMemo(() => buildSchemaOptions(catalogWithFormats), [catalogWithFormats]);
  const stats = useMemo(() => buildCatalogStats(catalogWithFormats), [catalogWithFormats]);

  return (
    <div className="data-manager">
      <div className="dm-stats-bar">
        <div className="dm-stat-chip">
          <span className="dm-stat-chip-value">{stats.files}</span>
          <span className="dm-stat-chip-label">Files</span>
        </div>
        <div className="dm-stat-chip">
          <span className="dm-stat-chip-value">{stats.tickers}</span>
          <span className="dm-stat-chip-label">Tickers</span>
        </div>
        <div className="dm-stat-chip">
          <span className="dm-stat-chip-value">{stats.size}</span>
          <span className="dm-stat-chip-label">Total Size</span>
        </div>
        <div className="dm-stat-chip">
          <span className="dm-stat-chip-value">{stats.rows}</span>
          <span className="dm-stat-chip-label">Total Rows</span>
        </div>
      </div>

      <div className="dm-main-row">
        <div className="dm-left-panel">
          <DataManagerDownloadCard
            form={form}
            setForm={setForm}
            error={error}
            costEstimate={costEstimate}
            downloading={downloading}
            downloadProgress={downloadProgress}
            estimating={estimating}
            onEstimateCost={handleEstimateCost}
            onDownload={handleDownload}
          />

          <DataManagerSettingsCard
            settingsOpen={settingsOpen}
            setSettingsOpen={setSettingsOpen}
            settings={settings}
            apiKeyInput={apiKeyInput}
            setApiKeyInput={setApiKeyInput}
            rootsForm={rootsForm}
            setRootsForm={setRootsForm}
            savingApiKey={savingApiKey}
            savingRoots={savingRoots}
            onSaveApiKey={handleSaveApiKey}
            onSaveRoots={handleSaveRoots}
          />
        </div>

        <DataManagerCatalogCard
          loading={loading}
          scanning={scanning}
          catalogWithFormats={catalogWithFormats}
          filteredCatalog={filteredCatalog}
          filters={filters}
          setFilters={setFilters}
          tickerOptions={tickerOptions}
          schemaOptions={schemaOptions}
          sourceOptions={sourceOptions}
          confirmDelete={confirmDelete}
          setConfirmDelete={setConfirmDelete}
          onDelete={handleDelete}
          onScan={handleScan}
          onRefresh={() => fetchCatalog()}
        />
      </div>
    </div>
  );
}

export default DataManager;
