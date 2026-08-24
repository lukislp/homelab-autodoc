import type { ClusterEntry } from "../api/clusters";

interface ClusterListProps {
  clusters: ClusterEntry[];
  onDelete: (clusterName: string) => void;
}

export function ClusterList({ clusters, onDelete }: ClusterListProps) {
  function handleDelete(clusterName: string) {
    // Deleting a cluster removes its data permanently - there's no undo, so
    // this is the one place in the admin app that asks before acting.
    if (window.confirm(`Delete "${clusterName}"? This removes its data permanently.`)) {
      onDelete(clusterName);
    }
  }

  return (
    <>
      <h1>Registered clusters</h1>
      {clusters.length === 0 ? (
        <p className="empty">No clusters registered yet.</p>
      ) : (
        clusters.map((cluster) => (
          <div className="device-row" key={cluster.name}>
            <strong>{cluster.name}</strong>
            {!cluster.has_inventory && (
              <span className="awaiting-badge">awaiting first push</span>
            )}
            <div className="actions">
              <button type="button" className="danger" onClick={() => handleDelete(cluster.name)}>
                Delete
              </button>
            </div>
          </div>
        ))
      )}
    </>
  );
}
