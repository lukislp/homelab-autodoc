"""Command-line entry point: `autodoc-server` runs the HTTP server via uvicorn."""

from __future__ import annotations

import argparse

import uvicorn


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="autodoc-server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    uvicorn.run(
        "autodoc_server.web.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        # Trust X-Forwarded-Proto/-For from the reverse proxy in front of this server (a k8s
        # Gateway/Ingress terminating TLS, in the common deployment) - otherwise
        # request.url_for() thinks every request is plain HTTP, which breaks the OAuth
        # redirect_uri (GitHub/OIDC providers reject it as not matching what's registered).
        # "*" is fine here: only the cluster's own Gateway can reach this pod at all (see the
        # NetworkPolicy in k8s/03-network-policies.yaml), so there's no untrusted path in.
        proxy_headers=True,
        forwarded_allow_ips="*",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
