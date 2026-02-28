import {
  L2_DIAGNOSTIC_KEYS,
  isObjectRecord,
  resolveBreakEven,
  resolveContextRisk,
  resolveRiskControls,
} from "./decision-panel-diagnostic-resolvers";
import {
  extractDecisionLogPayload,
  extractEntryQualityDiagnostics,
  extractIntradayLevels,
  extractL2Diagnostics,
  extractLevelContext,
} from "./decision-panel-diagnostic-extractors";

export {
  L2_DIAGNOSTIC_KEYS,
  extractDecisionLogPayload,
  extractEntryQualityDiagnostics,
  extractIntradayLevels,
  extractL2Diagnostics,
  extractLevelContext,
  isObjectRecord,
  resolveBreakEven,
  resolveContextRisk,
  resolveRiskControls,
};

export type DecisionPanelRiskControlsResolution = ReturnType<typeof resolveRiskControls>;
export type DecisionPanelContextRiskResolution = ReturnType<typeof resolveContextRisk>;
export type DecisionPanelBreakEvenResolution = ReturnType<typeof resolveBreakEven>;
export type DecisionPanelL2DiagnosticsResult = ReturnType<typeof extractL2Diagnostics>;
export type DecisionPanelIntradayLevelsResult = ReturnType<typeof extractIntradayLevels>;
export type DecisionPanelLevelContextResult = ReturnType<typeof extractLevelContext>;
export type DecisionPanelEntryQualityDiagnosticsResult = ReturnType<
  typeof extractEntryQualityDiagnostics
>;
export type DecisionPanelDecisionLogResult = ReturnType<typeof extractDecisionLogPayload>;
