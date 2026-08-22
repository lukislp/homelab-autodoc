# autodoc-collector

Read-only Kubernetes inventory collector for [homelab-autodoc](../README.md). Reads Deployments/StatefulSets, Services, Ingresses and PersistentVolumeClaims from one cluster and emits a deterministic, structured inventory (JSON or YAML) - no LLM, no invented facts.

## What it collects

Per namespace, every workload (Deployment or StatefulSet - see [Extending](#extending-to-a-new-workload-kind)) becomes an "app", with the Services/Ingresses/PersistentVolumeClaims that actually belong to it attached:

- **App**: name, kind, replicas/ready replicas, pod labels, containers (name, image, ports)
- **Service**: name, type, cluster IP, ports — matched to an app when the Service's selector is satisfied by the app's pod labels
- **Ingress**: name, host/path rules, TLS hosts — matched when it routes to one of the app's matched Services
- **Volume**: PVC claim name, storage class, capacity, access modes — matched via the pod template's `persistentVolumeClaim` volume references

`kube-system`/`kube-public`/`kube-node-lease` are skipped by default (`--include-system` to collect them too).

## Usage

```bash
pip install -e ../core -e ".[dev]"

# Local/dev: reads your current kubeconfig context
autodoc-collector --format yaml --output inventory.yaml

# Specific cluster/context, specific namespaces
autodoc-collector --context my-cluster --namespace apps --namespace media

# In-cluster (CronJob): no flags needed, uses the mounted ServiceAccount token.
# CLUSTER_NAME env var sets the display name (falls back to the kubeconfig
# context name locally, or "unknown-cluster" in-cluster without it set).
autodoc-collector
```

Run `autodoc-collector --help` for all options.

## Pushing to a server

Instead of writing the inventory locally, push it straight to an [autodoc-server](../server):

```bash
autodoc-collector --push http://autodoc.example.com
```

On first run this registers the cluster via the OAuth 2.0 Device Authorization Grant (no
pre-shared secret): it prints a URL and a short code, an admin approves it in the server's
admin app, and the collector then caches the issued token (default: `.autodoc-push-token` in
the current directory, override with `--token-file`) so future runs skip registration and push
directly. Denied or expired registrations exit non-zero without writing a token file.

## Docker

```bash
# from the repo root - the build context has to include the sibling autodoc-core package
docker build -f collector/Dockerfile -t autodoc-collector .
docker run --rm autodoc-collector --push http://autodoc.example.com
```

Published as `ghcr.io/lukislp/homelab-autodoc-collector` (multi-arch: amd64/arm64) on release. See [`../deploy/`](../deploy/) for the CronJob manifest.

## RBAC

[`../deploy/collector-rbac.yaml`](../deploy/collector-rbac.yaml) defines a ServiceAccount + ClusterRole with exactly `get`/`list`/`watch` on the resource kinds above - no write verbs anywhere, no access to Secrets or Pods. It's part of the full deployment manifests in [`../deploy/`](../deploy/) (CronJob, PVC-backed token cache) - see that directory's README for the complete `kubectl`/FluxCD setup.

For local testing against a real cluster as that ServiceAccount:

```bash
kubectl create namespace autodoc
kubectl apply -f ../deploy/collector-rbac.yaml
kubectl -n autodoc create token autodoc-collector --duration=1h
```

## Extending to a new workload kind

The collector only knows about a workload kind through a `WorkloadCollector` adapter in [`workloads.py`](src/autodoc_collector/workloads.py) - the association logic in [`collect.py`](src/autodoc_collector/collect.py) that attaches Services/Ingresses/Volumes only ever sees the adapter's normalized output (pod labels, containers, claim names), never the raw Kubernetes object. Adding e.g. DaemonSet support is:

1. Write a class with a `kind` name and `list(apis, namespace)` / `normalize(raw)` method (see `DeploymentCollector`/`StatefulSetCollector` for the shape).
2. Add an instance to `DEFAULT_WORKLOAD_COLLECTORS`.

Nothing else changes.

## Development

```bash
pip install -e ../core -e ".[dev]"
ruff check .
ruff format --check .
pytest
```
