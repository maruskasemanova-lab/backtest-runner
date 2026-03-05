import type { AOSMomentumSleeveDraft } from "./aosOptimizationsMomentum";
import {
  MOMENTUM_BOOLEAN_FIELDS,
  MOMENTUM_DRAFT_DEFAULTS,
  MOMENTUM_NUMERIC_FIELDS,
  MOMENTUM_SLEEVE_DEFAULTS,
  MOMENTUM_TEXT_FIELDS,
} from "./aosOptimizationsMomentumEditorSchema";

type DraftRecord = Record<string, unknown>;
type FieldChangeHandler = (field: string, value: unknown) => void;

type ActionBarProps = {
  momentumSaving: boolean;
  rawConfigSaving: boolean;
  onLoadFromJson: () => void;
  onApplyToJson: () => void;
  onSaveToServer: () => void;
};

type StatusProps = {
  momentumNotice: string | null;
  momentumError: string | null;
};

type SharedFieldsProps = {
  draft: DraftRecord;
  defaultDraft: DraftRecord;
  onFieldChange: FieldChangeHandler;
};

type SleevesSectionProps = {
  sleeves: AOSMomentumSleeveDraft[];
  onAddSleeve: () => void;
  onRemoveSleeve: (index: number) => void;
  onSleeveFieldChange: (index: number, field: string, value: unknown) => void;
};

const readFieldValue = (
  draft: DraftRecord,
  defaultDraft: DraftRecord,
  field: string,
): unknown => {
  const value = draft[field];
  return value ?? defaultDraft[field] ?? "";
};

function MomentumBooleanGrid({
  draft,
  onFieldChange,
}: {
  draft: DraftRecord;
  onFieldChange: FieldChangeHandler;
}) {
  return (
    <div className="tw-grid-fit-200">
      <MomentumBooleanFieldsContent draft={draft} onFieldChange={onFieldChange} />
    </div>
  );
}

function MomentumBooleanFieldsContent({
  draft,
  onFieldChange,
}: {
  draft: DraftRecord;
  onFieldChange: FieldChangeHandler;
}) {
  return (
    <>
      {MOMENTUM_BOOLEAN_FIELDS.map((field) => (
        <label key={field.field} className="field-row">
          <span>{field.label}</span>
          <input
            type="checkbox"
            checked={!!draft[field.field]}
            onChange={(event) => onFieldChange(field.field, event.target.checked)}
          />
        </label>
      ))}
    </>
  );
}

function MomentumNumberGrid({
  draft,
  defaultDraft,
  onFieldChange,
  gridClassName,
}: SharedFieldsProps & { gridClassName: string }) {
  return (
    <div className={gridClassName}>
      <MomentumNumberFieldsContent
        draft={draft}
        defaultDraft={defaultDraft}
        onFieldChange={onFieldChange}
      />
    </div>
  );
}

function MomentumNumberFieldsContent({
  draft,
  defaultDraft,
  onFieldChange,
}: SharedFieldsProps) {
  return (
    <>
      {MOMENTUM_NUMERIC_FIELDS.map((field) => (
        <div key={field.field} className="form-group">
          <label>{field.label}</label>
          <input
            type="number"
            min={field.min}
            max={field.max}
            step={field.step}
            value={readFieldValue(draft, defaultDraft, field.field) as string | number}
            onChange={(event) => onFieldChange(field.field, Number(event.target.value))}
          />
        </div>
      ))}
    </>
  );
}

function MomentumTextGrid({
  draft,
  defaultDraft,
  onFieldChange,
}: SharedFieldsProps) {
  return (
    <div className="tw-grid-fit-220">
      <MomentumTextFieldsContent
        draft={draft}
        defaultDraft={defaultDraft}
        onFieldChange={onFieldChange}
      />
    </div>
  );
}

function MomentumTextFieldsContent({
  draft,
  defaultDraft,
  onFieldChange,
}: SharedFieldsProps) {
  return (
    <>
      {MOMENTUM_TEXT_FIELDS.map((field) => (
        <div key={field.field} className="form-group">
          <label>{field.label}</label>
          <input
            type="text"
            value={String(readFieldValue(draft, defaultDraft, field.field) ?? "")}
            onChange={(event) => onFieldChange(field.field, event.target.value)}
            placeholder={field.placeholder}
          />
        </div>
      ))}
    </>
  );
}

function MomentumSleeveMetaFields({
  sleeve,
  index,
  onSleeveFieldChange,
}: {
  sleeve: DraftRecord;
  index: number;
  onSleeveFieldChange: (index: number, field: string, value: unknown) => void;
}) {
  return (
    <div className="tw-grid-fit-190">
      <div className="form-group">
        <label>Sleeve ID</label>
        <input
          type="text"
          value={String(readFieldValue(sleeve, MOMENTUM_SLEEVE_DEFAULTS, "sleeve_id") ?? "")}
          onChange={(event) => onSleeveFieldChange(index, "sleeve_id", event.target.value)}
          placeholder="impulse"
        />
      </div>
      <div className="form-group">
        <label>Allocation Weight (0-1)</label>
        <input
          type="number"
          min="0"
          max="1"
          step="0.05"
          value={readFieldValue(
            sleeve,
            MOMENTUM_SLEEVE_DEFAULTS,
            "allocation_weight",
          ) as string | number}
          onChange={(event) =>
            onSleeveFieldChange(index, "allocation_weight", Number(event.target.value))
          }
        />
      </div>
      <MomentumTextFieldsContent
        draft={sleeve}
        defaultDraft={MOMENTUM_SLEEVE_DEFAULTS}
        onFieldChange={(field, value) => onSleeveFieldChange(index, field, value)}
      />
    </div>
  );
}

function MomentumSleeveCard({
  sleeve,
  index,
  onRemoveSleeve,
  onSleeveFieldChange,
}: {
  sleeve: AOSMomentumSleeveDraft;
  index: number;
  onRemoveSleeve: (index: number) => void;
  onSleeveFieldChange: (index: number, field: string, value: unknown) => void;
}) {
  return (
    <div className="tw-sleeve-card">
      <div className="tw-sleeve-header">
        <div className="tw-sleeve-title">Sleeve #{index + 1}</div>
        <button className="btn btn-secondary" type="button" onClick={() => onRemoveSleeve(index)}>
          Remove
        </button>
      </div>

      <MomentumSleeveMetaFields
        sleeve={sleeve}
        index={index}
        onSleeveFieldChange={onSleeveFieldChange}
      />

      <div className="tw-grid-fit-190 ui-mt-md">
        <MomentumBooleanFieldsContent
          draft={sleeve}
          onFieldChange={(field, value) => onSleeveFieldChange(index, field, value)}
        />
      </div>

      <div className="tw-grid-fit-185">
        <MomentumNumberFieldsContent
          draft={sleeve}
          defaultDraft={MOMENTUM_SLEEVE_DEFAULTS}
          onFieldChange={(field, value) => onSleeveFieldChange(index, field, value)}
        />
      </div>
    </div>
  );
}

export function MomentumEditorHeader() {
  return (
    <div className="aos-momentum-header">
      <div className="aos-momentum-title">Visual Momentum Diversification</div>
      <div className="aos-momentum-copy">
        Structured editor for <code>adaptive.momentum_diversification</code> with multi-sleeve
        support.
      </div>
    </div>
  );
}

export function MomentumEditorActionBar({
  momentumSaving,
  rawConfigSaving,
  onLoadFromJson,
  onApplyToJson,
  onSaveToServer,
}: ActionBarProps) {
  const disableJsonActions = rawConfigSaving || momentumSaving;

  return (
    <div className="aos-momentum-actions">
      <button className="btn btn-secondary" onClick={onLoadFromJson} disabled={disableJsonActions}>
        Load From JSON
      </button>
      <button className="btn btn-secondary" onClick={onApplyToJson} disabled={disableJsonActions}>
        Apply Visual To JSON
      </button>
      <button className="btn btn-primary" onClick={onSaveToServer} disabled={momentumSaving}>
        {momentumSaving ? "Saving visual..." : "Save Visual To Server"}
      </button>
    </div>
  );
}

export function MomentumEditorStatus({
  momentumNotice,
  momentumError,
}: StatusProps) {
  return (
    <>
      {momentumNotice ? <div className="ui-note ui-note-success ui-note-compact">{momentumNotice}</div> : null}
      {momentumError ? <div className="ui-note ui-note-danger ui-note-compact">{momentumError}</div> : null}
    </>
  );
}

export function MomentumDraftFields({
  draft,
  onFieldChange,
}: {
  draft: DraftRecord;
  onFieldChange: FieldChangeHandler;
}) {
  return (
    <>
      <MomentumBooleanGrid draft={draft} onFieldChange={onFieldChange} />
      <MomentumNumberGrid
        draft={draft}
        defaultDraft={MOMENTUM_DRAFT_DEFAULTS}
        onFieldChange={onFieldChange}
        gridClassName="tw-grid-fit-185"
      />
      <MomentumTextGrid
        draft={draft}
        defaultDraft={MOMENTUM_DRAFT_DEFAULTS}
        onFieldChange={onFieldChange}
      />
    </>
  );
}

export function MomentumSleevesSection({
  sleeves,
  onAddSleeve,
  onRemoveSleeve,
  onSleeveFieldChange,
}: SleevesSectionProps) {
  return (
    <div className="tw-panel aos-momentum-panel">
      <div className="aos-momentum-section-head">
        <div className="aos-momentum-section-title">Momentum Sleeves</div>
        <button className="btn btn-secondary" type="button" onClick={onAddSleeve}>
          Add Sleeve
        </button>
      </div>

      {sleeves.length === 0 ? (
        <div className="ui-form-help">
          No sleeves defined. Add sleeve rows to enable multi-sleeve behavior.
        </div>
      ) : (
        <div className="aos-momentum-sleeve-list">
          {sleeves.map((sleeve, index) => (
            <MomentumSleeveCard
              key={`${sleeve?.sleeve_id || "sleeve"}-${index}`}
              sleeve={sleeve}
              index={index}
              onRemoveSleeve={onRemoveSleeve}
              onSleeveFieldChange={onSleeveFieldChange}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export function MomentumDirtyNotice() {
  return (
    <div className="ui-note ui-note-warning ui-note-compact">
      Visual momentum editor has unsaved changes.
    </div>
  );
}
