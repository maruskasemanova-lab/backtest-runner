import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useStrategyAnalyzerTickerCatalog } from "./useStrategyAnalyzerTickerCatalog";

const responseJson = (payload: unknown, ok = true, status = 200) =>
  ({
    ok,
    status,
    json: async () => payload,
  }) as Response;

describe("useStrategyAnalyzerTickerCatalog", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("does not clobber an explicit one-day analyzer range when catalog data refreshes", async () => {
    let resolveFetch: ((value: Response) => void) | null = null;
    const fetchMock = vi.fn(
      () =>
        new Promise<Response>((resolve) => {
          resolveFetch = resolve;
        }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const onTickerChange = vi.fn();
    const setTicker = vi.fn();
    const setDateFrom = vi.fn();
    const setDateTo = vi.fn();
    const resetForTickerChange = vi.fn();

    const { result, rerender } = renderHook(
      (props: {
        selectedTicker: string | null;
        ticker: string;
        dateFrom: string;
        dateTo: string;
      }) =>
        useStrategyAnalyzerTickerCatalog({
          ...props,
          onTickerChange,
          setTicker,
          setDateFrom,
          setDateTo,
          resetForTickerChange,
        }),
      {
        initialProps: {
          selectedTicker: "MU",
          ticker: "MU",
          dateFrom: "",
          dateTo: "",
        },
      },
    );

    rerender({
        selectedTicker: "MU",
        ticker: "MU",
        dateFrom: "2026-02-17",
        dateTo: "2026-02-17",
    });

    resolveFetch?.(
      responseJson({
        date_ranges: {
          MU: {
            ohlcv_start: "2025-08-01",
            ohlcv_end: "2026-02-25",
          },
        },
      }),
    );

    await waitFor(() => {
      expect(result.current.loadingTickers).toBe(false);
    });

    expect(fetchMock).toHaveBeenCalledWith("/api/available-data", { cache: "no-store" });
    expect(setTicker).not.toHaveBeenCalled();
    expect(onTickerChange).not.toHaveBeenCalled();
    expect(setDateFrom).not.toHaveBeenCalled();
    expect(setDateTo).not.toHaveBeenCalled();
  });

  it("seeds the full available range when the analyzer does not have a local date scope yet", async () => {
    const fetchMock = vi.fn(async () =>
      responseJson({
        date_ranges: {
          MU: {
            ohlcv_start: "2025-08-01",
            ohlcv_end: "2026-02-25",
          },
        },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const onTickerChange = vi.fn();
    const setTicker = vi.fn();
    const setDateFrom = vi.fn();
    const setDateTo = vi.fn();
    const resetForTickerChange = vi.fn();

    const { result } = renderHook(() =>
      useStrategyAnalyzerTickerCatalog({
        selectedTicker: "MU",
        ticker: "MU",
        dateFrom: "",
        dateTo: "",
        onTickerChange,
        setTicker,
        setDateFrom,
        setDateTo,
        resetForTickerChange,
      }),
    );

    await waitFor(() => {
      expect(result.current.loadingTickers).toBe(false);
    });

    expect(setDateFrom).toHaveBeenCalledWith("2025-08-01");
    expect(setDateTo).toHaveBeenCalledWith("2026-02-25");
  });
});
