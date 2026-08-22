import { getJson, post } from "./client";
import type { PendingDevice } from "../types";

export function listPendingDevices(): Promise<PendingDevice[]> {
  return getJson<PendingDevice[]>("/api/admin/devices");
}

export function approveDevice(userCode: string): Promise<{ status: string }> {
  return post<{ status: string }>(`/api/admin/devices/${encodeURIComponent(userCode)}/approve`);
}

export function denyDevice(userCode: string): Promise<{ status: string }> {
  return post<{ status: string }>(`/api/admin/devices/${encodeURIComponent(userCode)}/deny`);
}
