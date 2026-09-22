"""Endpoint repository for database operations."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import desc, func
from sqlalchemy.orm import selectinload
from sqlmodel import or_, select

from syft_space.components.endpoints.entities import Endpoint, EndpointQualityCard
from syft_space.components.shared.database import AsyncBaseRepository, AsyncDatabase


class EndpointRepository(AsyncBaseRepository[Endpoint]):
    """Repository for Endpoint CRUD operations."""

    def __init__(self, db: AsyncDatabase):
        """Initialize the endpoint repository.

        Args:
            db: Database instance
        """
        super().__init__(db, Endpoint)

    async def get_all(self, tenant_id: UUID) -> list[Endpoint]:
        """Get all endpoints for a specific tenant.

        Args:
            tenant_id: Tenant ID

        Returns:
            List of endpoints
        """
        async with self.db.get_session() as session:
            statement = (
                select(Endpoint)
                .where(Endpoint.tenant_id == tenant_id)
                .options(
                    selectinload(Endpoint.model),
                    selectinload(Endpoint.dataset),
                )
            )
            result = await session.exec(statement)
            return list(result.all())

    async def get_by_id(self, id: UUID, tenant_id: UUID) -> Endpoint | None:
        """Get an endpoint by ID within a tenant.

        Args:
            id: Endpoint ID
            tenant_id: Tenant ID

        Returns:
            Endpoint if found, None otherwise
        """
        async with self.db.get_session() as session:
            statement = select(Endpoint).where(
                Endpoint.id == id, Endpoint.tenant_id == tenant_id
            )
            result = await session.exec(statement)
            return result.first()

    async def get_by_slug(self, slug: str, tenant_id: UUID) -> Endpoint | None:
        """Get an endpoint by slug within a tenant.

        Args:
            slug: Endpoint slug
            tenant_id: Tenant ID

        Returns:
            Endpoint if found, None otherwise
        """
        async with self.db.get_session() as session:
            statement = (
                select(Endpoint)
                .where(Endpoint.slug == slug, Endpoint.tenant_id == tenant_id)
                .options(
                    selectinload(Endpoint.model),
                    selectinload(Endpoint.dataset),
                    selectinload(Endpoint.policies),
                )
            )
            result = await session.exec(statement)
            return result.first()

    async def delete_by_slug(self, slug: str, tenant_id: UUID) -> bool:
        """Delete an endpoint by slug within a tenant.

        Args:
            slug: Endpoint slug
            tenant_id: Tenant ID

        Returns:
            True if deleted, False if not found
        """
        async with self.db.get_session() as session:
            statement = select(Endpoint).where(
                Endpoint.slug == slug, Endpoint.tenant_id == tenant_id
            )
            result = await session.exec(statement)
            obj = result.first()
            if obj:
                await session.delete(obj)
                await session.commit()
                return True
            return False

    async def update_by_slug(
        self,
        slug: str,
        tenant_id: UUID,
        *,
        name: str | None = None,
        summary: str | None = None,
        description: str | None = None,
        system_prompt: str | None = None,
    ) -> Endpoint | None:
        """Update an endpoint by slug within a tenant.

        Args:
            slug: Endpoint slug
            tenant_id: Tenant ID
            name: New endpoint name
            summary: Updated summary
            description: Updated markdown description
            system_prompt: Updated custom system prompt. An empty string
                clears the override (falls back to model default); ``None``
                leaves the existing value untouched.

        Returns:
            Updated endpoint if found, None otherwise
        """
        async with self.db.get_session() as session:
            statement = (
                select(Endpoint)
                .where(Endpoint.slug == slug, Endpoint.tenant_id == tenant_id)
                .options(
                    selectinload(Endpoint.model),
                    selectinload(Endpoint.dataset),
                    selectinload(Endpoint.policies),
                )
            )
            result = await session.exec(statement)
            endpoint = result.first()

            if not endpoint:
                return None

            # Update fields if provided
            if name is not None:
                endpoint.name = name
            if summary is not None:
                endpoint.summary = summary
            if description is not None:
                endpoint.description = description
            if system_prompt is not None:
                # Empty string clears the override; any non-empty value sets it
                endpoint.system_prompt = system_prompt or None

            endpoint.updated_at = datetime.now(timezone.utc)
            session.add(endpoint)
            await session.commit()
            await session.refresh(endpoint)

            return endpoint

    async def get_by_dataset_id(
        self, dataset_id: UUID, tenant_id: UUID
    ) -> list[Endpoint]:
        """Get all endpoints using a specific dataset within a tenant.

        Args:
            dataset_id: Dataset UUID
            tenant_id: Tenant ID

        Returns:
            List of endpoints
        """
        async with self.db.get_session() as session:
            statement = select(Endpoint).where(
                Endpoint.dataset_id == dataset_id, Endpoint.tenant_id == tenant_id
            )
            result = await session.exec(statement)
            return list(result.all())

    async def get_by_model_id(self, model_id: UUID, tenant_id: UUID) -> list[Endpoint]:
        """Get all endpoints using a specific model within a tenant.

        Args:
            model_id: Model UUID
            tenant_id: Tenant ID

        Returns:
            List of endpoints
        """
        async with self.db.get_session() as session:
            statement = select(Endpoint).where(
                Endpoint.model_id == model_id, Endpoint.tenant_id == tenant_id
            )
            result = await session.exec(statement)
            return list(result.all())

    async def add_publication(
        self, endpoint_id: UUID, marketplace_id: UUID, tenant_id: UUID
    ) -> Endpoint | None:
        """Add a marketplace ID to endpoint's published_to list.

        Args:
            endpoint_id: Endpoint ID
            marketplace_id: Marketplace ID to add
            tenant_id: Tenant ID

        Returns:
            Updated endpoint if found, None otherwise
        """
        async with self.db.get_session() as session:
            statement = select(Endpoint).where(
                Endpoint.id == endpoint_id, Endpoint.tenant_id == tenant_id
            )
            result = await session.exec(statement)
            endpoint = result.first()
            if not endpoint:
                return None

            marketplace_id_str = str(marketplace_id)
            if marketplace_id_str not in endpoint.published_to:
                endpoint.published_to = [*endpoint.published_to, marketplace_id_str]
                endpoint.updated_at = datetime.now(timezone.utc)
                session.add(endpoint)
                await session.commit()
                await session.refresh(endpoint)

            return endpoint

    async def remove_publication(
        self, endpoint_id: UUID, marketplace_id: UUID, tenant_id: UUID
    ) -> Endpoint | None:
        """Remove a marketplace ID from endpoint's published_to list.

        Args:
            endpoint_id: Endpoint ID
            marketplace_id: Marketplace ID to remove
            tenant_id: Tenant ID

        Returns:
            Updated endpoint if found, None otherwise
        """
        async with self.db.get_session() as session:
            statement = select(Endpoint).where(
                Endpoint.id == endpoint_id, Endpoint.tenant_id == tenant_id
            )
            result = await session.exec(statement)
            endpoint = result.first()
            if not endpoint:
                return None

            marketplace_id_str = str(marketplace_id)
            if marketplace_id_str in endpoint.published_to:
                endpoint.published_to = [
                    mid for mid in endpoint.published_to if mid != marketplace_id_str
                ]
                endpoint.updated_at = datetime.now(timezone.utc)
                session.add(endpoint)
                await session.commit()
                await session.refresh(endpoint)

            return endpoint

    async def record_quality(
        self,
        endpoint_id: UUID,
        tenant_id: UUID,
        *,
        kind: str,
        score: float | None,
        fabrication_rate: float | None,
        samples: int,
        reliable: bool,
        checked_at: datetime,
        report: dict,
    ) -> EndpointQualityCard | None:
        """Append a benchmark's card for an endpoint.

        Appends rather than overwrites. A new run does not make the previous
        one untrue - it makes it the one before - and the owner deciding
        whether he vouches for today's share reads it against the ones behind
        it. The newest row is simply the card that currently stands.

        Args:
            endpoint_id: Endpoint the card is about
            tenant_id: Tenant owning it
            kind: What kind of product was measured
            score: Headline share for that kind, or None
            fabrication_rate: Share of no-answer questions answered anyway
            samples: How many questions were graded
            reliable: Whether the benchmark vouches for the figures
            checked_at: When the benchmark ran
            report: The whole card

        Returns:
            The stored card, or None if the endpoint is not this tenant's
        """
        async with self.db.get_session() as session:
            statement = select(Endpoint).where(
                Endpoint.id == endpoint_id, Endpoint.tenant_id == tenant_id
            )
            result = await session.exec(statement)
            if not result.first():
                return None

            card = EndpointQualityCard(
                tenant_id=tenant_id,
                endpoint_id=endpoint_id,
                kind=kind,
                score=score,
                fabrication_rate=fabrication_rate,
                samples=samples,
                reliable=reliable,
                checked_at=checked_at,
                report=report,
            )
            session.add(card)
            await session.commit()
            await session.refresh(card)

            return card

    async def get_current_quality(
        self, endpoint_id: UUID, tenant_id: UUID
    ) -> EndpointQualityCard | None:
        """The card that currently stands for an endpoint, if any.

        The newest card the owner has not withdrawn. None means no benchmark
        has reported - or every card has been retracted - which is not a score
        of zero and must never be rendered as one.

        Args:
            endpoint_id: Endpoint to read
            tenant_id: Tenant owning it

        Returns:
            The standing card, or None
        """
        async with self.db.get_session() as session:
            statement = (
                select(EndpointQualityCard)
                .where(
                    EndpointQualityCard.endpoint_id == endpoint_id,
                    EndpointQualityCard.tenant_id == tenant_id,
                    EndpointQualityCard.retracted_at.is_(None),  # type: ignore[union-attr]
                )
                .order_by(desc(EndpointQualityCard.checked_at))
            )
            result = await session.exec(statement)
            return result.first()

    async def get_quality_history(
        self, endpoint_id: UUID, tenant_id: UUID, *, limit: int = 50
    ) -> list[EndpointQualityCard]:
        """Every card reported for an endpoint, newest first.

        Retracted cards are included: withdrawing a card from the marketplaces
        does not unsay it to the owner, and a history with the awkward runs
        removed is not a history.

        Args:
            endpoint_id: Endpoint to read
            tenant_id: Tenant owning it
            limit: How many cards to return

        Returns:
            Cards ordered by when the benchmark ran, newest first
        """
        async with self.db.get_session() as session:
            statement = (
                select(EndpointQualityCard)
                .where(
                    EndpointQualityCard.endpoint_id == endpoint_id,
                    EndpointQualityCard.tenant_id == tenant_id,
                )
                .order_by(desc(EndpointQualityCard.checked_at))
                .limit(limit)
            )
            result = await session.exec(statement)
            return list(result.all())

    async def retract_quality(self, endpoint_id: UUID, tenant_id: UUID) -> int:
        """Withdraw every standing card for an endpoint.

        Marks rather than deletes. What was published and then taken back is
        itself a fact about this endpoint, and a retraction that erased the
        rows would make the next card look like the first one ever reported.

        Args:
            endpoint_id: Endpoint whose cards are withdrawn
            tenant_id: Tenant owning it

        Returns:
            How many cards were standing; 0 means there was nothing to
            withdraw, which is not an error
        """
        async with self.db.get_session() as session:
            statement = select(EndpointQualityCard).where(
                EndpointQualityCard.endpoint_id == endpoint_id,
                EndpointQualityCard.tenant_id == tenant_id,
                EndpointQualityCard.retracted_at.is_(None),  # type: ignore[union-attr]
            )
            result = await session.exec(statement)
            standing = list(result.all())

            now = datetime.now(timezone.utc)
            for card in standing:
                card.retracted_at = now
                session.add(card)

            if standing:
                await session.commit()

            return len(standing)

    async def count_published(self, tenant_id: UUID) -> int:
        """Count endpoints where published=true for a tenant.

        Args:
            tenant_id: Tenant ID

        Returns:
            Count of published endpoints
        """
        async with self.db.get_session() as session:
            statement = (
                select(func.count())
                .select_from(Endpoint)
                .where(
                    Endpoint.tenant_id == tenant_id,
                    Endpoint.published.is_(True),
                )
            )
            result = await session.exec(statement)
            return result.first() or 0

    async def count_created_in_range(
        self, tenant_id: UUID, start: datetime, end: datetime
    ) -> int:
        """Count endpoints created within a time range for a tenant.

        Args:
            tenant_id: Tenant ID
            start: Range start (inclusive)
            end: Range end (inclusive)

        Returns:
            Count of endpoints created in the range
        """
        async with self.db.get_session() as session:
            statement = (
                select(func.count())
                .select_from(Endpoint)
                .where(
                    Endpoint.tenant_id == tenant_id,
                    Endpoint.created_at >= start,
                    Endpoint.created_at <= end,
                )
            )
            result = await session.exec(statement)
            return result.first() or 0

    async def get_published_endpoints(self, tenant_id: UUID) -> list[Endpoint]:
        """Get all endpoints that are published to at least one marketplace.

        Args:
            tenant_id: Tenant ID

        Returns:
            List of published endpoints with policies eagerly loaded
        """
        async with self.db.get_session() as session:
            statement = (
                select(Endpoint)
                .where(
                    Endpoint.tenant_id == tenant_id,
                    or_(Endpoint.published_to.isnot(None), Endpoint.published_to != []),
                )
                .options(
                    selectinload(Endpoint.model),
                    selectinload(Endpoint.dataset),
                    selectinload(Endpoint.policies),
                )
            )
            result = await session.exec(statement)
            return list(result.all())
