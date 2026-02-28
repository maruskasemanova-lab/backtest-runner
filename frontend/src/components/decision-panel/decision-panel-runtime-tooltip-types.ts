import type {
  DecisionPanelBreakEvenBufferLike,
  DecisionPanelBreakEvenComputedLike,
  DecisionPanelBreakEvenPayloadLike,
  DecisionPanelDecisionLogLike,
  DecisionPanelDetailsLike,
  DecisionPanelEntryQualityDiagnosticsLike,
  DecisionPanelIntradayLevelsLike,
  DecisionPanelL2DiagnosticsLike,
  DecisionPanelLevelContextLike,
  DecisionPanelMetadataLike,
  DecisionPanelMarkerLike,
  DecisionPanelTooltipRuntimeMap,
} from "./decision-panel-types";

export type BuildDecisionPanelRuntimeTooltipsParams = {
  uiLanguage: string;
  selectedMarker: DecisionPanelMarkerLike | null;
  details: DecisionPanelDetailsLike;
  metadata: DecisionPanelMetadataLike;
  l2Diagnostics: DecisionPanelL2DiagnosticsLike;
  intradayLevels: DecisionPanelIntradayLevelsLike;
  levelContext: DecisionPanelLevelContextLike;
  entryQualityDiagnostics: DecisionPanelEntryQualityDiagnosticsLike;
  decisionLog: DecisionPanelDecisionLogLike;
  renderCostLabel: (key: string) => string;
  contextRiskFieldSource: (fieldName: string) => string;
  renderReasonValue: (value: unknown) => string;
  isRuntimeMissing: (value: unknown) => boolean;
  buildContextRiskMissingLines: (fieldKey: string) => string[];
  breakEvenPayload: DecisionPanelBreakEvenPayloadLike | null;
  breakEvenFieldSource: (fieldName: string) => string;
  renderBreakEvenTrigger: (rawValue: unknown) => string;
  renderBreakEvenProof: (payload: unknown) => string;
  buildBreakEvenMissingLines: (fieldKey: string) => string[];
  breakEvenStopDisplayValue: number | null;
  breakEvenStopSource: string;
  breakEvenComputed: DecisionPanelBreakEvenComputedLike | null;
  breakEvenBuffer: DecisionPanelBreakEvenBufferLike | null;
  breakEvenAntiSpikeSummary: string;
  formatPctValue: (value: unknown, digits?: number) => string;
  buildVwapFlowValueLines: (value: unknown, sourcePath: string) => string[];
};

export type DecisionPanelTooltipLocaleText = {
  value: string;
  source: string;
  l2Title: string;
  chosen: string;
  unavailable: string;
};

export type RuntimeTooltipSetter = (
  label: string,
  value: unknown,
  source: string,
  flow?: string[] | string,
) => void;

export type BuildDecisionPanelRuntimeTooltipsResult = {
  tooltipLocaleText: DecisionPanelTooltipLocaleText;
  baseTooltipFor: (label: string) => string;
  runtimeTooltipByLabel: DecisionPanelTooltipRuntimeMap;
};
