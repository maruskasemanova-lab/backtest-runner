import type { MomentumConfigSlice, MomentumSleeveDraft } from "../momentumUtils";
import { MomentumSleevesEditor } from "./MomentumSleevesEditor";
import {
  MOMENTUM_OVERRIDE_MICRO_REGIME_TEXT_FIELDS,
  MOMENTUM_OVERRIDE_NUMERIC_FIELDS,
  MOMENTUM_OVERRIDE_PRIMARY_TEXT_FIELD,
  MOMENTUM_OVERRIDE_TOGGLE_FIELDS,
  type NumericFieldDef,
} from "./momentumDiversificationFieldDefs";

interface MomentumDiversificationOverrideFieldsProps {
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

const parseNumericInputValue = (
  rawValue: string,
  definition: NumericFieldDef<MomentumConfigSlice>,
) => {
  const numeric = Number(rawValue);
  if (definition.parseValue) {
    return definition.parseValue(numeric);
  }
  return numeric;
};

export function MomentumDiversificationOverrideFields({
  config,
  momentumSleeves,
  onChange,
  onMomentumSleeveChange,
  onAddMomentumSleeve,
  onRemoveMomentumSleeve,
}: MomentumDiversificationOverrideFieldsProps) {
  return (
    <>
      <div className="tw-grid-fit-220 tw-mb-sm">
        {MOMENTUM_OVERRIDE_TOGGLE_FIELDS.map((field) => (
          <label className="field-row" key={String(field.field)}>
            <span>{field.label}</span>
            <input
              type="checkbox"
              checked={!!config[field.field]}
              onChange={(e) => onChange(String(field.field), e.target.checked)}
            />
          </label>
        ))}
      </div>

      <div className="tw-grid-fit-190">
        {MOMENTUM_OVERRIDE_NUMERIC_FIELDS.map((field) => (
          <div className="form-group" key={String(field.field)}>
            <label htmlFor={field.id}>{field.label}</label>
            <input
              id={field.id}
              type="number"
              min={field.min}
              max={field.max}
              step={field.step}
              value={config[field.field] as number}
              onChange={(e) =>
                onChange(String(field.field), parseNumericInputValue(e.target.value, field))
              }
            />
          </div>
        ))}
      </div>

      <div className="form-group">
        <label htmlFor={MOMENTUM_OVERRIDE_PRIMARY_TEXT_FIELD.id}>
          {MOMENTUM_OVERRIDE_PRIMARY_TEXT_FIELD.label}
        </label>
        <input
          id={MOMENTUM_OVERRIDE_PRIMARY_TEXT_FIELD.id}
          type="text"
          value={String(config[MOMENTUM_OVERRIDE_PRIMARY_TEXT_FIELD.field] ?? "")}
          onChange={(e) =>
            onChange(
              String(MOMENTUM_OVERRIDE_PRIMARY_TEXT_FIELD.field),
              e.target.value,
            )
          }
          placeholder={MOMENTUM_OVERRIDE_PRIMARY_TEXT_FIELD.placeholder}
        />
      </div>

      <div className="tw-grid-fit-220">
        {MOMENTUM_OVERRIDE_MICRO_REGIME_TEXT_FIELDS.map((field) => (
          <div className="form-group" key={String(field.field)}>
            <label htmlFor={field.id}>{field.label}</label>
            <input
              id={field.id}
              type="text"
              value={String(config[field.field] ?? "")}
              onChange={(e) => onChange(String(field.field), e.target.value)}
              placeholder={field.placeholder}
            />
          </div>
        ))}
      </div>

      <MomentumSleevesEditor
        momentumSleeves={momentumSleeves}
        onMomentumSleeveChange={onMomentumSleeveChange}
        onAddMomentumSleeve={onAddMomentumSleeve}
        onRemoveMomentumSleeve={onRemoveMomentumSleeve}
      />
    </>
  );
}
