import { describe, expect, it } from "vitest";
import {
  RUN_CONFIG_DRAFT_VERSION,
  buildNormalizedIntradayLevels,
  buildDefaultRunConfig,
  buildRunKeyFromStartPayload,
  resolveRunDateLabel,
  mergeRunConfigWithDefaults,
} from "./runConfigHelpers";

describe("runConfigHelpers draft migrations", () => {
  it("enables MU entry-quality gate for pre-v8 drafts", () => {
    const defaults = buildDefaultRunConfig();
    const merged = mergeRunConfigWithDefaults(
      {
        ticker: "MU",
        intraday_levels_enabled: true,
        intraday_levels_entry_quality_enabled: false,
      },
      defaults,
      7,
    );
    expect(merged.intraday_levels_entry_quality_enabled).toBe(true);
  });

  it("does not force entry-quality gate for non-MU pre-v8 drafts", () => {
    const defaults = buildDefaultRunConfig();
    const merged = mergeRunConfigWithDefaults(
      {
        ticker: "AAPL",
        intraday_levels_enabled: true,
        intraday_levels_entry_quality_enabled: false,
      },
      defaults,
      7,
    );
    expect(merged.intraday_levels_entry_quality_enabled).toBe(false);
  });

  it("respects explicit MU setting for v8 drafts", () => {
    const defaults = buildDefaultRunConfig();
    const merged = mergeRunConfigWithDefaults(
      {
        ticker: "MU",
        intraday_levels_enabled: true,
        intraday_levels_entry_quality_enabled: false,
      },
      defaults,
      RUN_CONFIG_DRAFT_VERSION,
    );
    expect(merged.intraday_levels_entry_quality_enabled).toBe(false);
  });
});

describe("buildNormalizedIntradayLevels", () => {
  it("forces MU entry-quality gate when intraday levels are enabled", () => {
    const normalized = buildNormalizedIntradayLevels({
      ticker: "MU",
      intraday_levels_enabled: true,
      intraday_levels_entry_quality_enabled: false,
    });
    expect(normalized.intraday_levels_entry_quality_enabled).toBe(true);
  });

  it("keeps entry-quality gate value for non-MU tickers", () => {
    const normalized = buildNormalizedIntradayLevels({
      ticker: "AAPL",
      intraday_levels_enabled: true,
      intraday_levels_entry_quality_enabled: false,
    });
    expect(normalized.intraday_levels_entry_quality_enabled).toBe(false);
  });
});

describe("run key helpers", () => {
  it("keeps range label semantics when date_from/date_to are provided", () => {
    expect(
      resolveRunDateLabel({
        date_from: "2026-02-09",
        date_to: "2026-02-09",
      }),
    ).toBe("2026-02-09_to_2026-02-09");
  });

  it("uses single-day label when only date is provided", () => {
    expect(resolveRunDateLabel({ date: "2026-02-09" })).toBe("2026-02-09");
  });

  it("builds run key from start payload identity fields", () => {
    expect(
      buildRunKeyFromStartPayload({
        run_id: "backtest-123",
        ticker: "mu",
        date_from: "2026-02-09",
        date_to: "2026-02-13",
      }),
    ).toBe("backtest-123:MU:2026-02-09_to_2026-02-13");
  });
});
