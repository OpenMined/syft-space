"""Tests for local satellite token verification.

Tokens are signed with a throwaway RSA key and the marketplace is replaced by
two counting stubs (the JWKS fetch and the remote ``/verify``), so each test
can assert both the outcome and whether the marketplace was called.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any
from uuid import uuid4

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException

from syft_space.components.auth.satellite_tokens import (
    GUEST_EMAIL,
    KEY_SET_HARD_LIMIT_SECONDS,
    KEY_SET_MAX_AGE_SECONDS,
    KEY_SET_REFETCH_INTERVAL_SECONDS,
    SUBJECT_EMAIL_TTL_SECONDS,
    SatelliteTokenVerifier,
    SubjectEmailCache,
)
from syft_space.components.marketplaces.entities import Marketplace

HUB_URL = "https://hub.test"
SATELLITE_ID = "5f0c2d0e-1111-4222-8333-444455556666"
EMAIL = "alice@test.org"


def _new_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _jwk(key: rsa.RSAPrivateKey, kid: str) -> dict[str, Any]:
    jwk: dict[str, Any] = jwt.algorithms.RSAAlgorithm.to_jwk(
        key.public_key(), as_dict=True
    )
    return {**jwk, "kid": kid, "use": "sig", "alg": "RS256"}


@pytest.fixture(scope="module")
def hub_key() -> rsa.RSAPrivateKey:
    return _new_key()


class Clock:
    """A monotonic clock the test moves by hand."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


class Hub:
    """Stands in for the marketplace: serves keys and answers /verify."""

    def __init__(self, keys: dict[str, rsa.RSAPrivateKey]):
        self.keys = keys
        self.reachable = True
        self.key_fetches = 0
        self.verify_calls: list[str] = []
        self.verify_error: HTTPException | None = None
        self.email = EMAIL

    async def fetch(self, base_url: str) -> dict[str, Any]:
        self.key_fetches += 1
        if not self.reachable:
            raise httpx.ConnectError("hub down")
        return {"keys": [_jwk(key, kid) for kid, key in self.keys.items()]}

    async def verify(self, token: str, marketplace: Marketplace) -> str:
        self.verify_calls.append(token)
        # Yield like a real network call, so concurrent requests interleave.
        await asyncio.sleep(0)
        if self.verify_error is not None:
            raise self.verify_error
        return self.email


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def hub(hub_key) -> Hub:
    return Hub({"hub-key-1": hub_key})


@pytest.fixture
def verifier(hub, clock) -> SatelliteTokenVerifier:
    return SatelliteTokenVerifier(fetch=hub.fetch, remote=hub.verify, clock=clock)


@pytest.fixture
def marketplace() -> Marketplace:
    return Marketplace(
        tenant_id=uuid4(),
        name="SyftHub",
        username="owner",
        url=HUB_URL,
        email="owner@test.org",
        password="pw",
        satellite_id=SATELLITE_ID,
    )


def _token(
    key: rsa.RSAPrivateKey,
    *,
    kid: str | None = "hub-key-1",
    sub: str = "123",
    aud: str = SATELLITE_ID,
    expires_in: float = 60,
    drop: tuple[str, ...] = (),
) -> str:
    now = int(time.time())
    claims: dict[str, Any] = {
        "sub": sub,
        "iss": "https://hub.syft.com",
        "aud": aud,
        "iat": now,
        "exp": now + int(expires_in),
        "role": "user",
    }
    for name in drop:
        del claims[name]
    headers = {"kid": kid} if kid else {}
    return jwt.encode(claims, key, algorithm="RS256", headers=headers)


async def _rejected(verifier, token, marketplace) -> HTTPException:
    with pytest.raises(HTTPException) as caught:
        await verifier.email_for(token, marketplace)
    return caught.value


# ── The normal path ──────────────────────────────────────────────


async def test_first_query_asks_hub_for_email_once(verifier, hub, hub_key, marketplace):
    token = _token(hub_key)

    assert await verifier.email_for(token, marketplace) == EMAIL
    assert hub.verify_calls == [token]
    assert hub.key_fetches == 1


async def test_fresh_token_from_same_user_makes_no_hub_call(
    verifier, hub, hub_key, marketplace
):
    await verifier.email_for(_token(hub_key), marketplace)
    # A different token (different expiry) for the same user.
    second = _token(hub_key, expires_in=45)

    assert await verifier.email_for(second, marketplace) == EMAIL
    assert len(hub.verify_calls) == 1
    assert hub.key_fetches == 1


async def test_each_user_gets_their_own_lookup(verifier, hub, hub_key, marketplace):
    await verifier.email_for(_token(hub_key, sub="123"), marketplace)
    hub.email = "bob@test.org"

    assert (
        await verifier.email_for(_token(hub_key, sub="456"), marketplace)
        == "bob@test.org"
    )
    assert len(hub.verify_calls) == 2


async def test_guest_token_never_reaches_hub(verifier, hub, hub_key, marketplace):
    token = _token(hub_key, sub="guest")

    assert await verifier.email_for(token, marketplace) == GUEST_EMAIL
    assert hub.verify_calls == []


# ── Email cache lifetime ─────────────────────────────────────────


async def test_email_is_looked_up_again_after_ttl(
    verifier, hub, hub_key, marketplace, clock
):
    await verifier.email_for(_token(hub_key), marketplace)
    hub.email = "alice-new@test.org"

    clock.now += SUBJECT_EMAIL_TTL_SECONDS - 1
    assert await verifier.email_for(_token(hub_key), marketplace) == EMAIL

    clock.now += 1
    assert (
        await verifier.email_for(_token(hub_key), marketplace) == "alice-new@test.org"
    )
    assert len(hub.verify_calls) == 2


async def test_reads_do_not_extend_the_ttl(verifier, hub, hub_key, marketplace, clock):
    await verifier.email_for(_token(hub_key), marketplace)

    # Read every five minutes; the entry still expires at fifteen.
    for _ in range(3):
        clock.now += SUBJECT_EMAIL_TTL_SECONDS / 3
        await verifier.email_for(_token(hub_key), marketplace)

    assert len(hub.verify_calls) == 2


async def test_failed_lookup_is_not_cached(verifier, hub, hub_key, marketplace):
    hub.verify_error = HTTPException(status_code=401, detail="Invalid satellite token")
    error = await _rejected(verifier, _token(hub_key), marketplace)
    assert error.status_code == 401

    hub.verify_error = None
    assert await verifier.email_for(_token(hub_key), marketplace) == EMAIL
    assert len(hub.verify_calls) == 2


async def test_concurrent_first_requests_from_one_user_share_one_lookup(
    verifier, hub, hub_key, marketplace
):
    tokens = [_token(hub_key, expires_in=60 - n) for n in range(10)]

    emails = await asyncio.gather(*(verifier.email_for(t, marketplace) for t in tokens))

    assert emails == [EMAIL] * 10
    assert len(hub.verify_calls) == 1
    assert len(verifier._lookups) == 0


async def test_waiting_request_does_its_own_lookup_when_the_first_fails(
    verifier, hub, hub_key, marketplace
):
    first, second = _token(hub_key, expires_in=60), _token(hub_key, expires_in=50)
    outcomes = iter([HTTPException(status_code=401, detail="Invalid"), None])

    async def verify(token, marketplace):
        hub.verify_calls.append(token)
        await asyncio.sleep(0)
        error = next(outcomes)
        if error is not None:
            raise error
        return EMAIL

    verifier._remote = verify
    results = await asyncio.gather(
        verifier.email_for(first, marketplace),
        verifier.email_for(second, marketplace),
        return_exceptions=True,
    )

    assert isinstance(results[0], HTTPException)
    assert results[1] == EMAIL
    assert hub.verify_calls == [first, second]
    assert len(verifier._lookups) == 0


def test_email_cache_evicts_least_recently_used():
    cache = SubjectEmailCache(max_entries=2)
    cache.put(HUB_URL, "1", "one@test.org")
    cache.put(HUB_URL, "2", "two@test.org")
    cache.get(HUB_URL, "1")
    cache.put(HUB_URL, "3", "three@test.org")

    assert cache.get(HUB_URL, "1") == "one@test.org"
    assert cache.get(HUB_URL, "2") is None
    assert cache.get(HUB_URL, "3") == "three@test.org"


def test_email_cache_drops_expired_entries_before_live_ones(clock):
    cache = SubjectEmailCache(ttl_seconds=100, max_entries=2, clock=clock)
    cache.put(HUB_URL, "old", "old@test.org")
    clock.now += 50
    cache.put(HUB_URL, "live", "live@test.org")
    clock.now += 40
    # "old" is read last, so "live" is the least recently used.
    cache.get(HUB_URL, "old")
    clock.now += 20
    # "old" has now expired; "live" has 30 seconds left.
    cache.put(HUB_URL, "new", "new@test.org")

    assert cache.get(HUB_URL, "live") == "live@test.org"
    assert cache.get(HUB_URL, "new") == "new@test.org"
    assert cache.get(HUB_URL, "old") is None


def test_email_cache_is_keyed_by_hub():
    cache = SubjectEmailCache()
    cache.put(HUB_URL, "123", EMAIL)

    assert cache.get("https://other-hub.test", "123") is None


# ── Tokens rejected locally, with no hub call ────────────────────


async def test_token_for_another_satellite_is_rejected(
    verifier, hub, hub_key, marketplace
):
    token = _token(hub_key, aud="another-satellite")

    error = await _rejected(verifier, token, marketplace)

    assert error.status_code == 401
    assert hub.verify_calls == []


async def test_expired_token_is_rejected(verifier, hub, hub_key, marketplace):
    token = _token(hub_key, expires_in=-120)

    error = await _rejected(verifier, token, marketplace)

    assert error.status_code == 401
    assert error.detail == "Satellite token expired"
    assert hub.verify_calls == []


async def test_cached_email_does_not_admit_an_expired_token(
    verifier, hub, hub_key, marketplace
):
    await verifier.email_for(_token(hub_key), marketplace)

    error = await _rejected(verifier, _token(hub_key, expires_in=-120), marketplace)

    assert error.status_code == 401


@pytest.mark.parametrize("claim", ["exp", "iat", "sub", "aud"])
async def test_token_missing_a_required_claim_is_rejected(
    verifier, hub, hub_key, marketplace, claim
):
    token = _token(hub_key, drop=(claim,))

    error = await _rejected(verifier, token, marketplace)

    assert error.status_code == 401
    assert hub.verify_calls == []


async def test_token_signed_by_another_key_is_rejected(verifier, hub, marketplace):
    # Right key id, wrong private key: a forged token.
    token = _token(_new_key())

    error = await _rejected(verifier, token, marketplace)

    assert error.status_code == 401
    assert hub.verify_calls == []


async def test_tampered_subject_is_rejected(verifier, hub, hub_key, marketplace):
    header, _, signature = _token(hub_key, sub="123").split(".")
    _, other_payload, _ = _token(hub_key, sub="456").split(".")

    error = await _rejected(
        verifier, f"{header}.{other_payload}.{signature}", marketplace
    )

    assert error.status_code == 401
    assert hub.verify_calls == []


async def test_unsigned_token_is_rejected(verifier, hub, marketplace):
    now = int(time.time())
    token = jwt.encode(
        {"sub": "123", "aud": SATELLITE_ID, "iat": now, "exp": now + 60},
        key="",
        algorithm="none",
        headers={"kid": "hub-key-1"},
    )

    error = await _rejected(verifier, token, marketplace)

    assert error.status_code == 401
    assert hub.key_fetches == 0
    assert hub.verify_calls == []


async def test_hmac_token_signed_with_the_public_key_is_rejected(
    verifier, hub, hub_key, marketplace
):
    # Algorithm confusion: the public key is not a secret, so it must never
    # be accepted as an HMAC key. Built by hand; PyJWT refuses to sign this.
    import base64
    import hashlib
    import hmac
    import json

    def b64(raw: bytes) -> str:
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    public_pem = hub_key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    now = int(time.time())
    header = b64(
        json.dumps({"alg": "HS256", "typ": "JWT", "kid": "hub-key-1"}).encode()
    )
    payload = b64(
        json.dumps(
            {"sub": "123", "aud": SATELLITE_ID, "iat": now, "exp": now + 60}
        ).encode()
    )
    signature = b64(
        hmac.new(public_pem, f"{header}.{payload}".encode(), hashlib.sha256).digest()
    )

    error = await _rejected(verifier, f"{header}.{payload}.{signature}", marketplace)

    assert error.status_code == 401
    assert hub.verify_calls == []


@pytest.mark.parametrize("token", ["", "not-a-jwt", "a.b.c"])
async def test_malformed_token_is_rejected(verifier, hub, marketplace, token):
    error = await _rejected(verifier, token, marketplace)

    assert error.status_code == 401
    assert hub.key_fetches == 0
    assert hub.verify_calls == []


async def test_token_without_key_id_is_rejected(verifier, hub, hub_key, marketplace):
    error = await _rejected(verifier, _token(hub_key, kid=None), marketplace)

    assert error.status_code == 401
    assert hub.verify_calls == []


# ── Key set: rotation, throttling, ageing ────────────────────────


async def test_unknown_key_id_refetches_once_then_is_throttled(
    verifier, hub, hub_key, marketplace, clock
):
    await verifier.email_for(_token(hub_key), marketplace)
    clock.now += KEY_SET_REFETCH_INTERVAL_SECONDS
    junk = _token(_new_key(), kid="made-up")

    for _ in range(5):
        error = await _rejected(verifier, junk, marketplace)
        assert error.status_code == 401

    assert hub.key_fetches == 2
    assert len(hub.verify_calls) == 1


async def test_rotated_key_is_picked_up(verifier, hub, hub_key, marketplace, clock):
    await verifier.email_for(_token(hub_key), marketplace)
    new_key = _new_key()
    hub.keys = {"hub-key-2": new_key}
    clock.now += KEY_SET_REFETCH_INTERVAL_SECONDS

    assert (
        await verifier.email_for(_token(new_key, kid="hub-key-2"), marketplace) == EMAIL
    )
    assert hub.key_fetches == 2

    # The retired key is gone with the refetch.
    error = await _rejected(verifier, _token(hub_key), marketplace)
    assert error.status_code == 401


async def test_keys_are_refreshed_after_max_age(
    verifier, hub, hub_key, marketplace, clock
):
    await verifier.email_for(_token(hub_key), marketplace)

    clock.now += KEY_SET_MAX_AGE_SECONDS + 1
    await verifier.email_for(_token(hub_key), marketplace)

    assert hub.key_fetches == 2


async def test_old_keys_keep_working_while_hub_is_down(
    verifier, hub, hub_key, marketplace, clock
):
    await verifier.email_for(_token(hub_key), marketplace)
    hub.reachable = False

    # Still inside the email TTL, so nothing needs the hub.
    clock.now += SUBJECT_EMAIL_TTL_SECONDS - 1
    assert await verifier.email_for(_token(hub_key), marketplace) == EMAIL
    assert len(hub.verify_calls) == 1


async def test_keys_past_the_hard_limit_are_not_trusted(
    verifier, hub, hub_key, marketplace, clock
):
    await verifier.email_for(_token(hub_key), marketplace)
    hub.reachable = False
    clock.now += KEY_SET_HARD_LIMIT_SECONDS + 1

    # Cannot decide locally any more: the hub is asked.
    await verifier.email_for(_token(hub_key), marketplace)

    assert len(hub.verify_calls) == 2


async def test_concurrent_first_requests_share_one_key_fetch(
    verifier, hub, hub_key, marketplace
):
    tokens = [_token(hub_key, sub=str(n)) for n in range(20)]

    await asyncio.gather(*(verifier.email_for(t, marketplace) for t in tokens))

    assert hub.key_fetches == 1


# ── Falling back to the hub ──────────────────────────────────────


async def test_space_without_satellite_id_asks_hub(verifier, hub, hub_key, marketplace):
    marketplace.satellite_id = None
    token = _token(hub_key)

    assert await verifier.email_for(token, marketplace) == EMAIL
    assert hub.verify_calls == [token]
    assert hub.key_fetches == 0


async def test_unfetchable_keys_fall_back_to_hub(verifier, hub, hub_key, marketplace):
    hub.reachable = False
    token = _token(hub_key)

    assert await verifier.email_for(token, marketplace) == EMAIL
    assert hub.verify_calls == [token]


async def test_key_set_without_rsa_keys_falls_back_to_hub(
    verifier, hub, hub_key, marketplace
):
    hub.keys = {}
    token = _token(hub_key)

    assert await verifier.email_for(token, marketplace) == EMAIL
    assert hub.verify_calls == [token]
