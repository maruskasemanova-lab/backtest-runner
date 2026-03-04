import { describe, expect, it } from "vitest";

import { mergeRunStateWithStreamBar } from "./appRunStateCollectionShared";

describe("mergeRunStateWithStreamBar", () => {
  it("does not regress current_bar_index on delayed stream updates", () => {
    const previousState = {
      current_bar_index: 897,
      total_bars: 897,
      progress_pct: 100,
      is_running: false,
      phase: "RUNNING",
    };

    const next = mergeRunStateWithStreamBar(previousState as any, { bar_index: 656 } as any);

    expect(next).not.toBeNull();
    expect(next?.current_bar_index).toBe(897);
    expect(next?.progress_pct).toBe(100);
  });

  it("advances current_bar_index for newer stream updates", () => {
    const previousState = {
      current_bar_index: 120,
      total_bars: 900,
      progress_pct: 13.3,
      is_running: true,
      phase: "RUNNING",
    };

    const next = mergeRunStateWithStreamBar(previousState as any, { bar_index: 150 } as any);

    expect(next?.current_bar_index).toBe(151);
    expect(next?.progress_pct).toBeCloseTo((151 / 900) * 100, 6);
  });
});
