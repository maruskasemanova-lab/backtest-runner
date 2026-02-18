import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useRunConfigProfiles } from "./useRunConfigProfiles";

const responseJson = (payload: unknown, ok = true, status = 200) =>
  ({
    ok,
    status,
    json: async () => payload,
  }) as Response;

const normalizeProfileRefToken = (value: unknown) => String(value || "").trim();
const normalizeAosTickerConfig = (payload: unknown) =>
  payload && typeof payload === "object" && !Array.isArray(payload)
    ? (payload as Record<string, any>)
    : {};

describe("useRunConfigProfiles unified-only flow", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("does not call legacy profile endpoints when unified endpoint fails", async () => {
    const hydrateExecutionConfigFromPositioning = vi.fn();
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/aos-config/MU") {
        return responseJson({});
      }
      if (url === "/api/profiles/MU") {
        return responseJson({ detail: "not found" }, false, 404);
      }
      throw new Error(`Unexpected fetch URL in test: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() =>
      useRunConfigProfiles({
        ticker: "MU",
        strategyApiUrl: "http://localhost:8001",
        activeProfileSentinel: "__ACTIVE__",
        normalizeProfileRefToken,
        normalizeAosTickerConfig,
        hydrateExecutionConfigFromPositioning,
      }),
    );

    await waitFor(() => {
      expect(result.current.unifiedProfilesLoading).toBe(false);
    });

    expect(result.current.unifiedProfilesError).toBe("Failed to load unified profiles.");
    const calledUrls = fetchMock.mock.calls.map((args) => String(args[0]));
    expect(calledUrls).not.toContain("/api/strategy-combos/MU");
    expect(calledUrls).not.toContain("/api/adaptive-tuner/options/MU");
  });

  it("does not fallback to legacy apply endpoints when unified apply fails", async () => {
    const hydrateExecutionConfigFromPositioning = vi.fn();
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/aos-config/MU") {
        return responseJson({});
      }
      if (url === "/api/profiles/MU") {
        return responseJson({
          ticker: "MU",
          profiles: [{ profile_id: "u1", profile_name: "Unified 1" }],
          active_profile_id: "u1",
        });
      }
      if (url === "/api/profiles/apply") {
        return responseJson({ detail: "Unified profile not found" }, false, 404);
      }
      throw new Error(`Unexpected fetch URL in test: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() =>
      useRunConfigProfiles({
        ticker: "MU",
        strategyApiUrl: "http://localhost:8001",
        activeProfileSentinel: "__ACTIVE__",
        normalizeProfileRefToken,
        normalizeAosTickerConfig,
        hydrateExecutionConfigFromPositioning,
      }),
    );

    await waitFor(() => {
      expect(result.current.unifiedProfilesLoading).toBe(false);
    });

    await expect(
      result.current.applyUnifiedProfile("MU", "u1", {
        applyNow: true,
        applyExecution: false,
      }),
    ).rejects.toThrow("Unified profile not found");

    const calledUrls = fetchMock.mock.calls.map((args) => String(args[0]));
    expect(calledUrls).not.toContain("/api/strategy-combos/apply");
    expect(calledUrls).not.toContain("/api/adaptive-tuner/profiles/apply");
  });
});
