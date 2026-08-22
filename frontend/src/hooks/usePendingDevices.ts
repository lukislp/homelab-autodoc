import { useCallback, useEffect, useState } from "react";
import { approveDevice, denyDevice, listPendingDevices } from "../api/devices";
import type { PendingDevice } from "../types";

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

  const fetchDevices = useCallback(() => {
    return listPendingDevices()
      .then(setDevices)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    fetchDevices();
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
