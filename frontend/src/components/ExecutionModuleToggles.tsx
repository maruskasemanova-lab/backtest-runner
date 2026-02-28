import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ALL_MODULE_KEYS,
  EXEC_CATEGORY_LABELS,
  EXEC_CATEGORY_ORDER,
  EXEC_CONFIG_SNAPSHOT_EVENT,
  EXEC_CONFIG_SNAPSHOT_REQUEST_EVENT,
  EXEC_MODULE_META,
  EXEC_MODULE_TOGGLE_EVENT,
  MODULE_SETTING_FIELDS,
  type ModuleSettingField,
} from "./execution-modules/executionModuleSchema";

export {
  EXEC_CONFIG_SNAPSHOT_EVENT,
  EXEC_MODULE_TOGGLE_EVENT,
} from "./execution-modules/executionModuleSchema";

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
      window.dispatchEvent(new CustomEvent(EXEC_CONFIG_SNAPSHOT_REQUEST_EVENT));
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
