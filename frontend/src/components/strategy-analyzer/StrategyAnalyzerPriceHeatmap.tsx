import { useEffect, useMemo, useState } from "react";
import type { StrategyAnalyzerPreviewBar } from "./types";

type Props = {
  bars: StrategyAnalyzerPreviewBar[];
  ticker: string;
  dateFrom: string;
  dateTo: string;
};

type Row = {
  level: number;
  values: number[];
};

type DbHeatmapRow = {
  price_bin: number;
  cumulative_bars: number[];
  cumulative_volume: number[];
};

type DbHeatmapTopByTime = {
  price_bin: number;
  cumulative_bars: number;
  share_pct: number;
};

type DbHeatmapTopByVolume = {
  price_bin: number;
  cumulative_volume: number;
  share_pct: number;
};

type DbHeatmapSummary = {
  total_bars: number;
  total_volume: number;
  min_price_bin: number | null;
  max_price_bin: number | null;
  level_count: number;
};

type DbHeatmapPayload = {
  ticker: string;
  date_from: string;
  date_to: string;
  bin_size: number;
  source: string;
  days: string[];
  rows: DbHeatmapRow[];
  latest_as_of_date: string | null;
  latest_summary: DbHeatmapSummary | null;
  top_by_time: DbHeatmapTopByTime[];
  top_by_volume: DbHeatmapTopByVolume[];
};

const BIN_OPTIONS = [0.25, 0.5, 1, 2];

const formatPrice = (value: number): string => `$${value.toFixed(2)}`;
const formatInt = (value: number): string => Math.round(value).toLocaleString();
const formatDayHeader = (day: string): string => (day.length >= 10 ? day.slice(5) : day);
const formatBarsAsDuration = (bars: number): string => {
  const totalMinutes = Math.max(0, Math.trunc(Number(bars) || 0));
  const hours = Math.trunc(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  return `${hours}h ${String(minutes).padStart(2, "0")}m`;
};

const heatAlpha = (value: number, max: number): number => {
  if (max <= 0) return 0;
  const ratio = Math.max(0, Math.min(1, value / max));
  return 0.12 + ratio * 0.58;
};

type HeatmapTableProps = {
  title: string;
  days: string[];
  rows: Row[];
};

function HeatmapTable({ title, days, rows }: HeatmapTableProps) {
  const maxValue = useMemo(() => {
    let max = 0;
    for (const row of rows) {
      for (const value of row.values) {
        if (value > max) max = value;
      }
    }
    return max;
  }, [rows]);

  return (
    <section className="sa-heatmap-panel">
      <h4 className="sa-heatmap-title">{title}</h4>
      <div className="sa-heatmap-scroll">
        <table className="sa-heatmap-table">
          <thead>
            <tr>
              <th className="sa-heatmap-sticky-left">Price</th>
              {days.map((day) => (
                <th key={day} title={day}>
                  {formatDayHeader(day)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.level}>
                <th className="sa-heatmap-sticky-left">{formatPrice(row.level)}</th>
                {row.values.map((value, index) => {
                  const alpha = heatAlpha(value, maxValue);
                  const bg = `rgba(47, 111, 237, ${alpha})`;
                  const tone = alpha > 0.43 ? "#f7fbff" : "var(--text-primary)";
                  return (
                    <td key={`${row.level}-${days[index]}`} style={{ background: bg, color: tone }}>
                      {formatInt(value)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export default function StrategyAnalyzerPriceHeatmap({ bars, ticker, dateFrom, dateTo }: Props) {
  const [binSize, setBinSize] = useState(0.5);
  const [payload, setPayload] = useState<DbHeatmapPayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    if (!ticker || !dateFrom || !dateTo) {
      setPayload(null);
      setLoadError(null);
      return;
    }
    const abortController = new AbortController();
    let isActive = true;
    setLoading(true);
    setLoadError(null);

    const endpoint = `/api/chart-preview/heatmap-daily-cumulative?ticker=${encodeURIComponent(ticker)}&date_from=${encodeURIComponent(
      dateFrom,
    )}&date_to=${encodeURIComponent(dateTo)}&bin_size=${encodeURIComponent(String(binSize))}`;

    void fetch(endpoint, { signal: abortController.signal, cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) {
          const detail = await response.json().catch(() => ({}));
          throw new Error(detail?.detail || `HTTP ${response.status}`);
        }
        return response.json() as Promise<DbHeatmapPayload>;
      })
      .then((nextPayload) => {
        if (!isActive) return;
        setPayload(nextPayload);
      })
      .catch((error: unknown) => {
        const isAbortError =
          (error instanceof DOMException && error.name === "AbortError") ||
          (typeof error === "object" &&
            error !== null &&
            "name" in error &&
            (error as { name?: string }).name === "AbortError");
        if (!isActive || isAbortError) return;
        setLoadError(error instanceof Error ? error.message : "Failed to load DB heatmap");
        setPayload(null);
      })
      .finally(() => {
        if (!isActive) return;
        setLoading(false);
      });

    return () => {
      isActive = false;
      abortController.abort();
    };
  }, [ticker, dateFrom, dateTo, binSize]);

  const days = payload?.days || [];
  const timeRows: Row[] = useMemo(
    () =>
      (payload?.rows || []).map((row) => ({
        level: Number(row.price_bin),
        values: (row.cumulative_bars || []).map((value) => Number(value || 0)),
      })),
    [payload],
  );
  const volumeRows: Row[] = useMemo(
    () =>
      (payload?.rows || []).map((row) => ({
        level: Number(row.price_bin),
        values: (row.cumulative_volume || []).map((value) => Number(Math.round(Number(value || 0)))),
      })),
    [payload],
  );

  const summary = payload?.latest_summary || null;
  const rangeText =
    summary?.min_price_bin != null && summary?.max_price_bin != null
      ? `${formatPrice(summary.min_price_bin)} - ${formatPrice(summary.max_price_bin)}`
      : "n/a";

  return (
    <div className="card sa-heatmap-card">
      <div className="sa-heatmap-head">
        <div>
          <div className="sa-section-kicker">Price Clustering</div>
          <h3 className="sa-section-title">Heatmap exekucii podla ceny (DB cumulative)</h3>
          <div className="sa-heatmap-meta">
            {ticker} | {dateFrom || "n/a"} → {dateTo || "n/a"} | Preview bars {bars.length.toLocaleString()} | Range {rangeText}
          </div>
          <div className="sa-heatmap-note">
            Zdroj: `daily_price_heatmap_levels` (kumulativne hodnoty k jednotlivym dnom).
          </div>
          <div className="sa-heatmap-note">
            `Bars` = počet 1m sviečok (čas = bars v minútach). Top tabuľky sú pre posledný deň v range ({payload?.latest_as_of_date || "n/a"}).
          </div>
          <div className="sa-heatmap-note">
            Tabulky nižšie sú scrollovateľné cez celý cenový rozsah a dni ({days.length}).
          </div>
          {payload?.latest_as_of_date ? (
            <div className="sa-heatmap-note">Posledný dostupný deň v rozsahu: {payload.latest_as_of_date}</div>
          ) : null}
        </div>
        <label className="sa-control-field sa-control-field-small" htmlFor="sa_heatmap_bin_size">
          <span className="sa-control-label">BIN SIZE</span>
          <select
            id="sa_heatmap_bin_size"
            className="sa-control-input"
            value={String(binSize)}
            onChange={(event) => setBinSize(Number(event.target.value))}
          >
            {BIN_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>
      </div>

      {loading ? <div className="sa-heatmap-note">Načítavam DB heatmapu...</div> : null}
      {!loading && loadError ? <div className="sa-heatmap-note">Chyba DB heatmapy: {loadError}</div> : null}
      {!loading && !loadError && payload && payload.rows.length === 0 ? (
        <div className="sa-heatmap-note">
          Pre tento ticker/range v DB nie sú prepočítané heatmap dáta. Spusť `python3 scripts/recompute_daily_price_heatmaps.py`.
        </div>
      ) : null}

      {!loading && !loadError && payload && payload.rows.length > 0 ? (
        <>
          <div className="sa-heatmap-summary-grid">
            <section className="sa-heatmap-panel">
              <h4 className="sa-heatmap-title">Top levels by cumulative time</h4>
              <table className="sa-heatmap-summary-table">
                <thead>
                  <tr>
                    <th>Price</th>
                    <th>Bars</th>
                    <th>Time</th>
                    <th>Share</th>
                  </tr>
                </thead>
                <tbody>
                  {(payload.top_by_time || []).map((item) => (
                    <tr key={`time-${item.price_bin}`}>
                      <td>{formatPrice(item.price_bin)}</td>
                      <td>{formatInt(item.cumulative_bars)}</td>
                      <td>{formatBarsAsDuration(item.cumulative_bars)}</td>
                      <td>{Number(item.share_pct || 0).toFixed(2)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>

            <section className="sa-heatmap-panel">
              <h4 className="sa-heatmap-title">Top levels by cumulative volume</h4>
              <table className="sa-heatmap-summary-table">
                <thead>
                  <tr>
                    <th>Price</th>
                    <th>Volume</th>
                    <th>Share</th>
                  </tr>
                </thead>
                <tbody>
                  {(payload.top_by_volume || []).map((item) => (
                    <tr key={`volume-${item.price_bin}`}>
                      <td>{formatPrice(item.price_bin)}</td>
                      <td>{formatInt(item.cumulative_volume)}</td>
                      <td>{Number(item.share_pct || 0).toFixed(2)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          </div>

          <HeatmapTable title="Kumulatívny čas pri cene (bars)" days={days} rows={timeRows} />
          <HeatmapTable title="Kumulatívny volume pri cene" days={days} rows={volumeRows} />
        </>
      ) : null}
    </div>
  );
}
