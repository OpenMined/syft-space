"""Kubernetes provisioner — the real implementation of the Provisioner protocol.

Renders the per-space manifests and applies them as a labeled bundle
(Secret + PVC → Deployment → Service → Ingress), then waits for the
Deployment to report an available replica before calling the space live.
The wait is status-aware: terminally-stuck pods fail fast with a specific
reason, while visible startup progress extends the deadline (capped).
Teardown deletes the bundle in reverse, keeping the PVC unless purge=True.

The ``kubernetes`` client is synchronous; every call goes through
``asyncio.to_thread`` so the station's event loop is never blocked.
"""

import asyncio
import time
from datetime import UTC, datetime
from typing import NamedTuple, Protocol

from kubernetes.client.rest import ApiException
from loguru import logger

from syft_station.components.provision.interfaces import (
    ProvisionError,
    SpaceRuntimeStatus,
    SpaceSpec,
)
from syft_station.components.provision.kube import KubeClient
from syft_station.components.provision.manifests import (
    LABEL_SPACE,
    RenderSettings,
    render_space_manifests,
    resource_name,
)

# Waiting reasons where the kubelet has already given up retrying, or the
# config is provably invalid — more waiting can never fix these. Notably
# absent: ErrImagePull (a registry blip gets natural grace until the kubelet
# escalates it to ImagePullBackOff).
_FATAL_WAITING_REASONS = frozenset(
    {
        "ImagePullBackOff",
        "InvalidImageName",
        "CreateContainerConfigError",
        "CrashLoopBackOff",
    }
)
# Waiting reasons that mean legitimate startup work is underway (e.g. a
# multi-GB image pull on a fresh node) — these extend the readiness deadline.
_PROGRESSING_REASONS = frozenset({"ContainerCreating", "PodInitializing"})

# Visible progress may push the deadline out to at most this many times the
# configured timeout; a hung start still terminates.
_DEADLINE_CAP_FACTOR = 3

_CRASH_LOG_LINES = 5
_CRASH_LOG_MAX_CHARS = 300

_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


class _PodInspection(NamedTuple):
    """What the space's newest pod says about how startup is going."""

    fatal: str | None  # admin-facing reason when the pod is terminally stuck
    state: str  # short snapshot for the timeout message
    progressing: bool  # visibly making startup progress (extends the deadline)


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
            await self._wait_until_available(name, spec.subdomain)
        except ProvisionError:
            raise
        except ApiException as e:
            raise ProvisionError(
                f"Kubernetes API error provisioning '{spec.subdomain}': "
                f"{e.status} {e.reason}"
            ) from e
        except Exception as e:
            raise ProvisionError(f"Failed to provision '{spec.subdomain}': {e}") from e
        return f"{self.settings.space_scheme}://{spec.subdomain}.{spec.domain}"

    async def deprovision(self, subdomain: str, purge: bool) -> None:
        """Delete the space's resource bundle.

        Keeps the data volume unless purge=True. Already-missing resources
        are ignored, so calling this twice is safe.
        """
        await asyncio.to_thread(self._delete_bundle, subdomain, purge)

    async def update_space_secret(self, subdomain: str, data: dict[str, str]) -> None:
        """Merge keys into the space's Secret (strategic-merge patch).

        The running pod keeps its current env — Secret env vars are read at
        container start — so changes apply on the next restart.
        """
        name = resource_name(subdomain)
        await asyncio.to_thread(
            self.kube.core.patch_namespaced_secret,
            name,
            self.settings.namespace,
            {"stringData": data},
        )
        logger.info(f"[k8s] patched secret/{name}: {sorted(data)}")

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

    async def _wait_until_available(self, name: str, subdomain: str) -> None:
        """Poll the Deployment until a replica is ready, or fail with a reason.

        Each tick also inspects the space's pods: terminally-stuck states
        (image can't be pulled, provably broken config, crash loop) fail
        immediately with a specific message instead of burning the whole
        timeout, while visible startup progress (image pull, container
        creation) extends the deadline — capped so a hung start still
        terminates.
        """
        ns = self.settings.namespace
        timeout = self.settings.provision_timeout_seconds
        interval = self.settings.provision_poll_interval_seconds
        start = time.monotonic()
        deadline = start + timeout
        hard_deadline = start + _DEADLINE_CAP_FACTOR * timeout
        last_state = "no pods observed"
        while True:
            deployment = await asyncio.to_thread(
                self.kube.apps.read_namespaced_deployment_status, name, ns
            )
            status = deployment.status
            available = (status.available_replicas or 0) if status else 0
            if available >= 1:
                logger.info(f"[k8s] deployment/{name} is available")
                return
            inspection = await asyncio.to_thread(self._inspect_pods, subdomain)
            if inspection.fatal:
                raise ProvisionError(inspection.fatal)
            last_state = inspection.state
            now = time.monotonic()
            if inspection.progressing:
                deadline = min(now + timeout, hard_deadline)
            if now >= deadline:
                raise ProvisionError(
                    f"Deployment '{name}' did not become available within "
                    f"{round(now - start)}s (last state: {last_state})"
                )
            await asyncio.sleep(interval)

    def _inspect_pods(self, subdomain: str) -> _PodInspection:
        """Classify the newest live pod's startup state (sync, via to_thread)."""
        result = self.kube.core.list_namespaced_pod(
            self.settings.namespace,
            label_selector=f"{LABEL_SPACE}={subdomain}",
        )
        # A retry can overlap the previous attempt's dying pod — only the
        # newest non-terminating pod reflects this attempt.
        live = [p for p in result.items or [] if not p.metadata.deletion_timestamp]
        if not live:
            return _PodInspection(
                fatal=None, state="no pods observed", progressing=False
            )
        pod = max(live, key=lambda p: p.metadata.creation_timestamp or _EPOCH)
        statuses = list(pod.status.container_statuses or []) + list(
            pod.status.init_container_statuses or []
        )
        for cs in statuses:
            waiting = cs.state.waiting if cs.state else None
            if waiting and waiting.reason in _FATAL_WAITING_REASONS:
                return _PodInspection(
                    fatal=self._fatal_message(pod.metadata.name, cs, waiting),
                    state=waiting.reason,
                    progressing=False,
                )
        state = self._state_snapshot(pod, statuses)
        return _PodInspection(
            fatal=None, state=state, progressing=state in _PROGRESSING_REASONS
        )

    @staticmethod
    def _state_snapshot(pod, statuses) -> str:
        """Short human label for what the pod is doing right now."""
        for condition in pod.status.conditions or []:
            if condition.type == "PodScheduled" and condition.status == "False":
                return condition.reason or "Unschedulable"
        for cs in statuses:
            waiting = cs.state.waiting if cs.state else None
            if waiting and waiting.reason:
                return waiting.reason
        return pod.status.phase or "Unknown"

    def _fatal_message(self, pod_name: str, cs, waiting) -> str:
        """Specific, admin-facing reason for a terminally-stuck container."""
        if waiting.reason == "CrashLoopBackOff":
            message = f"container '{cs.name}' keeps crashing (CrashLoopBackOff)"
            tail = self._crash_log_tail(pod_name, cs.name)
            return f"{message}: {tail}" if tail else message
        if waiting.reason == "ImagePullBackOff":
            detail = waiting.message or "image pull failed"
            return f"image '{cs.image}' cannot be pulled (ImagePullBackOff): {detail}"
        # InvalidImageName / CreateContainerConfigError — the kubelet's message
        # already names the broken field (bad tag syntax, missing Secret/key).
        return f"{waiting.reason}: {waiting.message or 'no detail from kubelet'}"

    def _crash_log_tail(self, pod_name: str, container: str) -> str:
        """Last few log lines of the crashed container, best-effort."""
        try:
            text = self.kube.core.read_namespaced_pod_log(
                pod_name,
                self.settings.namespace,
                container=container,
                previous=True,
                tail_lines=_CRASH_LOG_LINES,
            )
        except Exception:
            # Never let a log fetch mask the real failure reason.
            return ""
        lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
        return " | ".join(lines)[:_CRASH_LOG_MAX_CHARS]

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
