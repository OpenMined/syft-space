"""The station's SyftHub identity and its satellite.

One token per station, not per wallet: a second gateway reuses it rather
than minting another, and the satellite that token registers covers the
station's origin however many wallets it grows. Nothing heartbeats that
origin, so registration only ever happens here.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from syft_station.components.auth.syfthub import SyftHubSatelliteError
from syft_station.components.setup.handlers import StationIdentityHandler
from syft_station.components.setup.repository import SetupRepository
from syft_station.components.setup.satellites import StationSatelliteRegistrar
from syft_station.components.setup.schemas import ConnectIdentityRequest
from syft_station.components.shared.database import AsyncDatabase
from tests.conftest import ADMIN, StubHubIdentity

PUBLIC_URL = "https://station.example.com"
KNOWN_ID = StubHubIdentity.SATELLITE_ID


def build(
    db: AsyncDatabase,
    hub: StubHubIdentity,
    public_url: str = PUBLIC_URL,
    seed: str = "",
) -> tuple[StationIdentityHandler, SetupRepository]:
    repository = SetupRepository(db)
    registrar = StationSatelliteRegistrar(repository, hub, public_url, seed)
    return StationIdentityHandler(repository, hub, registrar), repository


def by_password() -> ConnectIdentityRequest:
    return ConnectIdentityRequest(syfthub_password=StubHubIdentity.HUB_PASSWORD)


# ── connecting the identity ─────────────────────────────────────────────


async def test_connect_mints_from_a_password_and_stores_the_token(db):
    hub = StubHubIdentity()
    handler, repository = build(db, hub)

    response = await handler.connect(by_password(), ADMIN.email)

    assert response.connected and response.username == ADMIN.username
    assert hub.minted == [ADMIN.email]
    config = await repository.get_config()
    assert config.hub_pat == "syft_pat_stub_1"
    assert config.hub_user_id == hub.user_id


async def test_connect_adopts_a_pasted_token_without_minting(db):
    hub = StubHubIdentity()
    handler, repository = build(db, hub)

    await handler.connect(
        ConnectIdentityRequest(
            syfthub_api_token="syft_pat_pasted",
            syfthub_password=StubHubIdentity.HUB_PASSWORD,
        ),
        ADMIN.email,
    )

    config = await repository.get_config()
    assert config.hub_pat == "syft_pat_pasted"
    assert hub.minted == []  # the token wins; the password path never ran


async def test_connect_with_neither_credential_is_rejected(db):
    handler, repository = build(db, StubHubIdentity())

    with pytest.raises(HTTPException) as excinfo:
        await handler.connect(ConnectIdentityRequest(), ADMIN.email)

    assert excinfo.value.status_code == 422
    assert (await repository.get_config()).hub_pat == ""


@pytest.mark.parametrize(
    "request_body",
    [
        ConnectIdentityRequest(syfthub_api_token="not-a-pat"),
        ConnectIdentityRequest(syfthub_password="wrong"),
    ],
    ids=["bad token", "bad password"],
)
async def test_a_rejected_credential_stores_nothing(db, request_body):
    handler, repository = build(db, StubHubIdentity())

    with pytest.raises(HTTPException) as excinfo:
        await handler.connect(request_body, ADMIN.email)

    assert excinfo.value.status_code == 400
    assert (await repository.get_config()).hub_pat == ""


async def test_connecting_again_rotates_the_token(db):
    hub = StubHubIdentity()
    handler, repository = build(db, hub)

    await handler.connect(by_password(), ADMIN.email)
    await handler.connect(by_password(), ADMIN.email)

    assert (await repository.get_config()).hub_pat == "syft_pat_stub_2"
    assert len(hub.minted) == 2


async def test_the_token_is_never_returned(db):
    hub = StubHubIdentity()
    handler, _ = build(db, hub)

    await handler.connect(by_password(), ADMIN.email)
    response = await handler.get()

    assert "syft_pat" not in response.model_dump_json()


async def test_get_reports_disconnected_before_anything_is_set(db):
    handler, _ = build(db, StubHubIdentity())

    assert (await handler.get()).connected is False


# ── the satellite it registers ──────────────────────────────────────────


async def test_connecting_registers_the_station_as_a_satellite(db):
    hub = StubHubIdentity()
    handler, repository = build(db, hub)

    response = await handler.connect(by_password(), ADMIN.email)

    assert hub.registered == [(PUBLIC_URL, "station")]
    assert response.satellite_id == KNOWN_ID
    assert (await repository.get_config()).satellite_id == KNOWN_ID


async def test_a_known_satellite_is_moved_rather_than_re_created(db):
    """Otherwise a changed public URL would leave a second satellite behind."""
    hub = StubHubIdentity()
    handler, repository = build(db, hub)
    await repository.update_satellite_id(KNOWN_ID)

    await handler.connect(by_password(), ADMIN.email)

    assert hub.moved == [(KNOWN_ID, PUBLIC_URL)]
    assert hub.registered == []


async def test_a_stale_satellite_id_is_replaced(db):
    hub = StubHubIdentity()
    handler, repository = build(db, hub)
    await repository.update_satellite_id("11111111-0000-4000-8000-000000000000")

    await handler.connect(by_password(), ADMIN.email)

    assert hub.registered == [(PUBLIC_URL, "station")]
    assert (await repository.get_config()).satellite_id == KNOWN_ID


async def test_the_env_seed_reclaims_a_registration_on_a_fresh_database(db):
    """A re-spun station adopts the id it was given instead of making a second."""
    hub = StubHubIdentity()
    handler, repository = build(db, hub, seed=KNOWN_ID)

    await handler.connect(by_password(), ADMIN.email)

    assert hub.moved == [(KNOWN_ID, PUBLIC_URL)]
    assert hub.registered == []
    assert (await repository.get_config()).satellite_id == KNOWN_ID


async def test_no_public_url_registers_nothing_but_still_connects(db):
    hub = StubHubIdentity()
    handler, repository = build(db, hub, public_url="")

    response = await handler.connect(by_password(), ADMIN.email)

    assert response.connected
    assert hub.registered == [] and hub.moved == []
    assert (await repository.get_config()).hub_pat == "syft_pat_stub_1"


async def test_a_failed_registration_still_saves_the_identity(db):
    """Minting only breaks once the hub enforces the origin check, and the
    next boot retries — losing the token instead would be worse."""

    class RefusingHub(StubHubIdentity):
        async def register_satellite(self, pat, base_url, kind="station"):
            raise SyftHubSatelliteError("already held under another kind")

    hub = RefusingHub()
    handler, repository = build(db, hub)

    response = await handler.connect(by_password(), ADMIN.email)

    assert response.connected
    config = await repository.get_config()
    assert config.hub_pat == "syft_pat_stub_1"
    assert config.satellite_id == ""
