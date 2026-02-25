import type {
  AdaptiveStudioObjectRecord,
  AdaptiveStudioUnifiedViewTab,
} from "./profileTypes";

type Props = {
  unifiedViewTab: AdaptiveStudioUnifiedViewTab;
  onUnifiedViewTabChange: (tab: AdaptiveStudioUnifiedViewTab) => void;
  strategyProfileData: AdaptiveStudioObjectRecord;
  executionProfileData: AdaptiveStudioObjectRecord;
};

export default function AdaptiveStudioUnifiedProfileViewer({
  unifiedViewTab,
  onUnifiedViewTabChange,
  strategyProfileData,
  executionProfileData,
}: Props) {
  return (
    <div className="adaptive-section">
      <div style={{ display: "flex", gap: 8, marginBottom: 8 }}>
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          onClick={() => onUnifiedViewTabChange("strategy")}
          style={{
            opacity: unifiedViewTab === "strategy" ? 1 : 0.75,
            borderColor: unifiedViewTab === "strategy" ? "var(--accent-primary)" : undefined,
          }}
        >
          Strategy profile
        </button>
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          onClick={() => onUnifiedViewTabChange("execution")}
          style={{
            opacity: unifiedViewTab === "execution" ? 1 : 0.75,
            borderColor: unifiedViewTab === "execution" ? "var(--accent-primary)" : undefined,
          }}
        >
          Execution profile
        </button>
      </div>
      <pre
        style={{
          margin: 0,
          padding: "10px",
          borderRadius: "8px",
          border: "1px solid var(--border-default)",
          background: "var(--surface-2)",
          color: "var(--text-primary)",
          fontSize: "0.75rem",
          overflowX: "auto",
          maxHeight: "280px",
        }}
      >
        {JSON.stringify(
          unifiedViewTab === "strategy" ? strategyProfileData : executionProfileData,
          null,
          2,
        )}
      </pre>
    </div>
  );
}
