import { isObjectRecord } from "./decision-panel-diagnostics";
import { formatTooltipRuntimeValue } from "./decision-panel-utils";
import type {
  BuildDecisionPanelRuntimeTooltipsParams,
  RuntimeTooltipSetter,
} from "./decision-panel-runtime-tooltip-types";

export const applyDecisionLogRuntimeTooltips = (
  params: BuildDecisionPanelRuntimeTooltipsParams,
  l2SourceFlowNotes: string[],
  setRuntimeTooltip: RuntimeTooltipSetter,
) => {
  const {
    uiLanguage,
    selectedMarker,
    details,
    l2Diagnostics,
    decisionLog,
    contextRiskFieldSource,
    renderReasonValue,
    isRuntimeMissing,
    buildContextRiskMissingLines,
    breakEvenPayload,
    breakEvenFieldSource,
    renderBreakEvenTrigger,
    renderBreakEvenProof,
    buildBreakEvenMissingLines,
    breakEvenStopDisplayValue,
    breakEvenStopSource,
    breakEvenComputed,
    breakEvenBuffer,
    breakEvenAntiSpikeSummary,
    formatPctValue,
    buildVwapFlowValueLines,
  } = params;

  setRuntimeTooltip(
    "Decision Action",
    decisionLog.payload?.decision_state?.action ?? "n/a",
    "details.market_context.decision_state.action",
  );
  setRuntimeTooltip(
    "Decision Phase",
    decisionLog.payload?.decision_state?.phase ?? "n/a",
    "details.market_context.decision_state.phase",
  );
  setRuntimeTooltip(
    "Regime / Micro",
    `${decisionLog.payload?.decision_state?.regime || "n/a"} / ${decisionLog.payload?.decision_state?.micro_regime || "n/a"}`,
    "details.market_context.decision_state.regime / micro_regime",
  );
  setRuntimeTooltip(
    "Selected Strategy",
    decisionLog.payload?.decision_state?.selected_strategy || selectedMarker?.strategy || "n/a",
    "details.market_context.decision_state.selected_strategy",
  );
  setRuntimeTooltip(
    "SL Reason",
    decisionLog.payload?.context_risk?.sl_reason ?? "n/a",
    contextRiskFieldSource("sl_reason"),
    decisionLog.payload?.context_risk?.sl_reason
      ? [
          uiLanguage === "en"
            ? `Interpreted: ${renderReasonValue(decisionLog.payload.context_risk.sl_reason)}`
            : `Interpretované: ${renderReasonValue(decisionLog.payload.context_risk.sl_reason)}`,
        ]
      : buildContextRiskMissingLines("sl_reason"),
  );
  setRuntimeTooltip(
    "TP Reason",
    decisionLog.payload?.context_risk?.tp_reason ?? "n/a",
    contextRiskFieldSource("tp_reason"),
    [
      decisionLog.payload?.context_risk?.tp_reason &&
      String(decisionLog.payload.context_risk.tp_reason).includes("fallback_original")
        ? uiLanguage === "en"
          ? "TP stayed at original strategy target (no context override)."
          : "TP ostal na pôvodnom targete stratégie (bez context override)."
        : "",
      decisionLog.payload?.context_risk?.tp_reason
        ? uiLanguage === "en"
          ? `Interpreted: ${renderReasonValue(decisionLog.payload.context_risk.tp_reason)}`
          : `Interpretované: ${renderReasonValue(decisionLog.payload.context_risk.tp_reason)}`
        : "",
      ...(!decisionLog.payload?.context_risk?.tp_reason
        ? buildContextRiskMissingLines("tp_reason")
        : []),
    ],
  );
  setRuntimeTooltip(
    "Effective RR",
    decisionLog.payload?.context_risk?.effective_rr ?? "n/a",
    contextRiskFieldSource("effective_rr"),
    decisionLog.payload?.context_risk?.room_pct != null &&
    decisionLog.payload?.context_risk?.risk_pct != null
      ? [
          uiLanguage === "en"
            ? `Formula: room_pct (${formatTooltipRuntimeValue(decisionLog.payload.context_risk.room_pct)}) / risk_pct (${formatTooltipRuntimeValue(decisionLog.payload.context_risk.risk_pct)})`
            : `Vzorec: room_pct (${formatTooltipRuntimeValue(decisionLog.payload.context_risk.room_pct)}) / risk_pct (${formatTooltipRuntimeValue(decisionLog.payload.context_risk.risk_pct)})`,
        ]
      : isRuntimeMissing(decisionLog.payload?.context_risk?.effective_rr)
        ? buildContextRiskMissingLines("effective_rr")
        : [],
  );
  setRuntimeTooltip(
    "Risk %",
    decisionLog.payload?.context_risk?.risk_pct ?? "n/a",
    contextRiskFieldSource("risk_pct"),
    [
      details?.entry_price != null && details?.stop_loss != null
        ? uiLanguage === "en"
          ? `Formula: abs(entry (${formatTooltipRuntimeValue(details.entry_price)}) - SL (${formatTooltipRuntimeValue(details.stop_loss)})) / entry * 100`
          : `Vzorec: abs(entry (${formatTooltipRuntimeValue(details.entry_price)}) - SL (${formatTooltipRuntimeValue(details.stop_loss)})) / entry * 100`
        : "",
      ...(isRuntimeMissing(decisionLog.payload?.context_risk?.risk_pct)
        ? buildContextRiskMissingLines("risk_pct")
        : []),
    ],
  );
  setRuntimeTooltip(
    "Break-even State",
    breakEvenPayload?.state ?? "n/a",
    breakEvenFieldSource("state"),
    [
      breakEvenPayload?.active != null
        ? uiLanguage === "en"
          ? `Active: ${formatTooltipRuntimeValue(breakEvenPayload.active)}`
          : `Aktívne: ${formatTooltipRuntimeValue(breakEvenPayload.active)}`
        : "",
      breakEvenPayload?.arm_bar_index != null
        ? `Arm bar: ${formatTooltipRuntimeValue(breakEvenPayload.arm_bar_index)}`
        : "",
      breakEvenPayload?.move_bar_index != null
        ? `Move bar: ${formatTooltipRuntimeValue(breakEvenPayload.move_bar_index)}`
        : "",
      ...(!breakEvenPayload ? buildBreakEvenMissingLines("state") : []),
    ],
  );
  setRuntimeTooltip(
    "Break-even Trigger",
    renderBreakEvenTrigger(breakEvenPayload?.activation_reason),
    breakEvenFieldSource("activation_reason"),
    [
      breakEvenPayload?.activation_reason
        ? uiLanguage === "en"
          ? `Raw token(s): ${breakEvenPayload.activation_reason}`
          : `Raw token(y): ${breakEvenPayload.activation_reason}`
        : "",
      breakEvenPayload?.movement_passed != null
        ? `movement_passed=${formatTooltipRuntimeValue(breakEvenPayload.movement_passed)}`
        : "",
      breakEvenPayload?.proof_passed != null
        ? `proof_passed=${formatTooltipRuntimeValue(breakEvenPayload.proof_passed)}`
        : "",
      breakEvenPayload?.no_go_blocked != null
        ? `no_go_blocked=${formatTooltipRuntimeValue(breakEvenPayload.no_go_blocked)}`
        : "",
      ...(!breakEvenPayload?.activation_reason
        ? buildBreakEvenMissingLines("activation_reason")
        : []),
    ],
  );
  setRuntimeTooltip(
    "Break-even Proof",
    renderBreakEvenProof(breakEvenPayload),
    `${breakEvenFieldSource("levels_proof")} | ${breakEvenFieldSource("l2_proof")}`,
    [
      isObjectRecord(breakEvenPayload?.levels_proof)
        ? `levels: passed=${formatTooltipRuntimeValue(breakEvenPayload.levels_proof.passed)}; no_go=${formatTooltipRuntimeValue(breakEvenPayload.levels_proof.no_go_blocked)}; close_confirmed=${formatTooltipRuntimeValue(breakEvenPayload.levels_proof.close_confirmed)}`
        : "",
      isObjectRecord(breakEvenPayload?.l2_proof)
        ? `l2: passed=${formatTooltipRuntimeValue(breakEvenPayload.l2_proof.passed)}; signed=${formatTooltipRuntimeValue(breakEvenPayload.l2_proof.directional_signed_aggression)}; imbalance=${formatTooltipRuntimeValue(breakEvenPayload.l2_proof.directional_imbalance)}`
        : "",
      ...(isObjectRecord(breakEvenPayload?.levels_proof) ||
      isObjectRecord(breakEvenPayload?.l2_proof)
        ? []
        : buildBreakEvenMissingLines("proof")),
    ],
  );
  setRuntimeTooltip(
    "Break-even Stop",
    breakEvenStopDisplayValue ?? "n/a",
    breakEvenStopSource,
    [
      breakEvenComputed?.entry_price != null
        ? `Entry: ${formatTooltipRuntimeValue(breakEvenComputed.entry_price)}`
        : "",
      breakEvenComputed?.total_costs_pct != null
        ? uiLanguage === "en"
          ? `Total costs %: ${formatPctValue(breakEvenComputed.total_costs_pct, 5)}`
          : `Celkové costs %: ${formatPctValue(breakEvenComputed.total_costs_pct, 5)}`
        : "",
      breakEvenBuffer?.selected_buffer_pct != null
        ? uiLanguage === "en"
          ? `Selected buffer %: ${formatPctValue(breakEvenBuffer.selected_buffer_pct, 5)}`
          : `Zvolený buffer %: ${formatPctValue(breakEvenBuffer.selected_buffer_pct, 5)}`
        : "",
      ...(breakEvenStopDisplayValue == null
        ? buildBreakEvenMissingLines("computed_break_even")
        : []),
    ],
  );
  setRuntimeTooltip(
    "Break-even Costs %",
    breakEvenComputed?.total_costs_pct ?? "n/a",
    breakEvenFieldSource("computed_break_even.total_costs_pct"),
    [
      breakEvenComputed?.base_costs_pct != null
        ? `base_costs_pct=${formatPctValue(breakEvenComputed.base_costs_pct, 5)}`
        : "",
      breakEvenComputed?.spread_component_pct != null
        ? `spread_component_pct=${formatPctValue(breakEvenComputed.spread_component_pct, 5)}`
        : "",
      breakEvenComputed?.spread_bps != null
        ? `spread_bps=${formatTooltipRuntimeValue(breakEvenComputed.spread_bps)}`
        : "",
      ...(breakEvenComputed?.total_costs_pct == null
        ? buildBreakEvenMissingLines("computed_break_even.total_costs_pct")
        : []),
    ],
  );
  setRuntimeTooltip(
    "Break-even Buffer %",
    breakEvenBuffer?.selected_buffer_pct ?? "n/a",
    breakEvenFieldSource("computed_break_even.buffer.selected_buffer_pct"),
    [
      breakEvenBuffer?.base_buffer_pct != null
        ? `base=${formatPctValue(breakEvenBuffer.base_buffer_pct, 5)}`
        : "",
      breakEvenBuffer?.min_buffer_pct != null
        ? `min=${formatPctValue(breakEvenBuffer.min_buffer_pct, 5)}`
        : "",
      breakEvenBuffer?.atr_buffer_pct != null
        ? `atr_1m=${formatPctValue(breakEvenBuffer.atr_buffer_pct, 5)}`
        : "",
      breakEvenBuffer?.atr5_buffer_pct != null
        ? `atr_5m=${formatPctValue(breakEvenBuffer.atr5_buffer_pct, 5)}`
        : "",
      breakEvenBuffer?.tick_buffer_pct != null
        ? `tick=${formatPctValue(breakEvenBuffer.tick_buffer_pct, 5)}`
        : "",
      breakEvenBuffer?.selected_buffer_abs != null
        ? `selected_abs=${formatTooltipRuntimeValue(breakEvenBuffer.selected_buffer_abs)}`
        : "",
      ...(breakEvenBuffer?.selected_buffer_pct == null
        ? buildBreakEvenMissingLines("computed_break_even.buffer")
        : []),
    ],
  );
  setRuntimeTooltip(
    "Break-even Anti-Spike",
    breakEvenAntiSpikeSummary,
    `${breakEvenFieldSource("anti_spike_bars_remaining")} | ${breakEvenFieldSource("anti_spike_consecutive_hits")} | ${breakEvenFieldSource("anti_spike_consecutive_hits_required")} | ${breakEvenFieldSource("anti_spike_require_close_beyond")}`,
    [
      breakEvenPayload?.anti_spike_bars_remaining != null
        ? `bars_remaining=${formatTooltipRuntimeValue(breakEvenPayload.anti_spike_bars_remaining)}`
        : "",
      breakEvenPayload?.anti_spike_consecutive_hits != null
        ? `hits=${formatTooltipRuntimeValue(breakEvenPayload.anti_spike_consecutive_hits)}`
        : "",
      breakEvenPayload?.anti_spike_consecutive_hits_required != null
        ? `required_hits=${formatTooltipRuntimeValue(breakEvenPayload.anti_spike_consecutive_hits_required)}`
        : "",
      breakEvenPayload?.anti_spike_require_close_beyond != null
        ? `require_close_beyond=${formatTooltipRuntimeValue(breakEvenPayload.anti_spike_require_close_beyond)}`
        : "",
      uiLanguage === "en"
        ? "Trigger rule: close-beyond OR required consecutive hits."
        : "Trigger pravidlo: close-beyond ALEBO required consecutive hits.",
      ...(!breakEvenPayload ? buildBreakEvenMissingLines("anti_spike") : []),
    ],
  );
  setRuntimeTooltip(
    "VWAP Execution Flow (Decision Log)",
    decisionLog.payload?.flow_snapshot?.vwap_execution_flow ?? "n/a",
    `decisionLog.payload.flow_snapshot.vwap_execution_flow (${l2Diagnostics.sourcePath || "n/a"})`,
    [
      ...l2SourceFlowNotes,
      ...buildVwapFlowValueLines(
        decisionLog.payload?.flow_snapshot?.vwap_execution_flow,
        l2Diagnostics.sourcePath || "n/a",
      ),
    ],
  );
  setRuntimeTooltip("Complete Decision Payload", "JSON payload", "decisionLog.payload");
};
