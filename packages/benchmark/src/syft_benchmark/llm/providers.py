"""Which kind of provider sits at an address.

Turning this service's identifier for a model into the name that will be sent
needs to know whose API is being called: the same model is
``anthropic/claude-sonnet-5`` at OpenRouter and ``claude-sonnet-5`` at
Anthropic's own API.

Worked out from the host rather than configured. Every role already has a URL
in the settings; a second field saying what that URL is would be a second thing
to keep in step, wrong the moment somebody changes one and not the other.

An unrecognised external host is ``UNKNOWN``, not an error: it means "send the
identifier as it stands", which is what a self-hosted gateway expects anyway.
"""

from __future__ import annotations

from enum import Enum
from urllib.parse import urlparse


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

# A host with no dot is a service on the docker network; a local address is the
# rig itself. Both mean Ollama: what the perimeter lets through unasked.
_LOCAL_HOSTS = frozenset(
    {"localhost", "127.0.0.1", "::1", "0.0.0.0", "host.docker.internal"}
)


def kind_for_url(url: str) -> ProviderKind:
    """The kind of provider at this address.

    Args:
        url: The base address of a role's provider

    Returns:
        The kind. ``UNKNOWN`` for an external host with no naming rules here.
    """
    host = (urlparse(url).hostname or "").lower()
    if not host:
        return ProviderKind.UNKNOWN
    if host in _LOCAL_HOSTS or "." not in host:
        return ProviderKind.OLLAMA
    for suffix, kind in _HOSTS:
        if host == suffix or host.endswith(f".{suffix}"):
            return kind
    return ProviderKind.UNKNOWN
