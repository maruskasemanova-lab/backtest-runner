export const DEFAULT_FILTERS = {
  ticker: "",
  schema: "all",
  format: "all",
  source: "all",
  managed: "all",
};

export const DEFAULT_DOWNLOAD_FORM = {
  ticker: "MU",
  schema: "mbp-10",
  start_date: "",
  end_date: "",
  dataset: "XNAS.ITCH",
  convert_to_parquet: true,
};

export const DEFAULT_ROOTS_FORM = {
  ohlcv_data_dirs: "",
  l2_data_dirs: "",
};

export const getRecentIsoDateRange = () => {
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);
  const twoDaysAgo = new Date(today);
  twoDaysAgo.setDate(twoDaysAgo.getDate() - 2);

  const toIsoDay = (d: Date) => d.toISOString().split("T")[0];
  return {
    startDate: toIsoDay(twoDaysAgo),
    endDate: toIsoDay(yesterday),
  };
};

export const toApiPayload = (form: Record<string, any>) => ({
  ticker: form.ticker,
  data_schema: form.schema,
  start_date: form.start_date,
  end_date: form.end_date,
  dataset: form.dataset,
  convert_to_parquet: form.convert_to_parquet,
});

export const parseRootLines = (value: string) =>
  value
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);

export const readStoredAuthToken = () => {
  if (typeof window === "undefined") return "";
  return (
    window.localStorage.getItem("backtest_jwt") ||
    window.localStorage.getItem("supabase_jwt") ||
    ""
  );
};

export const formatSize = (bytes: number) => {
  if (!bytes) return "-";
  const mb = bytes / (1024 * 1024);
  return mb >= 1000 ? `${(mb / 1024).toFixed(1)} GB` : `${mb.toFixed(1)} MB`;
};

export const formatRows = (count: number) => {
  if (!count) return "-";
  if (count >= 1_000_000) return `${(count / 1_000_000).toFixed(1)}M`;
  if (count >= 1_000) return `${(count / 1_000).toFixed(1)}K`;
  return count.toLocaleString();
};

export const schemaLabel = (schema: string) => {
  const labels: Record<string, string> = {
    "mbp-10": "L2 Depth",
    "ohlcv-1m": "OHLCV 1m",
    tcbbo: "Options TCBBO",
    trades: "Trades",
  };
  return labels[schema] || schema;
};

export const schemaIcon = (schema: string) => {
  const icons: Record<string, string> = {
    "mbp-10": "📊",
    "ohlcv-1m": "📈",
    tcbbo: "🧩",
    trades: "⚡",
  };
  return icons[schema] || "📁";
};

export const buildCatalogWithFormats = (catalog: any[]) =>
  (Array.isArray(catalog) ? catalog : []).map((entry) => ({
    ...entry,
    managed: entry.managed !== false,
    formats:
      entry.formats ||
      [
        entry.file_mbn ? "mbn" : null,
        entry.file_parquet ? "parquet" : null,
        entry.file_csv ? "csv" : null,
      ].filter(Boolean),
  }));

export const buildSourceOptions = (catalogWithFormats: any[]) => {
  const values = new Set(catalogWithFormats.map((entry) => entry.source_root).filter(Boolean));
  return Array.from(values).sort();
};

export const filterCatalogEntries = (
  catalogWithFormats: any[],
  filters: Record<string, string>,
) => {
  return catalogWithFormats.filter((entry) => {
    if (filters.ticker && entry.ticker !== filters.ticker) return false;
    if (filters.schema !== "all" && entry.schema !== filters.schema) return false;
    if (filters.format !== "all" && !entry.formats.includes(filters.format)) return false;
    if (filters.source !== "all" && entry.source_root !== filters.source) return false;
    if (filters.managed !== "all") {
      if (filters.managed === "managed" && entry.managed === false) return false;
      if (filters.managed === "external" && entry.managed !== false) return false;
    }
    return true;
  });
};

export const buildTickerOptions = (catalogWithFormats: any[]) =>
  Array.from(new Set(catalogWithFormats.map((entry) => entry.ticker))).sort();

export const buildSchemaOptions = (catalogWithFormats: any[]) =>
  Array.from(new Set(catalogWithFormats.map((entry) => entry.schema))).sort();

export const buildCatalogStats = (catalogWithFormats: any[]) => {
  const tickers = new Set(catalogWithFormats.map((entry) => entry.ticker));
  const totalSize = catalogWithFormats.reduce((sum, entry) => sum + (entry.size_bytes || 0), 0);
  const totalRows = catalogWithFormats.reduce((sum, entry) => sum + (entry.row_count || 0), 0);

  return {
    files: catalogWithFormats.length,
    tickers: tickers.size,
    size: formatSize(totalSize),
    rows: formatRows(totalRows),
  };
};
