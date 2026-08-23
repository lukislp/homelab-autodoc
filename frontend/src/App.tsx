import { useState } from "react";
import type { ReactNode } from "react";
import { loginUrl, logoutUrl, submitSetup } from "./api/auth";
import { ApiError } from "./api/client";
import { ClusterList } from "./components/ClusterList";
import { DeviceList } from "./components/DeviceList";
import { SetupForm } from "./components/SetupForm";
import { useAuthStatus } from "./hooks/useAuthStatus";
import { useClusters } from "./hooks/useClusters";
import { usePendingDevices } from "./hooks/usePendingDevices";
import type { SetupPayload } from "./types";

function Brand() {
  return (
    <div className="brand">
      <span className="dot" />
      homelab-autodoc
    </div>
  );
}

function Card({ children, wide = false }: { children: ReactNode; wide?: boolean }) {
  return <div className={wide ? "card card--wide" : "card"}>{children}</div>;
}

function SetupView() {
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(payload: SetupPayload) {
    setSubmitting(true);
    setError(null);
    try {
      await submitSetup(payload);
      window.location.href = loginUrl();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Could not save the configuration.");
      setSubmitting(false);
    }
  }

  return <SetupForm onSubmit={handleSubmit} submitting={submitting} error={error} />;
}

function LoginPromptView() {
  return (
    <>
      <h1>Admin login</h1>
      <p>Admin login is configured. Sign in to manage pending cluster registrations.</p>
      <a className="button-link" href={loginUrl()}>
        Log in
      </a>
    </>
  );
}

function DevicesView({ identity }: { identity: string }) {
  const { devices, loading, error, approve, deny } = usePendingDevices();
  const { clusters, loading: clustersLoading, error: clustersError, remove } = useClusters();

  return (
    <>
      <div className="topbar">
        <span>{identity}</span>
        <a href={logoutUrl()}>Log out</a>
      </div>
      {loading && <p className="empty">Loading…</p>}
      {error && <p className="error">{error}</p>}
      {!loading && !error && <DeviceList devices={devices} onApprove={approve} onDeny={deny} />}
      {clustersLoading && <p className="empty">Loading…</p>}
      {clustersError && <p className="error">{clustersError}</p>}
      {!clustersLoading && !clustersError && (
        <ClusterList clusters={clusters} onDelete={remove} />
      )}
    </>
  );
}

export default function App() {
  const { status, loading, error } = useAuthStatus();

  if (loading) {
    return (
      <>
        <Brand />
        <Card>
          <p className="empty">Loading…</p>
        </Card>
      </>
    );
  }

  if (error || !status) {
    return (
      <>
        <Brand />
        <Card>
          <p className="error">{error ?? "Could not reach the server."}</p>
        </Card>
      </>
    );
  }

  return (
    <>
      <Brand />
      <Card wide={Boolean(status.identity)}>
        {!status.configured ? (
          <SetupView />
        ) : !status.identity ? (
          <LoginPromptView />
        ) : (
          <DevicesView identity={status.identity} />
        )}
      </Card>
    </>
  );
}
