import type {
  AOSMomentumDraft,
  AOSMomentumSleeveDraft,
} from "./aosOptimizationsMomentum";
import { safeArray } from "./aosOptimizationsMomentum";
import {
  MomentumDirtyNotice,
  MomentumDraftFields,
  MomentumEditorActionBar,
  MomentumEditorHeader,
  MomentumEditorStatus,
  MomentumSleevesSection,
} from "./AOSOptimizationsMomentumEditorSections";

type Props = {
  momentumDraft: AOSMomentumDraft;
  momentumDirty: boolean;
  momentumSaving: boolean;
  momentumError: string | null;
  momentumNotice: string | null;
  rawConfigSaving: boolean;
  onLoadFromJson: () => void;
  onApplyToJson: () => void;
  onSaveToServer: () => void;
  onMomentumChange: (field: keyof AOSMomentumDraft, value: unknown) => void;
  onSleeveChange: (
    index: number,
    field: keyof AOSMomentumSleeveDraft,
    value: unknown,
  ) => void;
  onAddSleeve: () => void;
  onRemoveSleeve: (index: number) => void;
};

export default function AOSOptimizationsMomentumEditor({
  momentumDraft,
  momentumDirty,
  momentumSaving,
  momentumError,
  momentumNotice,
  rawConfigSaving,
  onLoadFromJson,
  onApplyToJson,
  onSaveToServer,
  onMomentumChange,
  onSleeveChange,
  onAddSleeve,
  onRemoveSleeve,
}: Props) {
  const sleeves = safeArray<AOSMomentumSleeveDraft>(momentumDraft?.sleeves);

  return (
    <div className="aos-momentum-editor">
      <MomentumEditorHeader />
      <MomentumEditorActionBar
        momentumSaving={momentumSaving}
        rawConfigSaving={rawConfigSaving}
        onLoadFromJson={onLoadFromJson}
        onApplyToJson={onApplyToJson}
        onSaveToServer={onSaveToServer}
      />
      <MomentumEditorStatus
        momentumNotice={momentumNotice}
        momentumError={momentumError}
      />
      <MomentumDraftFields
        draft={momentumDraft}
        onFieldChange={(field, value) =>
          onMomentumChange(field as keyof AOSMomentumDraft, value)
        }
      />
      <MomentumSleevesSection
        sleeves={sleeves}
        onAddSleeve={onAddSleeve}
        onRemoveSleeve={onRemoveSleeve}
        onSleeveFieldChange={(index, field, value) =>
          onSleeveChange(index, field as keyof AOSMomentumSleeveDraft, value)
        }
      />
      {momentumDirty ? <MomentumDirtyNotice /> : null}
    </div>
  );
}
