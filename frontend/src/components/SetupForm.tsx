import { useState } from "react";
import type { FormEvent } from "react";
import type { Provider, SetupPayload } from "../types";

interface SetupFormProps {
  onSubmit: (payload: SetupPayload) => Promise<void>;
  submitting: boolean;
  error: string | null;
}

export function SetupForm({ onSubmit, submitting, error }: SetupFormProps) {
  const [provider, setProvider] = useState<Provider>("github");
  const [clientId, setClientId] = useState("");
  const [clientSecret, setClientSecret] = useState("");
  const [allowedIdentity, setAllowedIdentity] = useState("");
  const [issuerUrl, setIssuerUrl] = useState("");

  const isOidc = provider === "oidc";

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    void onSubmit({
      provider,
      client_id: clientId,
      client_secret: clientSecret,
      allowed_identity: allowedIdentity,
      issuer_url: isOidc ? issuerUrl : undefined,
    });
  }

  return (
    <form onSubmit={handleSubmit}>
      <h1>Admin login setup</h1>

      <label htmlFor="provider">Provider</label>
      <select
        id="provider"
        value={provider}
        onChange={(e) => setProvider(e.target.value as Provider)}
      >
        <option value="github">GitHub</option>
        <option value="oidc">Custom OIDC provider</option>
      </select>

      {isOidc && (
        <>
          <label htmlFor="issuer_url">Issuer URL</label>
          <input
            id="issuer_url"
            type="url"
            required={isOidc}
            placeholder="https://auth.example.com"
            value={issuerUrl}
            onChange={(e) => setIssuerUrl(e.target.value)}
          />
        </>
      )}

      <label htmlFor="client_id">Client ID</label>
      <input
        id="client_id"
        type="text"
        required
        value={clientId}
        onChange={(e) => setClientId(e.target.value)}
      />

      <label htmlFor="client_secret">Client secret</label>
      <input
        id="client_secret"
        type="password"
        required
        value={clientSecret}
        onChange={(e) => setClientSecret(e.target.value)}
      />

      <label htmlFor="allowed_identity">Allowed identity</label>
      <input
        id="allowed_identity"
        type="text"
        required
        placeholder="GitHub username, or email for an OIDC provider"
        value={allowedIdentity}
        onChange={(e) => setAllowedIdentity(e.target.value)}
      />

      {error && <p className="error">{error}</p>}

      <button type="submit" disabled={submitting}>
        {submitting ? "Saving…" : "Save and continue to login"}
      </button>
    </form>
  );
}
