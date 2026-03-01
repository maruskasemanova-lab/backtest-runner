import { UnifiedConfigDialog } from "../unified-config/UnifiedConfigDialog";
import { useStrategyAnalyzerConfigState } from "./useStrategyAnalyzerConfigState";

interface StrategyAnalyzerUnifiedConfigWrapperProps {
  ticker: string;
  strategyApiUrl: string;
  onClose: () => void;
}

/**
 * Thin wrapper that creates a standalone useRunConfigState instance
 * and renders the UnifiedConfigDialog. Rendered conditionally so the
 * heavyweight hook is only active when the dialog is open.
 */
export default function StrategyAnalyzerUnifiedConfigWrapper({
  ticker,
  strategyApiUrl,
  onClose,
}: StrategyAnalyzerUnifiedConfigWrapperProps) {
  const state = useStrategyAnalyzerConfigState(ticker);

  return (
    <UnifiedConfigDialog
      isOpen
      onClose={onClose}
      config={state.config}
      handleChange={state.handleChange}
      momentumSleeves={state.momentumSleeves}
      onMomentumSleeveChange={state.handleMomentumSleeveChange}
      onAddMomentumSleeve={state.handleAddMomentumSleeve}
      onRemoveMomentumSleeve={state.handleRemoveMomentumSleeve}
      strategyApiUrl={strategyApiUrl}
      selectedTicker={ticker}
      activeProfile={state.activeProfile}
      activeProfileId={state.activeProfileId}
    />
  );
}
