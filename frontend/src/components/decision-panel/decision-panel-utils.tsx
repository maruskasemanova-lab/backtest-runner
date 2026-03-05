const DECISION_MARKER_TYPES = new Set([
  "entry_executed",
  "exit_executed",
  "stop_loss_hit",
  "take_profit_hit",
  "signal_generated",
  "execution_status",
  "trailing_stop_updated",
]);

const DEFAULT_ACCOUNT_SIZE = 10_000;

export const DECISION_PANEL_LANGUAGE_STORAGE_KEY =
  "backtest_runner.decision_panel_language";

const SUPPORTED_DECISION_LANGUAGES = new Set(["sk", "en"]);

const TOOLTIP_BASE_LABEL_ALIASES = {
  "Strategy (Entry)": "Strategy",
  "Strategy (Gate)": "Strategy",
  "Near Tested Levels (Gate)": "Near Tested Levels",
  "Near Tested Levels (Entry Timing)": "Near Tested Levels",
  "POC On Trade Side (Gate)": "POC On Trade Side",
  "POC On Trade Side (Entry Timing)": "POC On Trade Side",
  "VWAP Execution Flow (L2 Diagnostics)": "VWAP Execution Flow",
  "VWAP Execution Flow (Decision Log)": "VWAP Execution Flow",
};

export const resolveTooltipBaseLabel = (label) => {
  const normalized = String(label || "").trim();
  if (!normalized) return "";
  const aliased = TOOLTIP_BASE_LABEL_ALIASES[normalized];
  if (aliased) return aliased;
  return normalized.replace(/\s+\([^)]*\)\s*$/, "");
};

export const formatTooltipRuntimeValue = (value) => {
  if (value === null || value === undefined) return "n/a";
  if (typeof value === "number") {
    if (!Number.isFinite(value)) return "n/a";
    if (Math.abs(value) >= 1000)
      return value.toLocaleString("en-US", { maximumFractionDigits: 6 });
    return Number.isInteger(value)
      ? String(value)
      : value.toFixed(6).replace(/0+$/, "").replace(/\.$/, "");
  }
  if (typeof value === "boolean") return value ? "true" : "false";
  if (Array.isArray(value)) {
    if (!value.length) return "[]";
    return value.map((item) => formatTooltipRuntimeValue(item)).join(", ");
  }
  if (typeof value === "object") {
    const entries = Object.entries(value);
    if (!entries.length) return "{}";
    return entries
      .slice(0, 8)
      .map(([key, item]) => `${key}: ${formatTooltipRuntimeValue(item)}`)
      .join(" | ");
  }
  return String(value);
};

export const resolveDecisionLanguage = () => {
  if (typeof window === "undefined") return "sk";
  const stored = String(
    window.localStorage.getItem(DECISION_PANEL_LANGUAGE_STORAGE_KEY) || "",
  )
    .trim()
    .toLowerCase();
  if (SUPPORTED_DECISION_LANGUAGES.has(stored)) return stored;
  return "sk";
};

export const isDecisionMarker = (marker) =>
  DECISION_MARKER_TYPES.has(marker?.marker_type);

export const formatGenericValue = (value) => {
  if (value === null || value === undefined) return "n/a";
  if (typeof value === "number") {
    if (!Number.isFinite(value)) return "n/a";
    return Number.isInteger(value) ? String(value) : value.toFixed(4);
  }
  if (typeof value === "boolean") return value ? "true" : "false";
  if (Array.isArray(value)) {
    if (!value.length) return "[]";
    return value
      .map((item) => {
        if (typeof item === "object" && item !== null)
          return JSON.stringify(item);
        return String(item);
      })
      .join(", ");
  }
  if (typeof value === "object") {
    const entries = Object.entries(value);
    if (!entries.length) return "{}";
    return entries
      .slice(0, 10)
      .map(([k, v]) => `${k}: ${formatGenericValue(v)}`)
      .join(" | ");
  }
  return String(value);
};

export const renderValue = (val, keyPrefix = "") => {
  if (val === null || val === undefined) return "N/A";

  if (typeof val === "object" && !Array.isArray(val)) {
    if (Object.keys(val).length === 0) return "{}";

    return (
      <div className="object-container decision-tree">
        {Object.entries(val).map(([k, v]) => (
          <div
            key={`${keyPrefix}-${k}`}
            className="object-row decision-tree-row"
          >
            <span className="object-key decision-tree-key">{k}:</span>
            <div className="nested-object">
              {renderValue(v, `${keyPrefix}-${k}`)}
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (Array.isArray(val)) {
    if (val.length === 0) return "[]";
    return (
      <div className="object-container decision-tree">
        {val.map((v, i) => (
          <div
            key={`${keyPrefix}-${i}`}
            className="object-row decision-tree-row"
          >
            <span className="object-key decision-tree-key">[{i}]:</span>
            <div className="nested-object">
              {renderValue(v, `${keyPrefix}-${i}`)}
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (typeof val === "number") {
    return (
      <span className="decision-mono">
        {Math.abs(val) < 0.01 ? val.toFixed(6) : val.toFixed(4)}
      </span>
    );
  }

  return <span className="decision-mono">{String(val)}</span>;
};

export const toFiniteNumber = (value) => {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
};

export const resolvePnlPct = (details, pnlDollars) => {
  const explicitPct = toFiniteNumber(details?.pnl_pct);
  if (explicitPct !== null) return explicitPct;

  const dollars = Number(pnlDollars);
  if (!Number.isFinite(dollars)) return null;

  const notional = toFiniteNumber(details?.position_notional_usd);
  if (notional !== null && notional > 0) {
    return (dollars / notional) * 100;
  }

  return (dollars / DEFAULT_ACCOUNT_SIZE) * 100;
};

export const formatTime = (timestamp) => {
  if (!timestamp) return "N/A";
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) return "N/A";
  return date.toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
};

export const formatPrice = (value) => {
  const number = Number(value);
  return Number.isFinite(number) ? `$${number.toFixed(2)}` : "N/A";
};

export const getMarkerIdentity = (marker) => {
  if (!marker) return "";
  if (marker.id) return `id:${marker.id}`;
  return [
    marker.marker_type || "marker",
    marker.timestamp || marker.time || "na",
    marker.price ?? "na",
    marker.side || "na",
  ].join("|");
};

export const getMarkerKey = (marker, idx = 0) => {
  return (
    marker.id ||
    `${marker.marker_type || "marker"}-${marker.timestamp || marker.time || "na"}-${idx}`
  );
};

export const isSameMarker = (a, b) => {
  if (!a || !b) return false;
  if (a.id && b.id && a.id === b.id) return true;
  return (
    String(a.marker_type || "") === String(b.marker_type || "") &&
    String(a.timestamp || "") === String(b.timestamp || "") &&
    String(a.time || "") === String(b.time || "") &&
    Number(a.price ?? Number.NaN) === Number(b.price ?? Number.NaN)
  );
};

export const getMarkerIcon = (marker) => {
  const markerType = marker?.marker_type;
  const markerPnlUsd = marker?.details?.pnl_usd ?? marker?.details?.pnl_dollars;
  const markerPnlPct = resolvePnlPct(marker?.details, markerPnlUsd);
  if (
    markerType === "take_profit_hit" &&
    markerPnlPct !== null &&
    markerPnlPct <= 0
  ) {
    return "🔴";
  }
  const icons = {
    regime_detected: "🎯",
    strategy_selected: "📋",
    signal_generated: "📊",
    execution_status: "⏳",
    entry_executed: "🟢",
    exit_executed: "⚪",
    stop_loss_hit: "🔴",
    take_profit_hit: "💰",
    iceberg_detected: "❄️",
    trailing_stop_updated: "📍",
    session_started: "🏁",
    session_ended: "🏆",
  };
  return icons[markerType] || "📌";
};

export const formatExitMetrics = (marker) => {
  if (
    !["exit_executed", "stop_loss_hit", "take_profit_hit"].includes(
      marker?.marker_type,
    )
  ) {
    return null;
  }
  const details = marker?.details || {};
  const pnlUsd = details.pnl_usd ?? details.pnl_dollars;
  const pnlPct = resolvePnlPct(details, pnlUsd);
  const costUsd = details.cost_usd ?? details.costs?.total;
  const costPct = details.cost_pct;
  const barsHeld = details.bars_held;

  const parts = [];
  if (pnlPct != null || pnlUsd != null) {
    const pctText =
      pnlPct != null
        ? `${pnlPct >= 0 ? "+" : ""}${Number(pnlPct).toFixed(2)}%`
        : "n/a";
    const usdText =
      pnlUsd != null
        ? `${Number(pnlUsd) >= 0 ? "+" : ""}$${Number(pnlUsd).toFixed(2)}`
        : "n/a";
    parts.push(`PnL: ${pctText} (${usdText})`);
  }
  if (costUsd != null) {
    const costUsdText = `$${Number(costUsd).toFixed(2)}`;
    const costPctText =
      costPct != null ? ` (${Number(costPct).toFixed(2)}%)` : "";
    parts.push(`Costs: ${costUsdText}${costPctText}`);
  }
  if (barsHeld != null) {
    parts.push(`Held: ${Number(barsHeld)}`);
  }
  return parts.length ? parts.join(" | ") : null;
};
