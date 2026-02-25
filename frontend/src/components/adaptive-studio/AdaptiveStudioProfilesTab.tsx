import AdaptiveStudioUnifiedProfileCapture from "./AdaptiveStudioUnifiedProfileCapture";
import AdaptiveStudioUnifiedProfileList from "./AdaptiveStudioUnifiedProfileList";
import AdaptiveStudioUnifiedProfileViewer from "./AdaptiveStudioUnifiedProfileViewer";
import type {
  AdaptiveStudioActionLoadingToken,
  AdaptiveStudioObjectRecord,
  AdaptiveStudioUnifiedProfileRow,
  AdaptiveStudioUnifiedViewTab,
} from "./profileTypes";

type Props = {
  activeTicker: string;
  unifiedDraftName: string;
  onUnifiedDraftNameChange: (value: string) => void;
  onCaptureUnifiedProfile: () => void;
  captureDisabled: boolean;
  captureLoading: boolean;
  unifiedLoading: boolean;
  unifiedList: AdaptiveStudioUnifiedProfileRow[];
  activeUnifiedId: string;
  unifiedActionLoading: AdaptiveStudioActionLoadingToken;
  saving: boolean;
  loading: boolean;
  asObject: (value: unknown) => AdaptiveStudioObjectRecord;
  formatProfileTimestamp: (value: unknown) => string;
  onLoadUnifiedProfileToEditor: (profile: AdaptiveStudioUnifiedProfileRow) => void;
  onSetActiveUnifiedProfile: (profile: AdaptiveStudioUnifiedProfileRow) => void;
  hasActiveUnifiedProfile: boolean;
  unifiedViewTab: AdaptiveStudioUnifiedViewTab;
  onUnifiedViewTabChange: (tab: AdaptiveStudioUnifiedViewTab) => void;
  strategyProfileData: AdaptiveStudioObjectRecord;
  executionProfileData: AdaptiveStudioObjectRecord;
};

export default function AdaptiveStudioProfilesTab({
  activeTicker,
  unifiedDraftName,
  onUnifiedDraftNameChange,
  onCaptureUnifiedProfile,
  captureDisabled,
  captureLoading,
  unifiedLoading,
  unifiedList,
  activeUnifiedId,
  unifiedActionLoading,
  saving,
  loading,
  asObject,
  formatProfileTimestamp,
  onLoadUnifiedProfileToEditor,
  onSetActiveUnifiedProfile,
  hasActiveUnifiedProfile,
  unifiedViewTab,
  onUnifiedViewTabChange,
  strategyProfileData,
  executionProfileData,
}: Props) {
  return (
    <div className="adaptive-column">
      <AdaptiveStudioUnifiedProfileCapture
        draftName={unifiedDraftName}
        activeTicker={activeTicker}
        onDraftNameChange={onUnifiedDraftNameChange}
        onCapture={onCaptureUnifiedProfile}
        captureDisabled={captureDisabled}
        captureLoading={captureLoading}
      />

      <AdaptiveStudioUnifiedProfileList
        unifiedLoading={unifiedLoading}
        unifiedList={unifiedList}
        activeUnifiedId={activeUnifiedId}
        unifiedActionLoading={unifiedActionLoading}
        saving={saving}
        loading={loading}
        asObject={asObject}
        formatProfileTimestamp={formatProfileTimestamp}
        onLoadUnifiedProfileToEditor={onLoadUnifiedProfileToEditor}
        onSetActiveUnifiedProfile={onSetActiveUnifiedProfile}
      />

      {hasActiveUnifiedProfile && (
        <AdaptiveStudioUnifiedProfileViewer
          unifiedViewTab={unifiedViewTab}
          onUnifiedViewTabChange={onUnifiedViewTabChange}
          strategyProfileData={strategyProfileData}
          executionProfileData={executionProfileData}
        />
      )}
    </div>
  );
}
