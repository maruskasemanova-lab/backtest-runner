import { useCallback, useEffect } from "react";
import { defaultStrategyApiUrl } from "../utils";
import StrategySettings from "./StrategySettings";
import AdaptiveStudioDecisionFlowDiagram from "./adaptive-studio/AdaptiveStudioDecisionFlowDiagram";
import AdaptiveStudioExecutionModulesPanel from "./adaptive-studio/AdaptiveStudioExecutionModulesPanel";
import AdaptiveStudioFlowBiasPriorityEditor from "./adaptive-studio/AdaptiveStudioFlowBiasPriorityEditor";
import AdaptiveStudioHeaderControls from "./adaptive-studio/AdaptiveStudioHeaderControls";
import AdaptiveStudioNotices from "./adaptive-studio/AdaptiveStudioNotices";
import AdaptiveStudioProfilesTab from "./adaptive-studio/AdaptiveStudioProfilesTab";
import AdaptiveStudioRegimePreferences from "./adaptive-studio/AdaptiveStudioRegimePreferences";
import AdaptiveStudioSelectionFlowGate from "./adaptive-studio/AdaptiveStudioSelectionFlowGate";
import AdaptiveStudioTabsNav from "./adaptive-studio/AdaptiveStudioTabsNav";
import {
  ADAPTIVE_STUDIO_TABS,
  DEFAULT_STRATEGIES,
  EXECUTION_MODULES,
  EXECUTION_MODULE_CATEGORY_LABELS,
  EXECUTION_MODULE_PARAM_FIELDS_BY_MODULE,
  EXECUTION_MODULE_PROFILE_KEYS,
  MACRO_REGIMES,
  MICRO_REGIMES,
} from "./adaptive-studio/constants/adaptive-studio";
import { useAdaptiveStudioData } from "./adaptive-studio/hooks/useAdaptiveStudioData";
import { useAdaptiveStudioEditor } from "./adaptive-studio/hooks/useAdaptiveStudioEditor";
import { useAdaptiveStudioMutations } from "./adaptive-studio/hooks/useAdaptiveStudioMutations";
import { useAdaptiveStudioExecutionModuleHandlers } from "./adaptive-studio/useAdaptiveStudioExecutionModuleHandlers";
import { useExecutionModulesEditor } from "./adaptive-studio/useExecutionModulesEditor";
import {
  asObject,
  formatProfileTimestamp,
  normalizeExecutionParamValue,
  readExecutionConfigSnapshot,
  strategyLabel,
  toBoolean,
} from "./adaptive-studio/utils/adaptive-studio-transformers";

type ApplyExecutionFieldChangeOptions = {
  raw?: boolean;
};

function AdaptiveStrategyStudio({ selectedTicker, onTickerChange, strategyApiUrl }) {
  const {
    executionConfigSnapshot,
    expandedExecutionModules,
    toggleExecutionModuleExpanded,
    expandAllExecutionModules,
    collapseAllExecutionModules,
    refreshExecutionConfigSnapshot,
    updateExecutionConfigField,
    mergeExecutionConfigSnapshot,
    getExecutionParamValue,
  } = useExecutionModulesEditor({
    modules: EXECUTION_MODULES,
    normalizeExecutionParamValue,
    readExecutionConfigSnapshot,
  });

  const activeTicker = String(selectedTicker || "").toUpperCase();
  const strategyApiBase = (strategyApiUrl || defaultStrategyApiUrl).replace(/\/+$/, "");
  const {
    availableTickers,
    strategyUniverse,
    rawTickerConfig,
    profileList,
    activeProfileIdFromServer,
    unifiedList,
    activeUnifiedIdFromServer,
    loading,
    profileLoading,
    comboLoading,
    unifiedLoading,
    tickerConfigError,
    profileError,
    comboError,
    unifiedError,
    refreshActiveTickerData,
    refreshAllData,
    setTickerConfigCache,
  } = useAdaptiveStudioData({
    activeTicker,
    strategyApiBase,
    strategyUniverseFallback: DEFAULT_STRATEGIES,
  });
  const {
    saving,
    unifiedActionLoading,
    saveAdaptiveConfig,
    captureUnifiedProfile,
    applyUnifiedProfile,
  } = useAdaptiveStudioMutations({
    activeTicker,
    strategyApiBase,
    refreshActiveTickerData,
    setTickerConfigCache,
  });
  const {
    activeTab,
    setActiveTab,
    notice,
    form,
    unifiedDraftName,
    setUnifiedDraftName,
    unifiedViewTab,
    setUnifiedViewTab,
    markExecutionConfigDirty,
    handleSave,
    handleReload,
    handleCaptureUnifiedProfile,
    handleSetActiveUnifiedProfile,
    handleLoadUnifiedProfileToEditor,
    handleStrategySelectionModeChange,
    handleMaxActiveStrategiesChange,
    handleFlowBiasEnabledChange,
    handleUseOhlcvFallbacksChange,
    handleMinActiveBarsBeforeSwitchChange,
    handleSwitchCooldownBarsChange,
    movePriorityItem,
    toggleStrategyInList,
    moveFlowBiasStrategy,
    toggleFlowBiasStrategy,
    activeUnifiedProfile,
    strategyProfileData,
    executionProfileData,
    strategyModeLabel,
    l2BranchSummary,
    noL2BranchSummary,
    activeUnifiedLegacyComboSourceId,
    activeUnifiedLegacyTunedSourceId,
    surfaceError,
    hasTickers,
    reloadLoading,
    reloadDisabled,
    saveDisabled,
    captureDisabled,
    captureLoading,
  } = useAdaptiveStudioEditor({
    activeTicker,
    availableTickers,
    strategyUniverse,
    rawTickerConfig,
    profileList,
    activeProfileIdFromServer,
    unifiedList,
    activeUnifiedIdFromServer,
    loading,
    profileLoading,
    comboLoading,
    unifiedLoading,
    saving,
    unifiedActionLoading,
    tickerConfigError,
    refreshAllData,
    refreshExecutionConfigSnapshot,
    mergeExecutionConfigSnapshot,
    readExecutionConfigSnapshot,
    saveAdaptiveConfig,
    captureUnifiedProfile,
    applyUnifiedProfile,
  });

  useEffect(() => {
    if (activeTicker || !availableTickers.length || !onTickerChange) return;
    const fallback = availableTickers.includes("MU") ? "MU" : availableTickers[0];
    onTickerChange(fallback);
  }, [activeTicker, availableTickers, onTickerChange]);

  useEffect(() => {
    const handleComboUpdated = (event: Event) => {
      const ticker = String((event as CustomEvent<{ ticker?: string }>).detail?.ticker || "").toUpperCase();
      if (!ticker || ticker !== activeTicker) return;
      void refreshActiveTickerData();
    };
    window.addEventListener("strategy-combo-updated", handleComboUpdated);
    return () => {
      window.removeEventListener("strategy-combo-updated", handleComboUpdated);
    };
  }, [activeTicker, refreshActiveTickerData]);

  const applyExecutionFieldChange = useCallback(
    (
      configKey: string,
      value: unknown,
      options: ApplyExecutionFieldChangeOptions = {},
    ) => {
      updateExecutionConfigField(configKey, value, options);
      markExecutionConfigDirty();
    },
    [markExecutionConfigDirty, updateExecutionConfigField],
  );

  const {
    handleToggleEnabled: handleExecutionModuleToggleEnabled,
    handleFieldValueChange: handleExecutionModuleFieldValueChange,
  } = useAdaptiveStudioExecutionModuleHandlers({
    applyExecutionFieldChange,
    normalizeExecutionParamValue,
  });

  return (
    <main className="adaptive-studio-page">
      <section className="card adaptive-studio-controls">
        <AdaptiveStudioHeaderControls
          activeTicker={activeTicker}
          availableTickers={availableTickers}
          hasTickers={hasTickers}
          onTickerChange={onTickerChange}
          onReload={handleReload}
          onSave={handleSave}
          reloadDisabled={reloadDisabled}
          saveDisabled={saveDisabled}
          reloadLoading={reloadLoading}
          saveLoading={saving}
        />

        <AdaptiveStudioTabsNav
          tabs={ADAPTIVE_STUDIO_TABS}
          activeTab={activeTab}
          onTabChange={(tabId) => setActiveTab(tabId as typeof activeTab)}
        />

        <div className="studio-tab-content">
          <AdaptiveStudioNotices
            error={surfaceError}
            notice={notice}
            unifiedError={unifiedError}
            profileError={profileError}
            comboError={comboError}
          />

          {activeTab === "profiles" && (
            <AdaptiveStudioProfilesTab
              activeTicker={activeTicker}
              unifiedDraftName={unifiedDraftName}
              onUnifiedDraftNameChange={setUnifiedDraftName}
              onCaptureUnifiedProfile={handleCaptureUnifiedProfile}
              captureDisabled={captureDisabled}
              captureLoading={captureLoading}
              unifiedLoading={!!unifiedLoading}
              unifiedList={Array.isArray(unifiedList) ? unifiedList : []}
              activeUnifiedId={String(activeUnifiedIdFromServer || "")}
              unifiedActionLoading={typeof unifiedActionLoading === "string" ? unifiedActionLoading : null}
              saving={!!saving}
              loading={!!loading}
              asObject={asObject}
              formatProfileTimestamp={formatProfileTimestamp}
              onLoadUnifiedProfileToEditor={handleLoadUnifiedProfileToEditor}
              onSetActiveUnifiedProfile={handleSetActiveUnifiedProfile}
              hasActiveUnifiedProfile={!!activeUnifiedProfile}
              unifiedViewTab={unifiedViewTab}
              onUnifiedViewTabChange={setUnifiedViewTab}
              strategyProfileData={strategyProfileData}
              executionProfileData={executionProfileData}
            />
          )}

          {activeTab === "strategies" && (
            <div className="adaptive-column">
              <StrategySettings
                apiUrl={strategyApiBase}
                selectedTicker={activeTicker}
                initialExpandAll
              />
            </div>
          )}

          {activeTab === "modules" && (
            <div className="adaptive-column">
              <AdaptiveStudioExecutionModulesPanel
                modules={EXECUTION_MODULES}
                moduleProfileKeys={EXECUTION_MODULE_PROFILE_KEYS}
                moduleFieldsByModule={EXECUTION_MODULE_PARAM_FIELDS_BY_MODULE}
                categoryLabelsByCategory={EXECUTION_MODULE_CATEGORY_LABELS}
                executionConfigSnapshot={executionConfigSnapshot}
                expandedExecutionModules={expandedExecutionModules}
                coerceBooleanValue={toBoolean}
                onRefresh={refreshExecutionConfigSnapshot}
                onExpandAll={expandAllExecutionModules}
                onCollapseAll={collapseAllExecutionModules}
                onToggleExpanded={toggleExecutionModuleExpanded}
                onToggleEnabled={handleExecutionModuleToggleEnabled}
                getExecutionParamValue={getExecutionParamValue}
                onFieldValueChange={handleExecutionModuleFieldValueChange}
              />
            </div>
          )}

          {activeTab === "adaptive" && (
            <div className="adaptive-column">
              <AdaptiveStudioSelectionFlowGate
                strategySelectionMode={String(form.strategy_selection_mode || "adaptive_top_n")}
                maxActiveStrategiesValue={form.max_active_strategies}
                flowBiasEnabled={!!form.flow_bias_enabled}
                useOhlcvFallbacks={!!form.use_ohlcv_fallbacks}
                minActiveBarsBeforeSwitchValue={form.min_active_bars_before_switch}
                switchCooldownBarsValue={form.switch_cooldown_bars}
                onStrategySelectionModeChange={handleStrategySelectionModeChange}
                onMaxActiveStrategiesChange={handleMaxActiveStrategiesChange}
                onFlowBiasEnabledChange={handleFlowBiasEnabledChange}
                onUseOhlcvFallbacksChange={handleUseOhlcvFallbacksChange}
                onMinActiveBarsBeforeSwitchChange={handleMinActiveBarsBeforeSwitchChange}
                onSwitchCooldownBarsChange={handleSwitchCooldownBarsChange}
              />

              <AdaptiveStudioFlowBiasPriorityEditor
                selectedStrategies={Array.isArray(form.flow_bias_strategies) ? form.flow_bias_strategies : []}
                strategyUniverse={Array.isArray(strategyUniverse) ? strategyUniverse : []}
                strategyLabel={strategyLabel}
                onMoveStrategy={moveFlowBiasStrategy}
                onToggleStrategy={toggleFlowBiasStrategy}
              />

              <AdaptiveStudioRegimePreferences
                macroRegimes={MACRO_REGIMES}
                microRegimes={MICRO_REGIMES}
                macroPreferences={form.regime_preferences}
                microPreferences={form.micro_regime_preferences}
                strategyUniverse={strategyUniverse}
                strategyLabel={strategyLabel}
                onMovePriorityItem={movePriorityItem}
                onToggleStrategyInList={toggleStrategyInList}
              />
            </div>
          )}

          {activeTab === "flow" && (
            <div className="adaptive-column">
              <AdaptiveStudioDecisionFlowDiagram
                l2BranchSummary={l2BranchSummary}
                noL2BranchSummary={noL2BranchSummary}
                activeUnifiedId={String(activeUnifiedIdFromServer || "")}
                legacyComboSourceId={activeUnifiedLegacyComboSourceId}
                legacyTunedSourceId={activeUnifiedLegacyTunedSourceId}
                hysteresisBars={form.min_active_bars_before_switch}
                cooldownBars={form.switch_cooldown_bars}
                strategyModeLabel={strategyModeLabel}
              />
            </div>
          )}
        </div>
      </section>
    </main>
  );
}

export default AdaptiveStrategyStudio;
