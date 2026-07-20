"""Spaces handler — registry reads + admin-token lifecycle."""

from uuid import UUID

from fastapi import HTTPException, status

from syft_station.components.auth.session import ROLE_ADMIN, SessionUser
from syft_station.components.spaces.entities import Space
from syft_station.components.spaces.repository import (
    SpaceRepository,
    generate_space_token,
)
from syft_station.components.spaces.schemas import (
    SpaceResponse,
    TokenRevealResponse,
    TokenStatusResponse,
)


class SpaceHandler:
    """Space registry + one-time token reveal / regenerate."""

    def __init__(self, repository: SpaceRepository):
        self.repository = repository

    async def list_spaces(self) -> list[SpaceResponse]:
        spaces = await self.repository.get_all()
        return [SpaceResponse.model_validate(s.model_dump()) for s in spaces]

    async def list_mine(self, owner_email: str) -> list[SpaceResponse]:
        spaces = await self.repository.list_by_owner(owner_email)
        return [SpaceResponse.model_validate(s.model_dump()) for s in spaces]

    async def _get_owned_space(self, space_id: UUID, user: SessionUser) -> Space:
        space = await self.repository.get_by_id(space_id)
        if not space:
            raise HTTPException(status_code=404, detail="Space not found")
        if user.role != ROLE_ADMIN and space.owner_email != user.email:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not your space",
            )
        return space

    async def token_status(
        self, space_id: UUID, user: SessionUser
    ) -> TokenStatusResponse:
        space = await self._get_owned_space(space_id, user)
        token_row = await self.repository.get_token(space.id)
        if not token_row:
            raise HTTPException(status_code=404, detail="No token for this space")
        return TokenStatusResponse(
            revealed=token_row.revealed_at is not None,
            created_at=token_row.created_at,
        )

    async def reveal_token(
        self, space_id: UUID, user: SessionUser
    ) -> TokenRevealResponse:
        """One-time reveal: returns the plaintext once, then clears it."""
        space = await self._get_owned_space(space_id, user)
        token_row = await self.repository.get_token(space.id)
        if not token_row:
            raise HTTPException(status_code=404, detail="No token for this space")
        if token_row.token is None:
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="Token already revealed — regenerate to get a new one",
            )
        plaintext = token_row.token
        await self.repository.mark_token_revealed(token_row)
        return TokenRevealResponse(token=plaintext)

    async def regenerate_token(
        self, space_id: UUID, user: SessionUser
    ) -> TokenStatusResponse:
        """Mint a fresh unrevealed token (re-provision applies it in C2)."""
        space = await self._get_owned_space(space_id, user)
        fresh = await self.repository.replace_token(space.id, generate_space_token())
        return TokenStatusResponse(revealed=False, created_at=fresh.created_at)
