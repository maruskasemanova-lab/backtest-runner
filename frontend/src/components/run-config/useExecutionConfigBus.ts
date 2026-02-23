import { useEffect, useRef, type Dispatch, type SetStateAction } from "react";

const EXEC_CONFIG_SNAPSHOT_EVENT = "execution-config-snapshot";
const EXEC_CONFIG_SNAPSHOT_REQUEST_EVENT = "execution-config-snapshot-request";
const EXEC_MODULE_TOGGLE_EVENT = "execution-module-toggle";
const DEFAULT_FIXED_STOP_LOSS_PCT = 0.3;

const normalizeStopLossMode = (value: unknown): "strategy" | "fixed" | "capped" => {
  const normalized = String(value || "").trim().toLowerCase();
  if (normalized === "fixed" || normalized === "capped") {
    return normalized;
  }
  return "strategy";
};

const resolveFixedStopLossPct = (mode: unknown, value: unknown): number => {
  const normalizedMode = normalizeStopLossMode(mode);
  const parsed = Number(value);
  if (normalizedMode === "strategy") {
    return Number.isFinite(parsed) ? Math.max(0, parsed) : 0;
  }
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return DEFAULT_FIXED_STOP_LOSS_PCT;
  }
  return parsed;
};

const isSupportedExecutionValue = (value: unknown): value is string | number | boolean => {
  return (
    typeof value === "boolean" ||
    typeof value === "number" ||
    typeof value === "string"
  );
};

export const useExecutionConfigBus = <T extends Record<string, any>>(
  config: T,
  setConfig: Dispatch<SetStateAction<T>>,
): void => {
  const configRef = useRef(config);
  configRef.current = config;

  useEffect(() => {
    const handleToggle = (event: Event) => {
      const detail = (event as CustomEvent).detail || {};
      const configKey = detail?.configKey;
      const value = detail?.value;
      if (typeof configKey !== "string" || !isSupportedExecutionValue(value)) {
        return;
      }
      setConfig((prev) => {
        if (configKey === "stop_loss_mode") {
          const nextStopLossMode = normalizeStopLossMode(value);
          return {
            ...prev,
            stop_loss_mode: nextStopLossMode,
            fixed_stop_loss_pct: resolveFixedStopLossPct(
              nextStopLossMode,
              prev.fixed_stop_loss_pct,
            ),
          };
        }
        if (configKey === "fixed_stop_loss_pct") {
          return {
            ...prev,
            fixed_stop_loss_pct: resolveFixedStopLossPct(prev.stop_loss_mode, value),
          };
        }
        return { ...prev, [configKey]: value };
      });
    };

    const handleSnapshotRequest = () => {
      window.dispatchEvent(
        new CustomEvent(EXEC_CONFIG_SNAPSHOT_EVENT, { detail: configRef.current }),
      );
    };

    window.addEventListener(EXEC_MODULE_TOGGLE_EVENT, handleToggle);
    window.addEventListener(EXEC_CONFIG_SNAPSHOT_REQUEST_EVENT, handleSnapshotRequest);

    (window as any).__executionConfig = configRef.current;
    window.dispatchEvent(
      new CustomEvent(EXEC_CONFIG_SNAPSHOT_EVENT, { detail: configRef.current }),
    );

    return () => {
      window.removeEventListener(EXEC_MODULE_TOGGLE_EVENT, handleToggle);
      window.removeEventListener(
        EXEC_CONFIG_SNAPSHOT_REQUEST_EVENT,
        handleSnapshotRequest,
      );
    };
  }, [setConfig]);

  useEffect(() => {
    (window as any).__executionConfig = config;
    window.dispatchEvent(new CustomEvent(EXEC_CONFIG_SNAPSHOT_EVENT, { detail: config }));
  }, [config]);
};
