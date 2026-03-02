import { act, renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { NuqsTestingAdapter, type UrlUpdateEvent } from "nuqs/adapters/testing";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import useDiagnosticCalendarViewModel from "./useDiagnosticCalendarViewModel";

const responseJson = (payload: unknown, ok = true, status = 200) =>
  ({
    ok,
    status,
    json: async () => payload,
  }) as Response;

const buildWrapper = ({
  onUrlUpdate,
  searchParams = "",
}: {
  onUrlUpdate: (event: UrlUpdateEvent) => void;
  searchParams?: string;
}) => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      <NuqsTestingAdapter onUrlUpdate={onUrlUpdate} searchParams={searchParams}>
        {children}
      </NuqsTestingAdapter>
    </QueryClientProvider>
  );
};

describe("useDiagnosticCalendarViewModel URL sync", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("uses nuqs with the existing diagnostic query param keys", async () => {
    const onUrlUpdate = vi.fn((event: UrlUpdateEvent) => event);
    const fetchMock = vi.fn(async () =>
      responseJson({
        day_results: [],
        filter_options: {
          run_ids: [
            { run_id: "run-7" },
            { run_id: "run-9" },
          ],
          unified_profiles: [
            { profile_id: "profile-a" },
            { profile_id: "profile-b" },
          ],
        },
        split: {
          end: "2025-01-31",
          start: "2025-01-01",
        },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useDiagnosticCalendarViewModel(), {
      wrapper: buildWrapper({
        onUrlUpdate,
        searchParams: "?diag_ticker=nvda&diag_limit=13&diag_profile=profile-a&diag_run_id=run-7&diag_trade_view=adaptive",
      }),
    });

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledOnce();
    });

    expect(result.current.filterModel.appliedFilters).toEqual({
      adaptiveProfileId: "profile-a",
      historyLimit: "13",
      runId: "run-7",
      ticker: "NVDA",
    });

    act(() => {
      result.current.filterModel.applyDraftFilters({
        adaptiveProfileId: "profile-b",
        historyLimit: "21",
        runId: "run-9",
        ticker: "amd",
      });
    });

    await waitFor(() => {
      expect(onUrlUpdate).toHaveBeenCalled();
    });

    const lastUrlUpdate = onUrlUpdate.mock.calls[onUrlUpdate.mock.calls.length - 1]?.[0];
    expect(lastUrlUpdate?.queryString).toContain("diag_ticker=AMD");
    expect(lastUrlUpdate?.queryString).toContain("diag_limit=21");
    expect(lastUrlUpdate?.queryString).toContain("diag_profile=profile-b");
    expect(lastUrlUpdate?.queryString).toContain("diag_run_id=run-9");
    expect(lastUrlUpdate?.queryString).toContain("diag_trade_view=adaptive");

    act(() => {
      result.current.filterModel.setTradeViewMode("all");
    });

    await waitFor(() => {
      const nextUrlUpdate = onUrlUpdate.mock.calls[onUrlUpdate.mock.calls.length - 1]?.[0];
      expect(nextUrlUpdate?.queryString).not.toContain("diag_trade_view=");
    });

    act(() => {
      result.current.filterModel.setVariantFilter("variant:baseline");
    });

    await waitFor(() => {
      const variantUrlUpdate = onUrlUpdate.mock.calls[onUrlUpdate.mock.calls.length - 1]?.[0];
      expect(variantUrlUpdate?.queryString).toContain("diag_variant=variant:baseline");
      expect(variantUrlUpdate?.queryString).not.toContain("diag_run_id=");
    });
  });
});
