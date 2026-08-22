# autodoc-server

Receives pushed cluster inventories from the [collector](../collector), turns them into a Markdown site via the [generator](../generator), and serves the built [MkDocs Material](https://squidfunk.github.io/mkdocs-material/) site over HTTP.

## Layers

- [`logic/`](src/autodoc_server/logic) - framework-free: filesystem storage for inventories (`storage.py`) and turning them into the MkDocs source tree + built static site (`site_builder.py`). No `fastapi`/`starlette`/`uvicorn` import anywhere in here, by convention - it's fully testable and reusable without the web layer.
- [`web/`](src/autodoc_server/web) - the FastAPI app. Routes only validate input and call into `logic/`; no business logic lives here.

## Endpoints

- `POST /api/clusters/{cluster_name}/inventory` - push an inventory (`{"format": "json"|"yaml", "text": "..."}`), regenerates that cluster's docs and rebuilds the site. Requires an `X-Push-Token` header.
- `GET /healthz`
- `GET /` - the built site (static files).

## Auth: temporary

The push endpoint is currently gated by a single shared token (`AUTODOC_PUSH_TOKEN` env var, checked in [`web/auth.py`](src/autodoc_server/web/auth.py)) - a stopgap, not the final design. It gets replaced by the OAuth 2.0 Device Authorization Grant (a cluster self-registers, an admin approves/denies it from a web page) in S3.5, alongside a pluggable GitHub/OIDC admin login for the rest of the UI.

## Configuration

| Env var | Default | Meaning |
|---|---|---|
| `AUTODOC_DATA_DIR` | `data` | Where raw pushed inventories are stored |
| `AUTODOC_DOCS_DIR` | `docs_src` | Generated Markdown (MkDocs `docs_dir`) |
| `AUTODOC_MKDOCS_CONFIG` | `mkdocs.yml` | Path to the MkDocs config |
| `AUTODOC_PUSH_TOKEN` | *(required)* | Shared token clients must send as `X-Push-Token` |
| `AUTODOC_LLM_MODEL` | *(unset = no LLM)* | LiteLLM model string for the prose summary |
| `AUTODOC_LLM_API_KEY` / `AUTODOC_LLM_API_BASE` | *(unset)* | Passed straight to LiteLLM |

## Usage

```bash
pip install -e ../core -e ../generator -e ".[dev]"

AUTODOC_PUSH_TOKEN=change-me autodoc-server --port 8000

# from a collector inventory:
curl -X POST http://localhost:8000/api/clusters/homelab/inventory \
  -H "X-Push-Token: change-me" -H "Content-Type: application/json" \
  -d "{\"format\": \"json\", \"text\": $(cat inventory.json | python3 -c 'import json,sys;print(json.dumps(sys.stdin.read()))')}"
```

## Development

```bash
pip install -e ../core -e ../generator -e ".[dev]"
ruff check .
ruff format --check .
pytest
```
