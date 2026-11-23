"""Satellite token verification — local first, the marketplace as fallback.

A satellite token is an RS256 JWT the marketplace mints for one user and one
satellite. Its signature, expiry and audience are checked here against the
marketplace's published keys, so a query costs no marketplace call. The token
carries a user id (``sub``) but no email, so the email comes from a short-lived
in-memory map filled by the marketplace's ``/verify`` on first sight of a user.

The marketplace is asked only when this space cannot decide for itself: it has
no satellite id yet, the keys cannot be fetched, or the email is not cached.
A token that fails a local check is rejected without a marketplace call.
"""

from __future__ import annotations

import asyncio
import time
from collections import OrderedDict
from collections.abc import AsyncIterator, Awaitable, Callable, Hashable
from contextlib import asynccontextmanager
from typing import Any

import httpx
import jwt
from fastapi import HTTPException
from loguru import logger

from syft_space.components.marketplaces.entities import Marketplace
from syft_space.components.shared.syfthub import SyftHubClient, SyftHubError

ALGORITHM = "RS256"
REQUIRED_CLAIMS = ["exp", "iat", "sub", "aud"]
CLOCK_LEEWAY_SECONDS = 10

# How long a user's email is reused before the marketplace is asked again.
SUBJECT_EMAIL_TTL_SECONDS = 15 * 60
SUBJECT_EMAIL_MAX_ENTRIES = 10_000

# Keys are refreshed hourly, and distrusted after a day without a refresh.
KEY_SET_MAX_AGE_SECONDS = 60 * 60
KEY_SET_HARD_LIMIT_SECONDS = 24 * 60 * 60
# Floor between fetches, so tokens with made-up key ids cannot flood the hub.
KEY_SET_REFETCH_INTERVAL_SECONDS = 60
KEY_SET_FETCH_TIMEOUT_SECONDS = 10.0

# Guest tokens name no user; the marketplace answers /verify with these.
GUEST_SUB = "guest"
GUEST_EMAIL = "guest@syfthub.org"

Clock = Callable[[], float]
FetchKeySet = Callable[[str], Awaitable[dict[str, Any]]]
VerifyWithHub = Callable[[str, Marketplace], Awaitable[str]]


class HubKeysUnavailableError(Exception):
    """No trustworthy key set is held, so a token cannot be judged locally."""


async def fetch_key_set(base_url: str) -> dict[str, Any]:
    """GET the marketplace's JWKS document."""
    async with httpx.AsyncClient(timeout=KEY_SET_FETCH_TIMEOUT_SECONDS) as client:
        response = await client.get(f"{base_url}/.well-known/jwks.json")
        response.raise_for_status()
        document: dict[str, Any] = response.json()
        return document


class HubKeySet:
    """One marketplace's public signing keys, by key id."""

    def __init__(
        self,
        base_url: str,
        fetch: FetchKeySet = fetch_key_set,
        clock: Clock = time.monotonic,
    ):
        self.base_url = base_url
        self._fetch = fetch
        self._clock = clock
        self._keys: dict[str, Any] = {}
        self._fetched_at: float | None = None
        self._attempted_at: float | None = None
        self._lock = asyncio.Lock()

    async def key_for(self, kid: str) -> Any | None:
        """The public key for ``kid``, or None if the marketplace has no such key.

        Raises:
            HubKeysUnavailableError: no key set was ever fetched, or the one
                held is past its hard limit.
        """
        if self._should_fetch(kid):
            async with self._lock:
                # Re-checked: a concurrent caller may have fetched meanwhile.
                if self._should_fetch(kid):
                    await self._refresh()

        if self._fetched_at is None:
            raise HubKeysUnavailableError(self.base_url)
        if self._clock() - self._fetched_at > KEY_SET_HARD_LIMIT_SECONDS:
            raise HubKeysUnavailableError(self.base_url)
        return self._keys.get(kid)

    def _should_fetch(self, kid: str) -> bool:
        now = self._clock()
        if (
            self._attempted_at is not None
            and now - self._attempted_at < KEY_SET_REFETCH_INTERVAL_SECONDS
        ):
            return False
        if self._fetched_at is None:
            return True
        if now - self._fetched_at > KEY_SET_MAX_AGE_SECONDS:
            return True
        return kid not in self._keys

    async def _refresh(self) -> None:
        """Replace the keys from the marketplace; a failure keeps the old ones."""
        self._attempted_at = self._clock()
        try:
            document = await self._fetch(self.base_url)
            keys = _parse_key_set(document)
        except (httpx.HTTPError, ValueError, TypeError, jwt.PyJWTError) as e:
            logger.warning(f"Could not refresh signing keys from {self.base_url}: {e}")
            return
        self._keys = keys
        self._fetched_at = self._clock()


def _parse_key_set(document: dict[str, Any]) -> dict[str, Any]:
    """RSA public keys from a JWKS document, by key id."""
    keys: dict[str, Any] = {}
    for entry in document["keys"]:
        kid = entry.get("kid")
        if entry.get("kty") != "RSA" or not kid:
            continue
        keys[kid] = jwt.PyJWK(entry, algorithm=ALGORITHM).key
    if not keys:
        raise ValueError("key set holds no RSA keys")
    return keys


class SubjectEmailCache:
    """``(marketplace url, sub) -> email``, in memory, with a fixed lifetime.

    An entry expires a fixed time after it was written, however often it is
    read, so an email changed on the marketplace is picked up within the TTL.
    """

    def __init__(
        self,
        ttl_seconds: float = SUBJECT_EMAIL_TTL_SECONDS,
        max_entries: int = SUBJECT_EMAIL_MAX_ENTRIES,
        clock: Clock = time.monotonic,
    ):
        self._ttl_seconds = ttl_seconds
        self._max_entries = max_entries
        self._clock = clock
        self._entries: OrderedDict[tuple[str, str], tuple[str, float]] = OrderedDict()

    def get(self, base_url: str, sub: str) -> str | None:
        """The cached email, or None if absent or expired."""
        key = (base_url, sub)
        entry = self._entries.get(key)
        if entry is None:
            return None
        email, expires_at = entry
        if self._clock() >= expires_at:
            del self._entries[key]
            return None
        self._entries.move_to_end(key)
        return email

    def put(self, base_url: str, sub: str, email: str) -> None:
        """Store an email; when full, drop expired entries, then the least recent."""
        key = (base_url, sub)
        self._entries[key] = (email, self._clock() + self._ttl_seconds)
        self._entries.move_to_end(key)
        if len(self._entries) > self._max_entries:
            self._drop_expired()
        while len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)

    def _drop_expired(self) -> None:
        now = self._clock()
        expired = [
            k for k, (_, expires_at) in self._entries.items() if now >= expires_at
        ]
        for k in expired:
            del self._entries[k]

    def clear(self) -> None:
        """Drop every entry."""
        self._entries.clear()


class KeyedLocks:
    """One asyncio lock per key, kept only while someone holds or awaits it."""

    def __init__(self) -> None:
        self._locks: dict[Hashable, tuple[asyncio.Lock, int]] = {}

    @asynccontextmanager
    async def hold(self, key: Hashable) -> AsyncIterator[None]:
        """Hold the lock for ``key``; the entry is dropped with its last user."""
        lock, users = self._locks.get(key, (asyncio.Lock(), 0))
        self._locks[key] = (lock, users + 1)
        try:
            async with lock:
                yield
        finally:
            lock, users = self._locks[key]
            if users == 1:
                del self._locks[key]
            else:
                self._locks[key] = (lock, users - 1)

    def __len__(self) -> int:
        return len(self._locks)


async def verify_with_hub(token: str, marketplace: Marketplace) -> str:
    """Ask the marketplace to verify the token; return the user's email."""
    # The satellite id narrows the accepted audience to this space, so a
    # token minted for another service the same owner runs is rejected.
    try:
        async with SyftHubClient(str(marketplace.url)) as client:
            await client.login(marketplace.email, marketplace.password)
            result = await client.verify_satellite_token(
                token, marketplace.satellite_id
            )
    except SyftHubError as e:
        raise e.to_http_exception() from e
    except httpx.HTTPError as e:
        raise HTTPException(status_code=503, detail="Marketplace unreachable") from e

    # TODO: guest tokens (sub == "guest") are accepted here but rejected by
    # the station. Worth aligning the two receivers.
    if not result.valid:
        raise HTTPException(status_code=401, detail="Invalid satellite token")
    if result.is_expired:
        raise HTTPException(status_code=401, detail="Satellite token expired")
    if not result.email:
        raise HTTPException(status_code=401, detail="Token missing email claim")

    return str(result.email)


class SatelliteTokenVerifier:
    """Turns a satellite token into the verified email of the user it names."""

    def __init__(
        self,
        emails: SubjectEmailCache | None = None,
        fetch: FetchKeySet = fetch_key_set,
        remote: VerifyWithHub = verify_with_hub,
        clock: Clock = time.monotonic,
    ):
        self._emails = emails if emails is not None else SubjectEmailCache(clock=clock)
        self._fetch = fetch
        self._remote = remote
        self._clock = clock
        self._key_sets: dict[str, HubKeySet] = {}
        self._lookups = KeyedLocks()

    async def email_for(self, token: str, marketplace: Marketplace) -> str:
        """Verify ``token`` for this space and return the user's email.

        Raises:
            HTTPException: 401 if the token is invalid, expired or minted for
                another satellite; the marketplace's own status if it had to
                be asked and refused; 503 if it could not be reached.
        """
        # Without a satellite id there is no audience to check against.
        if not marketplace.satellite_id:
            return await self._remote(token, marketplace)

        base_url = str(marketplace.url).rstrip("/")
        kid = _key_id(token)
        try:
            key = await self._key_set(base_url).key_for(kid)
        except HubKeysUnavailableError:
            return await self._remote(token, marketplace)
        if key is None:
            logger.debug(f"Satellite token rejected: unknown key id {kid!r}")
            raise HTTPException(status_code=401, detail="Invalid satellite token")

        sub = _verified_subject(token, key, marketplace.satellite_id)
        if sub == GUEST_SUB:
            return GUEST_EMAIL

        email = self._emails.get(base_url, sub)
        if email is not None:
            return email
        # One lookup per user at a time; those who waited read the cache.
        async with self._lookups.hold((base_url, sub)):
            email = self._emails.get(base_url, sub)
            if email is None:
                email = await self._remote(token, marketplace)
                self._emails.put(base_url, sub, email)
            return email

    def _key_set(self, base_url: str) -> HubKeySet:
        key_set = self._key_sets.get(base_url)
        if key_set is None:
            key_set = HubKeySet(base_url, fetch=self._fetch, clock=self._clock)
            self._key_sets[base_url] = key_set
        return key_set


def _key_id(token: str) -> str:
    """The token's key id, read before verification only to pick the key."""
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as e:
        raise HTTPException(status_code=401, detail="Invalid satellite token") from e
    kid = header.get("kid")
    if header.get("alg") != ALGORITHM or not isinstance(kid, str) or not kid:
        raise HTTPException(status_code=401, detail="Invalid satellite token")
    return kid


def _verified_subject(token: str, key: Any, satellite_id: str) -> str:
    """Check signature, expiry and audience; return the token's ``sub``."""
    try:
        claims = jwt.decode(
            token,
            key,
            algorithms=[ALGORITHM],
            audience=satellite_id,
            leeway=CLOCK_LEEWAY_SECONDS,
            options={"require": REQUIRED_CLAIMS},
        )
    except jwt.ExpiredSignatureError as e:
        raise HTTPException(status_code=401, detail="Satellite token expired") from e
    except jwt.PyJWTError as e:
        logger.debug(f"Satellite token rejected: {type(e).__name__}")
        raise HTTPException(status_code=401, detail="Invalid satellite token") from e

    sub = claims["sub"]
    if not isinstance(sub, str) or not sub:
        raise HTTPException(status_code=401, detail="Invalid satellite token")
    return sub


# Default verifier shared by every request in the process.
default_verifier = SatelliteTokenVerifier()
