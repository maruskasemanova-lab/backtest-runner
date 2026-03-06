import { describe, expect, it } from "vitest";

import { extractRunBarAnalysis } from "./extractRunBarAnalysis";

describe("extractRunBarAnalysis", () => {
  it("keeps non-score evidence diagnostics from nested analysis payloads", () => {
    const snapshot = extractRunBarAnalysis({
      timestamp: "2026-02-17T15:00:00Z",
      analysis: {
        level_context: { quality_score: 7.2 },
        context_risk: { room_pct: 0.21 },
        entry_quality_diagnostics: { grade: "A" },
        tcbbo_confirmation: { passed: true },
        intrabar_confirmation: { coverage_points: 12 },
        micro_confirmation: { regime: "trend" },
      },
    });

    expect(snapshot).toMatchObject({
      timestamp: "2026-02-17T15:00:00Z",
      level_context: { quality_score: 7.2 },
      context_risk: { room_pct: 0.21 },
      entry_quality_diagnostics: { grade: "A" },
      tcbbo_confirmation: { passed: true },
      intrabar_confirmation: { coverage_points: 12 },
      micro_confirmation: { regime: "trend" },
    });
  });

  it("extracts checkpoint-only entry diagnostics without dropping checkpoint metadata", () => {
    const snapshot = extractRunBarAnalysis({
      offset_sec: 5,
      provisional: true,
      timestamp: "2026-02-17T15:05:05Z",
      level_context: { entry_quality: 6.5 },
      entry_quality_diagnostics: { grade: "B" },
      tcbbo_confirmation: { passed: false },
    });

    expect(snapshot).toMatchObject({
      checkpoint_mode: true,
      checkpoint_offset_sec: 5,
      provisional: true,
      level_context: { entry_quality: 6.5 },
      entry_quality_diagnostics: { grade: "B" },
      tcbbo_confirmation: { passed: false },
    });
  });
});
