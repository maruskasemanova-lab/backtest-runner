import type { AOSMomentumSleeveDraft } from "./aosOptimizationsMomentum";
import {
  MOMENTUM_ACTIONS_STYLE,
  MOMENTUM_BOOLEAN_FIELDS,
  MOMENTUM_DIRTY_STYLE,
  MOMENTUM_DRAFT_DEFAULTS,
  MOMENTUM_EMPTY_SLEEVES_STYLE,
  MOMENTUM_ERROR_STYLE,
  MOMENTUM_NOTICE_STYLE,
  MOMENTUM_NUMERIC_FIELDS,
  MOMENTUM_NUMERIC_GRID_STYLE,
  MOMENTUM_SECTION_HEADER_STYLE,
  MOMENTUM_SLEEVE_CARD_STYLE,
  MOMENTUM_SLEEVE_DEFAULTS,
  MOMENTUM_SLEEVE_META_GRID_STYLE,
  MOMENTUM_SLEEVE_NUMERIC_GRID_STYLE,
  MOMENTUM_SLEEVE_TOGGLE_GRID_STYLE,
  MOMENTUM_SLEEVES_PANEL_STYLE,
  MOMENTUM_TEXT_FIELDS,
  MOMENTUM_TEXT_GRID_STYLE,
  MOMENTUM_TOGGLE_GRID_STYLE,
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
    <div style={MOMENTUM_TOGGLE_GRID_STYLE}>
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
  gridStyle,
}: SharedFieldsProps & { gridStyle: typeof MOMENTUM_NUMERIC_GRID_STYLE }) {
  return (
    <div style={gridStyle}>
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
    <div style={MOMENTUM_TEXT_GRID_STYLE}>
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
    <div style={MOMENTUM_SLEEVE_META_GRID_STYLE}>
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
          value={readFieldValue(sleeve, MOMENTUM_SLEEVE_DEFAULTS, "allocation_weight") as string | number}
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
    <div style={MOMENTUM_SLEEVE_CARD_STYLE}>
      <div style={MOMENTUM_SECTION_HEADER_STYLE}>
        <div style={{ fontWeight: 700, fontSize: "0.76rem" }}>Sleeve #{index + 1}</div>
        <button className="btn btn-secondary" type="button" onClick={() => onRemoveSleeve(index)}>
          Remove
        </button>
      </div>

      <MomentumSleeveMetaFields
        sleeve={sleeve}
        index={index}
        onSleeveFieldChange={onSleeveFieldChange}
      />

      <div style={MOMENTUM_SLEEVE_TOGGLE_GRID_STYLE}>
        <MomentumBooleanFieldsContent
          draft={sleeve}
          onFieldChange={(field, value) => onSleeveFieldChange(index, field, value)}
        />
      </div>

      <div style={MOMENTUM_SLEEVE_NUMERIC_GRID_STYLE}>
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
    <>
      <div style={{ fontWeight: 700, fontSize: "0.82rem" }}>
        Visual Momentum Diversification
      </div>
      <div style={{ color: "var(--text-muted)", fontSize: "0.76rem" }}>
        Structured editor for <code>adaptive.momentum_diversification</code> with multi-sleeve
        support.
      </div>
    </>
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
    <div style={MOMENTUM_ACTIONS_STYLE}>
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
      {momentumNotice ? <div style={MOMENTUM_NOTICE_STYLE}>{momentumNotice}</div> : null}
      {momentumError ? <div style={MOMENTUM_ERROR_STYLE}>{momentumError}</div> : null}
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
        gridStyle={MOMENTUM_NUMERIC_GRID_STYLE}
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
    <div style={MOMENTUM_SLEEVES_PANEL_STYLE}>
      <div style={MOMENTUM_SECTION_HEADER_STYLE}>
        <div style={{ fontWeight: 700, fontSize: "0.78rem" }}>Momentum Sleeves</div>
        <button className="btn btn-secondary" type="button" onClick={onAddSleeve}>
          Add Sleeve
        </button>
      </div>

      {sleeves.length === 0 ? (
        <div style={MOMENTUM_EMPTY_SLEEVES_STYLE}>
          No sleeves defined. Add sleeve rows to enable multi-sleeve behavior.
        </div>
      ) : (
        <div style={{ display: "grid", gap: "10px" }}>
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
    <div style={MOMENTUM_DIRTY_STYLE}>
      Visual momentum editor has unsaved changes.
    </div>
  );
}
