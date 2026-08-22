import { getJson, postJson } from "./client";
import type { AuthStatus, SetupPayload } from "../types";

export function getAuthStatus(): Promise<AuthStatus> {
  return getJson<AuthStatus>("/api/auth/status");
}

export function submitSetup(payload: SetupPayload): Promise<{ status: string }> {
  return postJson<{ status: string }>("/api/setup", payload);
}

export function loginUrl(): string {
  // A real browser navigation (the provider redirect can't be done via fetch).
  return "/auth/login";
}

export function logoutUrl(): string {
  return "/auth/logout";
}
