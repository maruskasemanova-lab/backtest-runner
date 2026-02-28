import {
  extractDecisionLogPayload,
  extractEntryQualityDiagnostics,
  extractIntradayLevels,
  extractL2Diagnostics,
  extractLevelContext,
  isObjectRecord,
  resolveBreakEven,
  resolveContextRisk,
  resolveRiskControls,
} from "./decision-panel-diagnostics";
import {
  BREAK_EVEN_TRIGGER_TRANSLATIONS,
  COST_LABEL_BY_KEY,
  DECISION_LABELS,
  DECISION_REASON_TRANSLATIONS,
} from "./decision-panel-copy";
import {
  formatTooltipRuntimeValue,
  toFiniteNumber,
} from "./decision-panel-utils";
import type { DecisionPanelMarkerLike } from "./decision-panel-types";
import { buildDecisionPanelRuntimeTooltips } from "./decision-panel-runtime-tooltips";

export type UseDecisionPanelViewModelParams = {
  selectedMarker: DecisionPanelMarkerLike | null;
  uiLanguage: string;
};

export const buildDecisionPanelViewModel = (
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
  const {
    tooltipLocaleText,
    baseTooltipFor,
    runtimeTooltipByLabel,
  } = buildDecisionPanelRuntimeTooltips({
    uiLanguage,
    selectedMarker,
    details,
    metadata,
    l2Diagnostics,
    intradayLevels,
    levelContext,
    entryQualityDiagnostics,
    decisionLog,
    renderCostLabel,
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
  });
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
    runtimeTooltipByLabel,
  };
};
