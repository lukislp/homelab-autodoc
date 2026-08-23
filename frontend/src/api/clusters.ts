import { del, getJson } from "./client";

export function listClusters(): Promise<string[]> {
  return getJson<string[]>("/api/admin/clusters");
}

export function deleteCluster(clusterName: string): Promise<{ status: string }> {
  return del<{ status: string }>(`/api/admin/clusters/${encodeURIComponent(clusterName)}`);
}
