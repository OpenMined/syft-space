"""Whether an address stays on this machine.

The rule is the benchmark's perimeter rule (``syft_benchmark.config.host_is_inside``),
kept here because the two services do not import each other. The Space applies
it only to the addresses it owns: the benchmark it sends keys to, and its own
address as the benchmark calls it. Model providers are classified by the
benchmark, which reports ``local`` per role.
"""

import ipaddress
import re
from urllib.parse import urlparse

from pydantic import BaseModel

_LOCAL_NAMES = frozenset({"localhost", "host.docker.internal"})

# A single DNS label: letters, digits and inner hyphens, at most 63 characters.
_LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?")
# A label a resolver may read as an IPv4 address (``2130706433``, ``0x7f000001``).
_NUMERIC = re.compile(r"0x[0-9a-f]*|[0-9]+")
_CALLABLE_SCHEMES = frozenset({"http", "https"})


class Locality(BaseModel):
    """Where an address points."""

    host: str
    local: bool


def host_of(url: str) -> str:
    """The host of an http(s) ``url``, lower-cased, IPv6 brackets dropped.

    Empty, so not local, when the address has no host or any scheme other than
    http/https, scheme-relative ``//benchmark:8200`` included: no HTTP client
    can call it.
    """
    try:
        parsed = urlparse(url.strip())
        if parsed.scheme not in _CALLABLE_SCHEMES:
            return ""
        return (parsed.hostname or "").lower()
    except ValueError:
        return ""


def host_is_local(host: str) -> bool:
    """``localhost``, ``host.docker.internal``, loopback IP addresses (v4, v6,
    or v4-mapped v6), and a single-label hostname (a Docker service) that no
    resolver reads as a number. Private, link-local and unspecified addresses
    and an empty host are not local."""
    host = host.lower()
    if host in _LOCAL_NAMES:
        return True
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return _LABEL.fullmatch(host) is not None and not _NUMERIC.fullmatch(host)
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
        address = address.ipv4_mapped
    return address.is_loopback


def locality(url: str) -> Locality:
    """The host of ``url`` and whether it is local."""
    host = host_of(url)
    return Locality(host=host, local=host_is_local(host))
