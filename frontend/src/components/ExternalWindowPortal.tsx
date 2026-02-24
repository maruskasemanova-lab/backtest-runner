import { ReactNode, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

interface ExternalWindowPortalProps {
  isOpen: boolean;
  title: string;
  windowName: string;
  onClose?: () => void;
  width?: number;
  height?: number;
  children: ReactNode;
}

const cloneStylesIntoWindow = (sourceDoc: Document, targetDoc: Document) => {
  const styleNodes = sourceDoc.querySelectorAll('link[rel="stylesheet"], style');
  styleNodes.forEach((node) => {
    if (node.tagName.toLowerCase() === "link") {
      const sourceLink = node as HTMLLinkElement;
      const link = targetDoc.createElement("link");
      link.rel = "stylesheet";
      link.href = sourceLink.href;
      if (sourceLink.media) link.media = sourceLink.media;
      targetDoc.head.appendChild(link);
      return;
    }

    const sourceStyle = node as HTMLStyleElement;
    const style = targetDoc.createElement("style");
    style.textContent = sourceStyle.textContent;
    targetDoc.head.appendChild(style);
  });
};

export default function ExternalWindowPortal({
  isOpen,
  title,
  windowName,
  onClose,
  width = 560,
  height = 760,
  children,
}: ExternalWindowPortalProps) {
  const childWindowRef = useRef<Window | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const onCloseRef = useRef(onClose);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  useEffect(() => {
    if (!isOpen) {
      setReady(false);
      if (childWindowRef.current && !childWindowRef.current.closed) {
        childWindowRef.current.close();
      }
      childWindowRef.current = null;
      containerRef.current = null;
      return;
    }
    if (typeof window === "undefined") return;

    const popupLeft = Math.max(0, window.screenX + Math.round((window.outerWidth - width) / 2));
    const popupTop = Math.max(0, window.screenY + Math.round((window.outerHeight - height) / 2));
    const features = [
      `width=${Math.max(360, Math.round(width))}`,
      `height=${Math.max(360, Math.round(height))}`,
      `left=${popupLeft}`,
      `top=${popupTop}`,
      "resizable=yes",
      "scrollbars=yes",
    ].join(",");

    const childWindow = window.open("", windowName, features);
    if (!childWindow) {
      onCloseRef.current?.();
      return;
    }

    childWindowRef.current = childWindow;
    childWindow.document.title = title;
    childWindow.document.documentElement.className = window.document.documentElement.className;
    childWindow.document.body.className = window.document.body.className;
    childWindow.document.body.innerHTML = "";
    childWindow.document.body.style.margin = "0";
    childWindow.document.body.style.width = "100vw";
    childWindow.document.body.style.height = "100vh";
    childWindow.document.body.style.overflow = "hidden";
    childWindow.document.documentElement.style.width = "100%";
    childWindow.document.documentElement.style.height = "100%";
    cloneStylesIntoWindow(window.document, childWindow.document);

    const container = childWindow.document.createElement("div");
    container.style.width = "100%";
    container.style.height = "100%";
    container.style.display = "flex";
    container.style.flexDirection = "column";
    childWindow.document.body.appendChild(container);
    containerRef.current = container;
    setReady(true);

    const handleClose = () => {
      childWindowRef.current = null;
      containerRef.current = null;
      setReady(false);
      onCloseRef.current?.();
    };
    childWindow.addEventListener("beforeunload", handleClose);

    const closeCheckInterval = window.setInterval(() => {
      if (childWindow.closed) {
        window.clearInterval(closeCheckInterval);
        handleClose();
      }
    }, 400);

    return () => {
      window.clearInterval(closeCheckInterval);
      childWindow.removeEventListener("beforeunload", handleClose);
      if (!childWindow.closed) childWindow.close();
      if (childWindowRef.current === childWindow) childWindowRef.current = null;
      if (containerRef.current === container) containerRef.current = null;
      setReady(false);
    };
  }, [isOpen, width, height, windowName]);

  useEffect(() => {
    if (childWindowRef.current && !childWindowRef.current.closed) {
      childWindowRef.current.document.title = title;
    }
  }, [title]);

  if (!isOpen || !ready || !containerRef.current) return null;
  return createPortal(children, containerRef.current);
}
