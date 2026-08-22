import { describe, expect, it, vi } from "vitest";
import * as client from "./client";
import { approveDevice, denyDevice, listPendingDevices } from "./devices";

describe("api/devices", () => {
  it("listPendingDevices fetches /api/admin/devices", async () => {
    const spy = vi.spyOn(client, "getJson").mockResolvedValue([]);

    await listPendingDevices();

    expect(spy).toHaveBeenCalledWith("/api/admin/devices");
  });

  it("approveDevice posts to the approve endpoint with an encoded user_code", async () => {
    const spy = vi.spyOn(client, "post").mockResolvedValue({ status: "approved" });

    await approveDevice("AB CD");

    expect(spy).toHaveBeenCalledWith("/api/admin/devices/AB%20CD/approve");
  });

  it("denyDevice posts to the deny endpoint", async () => {
    const spy = vi.spyOn(client, "post").mockResolvedValue({ status: "denied" });

    await denyDevice("ABCD-1234");

    expect(spy).toHaveBeenCalledWith("/api/admin/devices/ABCD-1234/deny");
  });
});
