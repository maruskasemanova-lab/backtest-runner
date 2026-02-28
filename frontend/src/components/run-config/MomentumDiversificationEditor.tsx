import type { MomentumConfigSlice, MomentumSleeveDraft } from "./momentumUtils";
import { MomentumDiversificationOverrideFields } from "./momentum-diversification/MomentumDiversificationOverrideFields";

interface MomentumDiversificationEditorProps {
  config: MomentumConfigSlice;
  momentumSleeves: MomentumSleeveDraft[];
  onChange: (field: string, value: unknown) => void;
  onMomentumSleeveChange: (
    index: number,
    field: keyof MomentumSleeveDraft,
    value: unknown,
  ) => void;
  onAddMomentumSleeve: () => void;
  onRemoveMomentumSleeve: (index: number) => void;
}

function MomentumDiversificationEditor({
  config,
  momentumSleeves,
  onChange,
  onMomentumSleeveChange,
  onAddMomentumSleeve,
  onRemoveMomentumSleeve,
}: MomentumDiversificationEditorProps) {
  return (
    <div className="tw-panel">
      <div className="tw-panel-title">Momentum Diversification Override</div>
      <div className="tw-panel-hint">
        Voliteľný run-level override pre adaptive momentum routing (L2/CVD +
        price-action prahy, route a fail-fast). Keď je vypnutý, použije sa
        aktívny Adaptive Profile/AOS config.
      </div>

      <div className="form-group">
        <label
          className="field-row"
          htmlFor="momentum_diversification_override_enabled"
        >
          <span>Enable per-run momentum diversification override</span>
          <input
            id="momentum_diversification_override_enabled"
            type="checkbox"
            checked={!!config.momentum_diversification_override_enabled}
            onChange={(e) =>
              onChange("momentum_diversification_override_enabled", e.target.checked)
            }
          />
        </label>
      </div>

      {config.momentum_diversification_override_enabled ? (
        <MomentumDiversificationOverrideFields
          config={config}
          momentumSleeves={momentumSleeves}
          onChange={onChange}
          onMomentumSleeveChange={onMomentumSleeveChange}
          onAddMomentumSleeve={onAddMomentumSleeve}
          onRemoveMomentumSleeve={onRemoveMomentumSleeve}
        />
      ) : (
        <div className="text-[0.78rem] text-app-text-muted">
          Override je vypnutý, použije sa profil z Adaptive Tuner/AOS.
        </div>
      )}
    </div>
  );
}

export default MomentumDiversificationEditor;
