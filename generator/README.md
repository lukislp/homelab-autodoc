# autodoc-generator

Turns a [collector](../collector) inventory into a Markdown documentation site for [homelab-autodoc](../README.md) - one page per app, a per-namespace index, and a Mermaid dependency diagram.

## The hallucination boundary, structurally

- [`facts.py`](src/autodoc_generator/facts.py) and [`diagrams.py`](src/autodoc_generator/diagrams.py) are pure functions over the inventory - no LLM involved, fully deterministic.
- [`prose.py`](src/autodoc_generator/prose.py) is the *only* module that talks to an LLM. Its prompt is built solely from the same facts, with an explicit instruction not to add anything not listed.
- [`render.py`](src/autodoc_generator/render.py) receives the LLM summary as a plain string - it never calls an LLM itself, so a page can always be regenerated (facts + diagram) with zero LLM involvement via `--llm none`.

## LLM backends

[`llm.py`](src/autodoc_generator/llm.py) defines an `LLMClient` protocol implemented by `LiteLLMClient`, a thin wrapper around [LiteLLM](https://docs.litellm.ai/) - one client covering ~100 providers (Ollama, OpenAI, Anthropic, Azure, ...) selected purely by the `model` string plus an optional `api_key`/`api_base`. Switching providers is a config change, not new code - which is also what the server's setup wizard (S3.5) will expose per-provider.

## Usage

```bash
pip install -e ../core -e ".[dev]"

# Facts + diagrams only, no LLM
autodoc-generator inventory.json --output site/

# With a local Ollama for the per-app prose summary
autodoc-generator inventory.json --output site/ --llm-model ollama/llama3.1 --llm-api-base http://localhost:11434

# With a hosted provider
autodoc-generator inventory.json --output site/ --llm-model gpt-4o --llm-api-key sk-...
```

## Development

```bash
pip install -e ../core -e ".[dev]"
ruff check .
ruff format --check .
pytest
```
