type AdaptiveStudioTabItem = {
  id: string;
  label: string;
  icon: string;
};

type AdaptiveStudioTabsNavProps = {
  tabs: readonly AdaptiveStudioTabItem[];
  activeTab: string;
  onTabChange: (tabId: string) => void;
};

export default function AdaptiveStudioTabsNav({
  tabs,
  activeTab,
  onTabChange,
}: AdaptiveStudioTabsNavProps) {
  return (
    <div className="studio-tabs">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          className={`studio-tab ${activeTab === tab.id ? "active" : ""}`}
          onClick={() => onTabChange(tab.id)}
        >
          <span className="studio-tab-icon">{tab.icon}</span>
          <span>{tab.label}</span>
        </button>
      ))}
    </div>
  );
}
