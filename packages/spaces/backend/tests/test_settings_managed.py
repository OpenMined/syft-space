"""Managed-mode settings: /settings/managed, seed-once public URL, tunnel refusal.

A station-launched space gets SYFT_CLUSTER_MANAGED_BY and SYFT_PUBLIC_URL
injected. The frontend reads /settings/managed to trim self-hosted onboarding
(signup, hub tunnel); the env seeds the public URL once and never overwrites
a user's edit; generating a tunnel URL is refused because its marketplace
sync would overwrite the station-assigned address.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from fastapi import HTTPException
from pydantic import HttpUrl

from syft_space.components.settings.handlers import SettingsHandler
from syft_space.components.settings.repository import SettingsRepository
from syft_space.components.shared.database import AsyncDatabase
from syft_space.components.tenants.entities import Tenant
from syft_space.config import app_settings

STATION_URL = "http://john.station.localhost/"


@pytest_asyncio.fixture
async def settings_repository(main_db: AsyncDatabase) -> SettingsRepository:
    return SettingsRepository(main_db)


@pytest.fixture
def handler(settings_repository: SettingsRepository) -> SettingsHandler:
    # No marketplace: update_public_url then skips the SyftHub sync.
    marketplace_repository = MagicMock()
    marketplace_repository.get_default = AsyncMock(return_value=None)
    return SettingsHandler(
        settings_repository=settings_repository,
        marketplace_repository=marketplace_repository,
        proxy_service=None,
    )


# ============== GET /settings/managed ==============


async def test_unmanaged_by_default(handler, monkeypatch):
    monkeypatch.setattr(app_settings.cluster, "managed_by", "")

    response = await handler.get_managed()

    assert response.managed is False
    assert response.public_url is None


async def test_managed_with_public_url(handler, tenant: Tenant, monkeypatch):
    monkeypatch.setattr(app_settings.cluster, "managed_by", "Syft Station")
    monkeypatch.setattr(app_settings, "public_url", None)
    await handler.update_public_url(tenant, STATION_URL)

    response = await handler.get_managed()

    assert response.managed is True
    assert response.public_url == STATION_URL


# ============== Seed-once public URL ==============


async def test_env_seeds_empty_database(handler, tenant: Tenant, monkeypatch):
    monkeypatch.setattr(app_settings, "public_url", HttpUrl(STATION_URL))

    await handler.initialize_from_config([tenant])

    assert (await handler.get_public_url()).public_url == STATION_URL


async def test_env_does_not_overwrite_user_edit(handler, tenant: Tenant, monkeypatch):
    monkeypatch.setattr(app_settings, "public_url", None)
    await handler.update_public_url(tenant, "https://my-own-domain.example.com/")
    monkeypatch.setattr(app_settings, "public_url", HttpUrl(STATION_URL))

    await handler.initialize_from_config([tenant])

    url = (await handler.get_public_url()).public_url
    assert url == "https://my-own-domain.example.com/"


async def test_no_env_no_seed(handler, tenant: Tenant, monkeypatch):
    monkeypatch.setattr(app_settings, "public_url", None)

    await handler.initialize_from_config([tenant])

    assert (await handler.get_public_url()).public_url is None


# ============== Tunnel refusal in managed mode ==============


async def test_tunnel_connect_refused_when_managed(
    handler, tenant: Tenant, monkeypatch
):
    monkeypatch.setattr(app_settings.cluster, "managed_by", "Syft Station")

    with pytest.raises(HTTPException) as exc:
        await handler.configure_proxy(tenant)

    assert exc.value.status_code == 409


async def test_tunnel_connect_unguarded_when_unmanaged(
    handler, tenant: Tenant, monkeypatch
):
    # Guard ordering: unmanaged falls through to the normal path (here the
    # 404 for a missing proxy service, not the managed 409).
    monkeypatch.setattr(app_settings.cluster, "managed_by", "")

    with pytest.raises(HTTPException) as exc:
        await handler.configure_proxy(tenant)

    assert exc.value.status_code == 404


# ============== benchmarks_mode: on with the first connection, not after ==============


async def test_a_virgin_space_turns_reporting_on(
    settings_repository: SettingsRepository,
):
    """The switch nobody has ever touched follows the first connection."""
    await settings_repository.enable_benchmarks_if_untouched()

    assert await settings_repository.get_benchmarks_mode() == "local"


async def test_an_explicit_off_is_not_overridden(
    settings_repository: SettingsRepository,
):
    """A second benchmark connecting must not quietly turn reporting back on."""
    await settings_repository.update_benchmarks_mode("off")

    await settings_repository.enable_benchmarks_if_untouched()

    assert await settings_repository.get_benchmarks_mode() == "off"


async def test_turning_it_on_twice_is_a_no_op(
    settings_repository: SettingsRepository,
):
    """A second connection is not a second vote — the first is the one that counts."""
    await settings_repository.enable_benchmarks_if_untouched()
    await settings_repository.update_benchmarks_mode("off")

    await settings_repository.enable_benchmarks_if_untouched()

    assert await settings_repository.get_benchmarks_mode() == "off"


async def test_reading_the_mode_does_not_decide_it(
    settings_repository: SettingsRepository,
):
    """Opening the page that shows the switch is not the owner touching it.

    A read that stored a row would make the first connection look like a
    second one, and reporting would never come on at all.
    """
    assert await settings_repository.get_benchmarks_mode() == "off"

    await settings_repository.enable_benchmarks_if_untouched()

    assert await settings_repository.get_benchmarks_mode() == "local"
