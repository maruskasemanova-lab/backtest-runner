import { useCallback, useEffect, useRef, useState } from "react";
import { UNIFIED_CONFIG_SECTIONS, type UnifiedConfigSectionId } from "./types";

export function useUnifiedConfigNavigation() {
  const [activeSectionId, setActiveSectionId] =
    useState<UnifiedConfigSectionId>("strategies");
  const contentRef = useRef<HTMLDivElement>(null);
  const sectionRefs = useRef<Record<string, HTMLDivElement | null>>({});
  const isScrollingTo = useRef(false);

  const setSectionRef = useCallback(
    (id: string, node: HTMLDivElement | null) => {
      sectionRefs.current[id] = node;
    },
    [],
  );

  const scrollToSection = useCallback((sectionId: string) => {
    const node = sectionRefs.current[sectionId];
    if (!node || !contentRef.current) return;
    isScrollingTo.current = true;
    node.scrollIntoView({ behavior: "smooth", block: "start" });
    setActiveSectionId(sectionId as UnifiedConfigSectionId);
    setTimeout(() => {
      isScrollingTo.current = false;
    }, 800);
  }, []);

  useEffect(() => {
    const container = contentRef.current;
    if (!container) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (isScrollingTo.current) return;
        let best: { id: string; ratio: number } | null = null;
        for (const entry of entries) {
          const id = entry.target.getAttribute("data-section-id");
          if (!id) continue;
          if (!best || entry.intersectionRatio > best.ratio) {
            best = { id, ratio: entry.intersectionRatio };
          }
        }
        if (best && best.ratio > 0) {
          setActiveSectionId(best.id as UnifiedConfigSectionId);
        }
      },
      {
        root: container,
        threshold: [0, 0.1, 0.3, 0.5],
        rootMargin: "-10% 0px -60% 0px",
      },
    );

    for (const section of UNIFIED_CONFIG_SECTIONS) {
      const node = sectionRefs.current[section.id];
      if (node) observer.observe(node);
    }

    return () => observer.disconnect();
  }, []);

  return {
    activeSectionId,
    contentRef,
    setSectionRef,
    scrollToSection,
  };
}
