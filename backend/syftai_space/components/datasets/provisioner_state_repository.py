"""Provisioner state repository for database operations."""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy.dialects.sqlite import insert
from sqlmodel import select

from syftai_space.components.datasets.entities import (
    ProvisionerState,
    ProvisionerStatus,
)
from syftai_space.components.shared.database import BaseRepository, Database


class ProvisionerStateRepository(BaseRepository[ProvisionerState]):
    """Repository for ProvisionerState CRUD operations.

    Provides three distinct methods for state management:
    - create(): For new datasets, fails if state already exists
    - update(): For existing states, returns None if not found
    - upsert(): Atomic create-or-update for uncertain scenarios (e.g., restart)
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

    def get_by_dataset_id(self, dataset_id: UUID) -> Optional[ProvisionerState]:
        """Get provisioner state by dataset ID.

        Args:
            dataset_id: Dataset ID

        Returns:
            ProvisionerState if found, None otherwise
        """
        with self.db.get_session() as session:
            statement = select(ProvisionerState).where(
                ProvisionerState.dataset_id == dataset_id
            )
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

    def create(
        self,
        dataset_id: UUID,
        state: dict,
        status: ProvisionerStatus,
        error: Optional[str] = None,
    ) -> ProvisionerState:
        """Create new provisioner state for a dataset.

        Use this when you KNOW the state doesn't exist (e.g., new dataset creation).
        Raises IntegrityError if state already exists for dataset_id.

        Args:
            dataset_id: Dataset ID
            state: Provisioner state dictionary
            status: Initial status
            error: Optional error message

        Returns:
            Created ProvisionerState

        Raises:
            sqlalchemy.exc.IntegrityError: If state already exists for dataset_id
        """
        now = datetime.now(timezone.utc)
        started_at, stopped_at = self._compute_timestamps(status, now)

        provisioner_state = ProvisionerState(
            dataset_id=dataset_id,
            state=state,
            status=status.value,
            error=error,
            started_at=started_at,
            stopped_at=stopped_at,
        )

        with self.db.get_session() as session:
            session.add(provisioner_state)
            session.commit()
            session.refresh(provisioner_state)
            return provisioner_state

    def update(
        self,
        dataset_id: UUID,
        status: ProvisionerStatus,
        state: Optional[dict] = None,
        error: Optional[str] = None,
    ) -> Optional[ProvisionerState]:
        """Update existing provisioner state for a dataset.

        Use this when you KNOW the state exists (e.g., after checking or creating).
        Returns None if state doesn't exist.

        Args:
            dataset_id: Dataset ID
            status: New status
            state: Optional new state dictionary (None = keep existing)
            error: Optional error message

        Returns:
            Updated ProvisionerState if found, None otherwise
        """
        with self.db.get_session() as session:
            provisioner_state = session.exec(
                select(ProvisionerState).where(
                    ProvisionerState.dataset_id == dataset_id
                )
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

    def upsert(
        self,
        dataset_id: UUID,
        state: dict,
        status: ProvisionerStatus,
        error: Optional[str] = None,
    ) -> ProvisionerState:
        """Atomic create-or-update provisioner state for a dataset.

        Use this when you DON'T KNOW if state exists (e.g., restart scenarios).
        This is race-condition safe using SQLite's INSERT ON CONFLICT.

        Args:
            dataset_id: Dataset ID
            state: Provisioner state dictionary
            status: Target status
            error: Optional error message

        Returns:
            Created or updated ProvisionerState
        """
        now = datetime.now(timezone.utc)
        started_at, stopped_at = self._compute_timestamps(status, now)

        with self.db.get_session() as session:
            # Build the upsert statement
            stmt = insert(ProvisionerState).values(
                id=uuid4(),
                dataset_id=dataset_id,
                state=state,
                status=status.value,
                error=error,
                started_at=started_at,
                stopped_at=stopped_at,
                created_at=now,
                updated_at=now,
            )

            # On conflict (dataset_id is unique), update the existing record
            update_dict = {
                "state": state,
                "status": status.value,
                "error": error,
                "updated_at": now,
            }

            # Conditionally update timestamps
            if status == ProvisionerStatus.STARTING:
                update_dict["started_at"] = now
                update_dict["stopped_at"] = None
            elif status in (ProvisionerStatus.STOPPED, ProvisionerStatus.ERROR):
                update_dict["stopped_at"] = now

            stmt = stmt.on_conflict_do_update(
                index_elements=["dataset_id"],
                set_=update_dict,
            )

            session.execute(stmt)
            session.commit()

            # Fetch and return the record
            return session.exec(
                select(ProvisionerState).where(
                    ProvisionerState.dataset_id == dataset_id
                )
            ).first()

    def delete_by_dataset_id(self, dataset_id: UUID) -> bool:
        """Delete provisioner state by dataset ID.

        Args:
            dataset_id: Dataset ID

        Returns:
            True if deleted, False if not found
        """
        with self.db.get_session() as session:
            provisioner_state = session.exec(
                select(ProvisionerState).where(
                    ProvisionerState.dataset_id == dataset_id
                )
            ).first()

            if provisioner_state:
                session.delete(provisioner_state)
                session.commit()
                return True
            return False
