import { useEffect, useMemo, useCallback, useState } from "react";
import { useTickerStrategyPresets } from "./strategy-settings/useTickerStrategyPresets";
import { AosHistoryTimeline } from "./strategy-settings/AosHistoryTimeline";
import { useStrategySettingsState, UseStrategySettingsStateProps } from "./strategy-settings/useStrategySettingsState";
import { StrategyFieldRenderer } from "./strategy-settings/StrategyFieldRenderer";
import { ProFieldGuide, ProPlaybookItem, StrategyRuleOverview } from "./strategy-settings/types";
import {
  BUILTIN_RULE_OVERVIEW,
  DEFAULT_BUILTIN_RULE_OVERVIEW,
  DEFAULT_PRO_PLAYBOOK,
  PRO_FIELD_GUIDE,
  PRO_STRATEGY_PLAYBOOK,
  STRATEGY_DESCRIPTIONS,
  STRATEGY_RECOMMENDED_PARAMS,
} from "./strategy-settings/strategySettingsKnowledge";
import {
  buildFocusFieldLayout,
  FLOW_CORE_STRATEGIES,
  buildEditableFieldGroups,
  formatCategoryLabel,
  formatFieldLabel,
  getStrategyWarning,
  resolveStrategyCategory,
} from "./strategy-settings/strategySettingsGrouping";
interface StrategySettingsProps extends UseStrategySettingsStateProps {
  initialExpandAll?: boolean;
}

export default function StrategySettings({
  apiUrl,
  selectedTicker,
  initialExpandAll = false,
}: StrategySettingsProps) {
  const state = useStrategySettingsState({ apiUrl, selectedTicker });
  const [focusMode, setFocusMode] = useState(true);
  const [strategyQuery, setStrategyQuery] = useState("");
  const [advancedVisible, setAdvancedVisible] = useState<Record<string, boolean>>(
    {},
  );
  const [referenceVisible, setReferenceVisible] = useState<Record<string, boolean>>(
    {},
  );

  const applyRecommended = useCallback(async (name: string) => {
    const recommended = STRATEGY_RECOMMENDED_PARAMS[name as keyof typeof STRATEGY_RECOMMENDED_PARAMS];
    if (!recommended) return;
    try {
      const resp = await fetch(`${state.resolvedUrl}/api/strategies/update`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ strategy_name: name, params: recommended }),
      });
      if (!resp.ok) throw new Error(`Update failed: ${resp.status}`);
      const data = await resp.json();
      state.setStrategies((prev) =>
        prev ? { ...prev, [name]: data.current } : prev,
      );
      state.setDrafts((prev) => ({ ...prev, [name]: data.current }));
    } catch (err: any) {
      state.setError(err.message);
      state.fetchStrategies();
    }
  }, [state.resolvedUrl, state.setStrategies, state.setDrafts, state.setError, state.fetchStrategies]);

  const onApplyStrategyState = useCallback((strategyName: string, current: any) => {
    state.setStrategies((prev) =>
      prev ? { ...prev, [strategyName]: current } : prev,
    );
    state.setDrafts((prev) => ({ ...prev, [strategyName]: current }));
  }, [state.setStrategies, state.setDrafts]);

  // Hook usages
  useTickerStrategyPresets({
    selectedTicker,
    resolvedUrl: state.resolvedUrl,
    onApplyStrategyState,
    fetchStrategies: state.fetchStrategies,
  });

  useEffect(() => {
    state.setShowCoreOnly(selectedTicker === "MU");
  }, [selectedTicker, state.setShowCoreOnly]);

  useEffect(() => {
    state.fetchStrategies();
  }, [state.fetchStrategies]);

  useEffect(() => {
    const handler = (event: any) => {
      const ticker = String(event?.detail?.ticker || "")
        .toUpperCase()
        .trim();
      const selected = String(selectedTicker || "")
        .toUpperCase()
        .trim();
      if (!ticker || !selected || ticker !== selected) return;
      state.fetchStrategies();
    };
    window.addEventListener("adaptive-profile-updated", handler);
    return () =>
      window.removeEventListener("adaptive-profile-updated", handler);
  }, [state.fetchStrategies, selectedTicker]);

  useEffect(() => {
    if (!initialExpandAll || !state.strategies) return;
    const tickerKey =
      String(selectedTicker || "")
        .toUpperCase()
        .trim() || "ALL";
    if (state.autoExpandedTicker === tickerKey) return;
    const rows = Object.entries(state.strategies || {});
    if (!rows.length) return;
    const nextExp: Record<string, boolean> = {};
    const nextDr: Record<string, Record<string, any>> = {};
    rows.forEach(([name, cfg]) => {
      nextExp[name] = true;
      nextDr[name] = cfg && typeof cfg === "object" ? cfg : {};
    });
    state.setExpanded((prev) => ({ ...nextExp, ...prev }));
    state.setDrafts((prev) => ({ ...nextDr, ...prev }));
    state.setAutoExpandedTicker(tickerKey);
  }, [state.autoExpandedTicker, initialExpandAll, selectedTicker, state.strategies, state.setExpanded, state.setDrafts, state.setAutoExpandedTicker]);

  const strategyEntries = useMemo(() => {
    if (!state.strategies) return [];
    const sorted = Object.entries(state.strategies).sort((a, b) => {
      const aE = a[1]?.enabled ? 1 : 0;
      const bE = b[1]?.enabled ? 1 : 0;
      if (aE !== bE) return bE - aE;
      return String(a[1]?.display_name || a[0]).localeCompare(
        String(b[1]?.display_name || b[0]),
      );
    });
    const withCoreFilter =
      selectedTicker === "MU" && state.showCoreOnly
        ? sorted.filter(([name]) => FLOW_CORE_STRATEGIES.has(name))
        : sorted;
    const withCategoryFilter =
      state.strategyCategory === "all"
        ? withCoreFilter
        : withCoreFilter.filter(
      ([name]) => resolveStrategyCategory(name) === state.strategyCategory,
    );
    const normalizedQuery = strategyQuery.trim().toLowerCase();
    if (!normalizedQuery) return withCategoryFilter;
    return withCategoryFilter.filter(([name, cfg]) => {
      const displayName = String(cfg?.display_name || cfg?.name || name).toLowerCase();
      const normalizedName = String(name || "").replace(/_/g, " ").toLowerCase();
      return (
        displayName.includes(normalizedQuery) ||
        normalizedName.includes(normalizedQuery)
      );
    });
  }, [
    state.strategies,
    selectedTicker,
    state.showCoreOnly,
    state.strategyCategory,
    strategyQuery,
  ]);

  const expandAllVisible = useCallback(() => {
    if (!strategyEntries.length) return;
    const nextExp: Record<string, boolean> = {};
    const nextDr: Record<string, Record<string, any>> = {};
    strategyEntries.forEach(([name, cfg]) => {
      nextExp[name] = true;
      nextDr[name] = cfg && typeof cfg === "object" ? cfg : {};
    });
    state.setExpanded((prev) => ({ ...prev, ...nextExp }));
    state.setDrafts((prev) => ({ ...nextDr, ...prev }));
  }, [strategyEntries, state.setExpanded, state.setDrafts]);

  const collapseAllVisible = useCallback(() => {
    if (!strategyEntries.length) return;
    const visibleKeys = new Set(strategyEntries.map(([name]) => name));
    state.setExpanded((prev) => {
      const next = { ...prev };
      visibleKeys.forEach((name) => {
        next[name] = false;
      });
      return next;
    });
  }, [strategyEntries, state.setExpanded]);

  const getFieldGuide = useCallback((field: string): ProFieldGuide | null => {
    return PRO_FIELD_GUIDE[field] || null;
  }, []);

  const getStrategyPlaybook = useCallback((name: string): ProPlaybookItem[] => {
    return PRO_STRATEGY_PLAYBOOK[name] || DEFAULT_PRO_PLAYBOOK;
  }, []);

  const getStrategyRuleOverview = useCallback(
    (name: string): StrategyRuleOverview => {
      return BUILTIN_RULE_OVERVIEW[name] || DEFAULT_BUILTIN_RULE_OVERVIEW;
    },
    [],
  );
  
  const enabledCount = useMemo(
    () => strategyEntries.filter(([, cfg]) => !!cfg?.enabled).length,
    [strategyEntries],
  );

  const warningByStrategy = useMemo(() => {
    const next: Record<string, string | null> = {};
    strategyEntries.forEach(([name, cfg]) => {
      next[name] = getStrategyWarning(name, cfg);
    });
    return next;
  }, [strategyEntries]);

  const editableGroupsByStrategy = useMemo(() => {
    const next: Record<string, Array<[string, Array<[string, any]>]>> = {};
    strategyEntries.forEach(([name, cfg]) => {
      next[name] = buildEditableFieldGroups(name, cfg);
    });
    return next;
  }, [strategyEntries]);

  const focusLayoutByStrategy = useMemo(() => {
    const next: Record<
      string,
      ReturnType<typeof buildFocusFieldLayout>
    > = {};
    strategyEntries.forEach(([name, cfg]) => {
      next[name] = buildFocusFieldLayout(name, cfg);
    });
    return next;
  }, [strategyEntries]);

  const toggleAdvancedVisibility = useCallback((name: string) => {
    setAdvancedVisible((prev) => ({ ...prev, [name]: !prev[name] }));
  }, []);

  const toggleReferenceVisibility = useCallback((name: string) => {
    setReferenceVisible((prev) => ({ ...prev, [name]: !prev[name] }));
  }, []);

  const handleNameMouseEnter = useCallback(
    (e: React.MouseEvent, name: string) => {
      if (state.hoverTimeoutRef.current) clearTimeout(state.hoverTimeoutRef.current);
      const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
      state.setTooltipPos({ top: rect.bottom + 6, left: rect.left });
      state.hoverTimeoutRef.current = setTimeout(() => state.setTooltipStrategy(name), 250);
    },
    [state.hoverTimeoutRef, state.setTooltipPos, state.setTooltipStrategy],
  );

  const handleNameMouseLeave = useCallback(() => {
    if (state.hoverTimeoutRef.current) clearTimeout(state.hoverTimeoutRef.current);
    state.setTooltipStrategy(null);
  }, [state.hoverTimeoutRef, state.setTooltipStrategy]);

  return (
    <div className="sc-panel">
      {/* Toolbar */}
      <div className="sc-toolbar">
        <div className="sc-toolbar-left">
          <span className="sc-counter">
            {enabledCount}/{strategyEntries.length}
          </span>
          <select
            value={state.strategyCategory}
            onChange={(e) => state.setStrategyCategory(e.target.value)}
            className="sc-select"
            title="Filter strategy category"
          >
            <option value="all">All categories</option>
            <option value="flow">Flow</option>
            <option value="scalp">Scalp</option>
            <option value="other">Other</option>
          </select>
          {selectedTicker === "MU" && (
            <button
              className={`sc-chip-btn ${state.showCoreOnly ? "active" : ""}`}
              onClick={() => state.setShowCoreOnly((prev) => !prev)}
            >
              Core Only
            </button>
          )}
          <button
            className={`sc-chip-btn sc-chip-btn-focus ${focusMode ? "active" : ""}`}
            onClick={() => setFocusMode((prev) => !prev)}
            title="Focus view hides deep-dive controls until you need them"
          >
            {focusMode ? "Focus View" : "Show All"}
          </button>
          <button
            className={`sc-chip-btn sc-chip-btn-pro ${state.showProNotes ? "active" : ""}`}
            onClick={() => state.setShowProNotes((prev) => !prev)}
            title="Show professional setting guidance"
          >
            Pro Notes
          </button>
        </div>
        <div className="sc-toolbar-right">
          <input
            type="search"
            value={strategyQuery}
            onChange={(e) => setStrategyQuery(e.target.value)}
            className="sc-search-input"
            placeholder="Find strategy..."
            aria-label="Find strategy"
          />
          <button
            className="sc-icon-btn"
            onClick={state.fetchStrategies}
            disabled={state.loading}
            title="Refresh"
          >
            {state.loading ? "…" : "↻"}
          </button>
          <button
            className="sc-icon-btn"
            onClick={expandAllVisible}
            disabled={!strategyEntries.length}
            title="Expand all"
          >
            ⬇
          </button>
          <button
            className="sc-icon-btn"
            onClick={collapseAllVisible}
            disabled={!strategyEntries.length}
            title="Collapse all"
          >
            ⬆
          </button>
        </div>
      </div>

      {/* Status */}
      {state.error && <div className="sc-msg sc-msg-error">{state.error}</div>}
      {!state.strategies && !state.error && !state.loading && (
        <div className="sc-msg">No data</div>
      )}
      {selectedTicker === "MU" && state.showCoreOnly && (
        <div className="sc-msg">Core MU flow strategies only.</div>
      )}
      {state.strategies && strategyEntries.length === 0 && (
        <div className="sc-msg">No strategies match the filter.</div>
      )}

      {/* Strategy list */}
      <div className="sc-list">
        {state.strategies &&
          strategyEntries.map(([name, cfg]) => {
            const displayName = cfg.display_name || cfg.name || name;
            const regimes =
              (cfg.allowed_regimes || cfg.regimes || []).join(", ") || "all";
            const categoryKey = resolveStrategyCategory(name);
            const warning = warningByStrategy[name];
            const editableGroups = editableGroupsByStrategy[name] || [];
            const focusLayout = focusLayoutByStrategy[name];
            const isExpanded = !!state.expanded[name];
            const visibleAdvanced = !focusMode || !!advancedVisible[name];
            const visibleReference = !focusMode || !!referenceVisible[name];
            const primaryFieldCount = focusLayout?.focusFieldCount ?? 0;
            const advancedFieldCount = focusLayout?.advancedFieldCount ?? 0;
            return (
              <div
                key={name}
                className={`sc-item ${cfg.enabled ? "on" : "off"} ${isExpanded ? "open" : ""}`}
              >
                {/* Card header row */}
                <div
                  className="sc-item-head"
                  onClick={() => state.toggleExpanded(name)}
                >
                  <div className="sc-item-info">
                    <span
                      className="sc-item-name"
                      onMouseEnter={(e) => {
                        e.stopPropagation();
                        handleNameMouseEnter(e, name);
                      }}
                      onMouseLeave={handleNameMouseLeave}
                    >
                      {displayName}
                    </span>
                    <span className={`sc-cat ${categoryKey}`}>
                      {formatCategoryLabel(categoryKey)}
                    </span>
                    <span className="sc-regimes">{regimes}</span>
                    <span className="sc-density">
                      {focusMode
                        ? `${primaryFieldCount} core${advancedFieldCount ? ` + ${advancedFieldCount} advanced` : ""}`
                        : `${editableGroups.reduce(
                            (sum, [, fields]) => sum + fields.length,
                            0,
                          )} controls`}
                    </span>
                  </div>
                  <div
                    className="sc-item-controls"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <label className="switch">
                      <input
                        type="checkbox"
                        checked={cfg.enabled}
                        onChange={(e) => state.toggleStrategy(name, e.target.checked)}
                      />
                      <span className="slider" />
                    </label>
                  </div>
                  <span
                    className={`sc-expand-arrow ${isExpanded ? "open" : ""}`}
                  >
                    ›
                  </span>
                </div>

                {/* Expanded edit panel */}
                {isExpanded && (
                  <div className="sc-item-body">
                    {warning && <div className="sc-warning">⚠ {warning}</div>}
                    <div className="sc-hero-card">
                      <div className="sc-hero-head">
                        <div>
                          <div className="sc-hero-kicker">Strategy Flight Deck</div>
                          <div className="sc-hero-title">
                            {focusMode
                              ? "High-signal controls only"
                              : "Full strategy control surface"}
                          </div>
                        </div>
                        <span className="sc-core-count">
                          {focusMode
                            ? `${primaryFieldCount} core knobs`
                            : `${focusLayout?.totalEditableFields || 0} live controls`}
                        </span>
                      </div>
                      <div className="sc-summary-strip">
                        <span className="sc-summary-pill">
                          Regimes {regimes}
                        </span>
                        <span className="sc-summary-pill">
                          Risk {String(cfg?.risk_mode || "custom")}
                        </span>
                        <span className="sc-summary-pill">
                          Exit {String(cfg?.exit_mode || cfg?.trailing_stop_mode || "custom")}
                        </span>
                        {typeof cfg?.effective_trailing_stop_pct === "number" && (
                          <span className="sc-summary-pill">
                            Trail {Number(cfg.effective_trailing_stop_pct).toFixed(2)}%
                          </span>
                        )}
                        {typeof cfg?.effective_rr_ratio === "number" && (
                          <span className="sc-summary-pill">
                            RR {Number(cfg.effective_rr_ratio).toFixed(2)}
                          </span>
                        )}
                        {typeof cfg?.effective_atr_stop_multiplier === "number" && (
                          <span className="sc-summary-pill">
                            ATR x{Number(cfg.effective_atr_stop_multiplier).toFixed(2)}
                          </span>
                        )}
                      </div>
                      <div className="sc-hero-note">
                        {focusMode
                          ? "Front-load only the parameters that materially change trigger quality, risk shape, and live readiness."
                          : "Deep view exposes every editable field group for full system tuning and diagnostics."}
                      </div>
                    </div>

                    {!!focusLayout?.focusFields.length && (
                      <div className="sc-focus-card">
                        <div className="sc-section-heading">
                          <div className="sc-section-title">Core Setup</div>
                          <div className="sc-section-subtitle">
                            Essential tuning and live configuration controls.
                          </div>
                        </div>
                        <div className="sc-grid sc-grid-focus">
                          {focusLayout.focusFields.map(([field, value]) => (
                            <StrategyFieldRenderer
                              key={field}
                              name={name}
                              field={field}
                              value={value}
                              drafts={state.drafts}
                              strategies={state.strategies}
                              updateDraftField={state.updateDraftField}
                              appendFormulaToken={state.appendFormulaToken}
                              setDrafts={state.setDrafts}
                              showProNotes={state.showProNotes}
                              getFieldGuide={getFieldGuide}
                              formatFieldLabel={formatFieldLabel}
                            />
                          ))}
                        </div>
                      </div>
                    )}

                    {focusMode && (
                      <div className="sc-progressive-bar">
                        {advancedFieldCount > 0 && (
                          <button
                            className={`sc-stack-btn ${visibleAdvanced ? "active" : ""}`}
                            onClick={() => toggleAdvancedVisibility(name)}
                          >
                            {visibleAdvanced
                              ? "Hide advanced controls"
                              : `Open advanced controls (${advancedFieldCount})`}
                          </button>
                        )}
                        <button
                          className={`sc-stack-btn sc-stack-btn-secondary ${visibleReference ? "active" : ""}`}
                          onClick={() => toggleReferenceVisibility(name)}
                        >
                          {visibleReference ? "Hide system notes" : "Show system notes"}
                        </button>
                        {focusMode && !!focusLayout?.advancedGroups.length && (
                          <span className="sc-progressive-hint">
                            Hidden lanes:{" "}
                            {focusLayout.advancedGroups
                              .map(([groupLabel]) => groupLabel)
                              .join(" · ")}
                          </span>
                        )}
                      </div>
                    )}

                    {visibleAdvanced &&
                      focusLayout?.advancedGroups.map(([groupLabel, groupFields]) => (
                        <div key={groupLabel} className="sc-section sc-section-advanced">
                          <div className="sc-section-heading">
                            <div className="sc-section-title">{groupLabel}</div>
                            <div className="sc-section-subtitle">
                              Deep-dive controls for precise tuning.
                            </div>
                          </div>
                          <div className="sc-grid">
                            {groupFields.map(([field, value]) => (
                              <StrategyFieldRenderer
                                key={field}
                                name={name}
                                field={field}
                                value={value}
                                drafts={state.drafts}
                                strategies={state.strategies}
                                updateDraftField={state.updateDraftField}
                                appendFormulaToken={state.appendFormulaToken}
                                setDrafts={state.setDrafts}
                                showProNotes={state.showProNotes}
                                getFieldGuide={getFieldGuide}
                                formatFieldLabel={formatFieldLabel}
                              />
                            ))}
                          </div>
                        </div>
                      ))}

                    {visibleReference && (
                      <div className="sc-reference-stack">
                        {(() => {
                          const ruleOverview = getStrategyRuleOverview(name);
                          return (
                            <div className="sc-rule-card">
                              <div className="sc-rule-title">
                                Built-in Entry Checks
                              </div>
                              <ul className="sc-rule-list">
                                {ruleOverview.entry.map((item, idx) => (
                                  <li
                                    key={`${name}-entry-${idx}`}
                                    className="sc-rule-item"
                                  >
                                    {item}
                                  </li>
                                ))}
                              </ul>
                              <div className="sc-rule-title">
                                Built-in Exit Checks
                              </div>
                              <ul className="sc-rule-list">
                                {ruleOverview.exit.map((item, idx) => (
                                  <li
                                    key={`${name}-exit-${idx}`}
                                    className="sc-rule-item"
                                  >
                                    {item}
                                  </li>
                                ))}
                              </ul>
                            </div>
                          );
                        })()}
                        {state.showProNotes && (
                          <div className="sc-pro-card">
                            <div className="sc-pro-title">
                              Professional Playbook
                            </div>
                            <div className="sc-pro-grid">
                              {getStrategyPlaybook(name).map((item) => (
                                <div
                                  key={`${name}-${item.label}`}
                                  className="sc-pro-item"
                                >
                                  <span className="sc-pro-key">{item.label}:</span>{" "}
                                  {item.guidance}
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    )}

                    <div className="sc-actions">
                      <button
                        className="sc-btn"
                        onClick={() => state.handleReset(name)}
                      >
                        Reset
                      </button>
                      {STRATEGY_RECOMMENDED_PARAMS[name as keyof typeof STRATEGY_RECOMMENDED_PARAMS] && (
                        <button
                          className="sc-btn"
                          onClick={() => applyRecommended(name)}
                        >
                          Recommended
                        </button>
                      )}
                      <button
                        className="sc-btn sc-btn-primary"
                        onClick={() => state.saveDraft(name)}
                      >
                        Save
                      </button>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
      </div>
      
      {/* AOS Parameters Evolution History Timeline */}
      {selectedTicker && (
        <AosHistoryTimeline ticker={selectedTicker} />
      )}

      {/* Tooltip */}
      {state.tooltipStrategy && STRATEGY_DESCRIPTIONS[state.tooltipStrategy] && (
        <div
          className="strategy-tooltip"
          style={{ top: state.tooltipPos.top, left: state.tooltipPos.left }}
        >
          {STRATEGY_DESCRIPTIONS[state.tooltipStrategy]}
        </div>
      )}
    </div>
  );
}
