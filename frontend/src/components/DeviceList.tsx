import type { PendingDevice } from "../types";

interface DeviceListProps {
  devices: PendingDevice[];
  onApprove: (userCode: string) => void;
  onDeny: (userCode: string) => void;
}

export function DeviceList({ devices, onApprove, onDeny }: DeviceListProps) {
  return (
    <>
      <h1>Pending cluster registrations</h1>
      {devices.length === 0 ? (
        <p className="empty">No pending registrations.</p>
      ) : (
        devices.map((device) => (
          <div className="device-row" key={device.user_code}>
            <div>
              <strong>{device.cluster_name}</strong>
              <br />
              <span className="user-code">{device.user_code}</span>
            </div>
            <div className="actions">
              <button type="button" onClick={() => onApprove(device.user_code)}>
                Approve
              </button>
              <button
                type="button"
                className="danger"
                onClick={() => onDeny(device.user_code)}
              >
                Deny
              </button>
            </div>
          </div>
        ))
      )}
    </>
  );
}
