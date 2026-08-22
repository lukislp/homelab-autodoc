import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { DeviceList } from "./DeviceList";

const DEVICES = [
  { user_code: "ABCD-1234", cluster_name: "homelab" },
  { user_code: "EFGH-5678", cluster_name: "media-cluster" },
];

describe("DeviceList", () => {
  it("shows an empty state when there are no pending devices", () => {
    render(<DeviceList devices={[]} onApprove={vi.fn()} onDeny={vi.fn()} />);

    expect(screen.getByText(/no pending registrations/i)).toBeInTheDocument();
  });

  it("renders one row per pending device with its cluster name and user code", () => {
    render(<DeviceList devices={DEVICES} onApprove={vi.fn()} onDeny={vi.fn()} />);

    expect(screen.getByText("homelab")).toBeInTheDocument();
    expect(screen.getByText("ABCD-1234")).toBeInTheDocument();
    expect(screen.getByText("media-cluster")).toBeInTheDocument();
    expect(screen.getByText("EFGH-5678")).toBeInTheDocument();
  });

  it("calls onApprove with the right user_code when Approve is clicked", async () => {
    const user = userEvent.setup();
    const onApprove = vi.fn();
    render(<DeviceList devices={DEVICES} onApprove={onApprove} onDeny={vi.fn()} />);

    await user.click(screen.getAllByRole("button", { name: /approve/i })[1]);

    expect(onApprove).toHaveBeenCalledWith("EFGH-5678");
  });

  it("calls onDeny with the right user_code when Deny is clicked", async () => {
    const user = userEvent.setup();
    const onDeny = vi.fn();
    render(<DeviceList devices={DEVICES} onApprove={vi.fn()} onDeny={onDeny} />);

    await user.click(screen.getAllByRole("button", { name: /deny/i })[0]);

    expect(onDeny).toHaveBeenCalledWith("ABCD-1234");
  });
});
