import { DECISION_TOOLTIPS } from "./decision-panel-copy";
import { resolveTooltipBaseLabel } from "./decision-panel-utils";
import {
  applyDecisionLogRuntimeTooltips,
  applyEntryQualityRuntimeTooltips,
  applyIntradayLevelsRuntimeTooltips,
  applyL2RuntimeTooltips,
  applyLevelContextRuntimeTooltips,
  applyPrimaryRuntimeTooltips,
  buildL2SourceFlowNotes,
  buildTooltipLocaleText,
} from "./decision-panel-runtime-tooltip-sections";
import type {
  BuildDecisionPanelRuntimeTooltipsParams,
  BuildDecisionPanelRuntimeTooltipsResult,
  RuntimeTooltipSetter,
} from "./decision-panel-runtime-tooltip-types";

export const buildDecisionPanelRuntimeTooltips = (
  params: BuildDecisionPanelRuntimeTooltipsParams,
): BuildDecisionPanelRuntimeTooltipsResult => {
  const { uiLanguage, l2Diagnostics } = params;
  const tooltipLocaleText = buildTooltipLocaleText(uiLanguage);
  const baseTooltipFor = (label: string) => {
    const baseLabel = resolveTooltipBaseLabel(label);
    return (
      DECISION_TOOLTIPS[uiLanguage]?.[baseLabel] ??
      DECISION_TOOLTIPS.sk?.[baseLabel] ??
      DECISION_TOOLTIPS.sk?._default ??
      ""
    );
  };

  const runtimeTooltipByLabel: Record<string, any> = {};
  const setRuntimeTooltip: RuntimeTooltipSetter = (label, value, source, flow = []) => {
    runtimeTooltipByLabel[label] = {
      value,
      source,
      flow: Array.isArray(flow) ? flow.filter(Boolean) : [flow].filter(Boolean),
    };
  };

  const l2SourceFlowNotes = buildL2SourceFlowNotes(
    uiLanguage,
    tooltipLocaleText,
    l2Diagnostics,
  );

  applyPrimaryRuntimeTooltips(params, setRuntimeTooltip);
  applyL2RuntimeTooltips(params, l2SourceFlowNotes, setRuntimeTooltip);
  applyIntradayLevelsRuntimeTooltips(params, setRuntimeTooltip);
  applyLevelContextRuntimeTooltips(params, setRuntimeTooltip);
  applyEntryQualityRuntimeTooltips(params, setRuntimeTooltip);
  applyDecisionLogRuntimeTooltips(params, l2SourceFlowNotes, setRuntimeTooltip);

  return {
    tooltipLocaleText,
    baseTooltipFor,
    runtimeTooltipByLabel,
  };
};
