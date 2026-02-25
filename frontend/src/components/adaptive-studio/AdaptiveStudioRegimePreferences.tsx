import type { ReactNode } from "react";

type Props = {
  macroRegimes: string[];
  microRegimes: string[];
  renderPriorityEditor: (scope: string, key: string, title: string) => ReactNode;
};

export default function AdaptiveStudioRegimePreferences({
  macroRegimes,
  microRegimes,
  renderPriorityEditor,
}: Props) {
  return (
    <div className="adaptive-grid-2col">
      <div className="adaptive-section">
        <details>
          <summary>Macro Regime Preferences</summary>
          <div>
            <div className="adaptive-editor-grid">
              {macroRegimes.map((regime) =>
                renderPriorityEditor("regime_preferences", regime, regime),
              )}
            </div>
          </div>
        </details>
      </div>
      <div className="adaptive-section">
        <details>
          <summary>Micro Regime Preferences</summary>
          <div>
            <div className="adaptive-editor-grid">
              {microRegimes.map((regime) =>
                renderPriorityEditor("micro_regime_preferences", regime, regime),
              )}
            </div>
          </div>
        </details>
      </div>
    </div>
  );
}
