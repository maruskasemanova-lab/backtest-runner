import { useCallback, useEffect, useState } from "react";
import type { Dispatch, SetStateAction } from "react";

type UseRunConfigCheckpointsArgs = {
  strategyApiBase: string;
  selectedStartMode: string;
  resumeWarmStartModeValue: string;
  config: Record<string, any>;
  setConfig: Dispatch<SetStateAction<Record<string, any>>>;
};

export const useRunConfigCheckpoints = ({
  strategyApiBase,
  selectedStartMode,
  resumeWarmStartModeValue,
  config,
  setConfig,
}: UseRunConfigCheckpointsArgs) => {
  const [checkpointCatalog, setCheckpointCatalog] = useState<any[]>([]);
  const [checkpointLoading, setCheckpointLoading] = useState(false);
  const [checkpointSaving, setCheckpointSaving] = useState(false);
  const [checkpointMessage, setCheckpointMessage] = useState<string | null>(null);
  const [checkpointApiUnavailable, setCheckpointApiUnavailable] = useState(false);

  const formatCheckpointLabel = useCallback((item: any) => {
    const path = item?.path || "";
    const file = path.split(/[\\/]/).pop() || path || "(unknown)";
    const created = item?.created_at ? new Date(item.created_at).toLocaleString() : "unknown time";
    const trades = Number(item?.source?.total_trades || 0);
    const wr = item?.source?.win_rate;
    const wrText = typeof wr === "number" ? `${(wr * 100).toFixed(1)}%` : "n/a";
    return `${file} | ${trades} trades | WR ${wrText} | ${created}`;
  }, []);

  const fetchCheckpoints = useCallback(
    async (preferredPath: string | null = null) => {
      if (!strategyApiBase || checkpointApiUnavailable) {
        return;
      }

      setCheckpointLoading(true);
      setCheckpointMessage(null);
      try {
        const resp = await fetch(`${strategyApiBase}/api/orchestrator/checkpoints`);
        if (!resp.ok) {
          if (resp.status === 401 || resp.status === 403 || resp.status === 404) {
            setCheckpointApiUnavailable(true);
            setCheckpointCatalog([]);
            setCheckpointMessage("Checkpoint catalog is not available in this environment.");
            return;
          }
          throw new Error(`HTTP ${resp.status}`);
        }

        const payload = await resp.json();
        const catalog = Array.isArray(payload) ? payload : [];
        setCheckpointCatalog(catalog);

        if (preferredPath) {
          setConfig((prev) => ({ ...prev, checkpoint_path: preferredPath }));
        } else if (
          selectedStartMode === resumeWarmStartModeValue &&
          !config.checkpoint_path &&
          catalog.length > 0
        ) {
          setConfig((prev) => ({ ...prev, checkpoint_path: catalog[0].path || null }));
        }
      } catch (err) {
        setCheckpointApiUnavailable(true);
        console.warn("Checkpoint catalog load disabled:", err);
        setCheckpointMessage("Checkpoint API is not reachable right now.");
      } finally {
        setCheckpointLoading(false);
      }
    },
    [
      strategyApiBase,
      checkpointApiUnavailable,
      selectedStartMode,
      resumeWarmStartModeValue,
      config.checkpoint_path,
      setConfig,
    ],
  );

  const handleSaveCheckpointNow = useCallback(async () => {
    if (!strategyApiBase) {
      setCheckpointMessage("Strategy API URL is missing.");
      return;
    }

    setCheckpointSaving(true);
    setCheckpointMessage(null);
    try {
      const params = new URLSearchParams();
      if (config.run_id) params.set("run_id", config.run_id);
      if (config.ticker) params.set("ticker", config.ticker);
      if (config.date_from) params.set("date_from", config.date_from);
      if (config.date_to) params.set("date_to", config.date_to);
      const query = params.toString();
      const saveUrl = `${strategyApiBase}/api/orchestrator/checkpoint/save${query ? `?${query}` : ""}`;

      const resp = await fetch(saveUrl, { method: "POST" });
      if (!resp.ok) {
        throw new Error(`HTTP ${resp.status}`);
      }

      const payload = await resp.json();
      const savedPath = payload?.path || null;
      if (savedPath) {
        setConfig((prev) => ({
          ...prev,
          start_mode: resumeWarmStartModeValue,
          checkpoint_path: savedPath,
        }));
        await fetchCheckpoints(savedPath);
      }
      setCheckpointMessage(savedPath ? `Checkpoint saved: ${savedPath}` : "Checkpoint saved.");
    } catch (err) {
      console.error("Checkpoint save failed:", err);
      setCheckpointMessage("Checkpoint save failed.");
    } finally {
      setCheckpointSaving(false);
    }
  }, [strategyApiBase, config, resumeWarmStartModeValue, setConfig, fetchCheckpoints]);

  useEffect(() => {
    setCheckpointApiUnavailable(false);
    fetchCheckpoints();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [strategyApiBase]);

  return {
    checkpointCatalog,
    checkpointLoading,
    checkpointSaving,
    checkpointMessage,
    checkpointApiUnavailable,
    formatCheckpointLabel,
    fetchCheckpoints,
    handleSaveCheckpointNow,
  };
};
