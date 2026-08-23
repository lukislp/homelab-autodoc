import { useCallback, useEffect, useRef, useState } from "react";
import { approveDevice, denyDevice, listPendingDevices } from "../api/devices";
import type { PendingDevice } from "../types";

// How often the list re-fetches in the background so the view stays current
// without manual reloads (a collector registering shows up on its own).
export const POLL_INTERVAL_MS = 5000;

export interface UsePendingDevicesResult {
  devices: PendingDevice[];
  loading: boolean;
  error: string | null;
  approve: (userCode: string) => Promise<void>;
  deny: (userCode: string) => Promise<void>;
}

export function usePendingDevices(): UsePendingDevicesResult {
  const [devices, setDevices] = useState<PendingDevice[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const loadedOnce = useRef(false);

  const fetchDevices = useCallback(() => {
    return listPendingDevices()
      .then((result) => {
        loadedOnce.current = true;
        setDevices(result);
        setError(null);
      })
      .catch((err: Error) => {
        // A failed background poll keeps showing the last known list (the
        // next tick self-heals); only a failure before anything ever loaded
        // is worth surfacing.
        if (!loadedOnce.current) setError(err.message);
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    fetchDevices();
    const id = setInterval(() => {
      if (document.visibilityState === "visible") fetchDevices();
    }, POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, [fetchDevices]);

  const refresh = useCallback(() => {
    setLoading(true);
    return fetchDevices();
  }, [fetchDevices]);

  const approve = useCallback(
    async (userCode: string) => {
      await approveDevice(userCode);
      await refresh();
    },
    [refresh],
  );

  const deny = useCallback(
    async (userCode: string) => {
      await denyDevice(userCode);
      await refresh();
    },
    [refresh],
  );

  return { devices, loading, error, approve, deny };
}
