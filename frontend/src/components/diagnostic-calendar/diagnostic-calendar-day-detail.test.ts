import { describe, expect, it } from "vitest";
import { buildSelectedDayAnalyzerPayload } from "./diagnostic-calendar-day-detail";

describe("buildSelectedDayAnalyzerPayload", () => {
  it("carries context-risk variant key when run maps to a known variant", () => {
    const payload = buildSelectedDayAnalyzerPayload({
      selectedDate: "2026-01-29",
      selectedRunRecord: {
        run_id: "analyzer-no_context_risk-123",
        run_key: "analyzer-no_context_risk-123:MU:2026-01-29",
      } as any,
      ticker: "mu",
    });

    expect(payload).toEqual({
      ticker: "MU",
      isoDate: "2026-01-29",
      runKey: "analyzer-no_context_risk-123:MU:2026-01-29",
      runId: "analyzer-no_context_risk-123",
      variantKey: "variant:no_context_risk",
      dateFrom: null,
      dateTo: null,
    });
  });

  it("extracts dateFrom/dateTo from multi-day run_key", () => {
    const payload = buildSelectedDayAnalyzerPayload({
      selectedDate: "2026-01-29",
      selectedRunRecord: {
        run_id: "run-1",
        run_key: "run-1:MU:2026-01-27_to_2026-02-03",
      } as any,
      ticker: "MU",
    });

    expect(payload?.dateFrom).toBe("2026-01-27");
    expect(payload?.dateTo).toBe("2026-02-03");
    expect(payload?.isoDate).toBe("2026-01-29");
  });

  it("does not attach variant key for non-variant profile identities", () => {
    const payload = buildSelectedDayAnalyzerPayload({
      selectedDate: "2026-01-29",
      selectedRunRecord: {
        run_id: "run-1",
        run_key: "run-1:MU:2026-01-29",
        unified_profile_id: "profile-xyz",
      } as any,
      ticker: "MU",
    });

    expect(payload?.variantKey).toBeNull();
  });
});
