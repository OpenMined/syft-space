"""K8sProvisioner apply/wait/delete — driven by a recording fake, no cluster."""

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from kubernetes.client.rest import ApiException

from syft_station.components.provision import k8s as k8s_module
from syft_station.components.provision.interfaces import (
    ProvisionError,
    SpaceRuntimeStatus,
    SpaceSpec,
)
from syft_station.components.provision.k8s import K8sProvisioner

SETTINGS = SimpleNamespace(
    namespace="syft-spaces",
    space_image="openmined/syft-space",
    space_scheme="https",
    ingress_class="traefik",
    space_pvc_size="2Gi",
    space_cpu_request="250m",
    space_cpu_limit="1",
    space_memory_request="512Mi",
    space_memory_limit="2Gi",
    chromadb_host="chromadb",
    chromadb_port=8100,
    docling_url="http://docling-serve:5001",
    managed_by_name="Syft Station",
    space_host_mount=False,
    syfthub_url="https://hub.test",
    provision_timeout_seconds=5,
    provision_poll_interval_seconds=0.01,
)

SPEC = SpaceSpec(
    subdomain="alpha",
    space_name="Alpha Lab",
    owner_email="alice@test.com",
    version="1.2.3",
    domain="spaces.test.org",
    admin_token="sst_secrettoken",
)


class FakeKube:
    """Records API calls; core/apps/networking all resolve to this object
    (method names are unique across the three APIs)."""

    def __init__(self):
        self.calls: list[tuple[str, str, str]] = []  # (verb, kind, name)
        self.create_status: dict[str, int] = {}  # kind -> status to raise
        self.notfound_delete: set[str] = set()  # kinds that 404 on delete
        self.available_after_reads = 0  # reads that report 0 before ready
        self.status_read_count = 0
        self.scaled_to: int | None = None  # last replica count set
        self.spec_replicas = 1  # what read_namespaced_deployment reports
        self.available_replicas = 1
        self.deployment_missing = False  # read raises 404
        self.deployment_patches: list[dict] = []  # bodies passed to patch
        self.pods: list = []  # returned by list_namespaced_pod
        self.pod_list_selectors: list[str] = []
        self.pod_log = ""  # returned by read_namespaced_pod_log
        self.pod_log_error = False  # log read raises
        self.log_requests: list[dict] = []
        self.core = self.apps = self.networking = self

    def check_connection(self) -> str:
        return "v1.30.0-fake"

    # -- create --
    def _create(self, kind: str, body: dict) -> None:
        self.calls.append(("create", kind, body["metadata"]["name"]))
        if kind in self.create_status:
            raise ApiException(status=self.create_status[kind], reason="err")

    def create_namespaced_secret(self, namespace, body):
        self._create("secret", body)

    def create_namespaced_persistent_volume_claim(self, namespace, body):
        self._create("pvc", body)

    def create_namespaced_deployment(self, namespace, body):
        self._create("deployment", body)

    def create_namespaced_service(self, namespace, body):
        self._create("service", body)

    def create_namespaced_ingress(self, namespace, body):
        self._create("ingress", body)

    # -- patch (update on 409) --
    def patch_namespaced_secret(self, name, namespace, body):
        self.calls.append(("patch", "secret", name))

    def patch_namespaced_deployment(self, name, namespace, body):
        self.calls.append(("patch", "deployment", name))
        self.deployment_patches.append(body)

    def patch_namespaced_service(self, name, namespace, body):
        self.calls.append(("patch", "service", name))

    def patch_namespaced_ingress(self, name, namespace, body):
        self.calls.append(("patch", "ingress", name))

    # -- delete --
    def _delete(self, kind: str, name: str) -> None:
        self.calls.append(("delete", kind, name))
        if kind in self.notfound_delete:
            raise ApiException(status=404, reason="Not Found")

    def delete_namespaced_secret(self, name, namespace):
        self._delete("secret", name)

    def delete_namespaced_persistent_volume_claim(self, name, namespace):
        self._delete("pvc", name)

    def delete_namespaced_deployment(self, name, namespace):
        self._delete("deployment", name)

    def delete_namespaced_service(self, name, namespace):
        self._delete("service", name)

    def delete_namespaced_ingress(self, name, namespace):
        self._delete("ingress", name)

    # -- pods --
    def list_namespaced_pod(self, namespace, label_selector=None):
        self.pod_list_selectors.append(label_selector)
        return SimpleNamespace(items=self.pods)

    def read_namespaced_pod_log(
        self, name, namespace, container=None, previous=None, tail_lines=None
    ):
        self.log_requests.append(
            {
                "name": name,
                "container": container,
                "previous": previous,
                "tail_lines": tail_lines,
            }
        )
        if self.pod_log_error:
            raise ApiException(status=400, reason="no previous container")
        return self.pod_log

    # -- status --
    def read_namespaced_deployment_status(self, name, namespace):
        self.status_read_count += 1
        ready = self.status_read_count > self.available_after_reads
        return SimpleNamespace(
            status=SimpleNamespace(available_replicas=1 if ready else 0)
        )

    # -- scale / runtime status --
    def patch_namespaced_deployment_scale(self, name, namespace, body):
        self.calls.append(("scale", "deployment", name))
        self.scaled_to = body["spec"]["replicas"]

    def read_namespaced_deployment(self, name, namespace):
        if self.deployment_missing:
            raise ApiException(status=404, reason="Not Found")
        return SimpleNamespace(
            spec=SimpleNamespace(replicas=self.spec_replicas),
            status=SimpleNamespace(available_replicas=self.available_replicas),
        )


def verbs(calls, verb):
    return [(kind, name) for v, kind, name in calls if v == verb]


def make_pod(
    reason=None,
    message=None,
    image="ghcr.io/openmined/syft-space:dev",
    phase="Pending",
    unschedulable=False,
    deleting=False,
    created=None,
    init=False,
    name="space-alpha-abc123",
):
    """A pod SimpleNamespace with one container in the given waiting state."""
    waiting = SimpleNamespace(reason=reason, message=message) if reason else None
    cs = SimpleNamespace(
        name="space", image=image, state=SimpleNamespace(waiting=waiting)
    )
    conditions = (
        [SimpleNamespace(type="PodScheduled", status="False", reason="Unschedulable")]
        if unschedulable
        else []
    )
    return SimpleNamespace(
        metadata=SimpleNamespace(
            name=name,
            deletion_timestamp="2026-01-01T00:00:00Z" if deleting else None,
            creation_timestamp=created,
        ),
        status=SimpleNamespace(
            phase=phase,
            conditions=conditions,
            container_statuses=None if init else [cs],
            init_container_statuses=[cs] if init else None,
        ),
    )


def with_timeout(seconds):
    return SimpleNamespace(
        **{**SETTINGS.__dict__, "provision_timeout_seconds": seconds}
    )


@pytest.fixture
def kube() -> FakeKube:
    return FakeKube()


@pytest.fixture
def provisioner(kube) -> K8sProvisioner:
    return K8sProvisioner(kube, SETTINGS)


# ============== provision ==============


async def test_provision_applies_bundle_in_order_and_returns_url(provisioner, kube):
    url = await provisioner.provision(SPEC)

    assert url == "https://alpha.spaces.test.org"
    assert verbs(kube.calls, "create") == [
        ("secret", "space-alpha"),
        ("pvc", "space-alpha"),
        ("deployment", "space-alpha"),
        ("service", "space-alpha"),
        ("ingress", "space-alpha"),
    ]


async def test_provision_waits_until_deployment_available(provisioner, kube):
    kube.available_after_reads = 2  # 0, 0, then 1
    await provisioner.provision(SPEC)
    assert kube.status_read_count == 3


async def test_provision_times_out_to_provision_error(kube):
    kube.available_after_reads = 999  # never becomes available
    provisioner = K8sProvisioner(kube, with_timeout(0))

    with pytest.raises(ProvisionError, match="did not become available"):
        await provisioner.provision(SPEC)


async def test_retry_updates_existing_resources_but_keeps_pvc(provisioner, kube):
    # Everything already exists (a prior failed attempt left the bundle).
    kube.create_status = dict.fromkeys(
        ("secret", "pvc", "deployment", "service", "ingress"), 409
    )

    await provisioner.provision(SPEC)

    # Existing objects are converged via patch...
    assert ("secret", "space-alpha") in verbs(kube.calls, "patch")
    assert ("deployment", "space-alpha") in verbs(kube.calls, "patch")
    # ...but the PVC is never patched — its data is left untouched.
    assert ("pvc", "space-alpha") not in verbs(kube.calls, "patch")


async def test_api_error_on_create_becomes_provision_error(provisioner, kube):
    kube.create_status = {"deployment": 500}
    with pytest.raises(ProvisionError, match="Kubernetes API error"):
        await provisioner.provision(SPEC)


# ============== status-aware wait ==============


async def test_image_pull_backoff_fails_fast_with_image_and_detail(provisioner, kube):
    kube.available_after_reads = 999
    kube.pods = [make_pod(reason="ImagePullBackOff", message="manifest not found")]

    with pytest.raises(ProvisionError) as e:
        await provisioner.provision(SPEC)

    msg = str(e.value)
    assert "ImagePullBackOff" in msg
    assert "ghcr.io/openmined/syft-space:dev" in msg
    assert "manifest not found" in msg
    # Failed on the first tick — the 5s timeout was not burned.
    assert kube.status_read_count == 1
    assert kube.pod_list_selectors == ["syftcluster.openmined.org/space=alpha"]


async def test_crash_loop_fails_fast_with_log_tail(provisioner, kube):
    kube.available_after_reads = 999
    kube.pods = [make_pod(reason="CrashLoopBackOff")]
    kube.pod_log = "Traceback (most recent call last):\n  ValueError: boom\n"

    with pytest.raises(ProvisionError, match="CrashLoopBackOff") as e:
        await provisioner.provision(SPEC)

    assert "ValueError: boom" in str(e.value)
    (req,) = kube.log_requests
    assert req["previous"] is True
    assert req["tail_lines"] == 5
    assert req["container"] == "space"


async def test_crash_loop_log_fetch_failure_still_reports_crash(provisioner, kube):
    kube.available_after_reads = 999
    kube.pods = [make_pod(reason="CrashLoopBackOff")]
    kube.pod_log_error = True

    with pytest.raises(ProvisionError, match="CrashLoopBackOff"):
        await provisioner.provision(SPEC)


async def test_config_error_passes_kubelet_message_through(provisioner, kube):
    kube.available_after_reads = 999
    kube.pods = [
        make_pod(
            reason="CreateContainerConfigError",
            message='secret "space-alpha" not found',
        )
    ]

    with pytest.raises(ProvisionError, match='secret "space-alpha" not found'):
        await provisioner.provision(SPEC)


async def test_fatal_state_in_init_container_is_seen(provisioner, kube):
    kube.available_after_reads = 999
    kube.pods = [make_pod(reason="InvalidImageName", init=True)]

    with pytest.raises(ProvisionError, match="InvalidImageName"):
        await provisioner.provision(SPEC)


async def test_err_image_pull_alone_keeps_waiting(provisioner, kube):
    # A registry blip surfaces as ErrImagePull before the kubelet escalates
    # to BackOff — it gets natural grace rather than an instant failure.
    kube.available_after_reads = 3
    kube.pods = [make_pod(reason="ErrImagePull", message="registry blip")]

    await provisioner.provision(SPEC)


async def test_container_creating_never_fails_early(provisioner, kube):
    kube.available_after_reads = 3
    kube.pods = [make_pod(reason="ContainerCreating")]

    await provisioner.provision(SPEC)

    assert kube.status_read_count == 4


async def test_timeout_message_carries_last_observed_state(kube):
    kube.available_after_reads = 999
    kube.pods = [make_pod(unschedulable=True)]  # not fatal — kept waiting
    provisioner = K8sProvisioner(kube, with_timeout(0))

    with pytest.raises(ProvisionError, match=r"last state: Unschedulable"):
        await provisioner.provision(SPEC)


async def test_progress_extends_deadline_past_base_timeout(kube, monkeypatch):
    # Uncap the extension so timing jitter can't hit the hard deadline.
    monkeypatch.setattr(k8s_module, "_DEADLINE_CAP_FACTOR", 1000)
    kube.available_after_reads = 10  # ~10 ticks of work vs a 0.02s timeout
    kube.pods = [make_pod(reason="ContainerCreating")]
    provisioner = K8sProvisioner(kube, with_timeout(0.02))

    await provisioner.provision(SPEC)  # would time out without extension


async def test_ambiguous_state_does_not_extend_deadline(kube):
    kube.available_after_reads = 999
    kube.pods = [make_pod(phase="Pending")]  # no waiting reason — ambiguous
    provisioner = K8sProvisioner(kube, with_timeout(0.02))

    with pytest.raises(ProvisionError, match="last state: Pending"):
        await provisioner.provision(SPEC)

    assert kube.status_read_count < 10


async def test_hard_cap_bounds_even_continuous_progress(kube):
    kube.available_after_reads = 999
    kube.pods = [make_pod(reason="ContainerCreating")]
    provisioner = K8sProvisioner(kube, with_timeout(0.02))

    with pytest.raises(ProvisionError, match="did not become available"):
        await provisioner.provision(SPEC)


async def test_terminating_pods_are_ignored(kube):
    kube.available_after_reads = 999
    kube.pods = [make_pod(reason="ImagePullBackOff", deleting=True)]
    provisioner = K8sProvisioner(kube, with_timeout(0))

    with pytest.raises(ProvisionError, match="last state: no pods observed"):
        await provisioner.provision(SPEC)


async def test_newest_pod_wins_over_old_crashing_pod(provisioner, kube):
    old = make_pod(
        reason="CrashLoopBackOff",
        created=datetime(2026, 1, 1, tzinfo=UTC),
    )
    new = make_pod(
        reason="ContainerCreating",
        created=datetime(2026, 1, 2, tzinfo=UTC),
    )
    kube.available_after_reads = 3
    kube.pods = [old, new]

    # The old attempt's crash is not this attempt's verdict.
    await provisioner.provision(SPEC)


# ============== deprovision ==============


async def test_deprovision_keeps_pvc_by_default(provisioner, kube):
    await provisioner.deprovision("alpha", purge=False)
    assert verbs(kube.calls, "delete") == [
        ("ingress", "space-alpha"),
        ("service", "space-alpha"),
        ("deployment", "space-alpha"),
        ("secret", "space-alpha"),
    ]


async def test_deprovision_purge_also_deletes_pvc_last(provisioner, kube):
    await provisioner.deprovision("alpha", purge=True)
    assert verbs(kube.calls, "delete")[-1] == ("pvc", "space-alpha")


async def test_deprovision_ignores_missing_resources(provisioner, kube):
    kube.notfound_delete = {"ingress", "service", "deployment", "secret"}
    # Should not raise despite every delete 404-ing.
    await provisioner.deprovision("alpha", purge=False)


# ============== restart ==============


async def test_restart_bumps_pod_template_annotation(provisioner, kube):
    await provisioner.restart("alpha")

    assert ("patch", "deployment", "space-alpha") in kube.calls
    (body,) = kube.deployment_patches
    annotations = body["spec"]["template"]["metadata"]["annotations"]
    assert "syftcluster.openmined.org/restartedAt" in annotations


# ============== pause / resume / status ==============


async def test_pause_scales_to_zero(provisioner, kube):
    await provisioner.pause("alpha")
    assert ("scale", "deployment", "space-alpha") in kube.calls
    assert kube.scaled_to == 0


async def test_resume_scales_to_one(provisioner, kube):
    await provisioner.resume("alpha")
    assert kube.scaled_to == 1


async def test_status_running(provisioner, kube):
    kube.spec_replicas, kube.available_replicas = 1, 1
    assert await provisioner.get_status("alpha") == SpaceRuntimeStatus.RUNNING


async def test_status_paused_when_scaled_to_zero(provisioner, kube):
    kube.spec_replicas, kube.available_replicas = 0, 0
    assert await provisioner.get_status("alpha") == SpaceRuntimeStatus.PAUSED


async def test_status_unavailable_when_desired_but_no_pod(provisioner, kube):
    kube.spec_replicas, kube.available_replicas = 1, 0
    assert await provisioner.get_status("alpha") == SpaceRuntimeStatus.UNAVAILABLE


async def test_status_not_found_when_deployment_missing(provisioner, kube):
    kube.deployment_missing = True
    assert await provisioner.get_status("alpha") == SpaceRuntimeStatus.NOT_FOUND


# ============== check_connection ==============


async def test_check_connection_returns_version(provisioner):
    assert await provisioner.check_connection() == "v1.30.0-fake"
