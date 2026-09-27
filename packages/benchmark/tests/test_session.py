"""Console session tokens: signed, single-target, expiring — and nothing else.

No database here at all: a session token is a self-contained signed claim,
and "valid" is decided entirely by the signature and the clock.
"""

from __future__ import annotations

import time

import pytest

from syft_benchmark.config import Settings
from syft_benchmark.control.session import InvalidSession, mint, verify


def _settings(token: str = "installation-secret") -> Settings:
    return Settings(control_token=token)  # type: ignore[call-arg]


def test_a_freshly_minted_token_verifies_to_its_own_target() -> None:
    conf = _settings()
    token, expires_at = mint("node-a", conf)
    assert verify(token, conf) == "node-a"
    assert expires_at > int(time.time())


def test_two_targets_get_different_tokens() -> None:
    conf = _settings()
    a, _ = mint("node-a", conf)
    b, _ = mint("node-b", conf)
    assert a != b
    assert verify(a, conf) == "node-a"
    assert verify(b, conf) == "node-b"


def test_an_expired_token_is_refused() -> None:
    conf = _settings()
    token, _ = mint("node-a", conf, ttl=-1)
    with pytest.raises(InvalidSession):
        verify(token, conf)


def test_a_token_signed_under_a_different_installation_secret_is_refused() -> None:
    minted_under = _settings("secret-one")
    checked_under = _settings("secret-two")
    token, _ = mint("node-a", minted_under)
    with pytest.raises(InvalidSession):
        verify(token, checked_under)


def test_a_tampered_payload_is_refused_even_with_a_matching_signature_shape() -> None:
    """Swapping the target inside a real token must not just quietly work."""
    conf = _settings()
    token_a, _ = mint("node-a", conf)
    token_b, _ = mint("node-b", conf)
    # Graft b's payload onto a's signature: the signature must not verify.
    forged = f"{token_b.split('.')[0]}.{token_a.split('.')[1]}"
    with pytest.raises(InvalidSession):
        verify(forged, conf)


@pytest.mark.parametrize(
    "garbage",
    ["", "not-a-token-at-all", "onlyonepart", "..", "a.b.c", "not base64.!!!"],
)
def test_garbage_input_is_refused_not_raised_as_something_else(garbage: str) -> None:
    conf = _settings()
    with pytest.raises(InvalidSession):
        verify(garbage, conf)
