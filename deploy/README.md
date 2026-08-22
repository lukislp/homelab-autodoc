# deploy/

Kubernetes manifests for running [homelab-autodoc](../README.md) in a k3s cluster: the collector as a nightly CronJob, the server as a Deployment. Plain Kustomize - works with `kubectl apply -k`, and is exactly what a FluxCD `Kustomization` resource elsewhere in your fleet repo would point at.

## What's here

| File | What |
|---|---|
| `namespace.yaml` | The `autodoc` namespace everything else lives in |
| `collector-rbac.yaml` | Read-only ServiceAccount + ClusterRole for the collector (see [collector/README.md](../collector/README.md#rbac)) |
| `collector-cronjob.yaml` | Nightly CronJob (`0 2 * * *`) running `autodoc-collector --push` against the in-cluster server, plus the PVC that holds its push token |
| `server-deployment.yaml` | Deployment + Service + two PVCs (`/data`, `/config`) for the server |
| `kustomization.yaml` | Ties the above together |

## One-time setup

```bash
# 1. session secret for the admin app - required before the server will boot
kubectl create namespace autodoc
kubectl -n autodoc create secret generic autodoc-server-secrets \
  --from-literal=session-secret="$(openssl rand -base64 32)"

# 2. apply everything
kubectl apply -k deploy/

# 3. open the admin app once to run the setup wizard (GitHub or OIDC login)
kubectl -n autodoc port-forward svc/autodoc-server 8000:8000
# -> http://localhost:8000/admin
```

The collector CronJob's first run will register itself and then sit polling for up to the
device-grant expiry (10 minutes) waiting for you to approve it from the admin app - that's
expected, not a hang. Every run after that reuses the cached token and pushes immediately.

Set the real cluster name before deploying to more than one cluster - `collector-cronjob.yaml`'s
`CLUSTER_NAME` env var is a placeholder (`homelab`), meant to be overridden per cluster via a
Kustomize patch or a separate overlay, not edited in place if you're managing multiple clusters
from the same source.

## Token persistence

The collector's ServiceAccount is intentionally read-only (see its RBAC) - it can't write a
Kubernetes Secret for itself. Instead its push token lives on a small PVC mounted at the
`--token-file` path: no token yet → register and wait for approval → write it there; token
already there → skip straight to pushing. Simplest option that needed zero new code and zero
RBAC changes - see the project's architecture notes for the alternatives that were considered
(a narrowly-scoped Secret-write RBAC exception, or a separate one-time bootstrap Job) and why
this one was chosen to start with.

## Ingress

Not included - point your own Ingress/IngressRoute at the `autodoc-server` Service (port 8000)
using whatever ingress controller and TLS setup your cluster already uses.
