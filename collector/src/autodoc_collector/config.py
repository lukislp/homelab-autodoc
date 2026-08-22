"""Kubernetes API client setup - in-cluster ServiceAccount or local kubeconfig."""

from __future__ import annotations

import os

from kubernetes import config


def load_kube_config(kubeconfig: str | None = None, context: str | None = None) -> None:
    """Load in-cluster config when running as a Pod, otherwise fall back to kubeconfig."""
    try:
        config.load_incluster_config()
    except config.ConfigException:
        config.load_kube_config(config_file=kubeconfig, context=context)


def resolve_cluster_name(explicit_name: str | None) -> str:
    """Resolve the cluster's display name.

    Priority: explicit CLI flag > CLUSTER_NAME env var (set on the in-cluster
    CronJob) > the active kubeconfig context name > a generic fallback.
    """
    if explicit_name:
        return explicit_name

    env_name = os.environ.get("CLUSTER_NAME")
    if env_name:
        return env_name

    try:
        _, active_context = config.list_kube_config_contexts()
        return active_context["name"]
    except (config.ConfigException, FileNotFoundError, KeyError, TypeError):
        return "unknown-cluster"
