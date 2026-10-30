"""Which kind of provider sits at an address, worked out from the host.

The name sent for a model depends on it: ``anthropic/claude-sonnet-5`` at
OpenRouter is ``claude-sonnet-5`` at Anthropic's own API. An unrecognised
external host is ``UNKNOWN``: the identifier is sent as it stands.
"""

from __future__ import annotations

from enum import Enum

from syft_benchmark.config import host_is_inside, model_host


class ProviderKind(str, Enum):
    """Whose API answers at an address."""

    OLLAMA = "ollama"
    OPENROUTER = "openrouter"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    UNKNOWN = "unknown"


# The hosts whose naming is known. A suffix match, so a regional subdomain of
# the same provider is still that provider.
_HOSTS: tuple[tuple[str, ProviderKind], ...] = (
    ("openrouter.ai", ProviderKind.OPENROUTER),
    ("api.openai.com", ProviderKind.OPENAI),
    ("api.anthropic.com", ProviderKind.ANTHROPIC),
)


def api_root(url: str) -> str:
    """The provider's root without /v1: the settings hold the base address."""
    return url.rstrip("/").removesuffix("/v1")


def kind_for_url(url: str) -> ProviderKind:
    """The kind of provider at this address.

    Args:
        url: The base address of a role's provider

    Returns:
        The kind. ``UNKNOWN`` for an external host with no naming rules here.
    """
    host = model_host(url)
    if not host:
        return ProviderKind.UNKNOWN
    # What the perimeter lets through unasked is the rig's own Ollama.
    if host_is_inside(host):
        return ProviderKind.OLLAMA
    for suffix, kind in _HOSTS:
        if host == suffix or host.endswith(f".{suffix}"):
            return kind
    return ProviderKind.UNKNOWN
