"""Request repository."""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlmodel import select

from syft_station.components.requests.entities import (
    OPEN_CREATE_STATUSES,
    Request,
    RequestStatus,
    RequestType,
)
from syft_station.components.shared.database import AsyncBaseRepository, AsyncDatabase


@dataclass
class SpaceAttribution:
    """Name/owner of a space as recorded on its create request."""

    name: str
    subdomain: str
    owner_email: str
    deleted: bool


class RequestRepository(AsyncBaseRepository[Request]):
    """Repository for Request operations."""

    def __init__(self, db: AsyncDatabase):
        super().__init__(db, Request)

    async def space_identities(self) -> dict[UUID, SpaceAttribution]:
        """Attribution for every space ever provisioned, keyed by space id.

        The create_space request is the durable identity record — every
        space is born from one, approve-time name edits are written back to
        it, and it is never deleted. A space counts as deleted when an
        approved delete_space request exists for it, so money views resolve
        deleted spaces here after the registry row is gone.
        """
        async with self.db.get_session() as session:
            rows = (
                await session.exec(
                    select(Request).where(Request.space_id.is_not(None))  # type: ignore[union-attr]
                )
            ).all()

        deleted_ids = {
            r.space_id
            for r in rows
            if r.type == RequestType.DELETE_SPACE.value
            and r.status == RequestStatus.APPROVED.value
        }
        return {
            r.space_id: SpaceAttribution(
                name=r.space_name or "",
                subdomain=r.subdomain or "",
                owner_email=r.owner_email,
                deleted=r.space_id in deleted_ids,
            )
            for r in rows
            if r.type == RequestType.CREATE_SPACE.value and r.space_id is not None
        }

    async def list_by_owner(self, owner_email: str) -> list[Request]:
        async with self.db.get_session() as session:
            statement = (
                select(Request)
                .where(Request.owner_email == owner_email)
                .order_by(Request.created_at.desc())  # type: ignore[attr-defined]
            )
            return list((await session.exec(statement)).all())

    async def list_all(self) -> list[Request]:
        async with self.db.get_session() as session:
            statement = select(Request).order_by(
                Request.created_at.desc()  # type: ignore[attr-defined]
            )
            return list((await session.exec(statement)).all())

    async def open_create_for_owner(self, owner_email: str) -> Request | None:
        """The owner's unfinished create_space request, if any.

        A create_space in a not-yet-a-space state (OPEN_CREATE_STATUSES)
        occupies the owner's "one pending create" slot; submit rejects a
        second. Once approved the space exists and the slot is the space
        itself, so approved creates don't count here.
        """
        async with self.db.get_session() as session:
            statement = select(Request).where(
                Request.owner_email == owner_email,
                Request.type == RequestType.CREATE_SPACE.value,
                Request.status.in_(  # type: ignore[attr-defined]
                    [s.value for s in OPEN_CREATE_STATUSES]
                ),
            )
            return (await session.exec(statement)).first()

    async def open_delete_for_space(self, space_id: UUID) -> Request | None:
        """A pending delete_space request for this space, if any."""
        async with self.db.get_session() as session:
            statement = select(Request).where(
                Request.space_id == space_id,
                Request.type == RequestType.DELETE_SPACE.value,
                Request.status == RequestStatus.PENDING.value,
            )
            return (await session.exec(statement)).first()

    async def subdomain_reserved(
        self, subdomain: str, exclude_id: UUID | None = None
    ) -> bool:
        """True if an open create_space request already reserves this subdomain.

        (Existing spaces are checked separately, against the registry.)
        """
        async with self.db.get_session() as session:
            statement = select(Request).where(
                Request.type == RequestType.CREATE_SPACE.value,
                Request.subdomain == subdomain,
                Request.status.in_(  # type: ignore[attr-defined]
                    [s.value for s in OPEN_CREATE_STATUSES]
                ),
            )
            for row in (await session.exec(statement)).all():
                if exclude_id is None or row.id != exclude_id:
                    return True
            return False

    async def set_status(
        self,
        request: Request,
        status: RequestStatus,
        *,
        resolution_note: str | None = None,
        space_id: UUID | None = None,
    ) -> Request:
        request.status = status.value
        if resolution_note is not None:
            request.resolution_note = resolution_note
        if space_id is not None:
            request.space_id = space_id
        request.updated_at = datetime.now(UTC)
        # Stamp a resolution time when the request leaves the open states.
        if status not in OPEN_CREATE_STATUSES and request.resolved_at is None:
            request.resolved_at = request.updated_at
        return await self.update(request)
