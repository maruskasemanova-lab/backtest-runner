import React from "react";
import {
  START_MODE_FAST_RESTART,
  START_MODE_RESUME_WARM_START,
  START_MODE_OPTIONS,
  normalizeStartMode,
  formatStartTimingMs,
  formatStartTimingPhaseLabel,
} from "./runConfigHelpers";

interface StartModeSettingsProps {
  config: Record<string, any>;
  handleChange: (field: string, value: any) => void;
  fetchCheckpoints: () => void;
  checkpointLoading: boolean;
  selectedStartMode: string;
  selectedStartModeOption: any;
  startModeRuntime: any;
  checkpointCatalog: any[];
  handleSaveCheckpointNow: () => void;
  checkpointSaving: boolean;
  checkpointMessage: string | null;
  error: string | null;
  loading: boolean;
  aosLoading: boolean;
  unifiedProfilesLoading: boolean;
  loadingElapsedSec: number;
  handleFlushRunCache: () => void;
  cacheFlushLoading: boolean;
  cacheFlushMessage: string | null;
  prewarmStatus: { state: string; message: string | null };
  startTiming: any;
  formatCheckpointLabel: (cp: any) => string;
}

export function StartModeSettings({
  config,
  handleChange,
  fetchCheckpoints,
  checkpointLoading,
  selectedStartMode,
  selectedStartModeOption,
  startModeRuntime,
  checkpointCatalog,
  handleSaveCheckpointNow,
  checkpointSaving,
  checkpointMessage,
  error,
  loading,
  aosLoading,
  unifiedProfilesLoading,
  loadingElapsedSec,
  handleFlushRunCache,
  cacheFlushLoading,
  cacheFlushMessage,
  prewarmStatus,
  startTiming,
  formatCheckpointLabel,
}: StartModeSettingsProps) {
  return (
    <>
      <div id="start_mode_section" className="preset-box">
        <div className="preset-header">
          <span className="preset-title">Run Start Mode</span>
          <button
            type="button"
            className="btn btn-secondary tw-btn-compact"
            onClick={fetchCheckpoints}
            disabled={checkpointLoading}
          >
            {checkpointLoading ? "Refreshing..." : "Refresh"}
          </button>
        </div>
        <div className="preset-copy">
          Select one deterministic start behavior. Backend mapping stays unchanged.
        </div>

        <div className="form-group">
          <label htmlFor="start_mode">Start Mode</label>
          <select
            id="start_mode"
            value={selectedStartMode}
            onChange={(e) => {
              const nextMode = normalizeStartMode(e.target.value, START_MODE_FAST_RESTART);
              handleChange("start_mode", nextMode);
              if (
                nextMode === START_MODE_RESUME_WARM_START &&
                !config.checkpoint_path &&
                checkpointCatalog.length > 0
              ) {
                handleChange("checkpoint_path", checkpointCatalog[0].path || null);
              }
            }}
          >
            {START_MODE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>

        <div className="preset-copy">
          {selectedStartModeOption?.hint}
          {" "}Scope `{startModeRuntime?.orchestratorResetScope}`, cold-start-each-day{" "}
          {startModeRuntime?.coldStartEachDay ? "on" : "off"}.
        </div>

        <label className="field-row">
          <span>Auto-save Checkpoint After Run</span>
          <input
            type="checkbox"
            checked={!!config.auto_save_checkpoint}
            onChange={(e) => handleChange("auto_save_checkpoint", e.target.checked)}
          />
        </label>

        <label className="field-row">
          <span>Sync AOS Params On Start</span>
          <input
            type="checkbox"
            checked={!!config.apply_aos_optimizations_on_start}
            onChange={(e) => handleChange("apply_aos_optimizations_on_start", e.target.checked)}
          />
        </label>
        <div className="preset-copy">
          Pushes AOS/adaptive parameters to strategy API at start (deterministic, usually slower).
        </div>

        {selectedStartMode === START_MODE_RESUME_WARM_START && (
          <div className="form-group">
            <label htmlFor="checkpoint_path">Checkpoint</label>
            <select
              id="checkpoint_path"
              value={config.checkpoint_path || ""}
              onChange={(e) => handleChange("checkpoint_path", e.target.value || null)}
            >
              <option value="">Select checkpoint...</option>
              {checkpointCatalog.map((cp) => (
                <option key={cp.path} value={cp.path}>
                  {formatCheckpointLabel(cp)}
                </option>
              ))}
            </select>
          </div>
        )}

        {selectedStartMode === START_MODE_RESUME_WARM_START && (
          <div className="form-group">
            <label htmlFor="checkpoint_path_custom">Custom Checkpoint Path</label>
            <input
              id="checkpoint_path_custom"
              type="text"
              value={config.checkpoint_path || ""}
              onChange={(e) => handleChange("checkpoint_path", e.target.value || null)}
              placeholder="data/checkpoints/checkpoint_YYYYMMDD_HHMMSS.json"
            />
          </div>
        )}

        <button
          type="button"
          className="btn btn-secondary tw-full-btn"
          onClick={handleSaveCheckpointNow}
          disabled={checkpointSaving}
        >
          {checkpointSaving ? "Saving checkpoint..." : "Save Checkpoint Now"}
        </button>

        {checkpointMessage && (
          <div className="text-[0.8rem] leading-[1.4] text-app-text-secondary">
            {checkpointMessage}
          </div>
        )}
      </div>

      {error && (
        <div className="rounded-app-sm bg-red-500/10 p-2 text-[0.85rem] text-app-accent-red">{error}</div>
      )}

      <button
        type="submit"
        className="btn btn-primary tw-full-btn mt-2"
        disabled={
          loading ||
          aosLoading ||
          unifiedProfilesLoading ||
          !config.ticker ||
          !config.date_from ||
          !config.date_to
        }
      >
        {loading ? `Starting... ${loadingElapsedSec.toFixed(1)}s` : "Start Backtest"}
      </button>

      <button
        type="button"
        className="btn btn-secondary tw-full-btn mt-2"
        onClick={handleFlushRunCache}
        disabled={loading || cacheFlushLoading}
      >
        {cacheFlushLoading ? "Flushing Cache..." : "Flush Run Cache"}
      </button>

      {cacheFlushMessage && (
        <div className="tw-message-success">
          {cacheFlushMessage}
        </div>
      )}

      {prewarmStatus?.message && (
        <div
          className={
            prewarmStatus.state === "error"
              ? "tw-message-error"
              : prewarmStatus.state === "ready"
                ? "tw-message-success"
                : "tw-message-muted"
          }
        >
          {prewarmStatus.message}
        </div>
      )}

      {startTiming && (
        <div className="tw-timing-wrap">
          <div className="tw-timing-head">
            Start timing: total {formatStartTimingMs(startTiming?.total_ms)}
            {startTiming?.slowest_phase && (
              <>
                {" "} | slowest {formatStartTimingPhaseLabel(startTiming.slowest_phase)}{" "}
                {formatStartTimingMs(startTiming?.slowest_phase_ms)}
              </>
            )}
          </div>
          {startTiming?.context && (
            <div className="mb-1">
              {String(startTiming.context.ticker || "")}{" "}
              {String(startTiming.context.range_start || "")} → {String(startTiming.context.range_end || "")}{" "}
              | bars {Number(startTiming.context.bars_loaded || 0)} | ref{" "}
              {Number(startTiming.context.reference_bars_loaded || 0)} | aos-sync{" "}
              {startTiming.context.apply_aos_optimizations_on_start ? "on" : "off"} | l2 req{" "}
              {startTiming.context.requested_l2_only ||
              startTiming.context.requested_l2_confirm_enabled
                ? "on"
                : "off"}{" "}
              | l2 eff {startTiming.context.effective_l2_confirm_enabled ? "on" : "off"} | sweep-l2 auto{" "}
              {startTiming.context.liquidity_sweep_l2_auto_enabled
                ? `on (${String(startTiming.context.liquidity_sweep_l2_auto_source || "auto")})`
                : "off"}
            </div>
          )}
          {Object.entries(startTiming?.phases_ms || {}).map(([phaseKey, ms]) => (
            <div key={phaseKey}>
              {formatStartTimingPhaseLabel(phaseKey)}: {formatStartTimingMs(ms as number)}
            </div>
          ))}
        </div>
      )}
    </>
  );
}
