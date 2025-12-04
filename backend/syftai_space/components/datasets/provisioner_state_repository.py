"""Provisioner state repository for database operations."""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import or_
from sqlmodel import select

from syftai_space.components.datasets.entities import (
    Dataset,
    ProvisionerState,
    ProvisionerStatus,
)
from syftai_space.components.shared.database import BaseRepository, Database


class ProvisionerStateRepository(BaseRepository[ProvisionerState]):
    """Repository for ProvisionerState CRUD operations.

    Provisioner states are now dtype-based (one per dataset type) instead of
    dataset-based. Multiple datasets can share the same provisioner state.

    Provides methods for:
    - get_by_dtype(): Primary lookup method (one provisioner per dtype)
    - get_running_by_dtype(): Find running provisioner for a dtype
    - get_all_with_datasets(): Get provisioners that have attached datasets
    - create(): Create new provisioner state for a dtype
    - update(): Update existing provisioner state by ID
    - delete(): Delete provisioner state (only if no datasets attached)
    """

    def __init__(self, db: Database):
        """Initialize the provisioner state repository.

        Args:
            db: Database instance
        """
        super().__init__(db, ProvisionerState)

    def _compute_timestamps(
        self, status: ProvisionerStatus, now: datetime
    ) -> tuple[Optional[datetime], Optional[datetime]]:
        """Compute started_at and stopped_at based on status transition.

        Args:
            status: Target status
            now: Current timestamp

        Returns:
            Tuple of (started_at, stopped_at)
        """
        if status == ProvisionerStatus.STARTING:
            return (now, None)
        elif status in (ProvisionerStatus.STOPPED, ProvisionerStatus.ERROR):
            return (None, now)  # started_at unchanged, stopped_at set
        return (None, None)  # No timestamp changes

    def get_by_dtype(self, dtype: str) -> Optional[ProvisionerState]:
        """Get provisioner state by dtype.

        Primary lookup method - there's at most one provisioner per dtype.

        Args:
            dtype: Dataset type name

        Returns:
            ProvisionerState if found, None otherwise
        """
        with self.db.get_session() as session:
            statement = select(ProvisionerState).where(ProvisionerState.dtype == dtype)
            return session.exec(statement).first()

    def get_running_by_dtype(self, dtype: str) -> Optional[ProvisionerState]:
        """Get running provisioner state by dtype.

        Args:
            dtype: Dataset type name

        Returns:
            Running or starting ProvisionerState if found, None otherwise
        """
        with self.db.get_session() as session:
            statement = select(ProvisionerState).where(
                ProvisionerState.dtype == dtype,
                or_(
                    ProvisionerState.status == ProvisionerStatus.RUNNING.value,
                    ProvisionerState.status == ProvisionerStatus.STARTING.value,
                ),
            )
            return session.exec(statement).first()

    def get_by_id(self, state_id: UUID) -> Optional[ProvisionerState]:
        """Get provisioner state by ID.

        Args:
            state_id: ProvisionerState ID

        Returns:
            ProvisionerState if found, None otherwise
        """
        with self.db.get_session() as session:
            statement = select(ProvisionerState).where(ProvisionerState.id == state_id)
            return session.exec(statement).first()

    def get_all_by_status(self, status: ProvisionerStatus) -> list[ProvisionerState]:
        """Get all provisioner states by status.

        Args:
            status: Provisioner status to filter by

        Returns:
            List of provisioner states with matching status
        """
        with self.db.get_session() as session:
            statement = select(ProvisionerState).where(
                ProvisionerState.status == status.value
            )
            return list(session.exec(statement).all())

    def get_all_provisioner_states(self) -> list[ProvisionerState]:
        """Get all provisioner states.

        Returns:
            List of all ProvisionerState records
        """
        with self.db.get_session() as session:
            statement = select(ProvisionerState)
            return list(session.exec(statement).all())

    def get_all_with_datasets(self) -> list[ProvisionerState]:
        """Get all provisioner states that have at least one dataset attached.

        Used during startup to only start provisioners that are needed.

        Returns:
            List of ProvisionerState records with attached datasets
        """
        with self.db.get_session() as session:
            # Join with datasets to find provisioners with at least one dataset
            statement = (
                select(ProvisionerState)
                .join(Dataset, Dataset.provisioner_state_id == ProvisionerState.id)
                .distinct()
            )
            return list(session.exec(statement).all())

    def create(
        self,
        dtype: str,
        state: dict,
        status: ProvisionerStatus,
        error: Optional[str] = None,
    ) -> ProvisionerState:
        """Create new provisioner state for a dtype.

        Use this when you KNOW the state doesn't exist (e.g., first dataset of this type).
        Raises IntegrityError if state already exists for dtype.

        Args:
            dtype: Dataset type name
            state: Provisioner state dictionary (includes connection config fields)
            status: Initial status
            error: Optional error message

        Returns:
            Created ProvisionerState

        Raises:
            sqlalchemy.exc.IntegrityError: If state already exists for dtype
        """
        now = datetime.now(timezone.utc)
        started_at, stopped_at = self._compute_timestamps(status, now)

        provisioner_state = ProvisionerState(
            id=uuid4(),
            dtype=dtype,
            state=state,
            status=status.value,
            error=error,
            started_at=started_at,
            stopped_at=stopped_at,
            created_at=now,
            updated_at=now,
        )

        with self.db.get_session() as session:
            session.add(provisioner_state)
            session.commit()
            session.refresh(provisioner_state)
            return provisioner_state

    def update(
        self,
        state_id: UUID,
        status: ProvisionerStatus,
        state: Optional[dict] = None,
        error: Optional[str] = None,
    ) -> Optional[ProvisionerState]:
        """Update existing provisioner state by ID.

        Use this when you KNOW the state exists (e.g., after checking or creating).
        Returns None if state doesn't exist.

        Args:
            state_id: ProvisionerState ID
            status: New status
            state: Optional new state dictionary (None = keep existing)
            error: Optional error message

        Returns:
            Updated ProvisionerState if found, None otherwise
        """
        with self.db.get_session() as session:
            provisioner_state = session.exec(
                select(ProvisionerState).where(ProvisionerState.id == state_id)
            ).first()

            if not provisioner_state:
                return None

            now = datetime.now(timezone.utc)

            # Update fields
            provisioner_state.status = status.value
            provisioner_state.error = error
            provisioner_state.updated_at = now

            if state is not None:
                provisioner_state.state = state

            # Update timestamps based on status
            if status == ProvisionerStatus.STARTING:
                provisioner_state.started_at = now
                provisioner_state.stopped_at = None
            elif status in (ProvisionerStatus.STOPPED, ProvisionerStatus.ERROR):
                provisioner_state.stopped_at = now

            session.add(provisioner_state)
            session.commit()
            session.refresh(provisioner_state)
            return provisioner_state

    def count_datasets_by_provisioner(self, state_id: UUID) -> int:
        """Count datasets using a specific provisioner state.

        Args:
            state_id: ProvisionerState ID

        Returns:
            Number of datasets
        """
        with self.db.get_session() as session:
            from sqlalchemy import func

            statement = (
                select(func.count())
                .select_from(Dataset)
                .where(Dataset.provisioner_state_id == state_id)
            )
            result = session.exec(statement).first()
            return result or 0

    def delete_by_dtype(self, dtype: str) -> bool:
        """Delete provisioner state by dtype.

        This will only succeed if no datasets are attached.
        Use count_datasets_by_provisioner() first to check.

        Args:
            dtype: Dataset type name

        Returns:
            True if deleted, False if not found
        """
        with self.db.get_session() as session:
            provisioner_state = session.exec(
                select(ProvisionerState).where(ProvisionerState.dtype == dtype)
            ).first()

            if provisioner_state:
                session.delete(provisioner_state)
                session.commit()
                return True
            return False

    def delete_by_id(self, state_id: UUID) -> bool:
        """Delete provisioner state by ID.

        Args:
            state_id: ProvisionerState ID

        Returns:
            True if deleted, False if not found
        """
        with self.db.get_session() as session:
            provisioner_state = session.exec(
                select(ProvisionerState).where(ProvisionerState.id == state_id)
            ).first()

            if provisioner_state:
                session.delete(provisioner_state)
                session.commit()
                return True
            return False
