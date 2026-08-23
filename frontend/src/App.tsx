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

// GitHub's "mark" octicon, the standard glyph on "Login with GitHub" buttons.
function GitHubMark() {
  return (
    <svg viewBox="0 0 16 16" width="18" height="18" aria-hidden="true" fill="currentColor">
      <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27s1.36.09 2 .27c1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8Z" />
    </svg>
  );
}

function LoginPromptView({ provider }: { provider: Provider | null }) {
  return (
    <>
      <h1>Admin login</h1>
      <p>Admin login is configured. Sign in to manage pending cluster registrations.</p>
      <a className="button-link" href={loginUrl()}>
        {provider === "github" && <GitHubMark />}
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
