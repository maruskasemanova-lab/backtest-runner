import { act, renderHook, waitFor } from "@testing-library/react";
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
        authToken: "",
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
        authToken: "",
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

  it("keeps selected unified profile when profile refresh fails", async () => {
    const hydrateExecutionConfigFromPositioning = vi.fn();
    let profileCalls = 0;
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/aos-config/MU") {
        return responseJson({});
      }
      if (url === "/api/profiles/MU") {
        profileCalls += 1;
        if (profileCalls === 1) {
          return responseJson({
            ticker: "MU",
            profiles: [{ profile_id: "u1", profile_name: "Unified 1" }],
            active_profile_id: "u1",
          });
        }
        return responseJson({ detail: "temporary outage" }, false, 503);
      }
      throw new Error(`Unexpected fetch URL in test: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() =>
      useRunConfigProfiles({
        ticker: "MU",
        strategyApiUrl: "http://localhost:8001",
        authToken: "",
        activeProfileSentinel: "__ACTIVE__",
        normalizeProfileRefToken,
        normalizeAosTickerConfig,
        hydrateExecutionConfigFromPositioning,
      }),
    );

    await waitFor(() => {
      expect(result.current.unifiedProfilesLoading).toBe(false);
    });
    expect(result.current.selectedUnifiedProfileId).toBe("__ACTIVE__");

    act(() => {
      result.current.setSelectedUnifiedProfileId("u1");
    });
    expect(result.current.selectedUnifiedProfileId).toBe("u1");

    await act(async () => {
      await result.current.fetchUnifiedProfiles("MU");
    });

    expect(result.current.selectedUnifiedProfileId).toBe("u1");
    expect(result.current.unifiedProfilesResolved).toBe(true);
    expect(result.current.unifiedProfilesError).toBe("Failed to load unified profiles.");
  });

  it("adds Authorization header to unified profile calls when auth token is present", async () => {
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
        return responseJson({ success: true });
      }
      throw new Error(`Unexpected fetch URL in test: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() =>
      useRunConfigProfiles({
        ticker: "MU",
        strategyApiUrl: "http://localhost:8001",
        authToken: "test-token",
        activeProfileSentinel: "__ACTIVE__",
        normalizeProfileRefToken,
        normalizeAosTickerConfig,
        hydrateExecutionConfigFromPositioning,
      }),
    );

    await waitFor(() => {
      expect(result.current.unifiedProfilesLoading).toBe(false);
    });

    await act(async () => {
      await result.current.applyUnifiedProfile("MU", "u1", {
        applyNow: true,
        applyExecution: true,
      });
    });

    const profileFetchCall = fetchMock.mock.calls.find(
      (args) => String(args[0]) === "/api/profiles/MU",
    );
    expect(profileFetchCall?.[1]).toMatchObject({
      headers: { Authorization: "Bearer test-token" },
    });

    const applyFetchCall = fetchMock.mock.calls.find(
      (args) => String(args[0]) === "/api/profiles/apply",
    );
    expect(applyFetchCall?.[1]).toMatchObject({
      headers: {
        "Content-Type": "application/json",
        Authorization: "Bearer test-token",
      },
    });
  });
});
