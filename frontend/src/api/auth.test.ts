import { describe, expect, it, vi } from "vitest";
import * as client from "./client";
import { getAuthStatus, loginUrl, logoutUrl, submitSetup } from "./auth";

describe("api/auth", () => {
  it("getAuthStatus fetches /api/auth/status", async () => {
    const spy = vi.spyOn(client, "getJson").mockResolvedValue({ configured: true, identity: null });

    const result = await getAuthStatus();

    expect(spy).toHaveBeenCalledWith("/api/auth/status");
    expect(result).toEqual({ configured: true, identity: null });
  });

  it("submitSetup posts the payload to /api/setup", async () => {
    const spy = vi.spyOn(client, "postJson").mockResolvedValue({ status: "ok" });
    const payload = {
      provider: "github" as const,
      client_id: "a",
      client_secret: "b",
      allowed_identity: "c",
    };

    await submitSetup(payload);

    expect(spy).toHaveBeenCalledWith("/api/setup", payload);
  });

  it("loginUrl and logoutUrl point at the real backend redirects", () => {
    expect(loginUrl()).toBe("/auth/login");
    expect(logoutUrl()).toBe("/auth/logout");
  });
});
