"""Typed Kubernetes API clients, built once and passed around explicitly."""

from __future__ import annotations

from dataclasses import dataclass

from kubernetes import client


@dataclass(frozen=True, slots=True)
class K8sApis:
    core_v1: client.CoreV1Api
    apps_v1: client.AppsV1Api
    networking_v1: client.NetworkingV1Api
    batch_v1: client.BatchV1Api
    # Gateway API (HTTPRoute) is a CRD, not part of the core/apps/networking
    # API groups the typed client ships bindings for - CustomObjectsApi is
    # the generic (untyped, dict-based) way to read any CRD.
    custom_objects: client.CustomObjectsApi
    autoscaling_v2: client.AutoscalingV2Api

    @classmethod
    def build(cls) -> K8sApis:
        return cls(
            core_v1=client.CoreV1Api(),
            apps_v1=client.AppsV1Api(),
            networking_v1=client.NetworkingV1Api(),
            batch_v1=client.BatchV1Api(),
            custom_objects=client.CustomObjectsApi(),
            autoscaling_v2=client.AutoscalingV2Api(),
        )
