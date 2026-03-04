import { describe, expect, it } from "vitest";

import { toUnixSeconds } from "./utils";

describe("toUnixSeconds", () => {
  it("normalizes numeric epoch precision to seconds", () => {
    expect(toUnixSeconds(1_769_677_200)).toBe(1_769_677_200);
    expect(toUnixSeconds(1_769_677_200_000)).toBe(1_769_677_200);
    expect(toUnixSeconds(1_769_677_200_000_000)).toBe(1_769_677_200);
    expect(toUnixSeconds(1_769_677_200_000_000_000)).toBe(1_769_677_200);
  });

  it("normalizes numeric timestamp strings with ms/us/ns precision", () => {
    expect(toUnixSeconds("1769677200000")).toBe(1_769_677_200);
    expect(toUnixSeconds("1769677200000000")).toBe(1_769_677_200);
    expect(toUnixSeconds("1769677200000000000")).toBe(1_769_677_200);
  });

  it("normalizes object timestamp fields", () => {
    expect(toUnixSeconds({ timestamp: 1_769_677_200_000_000_000 })).toBe(1_769_677_200);
    expect(toUnixSeconds({ time: 1_769_677_200_000 })).toBe(1_769_677_200);
  });

  it("parses ISO timestamps with nanosecond fractions", () => {
    const parsed = toUnixSeconds("2026-01-29T09:00:00.000000000");
    expect(parsed).toBe(1_769_677_200);
  });

  it("treats ISO timestamps without timezone as UTC", () => {
    expect(toUnixSeconds("2026-01-29T21:00:00")).toBe(1_769_720_400);
  });

  it("preserves explicit timezone offsets in ISO timestamps", () => {
    expect(toUnixSeconds("2026-01-29T21:00:00+01:00")).toBe(1_769_716_800);
  });
});
