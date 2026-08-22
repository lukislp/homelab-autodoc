import { useCallback, useEffect, useState } from "react";
import { getAuthStatus } from "../api/auth";
import type { AuthStatus } from "../types";

export interface UseAuthStatusResult {
  status: AuthStatus | null;
  loading: boolean;
  error: string | null;
  refresh: () => void;
}

export function useAuthStatus(): UseAuthStatusResult {
  const [status, setStatus] = useState<AuthStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [version, setVersion] = useState(0);

  useEffect(() => {
    let cancelled = false;
    getAuthStatus()
      .then((result) => {
        if (!cancelled) setStatus(result);
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [version]);

  const refresh = useCallback(() => {
    setLoading(true);
    setVersion((v) => v + 1);
  }, []);

  return { status, loading, error, refresh };
}
