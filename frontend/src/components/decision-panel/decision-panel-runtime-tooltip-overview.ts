import { resolvePnlPct } from "./decision-panel-utils";
import type {
  BuildDecisionPanelRuntimeTooltipsParams,
  RuntimeTooltipSetter,
} from "./decision-panel-runtime-tooltip-types";

export const applyPrimaryRuntimeTooltips = (
  params: BuildDecisionPanelRuntimeTooltipsParams,
  setRuntimeTooltip: RuntimeTooltipSetter,
) => {
  const { uiLanguage, selectedMarker, details, metadata, renderCostLabel } = params;

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
    uiLanguage === "en" ? "Displayed as percentage in UI." : "V UI sa zobrazuje ako percento.",
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
};

export const applyL2RuntimeTooltips = (
  params: BuildDecisionPanelRuntimeTooltipsParams,
  l2SourceFlowNotes: string[],
  setRuntimeTooltip: RuntimeTooltipSetter,
) => {
  const { l2Diagnostics, buildVwapFlowValueLines } = params;

  setRuntimeTooltip("Flow Score", l2Diagnostics.flowScore, l2Diagnostics.sourcePath, l2SourceFlowNotes);
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
};

export const applyIntradayLevelsRuntimeTooltips = (
  params: BuildDecisionPanelRuntimeTooltipsParams,
  setRuntimeTooltip: RuntimeTooltipSetter,
) => {
  const { intradayLevels } = params;

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
  setRuntimeTooltip(
    "Latest Event",
    intradayLevels.latestEvent ?? "n/a",
    "details.intraday_levels.latest_event",
  );
};

export const applyLevelContextRuntimeTooltips = (
  params: BuildDecisionPanelRuntimeTooltipsParams,
  setRuntimeTooltip: RuntimeTooltipSetter,
) => {
  const { levelContext } = params;

  setRuntimeTooltip("Status", levelContext.payload?.passed, "details.level_context.passed");
  setRuntimeTooltip(
    "Strategy (Gate)",
    levelContext.payload?.strategy_key ?? "n/a",
    "details.level_context.strategy_key",
  );
  setRuntimeTooltip(
    "Gate Reason",
    levelContext.payload?.reason ?? "n/a",
    "details.level_context.reason",
  );
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
};

export const applyEntryQualityRuntimeTooltips = (
  params: BuildDecisionPanelRuntimeTooltipsParams,
  setRuntimeTooltip: RuntimeTooltipSetter,
) => {
  const { entryQualityDiagnostics } = params;

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
  setRuntimeTooltip(
    "Diagnosis Tags",
    entryQualityDiagnostics.tags,
    "details.entry_quality_diagnostics.first_bar_stop_tags",
  );
};
