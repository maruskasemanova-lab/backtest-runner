import { afterEach, describe, expect, it } from "vitest";
import {
  buildStrategyAnalyzerDayUrl,
  readInitialAppUrlState,
} from "./appShared";

const ORIGINAL_PATH = `${window.location.pathname}${window.location.search}${window.location.hash}`;

describe("appShared strategy analyzer URL handling", () => {
  afterEach(() => {
    window.history.replaceState({}, "", ORIGINAL_PATH || "/");
  });

  it("reads variant fallback from diag_variant when sa_variant is absent", () => {
    window.history.replaceState(
      {},
      "",
      "/?view=strategy-analyzer&sa_ticker=MU&sa_day=2026-01-29&diag_variant=variant%3Ano_context_risk",
    );

    const state = readInitialAppUrlState();
    expect(state.strategyAnalyzerOpenDayRequest?.variantKey).toBe("variant:no_context_risk");
  });

  it("writes sa_variant when building strategy analyzer URL", () => {
    window.history.replaceState({}, "", "/?view=diagnostics");

    const nextUrl = buildStrategyAnalyzerDayUrl({
      ticker: "MU",
      isoDate: "2026-01-29",
      runKey: "analyzer-no_context_risk-1:MU:2026-01-29",
      variantKey: "variant:no_context_risk",
    });

    expect(nextUrl).toContain("view=strategy-analyzer");
    expect(nextUrl).toContain("sa_variant=variant%3Ano_context_risk");
  });
});
