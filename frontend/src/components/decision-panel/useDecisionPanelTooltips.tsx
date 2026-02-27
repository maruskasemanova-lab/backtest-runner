import { useEffect, useState } from "react";
import type {
  FocusEvent as ReactFocusEvent,
  KeyboardEvent as ReactKeyboardEvent,
  MouseEvent as ReactMouseEvent,
} from "react";
import type {
  DecisionPanelDetailLabelOptions,
  DecisionPanelRenderDetailLabel,
  DecisionPanelTooltipRuntimeMap,
  DecisionPanelTooltipSelectedMarkerRef,
} from "./decision-panel-types";

type ActiveHelpTooltip = {
  top: number;
  left: number;
  maxWidth: number;
  placeAbove: boolean;
  text: string;
  pinned: boolean;
} | null;

type Params = {
  portalWindow: Window | null;
  runtimeTooltipByLabel: DecisionPanelTooltipRuntimeMap;
  resolveTooltipBaseLabel: (label: string) => string;
  formatTooltipRuntimeValue: (value: unknown) => string;
  tooltipLocaleText: { value: string; source: string };
  baseTooltipFor: (label: string) => string;
  t: (text: string) => string;
  selectedMarker: DecisionPanelTooltipSelectedMarkerRef | null;
  detailTab: string;
  uiLanguage: string;
  isDetailFullscreen: boolean;
};

type TooltipAnchorEvent = ReactMouseEvent<HTMLElement> | ReactFocusEvent<HTMLElement>;
type TooltipToggleEvent = ReactMouseEvent<HTMLElement> | ReactKeyboardEvent<HTMLElement>;

function isDetailLabelOptions(value: unknown): value is DecisionPanelDetailLabelOptions {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

export default function useDecisionPanelTooltips({
  portalWindow,
  runtimeTooltipByLabel,
  resolveTooltipBaseLabel,
  formatTooltipRuntimeValue,
  tooltipLocaleText,
  baseTooltipFor,
  t,
  selectedMarker,
  detailTab,
  uiLanguage,
  isDetailFullscreen,
}: Params) {
  const [activeHelpTooltip, setActiveHelpTooltip] = useState<ActiveHelpTooltip>(null);

  useEffect(() => {
    setActiveHelpTooltip(null);
  }, [
    selectedMarker?.id,
    selectedMarker?.timestamp,
    selectedMarker?.time,
    detailTab,
    uiLanguage,
    isDetailFullscreen,
  ]);

  useEffect(() => {
    if (!activeHelpTooltip) return undefined;
    if (!portalWindow) return undefined;
    const clearTooltip = () => setActiveHelpTooltip(null);
    portalWindow.addEventListener("scroll", clearTooltip, true);
    portalWindow.addEventListener("resize", clearTooltip);
    return () => {
      portalWindow.removeEventListener("scroll", clearTooltip, true);
      portalWindow.removeEventListener("resize", clearTooltip);
    };
  }, [activeHelpTooltip, portalWindow]);

  useEffect(() => {
    if (!activeHelpTooltip?.pinned) return undefined;
    if (!portalWindow) return undefined;
    const handlePointerDown = (event: PointerEvent) => {
      const target = event.target;
      const ElementCtor = portalWindow?.Element;
      if (
        ElementCtor &&
        target instanceof ElementCtor &&
        (target.closest(".detail-label-help") ||
          target.closest(".detail-label-trigger") ||
          target.closest(".decision-help-inline"))
      ) {
        return;
      }
      setActiveHelpTooltip(null);
    };
    portalWindow.addEventListener("pointerdown", handlePointerDown, true);
    return () => portalWindow.removeEventListener("pointerdown", handlePointerDown, true);
  }, [activeHelpTooltip?.pinned, portalWindow]);

  const runtimeTooltipFor = (label: string) => {
    const runtime =
      runtimeTooltipByLabel[label] ?? runtimeTooltipByLabel[resolveTooltipBaseLabel(label)] ?? null;
    if (!runtime) return "";
    const lines = [];
    lines.push(`${tooltipLocaleText.value}: ${formatTooltipRuntimeValue(runtime.value)}`);
    if (runtime.source) {
      lines.push(`${tooltipLocaleText.source}: ${runtime.source}`);
    }
    (Array.isArray(runtime.flow) ? runtime.flow : []).forEach((line) => lines.push(line));
    return lines.join("\n");
  };

  const tooltipFor = (label: string) => {
    const base = baseTooltipFor(label);
    const runtime = runtimeTooltipFor(label);
    return [base, runtime].filter((part) => String(part || "").trim()).join("\n\n");
  };

  const resolveHelpTooltipPosition = (anchorRect: DOMRect, viewportWindow = portalWindow) => {
    if (!viewportWindow) {
      return {
        top: anchorRect.bottom + 10,
        left: anchorRect.left,
        maxWidth: 520,
        placeAbove: false,
      };
    }
    const viewportWidth = Math.max(viewportWindow.innerWidth || 0, 320);
    const viewportHeight = Math.max(viewportWindow.innerHeight || 0, 320);
    const maxWidth = Math.min(520, Math.max(280, viewportWidth - 24));
    const horizontalPadding = 12;
    const idealLeft = anchorRect.left + anchorRect.width / 2 - maxWidth / 2;
    const left = Math.min(
      Math.max(horizontalPadding, idealLeft),
      Math.max(horizontalPadding, viewportWidth - maxWidth - horizontalPadding),
    );
    const placeAbove = anchorRect.bottom > viewportHeight * 0.72;
    const top = placeAbove ? Math.max(10, anchorRect.top - 10) : anchorRect.bottom + 10;
    return { top, left, maxWidth, placeAbove };
  };

  const showHelpTooltip = (event: TooltipAnchorEvent, tooltipText: string, pinned = false) => {
    const text = String(tooltipText || "").trim();
    if (!text) return;
    const anchorRect = event.currentTarget.getBoundingClientRect();
    const anchorWindow = event.currentTarget?.ownerDocument?.defaultView || portalWindow;
    setActiveHelpTooltip({
      ...resolveHelpTooltipPosition(anchorRect, anchorWindow),
      text,
      pinned,
    });
  };

  const hideHelpTooltip = () => {
    setActiveHelpTooltip((previous) => (previous?.pinned ? previous : null));
  };

  const togglePinnedHelpTooltip = (event: TooltipToggleEvent, tooltipText: string) => {
    event.preventDefault();
    event.stopPropagation();
    const text = String(tooltipText || "").trim();
    if (!text) return;
    const ElementCtor = portalWindow?.Element || (typeof Element !== "undefined" ? Element : null);
    const anchorElement =
      ElementCtor && event.currentTarget instanceof ElementCtor ? event.currentTarget : null;
    const anchorWindow = anchorElement?.ownerDocument?.defaultView || portalWindow;
    const nextPosition = anchorElement
      ? resolveHelpTooltipPosition(anchorElement.getBoundingClientRect(), anchorWindow)
      : { top: 12, left: 12, maxWidth: 420, placeAbove: false };
    setActiveHelpTooltip((previous) => {
      if (previous?.pinned && previous?.text === text) {
        return null;
      }
      return {
        ...nextPosition,
        text,
        pinned: true,
      };
    });
  };

  const renderDetailLabel: DecisionPanelRenderDetailLabel = (
    label,
    tooltipLabelOrOptions = label,
    style,
  ) => {
    const optionsObject = isDetailLabelOptions(tooltipLabelOrOptions) ? tooltipLabelOrOptions : null;
    const tooltipLabel = optionsObject
      ? optionsObject.tooltipLabel || label
      : tooltipLabelOrOptions || label;
    const effectiveStyle = optionsObject ? optionsObject.style : style;
    const runtimeOverride = optionsObject
      ? {
          value: optionsObject.runtimeValue,
          source: optionsObject.runtimeSource,
          flow: Array.isArray(optionsObject.runtimeFlow)
            ? optionsObject.runtimeFlow
            : [optionsObject.runtimeFlow].filter(Boolean),
        }
      : null;
    const tooltipText = runtimeOverride
      ? [
          baseTooltipFor(tooltipLabel),
          `${tooltipLocaleText.value}: ${formatTooltipRuntimeValue(runtimeOverride.value)}`,
          runtimeOverride.source ? `${tooltipLocaleText.source}: ${runtimeOverride.source}` : "",
          ...(runtimeOverride.flow || []),
        ]
          .filter((part) => String(part || "").trim())
          .join("\n\n")
      : tooltipFor(tooltipLabel);
    return (
      <span className="detail-label-with-tooltip">
        <button
          type="button"
          className="detail-label-trigger"
          aria-label={tooltipText}
          style={effectiveStyle}
          onMouseEnter={(event) => showHelpTooltip(event, tooltipText, false)}
          onMouseLeave={hideHelpTooltip}
          onFocus={(event) => showHelpTooltip(event, tooltipText, false)}
          onBlur={hideHelpTooltip}
          onClick={(event) => togglePinnedHelpTooltip(event, tooltipText)}
          onKeyDown={(event) => {
            if (event.key === "Enter" || event.key === " ") {
              togglePinnedHelpTooltip(event, tooltipText);
            }
            if (event.key === "Escape") {
              setActiveHelpTooltip(null);
            }
          }}
        >
          {t(label)}
        </button>
        <button
          type="button"
          className="detail-label-help"
          aria-label={tooltipText}
          aria-expanded={Boolean(activeHelpTooltip && activeHelpTooltip.text === tooltipText)}
          onMouseEnter={(event) => showHelpTooltip(event, tooltipText, false)}
          onMouseLeave={hideHelpTooltip}
          onFocus={(event) => showHelpTooltip(event, tooltipText, false)}
          onBlur={hideHelpTooltip}
          onClick={(event) => togglePinnedHelpTooltip(event, tooltipText)}
          onKeyDown={(event) => {
            if (event.key === "Enter" || event.key === " ") {
              togglePinnedHelpTooltip(event, tooltipText);
            }
            if (event.key === "Escape") {
              setActiveHelpTooltip(null);
            }
          }}
        >
          i
        </button>
      </span>
    );
  };

  return {
    activeHelpTooltip,
    setActiveHelpTooltip,
    renderDetailLabel,
  };
}
