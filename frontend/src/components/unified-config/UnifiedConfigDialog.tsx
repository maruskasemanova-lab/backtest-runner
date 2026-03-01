import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import {
  UNIFIED_CONFIG_SECTIONS,
  type SnapshotEntry,
  type SnapshotSection,
  type UnifiedConfigDialogProps,
} from "./types";
import { UnifiedConfigSidebar } from "./UnifiedConfigSidebar";
import { UnifiedConfigSections } from "./UnifiedConfigSections";
import { useUnifiedConfigNavigation } from "./useUnifiedConfigNavigation";

/* ── helpers ── */

const isPlainRecord = (v: any): v is Record<string, any> =>
  Boolean(v) && typeof v === "object" && !Array.isArray(v);

const toPrettyJson = (value: any) => {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
};

const toSnapshotEntries = (config: any): SnapshotEntry[] => {
  if (!isPlainRecord(config)) return [];
  return Object.keys(config)
    .sort((a, b) => a.localeCompare(b))
    .map((key) => {
      const value = config[key];
      if (typeof value === "boolean") {
        return {
          key,
          kind: "boolean" as const,
          boolValue: value,
          textValue: value ? "true" : "false",
          rows: 1,
        };
      }
      if (
        typeof value === "string" ||
        typeof value === "number" ||
        typeof value === "bigint" ||
        value === null ||
        typeof value === "undefined"
      ) {
        const textValue =
          value === null
            ? "null"
            : typeof value === "undefined"
              ? ""
              : String(value);
        return {
          key,
          kind: "scalar" as const,
          boolValue: false,
          textValue,
          rows: 1,
        };
      }
      const textValue = toPrettyJson(value);
      const lineCount = textValue.split("\n").length;
      return {
        key,
        kind: "complex" as const,
        boolValue: false,
        textValue,
        rows: Math.min(14, Math.max(3, lineCount)),
      };
    });
};

/* ── main component ── */

export function UnifiedConfigDialog({
  isOpen,
  onClose,
  config,
  handleChange,
  momentumSleeves,
  onMomentumSleeveChange,
  onAddMomentumSleeve,
  onRemoveMomentumSleeve,
  strategyApiUrl,
  selectedTicker,
  activeProfile,
  activeProfileId,
  activeProfileName,
  readOnly = false,
  title,
  subtitle,
  snapshotSections = [],
}: UnifiedConfigDialogProps) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  const nav = useUnifiedConfigNavigation();

  // Lock body scroll while open
  useEffect(() => {
    if (!isOpen) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [isOpen]);

  // Escape key
  useEffect(() => {
    if (!isOpen) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [isOpen, onClose]);

  if (!isOpen || !mounted) return null;

  const safeConfig = isPlainRecord(config) ? config : {};
  const safeHandleChange =
    typeof handleChange === "function" ? handleChange : () => {};
  const safeMomentumSleeves = Array.isArray(momentumSleeves)
    ? momentumSleeves
    : [];
  const safeOnMomentumSleeveChange =
    typeof onMomentumSleeveChange === "function"
      ? onMomentumSleeveChange
      : () => {};
  const safeOnAddMomentumSleeve =
    typeof onAddMomentumSleeve === "function"
      ? onAddMomentumSleeve
      : () => {};
  const safeOnRemoveMomentumSleeve =
    typeof onRemoveMomentumSleeve === "function"
      ? onRemoveMomentumSleeve
      : () => {};

  const ticker = String(selectedTicker || "").trim().toUpperCase();
  const apiUrl = String(strategyApiUrl || "http://localhost:8001").replace(
    /\/+$/,
    "",
  );

  // Snapshot mode (read-only run config snapshots)
  const normalizedSnapshotSections: SnapshotSection[] = Array.isArray(
    snapshotSections,
  )
    ? snapshotSections
        .filter(
          (s) =>
            isPlainRecord(s?.config) &&
            Object.keys(s.config || {}).length > 0,
        )
        .map((s) => ({
          title: String(s?.title || "Snapshot"),
          config: s?.config || {},
          description:
            typeof s?.description === "string" ? s.description : "",
        }))
    : [];
  const isSnapshotMode = Boolean(
    readOnly && normalizedSnapshotSections.length,
  );

  const resolvedTitle = title || (isSnapshotMode
    ? "Run Config Snapshot"
    : `Strategy Configuration${ticker ? ` \u2014 ${ticker}` : ""}`);
  const resolvedSubtitle = subtitle || (isSnapshotMode
    ? "Read-only configuration captured for this run."
    : "All settings organized by trading impact. Most important settings are at the top.");

  return createPortal(
    <div
      className="unified-config-overlay"
      onClick={onClose}
    >
      <div
        className="unified-config-shell card"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div
          className="card-header flex justify-between items-center"
          style={{ padding: "16px 24px" }}
        >
          <div>
            <h2 className="card-title text-lg">{resolvedTitle}</h2>
            <div className="text-xs text-gray-400 mt-1">
              {resolvedSubtitle}
            </div>
          </div>
          <button type="button" className="btn btn-secondary" onClick={onClose}>
            {isSnapshotMode ? "Close" : "Close / Done"}
          </button>
        </div>

        {/* Body */}
        {isSnapshotMode ? (
          <div
            className="card-body flex-1 overflow-y-auto"
            style={{ padding: "24px" }}
          >
            <SnapshotContent sections={normalizedSnapshotSections} />
          </div>
        ) : (
          <div className="unified-config-body">
            <UnifiedConfigSidebar
              sections={UNIFIED_CONFIG_SECTIONS}
              activeSectionId={nav.activeSectionId}
              onSectionClick={nav.scrollToSection}
            />
            <div
              ref={nav.contentRef}
              className="unified-config-content"
            >
              <UnifiedConfigSections
                config={safeConfig}
                handleChange={safeHandleChange}
                momentumSleeves={safeMomentumSleeves}
                onMomentumSleeveChange={safeOnMomentumSleeveChange}
                onAddMomentumSleeve={safeOnAddMomentumSleeve}
                onRemoveMomentumSleeve={safeOnRemoveMomentumSleeve}
                strategyApiUrl={apiUrl}
                selectedTicker={ticker}
                activeProfile={activeProfile}
                activeProfileId={activeProfileId}
                activeProfileName={activeProfileName}
                readOnly={readOnly}
                setSectionRef={nav.setSectionRef}
              />
            </div>
          </div>
        )}
      </div>
    </div>,
    document.body,
  );
}

/* ── Snapshot mode content (preserved from FullscreenConfigDialog) ── */

function SnapshotContent({ sections }: { sections: SnapshotSection[] }) {
  return (
    <div className="flex flex-col gap-4 run-config-form">
      {sections.map((section, index) => {
        const entries = toSnapshotEntries(section.config);
        return (
          <div
            className="tw-panel"
            key={`snapshot-section-${index}-${section.title}`}
          >
            <div className="tw-panel-title">{section.title}</div>
            {section.description ? (
              <div className="text-xs text-gray-400 mt-2">
                {section.description}
              </div>
            ) : null}
            {entries.length ? (
              <div className="tw-grid-fit-190" style={{ marginTop: "12px" }}>
                {entries.map((entry) =>
                  renderSnapshotField(entry, `snapshot-${index}`),
                )}
              </div>
            ) : (
              <div className="text-xs text-slate-500 italic mt-2">
                No values captured.
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function renderSnapshotField(entry: SnapshotEntry, fieldPrefix: string) {
  const fieldId = `${fieldPrefix}-${entry.key.replace(/[^a-zA-Z0-9_-]/g, "_")}`;
  const formattedLabel = entry.key.replace(/_/g, " ");

  if (entry.kind === "boolean") {
    return (
      <div className="form-group" key={`${fieldPrefix}-${entry.key}`}>
        <label className="field-row" htmlFor={fieldId}>
          <span style={{ textTransform: "capitalize" }}>{formattedLabel}</span>
          <input
            id={fieldId}
            type="checkbox"
            checked={entry.boolValue}
            disabled
            readOnly
          />
        </label>
      </div>
    );
  }

  if (entry.kind === "complex") {
    return (
      <div className="form-group" key={`${fieldPrefix}-${entry.key}`}>
        <label htmlFor={fieldId} style={{ textTransform: "capitalize" }}>
          {formattedLabel}
        </label>
        <textarea
          id={fieldId}
          value={entry.textValue}
          rows={entry.rows}
          disabled
          readOnly
          style={{
            background: "rgba(15, 23, 42, 0.5)",
            fontFamily: "var(--font-mono)",
          }}
        />
      </div>
    );
  }

  return (
    <div className="form-group" key={`${fieldPrefix}-${entry.key}`}>
      <label htmlFor={fieldId} style={{ textTransform: "capitalize" }}>
        {formattedLabel}
      </label>
      <input
        id={fieldId}
        type="text"
        value={entry.textValue}
        disabled
        readOnly
        style={{
          background: "rgba(15, 23, 42, 0.5)",
          fontFamily: "var(--font-mono)",
        }}
      />
    </div>
  );
}
