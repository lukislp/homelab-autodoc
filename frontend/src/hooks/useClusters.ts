import { useCallback, useEffect, useState } from "react";
import { deleteCluster, listClusters } from "../api/clusters";

export interface UseClustersResult {
  clusters: string[];
  loading: boolean;
  error: string | null;
  remove: (clusterName: string) => Promise<void>;
}

export function useClusters(): UseClustersResult {
  const [clusters, setClusters] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchClusters = useCallback(() => {
    return listClusters()
      .then(setClusters)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    fetchClusters();
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
