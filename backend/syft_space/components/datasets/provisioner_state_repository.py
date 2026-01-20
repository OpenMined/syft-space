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

    Provisioner states are dtype-based (one per dataset type). Multiple datasets
    can share the same provisioner state.

    Key methods:
    - get_by_dtype(): Primary lookup (one provisioner per dtype)
    - get_running_by_dtype(): Find running/starting provisioner
    - get_all(): Get all provisioner states
    - upsert_status(): Create or update with status transition guards
    - count_datasets_by_provisioner(): Count attached datasets
    - delete_by_dtype(): Delete provisioner state
    """

    def __init__(self, db: AsyncDatabase):
        """Initialize the provisioner state repository.

        Args:
            db: Database instance
        """
        super().__init__(db, ProvisionerState)

    async def get_by_dtype(self, dtype: str) -> ProvisionerState | None:
        """Get provisioner state by dtype.

        Primary lookup method - there's at most one provisioner per dtype.

        Args:
            dtype: Dataset type name

        Returns:
            ProvisionerState if found, None otherwise
        """
        async with self.db.get_session() as session:
            statement = select(ProvisionerState).where(ProvisionerState.dtype == dtype)
            result = await session.exec(statement)
            return result.first()

    async def get_by_id(self, id: UUID) -> ProvisionerState | None:
        """Get provisioner state by ID.

        Args:
            id: ProvisionerState UUID

        Returns:
            ProvisionerState if found, None otherwise
        """
        async with self.db.get_session() as session:
            return await session.get(ProvisionerState, id)

    async def get_running_by_dtype(self, dtype: str) -> ProvisionerState | None:
        """Get running provisioner state by dtype.

        Args:
            dtype: Dataset type name

        Returns:
            Running or starting ProvisionerState if found, None otherwise
        """
        async with self.db.get_session() as session:
            statement = select(ProvisionerState).where(
                ProvisionerState.dtype == dtype,
                or_(
                    ProvisionerState.status == ProvisionerStatus.RUNNING.value,
                    ProvisionerState.status == ProvisionerStatus.STARTING.value,
                ),
            )
            result = await session.exec(statement)
            return result.first()

    async def get_all(self) -> list[ProvisionerState]:
        """Get all provisioner states.

        Returns:
            List of all ProvisionerState records
        """
        async with self.db.get_session() as session:
            statement = select(ProvisionerState)
            result = await session.exec(statement)
            return list(result.all())

    async def upsert_status(
        self,
        dtype: str,
        status: ProvisionerStatus,
        state: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> ProvisionerState:
        """Create or update provisioner state with status transition guards.

        This is the single method for all provisioner state changes. It enforces
        valid status transitions to prevent race conditions.

        Valid transitions:
            None     -> STARTING (create new)
            STARTING -> RUNNING, ERROR
            RUNNING  -> STOPPING
            STOPPING -> STOPPED, ERROR
            STOPPED  -> STARTING (restart)
            ERROR    -> STARTING (retry), STOPPED (cleanup)

        Args:
            dtype: Dataset type name
            status: Target status
            state: Optional state dict (typically set when transitioning to RUNNING)
            error: Optional error message (typically set when transitioning to ERROR)

        Returns:
            Created or updated ProvisionerState

        Raises:
            ProvisionerBusyError: If provisioner is busy (STARTING/STOPPING)
            InvalidProvisionerTransitionError: If transition is not allowed
        """
        async with self.db.get_session() as session:
            # Check for existing record
            result = await session.exec(
                select(ProvisionerState).where(ProvisionerState.dtype == dtype)
            )
            existing = result.first()

            current_status = existing.status if existing else None

            # Validate transition
            allowed = ALLOWED_TRANSITIONS.get(current_status, [])
            if status not in allowed:
                if current_status in (
                    ProvisionerStatus.STARTING.value,
                    ProvisionerStatus.STOPPING.value,
                ):
                    raise ProvisionerBusyError(dtype, current_status)
                raise InvalidProvisionerTransitionError(
                    dtype, current_status, status.value
                )

            now = datetime.now(timezone.utc)

            if existing:
                # Update existing record
                existing.status = status.value
                existing.updated_at = now
                existing.error = error if status == ProvisionerStatus.ERROR else None

                if state is not None:
                    existing.state = state

                # Update timestamps based on status
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
                # Create new record
                provisioner_state = ProvisionerState(
                    id=uuid4(),
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

    async def count_datasets_by_provisioner(self, state_id: UUID) -> int:
        """Count datasets using a specific provisioner state.

        Args:
            state_id: ProvisionerState ID

        Returns:
            Number of datasets attached to this provisioner
        """
        async with self.db.get_session() as session:
            statement = (
                select(func.count())
                .select_from(Dataset)
                .where(Dataset.provisioner_state_id == state_id)
            )
            result = await session.exec(statement)
            return result.first() or 0

    async def delete_by_dtype(self, dtype: str) -> bool:
        """Delete provisioner state by dtype.

        Warning: This does not check for attached datasets. Use
        count_datasets_by_provisioner() first to verify it's safe to delete.

        Args:
            dtype: Dataset type name

        Returns:
            True if deleted, False if not found
        """
        async with self.db.get_session() as session:
            result = await session.exec(
                select(ProvisionerState).where(ProvisionerState.dtype == dtype)
            )
            provisioner_state = result.first()

            if provisioner_state:
                await session.delete(provisioner_state)
                await session.commit()
                return True
            return False
