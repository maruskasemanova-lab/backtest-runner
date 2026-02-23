import { useCallback, useEffect, useMemo, useRef, useState } from "react";

// ─── Event names for bidirectional sync with RunConfig ───
export const EXEC_MODULE_TOGGLE_EVENT = "execution-module-toggle";
export const EXEC_CONFIG_SNAPSHOT_EVENT = "execution-config-snapshot";

/** Metadata for each execution module. */
const EXEC_MODULE_META: Record<
  string,
  {
    label: string;
    description: string;
    category: "risk" | "exit" | "flow" | "engine";
    configKey: string; // boolean key in RunConfig state
  }
> = {
  adverse_flow_exit: {
    label: "Adverse Flow Exit",
    description:
      "Monitors real-time order flow and exits the trade when aggressive flow turns against your position. Protects from sudden institutional selling/buying pressure.",
    category: "exit",
    configKey: "adverse_flow_exit_enabled",
  },
  l2_confirmation_gate: {
    label: "L2 Confirmation Gate",
    description:
      "Requires Level 2 microstructure confirmation before any trade entry — checks imbalance, signed aggression, directional consistency across a lookback window.",
    category: "flow",
    configKey: "l2_confirm_enabled",
  },
  trailing_stop: {
    label: "Trailing Stop",
    description:
      "Activates a trailing stop-loss after the trade reaches a profit threshold. Includes break-even protection and optional activation during choppy regimes.",
    category: "risk",
    configKey: "trailing_enabled_in_choppy",
  },
  momentum_route: {
    label: "Momentum Route",
    description:
      "Routes momentum strategy signals through an L2 flow scoring filter. Only lets high-flow-score momentum trades through, reducing false breakouts.",
    category: "flow",
    configKey: "momentum_route_enabled",
  },
  momentum_fail_fast: {
    label: "Momentum Fail-Fast",
    description:
      "Exits momentum trades early when post-entry flow metrics deteriorate — aggression reverses, book pressure drops, or directional consistency collapses.",
    category: "exit",
    configKey: "momentum_fail_fast_exit_enabled",
  },
  momentum_diversification: {
    label: "Momentum Diversification",
    description:
      "Distributes momentum exposure across multiple strategy sleeves with per-sleeve flow scoring, preventing concentration risk in a single momentum signal.",
    category: "flow",
    configKey: "momentum_diversification_enabled",
  },
  aos_auto_apply: {
    label: "AOS Auto-Apply",
    description:
      "Automatically applies Adaptive Orchestration System optimizations when a backtest run starts — adjusts strategy weights and parameters based on recent regime analysis.",
    category: "engine",
    configKey: "apply_aos_optimizations_on_start",
  },
};

type ModuleSettingField =
  | {
      type: "number";
      configKey: string;
      label: string;
      min?: number;
      max?: number;
      step?: number;
      integer?: boolean;
      hint?: string;
      disabledWhen?: (config: Record<string, any>) => boolean;
    }
  | {
      type: "checkbox";
      configKey: string;
      label: string;
      hint?: string;
      disabledWhen?: (config: Record<string, any>) => boolean;
    }
  | {
      type: "select";
      configKey: string;
      label: string;
      options: Array<{ value: string; label: string }>;
      hint?: string;
      disabledWhen?: (config: Record<string, any>) => boolean;
    }
  | {
      type: "text";
      configKey: string;
      label: string;
      placeholder?: string;
      hint?: string;
      disabledWhen?: (config: Record<string, any>) => boolean;
    };

const MODULE_SETTING_FIELDS: Record<string, ModuleSettingField[]> = {
  trailing_stop: [
    { type: "number", configKey: "risk_per_trade_pct", label: "Risk Per Trade (%)", min: 0.1, max: 10, step: 0.1 },
    {
      type: "number",
      configKey: "max_position_notional_pct",
      label: "Max Position Notional (%)",
      min: 1,
      max: 100,
      step: 1,
    },
    {
      type: "number",
      configKey: "max_fill_participation_rate",
      label: "Max Fill Participation (0-1)",
      min: 0.01,
      max: 1,
      step: 0.01,
    },
    { type: "number", configKey: "min_fill_ratio", label: "Min Fill Ratio (0-1)", min: 0.01, max: 1, step: 0.01 },
    { type: "number", configKey: "time_exit_bars", label: "Time Exit (bars)", min: 1, step: 1, integer: true },
    { type: "number", configKey: "trailing_stop_pct", label: "Global Trailing Stop (%)", min: 0, max: 5, step: 0.01 },
    {
      type: "select",
      configKey: "stop_loss_mode",
      label: "Stop-Loss Mode",
      options: [
        { value: "strategy", label: "strategy" },
        { value: "fixed", label: "fixed" },
        { value: "capped", label: "capped" },
      ],
    },
    {
      type: "number",
      configKey: "fixed_stop_loss_pct",
      label: "Fixed Stop-Loss (%)",
      min: 0.01,
      max: 5,
      step: 0.05,
      disabledWhen: (config) => String(config.stop_loss_mode || "strategy") === "strategy",
    },
    { type: "number", configKey: "global_exit_rr_ratio", label: "Global Exit RR Ratio", min: 0, max: 10, step: 0.05 },
    {
      type: "number",
      configKey: "global_risk_atr_stop_multiplier",
      label: "Global Risk ATR Stop Multiplier",
      min: 0,
      max: 10,
      step: 0.05,
    },
    {
      type: "number",
      configKey: "global_risk_volume_stop_pct",
      label: "Global Risk Volume Stop (%)",
      min: 0,
      max: 10,
      step: 0.05,
    },
    {
      type: "number",
      configKey: "global_risk_min_stop_loss_pct",
      label: "Global Risk Min Stop-Loss (%)",
      min: 0,
      max: 5,
      step: 0.01,
    },
    {
      type: "number",
      configKey: "trailing_activation_pct",
      label: "Break-even Activation (% MFE)",
      min: 0,
      max: 5,
      step: 0.01,
    },
    {
      type: "number",
      configKey: "break_even_buffer_pct",
      label: "Break-even Buffer (%)",
      min: 0,
      max: 2,
      step: 0.01,
    },
    {
      type: "number",
      configKey: "break_even_min_hold_bars",
      label: "Break-even Min Hold (bars)",
      min: 1,
      step: 1,
      integer: true,
    },
  ],
  adverse_flow_exit: [
    {
      type: "number",
      configKey: "adverse_flow_threshold",
      label: "Adverse Flow Threshold",
      min: 0.02,
      max: 1,
      step: 0.01,
    },
    {
      type: "number",
      configKey: "adverse_flow_min_hold_bars",
      label: "Adverse Flow Min Hold (bars)",
      min: 1,
      step: 1,
      integer: true,
    },
  ],
  l2_confirmation_gate: [
    { type: "number", configKey: "l2_min_imbalance", label: "Min Imbalance", min: 0, step: 0.01 },
    {
      type: "number",
      configKey: "l2_min_signed_aggression",
      label: "Min Signed Aggression",
      min: 0,
      step: 0.01,
    },
    {
      type: "number",
      configKey: "l2_min_directional_consistency",
      label: "Min Directional Consistency",
      min: 0,
      step: 0.01,
    },
    { type: "number", configKey: "l2_lookback_bars", label: "Lookback Bars", min: 1, step: 1, integer: true },
  ],
  momentum_route: [
    {
      type: "number",
      configKey: "momentum_min_flow_score",
      label: "Min Flow Score",
      min: 0,
      max: 100,
      step: 1,
    },
    {
      type: "number",
      configKey: "momentum_route_flow_score_impulse",
      label: "Flow Score Impulse",
      min: 0,
      max: 200,
      step: 1,
    },
    {
      type: "number",
      configKey: "momentum_min_directional_consistency",
      label: "Min Directional Consistency",
      min: 0,
      max: 1,
      step: 0.01,
    },
    {
      type: "number",
      configKey: "momentum_min_signed_aggression",
      label: "Min Signed Aggression",
      min: 0,
      max: 1,
      step: 0.01,
    },
    { type: "number", configKey: "momentum_min_imbalance", label: "Min Imbalance", min: 0, max: 1, step: 0.01 },
    {
      type: "checkbox",
      configKey: "momentum_route_require_l2_coverage",
      label: "Require L2 Coverage",
    },
  ],
  momentum_fail_fast: [
    {
      type: "number",
      configKey: "momentum_fail_fast_max_bars",
      label: "Fail-Fast Max Bars",
      min: 1,
      step: 1,
      integer: true,
    },
    {
      type: "number",
      configKey: "momentum_fail_fast_signed_aggression_max",
      label: "Signed Aggression Max",
      min: -1,
      max: 1,
      step: 0.01,
    },
    {
      type: "number",
      configKey: "momentum_fail_fast_book_pressure_max",
      label: "Book Pressure Max",
      min: -1,
      max: 1,
      step: 0.01,
    },
    {
      type: "number",
      configKey: "momentum_fail_fast_directional_consistency_max",
      label: "Directional Consistency Max",
      min: 0,
      max: 1,
      step: 0.01,
    },
  ],
  momentum_diversification: [
    {
      type: "checkbox",
      configKey: "momentum_diversification_override_enabled",
      label: "Override Momentum Defaults",
    },
    {
      type: "checkbox",
      configKey: "momentum_require_l2_coverage",
      label: "Require L2 Coverage",
    },
    {
      type: "text",
      configKey: "momentum_apply_to_strategies",
      label: "Apply To Strategies (csv)",
      placeholder: "momentum_flow,mean_reversion",
    },
    {
      type: "text",
      configKey: "momentum_allowed_micro_regimes",
      label: "Allowed Micro Regimes (csv)",
      placeholder: "trend_up,trend_down",
    },
    {
      type: "text",
      configKey: "momentum_blocked_micro_regimes",
      label: "Blocked Micro Regimes (csv)",
      placeholder: "noise,rotation",
    },
  ],
};

/** Canonical ordered list of all execution module keys. */
const ALL_MODULE_KEYS = Object.keys(EXEC_MODULE_META);

const EXEC_CATEGORY_LABELS: Record<string, string> = {
  exit: "Exit Protection",
  flow: "Flow Routing",
  risk: "Risk Management",
  engine: "Engine",
};
const EXEC_CATEGORY_ORDER = ["exit", "flow", "risk", "engine"] as const;

interface ExecutionModuleTogglesProps {
  onNavigateToRiskLimits?: () => void;
  mode?: "compact" | "expanded";
}

export default function ExecutionModuleToggles({
  onNavigateToRiskLimits,
  mode = "compact",
}: ExecutionModuleTogglesProps) {
  const [moduleState, setModuleState] = useState<Record<string, boolean>>({});
  const [configState, setConfigState] = useState<Record<string, any>>({});
  const [expandedModules, setExpandedModules] = useState<Record<string, boolean>>({});
  const [hoveredModule, setHoveredModule] = useState<string | null>(null);
  const [tooltipPos, setTooltipPos] = useState({ top: 0, left: 0 });
  const hoverTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const updateConfigValue = useCallback((configKey: string, value: string | number | boolean) => {
    setConfigState((prev) => ({ ...prev, [configKey]: value }));
    window.dispatchEvent(
      new CustomEvent(EXEC_MODULE_TOGGLE_EVENT, {
        detail: { configKey, value },
      })
    );
  }, []);

  // Listen for config snapshots from RunConfig to hydrate initial state
  useEffect(() => {
    const handler = (e: Event) => {
      const config = (e as CustomEvent).detail;
      if (!config || typeof config !== "object") return;
      setConfigState(config as Record<string, any>);
      const next: Record<string, boolean> = {};
      for (const key of ALL_MODULE_KEYS) {
        const meta = EXEC_MODULE_META[key];
        if (meta && meta.configKey in config) {
          next[key] = !!config[meta.configKey];
        }
      }
      setModuleState(next);
    };

    window.addEventListener(EXEC_CONFIG_SNAPSHOT_EVENT, handler);

    // Try reading config directly from global ref (most reliable for initial hydration)
    const globalConfig = (window as any).__executionConfig;
    if (globalConfig && typeof globalConfig === "object") {
      handler({ detail: globalConfig } as unknown as Event);
    }

    // Also request via events as backup
    let retries = 0;
    const interval = setInterval(() => {
      if (retries >= 3) {
        clearInterval(interval);
        return;
      }
      window.dispatchEvent(new CustomEvent("execution-config-snapshot-request"));
      retries++;
    }, 200);

    return () => {
      clearInterval(interval);
      window.removeEventListener(EXEC_CONFIG_SNAPSHOT_EVENT, handler);
    };
  }, []);

  const toggleModule = useCallback((key: string, enabled: boolean) => {
    const meta = EXEC_MODULE_META[key];
    if (!meta) return;

    // Optimistic update + dispatch event for RunConfig
    setModuleState((prev) => ({ ...prev, [key]: enabled }));
    updateConfigValue(meta.configKey, enabled);
  }, [updateConfigValue]);

  const toggleExpanded = useCallback((key: string) => {
    setExpandedModules((prev) => ({ ...prev, [key]: !prev[key] }));
  }, []);

  const handleNumberFieldChange = useCallback(
    (field: Extract<ModuleSettingField, { type: "number" }>, rawValue: string) => {
      if (rawValue === "") return;
      const parsed = Number(rawValue);
      if (!Number.isFinite(parsed)) return;
      let next = parsed;
      if (field.integer) {
        next = Math.trunc(next);
      }
      if (Number.isFinite(field.min as number)) {
        next = Math.max(field.min as number, next);
      }
      if (Number.isFinite(field.max as number)) {
        next = Math.min(field.max as number, next);
      }
      updateConfigValue(field.configKey, next);
    },
    [updateConfigValue]
  );

  const renderModuleField = useCallback(
    (field: ModuleSettingField) => {
      const disabled = field.disabledWhen ? field.disabledWhen(configState) : false;
      const rawValue = configState[field.configKey];

      if (field.type === "checkbox") {
        return (
          <div key={field.configKey} className="stm-config-field stm-config-field-checkbox">
            <label className="stm-config-check">
              <input
                type="checkbox"
                checked={!!rawValue}
                onChange={(e) => updateConfigValue(field.configKey, e.target.checked)}
                disabled={disabled}
              />
              <span>{field.label}</span>
            </label>
            {field.hint ? <div className="stm-config-hint">{field.hint}</div> : null}
          </div>
        );
      }

      if (field.type === "select") {
        return (
          <div key={field.configKey} className="stm-config-field">
            <label htmlFor={`exec_${field.configKey}`}>{field.label}</label>
            <select
              id={`exec_${field.configKey}`}
              value={String(rawValue ?? "")}
              onChange={(e) => updateConfigValue(field.configKey, e.target.value)}
              disabled={disabled}
            >
              {field.options.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            {field.hint ? <div className="stm-config-hint">{field.hint}</div> : null}
          </div>
        );
      }

      if (field.type === "text") {
        return (
          <div key={field.configKey} className="stm-config-field">
            <label htmlFor={`exec_${field.configKey}`}>{field.label}</label>
            <input
              id={`exec_${field.configKey}`}
              type="text"
              value={String(rawValue ?? "")}
              placeholder={field.placeholder || ""}
              onChange={(e) => updateConfigValue(field.configKey, e.target.value)}
              disabled={disabled}
            />
            {field.hint ? <div className="stm-config-hint">{field.hint}</div> : null}
          </div>
        );
      }

      return (
        <div key={field.configKey} className="stm-config-field">
          <label htmlFor={`exec_${field.configKey}`}>{field.label}</label>
          <input
            id={`exec_${field.configKey}`}
            type="number"
            min={field.min}
            max={field.max}
            step={field.step}
            value={Number.isFinite(Number(rawValue)) ? Number(rawValue) : ""}
            onChange={(e) => handleNumberFieldChange(field, e.target.value)}
            disabled={disabled}
          />
          {field.hint ? <div className="stm-config-hint">{field.hint}</div> : null}
        </div>
      );
    },
    [configState, handleNumberFieldChange, updateConfigValue]
  );

  const enabledCount = useMemo(
    () => ALL_MODULE_KEYS.filter((k) => !!moduleState[k]).length,
    [moduleState]
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
        setHoveredModule(name);
      }, 300);
    },
    []
  );

  const handleMouseLeave = useCallback(() => {
    if (hoverTimeoutRef.current) clearTimeout(hoverTimeoutRef.current);
    setHoveredModule(null);
  }, []);

  // ─── Expanded mode (for Studio page) ───
  if (mode === "expanded") {
    return (
      <div className="stm-expanded">
        {EXEC_CATEGORY_ORDER.map((cat) => {
          const keysInCat = ALL_MODULE_KEYS.filter((k) => EXEC_MODULE_META[k].category === cat);
          if (!keysInCat.length) return null;
          return (
            <div key={cat} className="stm-expanded-category">
              <div className="stm-expanded-category-label">{EXEC_CATEGORY_LABELS[cat]}</div>
              <div className="stm-expanded-grid">
                {keysInCat.map((key) => {
                  const meta = EXEC_MODULE_META[key];
                  const enabled = !!moduleState[key];
                  return (
                    <button
                      key={key}
                      className={`stm-expanded-card ${enabled ? "enabled" : "disabled"}`}
                      onClick={() => toggleModule(key, !enabled)}
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
        <span className="stm-header-label">Global Modules</span>
        <span className="stm-header-count">
          {enabledCount}/{ALL_MODULE_KEYS.length}
        </span>
      </div>

      <div className="stm-list">
        {ALL_MODULE_KEYS.map((key) => {
          const meta = EXEC_MODULE_META[key];
          const enabled = !!moduleState[key];
          const fields = MODULE_SETTING_FIELDS[key] || [];
          const hasSettings = fields.length > 0;
          const isExpanded = !!expandedModules[key];

          return (
            <div
              key={key}
              className={`stm-row ${enabled ? "enabled" : "disabled"} ${isExpanded ? "open" : ""}`}
              onMouseEnter={(e) => handleMouseEnter(e, key)}
              onMouseLeave={handleMouseLeave}
            >
              <div className="stm-row-main">
                <button
                  className="stm-toggle-area"
                  onClick={() => toggleModule(key, !enabled)}
                  title={`${enabled ? "Disable" : "Enable"} ${meta.label}`}
                >
                  <span className={`stm-dot ${enabled ? "on" : "off"}`} />
                  <span className="stm-label">{meta.label}</span>
                </button>
                {hasSettings && (
                  <button
                    type="button"
                    className={`stm-expand-btn ${isExpanded ? "open" : ""}`}
                    onClick={(e) => {
                      e.stopPropagation();
                      toggleExpanded(key);
                    }}
                    title={isExpanded ? "Hide parameters" : "Show parameters"}
                    aria-label={isExpanded ? `Hide ${meta.label} parameters` : `Show ${meta.label} parameters`}
                  >
                    ▾
                  </button>
                )}
                {onNavigateToRiskLimits && (
                  <button
                    className="stm-gear"
                    onClick={(e) => {
                      e.stopPropagation();
                      onNavigateToRiskLimits();
                    }}
                    title={`Configure ${meta.label}`}
                  >
                    ⚙
                  </button>
                )}
              </div>
              {isExpanded && hasSettings && (
                <div className="stm-config-panel">
                  <div className="stm-config-grid">{fields.map((field) => renderModuleField(field))}</div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Tooltip */}
      {hoveredModule && EXEC_MODULE_META[hoveredModule] && (
        <div
          className="stm-tooltip"
          style={{ top: tooltipPos.top, left: tooltipPos.left }}
        >
          <div className="stm-tooltip-title">
            {EXEC_MODULE_META[hoveredModule].label}
          </div>
          <div className="stm-tooltip-desc">
            {EXEC_MODULE_META[hoveredModule].description}
          </div>
          <div className="stm-tooltip-category">
            {EXEC_MODULE_META[hoveredModule].category.toUpperCase()}
          </div>
        </div>
      )}
    </div>
  );
}
