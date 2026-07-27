"""Spaces registry (token lifecycle) and first-run setup."""

import pytest
from fastapi import HTTPException

from syft_station.components.provision.mock import MockProvisioner
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


async def test_setup_exposes_station_host_from_public_url(setup_handler, monkeypatch):
    """Onboarding surfaces the station's own host (parsed from its public URL,
    scheme/port stripped) so the admin confirms it and hangs spaces off it."""
    from syft_station.components.setup import handlers as setup_handlers

    monkeypatch.setattr(
        setup_handlers.app_settings, "public_url", "https://station.example.com"
    )
    setup = await setup_handler.get_setup()
    assert setup.station_host == "station.example.com"


async def test_setup_station_host_empty_without_public_url(setup_handler, monkeypatch):
    """Host-run dev has no public URL — the admin then types the domain freely."""
    from syft_station.components.setup import handlers as setup_handlers

    monkeypatch.setattr(setup_handlers.app_settings, "public_url", "")
    setup = await setup_handler.get_setup()
    assert setup.station_host == ""


# ============== Spaces + tokens ==============


@pytest.fixture
def space_handler(space_repository) -> SpaceHandler:
    return SpaceHandler(space_repository, MockProvisioner())


async def make_space(space_repository, owner_email: str = MEMBER.email) -> Space:
    space = await space_repository.create(
        Space(
            name="Alpha",
            subdomain="alpha",
            owner_email=owner_email,
            url="https://alpha.spaces.test.org",
        )
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


async def test_admin_url_is_repeatable(space_handler, space_repository):
    space = await make_space(space_repository)

    first = await space_handler.admin_url(space.id, MEMBER)
    again = await space_handler.admin_url(space.id, MEMBER)

    # The space URL with the key attached — clicking opens the space
    # signed in. Stable across calls (no one-time semantics).
    assert first.url.startswith(
        "https://alpha.spaces.test.org/frontend/#/?authToken=sst_"
    )
    assert again.url == first.url


async def test_admin_url_denied_for_non_owner(space_handler, space_repository):
    space = await make_space(space_repository, MEMBER.email)
    with pytest.raises(HTTPException) as exc:
        await space_handler.admin_url(space.id, OTHER_MEMBER)
    assert exc.value.status_code == 403


async def test_admin_can_access_any_space_admin_url(space_handler, space_repository):
    space = await make_space(space_repository, MEMBER.email)
    result = await space_handler.admin_url(space.id, ADMIN)
    assert "authToken=sst_" in result.url


async def test_regenerate_rotates_the_key_and_url(space_handler, space_repository):
    space = await make_space(space_repository)
    before = await space_handler.admin_url(space.id, MEMBER)

    rotated = await space_handler.regenerate_token(space.id, MEMBER)

    assert "authToken=sst_" in rotated.url
    assert rotated.url != before.url  # fresh key
    after = await space_handler.admin_url(space.id, MEMBER)
    assert after.url == rotated.url


# ============== Runtime ops (pause / resume / status) ==============


async def test_status_starts_running(space_handler, space_repository):
    space = await make_space(space_repository)
    result = await space_handler.runtime_status(space.id, MEMBER)
    assert result.status == "running"


async def test_pause_then_resume_round_trips(space_handler, space_repository):
    space = await make_space(space_repository)

    paused = await space_handler.pause(space.id, MEMBER)
    assert paused.status == "paused"

    resumed = await space_handler.resume(space.id, MEMBER)
    assert resumed.status == "running"


async def test_pause_denied_for_non_owner(space_handler, space_repository):
    space = await make_space(space_repository, MEMBER.email)
    with pytest.raises(HTTPException) as exc:
        await space_handler.pause(space.id, OTHER_MEMBER)
    assert exc.value.status_code == 403


async def test_admin_can_pause_any_space(space_handler, space_repository):
    space = await make_space(space_repository, MEMBER.email)
    paused = await space_handler.pause(space.id, ADMIN)
    assert paused.status == "paused"


async def test_status_unknown_space_404(space_handler):
    from uuid import uuid4

    with pytest.raises(HTTPException) as exc:
        await space_handler.runtime_status(uuid4(), MEMBER)
    assert exc.value.status_code == 404
