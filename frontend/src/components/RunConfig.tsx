import React from "react";
import { StartModeSettings } from "./run-config/StartModeSettings";
import {
  useRunConfigState,
  UseRunConfigStateProps,
} from "./run-config/useRunConfigState";
import RunConfigRunningInfo from "./run-config/RunConfigRunningInfo";
import { UnifiedConfigDialog } from "./unified-config/UnifiedConfigDialog";
import {
  ACTIVE_UNIFIED_PROFILE_SENTINEL,
  formatUnifiedProfileLabel,
  SHOW_RUN_CONFIG_ADVANCED_EXECUTION_CONTROLS,
} from "./run-config/runConfigHelpers";

export default function RunConfig(props: UseRunConfigStateProps) {
  const state = useRunConfigState(props);
  const [showFullscreenConfig, setShowFullscreenConfig] = React.useState(false);
  const unifiedProfiles = React.useMemo(
    () => (Array.isArray(state.unifiedProfiles) ? state.unifiedProfiles : []),
    [state.unifiedProfiles],
  );
  const activeUnifiedProfile = React.useMemo(() => {
    const activeProfileId = String(state.activeUnifiedProfileId || "").trim();
    if (!activeProfileId) return null;
    return (
      unifiedProfiles.find(
        (profile: any) =>
          String(profile?.profile_id || "").trim() === activeProfileId,
      ) || null
    );
  }, [state.activeUnifiedProfileId, unifiedProfiles]);
  const activeUnifiedProfileOptionLabel = React.useMemo(() => {
    if (state.unifiedProfilesLoading) return "Loading available profiles...";
    const activeProfileId = String(state.activeUnifiedProfileId || "").trim();
    if (!activeProfileId) return "Use active unified profile (none)";
    const activeProfileName = String(
      activeUnifiedProfile?.profile_name || "",
    ).trim();
    const labelToken = activeProfileName || activeProfileId;
    return `Use active unified profile (${labelToken})`;
  }, [
    activeUnifiedProfile,
    state.activeUnifiedProfileId,
    state.unifiedProfilesLoading,
  ]);
  const resolvedUnifiedProfileId = React.useMemo(() => {
    const selectedProfileId = String(
      state.selectedUnifiedProfileId || "",
    ).trim();
    if (
      selectedProfileId &&
      selectedProfileId !== ACTIVE_UNIFIED_PROFILE_SENTINEL
    ) {
      return selectedProfileId;
    }
    const activeProfileId = String(state.activeUnifiedProfileId || "").trim();
    if (activeProfileId) return activeProfileId;
    return String(
      state.effectiveSnapshot?.effectiveUnifiedProfileId || "",
    ).trim();
  }, [
    state.activeUnifiedProfileId,
    state.effectiveSnapshot?.effectiveUnifiedProfileId,
    state.selectedUnifiedProfileId,
  ]);
  const resolvedUnifiedProfile = React.useMemo(() => {
    if (!resolvedUnifiedProfileId) return null;
    return (
      unifiedProfiles.find(
        (profile: any) =>
          String(profile?.profile_id || "").trim() === resolvedUnifiedProfileId,
      ) || null
    );
  }, [resolvedUnifiedProfileId, unifiedProfiles]);
  const resolvedUnifiedProfileName = React.useMemo(() => {
    const explicitName = String(
      resolvedUnifiedProfile?.profile_name || "",
    ).trim();
    if (explicitName) return explicitName;
    return resolvedUnifiedProfileId;
  }, [resolvedUnifiedProfile, resolvedUnifiedProfileId]);

  if (props.isRunning) {
    return (
      <RunConfigRunningInfo
        config={state.config}
        effectiveSnapshot={state.effectiveSnapshot}
      />
    );
  }

  return (
    <div className="card">
      <div className="card-header tw-flex tw-justify-between tw-items-center">
        <span className="card-title">New Backtest Run</span>
        <button
          type="button"
          className="btn btn-secondary tw-btn-compact-xs"
          onClick={() => setShowFullscreenConfig(true)}
        >
          View Full Config
        </button>
      </div>
      <div className="card-body">
        <form
          className="run-config-form"
          onSubmit={
            state.showDateRangeControls || state.showStartControls
              ? state.handleSubmit
              : (e) => e.preventDefault()
          }
        >
          {state.showDateRangeControls && (
            <div className="form-group">
              <label htmlFor="run_id">Run ID</label>
              <input
                id="run_id"
                type="text"
                value={state.config.run_id ?? ""}
                onChange={(e) => state.handleChange("run_id", e.target.value)}
                required
              />
            </div>
          )}
          {state.showDateRangeControls && (
            <div className="form-group">
              <label htmlFor="active_run_select">
                Running Processes
                <span className="run-config-label-meta">
                  {` (${state.runningRunOptions.length})`}
                </span>
              </label>
              <select
                id="active_run_select"
                value={String(props.activeRunKey || "")}
                onChange={(e) => {
                  const targetRunKey = String(e.target.value || "");
                  if (!targetRunKey) return;
                  const selected = state.runningRunOptions.find(
                    (row) => String(row.run_key || "") === targetRunKey,
                  );
                  if (selected) {
                    state.hydrateConfigFromAttachedRun(selected);
                    state.markHydratedAttachedRunKey(targetRunKey);
                  }
                  if (typeof props.onAttachRun === "function") {
                    props.onAttachRun(targetRunKey);
                  }
                }}
              >
                <option value="">Select running run...</option>
                {state.runningRunOptions.map((row) => {
                  const runKey = String(row.run_key || "");
                  const runId = String(row.run_id || "");
                  const ticker = String(row.ticker || "").toUpperCase();
                  const date = String(row.date || "");
                  const phase = String(row.phase || "UNKNOWN");
                  const bars = Number(row.current_bar_index || 0);
                  const total = Number(row.total_bars || 0);
                  const progress = Number(row.progress_pct || 0);
                  const statusLabel = row.is_running
                    ? "RUNNING"
                    : row.is_paused
                      ? "PAUSED"
                      : phase;
                  return (
                    <option key={runKey} value={runKey}>
                      {`${runId} | ${ticker} | ${date} | ${statusLabel} | ${bars}/${total} (${progress.toFixed(1)}%)`}
                    </option>
                  );
                })}
              </select>
              <div className="ui-form-help ui-mt-xs">
                Pick a running/paused run to attach the UI to it.
              </div>
              <button
                type="button"
                className="btn btn-danger tw-btn-compact mt-2"
                onClick={state.handleKillSelectedRun}
                disabled={!props.activeRunKey || state.killRunLoading}
              >
                {state.killRunLoading
                  ? "Killing..."
                  : "Kill + Delete Selected Run"}
              </button>
            </div>
          )}
          {state.showDateRangeControls && (
            <div className="form-group">
              <label htmlFor="ticker">
                Ticker
                <div className="inline-toggle">
                  <span>L2 Only</span>
                  <input
                    type="checkbox"
                    checked={state.config.l2_only || false}
                    onChange={(e) => {
                      const checked = e.target.checked;
                      if (checked && state.availableData?.l2_tickers) {
                        const isCurrentTickerL2 =
                          state.availableData.l2_tickers.includes(
                            state.config.ticker,
                          );
                        if (
                          !isCurrentTickerL2 &&
                          state.availableData.l2_tickers.length > 0
                        ) {
                          state.handleTickerChange(
                            state.availableData.l2_tickers[0],
                          );
                        }
                      }
                      state.handleChange("l2_only", checked);
                    }}
                  />
                </div>
              </label>
              {state.availableData?.tickers ? (
                <select
                  id="ticker"
                  value={state.config.ticker}
                  onChange={(e) => state.handleTickerChange(e.target.value)}
                  required
                >
                  {(() => {
                    const filteredTickers = state.availableData.tickers.filter(
                      (t: string) =>
                        !state.config.l2_only ||
                        state.availableData?.l2_tickers?.includes(t),
                    );
                    const currentTicker = String(state.config.ticker || "")
                      .trim()
                      .toUpperCase();
                    const tickerOptions =
                      currentTicker && !filteredTickers.includes(currentTicker)
                        ? [currentTicker, ...filteredTickers]
                        : filteredTickers;
                    return tickerOptions.map((t: string, idx: number) => (
                      <option key={`${t}-${idx}`} value={t}>
                        {t}
                      </option>
                    ));
                  })()}
                </select>
              ) : (
                <input
                  id="ticker"
                  type="text"
                  value={state.config.ticker}
                  onChange={(e) =>
                    state.handleTickerChange(e.target.value.toUpperCase())
                  }
                  placeholder="Loading..."
                  required
                />
              )}
              {state.availableDataError ? (
                <div className="tw-message-error">
                  {state.availableDataError}
                </div>
              ) : null}
            </div>
          )}

          {state.showDateRangeControls && (
            <>
              <div className="form-group">
                <label htmlFor="date_from">
                  Date From
                  {state.dateRange.min && state.dateRange.max && (
                    <span className="run-config-label-meta">
                      {` (${state.dateRange.min} to ${state.dateRange.max})`}
                    </span>
                  )}
                </label>
                <input
                  id="date_from"
                  type="date"
                  value={state.config.date_from}
                  min={state.dateRange.min || undefined}
                  max={state.dateRange.max || undefined}
                  onChange={(e) => state.handleDateFromChange(e.target.value)}
                  required
                />
              </div>

              <div className="form-group">
                <label htmlFor="date_to">Date To</label>
                <input
                  id="date_to"
                  type="date"
                  value={state.config.date_to}
                  min={state.dateRange.min || undefined}
                  max={state.dateRange.max || undefined}
                  onChange={(e) => state.handleDateToChange(e.target.value)}
                  required
                />
                {state.config.l2_only &&
                  state.dateRange.l2_min &&
                  state.dateRange.l2_max && (
                    <div className="ui-form-help ui-mt-xs">
                      {`L2 coverage: ${state.dateRange.l2_min} to ${state.dateRange.l2_max}`}
                    </div>
                  )}
              </div>
            </>
          )}

          {state.showProfileControls && (
            <div id="unified_profile_section" className="form-group">
              <label htmlFor="aos_unified_profile">Available Profiles</label>
              <select
                id="aos_unified_profile"
                value={state.selectedUnifiedProfileId}
                onChange={state.handleUnifiedProfileSelectionChange}
                disabled={
                  state.unifiedProfilesLoading ||
                  state.unifiedProfileSwitching ||
                  !state.config.ticker
                }
              >
                <option value={ACTIVE_UNIFIED_PROFILE_SENTINEL}>
                  {activeUnifiedProfileOptionLabel}
                </option>
                {unifiedProfiles
                  .filter((profile: any) =>
                    String(profile?.profile_id || "").trim(),
                  )
                  .map((profile: any, idx: number) => {
                    const profileId = String(profile?.profile_id || "").trim();
                    return (
                      <option
                        key={profileId || `unified-${idx}`}
                        value={profileId}
                      >
                        {formatUnifiedProfileLabel(profile)}
                      </option>
                    );
                  })}
              </select>
              <div className="ui-actions ui-mt-sm">
                <button
                  type="button"
                  className="btn btn-secondary tw-btn-compact"
                  onClick={state.handleReloadAosAndProfiles}
                  disabled={
                    state.unifiedProfilesLoading ||
                    state.unifiedProfileSwitching ||
                    !state.config.ticker
                  }
                >
                  {state.unifiedProfilesLoading
                    ? "Refreshing..."
                    : "Refresh Profiles"}
                </button>
                <button
                  type="button"
                  className="btn btn-primary tw-btn-compact"
                  onClick={() => setShowFullscreenConfig(true)}
                  disabled={
                    state.unifiedProfilesLoading ||
                    state.unifiedProfileSwitching ||
                    !state.config.ticker
                  }
                >
                  Zobraziť konfiguráciu
                </button>
              </div>
            </div>
          )}

          {state.showStartControls && (
            <StartModeSettings
              config={state.config}
              handleChange={state.handleChange}
              fetchCheckpoints={state.fetchCheckpoints}
              checkpointLoading={state.checkpointLoading}
              selectedStartMode={state.selectedStartMode}
              selectedStartModeOption={state.selectedStartModeOption}
              startModeRuntime={state.startModeRuntime}
              checkpointCatalog={state.checkpointCatalog}
              handleSaveCheckpointNow={state.handleSaveCheckpointNow}
              checkpointSaving={state.checkpointSaving}
              checkpointMessage={state.checkpointMessage}
              formatCheckpointLabel={state.formatCheckpointLabel}
              error={state.error}
              loading={state.loading}
              aosLoading={state.aosLoading}
              unifiedProfilesLoading={state.unifiedProfilesLoading}
              loadingElapsedSec={state.loadingElapsedSec}
              handleFlushRunCache={state.handleFlushRunCache}
              cacheFlushLoading={state.cacheFlushLoading}
              cacheFlushMessage={state.cacheFlushMessage}
              prewarmStatus={state.prewarmStatus}
              startTiming={state.startTiming}
            />
          )}
        </form>
      </div>

      <UnifiedConfigDialog
        isOpen={showFullscreenConfig}
        onClose={() => setShowFullscreenConfig(false)}
        config={state.config}
        handleChange={state.handleChange}
        momentumSleeves={state.momentumSleeves}
        onMomentumSleeveChange={state.handleMomentumSleeveChange}
        onAddMomentumSleeve={state.handleAddMomentumSleeve}
        onRemoveMomentumSleeve={state.handleRemoveMomentumSleeve}
        strategyApiUrl={
          state.config.strategy_api_url || "http://localhost:8001"
        }
        selectedTicker={state.config.ticker}
        activeProfile={resolvedUnifiedProfile}
        activeProfileId={resolvedUnifiedProfileId}
        activeProfileName={resolvedUnifiedProfileName}
      />
    </div>
  );
}
