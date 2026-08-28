# homelab-autodoc

Helm chart for [homelab-autodoc](../../README.md) — living, auto-generated documentation for
Kubernetes homelabs.

This chart is deliberately generic and independent from the project's own production deployment
in [`../../k8s/`](../../k8s/): standard Ingress instead of a pre-existing Gateway API object,
ReadWriteOnce storage by default instead of a hard Longhorn/RWX dependency, no
NGINX-Gateway-Fabric-specific CRDs. Changes to one do not need to be ported to the other.

## Install

This chart never templates a `Namespace` object itself — a chart-owned `Namespace` resource is a
known Helm anti-pattern, confirmed the hard way while testing this chart: `server.existingSecret`
has to exist in the target namespace before install, so the namespace has to exist first too,
and a chart trying to "own" and template that already-existing namespace fails with an
ownership-adoption error. Create the namespace yourself first.

```bash
# 1. Namespace, optionally with the restricted PodSecurity profile (recommended - both images
#    already run non-root with all capabilities dropped, see values.yaml server.securityContext):
kubectl create namespace homelab-autodoc
kubectl label namespace homelab-autodoc \
  pod-security.kubernetes.io/enforce=restricted \
  pod-security.kubernetes.io/warn=restricted \
  pod-security.kubernetes.io/audit=restricted

# 2. A Secret the chart never creates for you - session secret + LLM API key:
kubectl -n homelab-autodoc create secret generic autodoc-server-secrets \
  --from-literal=session-secret="$(openssl rand -base64 32)" \
  --from-literal=llm-api-key="<your LLM provider API key>"

# 3. Install
helm install autodoc ./charts/homelab-autodoc \
  -n homelab-autodoc \
  --set server.existingSecret=autodoc-server-secrets
```

Then open `/admin` (port-forward if you haven't set up `server.ingress` or `server.gatewayApi`
yet) and run the setup wizard — see the chart's `NOTES.txt` output after install, or
[the root project README](../../README.md) for what the setup wizard and device-grant approval
actually do.

### A note on `helm install --wait`

`--wait` will very likely report `failed` on a **first** install even though everything actually
converges correctly. Cause: the collector's token PVC uses the default `WaitForFirstConsumer`
binding mode, so it only leaves `Pending` once the CronJob's *first* Pod is scheduled — which,
on the default nightly schedule, doesn't happen at install time. `--wait` doesn't know that and
times out watching a PVC that was never going to bind yet.

This is expected, not a chart bug — verified against a real `kind` cluster: the Deployment and
Service came up and became healthy while `helm install --wait` was still timing out on that one
PVC. Either:

- skip `--wait` and check `kubectl get pods -n <namespace>` / `helm status` yourself, or
- trigger the CronJob once so the PVC has a consumer before you `--wait`:
  `kubectl -n <namespace> create job --from=cronjob/<release>-collector collector-manual-test`

## Multi-cluster: one server, several collectors

Install once with defaults (`server.enabled: true`, `collector.enabled: true`) for a single
cluster. For additional clusters, install the chart again per cluster with:

```yaml
server:
  enabled: false
collector:
  pushUrl: "http://autodoc-server.<namespace>.svc.cluster.local:8000" # or an external URL
```

## Values

| Key | Default | Description |
|---|---|---|
| `server.enabled` | `true` | Deploy the server (Deployment, Service, PVCs). Set `false` for a collector-only install pointing at a shared server (see above). |
| `server.replicaCount` | `1` | Not horizontally scalable — `/data` and `/config` are single-writer. |
| `server.image.repository` / `.tag` | `ghcr.io/lukislp/homelab-autodoc-server` / `""` (= `Chart.AppVersion`) | |
| `server.updateStrategy` | `Recreate` | `Recreate` is the safe default for `ReadWriteOnce` storage (brief downtime on rollout). Set to `RollingUpdate` only if your storage is `ReadWriteMany` — otherwise the surge pod can't mount the same PVC and the rollout stalls. |
| `server.storage.data.size` / `.storageClassName` / `.accessModes` | `1Gi` / `""` (cluster default) / `["ReadWriteOnce"]` | Holds inventory + drift history — irreplaceable, back it up. |
| `server.storage.config.size` / `.storageClassName` / `.accessModes` | `10Mi` / `""` / `["ReadWriteOnce"]` | Holds the admin-auth provider config. |
| `server.resources` | `100m/256Mi` requests, `1/768Mi` limits | |
| `server.service.port` | `8000` | |
| `server.existingSecret` | `""` (**required**) | Secret with the keys named in `server.secretKeys`. Install fails fast with a clear message if unset. |
| `server.secretKeys.sessionSecret` / `.llmApiKey` | `session-secret` / `llm-api-key` | Keys to read from `server.existingSecret`. |
| `server.llm.model` | `openai/gpt-4o-mini` | LiteLLM model string; see [docs.litellm.ai/docs/providers](https://docs.litellm.ai/docs/providers). |
| `server.llm.reasoningEffort` | `""` | Only set for reasoning models that require an explicit value (e.g. `"medium"`). |
| `server.extraEnv` | `[]` | Extra `corev1.EnvVar` entries appended to the server container. |
| `server.fsGroup` | `10001` | Matches the non-root UID both images run as. Shared by the collector CronJob pod too. |
| `server.ingress.enabled` | `false` | Standard `networking.k8s.io/v1` Ingress. |
| `server.gatewayApi.enabled` | `false` | `HTTPRoute` against an **existing** Gateway (`server.gatewayApi.parentRef`) — this chart never creates a Gateway. |
| `server.networkPolicy.enabled` | `false` | Default-deny ingress + explicit allows (collector push, `server.networkPolicy.allowIngressFrom`). Off by default: safe on most CNIs, but a first install shouldn't have to fight a CNI you didn't expect to enforce policies. Note: policy *creation* doesn't imply *enforcement* — that depends entirely on your CNI (e.g. kindnet does not enforce NetworkPolicy at all). |
| `collector.enabled` | `true` | The nightly inventory CronJob. |
| `collector.clusterName` | `homelab` | Display name pushed with the inventory. |
| `collector.schedule` | `"0 2 * * *"` | |
| `collector.rbac.create` | `true` | Cluster-scoped, read-only, no Secrets access ever. Set `false` if your cluster provisions this RBAC out-of-band. |
| `collector.pushUrl` | `""` (= this release's own server Service) | Override for a collector-only install (see Multi-cluster above). |

See `values.yaml` for the full, commented list.

## What's verified vs. template-only

Live-tested on a local `kind` cluster:

- server Deployment/Service/PVCs (`ReadWriteOnce`, `Recreate` strategy), the admin UI, `/healthz`
- collector RBAC + token PVC + push connectivity (registered against the server, device-grant
  flow reached)
- `server.ingress` against a real `ingress-nginx` controller — host-based routing confirmed
  end-to-end (correct host reaches the server, wrong host gets nginx's own 404)
- `server.gatewayApi` against real Gateway API CRDs and an existing `Gateway` object — the
  `HTTPRoute` is accepted and cross-references the `Gateway` correctly (no data-plane controller
  installed, so `status.parents` doesn't populate — not needed to validate the manifest itself)
- `server.networkPolicy` / `collector.networkPolicy` *creation* — all four policies apply cleanly
- `ReadWriteMany` PVCs statically binding to a matching `storageClassName`/accessMode/capacity PV
  (a stand-in for a real RWX StorageClass, since kind's default `local-path` is RWO-only) — bound
  correctly, on the first try, from a clean install

Not live-tested:

- `server.networkPolicy` **enforcement** — creating the objects was verified above, but actually
  blocking/allowing traffic needs a policy-enforcing CNI, which kindnet (kind's default) is not
- `server.updateStrategy: RollingUpdate` **actually running** against `ReadWriteMany` storage —
  attempted with a self-hosted NFS server standing in for real RWX storage, PVCs bound
  correctly (see above), but the pod itself never got past `ContainerCreating`: the NFS export
  kept coming back empty on remount (`No such file or directory`) despite confirming its
  contents moments earlier, most likely NFS-over-`hostNetwork` mount-namespace flakiness specific
  to this kind-on-Docker-Desktop-on-Windows/WSL2 host rather than anything Kubernetes- or
  chart-related. Worth retrying against a real RWX StorageClass (Longhorn, an NFS CSI driver, or
  a cloud provider's RWX class) rather than a hand-rolled NFS server next time.
