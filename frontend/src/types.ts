export type Provider = "github" | "oidc";

export interface AuthStatus {
  configured: boolean;
  identity: string | null;
}

export interface SetupPayload {
  provider: Provider;
  client_id: string;
  client_secret: string;
  allowed_identity: string;
  issuer_url?: string;
}

export interface PendingDevice {
  user_code: string;
  cluster_name: string;
}
