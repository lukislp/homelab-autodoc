"""Typed Kubernetes API clients, built once and passed around explicitly."""

from __future__ import annotations

from dataclasses import dataclass

from kubernetes import client


@dataclass(frozen=True, slots=True)
class K8sApis:
    core_v1: client.CoreV1Api
    apps_v1: client.AppsV1Api
    networking_v1: client.NetworkingV1Api

    @classmethod
    def build(cls) -> K8sApis:
        return cls(
            core_v1=client.CoreV1Api(),
            apps_v1=client.AppsV1Api(),
            networking_v1=client.NetworkingV1Api(),
        )
