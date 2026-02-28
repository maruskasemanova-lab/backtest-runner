import { SHOW_RUN_CONFIG_ADVANCED_EXECUTION_CONTROLS } from "./runConfigHelpers";
import {
  AdverseFlowExitPanel,
  ContextAwareRiskPanel,
  ExecutionSizingPanel,
  MicroConfirmationPanel,
  PartialTakeProfitPanel,
  StopLossAndBreakEvenPanel,
} from "./RiskManagementPanels";
import type {
  RiskManagementChangeHandler,
  RiskManagementConfig,
} from "./riskManagementFieldControls";

interface RiskManagementSettingsProps {
  config: RiskManagementConfig;
  handleChange: RiskManagementChangeHandler;
}

export function RiskManagementSettings({
  config,
  handleChange,
}: RiskManagementSettingsProps) {
  if (!SHOW_RUN_CONFIG_ADVANCED_EXECUTION_CONTROLS) {
    return null;
  }

  return (
    <>
      <ExecutionSizingPanel config={config} handleChange={handleChange} />
      <ContextAwareRiskPanel config={config} handleChange={handleChange} />
      <StopLossAndBreakEvenPanel config={config} handleChange={handleChange} />
      <PartialTakeProfitPanel config={config} handleChange={handleChange} />
      <MicroConfirmationPanel config={config} handleChange={handleChange} />
      <AdverseFlowExitPanel config={config} handleChange={handleChange} />
    </>
  );
}
