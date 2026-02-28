import { L2_DIAGNOSTIC_KEYS } from "./decision-panel-diagnostics";
import type {
  BuildDecisionPanelRuntimeTooltipsParams,
  DecisionPanelTooltipLocaleText,
} from "./decision-panel-runtime-tooltip-types";

export const buildTooltipLocaleText = (
  uiLanguage: string,
): DecisionPanelTooltipLocaleText =>
  uiLanguage === "en"
    ? {
        value: "Current value",
        source: "Resolved source",
        l2Title: "L2 source selection",
        chosen: "Chosen source",
        unavailable: "Value not present on selected source",
      }
    : {
        value: "Aktuálna hodnota",
        source: "Použitý zdroj",
        l2Title: "Výber L2 zdroja",
        chosen: "Zvolený zdroj",
        unavailable: "Hodnota nie je na zvolenom zdroji",
      };

export const buildL2SourceFlowNotes = (
  uiLanguage: string,
  tooltipLocaleText: DecisionPanelTooltipLocaleText,
  l2Diagnostics: BuildDecisionPanelRuntimeTooltipsParams["l2Diagnostics"],
): string[] => {
  const l2CandidateFlowLines = (l2Diagnostics.candidateDiagnostics || []).map((candidate) => {
    const metrics =
      candidate.availableMetrics?.length > 0
        ? candidate.availableMetrics.join(", ")
        : uiLanguage === "en"
          ? "no metrics"
          : "žiadne metriky";
    const selectedSuffix =
      candidate.sourcePath === l2Diagnostics.sourcePath
        ? ` [${uiLanguage === "en" ? "used" : "použité"}]`
        : "";
    return `- ${candidate.sourcePath}: ${candidate.score}/${L2_DIAGNOSTIC_KEYS.length} (${metrics})${selectedSuffix}`;
  });

  return [
    `${tooltipLocaleText.chosen}: ${l2Diagnostics.sourcePath || "n/a"}`,
    `${tooltipLocaleText.l2Title}:`,
    ...l2CandidateFlowLines,
  ];
};
