"""Storage for benchmark connections and the endpoints they measure."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func
from sqlmodel import col, select

from syft_space.components.benchmarks.entities import (
    BenchmarkConnection,
    BenchmarkTarget,
)
from syft_space.components.shared.database import AsyncBaseRepository, AsyncDatabase


class BenchmarkConnectionRepository(AsyncBaseRepository[BenchmarkConnection]):
    """Connections: where a benchmark lives and how it reaches this Space."""

    def __init__(self, db: AsyncDatabase):
        super().__init__(db, BenchmarkConnection)

    async def list_for_tenant(self, tenant_id: UUID) -> list[BenchmarkConnection]:
        async with self.db.get_session() as session:
            rows = await session.exec(
                select(BenchmarkConnection)
                .where(BenchmarkConnection.tenant_id == tenant_id)
                .order_by(col(BenchmarkConnection.created_at))
            )
            return list(rows.all())

    async def get(
        self, tenant_id: UUID, connection_id: UUID
    ) -> BenchmarkConnection | None:
        async with self.db.get_session() as session:
            row = await session.get(BenchmarkConnection, connection_id)
            return row if row and row.tenant_id == tenant_id else None

    async def default_for(self, tenant_id: UUID) -> BenchmarkConnection | None:
        """The default active connection, or the only active one."""
        rows = await self.list_for_tenant(tenant_id)
        active = [row for row in rows if row.is_active]
        for row in active:
            if row.is_default:
                return row
        return active[0] if len(active) == 1 else None

    async def clear_default(self, tenant_id: UUID, keep: UUID) -> None:
        """Unset the default flag on every connection but ``keep``."""
        async with self.db.get_session() as session:
            rows = await session.exec(
                select(BenchmarkConnection).where(
                    BenchmarkConnection.tenant_id == tenant_id,
                    BenchmarkConnection.is_default,
                )
            )
            for row in rows.all():
                if row.id != keep:
                    row.is_default = False
                    row.updated_at = datetime.now(timezone.utc)
                    session.add(row)
            await session.commit()


class BenchmarkTargetRepository(AsyncBaseRepository[BenchmarkTarget]):
    """Targets: which endpoints this Space has opted into measuring."""

    def __init__(self, db: AsyncDatabase):
        super().__init__(db, BenchmarkTarget)

    async def for_endpoint(self, endpoint_id: UUID) -> BenchmarkTarget | None:
        return await self.get_by_field("endpoint_id", endpoint_id)

    async def list_for_connection(self, connection_id: UUID) -> list[BenchmarkTarget]:
        """The targets one connection measures."""
        async with self.db.get_session() as session:
            rows = await session.exec(
                select(BenchmarkTarget).where(
                    BenchmarkTarget.connection_id == connection_id
                )
            )
            return list(rows.all())

    async def count_by_connection(self, tenant_id: UUID) -> dict[UUID, int]:
        """How many targets each of the tenant's connections measures, in one
        query; connections measuring none are absent."""
        connection = col(BenchmarkTarget.connection_id)
        async with self.db.get_session() as session:
            rows = await session.exec(
                select(connection, func.count())
                .where(BenchmarkTarget.tenant_id == tenant_id, connection.is_not(None))
                .group_by(connection)
            )
            return dict(rows.all())

    async def remember_job(self, target_id: UUID, job: dict | None) -> None:
        """Cache the last job for when the benchmark is unreachable."""
        async with self.db.get_session() as session:
            row = await session.get(BenchmarkTarget, target_id)
            if row is None:
                return
            row.last_job = job
            row.updated_at = datetime.now(timezone.utc)
            session.add(row)
            await session.commit()
