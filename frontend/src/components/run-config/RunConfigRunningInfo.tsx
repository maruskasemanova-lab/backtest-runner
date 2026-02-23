import { formatStartModeLabel, START_MODE_DAY_ISOLATED_AUDIT } from "./runConfigHelpers";

type RunConfigRunningInfoProps = {
  config: Record<string, any>;
  effectiveSnapshot: Record<string, any>;
};

export default function RunConfigRunningInfo({
  config,
  effectiveSnapshot,
}: RunConfigRunningInfoProps) {
  const {
    hasEffectiveConfig,
    requestedStartMode,
    activeRiskPerTradePct,
    activeMaxPositionNotionalPct,
    activeMaxFillParticipationRate,
    activeMinFillRatio,
    activeTimeExitBars,
    activeAdverseFlowEnabled,
    activeAdverseFlowThreshold,
    activeAdverseFlowMinHoldBars,
    activeStopLossMode,
    activeFixedStopLossPct,
    activeTrailingActivationPct,
    activeTrailingStopPct,
    activeGlobalExitRrRatio,
    activeGlobalRiskAtrStopMultiplier,
    activeGlobalRiskVolumeStopPct,
    activeGlobalRiskMinStopLossPct,
    activeBreakEvenBufferPct,
    activeBreakEvenMinHoldBars,
    activeTrailingInChoppy,
    activeStartMode,
    activeStartModeLabel,
    activeColdStartEachDay,
    activeComparableMode,
    activeAosOptimizationsOnStart,
    activeOrchestratorResetScope,
    activeStrategySelectionMode,
    activeMaxActiveStrategies,
    activeIntradayLevelsEnabled,
    activeIntradayLevelsSwingLeftBars,
    activeIntradayLevelsSwingRightBars,
    activeIntradayLevelsTestTolerancePct,
    activeIntradayLevelsBreakTolerancePct,
    activeIntradayLevelsBreakoutVolumeLookback,
    activeIntradayLevelsBreakoutVolumeMultiplier,
    activeIntradayLevelsVolumeProfileBinSizePct,
    activeIntradayLevelsValueAreaPct,
    activeIntradayLevelsEntryQualityEnabled,
    activeIntradayLevelsMinLevelsForContext,
    activeIntradayLevelsEntryTolerancePct,
    activeIntradayLevelsBreakCooldownBars,
    activeIntradayLevelsRotationMaxTests,
    activeIntradayLevelsRotationVolumeMaxRatio,
    activeIntradayLevelsRecentBounceLookbackBars,
    activeIntradayLevelsRequireRecentBounceForMeanReversion,
    activeIntradayLevelsMomentumBreakMaxAgeBars,
    activeIntradayLevelsMomentumMinRoomPct,
    activeIntradayLevelsMomentumMinBrokenRatio,
    activeIntradayLevelsMinConfluenceScore,
    activeIntradayLevelsMemoryEnabled,
    activeIntradayLevelsMemoryMinTests,
    activeIntradayLevelsMemoryMaxAgeDays,
    activeIntradayLevelsMemoryDecayAfterDays,
    activeIntradayLevelsMemoryDecayWeight,
    activeIntradayLevelsMemoryMaxLevels,
    activeIntradayLevelsOpeningRangeEnabled,
    activeIntradayLevelsOpeningRangeMinutes,
    activeIntradayLevelsOpeningRangeBreakTolerancePct,
    activeIntradayLevelsPocMigrationEnabled,
    activeIntradayLevelsPocMigrationIntervalBars,
    activeIntradayLevelsPocMigrationTrendThresholdPct,
    activeIntradayLevelsPocMigrationRangeThresholdPct,
    activeIntradayLevelsCompositeProfileEnabled,
    activeIntradayLevelsCompositeProfileDays,
    activeIntradayLevelsCompositeProfileCurrentDayWeight,
    activeIntradayLevelsSpikeDetectionEnabled,
    activeIntradayLevelsSpikeMinWickRatio,
    activeIntradayLevelsPriorDayAnchorsEnabled,
    activeIntradayLevelsGapAnalysisEnabled,
    activeIntradayLevelsGapMinPct,
    activeIntradayLevelsGapMomentumThresholdPct,
    activeIntradayLevelsRvolFilterEnabled,
    activeIntradayLevelsRvolLookbackBars,
    activeIntradayLevelsRvolMinThreshold,
    activeIntradayLevelsRvolStrongThreshold,
    activeIntradayLevelsAdaptiveWindowEnabled,
    activeIntradayLevelsAdaptiveWindowMinBars,
    activeIntradayLevelsAdaptiveWindowRvolThreshold,
    activeIntradayLevelsAdaptiveWindowAtrRatioMax,
    activeIntradayLevelsMicroConfirmationEnabled,
    activeIntradayLevelsMicroConfirmationBars,
    activeIntradayLevelsConfluenceSizingEnabled,
    activeContextAwareRiskEnabled,
    activeContextRiskSlBufferPct,
    activeContextRiskMinRoomPct,
    activeContextRiskMinEffectiveRr,
    activeContextRiskTrailingTightenZone,
    activeContextRiskTrailingTightenFactor,
    activeContextRiskLevelTrailEnabled,
    activeContextRiskMaxAnchorSearchPct,
    activeContextRiskMinLevelTestsForSl,
    activeMomentumDiversificationRaw,
    activeMomentumDiversificationApplied,
    activeMomentumDiversificationSource,
    effectiveUnifiedProfileId,
  } = effectiveSnapshot;

  return (
      <div className="card">
        <div className="card-header">
          <span className="card-title">Run Info</span>
        </div>
        <div className="card-body">
          <div className="form-group">
            <label>Run ID</label>
            <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>{config.run_id}</div>
          </div>
          <div className="form-group">
            <label>Ticker</label>
            <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>{config.ticker}</div>
          </div>
          <div className="form-group">
            <label>Date Range</label>
            <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
              {config.date_from && config.date_to
                ? `${config.date_from} → ${config.date_to}`
                : config.date}
            </div>
          </div>
          <div className="form-group">
            <label className="field-row" htmlFor="run_info_include_extended_hours">
              <span>Include Pre/Post-Market Bars</span>
              <input
                id="run_info_include_extended_hours"
                type="checkbox"
                checked={!!config.include_extended_hours}
                disabled
                readOnly
              />
            </label>
            <div style={{ color: "var(--text-muted)", fontSize: "0.78rem", marginTop: "4px" }}>
              This value is set before run start in Run Config.
            </div>
          </div>
          <div className="form-group">
            <label>Account Size</label>
            <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
              ${Number(config.account_size_usd || 0).toLocaleString()}
            </div>
          </div>
          <div className="form-group">
            <label>Risk / Trade</label>
            <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
              {activeRiskPerTradePct.toFixed(2)}%
            </div>
          </div>
          <div className="form-group">
            <label>Max Position Notional</label>
            <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
              {activeMaxPositionNotionalPct.toFixed(2)}%
            </div>
          </div>
          <div className="form-group">
            <label>Max Fill Participation</label>
            <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
              {activeMaxFillParticipationRate.toFixed(2)}
            </div>
          </div>
          <div className="form-group">
            <label>Min Fill Ratio</label>
            <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
              {activeMinFillRatio.toFixed(2)}
            </div>
          </div>
          <div className="form-group">
            <label>Global Trailing Stop (%)</label>
            <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
              {activeTrailingStopPct.toFixed(2)}%
            </div>
          </div>
          <div className="form-group">
            <label>Global Exit RR</label>
            <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
              {activeGlobalExitRrRatio.toFixed(2)}
            </div>
          </div>
          <div className="form-group">
            <label>Global Risk ATR Multiplier</label>
            <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
              {activeGlobalRiskAtrStopMultiplier.toFixed(2)}
            </div>
          </div>
          <div className="form-group">
            <label>Global Risk Volume Stop (%)</label>
            <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
              {activeGlobalRiskVolumeStopPct.toFixed(2)}%
            </div>
          </div>
          <div className="form-group">
            <label>Global Risk Min Stop (%)</label>
            <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
              {activeGlobalRiskMinStopLossPct.toFixed(2)}%
            </div>
          </div>
          <div className="form-group">
            <label>Stop-Loss Mode</label>
            <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
              {activeStopLossMode}
              {(activeStopLossMode === "fixed" || activeStopLossMode === "capped") && (
                <> ({activeFixedStopLossPct.toFixed(2)}%)</>
              )}
            </div>
          </div>
          <div className="form-group">
            <label>Break-even Activation</label>
            <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
              {activeTrailingActivationPct.toFixed(2)}% MFE, hold {Math.max(1, Math.trunc(activeBreakEvenMinHoldBars || 1))} bars
            </div>
          </div>
          <div className="form-group">
            <label>Break-even Buffer</label>
            <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
              {activeBreakEvenBufferPct.toFixed(2)}%
            </div>
          </div>
          <div className="form-group">
            <label>Trailing In Choppy</label>
            <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
              {activeTrailingInChoppy ? "Enabled" : "Disabled"}
            </div>
          </div>
          <div className="form-group">
            <label>Time Exit</label>
            <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
              {activeTimeExitBars} bars
            </div>
          </div>
          <div className="form-group">
            <label>Adverse Flow Exit</label>
            <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
              {activeAdverseFlowEnabled ? "Enabled" : "Disabled"}
            </div>
          </div>
          {activeAdverseFlowEnabled && (
            <>
              <div className="form-group">
                <label>Adverse Flow Threshold</label>
                <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
                  {activeAdverseFlowThreshold.toFixed(2)}
                </div>
              </div>
              <div className="form-group">
                <label>Adverse Flow Min Hold</label>
                <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
                  {activeAdverseFlowMinHoldBars} bars
                </div>
              </div>
            </>
          )}
          <div className="form-group">
            <label>L2 Confirmation</label>
            <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
              {config.l2_confirm_enabled ? "Enabled" : "Disabled"}
            </div>
          </div>
          <div className="form-group">
            <label>Intraday Levels Tracker</label>
            <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
              {activeIntradayLevelsEnabled ? "Enabled" : "Disabled"}
            </div>
          </div>
          {activeIntradayLevelsEnabled && (
            <>
              <div className="form-group">
                <label>Swing Window</label>
                <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
                  left {activeIntradayLevelsSwingLeftBars}, right {activeIntradayLevelsSwingRightBars}
                </div>
              </div>
              <div className="form-group">
                <label>Test / Break Tolerance</label>
                <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
                  {activeIntradayLevelsTestTolerancePct.toFixed(3)}% / {activeIntradayLevelsBreakTolerancePct.toFixed(3)}%
                </div>
              </div>
              <div className="form-group">
                <label>Breakout Volume</label>
                <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
                  lookback {activeIntradayLevelsBreakoutVolumeLookback} bars, x{activeIntradayLevelsBreakoutVolumeMultiplier.toFixed(2)}
                </div>
              </div>
              <div className="form-group">
                <label>Volume Profile</label>
                <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
                  bin {activeIntradayLevelsVolumeProfileBinSizePct.toFixed(3)}%, value area {activeIntradayLevelsValueAreaPct.toFixed(2)}
                </div>
              </div>
              <div className="form-group">
                <label>Entry Quality Gate</label>
                <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
                  {activeIntradayLevelsEntryQualityEnabled ? "Enabled" : "Disabled"}
                </div>
              </div>
              {activeIntradayLevelsEntryQualityEnabled && (
                <>
                  <div className="form-group">
                    <label>Context Threshold</label>
                    <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
                      min levels {activeIntradayLevelsMinLevelsForContext}, tolerance {activeIntradayLevelsEntryTolerancePct.toFixed(3)}%
                    </div>
                  </div>
                  <div className="form-group">
                    <label>Break Cooldown</label>
                    <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
                      {activeIntradayLevelsBreakCooldownBars} bars
                    </div>
                  </div>
                  <div className="form-group">
                    <label>Rotation / MR Guards</label>
                    <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
                      max tests {activeIntradayLevelsRotationMaxTests}, volume ratio ≤ {activeIntradayLevelsRotationVolumeMaxRatio.toFixed(2)}, bounce lookback {activeIntradayLevelsRecentBounceLookbackBars}
                      {activeIntradayLevelsRequireRecentBounceForMeanReversion ? " (bounce required)" : ""}
                    </div>
                  </div>
                  <div className="form-group">
                    <label>Momentum Guards</label>
                    <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
                      break age ≤ {activeIntradayLevelsMomentumBreakMaxAgeBars} bars, room ≥ {activeIntradayLevelsMomentumMinRoomPct.toFixed(2)}%, broken ratio ≥ {activeIntradayLevelsMomentumMinBrokenRatio.toFixed(2)}
                    </div>
                  </div>
                  <div className="form-group">
                    <label>Confluence Score</label>
                    <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
                      min score {activeIntradayLevelsMinConfluenceScore}
                    </div>
                  </div>
                  <div className="form-group">
                    <label>Level Memory</label>
                    <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
                      {activeIntradayLevelsMemoryEnabled
                        ? `enabled, tests ≥ ${activeIntradayLevelsMemoryMinTests}, age ≤ ${activeIntradayLevelsMemoryMaxAgeDays}d, decay after ${activeIntradayLevelsMemoryDecayAfterDays}d (x${activeIntradayLevelsMemoryDecayWeight.toFixed(2)}), max ${activeIntradayLevelsMemoryMaxLevels}`
                        : "disabled"}
                    </div>
                  </div>
                  <div className="form-group">
                    <label>Opening Range</label>
                    <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
                      {activeIntradayLevelsOpeningRangeEnabled
                        ? `enabled, ${activeIntradayLevelsOpeningRangeMinutes} min, break tol ${activeIntradayLevelsOpeningRangeBreakTolerancePct.toFixed(3)}%`
                        : "disabled"}
                    </div>
                  </div>
                  <div className="form-group">
                    <label>POC Migration</label>
                    <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
                      {activeIntradayLevelsPocMigrationEnabled
                        ? `enabled, interval ${activeIntradayLevelsPocMigrationIntervalBars} bars, trend ${activeIntradayLevelsPocMigrationTrendThresholdPct.toFixed(2)}%, range ${activeIntradayLevelsPocMigrationRangeThresholdPct.toFixed(2)}%`
                        : "disabled"}
                    </div>
                  </div>
                  <div className="form-group">
                    <label>Composite VP</label>
                    <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
                      {activeIntradayLevelsCompositeProfileEnabled
                        ? `enabled, ${activeIntradayLevelsCompositeProfileDays} days, current-day weight ${activeIntradayLevelsCompositeProfileCurrentDayWeight.toFixed(2)}`
                        : "disabled"}
                    </div>
                  </div>
                </>
              )}
              <div className="form-group">
                <label>Spike Levels</label>
                <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
                  {activeIntradayLevelsSpikeDetectionEnabled
                    ? `enabled, wick ratio ≥ ${activeIntradayLevelsSpikeMinWickRatio.toFixed(2)}`
                    : "disabled"}
                </div>
              </div>
              <div className="form-group">
                <label>Prior-Day Anchors</label>
                <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
                  {activeIntradayLevelsPriorDayAnchorsEnabled ? "enabled" : "disabled"}
                </div>
              </div>
              <div className="form-group">
                <label>Gap Analysis</label>
                <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
                  {activeIntradayLevelsGapAnalysisEnabled
                    ? `enabled, min ${activeIntradayLevelsGapMinPct.toFixed(2)}%, momentum threshold ${activeIntradayLevelsGapMomentumThresholdPct.toFixed(2)}%`
                    : "disabled"}
                </div>
              </div>
              <div className="form-group">
                <label>RVOL Filter</label>
                <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
                  {activeIntradayLevelsRvolFilterEnabled
                    ? `enabled, lookback ${activeIntradayLevelsRvolLookbackBars}, min ${activeIntradayLevelsRvolMinThreshold.toFixed(2)}, strong ${activeIntradayLevelsRvolStrongThreshold.toFixed(2)}`
                    : "disabled"}
                </div>
              </div>
              <div className="form-group">
                <label>Adaptive Window</label>
                <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
                  {activeIntradayLevelsAdaptiveWindowEnabled
                    ? `enabled, min bars ${activeIntradayLevelsAdaptiveWindowMinBars}, RVOL ≥ ${activeIntradayLevelsAdaptiveWindowRvolThreshold.toFixed(2)}, ATR ratio ≤ ${activeIntradayLevelsAdaptiveWindowAtrRatioMax.toFixed(2)}`
                    : "disabled"}
                </div>
              </div>
              <div className="form-group">
                <label>Micro Confirmation</label>
                <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
                  {activeIntradayLevelsMicroConfirmationEnabled
                    ? `enabled, ${activeIntradayLevelsMicroConfirmationBars} bars`
                    : "disabled"}
                </div>
              </div>
              <div className="form-group">
                <label>Confluence Sizing</label>
                <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
                  {activeIntradayLevelsConfluenceSizingEnabled ? "enabled" : "disabled"}
                </div>
              </div>
            </>
          )}
          <div className="form-group">
            <label>Context-Aware Risk</label>
            <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
              {activeContextAwareRiskEnabled
                ? `enabled, SL buffer ${activeContextRiskSlBufferPct.toFixed(2)}%, min room ${activeContextRiskMinRoomPct.toFixed(2)}%, min RR ${activeContextRiskMinEffectiveRr.toFixed(2)}, tighten zone ${activeContextRiskTrailingTightenZone.toFixed(2)}, tighten factor ${activeContextRiskTrailingTightenFactor.toFixed(2)}, max anchor ${activeContextRiskMaxAnchorSearchPct.toFixed(2)}%, min tests ${activeContextRiskMinLevelTestsForSl}, level-trail ${activeContextRiskLevelTrailEnabled ? "on" : "off"}`
                : "disabled"}
            </div>
          </div>
          <div className="form-group">
            <label>Strategy Selection</label>
            <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
              {activeStrategySelectionMode === "all_enabled" ? "all enabled strategies" : "adaptive top-N"}
              {activeStrategySelectionMode !== "all_enabled" && <> ({activeMaxActiveStrategies})</>}
            </div>
          </div>
          <div className="form-group">
            <label>Unified Profile</label>
            <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
              {effectiveUnifiedProfileId || "none (using direct AOS settings)"}
            </div>
          </div>
          <div className="form-group">
            <label>Momentum Diversification</label>
            <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
              {activeMomentumDiversificationApplied
                ? `Applied (${activeMomentumDiversificationSource})`
                : "Not applied"}
            </div>
          </div>
          {activeMomentumDiversificationApplied && (
            <>
              <div className="form-group">
                <label>Momentum Flow Filter</label>
                <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
                  min_flow_score {Number(activeMomentumDiversificationRaw.min_flow_score ?? 0).toFixed(2)}, directional
                  {" "}
                  {Number(activeMomentumDiversificationRaw.min_directional_consistency ?? 0).toFixed(2)}, signed_aggr
                  {" "}
                  {Number(activeMomentumDiversificationRaw.min_signed_aggression ?? 0).toFixed(2)}
                </div>
              </div>
              <div className="form-group">
                <label>Momentum Route + Fail-Fast</label>
                <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
                  route {activeMomentumDiversificationRaw.route_enabled ? "on" : "off"}, fail-fast
                  {" "}
                  {activeMomentumDiversificationRaw.fail_fast_exit_enabled ? "on" : "off"}
                  {activeMomentumDiversificationRaw.fail_fast_exit_enabled && (
                    <> ({Math.max(1, Math.trunc(Number(activeMomentumDiversificationRaw.fail_fast_max_bars ?? 1)))} bars)</>
                  )}
                </div>
              </div>
            </>
          )}
          <div className="form-group">
            <label>Start Mode</label>
            <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
              {hasEffectiveConfig ? activeStartModeLabel : formatStartModeLabel(requestedStartMode)}
            </div>
          </div>
          <div className="form-group">
            <label>Reset Scope</label>
            <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
              {activeOrchestratorResetScope === "session"
                ? "Session-only (fast)"
                : (activeOrchestratorResetScope === "learning" ? "Learning-only" : "All (cold)")}
            </div>
          </div>
          <div className="form-group">
            <label>AOS Sync On Start</label>
            <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
              {activeAosOptimizationsOnStart ? "Enabled" : "Disabled (fast)"}
            </div>
          </div>
          <div className="form-group">
            <label>Checkpoint Auto-save</label>
            <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
              {config.auto_save_checkpoint ? "Enabled" : "Disabled"}
            </div>
          </div>
          <div className="form-group">
            <label>Cold Start Each Day</label>
            <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
              {(activeColdStartEachDay || activeComparableMode) ? "Enabled" : "Disabled"}
            </div>
          </div>
          {activeStartMode === START_MODE_DAY_ISOLATED_AUDIT && (
            <div className="form-group">
              <label>Comparable Mode</label>
              <div style={{ color: "var(--text-primary)", fontSize: "0.9rem" }}>
                Enabled (managed by Day-Isolated Audit mode)
              </div>
            </div>
          )}
          <div style={{ color: "var(--text-muted)", fontSize: "0.78rem", marginTop: "4px" }}>
            {hasEffectiveConfig
              ? "Values shown are effective execution settings returned by backend."
              : "Values shown are requested settings (backend effective settings unavailable)."}
          </div>
        </div>
      </div>
  );
}
