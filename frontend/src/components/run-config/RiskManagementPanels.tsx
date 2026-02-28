import {
  RiskManagementCheckboxField,
  RiskManagementNumberField,
  RiskManagementPanel,
  RiskManagementSelectField,
  type RiskManagementChangeHandler,
  type RiskManagementConfig,
} from "./riskManagementFieldControls";

type RiskManagementPanelProps = {
  config: RiskManagementConfig;
  handleChange: RiskManagementChangeHandler;
};

const clampMinZero = (value: number) => Math.max(0, value);
const clampUnitRange = (value: number) => Math.max(0, Math.min(1, value));
const clampPartialFraction = (value: number) => Math.max(0.05, Math.min(0.95, value));
const clampPartialTarget = (value: number) => Math.max(0.25, value);
const clampLevelTests = (value: number) => Math.max(0, Math.trunc(value));
const clampMaxAnchorSearch = (value: number) => Math.max(0.1, value);

const EXECUTION_SIZING_FIELDS = [
  { field: "risk_per_trade_pct", label: "Risk Per Trade (%)", min: "0.1", max: "10", step: "0.1" },
  { field: "max_position_notional_pct", label: "Max Position Notional (%)", min: "1", max: "100", step: "1" },
  { field: "max_fill_participation_rate", label: "Max Fill Participation (0-1)", min: "0.01", max: "1", step: "0.01" },
  { field: "min_fill_ratio", label: "Min Fill Ratio (0-1)", min: "0.01", max: "1", step: "0.01" },
  { field: "time_exit_bars", label: "Time Exit (bars)", min: "1", step: "1" },
] as const;

const CONTEXT_RISK_FIELDS = [
  { field: "context_risk_sl_buffer_pct", label: "SL Buffer (%)", min: "0", step: "0.01", normalize: clampMinZero },
  { field: "context_risk_min_sl_pct", label: "Min SL Floor (%)", min: "0", step: "0.01", normalize: clampMinZero },
  { field: "context_risk_min_room_pct", label: "Min Room (%)", min: "0", step: "0.01", normalize: clampMinZero },
  { field: "context_risk_min_effective_rr", label: "Min Effective RR", min: "0", step: "0.1", normalize: clampMinZero },
  {
    field: "context_risk_trailing_tighten_zone",
    label: "Trailing Tighten Zone (0-1)",
    min: "0",
    max: "1",
    step: "0.05",
    normalize: clampUnitRange,
  },
  {
    field: "context_risk_trailing_tighten_factor",
    label: "Trailing Tighten Factor (0-1)",
    min: "0",
    max: "1",
    step: "0.05",
    normalize: clampUnitRange,
  },
  {
    field: "context_risk_max_anchor_search_pct",
    label: "Max Anchor Search (%)",
    min: "0.1",
    step: "0.1",
    normalize: clampMaxAnchorSearch,
  },
  {
    field: "context_risk_min_level_tests_for_sl",
    label: "Min Level Tests for SL",
    min: "0",
    step: "1",
    normalize: clampLevelTests,
  },
] as const;

const STOP_LOSS_FIELDS = [
  { field: "trailing_stop_pct", label: "Global Trailing Stop (%)", min: "0", max: "5", step: "0.01" },
  { field: "global_exit_rr_ratio", label: "Global Exit RR Ratio", min: "0", max: "10", step: "0.05" },
  { field: "global_risk_atr_stop_multiplier", label: "Global Risk ATR Stop Multiplier", min: "0", max: "10", step: "0.05" },
  { field: "global_risk_volume_stop_pct", label: "Global Risk Volume Stop (%)", min: "0", max: "10", step: "0.05" },
  { field: "global_risk_min_stop_loss_pct", label: "Global Risk Min Stop-Loss (%)", min: "0", max: "5", step: "0.01" },
  { field: "trailing_activation_pct", label: "Trailing Activation (% MFE)", min: "0", max: "5", step: "0.01" },
] as const;

const BREAK_EVEN_FIELDS = [
  {
    field: "break_even_activation_min_r",
    label: "BE Activation Min R",
    min: "0",
    max: "5",
    step: "0.1",
    normalize: clampMinZero,
  },
  {
    field: "break_even_activation_min_r_trending_5m",
    label: "BE Min R (Trending 5m)",
    min: "0",
    max: "5",
    step: "0.1",
    normalize: clampMinZero,
  },
  {
    field: "break_even_activation_min_r_choppy_5m",
    label: "BE Min R (Choppy 5m)",
    min: "0",
    max: "5",
    step: "0.1",
    normalize: clampMinZero,
  },
  { field: "break_even_buffer_pct", label: "Break-even Buffer (%)", min: "0", max: "2", step: "0.01" },
  { field: "break_even_min_hold_bars", label: "Break-even Min Hold (bars)", min: "1", step: "1" },
] as const;

const PARTIAL_TAKE_PROFIT_FIELDS = [
  {
    field: "partial_take_profit_rr",
    label: "Partial TP Target (R-multiple)",
    min: "0.25",
    max: "10",
    step: "0.1",
    normalize: clampPartialTarget,
  },
  {
    field: "partial_take_profit_fraction",
    label: "Partial TP Fraction (0.05-0.95)",
    min: "0.05",
    max: "0.95",
    step: "0.05",
    normalize: clampPartialFraction,
  },
  {
    field: "partial_flow_deterioration_min_r",
    label: "Flow Deterioration Min R (0 = disabled)",
    min: "0",
    max: "5",
    step: "0.1",
    normalize: clampMinZero,
    fallbackValue: 0.5,
  },
] as const;

const ADVERSE_FLOW_FIELDS = [
  { field: "adverse_flow_threshold", label: "Adverse Flow Threshold", min: "0.02", max: "1", step: "0.01" },
  { field: "adverse_flow_min_hold_bars", label: "Adverse Flow Min Hold (bars)", min: "1", step: "1" },
] as const;

export function ExecutionSizingPanel({
  config,
  handleChange,
}: RiskManagementPanelProps) {
  return (
    <RiskManagementPanel
      title="Execution Sizing"
      hint="Tieto nastavenia riadia veľkosť pozície, fill realizmus a maximálnu dĺžku držania."
    >
      {EXECUTION_SIZING_FIELDS.map((field) => (
        <RiskManagementNumberField
          key={field.field}
          config={config}
          handleChange={handleChange}
          {...field}
        />
      ))}
    </RiskManagementPanel>
  );
}

export function ContextAwareRiskPanel({
  config,
  handleChange,
}: RiskManagementPanelProps) {
  return (
    <RiskManagementPanel
      title="Context-Aware Risk (Level-Anchored SL/TP)"
      hint="Prispôsobí SL a TP podľa najbližších S/R úrovní."
    >
      <RiskManagementCheckboxField
        field="context_aware_risk_enabled"
        label="Enable Context-Aware Risk"
        checked={!!config.context_aware_risk_enabled}
        handleChange={handleChange}
      />

      {config.context_aware_risk_enabled ? (
        <div className="tw-grid-fit-190" style={{ paddingTop: 4 }}>
          {CONTEXT_RISK_FIELDS.map((field) => (
            <RiskManagementNumberField
              key={field.field}
              config={config}
              handleChange={handleChange}
              {...field}
            />
          ))}
          <RiskManagementCheckboxField
            field="context_risk_level_trail_enabled"
            label="Trail SL along levels"
            checked={!!config.context_risk_level_trail_enabled}
            handleChange={handleChange}
          />
        </div>
      ) : null}
    </RiskManagementPanel>
  );
}

export function StopLossAndBreakEvenPanel({
  config,
  handleChange,
}: RiskManagementPanelProps) {
  return (
    <RiskManagementPanel
      title="Stop-Loss And Break-Even"
      hint="`strategy` = stop zo stratégie, `fixed` = vždy fixné %, `capped` = prísnejší zo strategy/fixed."
    >
      <RiskManagementSelectField
        config={config}
        field="stop_loss_mode"
        label="Stop-Loss Mode"
        handleChange={handleChange}
        defaultValue="strategy"
        options={[
          { value: "strategy", label: "strategy (use strategy stop)" },
          { value: "fixed", label: "fixed (always fixed % stop)" },
          { value: "capped", label: "capped (cap only wide stops)" },
        ]}
      />

      <RiskManagementNumberField
        config={config}
        field="fixed_stop_loss_pct"
        label="Fixed Stop-Loss (%)"
        min="0.01"
        max="5"
        step="0.05"
        disabled={config.stop_loss_mode === "strategy"}
        handleChange={handleChange}
      />

      {STOP_LOSS_FIELDS.map((field) => (
        <RiskManagementNumberField
          key={field.field}
          config={config}
          handleChange={handleChange}
          {...field}
        />
      ))}

      <RiskManagementNumberField
        config={config}
        field="break_even_activation_min_mfe_pct"
        label="BE Activation Min MFE (%)"
        min="0"
        max="5"
        step="0.01"
        normalize={clampMinZero}
        handleChange={handleChange}
      />

      <RiskManagementCheckboxField
        field="break_even_activation_use_levels"
        label="BE Require Levels Proof"
        checked={config.break_even_activation_use_levels !== false}
        handleChange={handleChange}
      />
      <RiskManagementCheckboxField
        field="break_even_activation_use_l2"
        label="BE Require L2 Proof"
        checked={config.break_even_activation_use_l2 !== false}
        handleChange={handleChange}
      />

      {BREAK_EVEN_FIELDS.map((field) => (
        <RiskManagementNumberField
          key={field.field}
          config={config}
          handleChange={handleChange}
          {...field}
        />
      ))}
      <RiskManagementCheckboxField
        field="trailing_enabled_in_choppy"
        label="Enable Trailing In CHOPPY"
        checked={!!config.trailing_enabled_in_choppy}
        handleChange={handleChange}
      />
    </RiskManagementPanel>
  );
}

export function PartialTakeProfitPanel({
  config,
  handleChange,
}: RiskManagementPanelProps) {
  return (
    <RiskManagementPanel
      title="Partial Take Profit"
      hint="Ak je aktivovaný, systém vezme časť pozície pri dosiahnutí RR cieľa a posunie stop na BE."
    >
      <RiskManagementCheckboxField
        field="enable_partial_take_profit"
        label="Enable Partial Take Profit"
        checked={config.enable_partial_take_profit !== false}
        handleChange={handleChange}
      />

      {config.enable_partial_take_profit !== false ? (
        <>
          {PARTIAL_TAKE_PROFIT_FIELDS.map((field) => (
            <RiskManagementNumberField
              key={field.field}
              config={config}
              handleChange={handleChange}
              {...field}
            />
          ))}
          <RiskManagementCheckboxField
            field="partial_flow_deterioration_skip_be"
            label="Skip BE After Flow Deterioration Partial"
            checked={config.partial_flow_deterioration_skip_be !== false}
            handleChange={handleChange}
          />
        </>
      ) : null}
    </RiskManagementPanel>
  );
}

export function MicroConfirmationPanel({
  config,
  handleChange,
}: RiskManagementPanelProps) {
  return (
    <RiskManagementPanel
      title="Micro Confirmation"
      hint="2-bar potvrdenie pred vstupom. Pre daytrading odporúčané VYPNUTÉ."
    >
      <RiskManagementCheckboxField
        field="intraday_levels_micro_confirmation_enabled"
        label="Enable 2-Bar Micro Confirmation"
        checked={!!config.intraday_levels_micro_confirmation_enabled}
        handleChange={handleChange}
      />
    </RiskManagementPanel>
  );
}

export function AdverseFlowExitPanel({
  config,
  handleChange,
}: RiskManagementPanelProps) {
  return (
    <RiskManagementPanel
      title="Adverse Flow Exit"
      hint="Ochranný exit pri zhoršení order-flow podmienok po vstupe."
    >
      <RiskManagementCheckboxField
        field="adverse_flow_exit_enabled"
        label="Adverse Flow Exit Enabled"
        checked={!!config.adverse_flow_exit_enabled}
        handleChange={handleChange}
      />

      {ADVERSE_FLOW_FIELDS.map((field) => (
        <RiskManagementNumberField
          key={field.field}
          config={config}
          handleChange={handleChange}
          {...field}
        />
      ))}
    </RiskManagementPanel>
  );
}
