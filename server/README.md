# autodoc-server

Receives pushed cluster inventories from the [collector](../collector), turns them into a Markdown site via the [generator](../generator), serves the built [MkDocs Material](https://squidfunk.github.io/mkdocs-material/) site, and hosts the admin app ([frontend/](../frontend)) that a human uses to approve new clusters.

## Layers

- [`logic/`](src/autodoc_server/logic) - framework-free: filesystem storage for inventories and push tokens (`storage.py`), the Device Authorization Grant state machine (`device_grant.py`), the persisted admin-auth config (`auth_config.py`), the OAuth 2.0 Authorization Code client (`oauth_client.py`), and turning inventories into the MkDocs source tree + built static site (`site_builder.py`). No `fastapi`/`starlette`/`uvicorn` import anywhere in here, by convention - it's fully testable and reusable without the web layer.
- [`web/`](src/autodoc_server/web) - the FastAPI app. Routes only validate input and call into `logic/`; no business logic lives here.
- [`../frontend/`](../frontend) - the React admin app (setup wizard + pending-registrations screen), built separately and served as static files at `/admin`.

## Endpoints

**Cluster-facing (no admin session needed):**

- `POST /device/code` - a cluster requests registration with no pre-shared secret (`{"cluster_name": "..."}`), gets back a `device_code`, a short human-readable `user_code`, and a `verification_uri` pointing at `/admin`.
- `POST /device/token` - the cluster polls this with its `device_code`. Returns `authorization_pending` / `access_denied` / `expired_token` (matching RFC 8628's error vocabulary) until an admin approves it, at which point it returns the cluster's `push_token`.
- `POST /api/clusters/{cluster_name}/inventory` - push an inventory (`{"format": "json"|"yaml", "text": "..."}`) using the token issued on approval. Requires an `X-Push-Token` header matching that cluster's issued token.

**Admin-facing (JSON API behind the React app):**

- `GET /api/auth/status` - `{configured, identity}`.
- `POST /api/setup` - save the admin-login provider config (GitHub or a generic OIDC issuer). Allowed once for free; after that, only with an active admin session.
- `GET /auth/login` / `GET /auth/callback` / `GET /auth/logout` - the actual OAuth redirect dance (real browser navigations, not JSON).
- `GET /api/admin/devices` / `POST /api/admin/devices/{user_code}/approve` / `.../deny` - list and decide on pending cluster registrations. Requires an admin session (cookie, set by `/auth/callback`).

**Everything else:**

- `GET /healthz`
- `GET /admin` - the React admin app (static files).
- `GET /` - the built MkDocs site (static files, public - no auth).

## Admin login

Two provider types, chosen at setup time (see `logic/auth_config.py`):

- **GitHub** - plain OAuth 2.0 (no OIDC discovery), identity is the GitHub username.
- **Generic OIDC** - any standards-compliant issuer, endpoints discovered via `{issuer_url}/.well-known/openid-configuration`, identity is the `email` claim.

The Authorization Code flow itself (`logic/oauth_client.py`) is hand-rolled with `httpx` rather than pulled in from a client library like Authlib - it's small and well-specified (RFC 6749 + OIDC Discovery), and owning every HTTP call keeps it fully testable by monkeypatching `httpx`, without mocking a third-party client's internals.

Only one identity is ever allowed to log in - the `allowed_identity` set during setup. If you lock yourself out (lost access to that identity, or the OAuth app was deleted), delete `AUTODOC_CONFIG_DIR/auth.json` and restart; setup runs again on the next request.

## Configuration

| Env var | Default | Meaning |
|---|---|---|
| `AUTODOC_DATA_DIR` | `data` | Where raw pushed inventories and per-cluster push tokens are stored |
| `AUTODOC_DOCS_DIR` | `docs_src` | Generated Markdown (MkDocs `docs_dir`) |
| `AUTODOC_MKDOCS_CONFIG` | `mkdocs.yml` | Path to the MkDocs config |
| `AUTODOC_CONFIG_DIR` | `config` | Where the admin-auth provider config is stored |
| `AUTODOC_ADMIN_UI_DIR` | `../frontend/dist` | Built React app, served at `/admin` |
| `AUTODOC_SESSION_SECRET` | *(random per process)* | Signs the admin session cookie. Unset means sessions don't survive a restart - fine for local use, set it explicitly for a real deployment |
| `AUTODOC_LLM_MODEL` | *(unset = no LLM)* | LiteLLM model string for the prose summary |
| `AUTODOC_LLM_API_KEY` / `AUTODOC_LLM_API_BASE` | *(unset)* | Passed straight to LiteLLM |

## Usage

```bash
pip install -e ../core -e ../generator -e ".[dev]"
(cd ../frontend && npm install && npm run build)

autodoc-server --port 8000
# open http://localhost:8000/admin to run the setup wizard
```

## Development

```bash
pip install -e ../core -e ../generator -e ".[dev]"
ruff check .
ruff format --check .
pytest
```
