"""Spaces registry (token lifecycle) and first-run setup."""

import pytest
from fastapi import HTTPException

from syft_station.components.setup.handlers import SetupHandler
from syft_station.components.setup.schemas import UpdateSetupRequest
from syft_station.components.spaces.entities import Space
from syft_station.components.spaces.handlers import SpaceHandler
from syft_station.components.spaces.repository import generate_space_token
from tests.conftest import ADMIN, MEMBER, OTHER_MEMBER

# ============== Setup ==============


@pytest.fixture
def setup_handler(setup_repository) -> SetupHandler:
    return SetupHandler(setup_repository)


async def test_setup_starts_not_onboarded(setup_handler):
    setup = await setup_handler.get_setup()
    assert setup.onboarded is False
    assert setup.domain == ""


async def test_setup_onboarded_iff_domain_set(setup_handler):
    setup = await setup_handler.update_setup(
        UpdateSetupRequest(domain="spaces.test.org", supported_version="1.0.0")
    )
    assert setup.onboarded is True
    assert setup.domain == "spaces.test.org"
    assert setup.supported_version == "1.0.0"


async def test_setup_partial_update_keeps_other_fields(setup_handler):
    await setup_handler.update_setup(
        UpdateSetupRequest(domain="spaces.test.org", supported_version="1.0.0")
    )
    setup = await setup_handler.update_setup(
        UpdateSetupRequest(supported_version="1.1.0")
    )
    assert setup.domain == "spaces.test.org"
    assert setup.supported_version == "1.1.0"


def test_setup_rejects_invalid_domain():
    with pytest.raises(ValueError):
        UpdateSetupRequest(domain="not a domain")


# ============== Spaces + tokens ==============


@pytest.fixture
def space_handler(space_repository) -> SpaceHandler:
    return SpaceHandler(space_repository)


async def make_space(space_repository, owner_email: str = MEMBER.email) -> Space:
    space = await space_repository.create(
        Space(name="Alpha", subdomain="alpha", owner_email=owner_email)
    )
    await space_repository.create_token(space.id, generate_space_token())
    return space


async def test_list_mine_is_owner_scoped(space_handler, space_repository):
    await make_space(space_repository, MEMBER.email)
    await make_space(space_repository, OTHER_MEMBER.email)

    mine = await space_handler.list_mine(MEMBER.email)
    assert len(mine) == 1

    all_spaces = await space_handler.list_spaces()
    assert len(all_spaces) == 2


async def test_token_reveal_is_one_time(space_handler, space_repository):
    space = await make_space(space_repository)

    status = await space_handler.token_status(space.id, MEMBER)
    assert status.revealed is False

    revealed = await space_handler.reveal_token(space.id, MEMBER)
    assert revealed.token.startswith("sst_")

    # Plaintext is gone after the reveal.
    with pytest.raises(HTTPException) as exc:
        await space_handler.reveal_token(space.id, MEMBER)
    assert exc.value.status_code == 410

    status = await space_handler.token_status(space.id, MEMBER)
    assert status.revealed is True


async def test_token_reveal_denied_for_non_owner(space_handler, space_repository):
    space = await make_space(space_repository, MEMBER.email)
    with pytest.raises(HTTPException) as exc:
        await space_handler.reveal_token(space.id, OTHER_MEMBER)
    assert exc.value.status_code == 403


async def test_admin_can_access_any_space_token(space_handler, space_repository):
    space = await make_space(space_repository, MEMBER.email)
    revealed = await space_handler.reveal_token(space.id, ADMIN)
    assert revealed.token.startswith("sst_")


async def test_regenerate_creates_fresh_unrevealed_token(
    space_handler, space_repository
):
    space = await make_space(space_repository)
    await space_handler.reveal_token(space.id, MEMBER)

    status = await space_handler.regenerate_token(space.id, MEMBER)
    assert status.revealed is False

    revealed = await space_handler.reveal_token(space.id, MEMBER)
    assert revealed.token.startswith("sst_")
