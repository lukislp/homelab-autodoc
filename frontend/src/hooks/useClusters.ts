import { useCallback, useEffect, useRef, useState } from "react";
import { type ClusterEntry, deleteCluster, listClusters } from "../api/clusters";
import { POLL_INTERVAL_MS } from "./usePendingDevices";

export interface UseClustersResult {
  clusters: ClusterEntry[];
  loading: boolean;
  error: string | null;
  remove: (clusterName: string) => Promise<void>;
}

export function useClusters(): UseClustersResult {
  const [clusters, setClusters] = useState<ClusterEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const loadedOnce = useRef(false);

  const fetchClusters = useCallback(() => {
    return listClusters()
      .then((result) => {
        loadedOnce.current = true;
        setClusters(result);
        setError(null);
      })
      .catch((err: Error) => {
        // Same stale-over-error trade-off as usePendingDevices: background
        // polls that fail retry silently, only the initial load surfaces.
        if (!loadedOnce.current) setError(err.message);
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    fetchClusters();
    const id = setInterval(() => {
      if (document.visibilityState === "visible") fetchClusters();
    }, POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, [fetchClusters]);

  const refresh = useCallback(() => {
    setLoading(true);
    return fetchClusters();
  }, [fetchClusters]);

  const remove = useCallback(
    async (clusterName: string) => {
      await deleteCluster(clusterName);
      await refresh();
    },
    [refresh],
  );

  return { clusters, loading, error, remove };
}
