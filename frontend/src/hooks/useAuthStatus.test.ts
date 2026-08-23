import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { getAuthStatus } from "../api/auth";
import { useAuthStatus } from "./useAuthStatus";

vi.mock("../api/auth", () => ({ getAuthStatus: vi.fn() }));

describe("useAuthStatus", () => {
  it("starts loading, then resolves with the fetched status", async () => {
    vi.mocked(getAuthStatus).mockResolvedValue({
      configured: true,
      provider: "github",
      identity: "lukislp",
    });

    const { result } = renderHook(() => useAuthStatus());

    expect(result.current.loading).toBe(true);

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.status).toEqual({
      configured: true,
      provider: "github",
      identity: "lukislp",
    });
    expect(result.current.error).toBeNull();
  });

  it("surfaces a fetch failure as an error", async () => {
    vi.mocked(getAuthStatus).mockRejectedValue(new Error("network down"));

    const { result } = renderHook(() => useAuthStatus());

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.error).toBe("network down");
    expect(result.current.status).toBeNull();
  });

  it("refresh() re-fetches and toggles loading again", async () => {
    vi.mocked(getAuthStatus).mockResolvedValue({
      configured: false,
      provider: null,
      identity: null,
    });
    const { result } = renderHook(() => useAuthStatus());
    await waitFor(() => expect(result.current.loading).toBe(false));
    const callsAfterMount = vi.mocked(getAuthStatus).mock.calls.length;

    vi.mocked(getAuthStatus).mockResolvedValue({
      configured: true,
      provider: "github",
      identity: null,
    });
    await act(async () => {
      result.current.refresh();
    });

    await waitFor(() => expect(result.current.status?.configured).toBe(true));
    expect(vi.mocked(getAuthStatus).mock.calls.length).toBeGreaterThan(callsAfterMount);
  });
});
