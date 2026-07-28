"""Shared fixtures for station backend tests."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest_asyncio
from sqlmodel import SQLModel

from syft_station.components.auth.session import ROLE_ADMIN, ROLE_MEMBER, SessionUser
from syft_station.components.auth.syfthub import (
    SyftHubAuthError,
    SyftHubBuyerTokenError,
    SyftHubProfile,
    VerifiedBuyer,
)
from syft_station.components.credits.entities import (  # noqa: F401
    Invoice,
    LedgerEntry,
    Payout,
    SpaceCreditToken,
    UserBalance,
    Wallet,
)
from syft_station.components.requests.entities import SpaceRequest  # noqa: F401
from syft_station.components.requests.repository import RequestRepository
from syft_station.components.setup.entities import StationConfig  # noqa: F401
from syft_station.components.setup.repository import SetupRepository
from syft_station.components.shared.database import AsyncDatabase, SQLiteConfig
from syft_station.components.spaces.entities import Space, SpaceToken  # noqa: F401
from syft_station.components.spaces.repository import SpaceRepository

# ============== Database ==============


@pytest_asyncio.fixture
async def tmp_dir():
    """Temporary directory cleaned up after each test."""
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest_asyncio.fixture
async def db(tmp_dir: Path) -> AsyncDatabase:
    """Temp-file database with all station tables created."""
    config = SQLiteConfig(tmp_dir / "station_test.db")
    database = AsyncDatabase(config)

    async with database.engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    yield database
    await database.dispose()


# ============== Repositories ==============


@pytest_asyncio.fixture
async def setup_repository(db: AsyncDatabase) -> SetupRepository:
    return SetupRepository(db)


@pytest_asyncio.fixture
async def request_repository(db: AsyncDatabase) -> RequestRepository:
    return RequestRepository(db)


@pytest_asyncio.fixture
async def space_repository(db: AsyncDatabase) -> SpaceRepository:
    return SpaceRepository(db)


# ============== Users ==============

ADMIN = SessionUser(
    email="admin@openmined.org", username="admin", name="Admin", role=ROLE_ADMIN
)


class StubHubIdentity:
    """SyftHubIdentityClient stand-in: PAT mint, whoami, buyer verification.

    Valid PATs are anything starting ``syft_pat_``; buyer tokens are the
    literal string ``sat:<email>`` — everything else is rejected the way
    the real hub would reject an invalid credential.
    """

    HUB_PASSWORD = "hub-pw"

    def __init__(self, user_id: int = 42):
        self.user_id = user_id
        self.minted: list[str] = []
        self.verified: list[str] = []

    async def mint_pat(self, email: str, password: str) -> str:
        if password != self.HUB_PASSWORD:
            raise SyftHubAuthError("Invalid SyftHub credentials")
        self.minted.append(email)
        return f"syft_pat_stub_{len(self.minted)}"

    async def whoami(self, pat: str) -> SyftHubProfile:
        if not pat.startswith("syft_pat_"):
            raise SyftHubAuthError("SyftHub rejected the token")
        return SyftHubProfile(
            id=self.user_id,
            username=ADMIN.username,
            email=ADMIN.email,
            full_name=ADMIN.name,
        )

    async def verify_buyer_token(self, pat: str, token: str) -> VerifiedBuyer:
        self.verified.append(token)
        if token.startswith("sat:"):
            return VerifiedBuyer(email=token.removeprefix("sat:"), exp=None)
        raise SyftHubBuyerTokenError("Invalid satellite token")


def buyer_auth(email: str) -> dict[str, str]:
    """Authorization header carrying a StubHubIdentity satellite token."""
    return {"Authorization": f"Bearer sat:{email}"}


MEMBER = SessionUser(
    email="user@test.com", username="user", name="Member", role=ROLE_MEMBER
)
OTHER_MEMBER = SessionUser(
    email="other@test.com", username="other", name="Other", role=ROLE_MEMBER
)
