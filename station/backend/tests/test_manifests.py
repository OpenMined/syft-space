"""Per-space manifest rendering — golden assertions, no cluster."""

from types import SimpleNamespace

import pytest

from syft_station.components.provision.interfaces import SpaceSpec
from syft_station.components.provision.manifests import (
    render_space_manifests,
    resource_name,
)

SETTINGS = SimpleNamespace(
    namespace="syft-spaces",
    space_image="openmined/syft-space",
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
)

SPEC = SpaceSpec(
    subdomain="alpha",
    space_name="Alpha Lab",
    owner_email="alice@test.com",
    version="1.2.3",
    domain="spaces.test.org",
    admin_token="sst_secrettoken",
)


@pytest.fixture
def manifests() -> dict[str, dict]:
    return render_space_manifests(SPEC, SETTINGS)


def _env(deployment: dict) -> dict[str, dict]:
    """Env list → {name: entry} for easy lookup."""
    container = deployment["spec"]["template"]["spec"]["containers"][0]
    return {e["name"]: e for e in container["env"]}


def test_all_five_manifests_rendered(manifests):
    assert set(manifests) == {"secret", "pvc", "deployment", "service", "ingress"}


def test_every_resource_shares_name_namespace_and_label(manifests):
    for kind, doc in manifests.items():
        assert doc["metadata"]["name"] == "space-alpha", kind
        assert doc["metadata"]["namespace"] == "syft-spaces", kind
        assert (
            doc["metadata"]["labels"]["syftcluster.openmined.org/space"] == "alpha"
        ), kind


def test_resource_name_helper():
    assert resource_name("alpha") == "space-alpha"


# ============== Secret ==============


def test_secret_carries_admin_token(manifests):
    secret = manifests["secret"]
    assert secret["kind"] == "Secret"
    assert secret["stringData"]["SYFT_ADMIN_API_KEY"] == "sst_secrettoken"


# ============== Deployment ==============


def test_deployment_image_is_repo_and_version(manifests):
    container = manifests["deployment"]["spec"]["template"]["spec"]["containers"][0]
    assert container["image"] == "openmined/syft-space:1.2.3"


def test_deployment_uses_recreate_and_single_replica(manifests):
    spec = manifests["deployment"]["spec"]
    assert spec["replicas"] == 1
    assert spec["strategy"]["type"] == "Recreate"


def test_deployment_admin_key_comes_from_secret_not_inline(manifests):
    admin = _env(manifests["deployment"])["SYFT_ADMIN_API_KEY"]
    assert "value" not in admin
    assert admin["valueFrom"]["secretKeyRef"] == {
        "name": "space-alpha",
        "key": "SYFT_ADMIN_API_KEY",
    }


def test_deployment_chromadb_wiring(manifests):
    env = _env(manifests["deployment"])
    assert env["SYFT_CHROMADB_HOST"]["value"] == "chromadb"
    assert env["SYFT_CHROMADB_HTTP_PORT"]["value"] == "8100"
    # Per-space isolation: the Chroma database is the subdomain.
    assert env["SYFT_CHROMADB_DATABASE"]["value"] == "alpha"
    # Must not spawn a local Chroma subprocess.
    assert env["SYFT_CHROMADB_PROVISION"]["value"] == "False"


def test_deployment_analytics_db_stays_on_the_volume(manifests):
    # The gotcha: unset, the image writes analytics.db to $HOME (off-volume).
    env = _env(manifests["deployment"])
    assert env["SYFT_ANALYTICS_DB_PATH"]["value"] == "/data/analytics.db"
    assert env["SYFT_SQLITE_DB_PATH"]["value"] == "/data/app.db"


def test_deployment_docling_and_branding(manifests):
    env = _env(manifests["deployment"])
    assert env["SYFT_DOCLING_SERVE_URL"]["value"] == "http://docling-serve:5001"
    assert env["SYFT_CLUSTER_MANAGED_BY"]["value"] == "Syft Station"
    assert env["SYFT_PUBLIC_URL"]["value"] == "https://alpha.spaces.test.org"


def test_deployment_mounts_pvc_at_data(manifests):
    pod = manifests["deployment"]["spec"]["template"]["spec"]
    container = pod["containers"][0]
    assert container["volumeMounts"][0]["mountPath"] == "/data"
    assert pod["volumes"][0]["persistentVolumeClaim"]["claimName"] == "space-alpha"


def test_deployment_health_probes_hit_the_contract_path(manifests):
    container = manifests["deployment"]["spec"]["template"]["spec"]["containers"][0]
    for probe in ("readinessProbe", "livenessProbe"):
        assert container[probe]["httpGet"]["path"] == "/api/v1/health"
        assert container[probe]["httpGet"]["port"] == 8080


def test_deployment_resources_from_settings(manifests):
    res = manifests["deployment"]["spec"]["template"]["spec"]["containers"][0][
        "resources"
    ]
    assert res["requests"] == {"cpu": "250m", "memory": "512Mi"}
    assert res["limits"] == {"cpu": "1", "memory": "2Gi"}


def test_owner_email_is_an_annotation(manifests):
    meta = manifests["deployment"]["spec"]["template"]["metadata"]
    assert meta["annotations"]["syftcluster.openmined.org/owner-email"] == (
        "alice@test.com"
    )


# ============== Service + Ingress ==============


def test_service_maps_80_to_8080(manifests):
    svc = manifests["service"]
    assert svc["spec"]["selector"] == {"syftcluster.openmined.org/space": "alpha"}
    port = svc["spec"]["ports"][0]
    assert port["port"] == 80
    assert port["targetPort"] == 8080


def test_ingress_routes_host_to_service(manifests):
    ingress = manifests["ingress"]
    assert ingress["spec"]["ingressClassName"] == "traefik"
    rule = ingress["spec"]["rules"][0]
    assert rule["host"] == "alpha.spaces.test.org"
    backend = rule["http"]["paths"][0]["backend"]["service"]
    assert backend["name"] == "space-alpha"
    assert backend["port"]["number"] == 80


def test_real_config_satisfies_render_settings():
    """The live app_settings must expose everything the templates need."""
    from syft_station.config import app_settings

    manifests = render_space_manifests(SPEC, app_settings)
    assert manifests["deployment"]["spec"]["template"]["spec"]["containers"][0][
        "image"
    ].startswith("openmined/syft-space:")
