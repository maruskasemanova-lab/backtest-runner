import type { UnifiedConfigSection } from "./types";

interface UnifiedConfigSidebarProps {
  sections: UnifiedConfigSection[];
  activeSectionId: string;
  onSectionClick: (sectionId: string) => void;
}

export function UnifiedConfigSidebar({
  sections,
  activeSectionId,
  onSectionClick,
}: UnifiedConfigSidebarProps) {
  return (
    <nav className="unified-config-sidebar">
      {sections.map((section) => (
        <button
          key={section.id}
          type="button"
          className={`unified-config-sidebar-item ${activeSectionId === section.id ? "active" : ""}`}
          onClick={() => onSectionClick(section.id)}
        >
          <span className="unified-config-sidebar-icon">{section.icon}</span>
          <span className="unified-config-sidebar-label">{section.label}</span>
        </button>
      ))}
    </nav>
  );
}
