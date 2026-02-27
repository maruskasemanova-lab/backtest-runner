type Props = {
  fullscreen: boolean;
  title: string;
  t: (text: string) => string;
  uiLanguage: string;
  setUiLanguage: (value: string) => void;
  detailTab: string;
  setDetailTab: (value: string) => void;
  onToggleFullscreen: () => void;
  activeHelpTooltip: { text?: string; pinned?: boolean } | null;
  onClosePinnedTooltip: () => void;
};

export default function DecisionPanelDetailChrome({
  fullscreen,
  title,
  t,
  uiLanguage,
  setUiLanguage,
  detailTab,
  setDetailTab,
  onToggleFullscreen,
  activeHelpTooltip,
  onClosePinnedTooltip,
}: Props) {
  return (
    <>
      <div className="decision-detail-header">
        <h4>{title}</h4>
        <div className="decision-detail-header-actions">
          <div className="decision-language-toggle" title={t("Language")}>
            <button
              type="button"
              className={`btn btn-secondary decision-detail-expand-btn ${uiLanguage === "sk" ? "active" : ""}`}
              onClick={() => setUiLanguage("sk")}
            >
              SK
            </button>
            <button
              type="button"
              className={`btn btn-secondary decision-detail-expand-btn ${uiLanguage === "en" ? "active" : ""}`}
              onClick={() => setUiLanguage("en")}
            >
              EN
            </button>
          </div>
          <button
            type="button"
            className="btn btn-secondary decision-detail-expand-btn"
            onClick={onToggleFullscreen}
            title={fullscreen ? t("Exit Full Screen") : t("Full Screen")}
          >
            {fullscreen ? t("Exit Full Screen") : t("Full Screen")}
          </button>
        </div>
      </div>

      <div className="decision-detail-tabs">
        <button
          className={`decision-detail-tab ${detailTab === "details" ? "active" : ""}`}
          onClick={() => setDetailTab("details")}
        >
          {t("Details")}
        </button>
        <button
          className={`decision-detail-tab ${detailTab === "raw" ? "active" : ""}`}
          onClick={() => setDetailTab("raw")}
        >
          {t("Raw")}
        </button>
        <button
          className={`decision-detail-tab ${detailTab === "decision_log" ? "active" : ""}`}
          onClick={() => setDetailTab("decision_log")}
        >
          {t("Decision Log")}
        </button>
      </div>

      {activeHelpTooltip?.pinned && (
        <div className="decision-help-inline" role="note">
          <div className="decision-help-inline-head">
            <strong>{uiLanguage === "en" ? "Tooltip detail" : "Detail tooltipu"}</strong>
            <button
              type="button"
              className="decision-help-inline-close"
              onClick={onClosePinnedTooltip}
              aria-label={uiLanguage === "en" ? "Close tooltip detail" : "Zavrieť detail tooltipu"}
            >
              ×
            </button>
          </div>
          <pre className="decision-help-inline-body">{activeHelpTooltip.text}</pre>
        </div>
      )}
    </>
  );
}
