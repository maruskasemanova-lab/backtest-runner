import { useCallback, useEffect, useState } from "react";

interface UseTickerStrategyPresetsArgs {
  selectedTicker?: string;
  resolvedUrl: string;
  onApplyStrategyState: (strategyName: string, current: Record<string, unknown>) => void;
  fetchStrategies: () => Promise<Record<string, any> | null>;
}

interface UseTickerStrategyPresetsResult {
  tickerPresets: Record<string, Record<string, Record<string, unknown>>>;
  presetsLoaded: boolean;
  applyTickerPresets: (ticker: string) => Promise<void>;
  enableAllStrategies: () => Promise<void>;
}

const MU_TICKER = "MU";

export function useTickerStrategyPresets({
  selectedTicker,
  resolvedUrl,
  onApplyStrategyState,
  fetchStrategies,
}: UseTickerStrategyPresetsArgs): UseTickerStrategyPresetsResult {
  const [tickerPresets, setTickerPresets] = useState<
    Record<string, Record<string, Record<string, unknown>>>
  >({});
  const [presetsLoaded, setPresetsLoaded] = useState(false);

  useEffect(() => {
    const fetchPresets = async () => {
      try {
        const resp = await fetch("/api/strategy-overrides");
        if (resp.ok) {
          const data = await resp.json();
          setTickerPresets(data || {});
          setPresetsLoaded(true);
        }
      } catch (err) {
        console.error("Failed to load ticker presets:", err);
      }
    };
    fetchPresets();
  }, []);

  const applyTickerPresets = useCallback(
    async (ticker: string) => {
      if (!ticker || !presetsLoaded) return;

      const presets = tickerPresets[ticker];
      if (!presets) return;

      for (const [stratName, params] of Object.entries(presets)) {
        try {
          const resp = await fetch(`${resolvedUrl}/api/strategies/update`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ strategy_name: stratName, params }),
          });
          if (resp.ok) {
            const data = await resp.json();
            onApplyStrategyState(stratName, data.current || {});
          }
        } catch (err) {
          console.error(`Failed to apply preset for ${stratName}:`, err);
        }
      }
    },
    [onApplyStrategyState, presetsLoaded, resolvedUrl, tickerPresets],
  );

  const enableAllStrategies = useCallback(async () => {
    if (!resolvedUrl) return;
    try {
      const resp = await fetch(`${resolvedUrl}/api/strategies`);
      if (!resp.ok) return;
      const data = await resp.json();
      const strategyNames = Object.keys(data || {});
      if (!strategyNames.length) return;

      await Promise.all(
        strategyNames.map((strategyName) =>
          fetch(`${resolvedUrl}/api/strategies/update`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              strategy_name: strategyName,
              params: { enabled: true },
            }),
          }).catch(() => null),
        ),
      );
      await fetchStrategies();
    } catch (err) {
      console.error("Failed to enable all strategies:", err);
    }
  }, [fetchStrategies, resolvedUrl]);

  useEffect(() => {
    if (!selectedTicker || !presetsLoaded) return;
    const upperTicker = String(selectedTicker || "").trim().toUpperCase();
    (async () => {
      await applyTickerPresets(upperTicker);
      if (upperTicker === MU_TICKER) {
        await enableAllStrategies();
      }
    })();
  }, [selectedTicker, presetsLoaded, applyTickerPresets, enableAllStrategies]);

  return {
    tickerPresets,
    presetsLoaded,
    applyTickerPresets,
    enableAllStrategies,
  };
}
