import { useCallback, useEffect, useRef } from "react";
import type { Dispatch, SetStateAction } from "react";

type UseAttachedRunHydrationArgs = {
  activeRunKey: string;
  activeRunState: Record<string, any> | null;
  runningRunOptions: any[];
  effectiveExecutionConfig: Record<string, any> | null;
  currentTicker: string;
  onTickerChange?: (ticker: string) => void;
  setConfig: Dispatch<SetStateAction<Record<string, any>>>;
  setSelectedUnifiedProfileId: (profileId: string) => void;
  resolveAttachedRunDates: (runRow: Record<string, any>) => {
    date: string;
    date_from: string;
    date_to: string;
  };
  normalizeProfileRefToken: (value: any) => string;
  parseRunKeyIdentity: (runKey: string) => Record<string, any> | null;
};

export const useAttachedRunHydration = ({
  activeRunKey,
  activeRunState,
  runningRunOptions,
  effectiveExecutionConfig,
  currentTicker,
  onTickerChange,
  setConfig,
  setSelectedUnifiedProfileId,
  resolveAttachedRunDates,
  normalizeProfileRefToken,
  parseRunKeyIdentity,
}: UseAttachedRunHydrationArgs) => {
  const lastHydratedAttachedRunKeyRef = useRef("");

  const markHydratedAttachedRunKey = useCallback((runKey: string) => {
    lastHydratedAttachedRunKeyRef.current = String(runKey || "").trim();
  }, []);

  const hydrateConfigFromAttachedRun = useCallback(
    (runRow: Record<string, any>) => {
      if (!runRow || typeof runRow !== "object") return;

      const runId = String(runRow.run_id || "").trim();
      const ticker = String(runRow.ticker || "").trim().toUpperCase();
      const normalizedDates = resolveAttachedRunDates(runRow);
      const date = normalizedDates.date;
      const dateFrom = normalizedDates.date_from;
      const dateTo = normalizedDates.date_to;
      const executionConfig =
        runRow.execution_config && typeof runRow.execution_config === "object"
          ? runRow.execution_config
          : effectiveExecutionConfig && typeof effectiveExecutionConfig === "object"
            ? effectiveExecutionConfig
            : {};
      const includeExtendedHours =
        typeof executionConfig.include_extended_hours === "boolean"
          ? executionConfig.include_extended_hours
          : typeof runRow.include_extended_hours === "boolean"
            ? runRow.include_extended_hours
            : null;

      setConfig((prev) => {
        const patch: Record<string, any> = {};
        const prevTicker = String(prev.ticker || "").trim().toUpperCase();

        if (runId && runId !== String(prev.run_id || "")) patch.run_id = runId;
        if (ticker && ticker !== prevTicker) patch.ticker = ticker;
        if (date && date !== String(prev.date || "")) patch.date = date;
        if (dateFrom && dateFrom !== String(prev.date_from || "")) patch.date_from = dateFrom;
        if (dateTo && dateTo !== String(prev.date_to || "")) patch.date_to = dateTo;
        if (
          typeof includeExtendedHours === "boolean" &&
          includeExtendedHours !== Boolean(prev.include_extended_hours)
        ) {
          patch.include_extended_hours = includeExtendedHours;
        }

        if (!Object.keys(patch).length) return prev;
        return {
          ...prev,
          ...patch,
        };
      });

      if (ticker && onTickerChange && ticker !== String(currentTicker || "").trim().toUpperCase()) {
        onTickerChange(ticker);
      }

      const reportMeta =
        runRow.report_metadata && typeof runRow.report_metadata === "object"
          ? runRow.report_metadata
          : {};
      const aosApplied =
        runRow.aos_applied && typeof runRow.aos_applied === "object" ? runRow.aos_applied : {};
      const unifiedMeta =
        aosApplied.unified_profile && typeof aosApplied.unified_profile === "object"
          ? aosApplied.unified_profile
          : {};
      const runProfileId = normalizeProfileRefToken(
        reportMeta.unified_profile_id ||
          runRow.unified_profile_id ||
          executionConfig.unified_profile_id ||
          unifiedMeta.active_profile_id ||
          unifiedMeta.profile_id,
      );
      if (runProfileId) {
        setSelectedUnifiedProfileId(runProfileId);
      }
    },
    [
      resolveAttachedRunDates,
      effectiveExecutionConfig,
      setConfig,
      onTickerChange,
      currentTicker,
      normalizeProfileRefToken,
      setSelectedUnifiedProfileId,
    ],
  );

  useEffect(() => {
    const targetRunKey = String(activeRunKey || "").trim();
    if (!targetRunKey) {
      lastHydratedAttachedRunKeyRef.current = "";
      return;
    }
    if (lastHydratedAttachedRunKeyRef.current === targetRunKey) {
      return;
    }
    const selected = runningRunOptions.find(
      (row) => String(row?.run_key || "").trim() === targetRunKey,
    );
    if (selected) {
      hydrateConfigFromAttachedRun(selected);
      lastHydratedAttachedRunKeyRef.current = targetRunKey;
      return;
    }

    const parsedFromKey = parseRunKeyIdentity(targetRunKey) || {};
    if (activeRunState && typeof activeRunState === "object") {
      hydrateConfigFromAttachedRun({
        ...activeRunState,
        ...parsedFromKey,
      });
      lastHydratedAttachedRunKeyRef.current = targetRunKey;
      return;
    }
    if (parsedFromKey && parsedFromKey.run_id) {
      hydrateConfigFromAttachedRun(parsedFromKey);
      lastHydratedAttachedRunKeyRef.current = targetRunKey;
    }
  }, [
    activeRunKey,
    activeRunState,
    hydrateConfigFromAttachedRun,
    parseRunKeyIdentity,
    runningRunOptions,
  ]);

  return {
    hydrateConfigFromAttachedRun,
    markHydratedAttachedRunKey,
  };
};
