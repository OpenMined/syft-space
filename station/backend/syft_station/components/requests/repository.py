"""Space request repository."""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlmodel import select

from syft_station.components.requests.entities import (
    OWNER_SLOT_STATUSES,
    SUBDOMAIN_RESERVING_STATUSES,
    RequestStatus,
    SpaceRequest,
)
from syft_station.components.shared.database import AsyncBaseRepository, AsyncDatabase


@dataclass
class SpaceAttribution:
    """Name/owner of a space as recorded on its request row."""

    name: str
    subdomain: str
    owner_email: str
    deleted: bool


class RequestRepository(AsyncBaseRepository[SpaceRequest]):
    """Repository for SpaceRequest operations."""

    def __init__(self, db: AsyncDatabase):
        super().__init__(db, SpaceRequest)

    async def space_identities(self) -> dict[UUID, SpaceAttribution]:
        """Attribution for every space ever provisioned, keyed by space id.

        Request rows are the durable identity record: every space is born
        from one (admin-created spaces included), approve-time name edits
        are written back to it, and deletion only flips its status — so
        money views resolve deleted spaces here after the registry row is
        gone.
        """
        async with self.db.get_session() as session:
            statement = select(SpaceRequest).where(
                SpaceRequest.space_id.is_not(None)  # type: ignore[union-attr]
            )
            result = await session.exec(statement)
            return {
                row.space_id: SpaceAttribution(
                    name=row.space_name,
                    subdomain=row.subdomain,
                    owner_email=row.owner_email,
                    deleted=row.status == RequestStatus.DELETED.value,
                )
                for row in result.all()
                if row.space_id is not None
            }

    async def list_by_owner(self, owner_email: str) -> list[SpaceRequest]:
        async with self.db.get_session() as session:
            statement = (
                select(SpaceRequest)
                .where(SpaceRequest.owner_email == owner_email)
                .order_by(SpaceRequest.created_at.desc())  # type: ignore[attr-defined]
            )
            result = await session.exec(statement)
            return list(result.all())

    async def list_all(self) -> list[SpaceRequest]:
        async with self.db.get_session() as session:
            statement = select(SpaceRequest).order_by(
                SpaceRequest.created_at.desc()  # type: ignore[attr-defined]
            )
            result = await session.exec(statement)
            return list(result.all())

    async def live_request_for_owner(self, owner_email: str) -> SpaceRequest | None:
        """Return the request occupying this owner's one-space slot, if any.

        SyftHub supports a single space per user, so while an owner has a
        request in any OWNER_SLOT_STATUSES state, submit rejects a new one.
        """
        async with self.db.get_session() as session:
            statement = select(SpaceRequest).where(
                SpaceRequest.owner_email == owner_email,
                SpaceRequest.status.in_(  # type: ignore[attr-defined]
                    [s.value for s in OWNER_SLOT_STATUSES]
                ),
            )
            result = await session.exec(statement)
            return result.first()

    async def subdomain_in_use(
        self, subdomain: str, exclude_id: UUID | None = None
    ) -> bool:
        """True if a request in a subdomain-reserving state holds this subdomain.

        Distinct from the owner slot: FAILED frees the subdomain (a retry
        re-takes it) but still holds the owner's slot.
        """
        async with self.db.get_session() as session:
            statement = select(SpaceRequest).where(
                SpaceRequest.subdomain == subdomain,
                SpaceRequest.status.in_(  # type: ignore[attr-defined]
                    [s.value for s in SUBDOMAIN_RESERVING_STATUSES]
                ),
            )
            result = await session.exec(statement)
            for row in result.all():
                if exclude_id is None or row.id != exclude_id:
                    return True
            return False

    async def set_status(
        self,
        request: SpaceRequest,
        status: RequestStatus,
        *,
        reject_reason: str | None = None,
        space_id: UUID | None = None,
    ) -> SpaceRequest:
        request.status = status.value
        if reject_reason is not None:
            request.reject_reason = reject_reason
        if space_id is not None:
            request.space_id = space_id
        request.updated_at = datetime.now(UTC)
        return await self.update(request)
