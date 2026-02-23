import { useState, useCallback, useMemo, useRef } from "react";
import { defaultStrategyApiUrl } from "../../utils";

export interface UseStrategySettingsStateProps {
  apiUrl?: string;
  selectedTicker?: string;
}

export function useStrategySettingsState({
  apiUrl,
}: UseStrategySettingsStateProps) {
  const [strategies, setStrategies] = useState<Record<string, any> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [drafts, setDrafts] = useState<Record<string, Record<string, any>>>({});
  const [showCoreOnly, setShowCoreOnly] = useState(true);
  const [showProNotes, setShowProNotes] = useState(true);
  const [strategyCategory, setStrategyCategory] = useState("all");
  const [autoExpandedTicker, setAutoExpandedTicker] = useState("");
  const [tooltipStrategy, setTooltipStrategy] = useState<string | null>(null);
  const [tooltipPos, setTooltipPos] = useState({ top: 0, left: 0 });
  
  const hoverTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const resolvedUrl = apiUrl || defaultStrategyApiUrl;

  const fetchStrategies = useCallback(async () => {
    if (!resolvedUrl) return null;
    setLoading(true);
    setError(null);
    try {
      const resp = await fetch(`${resolvedUrl}/api/strategies`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      setStrategies(data);
      return data;
    } catch (err: any) {
      setError(`Failed to load strategies: ${err.message}`);
      return null;
    } finally {
      setLoading(false);
    }
  }, [resolvedUrl]);

  const toggleExpanded = useCallback((name: string) => {
    setExpanded((prev) => ({ ...prev, [name]: !prev[name] }));
    setDrafts((prev) => ({
      ...prev,
      [name]: prev[name] || strategies?.[name] || {},
    }));
  }, [strategies]);

  const toggleStrategy = useCallback(async (name: string, enabled: boolean) => {
    try {
      setStrategies((prev) =>
        prev ? { ...prev, [name]: { ...prev[name], enabled } } : prev,
      );
      const resp = await fetch(`${resolvedUrl}/api/strategies/toggle`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ strategy_name: name, enabled }),
      });
      if (!resp.ok) throw new Error(`Toggle failed: ${resp.status}`);
    } catch (err: any) {
      setError(err.message);
      fetchStrategies();
    }
  }, [resolvedUrl, fetchStrategies]);

  const updateDraftField = useCallback((name: string, field: string, value: any) => {
    setDrafts((prev) => ({
      ...prev,
      [name]: { ...(prev[name] || {}), [field]: value },
    }));
  }, []);

  const saveDraft = useCallback(async (name: string) => {
    const draft = drafts[name];
    if (!draft) return;
    try {
      const params = { ...draft };
      // Delete properties that shouldn't be overridden
      delete params.enabled;
      delete params.name;
      delete params.display_name;
      delete params.open_positions;
      delete params.total_signals;
      delete params.last_signal;
      delete params.global_trailing_stop_pct;
      delete params.effective_trailing_stop_pct;
      delete params.global_rr_ratio;
      delete params.effective_rr_ratio;
      delete params.global_atr_stop_multiplier;
      delete params.effective_atr_stop_multiplier;
      delete params.global_volume_stop_pct;
      delete params.effective_volume_stop_pct;
      delete params.global_min_stop_loss_pct;
      delete params.effective_min_stop_loss_pct;
      delete params.custom_formula_supported_variables;
      delete params.custom_formula_variable_docs;
      delete params.custom_formula_examples;

      const resp = await fetch(`${resolvedUrl}/api/strategies/update`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ strategy_name: name, params }),
      });
      if (!resp.ok) throw new Error(`Update failed: ${resp.status}`);
      const data = await resp.json();
      setStrategies((prev) =>
        prev ? { ...prev, [name]: data.current } : prev,
      );
      setDrafts((prev) => ({ ...prev, [name]: data.current }));
    } catch (err: any) {
      setError(err.message);
      fetchStrategies();
    }
  }, [drafts, resolvedUrl, fetchStrategies]);

  const appendFormulaToken = useCallback(
    (name: string, field: string, token: string) => {
      setDrafts((prev) => {
        const existingDraft = { ...(prev[name] || {}) };
        const currentBase =
          existingDraft[field] ?? strategies?.[name]?.[field] ?? "";
        const current = String(currentBase || "");
        const needsSpace = current.length > 0 && !/\s$/.test(current);
        const next = `${current}${needsSpace ? " " : ""}${token}`;
        return {
          ...prev,
          [name]: { ...existingDraft, [field]: next },
        };
      });
    },
    [strategies],
  );

  const handleReset = useCallback(async (name: string) => {
    const fresh = await fetchStrategies();
    const latest = fresh?.[name] || strategies?.[name] || {};
    setDrafts((prev) => ({ ...prev, [name]: latest }));
  }, [fetchStrategies, strategies]);

  return {
    strategies,
    setStrategies,
    loading,
    error,
    setError,
    expanded,
    setExpanded,
    drafts,
    setDrafts,
    showCoreOnly,
    setShowCoreOnly,
    showProNotes,
    setShowProNotes,
    strategyCategory,
    setStrategyCategory,
    autoExpandedTicker,
    setAutoExpandedTicker,
    tooltipStrategy,
    setTooltipStrategy,
    tooltipPos,
    setTooltipPos,
    hoverTimeoutRef,
    resolvedUrl,
    fetchStrategies,
    toggleExpanded,
    toggleStrategy,
    updateDraftField,
    saveDraft,
    appendFormulaToken,
    handleReset
  };
}
