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
pip install -e ".[dev]"

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

## RBAC

`manifests/rbac.yaml` defines a ServiceAccount + ClusterRole with exactly `get`/`list`/`watch` on the resource kinds above - no write verbs anywhere, no access to Secrets or Pods.

```bash
kubectl create namespace autodoc
kubectl apply -f manifests/rbac.yaml
```

For local testing against a real cluster as that ServiceAccount:

```bash
kubectl -n autodoc create token autodoc-collector --duration=1h
```

## Extending to a new workload kind

The collector only knows about a workload kind through a `WorkloadCollector` adapter in [`workloads.py`](src/autodoc_collector/workloads.py) - the association logic in [`collect.py`](src/autodoc_collector/collect.py) that attaches Services/Ingresses/Volumes only ever sees the adapter's normalized output (pod labels, containers, claim names), never the raw Kubernetes object. Adding e.g. DaemonSet support is:

1. Write a class with a `kind` name and `list(apis, namespace)` / `normalize(raw)` method (see `DeploymentCollector`/`StatefulSetCollector` for the shape).
2. Add an instance to `DEFAULT_WORKLOAD_COLLECTORS`.

Nothing else changes.

## Development

```bash
pip install -e ".[dev]"
ruff check .
ruff format --check .
pytest
```
