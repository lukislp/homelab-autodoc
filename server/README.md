# autodoc-server

Receives pushed cluster inventories from the [collector](../collector), turns them into a Markdown site via the [generator](../generator), and serves the built [MkDocs Material](https://squidfunk.github.io/mkdocs-material/) site over HTTP.

## Layers

- [`logic/`](src/autodoc_server/logic) - framework-free: filesystem storage for inventories (`storage.py`) and turning them into the MkDocs source tree + built static site (`site_builder.py`). No `fastapi`/`starlette`/`uvicorn` import anywhere in here, by convention - it's fully testable and reusable without the web layer.
- [`web/`](src/autodoc_server/web) - the FastAPI app. Routes only validate input and call into `logic/`; no business logic lives here.

## Endpoints

- `POST /device/code` - a cluster requests registration with no pre-shared secret (`{"cluster_name": "..."}`), gets back a `device_code`, a short human-readable `user_code`, and a `verification_uri`.
- `POST /device/token` - the cluster polls this with its `device_code`. Returns `authorization_pending` / `access_denied` / `expired_token` (matching RFC 8628's error vocabulary) until an admin approves it, at which point it returns the cluster's `push_token`.
- `GET /admin/devices` / `POST /admin/devices/{user_code}/approve` / `.../deny` - admin-facing: list and decide on pending registrations. Requires an `X-Admin-Token` header.
- `POST /api/clusters/{cluster_name}/inventory` - push an inventory (`{"format": "json"|"yaml", "text": "..."}`) using the token issued on approval, regenerates that cluster's docs and rebuilds the site. Requires an `X-Push-Token` header matching that cluster's issued token.
- `GET /healthz`
- `GET /` - the built site (static files).

## Auth: still partly temporary

Cluster registration is now the real thing: the [OAuth 2.0 Device Authorization Grant](https://www.rfc-editor.org/rfc/rfc8628) (`logic/device_grant.py`) - no pre-shared secret, each cluster gets its own token only after an admin approves it, and that token is scoped to exactly that cluster (`Storage.verify_push_token`), not shared across clusters like the old single `AUTODOC_PUSH_TOKEN` was.

What's still a stopgap: the `/admin/devices/*` endpoints themselves are gated by a single shared `AUTODOC_ADMIN_TOKEN` (checked in [`web/admin_auth.py`](src/autodoc_server/web/admin_auth.py)), not a real login. That gets replaced by pluggable GitHub/OIDC admin login + a setup wizard in a follow-up - at which point `/admin/devices` also becomes an actual web page instead of a JSON API.

## Configuration

| Env var | Default | Meaning |
|---|---|---|
| `AUTODOC_DATA_DIR` | `data` | Where raw pushed inventories and per-cluster push tokens are stored |
| `AUTODOC_DOCS_DIR` | `docs_src` | Generated Markdown (MkDocs `docs_dir`) |
| `AUTODOC_MKDOCS_CONFIG` | `mkdocs.yml` | Path to the MkDocs config |
| `AUTODOC_ADMIN_TOKEN` | *(required)* | Temporary shared token for `/admin/devices/*`, sent as `X-Admin-Token` |
| `AUTODOC_LLM_MODEL` | *(unset = no LLM)* | LiteLLM model string for the prose summary |
| `AUTODOC_LLM_API_KEY` / `AUTODOC_LLM_API_BASE` | *(unset)* | Passed straight to LiteLLM |

## Usage

```bash
pip install -e ../core -e ../generator -e ".[dev]"

AUTODOC_ADMIN_TOKEN=change-me autodoc-server --port 8000

# 1. cluster registers:
curl -X POST http://localhost:8000/device/code -H "Content-Type: application/json" \
  -d '{"cluster_name": "homelab"}'
# -> shows a user_code and verification_uri

# 2. admin approves it:
curl -X POST http://localhost:8000/admin/devices/<user_code>/approve \
  -H "X-Admin-Token: change-me"

# 3. cluster polls for its token, then pushes with it:
curl -X POST http://localhost:8000/device/token -H "Content-Type: application/json" \
  -d '{"device_code": "<device_code>"}'
curl -X POST http://localhost:8000/api/clusters/homelab/inventory \
  -H "X-Push-Token: <push_token>" -H "Content-Type: application/json" \
  -d "{\"format\": \"json\", \"text\": $(cat inventory.json | python3 -c 'import json,sys;print(json.dumps(sys.stdin.read()))')}"
```

Note: the collector CLI doesn't perform this registration/push flow itself yet - that's a separate, not-yet-built piece (the client-side half of the device grant).

## Development

```bash
pip install -e ../core -e ../generator -e ".[dev]"
ruff check .
ruff format --check .
pytest
```
