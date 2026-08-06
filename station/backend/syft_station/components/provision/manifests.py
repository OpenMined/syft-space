"""Render the per-space Kubernetes manifests from templates.

The templates in ``syft_station/k8s/space/*.yaml`` are real, reviewable
manifests with ``${VAR}`` placeholders. Every dynamic value is a scalar (the
env-var set is fixed), so a plain ``string.Template`` substitution is both
safe and keeps the YAML readable as what ``kubectl get -o yaml`` would show.
"""

import string
from pathlib import Path
from typing import Protocol

import yaml

from syft_station.components.provision.interfaces import SpaceSpec

# manifests.py is at syft_station/components/provision/; templates at
# syft_station/k8s/space/ — three parents up to the package root.
TEMPLATE_DIR = Path(__file__).parent.parent.parent / "k8s" / "space"

# Label carrying the space slug; selects a space's whole resource bundle.
LABEL_SPACE = "syftcluster.openmined.org/space"

# Rendered in a fixed apply order (Secret/PVC before the Deployment that
# mounts them; Service before Ingress).
MANIFEST_FILES: tuple[tuple[str, str], ...] = (
    ("secret", "secret.yaml"),
    ("pvc", "pvc.yaml"),
    ("deployment", "deployment.yaml"),
    ("service", "service.yaml"),
    ("ingress", "ingress.yaml"),
)


class RenderSettings(Protocol):
    """The station config values the templates need."""

    namespace: str
    space_image: str
    space_scheme: str
    ingress_class: str
    space_pvc_size: str
    space_cpu_request: str
    space_cpu_limit: str
    space_memory_request: str
    space_memory_limit: str
    chromadb_host: str
    chromadb_port: int
    docling_url: str
    managed_by_name: str
    syfthub_url: object  # str | pydantic HttpUrl — rendered via str()


def resource_name(subdomain: str) -> str:
    """Name shared by every resource in a space's bundle."""
    return f"space-{subdomain}"


def _substitutions(spec: SpaceSpec, settings: RenderSettings) -> dict[str, str]:
    return {
        "RESOURCE_NAME": resource_name(spec.subdomain),
        "NAMESPACE": settings.namespace,
        "SUBDOMAIN": spec.subdomain,
        "OWNER_EMAIL": spec.owner_email,
        "ADMIN_TOKEN": spec.admin_token,
        "IMAGE": f"{settings.space_image}:{spec.version}",
        "CHROMADB_HOST": settings.chromadb_host,
        "CHROMADB_PORT": str(settings.chromadb_port),
        "DOCLING_URL": settings.docling_url,
        "MANAGED_BY": settings.managed_by_name,
        "SYFTHUB_URL": str(settings.syfthub_url).rstrip("/"),
        "PUBLIC_URL": f"{settings.space_scheme}://{spec.subdomain}.{spec.domain}",
        "HOST": f"{spec.subdomain}.{spec.domain}",
        "INGRESS_CLASS": settings.ingress_class,
        "PVC_SIZE": settings.space_pvc_size,
        "CPU_REQUEST": settings.space_cpu_request,
        "CPU_LIMIT": settings.space_cpu_limit,
        "MEMORY_REQUEST": settings.space_memory_request,
        "MEMORY_LIMIT": settings.space_memory_limit,
    }


def _render_one(filename: str, values: dict[str, str]) -> dict:
    text = (TEMPLATE_DIR / filename).read_text()
    rendered = string.Template(text).substitute(values)
    return yaml.safe_load(rendered)


def render_space_manifests(
    spec: SpaceSpec, settings: RenderSettings
) -> dict[str, dict]:
    """Render all per-space manifests as apply-ordered dicts, keyed by kind."""
    values = _substitutions(spec, settings)
    manifests = {key: _render_one(filename, values) for key, filename in MANIFEST_FILES}
    # Managed-credits keys are conditional (a space may have no wallet), so
    # they're injected here rather than templated — the Deployment reads them
    # via optional secretKeyRefs, absent keys simply leave the env unset.
    if spec.credits_token:
        manifests["secret"]["stringData"].update(
            {
                "SYFT_CLUSTER_CREDITS_URL": spec.credits_url,
                "SYFT_CLUSTER_CREDITS_TOKEN": spec.credits_token,
                "SYFT_CLUSTER_CREDITS_CURRENCY": spec.credits_currency,
                "SYFT_CLUSTER_CREDITS_WALLET_ID": spec.credits_wallet_id,
                "SYFT_CLUSTER_PUBLIC_URL": spec.credits_public_url,
            }
        )
        # These two are optional even with a wallet, and omitted rather than
        # sent empty — the space parses them as int/JSON, and "" would crash.
        if spec.credits_wallet_owner:
            manifests["secret"]["stringData"]["SYFT_CLUSTER_WALLET_OWNER"] = (
                spec.credits_wallet_owner
            )
        if spec.credits_bundles:
            manifests["secret"]["stringData"]["SYFT_CLUSTER_BUNDLES"] = (
                spec.credits_bundles
            )
    return manifests
