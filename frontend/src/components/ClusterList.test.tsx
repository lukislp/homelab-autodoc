import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ClusterList } from "./ClusterList";

const CLUSTERS = ["homelab", "media-cluster"];

describe("ClusterList", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows an empty state when there are no registered clusters", () => {
    render(<ClusterList clusters={[]} onDelete={vi.fn()} />);

    expect(screen.getByText(/no clusters registered yet/i)).toBeInTheDocument();
  });

  it("renders one row per registered cluster", () => {
    render(<ClusterList clusters={CLUSTERS} onDelete={vi.fn()} />);

    expect(screen.getByText("homelab")).toBeInTheDocument();
    expect(screen.getByText("media-cluster")).toBeInTheDocument();
  });

  it("calls onDelete with the right cluster name after the user confirms", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const user = userEvent.setup();
    const onDelete = vi.fn();
    render(<ClusterList clusters={CLUSTERS} onDelete={onDelete} />);

    await user.click(screen.getAllByRole("button", { name: /delete/i })[1]);

    expect(onDelete).toHaveBeenCalledWith("media-cluster");
  });

  it("does not call onDelete when the user cancels the confirmation", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(false);
    const user = userEvent.setup();
    const onDelete = vi.fn();
    render(<ClusterList clusters={CLUSTERS} onDelete={onDelete} />);

    await user.click(screen.getAllByRole("button", { name: /delete/i })[0]);

    expect(onDelete).not.toHaveBeenCalled();
  });
});
