"""Kubernetes provisioner — the real implementation of the Provisioner protocol.

Renders the per-space manifests and applies them as a labeled bundle
(Secret + PVC → Deployment → Service → Ingress), then waits for the
Deployment to report an available replica before calling the space live.
Teardown deletes the bundle in reverse, keeping the PVC unless purge=True.

The ``kubernetes`` client is synchronous; every call goes through
``asyncio.to_thread`` so the station's event loop is never blocked.
"""

import asyncio
import time
from typing import Protocol

from kubernetes.client.rest import ApiException
from loguru import logger

from syft_station.components.provision.interfaces import (
    ProvisionError,
    SpaceRuntimeStatus,
    SpaceSpec,
)
from syft_station.components.provision.kube import KubeClient
from syft_station.components.provision.manifests import (
    RenderSettings,
    render_space_manifests,
    resource_name,
)


class _ProvisionSettings(RenderSettings, Protocol):
    """Render settings plus the fields the provisioner itself needs."""

    provision_timeout_seconds: int
    provision_poll_interval_seconds: float


class K8sProvisioner:
    """Provisions spaces as native Kubernetes resource bundles."""

    def __init__(self, kube: KubeClient, settings: _ProvisionSettings):
        self.kube = kube
        self.settings = settings

    async def check_connection(self) -> str:
        """Probe the cluster (used at startup); returns its version."""
        return await asyncio.to_thread(self.kube.check_connection)

    # ── Provisioner protocol ────────────────────────────────────────────────

    async def provision(self, spec: SpaceSpec) -> str:
        """Apply the space's resource bundle and block until it's live.

        Returns the space URL once the Deployment reports an available
        replica. Any Kubernetes error or the readiness timeout surfaces as a
        ProvisionError (which the request handler turns into a FAILED state).
        """
        manifests = render_space_manifests(spec, self.settings)
        name = resource_name(spec.subdomain)
        try:
            await asyncio.to_thread(self._apply_bundle, manifests)
            await self._wait_until_available(name)
        except ProvisionError:
            raise
        except ApiException as e:
            raise ProvisionError(
                f"Kubernetes API error provisioning '{spec.subdomain}': "
                f"{e.status} {e.reason}"
            ) from e
        except Exception as e:
            raise ProvisionError(f"Failed to provision '{spec.subdomain}': {e}") from e
        return f"https://{spec.subdomain}.{spec.domain}"

    async def deprovision(self, subdomain: str, purge: bool) -> None:
        """Delete the space's resource bundle.

        Keeps the data volume unless purge=True. Already-missing resources
        are ignored, so calling this twice is safe.
        """
        await asyncio.to_thread(self._delete_bundle, subdomain, purge)

    async def pause(self, subdomain: str) -> None:
        """Scale the space to zero replicas — frees compute, keeps data."""
        await asyncio.to_thread(self._scale, subdomain, 0)

    async def resume(self, subdomain: str) -> None:
        """Scale a paused space back to one replica."""
        await asyncio.to_thread(self._scale, subdomain, 1)

    async def get_status(self, subdomain: str) -> SpaceRuntimeStatus:
        """Read the space's live running state from its Deployment."""
        return await asyncio.to_thread(self._read_status, subdomain)

    # ── Sync helpers (run via to_thread) ─────────────────────────────────────

    def _apply_bundle(self, manifests: dict[str, dict]) -> None:
        ns = self.settings.namespace
        # Secret + PVC must exist before the Deployment that mounts them;
        # Service before Ingress.
        self._create_or_update("secret", manifests["secret"], ns)
        self._create_pvc_if_absent(manifests["pvc"], ns)
        self._create_or_update("deployment", manifests["deployment"], ns)
        self._create_or_update("service", manifests["service"], ns)
        self._create_or_update("ingress", manifests["ingress"], ns)

    def _ops(self, kind: str):
        """(create, update) API callables for a kind."""
        core, apps, net = self.kube.core, self.kube.apps, self.kube.networking
        return {
            "secret": (
                core.create_namespaced_secret,
                core.patch_namespaced_secret,
            ),
            "deployment": (
                apps.create_namespaced_deployment,
                apps.patch_namespaced_deployment,
            ),
            "service": (
                core.create_namespaced_service,
                core.patch_namespaced_service,
            ),
            "ingress": (
                net.create_namespaced_ingress,
                net.patch_namespaced_ingress,
            ),
        }[kind]

    def _create_or_update(self, kind: str, manifest: dict, ns: str) -> None:
        name = manifest["metadata"]["name"]
        create, update = self._ops(kind)
        try:
            create(namespace=ns, body=manifest)
            logger.info(f"[k8s] created {kind}/{name}")
        except ApiException as e:
            if e.status != 409:
                raise
            # Retry path: the resource already exists — converge it.
            update(name=name, namespace=ns, body=manifest)
            logger.info(f"[k8s] updated existing {kind}/{name}")

    def _create_pvc_if_absent(self, manifest: dict, ns: str) -> None:
        name = manifest["metadata"]["name"]
        try:
            self.kube.core.create_namespaced_persistent_volume_claim(
                namespace=ns, body=manifest
            )
            logger.info(f"[k8s] created pvc/{name}")
        except ApiException as e:
            if e.status != 409:
                raise
            # A PVC is immutable and holds the space's data — never touch an
            # existing one on retry; just keep it.
            logger.info(f"[k8s] pvc/{name} already exists — keeping its data")

    async def _wait_until_available(self, name: str) -> None:
        """Poll the Deployment until a replica is ready, or time out."""
        ns = self.settings.namespace
        timeout = self.settings.provision_timeout_seconds
        interval = self.settings.provision_poll_interval_seconds
        deadline = time.monotonic() + timeout
        while True:
            deployment = await asyncio.to_thread(
                self.kube.apps.read_namespaced_deployment_status, name, ns
            )
            status = deployment.status
            available = (status.available_replicas or 0) if status else 0
            if available >= 1:
                logger.info(f"[k8s] deployment/{name} is available")
                return
            if time.monotonic() >= deadline:
                raise ProvisionError(
                    f"Deployment '{name}' did not become available within {timeout}s"
                )
            await asyncio.sleep(interval)

    def _scale(self, subdomain: str, replicas: int) -> None:
        name = resource_name(subdomain)
        self.kube.apps.patch_namespaced_deployment_scale(
            name=name,
            namespace=self.settings.namespace,
            body={"spec": {"replicas": replicas}},
        )
        logger.info(f"[k8s] scaled deployment/{name} to {replicas}")

    def _read_status(self, subdomain: str) -> SpaceRuntimeStatus:
        """Derive runtime status from the Deployment's desired vs ready pods.

        desired 0 → PAUSED; a ready pod → RUNNING; desired but none ready
        → UNAVAILABLE (starting or unhealthy); no Deployment → NOT_FOUND.
        """
        name = resource_name(subdomain)
        try:
            deployment = self.kube.apps.read_namespaced_deployment(
                name, self.settings.namespace
            )
        except ApiException as e:
            if e.status == 404:
                return SpaceRuntimeStatus.NOT_FOUND
            raise
        spec = deployment.spec
        desired = spec.replicas if spec and spec.replicas is not None else 0
        status = deployment.status
        available = (status.available_replicas or 0) if status else 0
        if desired == 0:
            return SpaceRuntimeStatus.PAUSED
        if available >= 1:
            return SpaceRuntimeStatus.RUNNING
        return SpaceRuntimeStatus.UNAVAILABLE

    def _delete_bundle(self, subdomain: str, purge: bool) -> None:
        ns = self.settings.namespace
        name = resource_name(subdomain)
        core, apps, net = self.kube.core, self.kube.apps, self.kube.networking
        # Reverse of apply order; 404s are fine (idempotent teardown).
        self._delete(net.delete_namespaced_ingress, name, ns, "ingress")
        self._delete(core.delete_namespaced_service, name, ns, "service")
        self._delete(apps.delete_namespaced_deployment, name, ns, "deployment")
        self._delete(core.delete_namespaced_secret, name, ns, "secret")
        if purge:
            self._delete(
                core.delete_namespaced_persistent_volume_claim, name, ns, "pvc"
            )
        else:
            logger.info(f"[k8s] keeping pvc/{name} (purge=False)")

    @staticmethod
    def _delete(fn, name: str, ns: str, kind: str) -> None:
        try:
            fn(name=name, namespace=ns)
            logger.info(f"[k8s] deleted {kind}/{name}")
        except ApiException as e:
            if e.status == 404:
                return
            raise
