"""Shared fixtures for station backend tests."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest_asyncio
from sqlmodel import SQLModel

from syft_station.components.auth.session import ROLE_ADMIN, ROLE_MEMBER, SessionUser
from syft_station.components.credits.entities import (  # noqa: F401
    Invoice,
    LedgerEntry,
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
MEMBER = SessionUser(
    email="user@test.com", username="user", name="Member", role=ROLE_MEMBER
)
OTHER_MEMBER = SessionUser(
    email="other@test.com", username="other", name="Other", role=ROLE_MEMBER
)
