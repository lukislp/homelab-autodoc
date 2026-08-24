import { del, getJson } from "./client";

export interface ClusterEntry {
  name: string;
  // False until the cluster's collector has pushed its first inventory -
  // rendered as an "awaiting first push" badge instead of hiding the row.
  has_inventory: boolean;
}

export function listClusters(): Promise<ClusterEntry[]> {
  return getJson<ClusterEntry[]>("/api/admin/clusters");
}

export function deleteCluster(clusterName: string): Promise<{ status: string }> {
  return del<{ status: string }>(`/api/admin/clusters/${encodeURIComponent(clusterName)}`);
}
