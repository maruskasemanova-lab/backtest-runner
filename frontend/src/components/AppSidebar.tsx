import type { MouseEvent, RefObject } from 'react';
import type {
  SidebarNavConfigItem,
  SidebarSection,
} from '../hooks/useBacktestSidebarSections';
import {
  clampSidebarWidth,
  VIEW_TABS,
} from '../app/appShared';

type AppSidebarProps = {
  activeSidebarNavItem: string | null;
  activeSidebarSectionId: string | null;
  activeView: string;
  isNavOpen: boolean;
  onSetActiveView: (view: string) => void;
  onSetNavOpen: (open: boolean) => void;
  onSidebarNavToggle: (item: SidebarNavConfigItem) => void;
  onSidebarResizeMouseDown: (event: MouseEvent<HTMLDivElement>) => void;
  runtimeNotice: string;
  sidebarNavItems: SidebarNavConfigItem[];
  sidebarRailRef: RefObject<HTMLDivElement | null>;
  sidebarSectionsById: Map<string, SidebarSection>;
  sidebarWidth: number;
};

function AppSidebar({
  activeSidebarNavItem,
  activeSidebarSectionId,
  activeView,
  isNavOpen,
  onSetActiveView,
  onSetNavOpen,
  onSidebarNavToggle,
  onSidebarResizeMouseDown,
  runtimeNotice,
  sidebarNavItems,
  sidebarRailRef,
  sidebarSectionsById,
  sidebarWidth,
}: AppSidebarProps) {
  const clampedSidebarWidth = clampSidebarWidth(sidebarWidth);
  const activeViewMeta = VIEW_TABS.find((tab) => tab.id === activeView) ?? VIEW_TABS[0];

  return (
    <>
      <aside
        className={`app-sidebar ${isNavOpen ? 'mobile-open' : ''}`}
        style={{ width: `${clampedSidebarWidth}px`, minWidth: `${clampedSidebarWidth}px` }}
      >
        <div className="sidebar-brand">
          <span className="sidebar-brand-icon">📈</span>
          <div className="sidebar-brand-text">
            <span className="sidebar-brand-name">Backtest Runner</span>
            <span className="sidebar-brand-tagline">Trading Workspace</span>
          </div>
        </div>
        <div className="sidebar-brand-meta">
          <span className="sidebar-brand-chip">Control Surface</span>
          <span className="sidebar-brand-chip sidebar-brand-chip-active">
            {activeViewMeta.label}
          </span>
        </div>

        <nav className="sidebar-main-nav">
          {VIEW_TABS.map((tab) => (
            <button
              key={tab.id}
              className={`sidebar-nav-btn ${activeView === tab.id ? 'active' : ''}`}
              onClick={() => {
                onSetActiveView(tab.id);
                onSetNavOpen(false);
              }}
              title={tab.label}
            >
              <span className="sidebar-nav-icon">{tab.icon}</span>
              <span className="sidebar-nav-label">{tab.label}</span>
            </button>
          ))}
        </nav>

        {activeView === 'backtest' && sidebarNavItems.length > 0 && (
          <>
            <div className="sidebar-divider" />
            <div className="sidebar-section-nav" ref={sidebarRailRef}>
              <div className="sidebar-control-header">
                <span className="sidebar-control-kicker">Control Lanes</span>
                <span className="sidebar-control-mode">{activeViewMeta.label}</span>
              </div>
              {runtimeNotice ? <div className="sidebar-notice">{runtimeNotice}</div> : null}

              {sidebarNavItems.map((item, itemIndex) => {
                const section = sidebarSectionsById.get(item.sectionId);
                if (!section) return null;
                const isActiveItem = activeSidebarNavItem === item.id;
                const isRunConfigItem = section.id === 'run-config';

                return (
                  <div
                    key={item.id}
                    className={`sidebar-section-entry ${!isRunConfigItem && isActiveItem ? 'open' : ''}`}
                    style={{ order: itemIndex * 2 }}
                  >
                    <button
                      id={`sidebar-nav-${item.id}`}
                      type="button"
                      className={`sidebar-section-btn ${isActiveItem ? 'active' : ''}`}
                      onClick={() => onSidebarNavToggle(item)}
                      aria-expanded={isActiveItem}
                      title={`${item.label} (${item.rangeLabel})`}
                    >
                      <span className="sidebar-section-icon">{item.icon}</span>
                      <span className="sidebar-section-label">{item.label}</span>
                      <span className="sidebar-section-badge">{item.rangeLabel}</span>
                      <span className={`sidebar-section-caret ${isActiveItem ? 'open' : ''}`}>▾</span>
                    </button>
                    {!isRunConfigItem && isActiveItem ? (
                      <div className="sidebar-panel">
                        <div className="sidebar-panel-content">{section.content}</div>
                      </div>
                    ) : null}
                  </div>
                );
              })}

              {activeSidebarSectionId === 'run-config' && (() => {
                const section = sidebarSectionsById.get('run-config');
                if (!section) return null;
                const activeIdx = sidebarNavItems.findIndex((item) => item.id === activeSidebarNavItem);
                return (
                  <div
                    className="sidebar-section-entry open"
                    style={{ order: activeIdx >= 0 ? activeIdx * 2 + 1 : 999 }}
                  >
                    <div className="sidebar-panel">
                      <div className="sidebar-panel-content">{section.content}</div>
                    </div>
                  </div>
                );
              })()}
            </div>
          </>
        )}
        <div
          className="sidebar-resize-handle"
          onMouseDown={onSidebarResizeMouseDown}
          role="separator"
          aria-orientation="vertical"
          aria-label="Resize sidebar"
          title="Drag to resize sidebar"
        />
      </aside>
      {isNavOpen ? <div className="sidebar-overlay" onClick={() => onSetNavOpen(false)} /> : null}
    </>
  );
}

export default AppSidebar;
