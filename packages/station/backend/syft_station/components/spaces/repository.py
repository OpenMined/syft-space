"""Space registry repository."""

import secrets
from collections.abc import Iterable, Sequence
from uuid import UUID

from sqlmodel import col, select

from syft_station.components.shared.database import AsyncBaseRepository, AsyncDatabase
from syft_station.components.spaces.entities import (
    Space,
    SpaceCondition,
    SpaceConditionType,
    SpaceToken,
)


def generate_space_token() -> str:
    """Mint a space admin API key."""
    return f"sst_{secrets.token_urlsafe(32)}"


class SpaceRepository(AsyncBaseRepository[Space]):
    """Repository for Space + SpaceToken operations."""

    def __init__(self, db: AsyncDatabase):
        super().__init__(db, Space)

    async def list_by_owner(self, owner_email: str) -> list[Space]:
        async with self.db.get_session() as session:
            statement = select(Space).where(Space.owner_email == owner_email)
            result = await session.exec(statement)
            return list(result.all())

    async def get_by_subdomain(self, subdomain: str) -> Space | None:
        async with self.db.get_session() as session:
            statement = select(Space).where(Space.subdomain == subdomain)
            result = await session.exec(statement)
            return result.first()

    async def delete_space(self, space_id: UUID) -> None:
        """Remove a space and its token rows.

        Conditions go with the space through the relationship's cascade;
        tokens have no relationship, so they're removed here.
        """
        async with self.db.get_session() as session:
            tokens = await session.exec(
                select(SpaceToken).where(SpaceToken.space_id == space_id)
            )
            for row in tokens.all():
                await session.delete(row)
            space = await session.get(Space, space_id)
            if space:
                await session.delete(space)
            await session.commit()

    # --- Tokens ---

    async def create_token(self, space_id: UUID, token: str) -> SpaceToken:
        async with self.db.get_session() as session:
            row = SpaceToken(space_id=space_id, token=token)
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return row

    async def get_token(self, space_id: UUID) -> SpaceToken | None:
        async with self.db.get_session() as session:
            statement = select(SpaceToken).where(SpaceToken.space_id == space_id)
            result = await session.exec(statement)
            return result.first()

    async def replace_token(self, space_id: UUID, token: str) -> SpaceToken:
        """Regenerate: replace any existing token row with a fresh one."""
        async with self.db.get_session() as session:
            statement = select(SpaceToken).where(SpaceToken.space_id == space_id)
            result = await session.exec(statement)
            for row in result.all():
                await session.delete(row)
            fresh = SpaceToken(space_id=space_id, token=token)
            session.add(fresh)
            await session.commit()
            await session.refresh(fresh)
            return fresh

    # --- Conditions ---

    async def raise_condition(
        self, space_id: UUID, type_: SpaceConditionType, message: str
    ) -> SpaceCondition:
        """Flag something the admin has to act on; re-raising rewrites the
        message so the newest cause is the one shown."""
        async with self.db.get_session() as session:
            statement = select(SpaceCondition).where(
                SpaceCondition.space_id == space_id,
                SpaceCondition.type == type_.value,
            )
            result = await session.exec(statement)
            row = result.first()
            if row is None:
                row = SpaceCondition(
                    space_id=space_id, type=type_.value, message=message
                )
                session.add(row)
            else:
                row.message = message
            await session.commit()
            await session.refresh(row)
            return row

    async def flag_wallet_stale(
        self, message: str, wallet_id: UUID | None = None
    ) -> int:
        """Flag every space carrying wallet facts that have since changed;
        returns how many. Optionally narrowed to one wallet's spaces.

        Named for the seams that call it — the wallet save and the SyftHub
        identity — neither of which knows the conditions vocabulary.
        """
        async with self.db.get_session() as session:
            statement = select(Space.id).where(col(Space.wallet_id).is_not(None))
            if wallet_id is not None:
                statement = statement.where(Space.wallet_id == wallet_id)
            result = await session.exec(statement)
            space_ids = list(result.all())
        for space_id in space_ids:
            await self.raise_condition(
                space_id, SpaceConditionType.WALLET_STALE, message
            )
        return len(space_ids)

    async def clear_conditions(
        self, space_id: UUID, types: Iterable[SpaceConditionType]
    ) -> int:
        """Resolve conditions of these types; returns how many were cleared."""
        values = [t.value for t in types]
        if not values:
            return 0
        async with self.db.get_session() as session:
            statement = select(SpaceCondition).where(
                SpaceCondition.space_id == space_id,
                col(SpaceCondition.type).in_(values),
            )
            result = await session.exec(statement)
            rows = result.all()
            for row in rows:
                await session.delete(row)
            await session.commit()
            return len(rows)

    async def conditions_for(
        self, space_ids: Sequence[UUID]
    ) -> dict[UUID, list[SpaceCondition]]:
        """Conditions keyed by space — bulk, because the list endpoints
        would otherwise read them one space at a time."""
        if not space_ids:
            return {}
        async with self.db.get_session() as session:
            statement = select(SpaceCondition).where(
                col(SpaceCondition.space_id).in_(list(space_ids))
            )
            result = await session.exec(statement)
            by_space: dict[UUID, list[SpaceCondition]] = {}
            for row in result.all():
                by_space.setdefault(row.space_id, []).append(row)
            return by_space
