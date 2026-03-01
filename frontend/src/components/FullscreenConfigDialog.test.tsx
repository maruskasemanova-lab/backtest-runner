import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { FullscreenConfigDialog } from "./FullscreenConfigDialog";

describe("FullscreenConfigDialog unified profile visibility", () => {
  it("shows the effective profile name and payload even without activeProfile object", async () => {
    render(
      <FullscreenConfigDialog
        isOpen
        onClose={() => {}}
        config={{
          strategy_profile: {
            strategy_params: {
              momentum_flow: {
                entry_threshold: 0.7,
              },
            },
          },
        }}
        activeProfileId="mu-scalp-v2"
        activeProfileName="MU Scalp V2"
      />
    );

    await waitFor(() => {
      expect(screen.getByText("Using unified profile: MU Scalp V2 (mu-scalp-v2)")).toBeInTheDocument();
    });

    expect(screen.queryByText("No active unified profile selected.")).not.toBeInTheDocument();
    expect(screen.getByText("Strategy Parameters")).toBeInTheDocument();
    expect(screen.getByText("momentum_flow")).toBeInTheDocument();
  });

  it("keeps fallback when profile identity and payload are both missing", async () => {
    render(
      <FullscreenConfigDialog
        isOpen
        onClose={() => {}}
        config={{}}
      />
    );

    await waitFor(() => {
      expect(screen.getByText("No active unified profile selected.")).toBeInTheDocument();
    });
    expect(screen.getByText("Using unified profile: unresolved")).toBeInTheDocument();
  });
});
