import { useEffect, useState, useCallback } from "react";

/**
 * MultiLayerSettings – configures both decision modes:
 * - Legacy multi-layer engine (pattern + strategy weighted scoring)
 * - Evidence-based orchestrator engine
 *
 * Talks directly to the strategy API (port 8001) endpoints:
 *   GET  /api/multilayer/config
 *   POST /api/multilayer/config
 *   GET  /api/orchestrator/config
 *   POST /api/orchestrator/config
 */
function MultiLayerSettings({ apiUrl }) {
  const [config, setConfig] = useState(null);
  const [draft, setDraft] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [engineConfig, setEngineConfig] = useState(null);
  const [engineDraft, setEngineDraft] = useState(null);
  const [engineLoading, setEngineLoading] = useState(false);
  const [engineError, setEngineError] = useState(null);
  const [engineSaving, setEngineSaving] = useState(false);
  const [engineSaved, setEngineSaved] = useState(false);
  const [evidenceSaved, setEvidenceSaved] = useState(false);
  const [saved, setSaved] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [detectorExpanded, setDetectorExpanded] = useState(false);

  const resolvedUrl =
    apiUrl || `http://${window.location.hostname}:8001`;

  const fetchConfig = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await fetch(`${resolvedUrl}/api/multilayer/config`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      setConfig(data);
      setDraft({ ...data });
    } catch (err) {
      setError(`Failed to load: ${err.message}`);
    } finally {
      setLoading(false);
    }
  }, [resolvedUrl]);

  const fetchEngineConfig = useCallback(async () => {
    setEngineLoading(true);
    setEngineError(null);
    try {
      const resp = await fetch(`${resolvedUrl}/api/orchestrator/config`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      setEngineConfig(data);
      if (typeof data?.use_evidence_engine === "boolean") {
        setEngineDraft({
          min_confirming_sources: Number(data.min_confirming_sources ?? 2),
          base_threshold: Number(data.base_threshold ?? 55),
          use_adaptive_regime: Boolean(data.use_adaptive_regime ?? true),
          use_calibration: Boolean(data.use_calibration ?? true),
          use_quality_sizing: Boolean(data.use_quality_sizing ?? true),
          use_cross_asset: Boolean(data.use_cross_asset ?? true),
          use_edge_monitor: Boolean(data.use_edge_monitor ?? true),
        });
      }
    } catch (err) {
      setEngineError(`Failed to load engine config: ${err.message}`);
    } finally {
      setEngineLoading(false);
    }
  }, [resolvedUrl]);

  const saveEngineConfig = async (useEvidenceEngine) => {
    setEngineSaving(true);
    setEngineSaved(false);
    setEngineError(null);
    try {
      const resp = await fetch(`${resolvedUrl}/api/orchestrator/config`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ use_evidence_engine: useEvidenceEngine }),
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      await fetchEngineConfig();
      setEngineSaved(true);
      setTimeout(() => setEngineSaved(false), 2000);
    } catch (err) {
      setEngineError(`Engine switch failed: ${err.message}`);
    } finally {
      setEngineSaving(false);
    }
  };

  const updateEngineField = (field, value) => {
    setEngineDraft((prev) => ({ ...prev, [field]: value }));
  };

  const resetEvidenceDraft = () => {
    if (!engineConfig || typeof engineConfig.use_evidence_engine !== "boolean") {
      return;
    }
    setEngineDraft({
      min_confirming_sources: Number(engineConfig.min_confirming_sources ?? 2),
      base_threshold: Number(engineConfig.base_threshold ?? 55),
      use_adaptive_regime: Boolean(engineConfig.use_adaptive_regime ?? true),
      use_calibration: Boolean(engineConfig.use_calibration ?? true),
      use_quality_sizing: Boolean(engineConfig.use_quality_sizing ?? true),
      use_cross_asset: Boolean(engineConfig.use_cross_asset ?? true),
      use_edge_monitor: Boolean(engineConfig.use_edge_monitor ?? true),
    });
  };

  const saveEvidenceConfig = async () => {
    if (!engineDraft) return;
    setEngineSaving(true);
    setEngineError(null);
    setEvidenceSaved(false);
    try {
      const payload = {
        min_confirming_sources: Number(engineDraft.min_confirming_sources),
        base_threshold: Number(engineDraft.base_threshold),
        use_adaptive_regime: Boolean(engineDraft.use_adaptive_regime),
        use_calibration: Boolean(engineDraft.use_calibration),
        use_quality_sizing: Boolean(engineDraft.use_quality_sizing),
        use_cross_asset: Boolean(engineDraft.use_cross_asset),
        use_edge_monitor: Boolean(engineDraft.use_edge_monitor),
      };
      const resp = await fetch(`${resolvedUrl}/api/orchestrator/config`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      await fetchEngineConfig();
      setEvidenceSaved(true);
      setTimeout(() => setEvidenceSaved(false), 2000);
    } catch (err) {
      setEngineError(`Evidence settings save failed: ${err.message}`);
    } finally {
      setEngineSaving(false);
    }
  };

  useEffect(() => {
    fetchConfig();
    fetchEngineConfig();
  }, [fetchConfig, fetchEngineConfig]);

  const saveConfig = async () => {
    if (!draft) return;
    setError(null);
    setSaved(false);
    try {
      const payload = {
        pattern_weight: draft.pattern_weight,
        strategy_weight: draft.strategy_weight,
        threshold: draft.threshold,
        strategy_only_threshold: draft.strategy_only_threshold,
        require_pattern: draft.require_pattern,
        // detector sub-fields
        ...(draft.detector || {}),
      };
      const resp = await fetch(`${resolvedUrl}/api/multilayer/config`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      setConfig(data.current);
      setDraft({ ...data.current });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (err) {
      setError(`Save failed: ${err.message}`);
    }
  };

  const updateField = (field, value) => {
    setDraft((prev) => ({ ...prev, [field]: value }));
  };

  const updateDetectorField = (field, value) => {
    setDraft((prev) => ({
      ...prev,
      detector: { ...(prev?.detector || {}), [field]: value },
    }));
  };

  const resetDraft = () => {
    if (config) setDraft({ ...config });
  };

  // Compute whether weights sum to 1
  const weightSum = (draft?.pattern_weight || 0) + (draft?.strategy_weight || 0);
  const weightWarning = Math.abs(weightSum - 1.0) > 0.01;
  const hasEngineToggle = typeof engineConfig?.use_evidence_engine === "boolean";
  const isEvidenceMode = hasEngineToggle && !!engineConfig?.use_evidence_engine;
  const showLegacyControls = !hasEngineToggle || engineConfig?.use_evidence_engine === false;

  return (
    <div className="card">
      <div
        className="card-header"
        style={{ cursor: "pointer", userSelect: "none" }}
        onClick={() => setExpanded((p) => !p)}
      >
        <span className="card-title">Multi-Layer Engine</span>
        <span style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
          {expanded ? "▲" : "▼"}
        </span>
      </div>

      {expanded && (
        <div
          className="card-body"
          style={{ display: "flex", flexDirection: "column", gap: 10 }}
        >
          {error && (
            <div style={{ color: "var(--accent-red)", fontSize: "0.85rem" }}>
              {error}
            </div>
          )}
          {loading && (
            <div style={{ color: "var(--text-muted)", fontSize: "0.85rem" }}>
              Loading...
            </div>
          )}

          <div
            style={{
              fontSize: "0.8rem",
              fontWeight: 600,
              color: "var(--text-secondary)",
              borderBottom: "1px solid var(--border-color)",
              paddingBottom: 4,
            }}
          >
            Decision Engine
          </div>

          {engineError && (
            <div style={{ color: "var(--accent-red)", fontSize: "0.85rem" }}>
              {engineError}
            </div>
          )}

          {engineLoading && (
            <div style={{ color: "var(--text-muted)", fontSize: "0.85rem" }}>
              Loading engine config...
            </div>
          )}

          {engineConfig && (
            <>
              <div className="field-row">
                <span className="field-label">Mode</span>
                <span
                  style={{
                    fontSize: "0.82rem",
                    fontWeight: 600,
                    color: "var(--text-primary)",
                  }}
                >
                  {hasEngineToggle
                    ? (engineConfig.use_evidence_engine ? "Evidence-based" : "Legacy multi-layer")
                    : "Unavailable"}
                </span>
              </div>

              {hasEngineToggle ? (
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "1fr 1fr",
                    gap: 8,
                  }}
                >
                  <button
                    className="btn btn-secondary"
                    disabled={engineSaving || !!engineConfig.use_evidence_engine}
                    onClick={() => saveEngineConfig(true)}
                  >
                    Use Evidence
                  </button>
                  <button
                    className="btn btn-secondary"
                    disabled={engineSaving || engineConfig.use_evidence_engine === false}
                    onClick={() => saveEngineConfig(false)}
                  >
                    Use Legacy
                  </button>
                </div>
              ) : (
                <div style={{ color: "var(--text-muted)", fontSize: "0.8rem" }}>
                  Strategy API does not expose orchestrator toggle.
                </div>
              )}

              <div
                style={{
                  background: "var(--bg-card)",
                  border: "1px solid var(--border-color)",
                  borderRadius: 6,
                  padding: "8px 10px",
                  fontSize: "0.78rem",
                  color: "var(--text-muted)",
                  lineHeight: 1.45,
                }}
              >
                {isEvidenceMode
                  ? "Evidence mode uses dynamic threshold + confirming sources. Legacy pattern/strategy weights are not used for execution."
                  : "Legacy mode uses pattern + strategy weighted scoring. Evidence mode uses confirming sources with dynamic threshold."}
              </div>

              {engineSaved && (
                <div style={{ color: "var(--accent-green)", fontSize: "0.8rem" }}>
                  Engine updated
                </div>
              )}

              {isEvidenceMode && engineDraft && (
                <>
                  <div
                    style={{
                      fontSize: "0.8rem",
                      fontWeight: 600,
                      color: "var(--text-secondary)",
                      borderBottom: "1px solid var(--border-color)",
                      paddingBottom: 4,
                    }}
                  >
                    Evidence Settings
                  </div>

                  <div className="field-row">
                    <span className="field-label">Min confirming sources</span>
                    <input
                      type="number"
                      step="1"
                      min="1"
                      max="10"
                      value={engineDraft.min_confirming_sources ?? 2}
                      onChange={(e) =>
                        updateEngineField("min_confirming_sources", Number(e.target.value))
                      }
                      className="field-input"
                      style={{ width: 70 }}
                    />
                  </div>

                  <div className="field-row">
                    <span className="field-label">Base threshold</span>
                    <input
                      type="number"
                      step="1"
                      min="0"
                      max="100"
                      value={engineDraft.base_threshold ?? 55}
                      onChange={(e) =>
                        updateEngineField("base_threshold", Number(e.target.value))
                      }
                      className="field-input"
                      style={{ width: 70 }}
                    />
                  </div>

                  <div className="field-row">
                    <span className="field-label">Adaptive regime</span>
                    <input
                      type="checkbox"
                      checked={engineDraft.use_adaptive_regime ?? true}
                      onChange={(e) =>
                        updateEngineField("use_adaptive_regime", e.target.checked)
                      }
                    />
                  </div>

                  <div className="field-row">
                    <span className="field-label">Calibration</span>
                    <input
                      type="checkbox"
                      checked={engineDraft.use_calibration ?? true}
                      onChange={(e) =>
                        updateEngineField("use_calibration", e.target.checked)
                      }
                    />
                  </div>

                  <div className="field-row">
                    <span className="field-label">Quality sizing</span>
                    <input
                      type="checkbox"
                      checked={engineDraft.use_quality_sizing ?? true}
                      onChange={(e) =>
                        updateEngineField("use_quality_sizing", e.target.checked)
                      }
                    />
                  </div>

                  <div className="field-row">
                    <span className="field-label">Cross-asset context</span>
                    <input
                      type="checkbox"
                      checked={engineDraft.use_cross_asset ?? true}
                      onChange={(e) =>
                        updateEngineField("use_cross_asset", e.target.checked)
                      }
                    />
                  </div>

                  <div className="field-row">
                    <span className="field-label">Edge monitor</span>
                    <input
                      type="checkbox"
                      checked={engineDraft.use_edge_monitor ?? true}
                      onChange={(e) =>
                        updateEngineField("use_edge_monitor", e.target.checked)
                      }
                    />
                  </div>

                  <div
                    style={{
                      display: "flex",
                      justifyContent: "flex-end",
                      gap: 8,
                      marginTop: 6,
                    }}
                  >
                    <button
                      className="btn btn-secondary"
                      onClick={resetEvidenceDraft}
                      disabled={engineSaving}
                    >
                      Reset
                    </button>
                    <button
                      className="btn btn-primary"
                      onClick={saveEvidenceConfig}
                      disabled={engineSaving}
                    >
                      Save Evidence
                    </button>
                    {evidenceSaved && (
                      <span
                        style={{
                          color: "var(--accent-green)",
                          fontSize: "0.8rem",
                          alignSelf: "center",
                        }}
                      >
                        Saved
                      </span>
                    )}
                  </div>
                </>
              )}
            </>
          )}

          {draft && showLegacyControls && (
            <>
              {/* ── Scoring weights ──────────────────────── */}
              <div
                style={{
                  fontSize: "0.8rem",
                  fontWeight: 600,
                  color: "var(--text-secondary)",
                  borderBottom: "1px solid var(--border-color)",
                  paddingBottom: 4,
                }}
              >
                Scoring Weights
              </div>

              <div className="field-row">
                <span className="field-label">Pattern weight</span>
                <input
                  type="number"
                  step="0.05"
                  min="0"
                  max="1"
                  value={draft.pattern_weight ?? 0.4}
                  onChange={(e) =>
                    updateField("pattern_weight", Number(e.target.value))
                  }
                  className="field-input"
                  style={{ width: 70 }}
                />
              </div>

              <div className="field-row">
                <span className="field-label">Strategy weight</span>
                <input
                  type="number"
                  step="0.05"
                  min="0"
                  max="1"
                  value={draft.strategy_weight ?? 0.6}
                  onChange={(e) =>
                    updateField("strategy_weight", Number(e.target.value))
                  }
                  className="field-input"
                  style={{ width: 70 }}
                />
              </div>

              {weightWarning && (
                <div
                  style={{
                    color: "var(--accent-red)",
                    fontSize: "0.78rem",
                    background: "rgba(239,68,68,0.08)",
                    padding: "4px 8px",
                    borderRadius: 6,
                  }}
                >
                  Weights sum to {weightSum.toFixed(2)} (should be 1.0)
                </div>
              )}

              <div className="field-row">
                <span className="field-label">Threshold</span>
                <input
                  type="number"
                  step="1"
                  min="0"
                  max="100"
                  value={draft.threshold ?? 65}
                  onChange={(e) =>
                    updateField("threshold", Number(e.target.value))
                  }
                  className="field-input"
                  style={{ width: 70 }}
                />
              </div>

              <div className="field-row">
                <span className="field-label">Strategy-only threshold</span>
                <input
                  type="number"
                  step="1"
                  min="0"
                  max="100"
                  value={draft.strategy_only_threshold ?? 0}
                  onChange={(e) =>
                    updateField("strategy_only_threshold", Number(e.target.value))
                  }
                  className="field-input"
                  style={{ width: 70 }}
                />
              </div>

              <div className="field-row">
                <span className="field-label">Require pattern</span>
                <input
                  type="checkbox"
                  checked={draft.require_pattern ?? true}
                  onChange={(e) =>
                    updateField("require_pattern", e.target.checked)
                  }
                />
              </div>

              {/* Visual explanation */}
              <div
                style={{
                  background: "var(--bg-card)",
                  border: "1px solid var(--border-color)",
                  borderRadius: 6,
                  padding: "8px 10px",
                  fontSize: "0.78rem",
                  color: "var(--text-muted)",
                  lineHeight: 1.5,
                }}
              >
                <strong>Formula:</strong> combined ={" "}
                {(draft.pattern_weight ?? 0.4).toFixed(2)} × pattern +{" "}
                {(draft.strategy_weight ?? 0.6).toFixed(2)} × strategy
                <br />
                Trade if combined &ge; <strong>{draft.threshold ?? 65}</strong>
                <br />
                Strategy-only gate:{" "}
                <strong>{draft.strategy_only_threshold ?? 0}</strong>
                {(draft.strategy_only_threshold ?? 0) > 0
                  ? " (used when pattern score is 0)"
                  : " (disabled, uses base threshold)"}
                <br />
                {draft.require_pattern
                  ? "Patterns MUST fire before strategies are consulted."
                  : "Strategies can trigger trades even without a pattern."}
              </div>

              {/* ── Candlestick Detector Settings ─────── */}
              <div
                style={{
                  fontSize: "0.8rem",
                  fontWeight: 600,
                  color: "var(--text-secondary)",
                  borderBottom: "1px solid var(--border-color)",
                  paddingBottom: 4,
                  marginTop: 4,
                  cursor: "pointer",
                  userSelect: "none",
                  display: "flex",
                  justifyContent: "space-between",
                }}
                onClick={() => setDetectorExpanded((p) => !p)}
              >
                <span>Candlestick Detector</span>
                <span>{detectorExpanded ? "▲" : "▼"}</span>
              </div>

              {detectorExpanded && draft.detector && (
                <>
                  <div className="field-row">
                    <span className="field-label">Doji body %</span>
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      max="1"
                      value={draft.detector.body_doji_pct ?? 0.1}
                      onChange={(e) =>
                        updateDetectorField(
                          "body_doji_pct",
                          Number(e.target.value)
                        )
                      }
                      className="field-input"
                      style={{ width: 70 }}
                    />
                  </div>

                  <div className="field-row">
                    <span className="field-label">Hammer wick ratio</span>
                    <input
                      type="number"
                      step="0.1"
                      min="1"
                      max="5"
                      value={draft.detector.wick_ratio_hammer ?? 2.0}
                      onChange={(e) =>
                        updateDetectorField(
                          "wick_ratio_hammer",
                          Number(e.target.value)
                        )
                      }
                      className="field-input"
                      style={{ width: 70 }}
                    />
                  </div>

                  <div className="field-row">
                    <span className="field-label">Engulfing min body %</span>
                    <input
                      type="number"
                      step="0.05"
                      min="0"
                      max="1"
                      value={draft.detector.engulfing_min_body_pct ?? 0.3}
                      onChange={(e) =>
                        updateDetectorField(
                          "engulfing_min_body_pct",
                          Number(e.target.value)
                        )
                      }
                      className="field-input"
                      style={{ width: 70 }}
                    />
                  </div>

                  <div className="field-row">
                    <span className="field-label">Volume confirm ratio</span>
                    <input
                      type="number"
                      step="0.1"
                      min="1"
                      max="5"
                      value={draft.detector.volume_confirm_ratio ?? 1.3}
                      onChange={(e) =>
                        updateDetectorField(
                          "volume_confirm_ratio",
                          Number(e.target.value)
                        )
                      }
                      className="field-input"
                      style={{ width: 70 }}
                    />
                  </div>

                  <div className="field-row">
                    <span className="field-label">VWAP proximity %</span>
                    <input
                      type="number"
                      step="0.05"
                      min="0"
                      max="3"
                      value={draft.detector.vwap_proximity_pct ?? 0.3}
                      onChange={(e) =>
                        updateDetectorField(
                          "vwap_proximity_pct",
                          Number(e.target.value)
                        )
                      }
                      className="field-input"
                      style={{ width: 70 }}
                    />
                  </div>
                </>
              )}

              {/* ── Buttons ─────────────────────────────── */}
              <div
                style={{
                  display: "flex",
                  justifyContent: "flex-end",
                  gap: 8,
                  marginTop: 6,
                }}
              >
                <button
                  className="btn btn-secondary"
                  onClick={resetDraft}
                >
                  Reset
                </button>
                <button className="btn btn-primary" onClick={saveConfig}>
                  Save
                </button>
                {saved && (
                  <span
                    style={{
                      color: "var(--accent-green)",
                      fontSize: "0.8rem",
                      alignSelf: "center",
                    }}
                  >
                    Saved
                  </span>
                )}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}

export default MultiLayerSettings;
