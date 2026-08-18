"""Kube client construction and config resolution — no real cluster touched."""

import pytest

from syft_station.components.provision import kube
from syft_station.components.provision.kube import (
    KubeClient,
    KubeConfigError,
    build_api_client,
)


class FakeApiClient:
    """Stand-in for kubernetes.client.ApiClient."""


def test_kubeclient_exposes_typed_apis():
    kc = KubeClient(FakeApiClient())
    assert kc.core is not None
    assert kc.apps is not None
    assert kc.networking is not None


# ============== check_connection ==============


def test_check_connection_returns_version(monkeypatch):
    class FakeVersionApi:
        def __init__(self, api_client):
            pass

        def get_code(self):
            return type("V", (), {"git_version": "v1.30.0"})()

    monkeypatch.setattr(kube.client, "VersionApi", FakeVersionApi)
    assert KubeClient(FakeApiClient()).check_connection() == "v1.30.0"


def test_check_connection_wraps_failure(monkeypatch):
    class FakeVersionApi:
        def __init__(self, api_client):
            pass

        def get_code(self):
            raise RuntimeError("no route to host")

    monkeypatch.setattr(kube.client, "VersionApi", FakeVersionApi)
    with pytest.raises(KubeConfigError):
        KubeClient(FakeApiClient()).check_connection()


# ============== build_api_client resolution ==============


@pytest.fixture
def record_config(monkeypatch):
    """Capture which config loader build_api_client calls, without loading."""
    calls: list = []
    monkeypatch.setattr(
        kube.config, "load_incluster_config", lambda: calls.append("incluster")
    )
    monkeypatch.setattr(
        kube.config, "load_kube_config", lambda **kw: calls.append(("kubeconfig", kw))
    )
    monkeypatch.setattr(kube.client, "ApiClient", lambda: FakeApiClient())
    return calls


def test_build_api_client_in_cluster(monkeypatch, record_config):
    monkeypatch.setenv("KUBERNETES_SERVICE_HOST", "10.0.0.1")
    build_api_client()
    assert record_config == ["incluster"]


def test_build_api_client_with_kubeconfig_path(monkeypatch, record_config):
    monkeypatch.delenv("KUBERNETES_SERVICE_HOST", raising=False)
    build_api_client("/tmp/kubeconfig")
    assert record_config == [("kubeconfig", {"config_file": "/tmp/kubeconfig"})]


def test_build_api_client_defaults_to_local_kubeconfig(monkeypatch, record_config):
    monkeypatch.delenv("KUBERNETES_SERVICE_HOST", raising=False)
    build_api_client()
    assert record_config == [("kubeconfig", {})]


def test_build_api_client_wraps_config_exception(monkeypatch):
    monkeypatch.delenv("KUBERNETES_SERVICE_HOST", raising=False)

    def boom(**kw):
        raise kube.config.ConfigException("no config")

    monkeypatch.setattr(kube.config, "load_kube_config", boom)
    with pytest.raises(KubeConfigError):
        build_api_client()
