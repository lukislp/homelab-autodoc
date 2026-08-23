interface ClusterListProps {
  clusters: string[];
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
        clusters.map((clusterName) => (
          <div className="device-row" key={clusterName}>
            <strong>{clusterName}</strong>
            <div className="actions">
              <button type="button" className="danger" onClick={() => handleDelete(clusterName)}>
                Delete
              </button>
            </div>
          </div>
        ))
      )}
    </>
  );
}
