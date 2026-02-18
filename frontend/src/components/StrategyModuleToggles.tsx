import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { defaultStrategyApiUrl } from "../utils";

/** Human-readable metadata for each known strategy module. */
const STRATEGY_META: Record<
  string,
  { label: string; description: string; category: "flow" | "scalp" | "trend" | "other" }
> = {
  momentum_flow: {
    label: "Momentum Flow",
    description:
      "Uses real-time L2 order flow to detect directional momentum surges. Best in trending markets where aggressive buying/selling creates clear directional pressure.",
    category: "flow",
  },
  absorption_reversal: {
    label: "Absorption Reversal",
    description:
      "Detects when large resting orders absorb aggressive flow, signaling an imminent price reversal. Works best in choppy or range-bound conditions.",
    category: "flow",
  },
  exhaustion_fade: {
    label: "Exhaustion Fade",
    description:
      "Identifies when a directional move is losing steam — volume drops while price extends. Fades the move for a mean-reversion trade.",
    category: "flow",
  },
  scalp_l2_intrabar: {
    label: "Scalp L2 Intrabar",
    description:
      "Ultra-short-term scalping using intrabar L2 microstructure — aggression ratios, book pressure, and spread dynamics to capture quick moves.",
    category: "scalp",
  },
  iceberg_defense: {
    label: "Iceberg Defense",
    description:
      "Exits positions when hidden iceberg orders are detected working against your trade direction, protecting from adverse institutional flow.",
    category: "flow",
  },
  mean_reversion: {
    label: "Mean Reversion",
    description:
      "Enters when price deviates significantly from its mean (VWAP or moving average), expecting a return to fair value. Best in choppy/mixed regimes.",
    category: "other",
  },
  momentum: {
    label: "Momentum",
    description:
      "Classic breakout strategy — enters after a consolidation range is broken on high volume. Rides the new trend direction with trailing stops.",
    category: "trend",
  },
  pullback: {
    label: "Pullback",
    description:
      "Enters on pullbacks within an established trend. Waits for price to retrace to a moving average support before joining the trend.",
    category: "trend",
  },
  rotation: {
    label: "Rotation",
    description:
      "Detects sector or style rotation patterns within the price action. Capitalizes on regime transitions between trending and mean-reverting phases.",
    category: "other",
  },
  vwap_magnet: {
    label: "VWAP Magnet",
    description:
      "Trades the tendency of price to gravitate toward VWAP. Enters when price is extended away from VWAP with exhaustion signals.",
    category: "other",
  },
  volume_profile: {
    label: "Volume Profile",
    description:
      "Uses volume-at-price distribution to identify high-volume nodes (support/resistance) and low-volume gaps (breakout opportunities).",
    category: "other",
  },
  gap_liquidity: {
    label: "Gap & Liquidity",
    description:
      "Trades gap fills and liquidity voids. Enters when price moves into a low-liquidity zone with confirmation from L2 book dynamics.",
    category: "trend",
  },
};

/** Canonical ordered list of all strategy module keys. */
const ALL_STRATEGY_KEYS = Object.keys(STRATEGY_META);

const CATEGORY_LABELS: Record<string, string> = {
  flow: "Order Flow",
  scalp: "Scalping",
  trend: "Trend Following",
  other: "General",
};
const CATEGORY_ORDER = ["flow", "scalp", "trend", "other"] as const;

interface StrategyModuleTogglesProps {
  apiUrl?: string;
  selectedTicker?: string;
  onNavigateToStudio?: () => void;
  mode?: "compact" | "expanded";
}

export default function StrategyModuleToggles({
  apiUrl,
  onNavigateToStudio,
  mode = "compact",
}: StrategyModuleTogglesProps) {
  // API status overlay — maps strategy key → { enabled, ... }
  const [apiStatus, setApiStatus] = useState<Record<string, any> | null>(null);
  const [apiConnected, setApiConnected] = useState(false);
  const [loading, setLoading] = useState(false);
  const [hoveredStrategy, setHoveredStrategy] = useState<string | null>(null);
  const [tooltipPos, setTooltipPos] = useState({ top: 0, left: 0 });
  const hoverTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const resolvedUrl = apiUrl || defaultStrategyApiUrl;

  const fetchStrategies = useCallback(async () => {
    if (!resolvedUrl) return;
    setLoading(true);
    try {
      const resp = await fetch(`${resolvedUrl}/api/strategies`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      // API returns Record<string, { enabled, ... }> — merge into status
      if (data && typeof data === "object" && !Array.isArray(data)) {
        setApiStatus(data);
      } else {
        // Gracefully handle unexpected array format
        setApiStatus(null);
      }
      setApiConnected(true);
    } catch {
      setApiConnected(false);
      setApiStatus(null);
    } finally {
      setLoading(false);
    }
  }, [resolvedUrl]);

  useEffect(() => {
    fetchStrategies();
  }, [fetchStrategies]);

  const toggleStrategy = useCallback(
    async (name: string, enabled: boolean) => {
      // Optimistic update
      setApiStatus((prev) => {
        if (!prev) return prev;
        return { ...prev, [name]: { ...prev[name], enabled } };
      });
      try {
        const resp = await fetch(`${resolvedUrl}/api/strategies/toggle`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ strategy_name: name, enabled }),
        });
        if (!resp.ok) throw new Error(`Toggle failed`);
      } catch {
        // Revert on failure
        fetchStrategies();
      }
    },
    [resolvedUrl, fetchStrategies]
  );

  /** Derive enabled state — true if API says enabled, false otherwise. */
  const isEnabled = useCallback(
    (key: string) => {
      if (!apiStatus || !apiStatus[key]) return false;
      return !!apiStatus[key].enabled;
    },
    [apiStatus]
  );

  const enabledCount = useMemo(
    () => ALL_STRATEGY_KEYS.filter((k) => isEnabled(k)).length,
    [isEnabled]
  );

  const handleMouseEnter = useCallback(
    (e: React.MouseEvent, name: string) => {
      if (hoverTimeoutRef.current) clearTimeout(hoverTimeoutRef.current);
      const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
      setTooltipPos({
        top: rect.top,
        left: rect.right + 12,
      });
      hoverTimeoutRef.current = setTimeout(() => {
        setHoveredStrategy(name);
      }, 300);
    },
    []
  );

  const handleMouseLeave = useCallback(() => {
    if (hoverTimeoutRef.current) clearTimeout(hoverTimeoutRef.current);
    setHoveredStrategy(null);
  }, []);

  // ─── Expanded mode (for Studio page) ───
  if (mode === "expanded") {
    return (
      <div className="stm-expanded">
        {!apiConnected && (
          <div className="stm-offline-banner stm-offline-banner-inline">
            <span>⚠ API offline</span>
            <button className="stm-retry-btn" onClick={fetchStrategies} disabled={loading}>
              {loading ? "Pripájam..." : "Zapni API"}
            </button>
          </div>
        )}

        {CATEGORY_ORDER.map((cat) => {
          const keysInCat = ALL_STRATEGY_KEYS.filter((k) => STRATEGY_META[k].category === cat);
          if (!keysInCat.length) return null;
          return (
            <div key={cat} className="stm-expanded-category">
              <div className="stm-expanded-category-label">{CATEGORY_LABELS[cat]}</div>
              <div className="stm-expanded-grid">
                {keysInCat.map((key) => {
                  const meta = STRATEGY_META[key];
                  const enabled = isEnabled(key);
                  return (
                    <button
                      key={key}
                      className={`stm-expanded-card ${enabled ? "enabled" : "disabled"} ${!apiConnected ? "offline" : ""}`}
                      onClick={() => apiConnected && toggleStrategy(key, !enabled)}
                      disabled={!apiConnected}
                    >
                      <div className="stm-expanded-card-head">
                        <span className={`stm-dot ${enabled ? "on" : "off"}`} />
                        <span className="stm-expanded-card-name">{meta.label}</span>
                      </div>
                      <p className="stm-expanded-card-desc">{meta.description}</p>
                    </button>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
    );
  }

  // ─── Compact mode (sidebar) ───
  return (
    <div className="stm-container">
      <div className="stm-header">
        <span className="stm-header-label">Strategy Modules</span>
        <span className="stm-header-count">
          {apiConnected ? `${enabledCount}/${ALL_STRATEGY_KEYS.length}` : "offline"}
        </span>
      </div>

      {!apiConnected && (
        <div className="stm-offline-banner">
          <span>⚠ API offline</span>
          <button className="stm-retry-btn" onClick={fetchStrategies} disabled={loading}>
            {loading ? "Pripájam..." : "Zapni API"}
          </button>
        </div>
      )}

      <div className="stm-list">
        {ALL_STRATEGY_KEYS.map((key) => {
          const meta = STRATEGY_META[key];
          const enabled = isEnabled(key);

          return (
            <div
              key={key}
              className={`stm-row ${enabled ? "enabled" : "disabled"} ${!apiConnected ? "offline" : ""}`}
              onMouseEnter={(e) => handleMouseEnter(e, key)}
              onMouseLeave={handleMouseLeave}
            >
              <button
                className="stm-toggle-area"
                onClick={() => apiConnected && toggleStrategy(key, !enabled)}
                title={apiConnected ? `${enabled ? "Disable" : "Enable"} ${meta.label}` : `${meta.label} — API offline`}
                disabled={!apiConnected}
              >
                <span className={`stm-dot ${enabled ? "on" : "off"}`} />
                <span className="stm-label">{meta.label}</span>
              </button>
              {onNavigateToStudio && (
                <button
                  className="stm-gear"
                  onClick={(e) => {
                    e.stopPropagation();
                    onNavigateToStudio();
                  }}
                  title={`Configure in Adaptive Studio`}
                >
                  ⚙
                </button>
              )}
            </div>
          );
        })}
      </div>

      {/* Tooltip */}
      {hoveredStrategy && STRATEGY_META[hoveredStrategy] && (
        <div
          className="stm-tooltip"
          style={{ top: tooltipPos.top, left: tooltipPos.left }}
        >
          <div className="stm-tooltip-title">
            {STRATEGY_META[hoveredStrategy].label}
          </div>
          <div className="stm-tooltip-desc">
            {STRATEGY_META[hoveredStrategy].description}
          </div>
          <div className="stm-tooltip-category">
            {STRATEGY_META[hoveredStrategy].category.toUpperCase()}
          </div>
        </div>
      )}
    </div>
  );
}
