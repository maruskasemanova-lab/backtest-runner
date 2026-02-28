import { AdaptiveTunerConfigPanel } from "./adaptive-tuner/AdaptiveTunerConfigPanel";
import { AdaptiveTunerMonitorPanel } from "./adaptive-tuner/AdaptiveTunerMonitorPanel";
import { AdaptiveTunerResultsPanel } from "./adaptive-tuner/AdaptiveTunerResultsPanel";
import { useAdaptiveTunerController } from "./adaptive-tuner/useAdaptiveTunerController";

interface AdaptiveTunerProps {
  selectedTicker?: string;
  onTickerChange?: (ticker: string) => void;
  strategyApiUrl?: string;
}

function AdaptiveTuner({ selectedTicker, onTickerChange, strategyApiUrl }: AdaptiveTunerProps) {
  const controller = useAdaptiveTunerController({
    selectedTicker,
    onTickerChange,
    strategyApiUrl,
  });

  const activeProfileId = String(controller.tickerOptions?.active_profile_id || "").trim();
  const trialRows = controller.sortedTrials.slice(0, 80);

  return (
    <main className="tuner-page">
      <AdaptiveTunerConfigPanel controller={controller} />

      <div className="tuner-main-content">
        <AdaptiveTunerMonitorPanel controller={controller} />
        <AdaptiveTunerResultsPanel
          controller={controller}
          activeProfileId={activeProfileId}
          trialRows={trialRows}
        />
      </div>
    </main>
  );
}

export default AdaptiveTuner;
