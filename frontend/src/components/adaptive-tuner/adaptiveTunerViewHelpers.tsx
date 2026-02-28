type GenericRecord = Record<string, any>;

interface RangeSummary {
  start?: string;
  end?: string;
  total_days?: number;
}

interface DimensionImportanceBarsProps {
  importance?: Record<string, number> | null;
}

interface InteractionItem {
  dimensions?: string;
  pair?: string;
  effect?: number;
  delta?: number;
  count?: number;
}

interface SurprisingVector {
  label?: string;
  key?: string;
  candidate?: Record<string, unknown>;
  score?: number;
  z_score?: number;
  trades?: number;
  trade_count?: number;
}

export const formatCandidate = (candidate: GenericRecord | null | undefined) => {
  if (!candidate || typeof candidate !== "object") return "-";
  const mode = candidate.strategy_selection_mode || "adaptive_top_n";
  return `${mode} | top=${candidate.max_active_strategies} | hysteresis=${candidate.min_active_bars_before_switch} | cooldown=${candidate.switch_cooldown_bars} | flowBias=${candidate.flow_bias_enabled ? "on" : "off"} | fallback=${candidate.use_ohlcv_fallbacks ? "on" : "off"}`;
};

export const formatV2Candidate = (candidate: GenericRecord | null | undefined) => {
  if (!candidate || typeof candidate !== "object") return "-";
  const parts: string[] = [];
  const strategies = candidate.enabled_strategies;
  if (Array.isArray(strategies) && strategies.length) {
    parts.push(strategies.join("+"));
  }
  const regime = candidate.regime_filter;
  if (Array.isArray(regime) && regime.length) {
    parts.push(`regime:${regime.join(",")}`);
  }
  if (candidate.l2_min_imbalance != null) {
    parts.push(`imb:${Number(candidate.l2_min_imbalance).toFixed(3)}`);
  }
  if (candidate.base_threshold != null) {
    parts.push(`thr:${candidate.base_threshold}`);
  }
  if (candidate.min_confirming_sources != null) {
    parts.push(`src:${candidate.min_confirming_sources}`);
  }
  return parts.length ? parts.join(" | ") : formatCandidate(candidate);
};

export const formatRange = (range: RangeSummary | null | undefined) => {
  if (!range || !range.start || !range.end) return "-";
  return `${range.start} -> ${range.end} (${Number(range.total_days || 0)} days)`;
};

export const formatJobLabel = (job: Record<string, any>) => {
  const jobId = String(job?.job_id || "").slice(0, 8) || "job";
  const status = String(job?.status || "idle").toLowerCase();
  const version = Number(job?.adaptive_version || job?.request?.adaptive_version || 1);
  return `${jobId} | v${version} | ${status}`;
};

export const statusClassName = (status: string) => {
  const normalized = String(status || "").toLowerCase();
  if (normalized === "running") return "running";
  if (normalized === "completed") return "completed";
  if (normalized === "failed") return "failed";
  if (normalized === "queued") return "queued";
  return "idle";
};

export function DimensionImportanceBars({ importance }: DimensionImportanceBarsProps) {
  if (!importance || typeof importance !== "object") return null;
  const entries = Object.entries(importance).sort((a, b) => b[1] - a[1]);
  if (!entries.length) return null;
  const maxVal = Math.max(...entries.map(([, v]) => v), 0.01);

  return (
    <div className="vector-importance-bars">
      {entries.map(([dim, val]) => (
        <div className="vector-bar-row" key={dim}>
          <span className="vector-bar-label">{dim}</span>
          <div className="vector-bar-track">
            <div
              className="vector-bar-fill"
              style={{ width: `${Math.min(100, (val / maxVal) * 100)}%` }}
            />
          </div>
          <span className="vector-bar-value">{(val * 100).toFixed(1)}%</span>
        </div>
      ))}
    </div>
  );
}

export function InteractionsList({ interactions }: { interactions?: InteractionItem[] | null }) {
  if (!Array.isArray(interactions) || !interactions.length) return null;
  return (
    <div className="vector-interactions-list">
      {interactions.slice(0, 8).map((ix, idx) => (
        <div className="vector-interaction-item" key={idx}>
          <span className="interaction-dims">{ix.dimensions || ix.pair || "?"}</span>
          <span className="interaction-effect">
            Δ={Number(ix.effect ?? ix.delta ?? 0).toFixed(4)}
          </span>
          {ix.count != null && <span className="interaction-count">n={ix.count}</span>}
        </div>
      ))}
    </div>
  );
}

export function SurprisingVectorsTable({ vectors }: { vectors?: SurprisingVector[] | null }) {
  if (!Array.isArray(vectors) || !vectors.length) return null;
  return (
    <div className="vector-surprising-table-wrap">
      <table className="vector-surprising-table">
        <thead>
          <tr>
            <th>Vector</th>
            <th>Score</th>
            <th>z-score</th>
            <th>Trades</th>
          </tr>
        </thead>
        <tbody>
          {vectors.slice(0, 10).map((v, idx) => (
            <tr key={idx}>
              <td>{v.label || v.key || JSON.stringify(v.candidate || {})}</td>
              <td>{Number(v.score ?? 0).toFixed(4)}</td>
              <td className={Number(v.z_score ?? 0) > 1.5 ? "z-high" : ""}>
                {Number(v.z_score ?? 0).toFixed(2)}σ
              </td>
              <td>{Number(v.trades ?? v.trade_count ?? 0)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
