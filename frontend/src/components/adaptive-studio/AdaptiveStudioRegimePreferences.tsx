import AdaptiveStudioPriorityEditor from "./AdaptiveStudioPriorityEditor";
import type { AdaptiveStudioPriorityScope } from "./profileTypes";

type Props = {
  macroRegimes: string[];
  microRegimes: string[];
  macroPreferences: Record<string, string[]>;
  microPreferences: Record<string, string[]>;
  strategyUniverse: string[];
  strategyLabel: (name: string) => string;
  onMovePriorityItem: (
    scope: AdaptiveStudioPriorityScope,
    key: string,
    index: number,
    direction: number,
  ) => void;
  onToggleStrategyInList: (
    scope: AdaptiveStudioPriorityScope,
    key: string,
    strategy: string,
  ) => void;
};

export default function AdaptiveStudioRegimePreferences({
  macroRegimes,
  microRegimes,
  macroPreferences,
  microPreferences,
  strategyUniverse,
  strategyLabel,
  onMovePriorityItem,
  onToggleStrategyInList,
}: Props) {
  return (
    <div className="adaptive-grid-2col">
      <div className="adaptive-section">
        <details>
          <summary>Macro Regime Preferences</summary>
          <div>
            <div className="adaptive-editor-grid">
              {macroRegimes.map((regime) => (
                <AdaptiveStudioPriorityEditor
                  key={`macro-${regime}`}
                  title={regime}
                  regimeKey={regime}
                  selectedStrategies={macroPreferences?.[regime] || []}
                  strategyUniverse={strategyUniverse}
                  strategyLabel={strategyLabel}
                  onMoveItem={(index, direction) =>
                    onMovePriorityItem("regime_preferences", regime, index, direction)
                  }
                  onToggleStrategy={(strategy) =>
                    onToggleStrategyInList("regime_preferences", regime, strategy)
                  }
                />
              ))}
            </div>
          </div>
        </details>
      </div>
      <div className="adaptive-section">
        <details>
          <summary>Micro Regime Preferences</summary>
          <div>
            <div className="adaptive-editor-grid">
              {microRegimes.map((regime) => (
                <AdaptiveStudioPriorityEditor
                  key={`micro-${regime}`}
                  title={regime}
                  regimeKey={regime}
                  selectedStrategies={microPreferences?.[regime] || []}
                  strategyUniverse={strategyUniverse}
                  strategyLabel={strategyLabel}
                  onMoveItem={(index, direction) =>
                    onMovePriorityItem("micro_regime_preferences", regime, index, direction)
                  }
                  onToggleStrategy={(strategy) =>
                    onToggleStrategyInList("micro_regime_preferences", regime, strategy)
                  }
                />
              ))}
            </div>
          </div>
        </details>
      </div>
    </div>
  );
}
