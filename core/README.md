# autodoc-core

The shared `ClusterInventory` data model for [homelab-autodoc](../README.md) - the deterministic facts that the [collector](../collector) writes and the [generator](../generator) reads. No Kubernetes or LLM dependency, just the model and its JSON/YAML (de)serialization.

## Development

```bash
pip install -e ".[dev]"
ruff check .
ruff format --check .
pytest
```
