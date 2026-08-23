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
import type { Provider, SetupPayload } from "./types";

function Brand() {
  return (
    <div className="brand">
      <span className="dot" />
      homelab-autodoc
    </div>
  );
}

// Centered-card treatment for the pre-login states (loading, error, setup,
// login prompt) - the typical login-form look. The logged-in management view
// (DevicesView) is full-screen instead.
function CenteredCard({ children }: { children: ReactNode }) {
  return (
    <div className="centered">
      <Brand />
      <div className="card">{children}</div>
    </div>
  );
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

const LOGIN_LABELS: Record<Provider, string> = {
  github: "Login with GitHub",
  oidc: "Login with SSO",
};

function LoginPromptView({ provider }: { provider: Provider | null }) {
  return (
    <>
      <h1>Admin login</h1>
      <p>Admin login is configured. Sign in to manage pending cluster registrations.</p>
      <a className="button-link" href={loginUrl()}>
        {provider ? LOGIN_LABELS[provider] : "Log in"}
      </a>
    </>
  );
}

function DevicesView({ identity }: { identity: string }) {
  const { devices, loading, error, approve, deny } = usePendingDevices();
  const { clusters, loading: clustersLoading, error: clustersError, remove } = useClusters();

  return (
    <div className="page">
      <header className="page-header">
        <Brand />
        <nav className="page-nav">
          <a href="/">← Back to docs</a>
          <span className="identity">{identity}</span>
          <a href={logoutUrl()}>Log out</a>
        </nav>
      </header>
      <main className="page-main">
        <section className="panel">
          {loading && <p className="empty">Loading…</p>}
          {error && <p className="error">{error}</p>}
          {!loading && !error && (
            <DeviceList devices={devices} onApprove={approve} onDeny={deny} />
          )}
        </section>
        <section className="panel">
          {clustersLoading && <p className="empty">Loading…</p>}
          {clustersError && <p className="error">{clustersError}</p>}
          {!clustersLoading && !clustersError && (
            <ClusterList clusters={clusters} onDelete={remove} />
          )}
        </section>
      </main>
    </div>
  );
}

export default function App() {
  const { status, loading, error } = useAuthStatus();

  if (loading) {
    return (
      <CenteredCard>
        <p className="empty">Loading…</p>
      </CenteredCard>
    );
  }

  if (error || !status) {
    return (
      <CenteredCard>
        <p className="error">{error ?? "Could not reach the server."}</p>
      </CenteredCard>
    );
  }

  if (status.identity) {
    return <DevicesView identity={status.identity} />;
  }

  return (
    <CenteredCard>
      {!status.configured ? <SetupView /> : <LoginPromptView provider={status.provider} />}
    </CenteredCard>
  );
}
