import { useMemo } from "react";
import {
  extractDecisionLogPayload,
  extractEntryQualityDiagnostics,
  extractIntradayLevels,
  extractL2Diagnostics,
  extractLevelContext,
  isObjectRecord,
  L2_DIAGNOSTIC_KEYS,
  resolveBreakEven,
  resolveContextRisk,
  resolveRiskControls,
} from "./decision-panel-diagnostics";
import {
  BREAK_EVEN_TRIGGER_TRANSLATIONS,
  COST_LABEL_BY_KEY,
  DECISION_LABELS,
  DECISION_REASON_TRANSLATIONS,
  DECISION_TOOLTIPS,
} from "./decision-panel-copy";
import {
  formatTooltipRuntimeValue,
  resolvePnlPct,
  resolveTooltipBaseLabel,
  toFiniteNumber,
} from "./decision-panel-utils";
import type {
  DecisionPanelMarkerLike,
  DecisionPanelTooltipRuntimeMap,
} from "./decision-panel-types";

type UseDecisionPanelViewModelParams = {
  selectedMarker: DecisionPanelMarkerLike | null;
  uiLanguage: string;
};

const buildDecisionPanelViewModel = (
  selectedMarker: DecisionPanelMarkerLike | null,
  uiLanguage: string,
) => {
  const details = selectedMarker?.details || {};
  const metadata = details.metadata || {};
  const l2Diagnostics = extractL2Diagnostics(selectedMarker, details, metadata);
  const intradayLevels = extractIntradayLevels(selectedMarker, details, metadata);
  const levelContext = extractLevelContext(selectedMarker, details, metadata);
  const entryQualityDiagnostics = extractEntryQualityDiagnostics(selectedMarker, details, metadata);
  const decisionLog = extractDecisionLogPayload(selectedMarker, details, metadata);

  const t = (text) =>
    DECISION_LABELS[uiLanguage]?.[text] ??
    DECISION_LABELS.en?.[text] ??
    text;
  const renderYesNo = (flag) => (flag ? t("yes") : t("no"));
  const renderEnabled = (flag) => (flag ? t("Enabled") : t("Disabled"));
  const renderGateStatus = (flag) => (flag ? t("PASSED") : t("BLOCKED"));
  const renderCostLabel = (key) => {
    const mapped = COST_LABEL_BY_KEY[key];
    if (mapped) return mapped;
    return key.charAt(0).toUpperCase() + key.slice(1).replace('_', ' ');
  };
  const translateReasonToken = (rawToken) => {
    const token = String(rawToken || "").trim();
    if (!token) return token;
    const translations =
      DECISION_REASON_TRANSLATIONS[uiLanguage] ?? DECISION_REASON_TRANSLATIONS.en;
    const exact = translations[token];
    if (exact) return `${exact} (${token})`;

    const separators = [token.indexOf(":"), token.indexOf("(")].filter(
      (index) => index > 0,
    );
    if (!separators.length) return token;

    const splitIndex = Math.min(...separators);
    const prefix = token.slice(0, splitIndex);
    const translatedPrefix = translations[prefix];
    if (!translatedPrefix) return token;
    return `${translatedPrefix}${token.slice(splitIndex)} (${token})`;
  };
  const renderReasonValue = (value) => {
    const raw = String(value || "").trim();
    if (!raw) return "n/a";
    return raw
      .split("|")
      .map((token) => translateReasonToken(token))
      .join(" | ");
  };
  const detailSignalMetadata = isObjectRecord(details?.signal_metadata) ? details.signal_metadata : null;
  const detailMarketContext = isObjectRecord(details?.market_context) ? details.market_context : null;
  const riskControlsResolution = resolveRiskControls({
    details,
    signalMetadata: detailSignalMetadata,
    marketContext: detailMarketContext,
  });
  const contextRiskResolution = resolveContextRisk({
    details,
    signalMetadata: detailSignalMetadata,
    marketContext: detailMarketContext,
    riskControls: riskControlsResolution.value,
  });
  const breakEvenResolution = resolveBreakEven({
    details,
    signalMetadata: detailSignalMetadata,
    marketContext: detailMarketContext,
  });
  const contextRiskFieldSource = (fieldName) =>
    contextRiskResolution.sourcePath === "n/a"
      ? "context_risk (unavailable)"
      : `${contextRiskResolution.sourcePath}.${fieldName}`;
  const breakEvenSourcePath = String(
    decisionLog.payload?.break_even_source_path || breakEvenResolution.sourcePath || "n/a",
  );
  const breakEvenPayload = isObjectRecord(decisionLog.payload?.break_even)
    ? decisionLog.payload.break_even
    : null;
  const breakEvenComputed = isObjectRecord(breakEvenPayload?.computed_break_even)
    ? breakEvenPayload.computed_break_even
    : null;
  const breakEvenBuffer = isObjectRecord(breakEvenComputed?.buffer)
    ? breakEvenComputed.buffer
    : null;
  const breakEvenFieldSource = (fieldName) =>
    breakEvenSourcePath === "n/a"
      ? "break_even (unavailable)"
      : `${breakEvenSourcePath}.${fieldName}`;
  const formatPctValue = (value, digits = 4) => {
    const numeric = toFiniteNumber(value);
    return numeric == null ? "n/a" : `${numeric.toFixed(digits)}%`;
  };
  const translateBreakEvenToken = (rawToken) => {
    const token = String(rawToken || "").trim();
    if (!token) return token;
    const translations =
      BREAK_EVEN_TRIGGER_TRANSLATIONS[uiLanguage] ??
      BREAK_EVEN_TRIGGER_TRANSLATIONS.en;
    const mapped = translations[token];
    return mapped ? `${mapped} (${token})` : token;
  };
  const renderBreakEvenTrigger = (rawValue) => {
    const raw = String(rawValue || "").trim();
    if (!raw) return "n/a";
    return raw
      .split("|")
      .map((token) => translateBreakEvenToken(token))
      .join(" | ");
  };
  const renderBreakEvenProof = (payload) => {
    if (!isObjectRecord(payload)) return "n/a";
    const levels = isObjectRecord(payload.levels_proof) ? payload.levels_proof : null;
    const l2 = isObjectRecord(payload.l2_proof) ? payload.l2_proof : null;
    if (!levels && !l2) return "n/a";
    const parts = [];
    if (levels) {
      const levelState = levels.passed ? "pass" : "fail";
      const levelNoGo = levels.no_go_blocked ? "/no-go" : "";
      parts.push(`levels:${levelState}${levelNoGo}`);
    }
    if (l2) {
      parts.push(`l2:${l2.passed ? "pass" : "fail"}`);
    }
    return parts.join(" | ") || "n/a";
  };
  const breakEvenStopDisplayValue = toFiniteNumber(
    breakEvenComputed?.updated_stop_loss ??
    breakEvenComputed?.stop_level ??
    breakEvenPayload?.stop_loss,
  );
  const breakEvenStopSource =
    breakEvenComputed?.updated_stop_loss != null
      ? breakEvenFieldSource("computed_break_even.updated_stop_loss")
      : breakEvenComputed?.stop_level != null
        ? breakEvenFieldSource("computed_break_even.stop_level")
        : breakEvenPayload?.stop_loss != null
          ? breakEvenFieldSource("stop_loss")
          : breakEvenFieldSource("computed_break_even.stop_level");
  const breakEvenAntiSpikeSummary = breakEvenPayload
    ? `${Number(breakEvenPayload.anti_spike_bars_remaining || 0)} bars / ${Number(
        breakEvenPayload.anti_spike_consecutive_hits || 0,
      )}/${Number(
        breakEvenPayload.anti_spike_consecutive_hits_required || 0,
      )} hits / closeBeyond=${breakEvenPayload.anti_spike_require_close_beyond ? "true" : "false"}`
    : "n/a";
  const describePathPresence = (value) => {
    if (isObjectRecord(value)) return uiLanguage === "en" ? "object" : "objekt";
    if (value === null) return "null";
    if (value === undefined) return uiLanguage === "en" ? "missing" : "chýba";
    if (Array.isArray(value)) return `${uiLanguage === "en" ? "array" : "pole"}(${value.length})`;
    return String(value);
  };
  const isRuntimeMissing = (value) => {
    if (value === null || value === undefined) return true;
    if (typeof value !== "string") return false;
    const normalized = value.trim().toLowerCase();
    return (
      normalized === "" ||
      normalized === "n/a" ||
      normalized === "na" ||
      normalized === "null" ||
      normalized === "undefined"
    );
  };
  const numericEntryPrice = toFiniteNumber(details?.entry_price);
  const numericStopLoss = toFiniteNumber(details?.stop_loss);
  const numericTakeProfit = toFiniteNumber(details?.take_profit);
  const fallbackRiskPct =
    numericEntryPrice !== null &&
    numericStopLoss !== null &&
    numericEntryPrice !== 0
      ? (Math.abs(numericEntryPrice - numericStopLoss) / Math.abs(numericEntryPrice)) * 100
      : null;
  const fallbackApproxRr =
    numericEntryPrice !== null &&
    numericStopLoss !== null &&
    numericTakeProfit !== null &&
    Math.abs(numericEntryPrice - numericStopLoss) > 0
      ? Math.abs(numericTakeProfit - numericEntryPrice) /
        Math.abs(numericEntryPrice - numericStopLoss)
      : null;
  const buildContextRiskMissingLines = (fieldKey) => {
    const lines = [];
    lines.push(
      uiLanguage === "en"
        ? "Why n/a: context_risk field is unavailable for this marker."
        : "Prečo n/a: pole context_risk nie je pre tento marker dostupné.",
    );
    lines.push(
      uiLanguage === "en"
        ? `Resolved context_risk source: ${contextRiskResolution.sourcePath}`
        : `Nájdený zdroj context_risk: ${contextRiskResolution.sourcePath}`,
    );

    const checkedPaths = contextRiskResolution.candidates
      .slice(0, 7)
      .map((candidate) => `- ${candidate.path}: ${describePathPresence(candidate.value)}`);
    if (checkedPaths.length) {
      lines.push(uiLanguage === "en" ? "Checked paths:" : "Kontrolované cesty:");
      lines.push(...checkedPaths);
    }

    const riskControls = riskControlsResolution.value;
    if (isObjectRecord(riskControls)) {
      const summaryBits = [];
      if (riskControls.stop_loss_mode != null) {
        summaryBits.push(`stop_loss_mode=${riskControls.stop_loss_mode}`);
      }
      if (riskControls.fixed_stop_loss_pct != null) {
        summaryBits.push(`fixed_stop_loss_pct=${formatTooltipRuntimeValue(riskControls.fixed_stop_loss_pct)}%`);
      }
      if (riskControls.effective_stop_loss != null) {
        summaryBits.push(`effective_stop_loss=${formatTooltipRuntimeValue(riskControls.effective_stop_loss)}`);
      }
      if (riskControls.strategy_stop_loss != null) {
        summaryBits.push(`strategy_stop_loss=${formatTooltipRuntimeValue(riskControls.strategy_stop_loss)}`);
      }
      if (summaryBits.length) {
        lines.push(
          uiLanguage === "en"
            ? `Related risk_controls (${riskControlsResolution.sourcePath}): ${summaryBits.join(", ")}`
            : `Súvisiace risk_controls (${riskControlsResolution.sourcePath}): ${summaryBits.join(", ")}`,
        );
      }
    }

    if (fieldKey === "risk_pct" && fallbackRiskPct !== null) {
      lines.push(
        uiLanguage === "en"
          ? `Fallback computed risk% from entry/SL: ${fallbackRiskPct.toFixed(4)}%`
          : `Fallback výpočet rizika z entry/SL: ${fallbackRiskPct.toFixed(4)}%`,
      );
    }
    if (fieldKey === "effective_rr" && fallbackApproxRr !== null) {
      lines.push(
        uiLanguage === "en"
          ? `Approx RR from entry/SL/TP (fallback): ${fallbackApproxRr.toFixed(4)}`
          : `Približné RR z entry/SL/TP (fallback): ${fallbackApproxRr.toFixed(4)}`,
      );
    }
    if (fieldKey === "tp_reason" && numericTakeProfit !== null) {
      lines.push(
        uiLanguage === "en"
          ? "TP value exists, but TP reason token is absent in context_risk."
          : "TP hodnota existuje, ale dôvod TP token v context_risk chýba.",
      );
    }
    if (fieldKey === "sl_reason" && numericStopLoss !== null) {
      lines.push(
        uiLanguage === "en"
          ? "SL value exists, but SL reason token is absent in context_risk."
          : "SL hodnota existuje, ale dôvod SL token v context_risk chýba.",
      );
    }

    return lines;
  };
  const buildBreakEvenMissingLines = (fieldKey) => {
    const lines = [];
    lines.push(
      uiLanguage === "en"
        ? "Why n/a: break_even field is unavailable for this marker."
        : "Prečo n/a: pole break_even nie je pre tento marker dostupné.",
    );
    lines.push(
      uiLanguage === "en"
        ? `Resolved break_even source: ${breakEvenSourcePath}`
        : `Nájdený zdroj break_even: ${breakEvenSourcePath}`,
    );

    const checkedPaths = (breakEvenResolution.candidates || [])
      .slice(0, 7)
      .map((candidate) => `- ${candidate.path}: ${describePathPresence(candidate.value)}`);
    if (checkedPaths.length) {
      lines.push(uiLanguage === "en" ? "Checked paths:" : "Kontrolované cesty:");
      lines.push(...checkedPaths);
    }

    const exitReason = String(details?.exit_reason || "").trim().toLowerCase();
    if (exitReason === "breakeven_stop") {
      lines.push(
        uiLanguage === "en"
          ? "Exit reason is breakeven_stop, but BE diagnostics payload is missing."
          : "Exit reason je breakeven_stop, ale diagnostický BE payload chýba.",
      );
    }
    if (fieldKey === "computed_break_even" && breakEvenPayload?.activation_reason) {
      lines.push(
        uiLanguage === "en"
          ? `Activation trigger exists: ${renderBreakEvenTrigger(breakEvenPayload.activation_reason)}`
          : `Trigger aktivácie existuje: ${renderBreakEvenTrigger(breakEvenPayload.activation_reason)}`,
      );
    }

    return lines;
  };
  const buildVwapFlowValueLines = (value, sourcePath) => {
    if (value === null || value === undefined) {
      return [
        uiLanguage === "en"
          ? "Why n/a: selected flow snapshot has no vwap_execution_flow metric."
          : "Prečo n/a: zvolený flow snapshot neobsahuje metriku vwap_execution_flow.",
      ];
    }
    if (Number(value) === 0) {
      return [
        uiLanguage === "en"
          ? "0.000 is a valid neutral reading, not a missing value."
          : "0.000 je validná neutrálna hodnota, nie chýbajúci údaj.",
        uiLanguage === "en"
          ? `Metric source: ${sourcePath || "n/a"}`
          : `Zdroj metriky: ${sourcePath || "n/a"}`,
      ];
    }
    return [];
  };
  const tooltipLocaleText =
    uiLanguage === "en"
      ? {
          value: "Current value",
          source: "Resolved source",
          l2Title: "L2 source selection",
          chosen: "Chosen source",
          unavailable: "Value not present on selected source",
        }
      : {
          value: "Aktuálna hodnota",
          source: "Použitý zdroj",
          l2Title: "Výber L2 zdroja",
          chosen: "Zvolený zdroj",
          unavailable: "Hodnota nie je na zvolenom zdroji",
        };
  const baseTooltipFor = (label) => {
    const baseLabel = resolveTooltipBaseLabel(label);
    return (
      DECISION_TOOLTIPS[uiLanguage]?.[baseLabel] ??
      DECISION_TOOLTIPS.sk?.[baseLabel] ??
      DECISION_TOOLTIPS.sk?._default ??
      ""
    );
  };
  const l2CandidateFlowLines = (l2Diagnostics.candidateDiagnostics || []).map((candidate) => {
    const metrics =
      candidate.availableMetrics?.length > 0
        ? candidate.availableMetrics.join(", ")
        : (uiLanguage === "en" ? "no metrics" : "žiadne metriky");
    const selectedSuffix =
      candidate.sourcePath === l2Diagnostics.sourcePath
        ? ` [${uiLanguage === "en" ? "used" : "použité"}]`
        : "";
    return `- ${candidate.sourcePath}: ${candidate.score}/${L2_DIAGNOSTIC_KEYS.length} (${metrics})${selectedSuffix}`;
  });

  const runtimeTooltipByLabel = {};
  const setRuntimeTooltip = (label, value, source, flow = []) => {
    runtimeTooltipByLabel[label] = {
      value,
      source,
      flow: Array.isArray(flow) ? flow.filter(Boolean) : [flow].filter(Boolean),
    };
  };

  setRuntimeTooltip("Event Type", selectedMarker?.marker_type ?? "n/a", "marker.marker_type");
  setRuntimeTooltip(
    "Time",
    selectedMarker?.timestamp ?? selectedMarker?.time ?? "n/a",
    "marker.timestamp / marker.time",
  );
  setRuntimeTooltip("Price", selectedMarker?.price ?? "n/a", "marker.price");
  setRuntimeTooltip("Side", selectedMarker?.side ?? "n/a", "marker.side");
  setRuntimeTooltip(
    "Strategy (Entry)",
    selectedMarker?.strategy ?? metadata?.strategy ?? "Unknown",
    selectedMarker?.strategy ? "marker.strategy" : "details.metadata.strategy",
  );
  setRuntimeTooltip(
    "Confidence",
    selectedMarker?.confidence ?? "n/a",
    "marker.confidence",
    uiLanguage === "en"
      ? "Displayed as percentage in UI."
      : "V UI sa zobrazuje ako percento.",
  );
  setRuntimeTooltip("Stop Loss", details?.stop_loss ?? "n/a", "details.stop_loss");
  setRuntimeTooltip("Take Profit", details?.take_profit ?? "n/a", "details.take_profit");
  setRuntimeTooltip("R:R Ratio", details?.risk_reward ?? "n/a", "details.risk_reward");
  setRuntimeTooltip("Exit Reason", details?.exit_reason ?? "n/a", "details.exit_reason");
  setRuntimeTooltip(
    "PnL",
    resolvePnlPct(details, details?.pnl_dollars ?? details?.pnl_usd),
    "details.pnl_pct (fallback: pnl_dollars/position_notional_usd, then account default)",
  );
  setRuntimeTooltip(
    "PnL $",
    details?.pnl_dollars ?? details?.pnl_usd ?? "n/a",
    "details.pnl_dollars / details.pnl_usd",
  );
  setRuntimeTooltip("Bars Held", details?.bars_held ?? "n/a", "details.bars_held");
  setRuntimeTooltip("Reasoning", details?.reasoning ?? "n/a", "details.reasoning");

  Object.entries(details?.costs || {}).forEach(([costKey, costValue]) => {
    setRuntimeTooltip(
      renderCostLabel(costKey),
      costValue,
      `details.costs.${costKey}`,
      uiLanguage === "en"
        ? "Included in net trade PnL."
        : "Táto položka je zahrnutá v net PnL obchodu.",
    );
  });

  const l2SourceFlowNotes = [
    `${tooltipLocaleText.chosen}: ${l2Diagnostics.sourcePath || "n/a"}`,
    `${tooltipLocaleText.l2Title}:`,
    ...l2CandidateFlowLines,
  ];
  setRuntimeTooltip(
    "Flow Score",
    l2Diagnostics.flowScore,
    l2Diagnostics.sourcePath,
    l2SourceFlowNotes,
  );
  setRuntimeTooltip(
    "Signed Aggression",
    l2Diagnostics.signedAggression,
    l2Diagnostics.sourcePath,
    l2SourceFlowNotes,
  );
  setRuntimeTooltip(
    "L2 Aggression Z",
    l2Diagnostics.l2AggressionZ,
    l2Diagnostics.sourcePath,
    l2SourceFlowNotes,
  );
  setRuntimeTooltip(
    "L2 Book Pressure Z",
    l2Diagnostics.l2BookPressureZ,
    l2Diagnostics.sourcePath,
    l2SourceFlowNotes,
  );
  setRuntimeTooltip(
    "Absorption Rate",
    l2Diagnostics.absorptionRate,
    l2Diagnostics.sourcePath,
    l2SourceFlowNotes,
  );
  setRuntimeTooltip(
    "Large Trader Activity",
    l2Diagnostics.largeTraderActivity,
    l2Diagnostics.sourcePath,
    l2SourceFlowNotes,
  );
  setRuntimeTooltip(
    "VWAP Execution Flow (L2 Diagnostics)",
    l2Diagnostics.vwapExecutionFlow,
    l2Diagnostics.sourcePath,
    [
      ...l2SourceFlowNotes,
      ...buildVwapFlowValueLines(
        l2Diagnostics.vwapExecutionFlow,
        l2Diagnostics.sourcePath || "n/a",
      ),
    ],
  );
  setRuntimeTooltip(
    "L2 Source",
    l2Diagnostics.sourcePath,
    "resolved in resolveL2Source()",
    l2SourceFlowNotes,
  );
  setRuntimeTooltip(
    "Sweep Detected",
    l2Diagnostics.sweepDetected,
    l2Diagnostics.sourcePath,
    l2SourceFlowNotes,
  );

  setRuntimeTooltip("Tracker", intradayLevels.enabled, "details.intraday_levels.enabled");
  setRuntimeTooltip(
    "Active / Tested / Broken",
    `${Number(intradayLevels.stats.active_levels || 0)} / ${Number(intradayLevels.stats.tested_levels || 0)} / ${Number(intradayLevels.stats.broken_levels || 0)}`,
    "details.intraday_levels.stats.*",
  );
  setRuntimeTooltip(
    "Bounce / Break Events",
    `${Number(intradayLevels.stats.bounce_events || 0)} / ${Number(intradayLevels.stats.break_events || 0)}`,
    "details.intraday_levels.stats.bounce_events / break_events",
  );
  setRuntimeTooltip(
    "POC",
    intradayLevels.volumeProfile.poc_price ?? "n/a",
    "details.intraday_levels.volume_profile.poc_price",
  );
  setRuntimeTooltip(
    "Value Area",
    intradayLevels.volumeProfile.value_area_low != null &&
      intradayLevels.volumeProfile.value_area_high != null
      ? `${intradayLevels.volumeProfile.value_area_low} - ${intradayLevels.volumeProfile.value_area_high}`
      : "n/a",
    "details.intraday_levels.volume_profile.value_area_low / value_area_high",
  );
  setRuntimeTooltip("Latest Event", intradayLevels.latestEvent ?? "n/a", "details.intraday_levels.latest_event");

  setRuntimeTooltip("Status", levelContext.payload?.passed, "details.level_context.passed");
  setRuntimeTooltip(
    "Strategy (Gate)",
    levelContext.payload?.strategy_key ?? "n/a",
    "details.level_context.strategy_key",
  );
  setRuntimeTooltip("Gate Reason", levelContext.payload?.reason ?? "n/a", "details.level_context.reason");
  setRuntimeTooltip(
    "Near Tested Levels (Gate)",
    levelContext.payload?.stats?.near_tested_levels_count ?? 0,
    "details.level_context.stats.near_tested_levels_count",
  );
  setRuntimeTooltip(
    "Value Area Position",
    levelContext.payload?.volume_profile?.value_area_position ?? "n/a",
    "details.level_context.volume_profile.value_area_position",
  );
  setRuntimeTooltip(
    "POC On Trade Side (Gate)",
    levelContext.payload?.volume_profile?.poc_on_trade_side,
    "details.level_context.volume_profile.poc_on_trade_side",
  );
  setRuntimeTooltip(
    "Room To Next Opposite Level",
    levelContext.payload?.room_to_next_opposite_level_pct ?? "n/a",
    "details.level_context.room_to_next_opposite_level_pct",
  );
  setRuntimeTooltip("Fail Reasons", levelContext.reasons, "details.level_context.reasons");

  setRuntimeTooltip(
    "First-Bar Stop Loss",
    entryQualityDiagnostics.payload?.is_first_bar_stop_loss,
    "details.entry_quality_diagnostics.is_first_bar_stop_loss",
  );
  setRuntimeTooltip(
    "Stop Distance",
    entryQualityDiagnostics.payload?.stop_distance_pct ?? "n/a",
    "details.entry_quality_diagnostics.stop_distance_pct",
  );
  setRuntimeTooltip(
    "VWAP Distance",
    entryQualityDiagnostics.payload?.vwap_distance_pct ?? "n/a",
    "details.entry_quality_diagnostics.vwap_distance_pct",
  );
  setRuntimeTooltip(
    "Confluence Score",
    entryQualityDiagnostics.payload?.near_confluence_score ?? "n/a",
    "details.entry_quality_diagnostics.near_confluence_score",
  );
  setRuntimeTooltip(
    "Near Tested Levels (Entry Timing)",
    entryQualityDiagnostics.payload?.near_tested_levels_count ?? "n/a",
    "details.entry_quality_diagnostics.near_tested_levels_count",
  );
  setRuntimeTooltip(
    "POC On Trade Side (Entry Timing)",
    entryQualityDiagnostics.payload?.poc_on_trade_side,
    "details.entry_quality_diagnostics.poc_on_trade_side",
  );
  setRuntimeTooltip("Diagnosis Tags", entryQualityDiagnostics.tags, "details.entry_quality_diagnostics.first_bar_stop_tags");

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
        ? (uiLanguage === "en"
          ? "TP stayed at original strategy target (no context override)."
          : "TP ostal na pôvodnom targete stratégie (bez context override).")
        : "",
      decisionLog.payload?.context_risk?.tp_reason
        ? (uiLanguage === "en"
          ? `Interpreted: ${renderReasonValue(decisionLog.payload.context_risk.tp_reason)}`
          : `Interpretované: ${renderReasonValue(decisionLog.payload.context_risk.tp_reason)}`)
        : "",
      ...(!decisionLog.payload?.context_risk?.tp_reason ? buildContextRiskMissingLines("tp_reason") : []),
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
      : (isRuntimeMissing(decisionLog.payload?.context_risk?.effective_rr)
        ? buildContextRiskMissingLines("effective_rr")
        : []),
  );
  setRuntimeTooltip(
    "Risk %",
    decisionLog.payload?.context_risk?.risk_pct ?? "n/a",
    contextRiskFieldSource("risk_pct"),
    [
      (details?.entry_price != null && details?.stop_loss != null)
        ? (
          uiLanguage === "en"
            ? `Formula: abs(entry (${formatTooltipRuntimeValue(details.entry_price)}) - SL (${formatTooltipRuntimeValue(details.stop_loss)})) / entry * 100`
            : `Vzorec: abs(entry (${formatTooltipRuntimeValue(details.entry_price)}) - SL (${formatTooltipRuntimeValue(details.stop_loss)})) / entry * 100`
        )
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
        ? (
          uiLanguage === "en"
            ? `Active: ${formatTooltipRuntimeValue(breakEvenPayload.active)}`
            : `Aktívne: ${formatTooltipRuntimeValue(breakEvenPayload.active)}`
        )
        : "",
      breakEvenPayload?.arm_bar_index != null
        ? (
          uiLanguage === "en"
            ? `Arm bar: ${formatTooltipRuntimeValue(breakEvenPayload.arm_bar_index)}`
            : `Arm bar: ${formatTooltipRuntimeValue(breakEvenPayload.arm_bar_index)}`
        )
        : "",
      breakEvenPayload?.move_bar_index != null
        ? (
          uiLanguage === "en"
            ? `Move bar: ${formatTooltipRuntimeValue(breakEvenPayload.move_bar_index)}`
            : `Move bar: ${formatTooltipRuntimeValue(breakEvenPayload.move_bar_index)}`
        )
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
        ? (
          uiLanguage === "en"
            ? `Raw token(s): ${breakEvenPayload.activation_reason}`
            : `Raw token(y): ${breakEvenPayload.activation_reason}`
        )
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
      ...(!breakEvenPayload?.activation_reason ? buildBreakEvenMissingLines("activation_reason") : []),
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
      ...(isObjectRecord(breakEvenPayload?.levels_proof) || isObjectRecord(breakEvenPayload?.l2_proof)
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
        ? (
          uiLanguage === "en"
            ? `Entry: ${formatTooltipRuntimeValue(breakEvenComputed.entry_price)}`
            : `Entry: ${formatTooltipRuntimeValue(breakEvenComputed.entry_price)}`
        )
        : "",
      breakEvenComputed?.total_costs_pct != null
        ? (
          uiLanguage === "en"
            ? `Total costs %: ${formatPctValue(breakEvenComputed.total_costs_pct, 5)}`
            : `Celkové costs %: ${formatPctValue(breakEvenComputed.total_costs_pct, 5)}`
        )
        : "",
      breakEvenBuffer?.selected_buffer_pct != null
        ? (
          uiLanguage === "en"
            ? `Selected buffer %: ${formatPctValue(breakEvenBuffer.selected_buffer_pct, 5)}`
            : `Zvolený buffer %: ${formatPctValue(breakEvenBuffer.selected_buffer_pct, 5)}`
        )
        : "",
      ...((breakEvenStopDisplayValue == null) ? buildBreakEvenMissingLines("computed_break_even") : []),
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

  return {
    details,
    metadata,
    l2Diagnostics,
    intradayLevels,
    levelContext,
    entryQualityDiagnostics,
    decisionLog,
    t,
    renderYesNo,
    renderEnabled,
    renderGateStatus,
    renderCostLabel,
    renderReasonValue,
    breakEvenPayload,
    renderBreakEvenTrigger,
    renderBreakEvenProof,
    breakEvenStopDisplayValue,
    breakEvenComputed,
    breakEvenBuffer,
    breakEvenAntiSpikeSummary,
    formatPctValue,
    tooltipLocaleText,
    baseTooltipFor,
    runtimeTooltipByLabel: runtimeTooltipByLabel as DecisionPanelTooltipRuntimeMap,
  };
};

export default function useDecisionPanelViewModel({
  selectedMarker,
  uiLanguage,
}: UseDecisionPanelViewModelParams) {
  return useMemo(
    () => buildDecisionPanelViewModel(selectedMarker, uiLanguage),
    [selectedMarker, uiLanguage],
  );
}
