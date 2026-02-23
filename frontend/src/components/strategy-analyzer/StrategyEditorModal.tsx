import { useEffect, useMemo, useState } from "react";
import StrategySettings from "../StrategySettings";
import { FullscreenConfigDialog } from "../FullscreenConfigDialog";
import { useRunConfigState } from "../run-config/useRunConfigState";
import { ACTIVE_UNIFIED_PROFILE_SENTINEL } from "../run-config/runConfigHelpers";

interface StrategyAnalyzerFullProfileDialogProps {
  ticker: string;
  isOpen: boolean;
  onClose: () => void;
}

function StrategyAnalyzerFullProfileDialog({
  ticker,
  isOpen,
  onClose,
}: StrategyAnalyzerFullProfileDialogProps) {
  const state = useRunConfigState({
    onStart: async () => null,
    isRunning: false,
    onTickerChange: () => {},
    effectiveExecutionConfig: null,
    activeRuns: [],
    activeRunKey: "",
    onAttachRun: () => {},
    onKillRun: undefined,
    sidebarSubsection: "profiles",
    authToken: "",
    activeRunState: null,
  });
  const currentRunConfigTicker = String(state.config?.ticker || "").trim().toUpperCase();

  useEffect(() => {
    if (!isOpen) return;
    const upperTicker = String(ticker || "").trim().toUpperCase();
    if (!upperTicker) return;
    if (currentRunConfigTicker === upperTicker) return;
    state.handleTickerChange(upperTicker);
  }, [currentRunConfigTicker, isOpen, ticker, state.handleTickerChange]);

  const activeProfileId = useMemo(() => {
    const selectedId = String(state.selectedUnifiedProfileId || "").trim();
    if (!selectedId || selectedId === ACTIVE_UNIFIED_PROFILE_SENTINEL) {
      return String(state.activeUnifiedProfileId || "").trim();
    }
    return selectedId;
  }, [state.activeUnifiedProfileId, state.selectedUnifiedProfileId]);

  const activeProfile = useMemo(() => {
    if (!activeProfileId) return null;
    const profiles = Array.isArray(state.unifiedProfiles) ? state.unifiedProfiles : [];
    return (
      profiles.find(
        (profile: any) => String(profile?.profile_id || "").trim() === activeProfileId
      ) || null
    );
  }, [activeProfileId, state.unifiedProfiles]);

  return (
    <FullscreenConfigDialog
      isOpen={isOpen}
      onClose={onClose}
      config={state.config}
      handleChange={state.handleChange}
      momentumSleeves={state.momentumSleeves}
      onMomentumSleeveChange={state.handleMomentumSleeveChange}
      onAddMomentumSleeve={state.handleAddMomentumSleeve}
      onRemoveMomentumSleeve={state.handleRemoveMomentumSleeve}
      activeProfile={activeProfile}
      zIndex={2000}
    />
  );
}

interface StrategyEditorModalProps {
  ticker: string;
  strategyApiUrl: string;
  onClose: () => void;
}

export default function StrategyEditorModal({
  ticker,
  strategyApiUrl,
  onClose,
}: StrategyEditorModalProps) {
  const [showFullProfileConfig, setShowFullProfileConfig] = useState(false);

  // Prevent body scroll while modal is open
  useEffect(() => {
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, []);

  // Escape key closes modal
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  return (
    <div
      className="strategy-editor-modal-overlay"
      onClick={onClose}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 1000,
        background: "rgba(0, 0, 0, 0.5)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "2rem",
      }}
    >
      <div
        className="strategy-editor-modal-dialog card"
        onClick={(e) => e.stopPropagation()}
        style={{
          width: "min(960px, 90vw)",
          maxHeight: "85vh",
          display: "flex",
          flexDirection: "column",
          borderRadius: "var(--radius-lg, 12px)",
          boxShadow: "var(--shadow-lg, 0 8px 32px rgba(0,0,0,0.2))",
          overflow: "hidden",
        }}
      >
        {/* Header */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "1rem 1.25rem",
            borderBottom: "1px solid var(--border-color)",
          }}
        >
          <h2
            style={{
              margin: 0,
              fontSize: "1.1rem",
              fontWeight: 700,
              color: "var(--text-primary)",
            }}
          >
            Strategy Editor — {ticker}
          </h2>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => setShowFullProfileConfig(true)}
              style={{ padding: "4px 10px", fontSize: "0.78rem" }}
              title="Open the same full profile configuration view used in Run Config"
            >
              Full Profile
            </button>
            <button
              onClick={onClose}
              style={{
                background: "none",
                border: "none",
                fontSize: "1.25rem",
                cursor: "pointer",
                color: "var(--text-muted)",
                padding: "4px 8px",
                lineHeight: 1,
              }}
              title="Close"
            >
              &times;
            </button>
          </div>
        </div>

        {/* Body */}
        <div
          style={{
            flex: 1,
            overflowY: "auto",
            padding: "1rem 1.25rem",
          }}
        >
          <StrategySettings
            apiUrl={strategyApiUrl}
            selectedTicker={ticker}
            initialExpandAll
          />
        </div>

        {/* Footer */}
        <div
          style={{
            display: "flex",
            justifyContent: "flex-end",
            gap: "0.5rem",
            padding: "0.75rem 1.25rem",
            borderTop: "1px solid var(--border-color)",
          }}
        >
          <button
            className="btn"
            onClick={onClose}
            style={{ padding: "6px 20px", fontSize: "0.85rem" }}
          >
            Close
          </button>
        </div>
      </div>

      {showFullProfileConfig ? (
        <StrategyAnalyzerFullProfileDialog
          ticker={ticker}
          isOpen={showFullProfileConfig}
          onClose={() => setShowFullProfileConfig(false)}
        />
      ) : null}
    </div>
  );
}
