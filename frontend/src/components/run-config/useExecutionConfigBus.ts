import { useEffect, useRef, type Dispatch, type SetStateAction } from "react";

const EXEC_CONFIG_SNAPSHOT_EVENT = "execution-config-snapshot";
const EXEC_CONFIG_SNAPSHOT_REQUEST_EVENT = "execution-config-snapshot-request";
const EXEC_MODULE_TOGGLE_EVENT = "execution-module-toggle";

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
      setConfig((prev) => ({ ...prev, [configKey]: value }));
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
