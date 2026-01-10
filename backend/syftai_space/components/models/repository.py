"""Model repository for database operations."""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from sqlmodel import select

from syftai_space.components.models.entities import Model
from syftai_space.components.shared.database import BaseRepository, Database


class ModelRepository(BaseRepository[Model]):
    """Repository for Model CRUD operations."""

    def __init__(self, db: Database):
        """Initialize the model repository.

        Args:
            db: Database instance
        """
        super().__init__(db, Model)

    def get_all(self, tenant_id: UUID) -> list[Model]:
        """Get all models for a specific tenant.

        Args:
            tenant_id: Tenant ID

        Returns:
            List of models
        """
        with self.db.get_session() as session:
            statement = (
                select(Model)
                .where(Model.tenant_id == tenant_id)
                .options(selectinload(Model.endpoints))
            )
            return list(session.exec(statement).all())

    def get_by_id(self, id: int, tenant_id: UUID) -> Optional[Model]:
        """Get a model by ID within a tenant.

        Args:
            id: Model ID
            tenant_id: Tenant ID

        Returns:
            Model if found, None otherwise
        """
        with self.db.get_session() as session:
            statement = (
                select(Model)
                .where(Model.id == id, Model.tenant_id == tenant_id)
                .options(selectinload(Model.endpoints))
            )
            return session.exec(statement).first()

    def get_by_name(self, name: str, tenant_id: UUID) -> Optional[Model]:
        """Get a model by name within a tenant.

        Args:
            name: Model name
            tenant_id: Tenant ID

        Returns:
            Model if found, None otherwise
        """
        with self.db.get_session() as session:
            statement = (
                select(Model)
                .where(Model.name == name, Model.tenant_id == tenant_id)
                .options(selectinload(Model.endpoints))
            )
            return session.exec(statement).first()

    def delete_by_name(self, name: str, tenant_id: UUID) -> bool:
        """Delete a model by name within a tenant.

        Args:
            name: Model name
            tenant_id: Tenant ID

        Returns:
            True if deleted, False if not found
        """
        with self.db.get_session() as session:
            statement = select(Model).where(
                Model.name == name, Model.tenant_id == tenant_id
            )
            obj = session.exec(statement).first()
            if obj:
                session.delete(obj)
                session.commit()
                return True
            return False

    def get_by_type(self, type_name: str, tenant_id: UUID) -> list[Model]:
        """Get all models of a specific type within a tenant.

        Args:
            type_name: Model type name
            tenant_id: Tenant ID

        Returns:
            List of models
        """
        with self.db.get_session() as session:
            statement = select(Model).where(
                Model.dtype == type_name, Model.tenant_id == tenant_id
            )
            return list(session.exec(statement).all())

    def update_by_name(
        self,
        name: str,
        tenant_id: UUID,
        *,
        name_new: Optional[str] = None,
        summary: Optional[str] = None,
        tags: Optional[str] = None,
    ) -> Optional[Model]:
        """Update a model by name within a tenant.

        Uses SELECT FOR UPDATE locking to prevent race conditions when updating
        the name. If name is being changed, it's updated first with proper locking,
        then other fields are updated in the same transaction.

        Args:
            name: Current model name
            tenant_id: Tenant ID
            name_new: New model name (must be unique per tenant)
            summary: Updated summary
            tags: Updated tags

        Returns:
            Updated model if found, None otherwise

        Raises:
            ValueError: If name is being changed and new name already exists
            IntegrityError: If database unique constraint is violated (race condition)
        """
        with self.db.get_session() as session:
            # Load model by current name WITH LOCK to prevent concurrent modifications
            # This ensures no other transaction can modify/delete this model
            model_stmt = (
                select(Model)
                .where(Model.name == name, Model.tenant_id == tenant_id)
                .with_for_update()
            )
            model = session.exec(model_stmt).first()

            if not model:
                return None

            # Handle name update first with proper locking if it's being changed
            if name_new is not None and name_new != model.name:
                # Lock any existing model with the new name to prevent concurrent updates
                # This ensures atomicity: we check AND update in the same locked transaction
                existing_stmt = (
                    select(Model)
                    .where(
                        Model.name == name_new,
                        Model.tenant_id == tenant_id,
                        Model.id != model.id,  # Exclude current model
                    )
                    .with_for_update(
                        nowait=True
                    )  # Fail fast if locked by another transaction
                )
                existing = session.exec(existing_stmt).first()

                if existing:
                    raise ValueError(
                        f"Model '{name_new}' already exists for this tenant"
                    )

                # Update name atomically within the locked transaction
                model.name = name_new

            # Apply updates to other fields if provided
            if summary is not None:
                model.summary = summary
            if tags is not None:
                model.tags = tags

            # Update timestamp
            model.updated_at = datetime.now(timezone.utc)

            # Save all changes in single commit
            session.add(model)
            try:
                session.commit()
                # Reload model with endpoints eagerly loaded before returning
                reloaded = session.exec(
                    select(Model)
                    .where(Model.id == model.id)
                    .options(selectinload(Model.endpoints))
                ).first()
                return reloaded if reloaded else model
            except IntegrityError as e:
                session.rollback()
                # Re-raise as ValueError for consistent error handling
                raise ValueError(
                    f"Model '{name_new}' already exists for this tenant"
                ) from e
