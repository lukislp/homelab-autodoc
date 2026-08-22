import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { approveDevice, denyDevice, listPendingDevices } from "../api/devices";
import { usePendingDevices } from "./usePendingDevices";

vi.mock("../api/devices", () => ({
  listPendingDevices: vi.fn(),
  approveDevice: vi.fn(),
  denyDevice: vi.fn(),
}));

const DEVICES = [{ user_code: "ABCD-1234", cluster_name: "homelab" }];

describe("usePendingDevices", () => {
  it("loads the pending devices on mount", async () => {
    vi.mocked(listPendingDevices).mockResolvedValue(DEVICES);

    const { result } = renderHook(() => usePendingDevices());

    expect(result.current.loading).toBe(true);
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.devices).toEqual(DEVICES);
  });

  it("approve() calls the API and refetches the list", async () => {
    vi.mocked(listPendingDevices).mockResolvedValueOnce(DEVICES).mockResolvedValueOnce([]);
    vi.mocked(approveDevice).mockResolvedValue({ status: "approved" });
    const { result } = renderHook(() => usePendingDevices());
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(() => result.current.approve("ABCD-1234"));

    expect(approveDevice).toHaveBeenCalledWith("ABCD-1234");
    expect(result.current.devices).toEqual([]);
  });

  it("deny() calls the API and refetches the list", async () => {
    vi.mocked(listPendingDevices).mockResolvedValueOnce(DEVICES).mockResolvedValueOnce([]);
    vi.mocked(denyDevice).mockResolvedValue({ status: "denied" });
    const { result } = renderHook(() => usePendingDevices());
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(() => result.current.deny("ABCD-1234"));

    expect(denyDevice).toHaveBeenCalledWith("ABCD-1234");
    expect(result.current.devices).toEqual([]);
  });

  it("surfaces a fetch failure as an error", async () => {
    vi.mocked(listPendingDevices).mockRejectedValue(new Error("boom"));

    const { result } = renderHook(() => usePendingDevices());

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.error).toBe("boom");
  });
});
