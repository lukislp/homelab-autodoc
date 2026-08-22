"""Command-line entry point: `autodoc-collector`."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from autodoc_core.serialize import to_text

from . import __version__
from .collect import collect_cluster_inventory
from .config import load_kube_config, resolve_cluster_name


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="autodoc-collector",
        description="Read-only Kubernetes inventory collector for homelab-autodoc.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument(
        "--cluster-name",
        help="Display name for this cluster. Defaults to CLUSTER_NAME env var, "
        "then the active kubeconfig context name.",
    )
    parser.add_argument("--kubeconfig", help="Path to a kubeconfig file (local/dev use).")
    parser.add_argument("--context", help="kubeconfig context to use (local/dev use).")
    parser.add_argument(
        "--namespace",
        action="append",
        dest="namespaces",
        help="Namespace to include (repeatable). Defaults to all non-system namespaces.",
    )
    parser.add_argument(
        "--include-system",
        action="store_true",
        help="Also collect kube-system/kube-public/kube-node-lease.",
    )
    parser.add_argument(
        "--format",
        choices=["json", "yaml"],
        default="json",
        help="Output format (default: json).",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Write to this file instead of stdout.",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Compact JSON output (ignored for yaml).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    load_kube_config(kubeconfig=args.kubeconfig, context=args.context)
    cluster_name = resolve_cluster_name(args.cluster_name)

    inventory = collect_cluster_inventory(
        cluster_name=cluster_name,
        namespaces=args.namespaces,
        include_system=args.include_system,
    )
    text = to_text(inventory, fmt=args.format, pretty=not args.compact)

    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text)

    return 0


if __name__ == "__main__":
    sys.exit(main())
