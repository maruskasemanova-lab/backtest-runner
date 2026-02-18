import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useAdaptiveTunerController } from "./useAdaptiveTunerController";

const buildOptionsPayload = (ticker: string) => ({
  ticker,
  default_date_from: "2026-02-03",
  default_date_to: "2026-02-05",
  profiles: [],
  active_profile_id: null,
  ohlcv_range: { start: "2026-02-03", end: "2026-02-05", total_days: 3 },
  l2_range: { start: "2026-02-03", end: "2026-02-05", total_days: 3 },
  l2_overlap_range: { start: "2026-02-03", end: "2026-02-05", total_days: 3 },
});

const responseJson = (payload: unknown, ok = true, status = 200) =>
  ({
    ok,
    status,
    json: async () => payload,
  }) as Response;

describe("useAdaptiveTunerController ticker selection", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("keeps locally selected ticker while parent selectedTicker is still stale", async () => {
    const onTickerChange = vi.fn();
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/available-data?refresh=1") {
        return responseJson({ tickers: ["MU", "NVDA"] });
      }
      if (url === "/api/adaptive-tuner?limit=20") {
        return responseJson([]);
      }
      if (url === "/api/adaptive-tuner/options/MU") {
        return responseJson(buildOptionsPayload("MU"));
      }
      if (url === "/api/adaptive-tuner/options/NVDA") {
        return responseJson(buildOptionsPayload("NVDA"));
      }
      throw new Error(`Unhandled fetch URL in test: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() =>
      useAdaptiveTunerController({
        selectedTicker: "MU",
        onTickerChange,
      }),
    );

    await waitFor(() => {
      expect(result.current.form.ticker).toBe("MU");
    });

    await act(async () => {
      await result.current.handleTickerChange("NVDA");
    });

    expect(result.current.form.ticker).toBe("NVDA");
    expect(onTickerChange).toHaveBeenCalledWith("NVDA");

    const optionCalls = fetchMock.mock.calls
      .map((args) => String(args[0]))
      .filter((url) => url.startsWith("/api/adaptive-tuner/options/"));
    expect(optionCalls[optionCalls.length - 1]).toBe("/api/adaptive-tuner/options/NVDA");
  });

  it("does not overwrite a user-picked ticker when initial available-data request resolves later", async () => {
    const onTickerChange = vi.fn();
    let resolveAvailableData: ((value: Response) => void) | null = null;
    const availableDataPromise = new Promise<Response>((resolve) => {
      resolveAvailableData = resolve;
    });

    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/available-data?refresh=1") {
        return availableDataPromise;
      }
      if (url === "/api/adaptive-tuner?limit=20") {
        return responseJson([]);
      }
      if (url === "/api/adaptive-tuner/options/NVDA") {
        return responseJson(buildOptionsPayload("NVDA"));
      }
      if (url === "/api/adaptive-tuner/options/MU") {
        return responseJson(buildOptionsPayload("MU"));
      }
      throw new Error(`Unhandled fetch URL in test: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() =>
      useAdaptiveTunerController({
        onTickerChange,
      }),
    );

    await act(async () => {
      const selectTickerPromise = result.current.handleTickerChange("NVDA");
      resolveAvailableData?.(responseJson({ tickers: ["MU", "NVDA"] }));
      await selectTickerPromise;
    });

    await waitFor(() => {
      expect(result.current.form.ticker).toBe("NVDA");
    });

    const optionCalls = fetchMock.mock.calls
      .map((args) => String(args[0]))
      .filter((url) => url.startsWith("/api/adaptive-tuner/options/"));

    expect(optionCalls.every((url) => url.endsWith("/NVDA"))).toBe(true);
    expect(onTickerChange).toHaveBeenCalledWith("NVDA");
  });
});

