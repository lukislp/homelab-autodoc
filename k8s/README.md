# k8s/

Manifests for running [homelab-autodoc](../README.md) on the real cluster (`pinode01`/`pinode02`, k3s, arm64).

Onboarded into the cluster-wide [homelab-infra](https://github.com/lukislp/homelab-infra) Flux GitOps pattern - this repo owns its own Flux wiring (`k8s/flux/`), rather than a central repo managing it on this repo's behalf. `01-app.yaml` (the server's PVC + Deployment + Service) is **Flux-managed**: `k8s/flux/` watches GHCR for new server image tags and auto-bumps the `$imagepolicy`-marked image line, `k8s/flux-deploy/kustomization.yaml` is the subset Flux actually applies. Everything else (`00-namespace.yaml`, `02-httproute.yaml`, `03-network-policies.yaml`, `03-collector-rbac.yaml`, `04-collector-cronjob.yaml`) stays **bootstrap-only** - applied once by hand, never touched by Flux (homelab-infra's `flux/01-reconciler-rbac.yaml` least-privilege ClusterRole doesn't grant those resource kinds).

## Bootstrap (once)

```bash
export KUBECONFIG=$env:USERPROFILE\.kube\studylife-config   # PowerShell

# 1. secrets for the admin app - required before the server will boot. The OpenAI key is the
#    same one studylife-ai uses (see that repo's k8s/02-secret.yaml) - copy its value, don't
#    provision a separate one.
kubectl create namespace homelab-autodoc
kubectl -n homelab-autodoc create secret generic autodoc-server-secrets \
  --from-literal=session-secret="$(openssl rand -base64 32)" \
  --from-literal=openai-api-key="<same key studylife-ai uses>"

# 2. the bootstrap-only resources (namespace, RBAC, HTTPRoute, NetworkPolicies, CronJob)
kubectl apply -k k8s/

# 3. wire this repo into Flux - additive, doesn't touch any other app's objects
kubectl apply -f k8s/flux/
flux get sources git homelab-autodoc
flux get kustomizations homelab-autodoc-deploy
```

After step 3, Flux applies `01-app.yaml` on its own (5-minute reconcile interval) - no manual `kubectl apply -f k8s/01-app.yaml` needed, and image-automation-controller commits new server image tags to `master` automatically as they're published.

## Exposing it (manual, outside this repo)

The HTTPRoute (`02-httproute.yaml`) stays in this repo, not `homelab-infra` - same as every other app-specific route (`unifiprotectdashboard`, `piwatch`, `studylife-mcp`); only cluster-owned shared services (e.g. `grafana`) live centrally in `homelab-infra/cluster/03-httproutes-shared.yaml`.

1. **Gateway listener**: `studylife-gateway` (in `nginx-gateway`) needs a listener for `autodoc.heim.lan` (already added live via a surgical, append-only `kubectl patch --type=json` - see that Gateway's own documented incident for why never a wholesale re-`apply`).
2. **DNS**: point `autodoc.heim.lan` at the Gateway's MetalLB IP.
3. **Public name** (optional): an NGINX Proxy Manager proxy host forwarding `autodoc.lukas2311-homelab.com` to `autodoc.heim.lan`.

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
flux logs --kind ImageUpdateAutomation --name homelab-autodoc-server -n flux-system
```

## Tear down

```bash
kubectl delete -f k8s/flux/       # stop Flux from reconciling/recreating 01-app.yaml first
kubectl delete -k k8s/
kubectl -n homelab-autodoc delete secret autodoc-server-secrets
kubectl delete namespace homelab-autodoc
```
