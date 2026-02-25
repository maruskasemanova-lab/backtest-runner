type Props = {
  enabledCount: number;
  totalCount: number;
  onRefresh: () => void;
  onExpandAll: () => void;
  onCollapseAll: () => void;
};

export default function AdaptiveStudioExecutionModulesToolbar({
  enabledCount,
  totalCount,
  onRefresh,
  onExpandAll,
  onCollapseAll,
}: Props) {
  return (
    <div className="sc-toolbar">
      <div className="sc-toolbar-left">
        <span className="sc-counter">
          {enabledCount}/{totalCount}
        </span>
        <span className="sc-msg">
          Global defaults synced with RunConfig execution snapshot.
        </span>
      </div>
      <div className="sc-toolbar-right">
        <button
          className="sc-icon-btn"
          onClick={onRefresh}
          title="Refresh snapshot"
        >
          ↻
        </button>
        <button
          className="sc-icon-btn"
          onClick={onExpandAll}
          title="Expand all"
        >
          ⬇
        </button>
        <button
          className="sc-icon-btn"
          onClick={onCollapseAll}
          title="Collapse all"
        >
          ⬆
        </button>
      </div>
    </div>
  );
}
