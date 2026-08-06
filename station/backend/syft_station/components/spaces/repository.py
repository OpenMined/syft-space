"""Space registry repository."""

import secrets
from uuid import UUID

from sqlmodel import select

from syft_station.components.shared.database import AsyncBaseRepository, AsyncDatabase
from syft_station.components.spaces.entities import Space, SpaceToken


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
        """Remove a space and its token rows from the registry."""
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
