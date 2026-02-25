import type {
  AdaptiveStudioActionLoadingToken,
  AdaptiveStudioObjectRecord,
  AdaptiveStudioUnifiedProfileRow,
} from "./profileTypes";

type Props = {
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
};

export default function AdaptiveStudioUnifiedProfileList({
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
}: Props) {
  const activeBadgeLabel = activeUnifiedId
    ? `Active: ${activeUnifiedId.slice(0, 12)}…`
    : "None active";

  return (
    <div className="adaptive-section">
      <details open>
        <summary>
          <span>Unified Profile List</span>
          <span className={`profile-badge ${activeUnifiedId ? "active-badge" : "inactive-badge"}`}>
            {activeBadgeLabel}
          </span>
        </summary>
        <div>
          {unifiedLoading ? (
            <div className="adaptive-empty">Loading…</div>
          ) : !unifiedList.length ? (
            <div className="adaptive-empty">No unified profiles saved yet.</div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {unifiedList.map((profile, idx) => {
                const row = asObject(profile);
                const profileId = String(row.profile_id || "").trim();
                const isActive = !!profileId && profileId === activeUnifiedId;
                const strategyProfile = asObject(row.strategy_profile);
                const strategyParams = asObject(strategyProfile.strategy_params);
                const strategyCount = Object.keys(strategyParams).length;
                const executionProfile = asObject(row.execution_profile);
                const positioning = asObject(executionProfile.positioning);
                const hasExecution = Object.keys(positioning).length > 0;
                const isSettingActive = unifiedActionLoading === `active:${profileId}`;

                return (
                  <div
                    className={`profile-table-row ${isActive ? "active" : ""}`}
                    key={profileId || `up-${idx}`}
                  >
                    <span className={`profile-badge ${isActive ? "active-badge" : "inactive-badge"}`}>
                      {isActive ? "●" : "○"}
                    </span>
                    <span className="profile-name">
                      {String(row.profile_name || "").trim() || profileId || "profile"}
                    </span>
                    <span className="profile-meta">{strategyCount} strategies</span>
                    <span className="profile-meta">{hasExecution ? "execution yes" : "execution no"}</span>
                    <span className="profile-meta">
                      {formatProfileTimestamp(row.updated_at || row.created_at)}
                    </span>
                    <div className="profile-table-actions">
                      <button
                        className="btn btn-secondary btn-sm"
                        onClick={() => onLoadUnifiedProfileToEditor(profile)}
                        disabled={!profileId || !!unifiedActionLoading}
                      >
                        Load
                      </button>
                      <button
                        className="btn btn-secondary btn-sm"
                        onClick={() => onSetActiveUnifiedProfile(profile)}
                        disabled={!profileId || isActive || !!unifiedActionLoading || saving || loading}
                      >
                        {isSettingActive ? "…" : isActive ? "Active" : "Set Active"}
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </details>
    </div>
  );
}
