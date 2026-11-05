"""Short-lived, single-target session tokens for the ``/console/*`` routes.

The installation token drives every target, so it is not handed out per
request. A session names one target, expires on its own, and is minted by the
holder of the installation token (the Space's backend) for each proxied call.

There is no session table: the token is a signed claim,
``base64url(payload) + "." + base64url(HMAC-SHA256(session key, payload))``,
valid while the signature checks out and ``exp`` has not passed. The signing
key is ``HMAC(control_token, "console-session")``, never ``control_token``
itself, so it rotates whenever the installation token does.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

from syft_benchmark.config import Settings

_ALGO = hashlib.sha256

# Long enough for one proxied call and its retries, short enough that a
# leaked token is not a standing door.
DEFAULT_TTL_SECONDS = 3600


class InvalidSession(Exception):
    """The token does not check out: unsigned, malformed, or expired."""


def _signing_key(conf: Settings) -> bytes:
    return hmac.new(conf.control_token.encode(), b"console-session", _ALGO).digest()


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


def mint(
    target_key: str, conf: Settings, *, ttl: int = DEFAULT_TTL_SECONDS
) -> tuple[str, int]:
    """A signed token good for one target, until it expires.

    Args:
        target_key: The one target this session may act on
        conf: The installation's settings — ``control_token`` is what signs it
        ttl: How many seconds from now it is good for

    Returns:
        The token, and the Unix timestamp it expires at
    """
    expires_at = int(time.time()) + ttl
    payload = json.dumps(
        {"key": target_key, "exp": expires_at}, separators=(",", ":")
    ).encode()
    signature = hmac.new(_signing_key(conf), payload, _ALGO).digest()
    return f"{_b64(payload)}.{_b64(signature)}", expires_at


def verify(token: str, conf: Settings) -> str:
    """The target key a session token is good for, if it checks out.

    Raises:
        InvalidSession: malformed, wrongly signed, or expired
    """
    try:
        payload_b64, signature_b64 = token.split(".", 1)
        payload = _unb64(payload_b64)
        signature = _unb64(signature_b64)
    except ValueError as exc:
        raise InvalidSession("malformed session token") from exc

    expected = hmac.new(_signing_key(conf), payload, _ALGO).digest()
    if not hmac.compare_digest(signature, expected):
        raise InvalidSession("the session token's signature does not check out")

    try:
        claim = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise InvalidSession("malformed session token") from exc

    if not isinstance(claim, dict) or int(claim.get("exp", 0)) < int(time.time()):
        raise InvalidSession("the session token has expired")

    key = claim.get("key")
    if not isinstance(key, str) or not key:
        raise InvalidSession("malformed session token")
    return key
