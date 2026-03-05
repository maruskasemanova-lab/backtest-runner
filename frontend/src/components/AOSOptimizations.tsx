import { useCallback, useEffect, useState } from "react";
import AOSOptimizationsMomentumEditor from "./aos-optimizations/AOSOptimizationsMomentumEditor";
import {
  createDefaultMomentumDraft,
  createDefaultSleeveDraft,
  mergeMomentumIntoTickerConfig,
  normalizeMomentumDraft,
  parseTickerConfigText,
  resolveRunnerUrl,
  safeArray,
  safeObject,
  type AOSMomentumDraft,
  type AOSMomentumSleeveDraft,
  type AOSOptimizationsRecord,
} from "./aos-optimizations/aosOptimizationsMomentum";

type AOSOptimizationsProps = {
  apiUrl?: string;
  onOptimizationChange?: (ticker: string, config: AOSOptimizationsRecord) => void;
  selectedTicker?: string;
};

function AOSOptimizations({
  apiUrl,
  onOptimizationChange,
  selectedTicker,
}: AOSOptimizationsProps) {
  const [aosConfig, setAosConfig] = useState<AOSOptimizationsRecord>({ tickers: {} });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [rawConfigText, setRawConfigText] = useState("");
  const [rawConfigError, setRawConfigError] = useState<string | null>(null);
  const [rawConfigSaving, setRawConfigSaving] = useState(false);
  const [rawConfigDirty, setRawConfigDirty] = useState(false);
  const [momentumDraft, setMomentumDraft] = useState<AOSMomentumDraft>(createDefaultMomentumDraft);
  const [momentumDirty, setMomentumDirty] = useState(false);
  const [momentumSaving, setMomentumSaving] = useState(false);
  const [momentumError, setMomentumError] = useState<string | null>(null);
  const [momentumNotice, setMomentumNotice] = useState<string | null>(null);

  const selectedTickerKey = (selectedTicker || "").toUpperCase();

  const fetchAOSConfig = useCallback(async () => {
    setLoading(true);
    setError(null);
    const runnerUrl = resolveRunnerUrl(apiUrl);

    try {
      const resp = await fetch(`${runnerUrl}/api/aos-config`);
      if (!resp.ok) {
        throw new Error(`HTTP ${resp.status}`);
      }
      const payload = await resp.json();
      const normalized = safeObject(payload);
      normalized.tickers = safeObject(normalized.tickers);
      setAosConfig(normalized);
    } catch (err) {
      console.log("AOS config API unavailable", err);
      setError("AOS config API is unavailable.");
      setAosConfig({ tickers: {} });
    } finally {
      setLoading(false);
    }
  }, [apiUrl]);

  useEffect(() => {
    void fetchAOSConfig();
  }, [fetchAOSConfig]);

  useEffect(() => {
    if (!selectedTickerKey) {
      setRawConfigText("");
      setRawConfigError(null);
      setRawConfigDirty(false);
      setMomentumDraft(createDefaultMomentumDraft());
      setMomentumDirty(false);
      setMomentumError(null);
      setMomentumNotice(null);
      return;
    }

    const tickerConfig = safeObject(safeObject(aosConfig).tickers?.[selectedTickerKey]);
    const momentumCfg = safeObject(safeObject(tickerConfig.adaptive).momentum_diversification);
    setRawConfigText(JSON.stringify(tickerConfig, null, 2));
    setRawConfigError(null);
    setRawConfigDirty(false);
    setMomentumDraft(normalizeMomentumDraft(momentumCfg));
    setMomentumDirty(false);
    setMomentumError(null);
    setMomentumNotice(null);
  }, [selectedTickerKey, aosConfig]);

  const persistConfig = useCallback(
    async (tickerKey: string, configValue: AOSOptimizationsRecord) => {
      if (!tickerKey) return;
      const runnerUrl = resolveRunnerUrl(apiUrl);

      const resp = await fetch(`${runnerUrl}/api/aos-config/update`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ticker: tickerKey,
          config: configValue,
        }),
      });

      if (!resp.ok) {
        throw new Error(`HTTP ${resp.status}`);
      }
    },
    [apiUrl],
  );

  const applyRawConfig = async () => {
    if (!selectedTickerKey) return;

    let parsed: AOSOptimizationsRecord;
    try {
      parsed = parseTickerConfigText(rawConfigText || "{}");
    } catch (err) {
      setRawConfigError(err instanceof Error ? err.message : String(err));
      return;
    }

    const nextConfig = safeObject(parsed);
    setRawConfigSaving(true);
    setRawConfigError(null);

    try {
      await persistConfig(selectedTickerKey, nextConfig);

      setAosConfig((prev) => ({
        ...safeObject(prev),
        tickers: {
          ...safeObject(prev?.tickers),
          [selectedTickerKey]: nextConfig,
        },
      }));

      setRawConfigText(JSON.stringify(nextConfig, null, 2));
      setRawConfigDirty(false);
      const momentumCfg = safeObject(safeObject(nextConfig.adaptive).momentum_diversification);
      setMomentumDraft(normalizeMomentumDraft(momentumCfg));
      setMomentumDirty(false);
      setMomentumError(null);
      setMomentumNotice("Visual momentum editor synced from saved JSON.");
      setError(null);

      if (onOptimizationChange) {
        onOptimizationChange(selectedTickerKey, nextConfig);
      }
    } catch (err) {
      console.log("Could not save AOS config to server", err);
      setError("Could not save AOS config to server. Changes are local only.");
    } finally {
      setRawConfigSaving(false);
    }
  };

  const resetRawConfig = () => {
    if (!selectedTickerKey) return;
    const tickerConfig = safeObject(safeObject(aosConfig).tickers?.[selectedTickerKey]);
    const momentumCfg = safeObject(safeObject(tickerConfig.adaptive).momentum_diversification);
    setRawConfigText(JSON.stringify(tickerConfig, null, 2));
    setRawConfigError(null);
    setRawConfigDirty(false);
    setMomentumDraft(normalizeMomentumDraft(momentumCfg));
    setMomentumDirty(false);
    setMomentumError(null);
    setMomentumNotice("Reset to persisted ticker config.");
  };

  const handleMomentumChange = (field: keyof AOSMomentumDraft, value: unknown) => {
    setMomentumDraft((prev) => ({ ...prev, [field]: value }));
    setMomentumDirty(true);
    setMomentumError(null);
    setMomentumNotice(null);
  };

  const handleSleeveChange = (
    index: number,
    field: keyof AOSMomentumSleeveDraft,
    value: unknown,
  ) => {
    setMomentumDraft((prev) => {
      const current = safeArray<AOSMomentumSleeveDraft>(prev?.sleeves);
      if (index < 0 || index >= current.length) return prev;
      return {
        ...prev,
        sleeves: current.map((item, idx) =>
          idx === index ? { ...safeObject(item), [field]: value } : item,
        ) as AOSMomentumSleeveDraft[],
      };
    });
    setMomentumDirty(true);
    setMomentumError(null);
    setMomentumNotice(null);
  };

  const addSleeve = () => {
    setMomentumDraft((prev) => {
      const current = safeArray<AOSMomentumSleeveDraft>(prev?.sleeves);
      return {
        ...prev,
        sleeves: [...current, createDefaultSleeveDraft(current.length + 1)],
      };
    });
    setMomentumDirty(true);
    setMomentumError(null);
    setMomentumNotice(null);
  };

  const removeSleeve = (index: number) => {
    setMomentumDraft((prev) => {
      const current = safeArray<AOSMomentumSleeveDraft>(prev?.sleeves);
      return {
        ...prev,
        sleeves: current.filter((_, idx) => idx !== index),
      };
    });
    setMomentumDirty(true);
    setMomentumError(null);
    setMomentumNotice(null);
  };

  const loadMomentumFromEditor = () => {
    try {
      const parsed = parseTickerConfigText(rawConfigText || "{}");
      const momentumCfg = safeObject(safeObject(parsed.adaptive).momentum_diversification);
      setMomentumDraft(normalizeMomentumDraft(momentumCfg));
      setMomentumDirty(false);
      setMomentumError(null);
      setMomentumNotice("Loaded momentum settings from JSON editor.");
    } catch (err) {
      setMomentumError(err instanceof Error ? err.message : String(err));
    }
  };

  const applyMomentumToEditor = () => {
    try {
      const base = parseTickerConfigText(rawConfigText || "{}");
      const nextConfig = mergeMomentumIntoTickerConfig(base, momentumDraft);
      setRawConfigText(JSON.stringify(nextConfig, null, 2));
      setRawConfigDirty(true);
      setRawConfigError(null);
      setMomentumDirty(false);
      setMomentumError(null);
      setMomentumNotice("Applied visual momentum settings to JSON editor.");
    } catch (err) {
      setMomentumError(err instanceof Error ? err.message : String(err));
    }
  };

  const saveMomentumDirect = async () => {
    if (!selectedTickerKey) return;
    setMomentumSaving(true);
    setMomentumError(null);
    setMomentumNotice(null);
    try {
      let baseConfig = safeObject(safeObject(aosConfig).tickers?.[selectedTickerKey]);
      if (rawConfigDirty) {
        baseConfig = parseTickerConfigText(rawConfigText || "{}");
      }
      const nextConfig = mergeMomentumIntoTickerConfig(baseConfig, momentumDraft);
      await persistConfig(selectedTickerKey, nextConfig);

      setAosConfig((prev) => ({
        ...safeObject(prev),
        tickers: {
          ...safeObject(prev?.tickers),
          [selectedTickerKey]: nextConfig,
        },
      }));
      setRawConfigText(JSON.stringify(nextConfig, null, 2));
      setRawConfigDirty(false);
      setRawConfigError(null);
      setMomentumDraft(
        normalizeMomentumDraft(safeObject(safeObject(nextConfig.adaptive).momentum_diversification)),
      );
      setMomentumDirty(false);
      setMomentumNotice("Saved visual momentum settings to server.");
      setError(null);

      if (onOptimizationChange) {
        onOptimizationChange(selectedTickerKey, nextConfig);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setMomentumError(
        rawConfigDirty
          ? `Cannot save while JSON editor is invalid: ${message}`
          : `Could not save visual momentum settings: ${message}`,
      );
    } finally {
      setMomentumSaving(false);
    }
  };

  const hasTickerConfig =
    !!selectedTickerKey &&
    Object.prototype.hasOwnProperty.call(safeObject(safeObject(aosConfig).tickers), selectedTickerKey);

  if (!selectedTickerKey) {
    return (
      <div className="card">
        <div className="card-header">
          <span className="card-title">AOS Config</span>
        </div>
        <div className="card-body ui-muted">
          Select a ticker to edit AOS configuration from file.
        </div>
      </div>
    );
  }

  return (
    <div className="card aos-config-card">
      <div className="card-header">
        <span className="card-title">AOS Config - {selectedTickerKey}</span>
        <button className="btn btn-secondary" onClick={fetchAOSConfig} disabled={loading || rawConfigSaving || momentumSaving}>
          Reload
        </button>
      </div>

      <div className="card-body aos-config-body">
        {loading && <div className="ui-note ui-note-compact">Loading config...</div>}
        {error && <div className="ui-note ui-note-danger ui-note-compact">{error}</div>}

        <div className="ui-note ui-note-compact">
          Source of truth: DB-backed config snapshots exposed via <code>/api/aos-config</code>.
          Local files under <code>aos_optimization/</code> are bootstrap and compatibility inputs, not the primary runtime store.
          Saved changes are applied on the next <code>/api/run/start</code>.
        </div>

        {!hasTickerConfig && (
          <div className="ui-note ui-note-warning ui-note-compact">
            No existing config for {selectedTickerKey} in file. Editing starts from an empty object.
          </div>
        )}

        <AOSOptimizationsMomentumEditor
          momentumDraft={momentumDraft}
          momentumDirty={momentumDirty}
          momentumSaving={momentumSaving}
          momentumError={momentumError}
          momentumNotice={momentumNotice}
          rawConfigSaving={rawConfigSaving}
          onLoadFromJson={loadMomentumFromEditor}
          onApplyToJson={applyMomentumToEditor}
          onSaveToServer={saveMomentumDirect}
          onMomentumChange={handleMomentumChange}
          onSleeveChange={handleSleeveChange}
          onAddSleeve={addSleeve}
          onRemoveSleeve={removeSleeve}
        />

        <textarea
          value={rawConfigText}
          onChange={(e) => {
            setRawConfigText(e.target.value);
            setRawConfigDirty(true);
            setRawConfigError(null);
          }}
          className="ui-code-area aos-config-editor"
        />

        {rawConfigError && (
          <div className="ui-note ui-note-danger ui-note-compact">
            {rawConfigError}
          </div>
        )}

        <div className="ui-actions">
          <button className="btn btn-primary" onClick={applyRawConfig} disabled={rawConfigSaving || !rawConfigDirty}>
            {rawConfigSaving ? "Saving..." : "Apply JSON"}
          </button>
          <button className="btn btn-secondary" onClick={resetRawConfig} disabled={rawConfigSaving || momentumSaving}>
            Reset
          </button>
        </div>
      </div>
    </div>
  );
}

export default AOSOptimizations;
