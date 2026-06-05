"""Provisioner state repository for database operations."""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, or_
from sqlmodel import select

from syft_space.components.datasets.entities import (
    Dataset,
    InvalidProvisionerTransitionError,
    ProvisionerBusyError,
    ProvisionerState,
    ProvisionerStatus,
)
from syft_space.components.shared.database import AsyncBaseRepository, AsyncDatabase

# Valid status transitions
# from_status -> [allowed_to_statuses]
ALLOWED_TRANSITIONS: dict[str | None, list[ProvisionerStatus]] = {
    None: [ProvisionerStatus.STARTING],  # Create new
    ProvisionerStatus.STARTING.value: [
        ProvisionerStatus.RUNNING,
        ProvisionerStatus.ERROR,
    ],
    ProvisionerStatus.RUNNING.value: [ProvisionerStatus.STOPPING],
    ProvisionerStatus.STOPPING.value: [
        ProvisionerStatus.STOPPED,
        ProvisionerStatus.ERROR,
    ],
    ProvisionerStatus.STOPPED.value: [ProvisionerStatus.STARTING],
    ProvisionerStatus.ERROR.value: [
        ProvisionerStatus.STARTING,
        ProvisionerStatus.STOPPED,
    ],
}


class ProvisionerStateRepository(AsyncBaseRepository[ProvisionerState]):
    """Repository for ProvisionerState CRUD operations.

    Provisioner states are keyed by ``vector_store_type`` — one running
    provisioner per vector store; every binding that composes that
    vector store shares the row.

    Key methods:
    - ``get_by_vector_store_type`` — primary lookup
    - ``get_running_by_vector_store_type`` — running / starting state
    - ``upsert_status`` — create or update with transition guards
    - ``count_datasets_by_provisioner`` — attached-dataset count
    - ``delete_by_vector_store_type`` — delete state

    During the dual-write transition the row also carries a legacy
    ``dtype`` column that callers pass through ``upsert_status``;
    that column drops in a follow-up migration.
    """

    def __init__(self, db: AsyncDatabase):
        """Initialize the provisioner state repository.

        Args:
            db: Database instance.
        """
        super().__init__(db, ProvisionerState)

    async def get_by_vector_store_type(
        self, vector_store_type: str
    ) -> ProvisionerState | None:
        """Get provisioner state by vector store type.

        Args:
            vector_store_type: Vector store name (e.g. ``"chromadb_local"``).

        Returns:
            ProvisionerState if found, None otherwise.
        """
        async with self.db.get_session() as session:
            statement = select(ProvisionerState).where(
                ProvisionerState.vector_store_type == vector_store_type
            )
            result = await session.exec(statement)
            return result.first()

    async def get_by_id(self, id: UUID) -> ProvisionerState | None:
        """Get provisioner state by ID."""
        async with self.db.get_session() as session:
            return await session.get(ProvisionerState, id)

    async def get_running_by_vector_store_type(
        self, vector_store_type: str
    ) -> ProvisionerState | None:
        """Get running / starting provisioner state by vector store type."""
        async with self.db.get_session() as session:
            statement = select(ProvisionerState).where(
                ProvisionerState.vector_store_type == vector_store_type,
                or_(
                    ProvisionerState.status == ProvisionerStatus.RUNNING.value,
                    ProvisionerState.status == ProvisionerStatus.STARTING.value,
                ),
            )
            result = await session.exec(statement)
            return result.first()

    async def get_all(self) -> list[ProvisionerState]:
        """Get all provisioner states."""
        async with self.db.get_session() as session:
            statement = select(ProvisionerState)
            result = await session.exec(statement)
            return list(result.all())

    async def upsert_status(
        self,
        vector_store_type: str,
        dtype: str,
        status: ProvisionerStatus,
        state: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> ProvisionerState:
        """Create or update provisioner state with status transition guards.

        Keyed by ``vector_store_type``; ``dtype`` is dual-written to the
        legacy column for safe rollback and dropped in a follow-up.

        Valid transitions:
            None     -> STARTING (create new)
            STARTING -> RUNNING, ERROR
            RUNNING  -> STOPPING
            STOPPING -> STOPPED, ERROR
            STOPPED  -> STARTING (restart)
            ERROR    -> STARTING (retry), STOPPED (cleanup)

        Args:
            vector_store_type: Vector store name (lookup key).
            dtype: Binding name (legacy column write-through).
            status: Target status.
            state: Optional state dict (typically set when transitioning to RUNNING).
            error: Optional error message (typically set when transitioning to ERROR).

        Returns:
            Created or updated ProvisionerState.

        Raises:
            ProvisionerBusyError: If provisioner is busy (STARTING/STOPPING).
            InvalidProvisionerTransitionError: If transition is not allowed.
        """
        async with self.db.get_session() as session:
            result = await session.exec(
                select(ProvisionerState).where(
                    ProvisionerState.vector_store_type == vector_store_type
                )
            )
            existing = result.first()

            current_status = existing.status if existing else None

            allowed = ALLOWED_TRANSITIONS.get(current_status, [])
            if status not in allowed:
                if current_status in (
                    ProvisionerStatus.STARTING.value,
                    ProvisionerStatus.STOPPING.value,
                ):
                    raise ProvisionerBusyError(vector_store_type, current_status)
                raise InvalidProvisionerTransitionError(
                    vector_store_type, current_status, status.value
                )

            now = datetime.now(timezone.utc)

            if existing:
                existing.status = status.value
                existing.updated_at = now
                existing.error = error if status == ProvisionerStatus.ERROR else None
                # Dual-write the legacy column in case the row was written
                # before backfill (defensive — backfill should have populated it).
                existing.dtype = dtype

                if state is not None:
                    existing.state = state

                if status == ProvisionerStatus.STARTING:
                    existing.started_at = now
                    existing.stopped_at = None
                elif status in (ProvisionerStatus.STOPPED, ProvisionerStatus.ERROR):
                    existing.stopped_at = now

                session.add(existing)
                await session.commit()
                await session.refresh(existing)
                return existing
            else:
                provisioner_state = ProvisionerState(
                    id=uuid4(),
                    vector_store_type=vector_store_type,
                    dtype=dtype,
                    state=state or {},
                    status=status.value,
                    error=error,
                    started_at=now if status == ProvisionerStatus.STARTING else None,
                    stopped_at=None,
                    created_at=now,
                    updated_at=now,
                )

                session.add(provisioner_state)
                await session.commit()
                await session.refresh(provisioner_state)
                return provisioner_state

    async def force_status_update(
        self,
        vector_store_type: str,
        status: ProvisionerStatus,
        error: str | None = None,
    ) -> ProvisionerState | None:
        """Force update status bypassing transition guards.

        WARNING: Only use for recovery scenarios during startup.
        Bypasses all state transition validation.
        """
        async with self.db.get_session() as session:
            result = await session.exec(
                select(ProvisionerState).where(
                    ProvisionerState.vector_store_type == vector_store_type
                )
            )
            existing = result.first()
            if not existing:
                return None

            now = datetime.now(timezone.utc)
            existing.status = status.value
            existing.error = error
            existing.updated_at = now
            existing.stopped_at = now

            session.add(existing)
            await session.commit()
            await session.refresh(existing)
            return existing

    async def count_datasets_by_provisioner(self, state_id: UUID) -> int:
        """Count datasets using a specific provisioner state."""
        async with self.db.get_session() as session:
            statement = (
                select(func.count())
                .select_from(Dataset)
                .where(Dataset.provisioner_state_id == state_id)
            )
            result = await session.exec(statement)
            return result.first() or 0

    async def delete_by_vector_store_type(self, vector_store_type: str) -> bool:
        """Delete provisioner state by vector store type.

        Warning: This does not check for attached datasets. Use
        ``count_datasets_by_provisioner()`` first to verify it's safe to delete.

        Returns:
            True if deleted, False if not found.
        """
        async with self.db.get_session() as session:
            result = await session.exec(
                select(ProvisionerState).where(
                    ProvisionerState.vector_store_type == vector_store_type
                )
            )
            provisioner_state = result.first()

            if provisioner_state:
                await session.delete(provisioner_state)
                await session.commit()
                return True
            return False
