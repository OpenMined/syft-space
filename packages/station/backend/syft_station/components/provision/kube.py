"""Kubernetes client construction and config resolution.

The one place that decides how we authenticate to the cluster:

  1. In-cluster (KUBERNETES_SERVICE_HOST set) → the pod's ServiceAccount.
  2. Else a configured kubeconfig path (SYFT_STATION_KUBECONFIG).
  3. Else the default kubeconfig (~/.kube/config) — local dev against k3d.

KubeClient bundles the typed API objects the provisioner uses. Tests build
one from a fake ApiClient, so nothing here touches a real cluster under test.
"""

import os

from kubernetes import client, config
from loguru import logger


class KubeConfigError(Exception):
    """The cluster connection could not be established."""


def _in_cluster() -> bool:
    return "KUBERNETES_SERVICE_HOST" in os.environ


def build_api_client(kubeconfig: str = "") -> client.ApiClient:
    """Resolve credentials and return a configured ApiClient.

    Raises KubeConfigError if no usable configuration is found.
    """
    try:
        if _in_cluster():
            logger.info("Loading in-cluster Kubernetes config (ServiceAccount)")
            config.load_incluster_config()
        elif kubeconfig:
            logger.info(f"Loading Kubernetes config from {kubeconfig}")
            config.load_kube_config(config_file=kubeconfig)
        else:
            logger.info("Loading default kubeconfig (~/.kube/config)")
            config.load_kube_config()
    except config.ConfigException as e:
        raise KubeConfigError(f"Could not load Kubernetes config: {e}") from e

    return client.ApiClient()


class KubeClient:
    """Typed Kubernetes API accessors over a single ApiClient."""

    def __init__(self, api_client: client.ApiClient):
        self.api_client = api_client
        self.core = client.CoreV1Api(api_client)
        self.apps = client.AppsV1Api(api_client)
        self.networking = client.NetworkingV1Api(api_client)

    @classmethod
    def from_env(cls, kubeconfig: str = "") -> "KubeClient":
        """Build a client using in-cluster / kubeconfig resolution."""
        return cls(build_api_client(kubeconfig))

    def check_connection(self) -> str:
        """Probe the cluster; return its version string, or raise.

        Synchronous — call via asyncio.to_thread from async code.
        """
        try:
            version = client.VersionApi(self.api_client).get_code()
        except Exception as e:  # ApiException, urllib3 errors, etc.
            raise KubeConfigError(f"Cannot reach the Kubernetes cluster: {e}") from e
        return version.git_version
