"""Command-line entry point: `autodoc-generator`."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from autodoc_core.serialize import from_text

from . import __version__, render
from .llm import LiteLLMClient
from .prose import generate_summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="autodoc-generator",
        description="Turns a collector inventory into a Markdown documentation site.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("inventory", type=Path, help="Inventory file written by autodoc-collector.")
    parser.add_argument(
        "--format",
        choices=["json", "yaml"],
        help="Inventory format. Defaults to guessing from the file extension.",
    )
    parser.add_argument(
        "--output", "-o", type=Path, required=True, help="Output directory for the Markdown site."
    )
    parser.add_argument(
        "--llm-model",
        default=None,
        help="LiteLLM model string for the prose summary, e.g. 'ollama/llama3.1', 'gpt-4o', "
        "'claude-3-5-sonnet-20241022'. Omit to skip the LLM and emit facts/diagrams only.",
    )
    parser.add_argument("--llm-api-key", default=None)
    parser.add_argument(
        "--llm-api-base", default=None, help="Override API base URL, e.g. a local Ollama server."
    )
    return parser


def _guess_format(path: Path, explicit: str | None) -> str:
    if explicit:
        return explicit
    return "yaml" if path.suffix in (".yaml", ".yml") else "json"


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    fmt = _guess_format(args.inventory, args.format)
    inventory = from_text(args.inventory.read_text(encoding="utf-8"), fmt=fmt)

    llm = (
        LiteLLMClient(model=args.llm_model, api_key=args.llm_api_key, api_base=args.llm_api_base)
        if args.llm_model
        else None
    )

    cluster_dir = args.output / inventory.cluster_name
    for namespace in inventory.namespaces:
        namespace_dir = cluster_dir / namespace.name
        namespace_dir.mkdir(parents=True, exist_ok=True)
        namespace_dir.joinpath("index.md").write_text(
            render.render_namespace_index(namespace, inventory.cluster_name), encoding="utf-8"
        )
        for app in namespace.apps:
            summary = generate_summary(app, llm) if llm else None
            namespace_dir.joinpath(f"{app.name}.md").write_text(
                render.render_app_page(app, namespace, inventory.cluster_name, summary),
                encoding="utf-8",
            )

    return 0


if __name__ == "__main__":
    sys.exit(main())
