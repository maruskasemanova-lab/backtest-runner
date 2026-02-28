import type { MomentumSleeveDraft } from "../momentumUtils";
import {
  MOMENTUM_SLEEVE_ALLOCATION_FIELD,
  MOMENTUM_SLEEVE_NUMERIC_FIELDS,
  MOMENTUM_SLEEVE_TEXT_FIELDS,
  MOMENTUM_SLEEVE_TOGGLE_FIELDS,
  type NumericFieldDef,
} from "./momentumDiversificationFieldDefs";

interface MomentumSleevesEditorProps {
  momentumSleeves: MomentumSleeveDraft[];
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
  definition: NumericFieldDef<MomentumSleeveDraft>,
) => {
  const numeric = Number(rawValue);
  if (definition.parseValue) {
    return definition.parseValue(numeric);
  }
  return numeric;
};

function MomentumSleeveCard({
  sleeve,
  index,
  onMomentumSleeveChange,
  onRemoveMomentumSleeve,
}: {
  sleeve: MomentumSleeveDraft;
  index: number;
  onMomentumSleeveChange: (
    index: number,
    field: keyof MomentumSleeveDraft,
    value: unknown,
  ) => void;
  onRemoveMomentumSleeve: (index: number) => void;
}) {
  return (
    <div className="tw-sleeve-card">
      <div className="tw-sleeve-header">
        <div className="tw-sleeve-title">Sleeve #{index + 1}</div>
        <button
          type="button"
          className="btn btn-secondary tw-btn-compact-xs"
          onClick={() => onRemoveMomentumSleeve(index)}
        >
          Remove
        </button>
      </div>

      <div className="tw-grid-fit-200">
        <div className="form-group">
          <label>{MOMENTUM_SLEEVE_TEXT_FIELDS[0].label}</label>
          <input
            type="text"
            value={String(sleeve?.[MOMENTUM_SLEEVE_TEXT_FIELDS[0].field] ?? "")}
            onChange={(e) =>
              onMomentumSleeveChange(
                index,
                MOMENTUM_SLEEVE_TEXT_FIELDS[0].field,
                e.target.value,
              )
            }
            placeholder={MOMENTUM_SLEEVE_TEXT_FIELDS[0].placeholder}
          />
        </div>

        <div className="form-group">
          <label>{MOMENTUM_SLEEVE_ALLOCATION_FIELD.label}</label>
          <input
            type="number"
            min={MOMENTUM_SLEEVE_ALLOCATION_FIELD.min}
            max={MOMENTUM_SLEEVE_ALLOCATION_FIELD.max}
            step={MOMENTUM_SLEEVE_ALLOCATION_FIELD.step}
            value={
              (sleeve?.[MOMENTUM_SLEEVE_ALLOCATION_FIELD.field] as number | undefined) ??
              MOMENTUM_SLEEVE_ALLOCATION_FIELD.fallback ??
              0
            }
            onChange={(e) =>
              onMomentumSleeveChange(
                index,
                MOMENTUM_SLEEVE_ALLOCATION_FIELD.field,
                parseNumericInputValue(e.target.value, MOMENTUM_SLEEVE_ALLOCATION_FIELD),
              )
            }
          />
        </div>

        {MOMENTUM_SLEEVE_TEXT_FIELDS.slice(1).map((field) => (
          <div className="form-group" key={String(field.field)}>
            <label>{field.label}</label>
            <input
              type="text"
              value={String(sleeve?.[field.field] ?? "")}
              onChange={(e) => onMomentumSleeveChange(index, field.field, e.target.value)}
              placeholder={field.placeholder}
            />
          </div>
        ))}
      </div>

      <div className="tw-grid-fit-220 tw-mb-sm">
        {MOMENTUM_SLEEVE_TOGGLE_FIELDS.map((field) => (
          <label className="field-row" key={String(field.field)}>
            <span>{field.label}</span>
            <input
              type="checkbox"
              checked={!!sleeve?.[field.field]}
              onChange={(e) =>
                onMomentumSleeveChange(index, field.field, e.target.checked)
              }
            />
          </label>
        ))}
      </div>

      <div className="tw-grid-fit-185">
        {MOMENTUM_SLEEVE_NUMERIC_FIELDS.map((field) => (
          <div className="form-group" key={String(field.field)}>
            <label>{field.label}</label>
            <input
              type="number"
              min={field.min}
              max={field.max}
              step={field.step}
              value={(sleeve?.[field.field] as number | undefined) ?? field.fallback ?? 0}
              onChange={(e) =>
                onMomentumSleeveChange(
                  index,
                  field.field,
                  parseNumericInputValue(e.target.value, field),
                )
              }
            />
          </div>
        ))}
      </div>
    </div>
  );
}

export function MomentumSleevesEditor({
  momentumSleeves,
  onMomentumSleeveChange,
  onAddMomentumSleeve,
  onRemoveMomentumSleeve,
}: MomentumSleevesEditorProps) {
  return (
    <div className="tw-subpanel">
      <div className="tw-subpanel-header">
        <div className="tw-subpanel-title">Multi-Sleeve Diversification</div>
        <button
          type="button"
          className="btn btn-secondary tw-btn-compact"
          onClick={onAddMomentumSleeve}
        >
          Add Sleeve
        </button>
      </div>
      <div className="tw-subpanel-copy">
        Vizualny editor pre `sleeves[]`. Ak pridáš aspoň jeden sleeve, backend
        použije multi-sleeve režim.
      </div>

      {momentumSleeves.length === 0 ? (
        <div className="text-[0.75rem] text-app-text-muted">
          Zatial nie je definovany ziadny sleeve.
        </div>
      ) : (
        <div className="tw-sleeves-grid">
          {momentumSleeves.map((sleeve, index) => (
            <MomentumSleeveCard
              key={`${sleeve?.sleeve_id || "sleeve"}-${index}`}
              sleeve={sleeve}
              index={index}
              onMomentumSleeveChange={onMomentumSleeveChange}
              onRemoveMomentumSleeve={onRemoveMomentumSleeve}
            />
          ))}
        </div>
      )}
    </div>
  );
}
