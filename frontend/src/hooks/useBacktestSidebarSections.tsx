import { useMemo, type ReactNode } from 'react';
import PlaybackControls from '../components/PlaybackControls';
import RunConfig from '../components/RunConfig';
import SessionSummary from '../components/SessionSummary';
import StrategyModuleToggles from '../components/StrategyModuleToggles';
import ExecutionModuleToggles from '../components/ExecutionModuleToggles';
import type { StrategyAnalyzerDecisionMarker } from '../components/strategy-analyzer/types';

type SidebarNavConfigItem = {
  id: string;
  sectionId: string;
  runConfigMode?: 'all' | 'dates' | 'profiles' | 'start';
};

type SidebarSection = {
  id: string;
  title: string;
  rangeLabel: string;
  maxHeight: number;
  content: ReactNode;
};

type UseBacktestSidebarSectionsArgs = {
  sidebarNavConfig: readonly SidebarNavConfigItem[];
  activeSidebarNavItem: string | null;
  activeRuns: any[];
  runKey: string | null;
  runState: any;
  markers: StrategyAnalyzerDecisionMarker[];
  hasActiveAttachedRun: boolean;
  effectiveExecutionConfig: any;
  authToken: string;
  selectedTicker: string | null;
  strategyApiUrl: string;
  isPlaying: boolean;
  speed: any;
  tradeEvaluationMode: string;
  isReloadingSnapshot: boolean;
  setSelectedTicker: (value: string | null) => void;
  setActiveView: (view: string) => void;
  setSpeed: (value: any) => void;
  setTradeEvaluationMode: (value: any) => void;
  handleStartRun: (config: any) => Promise<any>;
  handleAttachRun: (runKey: string) => Promise<any>;
  handleKillRun: (runKey: string) => Promise<any>;
  handleStep: (options?: any) => Promise<any> | void;
  handlePlay: (options?: any) => Promise<any> | void;
  handlePause: () => Promise<any> | void;
  handleStop: () => Promise<any> | void;
  handleReloadBacktest: () => Promise<any> | void;
  handleReset: () => Promise<any> | void;
};

export const useBacktestSidebarSections = ({
  sidebarNavConfig,
  activeSidebarNavItem,
  activeRuns,
  runKey,
  runState,
  markers,
  hasActiveAttachedRun,
  effectiveExecutionConfig,
  authToken,
  selectedTicker,
  strategyApiUrl,
  isPlaying,
  speed,
  tradeEvaluationMode,
  isReloadingSnapshot,
  setSelectedTicker,
  setActiveView,
  setSpeed,
  setTradeEvaluationMode,
  handleStartRun,
  handleAttachRun,
  handleKillRun,
  handleStep,
  handlePlay,
  handlePause,
  handleStop,
  handleReloadBacktest,
  handleReset,
}: UseBacktestSidebarSectionsArgs) => {
  const activeRunConfigSidebarMode = useMemo<'all' | 'dates' | 'profiles' | 'start'>(() => {
    const activeItem = sidebarNavConfig.find((item) => item.id === activeSidebarNavItem);
    if (!activeItem || activeItem.sectionId !== 'run-config') {
      return 'all';
    }
    return activeItem.runConfigMode || 'all';
  }, [activeSidebarNavItem, sidebarNavConfig]);

  const runConfigSidebarContent = useMemo(
    () => (
      <RunConfig
        onStart={handleStartRun}
        isRunning={hasActiveAttachedRun}
        onTickerChange={setSelectedTicker}
        effectiveExecutionConfig={effectiveExecutionConfig}
        activeRuns={activeRuns}
        activeRunKey={runKey}
        onAttachRun={handleAttachRun}
        onKillRun={handleKillRun}
        sidebarSubsection={activeRunConfigSidebarMode}
        authToken={authToken}
        activeRunState={runState}
      />
    ),
    [
      activeRunConfigSidebarMode,
      activeRuns,
      authToken,
      effectiveExecutionConfig,
      handleAttachRun,
      handleKillRun,
      handleStartRun,
      hasActiveAttachedRun,
      runKey,
      runState,
      setSelectedTicker,
    ],
  );

  const strategySettingsSidebarContent = useMemo(
    () => (
      <StrategyModuleToggles
        apiUrl={strategyApiUrl}
        selectedTicker={selectedTicker}
        onNavigateToStudio={() => setActiveView('adaptive-studio')}
      />
    ),
    [selectedTicker, setActiveView, strategyApiUrl],
  );

  const executionModulesSidebarContent = useMemo(() => <ExecutionModuleToggles />, []);

  const playbackSidebarContent = useMemo(() => {
    if (!runKey) return null;
    return (
      <PlaybackControls
        runState={runState}
        isPlaying={isPlaying}
        speed={speed}
        tradeEvaluationMode={tradeEvaluationMode}
        isReloading={isReloadingSnapshot}
        onSpeedChange={setSpeed}
        onTradeEvaluationModeChange={setTradeEvaluationMode}
        onStep={handleStep}
        onPlay={handlePlay}
        onPause={handlePause}
        onStop={handleStop}
        onReload={handleReloadBacktest}
        onReset={handleReset}
      />
    );
  }, [
    handlePause,
    handlePlay,
    handleReloadBacktest,
    handleReset,
    handleStep,
    handleStop,
    isPlaying,
    isReloadingSnapshot,
    runKey,
    runState,
    setSpeed,
    setTradeEvaluationMode,
    speed,
    tradeEvaluationMode,
  ]);

  const sessionSummarySidebarContent = useMemo(() => {
    if (!runState) return null;
    return <SessionSummary runState={runState} markers={markers} />;
  }, [markers, runState]);

  const sidebarSections = useMemo<SidebarSection[]>(() => {
    const sections: SidebarSection[] = [
      {
        id: 'run-config',
        title: 'Run Configuration',
        rangeLabel: 'Range A',
        maxHeight: 780,
        content: runConfigSidebarContent,
      },
      {
        id: 'strategy-settings',
        title: 'Strategy Settings',
        rangeLabel: 'Range B',
        maxHeight: 720,
        content: strategySettingsSidebarContent,
      },
      {
        id: 'execution-modules',
        title: 'Global Modules',
        rangeLabel: 'Range E',
        maxHeight: 720,
        content: executionModulesSidebarContent,
      },
    ];

    if (playbackSidebarContent) {
      sections.push({
        id: 'playback-controls',
        title: 'Playback Controls',
        rangeLabel: 'Range C',
        maxHeight: 420,
        content: playbackSidebarContent,
      });
    }

    if (sessionSummarySidebarContent) {
      sections.push({
        id: 'session-summary',
        title: 'Session Summary',
        rangeLabel: 'Range D',
        maxHeight: 340,
        content: sessionSummarySidebarContent,
      });
    }

    return sections;
  }, [
    executionModulesSidebarContent,
    playbackSidebarContent,
    runConfigSidebarContent,
    sessionSummarySidebarContent,
    strategySettingsSidebarContent,
  ]);

  const sidebarNavItems = useMemo(() => {
    const availableSectionIds = new Set(sidebarSections.map((section) => section.id));
    return sidebarNavConfig.filter((item) => availableSectionIds.has(item.sectionId));
  }, [sidebarNavConfig, sidebarSections]);

  const sidebarSectionsById = useMemo(() => {
    const map = new Map<string, SidebarSection>();
    sidebarSections.forEach((section) => {
      map.set(section.id, section);
    });
    return map;
  }, [sidebarSections]);

  const activeSidebarSectionId = useMemo(() => {
    const activeItem = sidebarNavItems.find((item) => item.id === activeSidebarNavItem);
    return activeItem?.sectionId || null;
  }, [activeSidebarNavItem, sidebarNavItems]);

  return {
    sidebarSections,
    sidebarNavItems,
    sidebarSectionsById,
    activeSidebarSectionId,
  };
};
