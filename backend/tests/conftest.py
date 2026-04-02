"""Shared fixtures for backend tests."""

from __future__ import annotations

import asyncio
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlmodel import SQLModel

from syft_space.components.analytics.entities import QueryEvent, QueryEventStatus
from syft_space.components.analytics.repository import QueryEventRepository

# Import ALL entity modules so SQLAlchemy mappers resolve relationships
# (Endpoint has FK relationships to Dataset, Model, Tenant, Policy)
from syft_space.components.datasets.entities import Dataset  # noqa: F401
from syft_space.components.endpoints.entities import Endpoint
from syft_space.components.endpoints.repository import EndpointRepository
from syft_space.components.marketplaces.entities import Marketplace  # noqa: F401
from syft_space.components.models.entities import Model  # noqa: F401
from syft_space.components.policies.entities import Policy  # noqa: F401
from syft_space.components.shared.database import AsyncDatabase, SQLiteConfig
from syft_space.components.tenants.entities import Tenant

# ============== Event loop ==============


@pytest.fixture(scope="session")
def event_loop():
    """Create a single event loop for the entire test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ============== Databases ==============


@pytest.fixture
async def tmp_dir():
    """Temporary directory cleaned up after each test."""
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
async def analytics_db(tmp_dir: Path) -> AsyncDatabase:
    """In-memory-like analytics database (temp file) with tables created."""
    db_path = tmp_dir / "analytics_test.db"
    config = SQLiteConfig(db_path, enable_foreign_keys=False)
    db = AsyncDatabase(config)

    async with db.engine.begin() as conn:
        await conn.run_sync(lambda c: QueryEvent.__table__.create(c, checkfirst=True))

    yield db
    await db.dispose()


@pytest.fixture
async def main_db(tmp_dir: Path) -> AsyncDatabase:
    """Main database with tenant + endpoint tables for cross-DB handler tests."""
    db_path = tmp_dir / "main_test.db"
    config = SQLiteConfig(db_path, enable_foreign_keys=False)
    db = AsyncDatabase(config)

    async with db.engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    yield db
    await db.dispose()


# ============== Repositories ==============


@pytest.fixture
async def event_repository(analytics_db: AsyncDatabase) -> QueryEventRepository:
    return QueryEventRepository(analytics_db)


@pytest.fixture
async def endpoint_repository(main_db: AsyncDatabase) -> EndpointRepository:
    return EndpointRepository(main_db)


# ============== Tenant ==============

TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")


@pytest.fixture
async def tenant(main_db: AsyncDatabase) -> Tenant:
    """Create and persist a test tenant."""
    t = Tenant(
        id=TENANT_ID,
        name="test-tenant",
        display_name="Test Tenant",
        domain="test.example.com",
    )
    async with main_db.get_session() as session:
        session.add(t)
        await session.commit()
        await session.refresh(t)
    return t


# ============== Helpers ==============


def make_event(
    *,
    tenant_id: UUID = TENANT_ID,
    endpoint_id: UUID | None = None,
    endpoint_slug: str = "test-endpoint",
    dataset_id: UUID | None = None,
    user_email: str = "user@example.com",
    revenue_amount: float = 0.0,
    currency: str = "USD",
    status: str = QueryEventStatus.SUCCESS.value,
    timestamp: datetime | None = None,
) -> QueryEvent:
    """Factory for QueryEvent with sensible defaults."""
    return QueryEvent(
        id=uuid4(),
        tenant_id=tenant_id,
        endpoint_id=endpoint_id,
        endpoint_slug=endpoint_slug,
        dataset_id=dataset_id,
        user_email=user_email,
        revenue_amount=revenue_amount,
        currency=currency,
        status=status,
        timestamp=timestamp or datetime.now(timezone.utc),
    )


def make_endpoint(
    *,
    tenant_id: UUID = TENANT_ID,
    name: str = "Test Endpoint",
    slug: str = "test-endpoint",
    published: bool = False,
    dataset_id: UUID | None = None,
    created_at: datetime | None = None,
) -> Endpoint:
    """Factory for Endpoint with sensible defaults."""
    return Endpoint(
        id=uuid4(),
        tenant_id=tenant_id,
        name=name,
        slug=slug,
        published=published,
        dataset_id=dataset_id or uuid4(),
        response_type="raw",
        created_at=created_at or datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
