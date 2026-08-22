# k8s/

Manifests for running [homelab-autodoc](../README.md) on the real cluster (`pinode01`/`pinode02`, k3s, arm64).

**Not onboarded into the central `studylife` repo's Flux GitOps pattern yet** - everything here is bootstrap-only for now, applied by hand. `01-app.yaml` (the server's PVC + Deployment + Service) is written ready for that onboarding - image pinned to a real tag with a `$imagepolicy` marker, same shape as every sibling app already on this cluster - but nothing currently reconciles it automatically. `k8s/flux-deploy/kustomization.yaml` is the subset a future Flux `Kustomization` would apply; the rest (`00-namespace.yaml`, `02-httproute.yaml`, `03-network-policies.yaml`, `03-collector-rbac.yaml`, `04-collector-cronjob.yaml`) would stay bootstrap-only even after onboarding, same as every sibling app - the central `kustomize-controller`'s least-privilege RBAC doesn't grant those resource kinds.

## Bootstrap (once)

```bash
export KUBECONFIG=$env:USERPROFILE\.kube\studylife-config   # PowerShell

# 1. session secret for the admin app - required before the server will boot
kubectl create namespace homelab-autodoc
kubectl -n homelab-autodoc create secret generic autodoc-server-secrets \
  --from-literal=session-secret="$(openssl rand -base64 32)"

# 2. everything else
kubectl apply -k k8s/
```

## Exposing it (manual, three steps outside this repo)

1. **Gateway listener**: `studylife-gateway` (in `nginx-gateway`) needs a new listener for `autodoc.heim.lan`. Per that Gateway's own documented incident, this must be a surgical, append-only `kubectl patch --type=json` against the *live* object - never a wholesale re-`apply` of the studylife repo's gateway file, which has previously reverted every other service's listener hostnames.
2. **DNS**: point `autodoc.heim.lan` at the Gateway's MetalLB IP.
3. **Public name** (optional): an NGINX Proxy Manager proxy host forwarding `autodoc.lukas2311-homelab.com` to `autodoc.heim.lan`, same as every other exposed service.

Until these are done, reach the admin app via port-forward instead (see below) - the app itself works fully, it's just not reachable via its normal hostname.

## First-time setup

```bash
kubectl -n homelab-autodoc port-forward svc/autodoc-server 8000:8000
```

Open `http://localhost:8000/admin` and run the setup wizard (GitHub or OIDC login). The collector CronJob's first run will then register itself and sit polling for up to 10 minutes (the device-grant expiry) waiting for that admin login to approve it from `/admin` - expected, not a hang. Every run after that reuses its cached token (see `04-collector-cronjob.yaml`) and pushes immediately.

## Token persistence

The collector's ServiceAccount is intentionally read-only - it can't write a Kubernetes Secret for itself. Its push token instead lives on a small PVC mounted at the `--token-file` path: no token yet -> register and wait for approval -> write it there; token already there -> skip straight to pushing. Considered and rejected for now: a narrowly-scoped Secret-write RBAC exception, and a separate one-time bootstrap Job with its own ServiceAccount - the PVC needed zero new code and zero RBAC change.

## Watch it

```bash
kubectl -n homelab-autodoc logs -f deploy/autodoc-server
kubectl -n homelab-autodoc logs -f -l job-name --selector=batch.kubernetes.io/job-name  # most recent collector run
```

## Tear down

```bash
kubectl delete -k k8s/
kubectl -n homelab-autodoc delete secret autodoc-server-secrets
kubectl delete namespace homelab-autodoc
```
