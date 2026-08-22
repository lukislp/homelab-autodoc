"""Command-line entry point: `autodoc-collector`."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from autodoc_core.serialize import to_text

from . import __version__
from .collect import collect_cluster_inventory
from .config import load_kube_config, resolve_cluster_name
from .push import (
    RegistrationDenied,
    RegistrationExpired,
    poll_for_push_token,
    push_inventory,
    request_device_code,
)
from .token_cache import load_cached_token, save_cached_token


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
    parser.add_argument(
        "--push",
        metavar="SERVER_URL",
        help="Push the inventory to this autodoc-server instead of printing it. "
        "Registers via the Device Authorization Grant on first use (an admin must "
        "approve it), then caches the issued token for future runs.",
    )
    parser.add_argument(
        "--token-file",
        type=Path,
        default=Path(".autodoc-push-token"),
        help="Where to cache this cluster's push token (default: %(default)s).",
    )
    return parser


def _push(args: argparse.Namespace, cluster_name: str, text: str) -> int:
    token = load_cached_token(args.token_file)

    if token is None:
        device = request_device_code(args.push, cluster_name)
        print(f"Registering '{cluster_name}' with {args.push}", file=sys.stderr)
        print(f"Approve at: {device.verification_uri_complete}", file=sys.stderr)
        print(f"(user code: {device.user_code})", file=sys.stderr)
        try:
            token = poll_for_push_token(
                args.push, device.device_code, device.interval, device.expires_in
            )
        except (RegistrationDenied, RegistrationExpired) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        save_cached_token(args.token_file, token)
        print("Registration approved, token cached.", file=sys.stderr)

    result = push_inventory(args.push, cluster_name, token, text, args.format)
    print(f"Pushed: {result}", file=sys.stderr)
    return 0


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
    elif not args.push:
        print(text)

    if args.push:
        return _push(args, cluster_name, text)

    return 0


if __name__ == "__main__":
    sys.exit(main())
