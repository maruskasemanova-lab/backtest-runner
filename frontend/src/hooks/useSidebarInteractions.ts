import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  type Dispatch,
  type MouseEvent as ReactMouseEvent,
  type SetStateAction,
} from 'react';

type SidebarNavItemLike = {
  id: string;
  sectionId: string;
  focusFieldId?: string | null;
};

type UseSidebarInteractionsArgs = {
  sidebarNavItems: SidebarNavItemLike[];
  activeSidebarNavItem: string | null;
  activeSidebarSectionId: string | null;
  runConfigPanelHostId: string;
  setActiveSidebarNavItem: Dispatch<SetStateAction<string | null>>;
  isSidebarRailExpanded: boolean;
  setIsSidebarRailExpanded: Dispatch<SetStateAction<boolean>>;
  sidebarWidth: number;
  setSidebarWidth: Dispatch<SetStateAction<number>>;
  clampSidebarWidth: (value: number) => number;
  mobileSidebarBreakpoint: number;
  sidebarWidthStorageKey: string;
};

export const useSidebarInteractions = ({
  sidebarNavItems,
  activeSidebarNavItem,
  activeSidebarSectionId,
  runConfigPanelHostId,
  setActiveSidebarNavItem,
  isSidebarRailExpanded,
  setIsSidebarRailExpanded,
  sidebarWidth,
  setSidebarWidth,
  clampSidebarWidth,
  mobileSidebarBreakpoint,
  sidebarWidthStorageKey,
}: UseSidebarInteractionsArgs) => {
  const sidebarResizeStateRef = useRef<{ startX: number; startWidth: number } | null>(null);

  const isSidebarExpanded = useMemo(
    () => isSidebarRailExpanded && sidebarNavItems.length > 0,
    [isSidebarRailExpanded, sidebarNavItems.length],
  );

  const focusSidebarField = useCallback((fieldId: string | null | undefined) => {
    if (!fieldId) return;
    window.setTimeout(() => {
      const element = document.getElementById(fieldId);
      if (!element) return;
      element.scrollIntoView({ behavior: 'smooth', block: 'center' });
      element.classList.add('sidebar-field-focus');
      window.setTimeout(() => {
        element.classList.remove('sidebar-field-focus');
      }, 920);
    }, 110);
  }, []);

  useEffect(() => {
    if (!sidebarNavItems.length) {
      setActiveSidebarNavItem(null);
      return;
    }
    setActiveSidebarNavItem((prev) => {
      if (prev === null) {
        return null;
      }
      if (prev && sidebarNavItems.some((item) => item.id === prev)) {
        return prev;
      }
      return sidebarNavItems[0].id;
    });
  }, [setActiveSidebarNavItem, sidebarNavItems]);

  const handleSidebarNavToggle = useCallback(
    (item: SidebarNavItemLike) => {
      const runConfigSectionOpen = activeSidebarSectionId === 'run-config';
      const clickedRunConfigHost =
        item.sectionId === 'run-config' && item.id === runConfigPanelHostId;
      const isClosingCurrentItem = activeSidebarNavItem === item.id;
      const collapsingRunConfigHost =
        clickedRunConfigHost && activeSidebarNavItem === runConfigPanelHostId;

      if (item.sectionId === 'run-config') {
        // Keep RunConfig mounted while switching run-config subsections.
        if (runConfigSectionOpen && (isClosingCurrentItem || collapsingRunConfigHost)) {
          setActiveSidebarNavItem(null);
          return;
        }
      } else if (isClosingCurrentItem) {
        setActiveSidebarNavItem(null);
        return;
      }

      setActiveSidebarNavItem(item.id);
      setIsSidebarRailExpanded(true);
      window.setTimeout(() => {
        const navElement = document.getElementById(`sidebar-nav-${item.id}`);
        navElement?.scrollIntoView({
          behavior: 'smooth',
          block: 'center',
          inline: 'nearest',
        });
      }, 40);
      focusSidebarField(item.focusFieldId);
    },
    [
      activeSidebarNavItem,
      activeSidebarSectionId,
      focusSidebarField,
      runConfigPanelHostId,
      setActiveSidebarNavItem,
      setIsSidebarRailExpanded,
    ],
  );

  const handleSidebarMouseEnter = useCallback(() => {
    setIsSidebarRailExpanded(true);
  }, [setIsSidebarRailExpanded]);

  const handleSidebarMouseLeave = useCallback(() => {
    setIsSidebarRailExpanded(false);
  }, [setIsSidebarRailExpanded]);

  const handleSidebarResizeMouseDown = useCallback(
    (event: ReactMouseEvent<HTMLDivElement>) => {
      if (typeof window === 'undefined') return;
      if (window.innerWidth <= mobileSidebarBreakpoint) return;
      event.preventDefault();
      const startWidth = clampSidebarWidth(sidebarWidth);
      sidebarResizeStateRef.current = {
        startX: event.clientX,
        startWidth,
      };

      const onMouseMove = (moveEvent: MouseEvent) => {
        if (!sidebarResizeStateRef.current) return;
        const deltaX = moveEvent.clientX - sidebarResizeStateRef.current.startX;
        const nextWidth = clampSidebarWidth(sidebarResizeStateRef.current.startWidth + deltaX);
        setSidebarWidth(nextWidth);
      };

      const onMouseUp = () => {
        sidebarResizeStateRef.current = null;
        window.removeEventListener('mousemove', onMouseMove);
        window.removeEventListener('mouseup', onMouseUp);
      };

      window.addEventListener('mousemove', onMouseMove);
      window.addEventListener('mouseup', onMouseUp);
    },
    [clampSidebarWidth, mobileSidebarBreakpoint, setSidebarWidth, sidebarWidth],
  );

  useEffect(() => {
    if (typeof window === 'undefined') return;
    window.localStorage.setItem(
      sidebarWidthStorageKey,
      String(clampSidebarWidth(sidebarWidth)),
    );
  }, [clampSidebarWidth, sidebarWidth, sidebarWidthStorageKey]);

  return {
    isSidebarExpanded,
    handleSidebarNavToggle,
    handleSidebarMouseEnter,
    handleSidebarMouseLeave,
    handleSidebarResizeMouseDown,
  };
};
