"""Spaces registry (token lifecycle) and first-run setup."""

import pytest
from fastapi import HTTPException

from syft_station.components.credits.provisioning import SpaceCreditsService
from syft_station.components.credits.repository import (
    SpaceCreditTokenRepository,
    WalletRepository,
)
from syft_station.components.provision.mock import MockProvisioner
from syft_station.components.setup.handlers import SetupHandler
from syft_station.components.setup.schemas import UpdateSetupRequest
from syft_station.components.spaces.entities import Space
from syft_station.components.spaces.handlers import SpaceHandler
from syft_station.components.spaces.provisioning import SpaceConverger
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
def provisioner() -> "TrackingProvisioner":
    return TrackingProvisioner()


@pytest.fixture
def space_handler(space_repository, setup_repository, provisioner, db) -> SpaceHandler:
    credits = SpaceCreditsService(
        WalletRepository(db),
        SpaceCreditTokenRepository(db),
        "http://station.test",
        "http://station.public",
    )
    return SpaceHandler(
        space_repository,
        provisioner,
        setup_repository,
        SpaceConverger(space_repository, setup_repository, provisioner, credits),
    )


class TrackingProvisioner(MockProvisioner):
    """Mock + records restarts; set fail_restart to simulate a k8s error."""

    def __init__(self):
        super().__init__()
        self.restarted: list[str] = []
        self.fail_restart = False

    async def restart(self, subdomain: str) -> None:
        if self.fail_restart:
            raise RuntimeError("substrate says no")
        self.restarted.append(subdomain)


async def make_space(
    space_repository,
    owner_email: str = MEMBER.email,
    subdomain: str = "alpha",
    version: str = "",
) -> Space:
    space = await space_repository.create(
        Space(
            name=subdomain.capitalize(),
            subdomain=subdomain,
            owner_email=owner_email,
            url=f"https://{subdomain}.spaces.test.org",
            version=version,
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


async def test_logs_returns_snapshot_lines(space_handler, space_repository):
    space = await make_space(space_repository, MEMBER.email)
    result = await space_handler.logs(space.id, MEMBER, tail_lines=200)
    assert result.lines and all(isinstance(ln, str) for ln in result.lines)


async def test_logs_denied_for_non_owner(space_handler, space_repository):
    space = await make_space(space_repository, MEMBER.email)
    with pytest.raises(HTTPException) as exc:
        await space_handler.logs(space.id, OTHER_MEMBER, tail_lines=200)
    assert exc.value.status_code == 403


async def test_admin_can_read_any_space_logs(space_handler, space_repository):
    space = await make_space(space_repository, MEMBER.email)
    result = await space_handler.logs(space.id, ADMIN, tail_lines=200)
    assert result.lines


async def test_logs_empty_when_paused(space_handler, space_repository):
    space = await make_space(space_repository, MEMBER.email)
    await space_handler.pause(space.id, MEMBER)
    result = await space_handler.logs(space.id, MEMBER, tail_lines=200)
    assert result.lines == []


async def test_status_unknown_space_404(space_handler):
    from uuid import uuid4

    with pytest.raises(HTTPException) as exc:
        await space_handler.runtime_status(uuid4(), MEMBER)
    assert exc.value.status_code == 404


# ============== Restart ==============


async def test_restart_rolls_the_space(space_handler, space_repository, provisioner):
    space = await make_space(space_repository)
    result = await space_handler.restart(space.id, MEMBER)
    assert result.status == "running"
    assert provisioner.restarted == ["alpha"]


async def test_restart_denied_for_non_owner(space_handler, space_repository):
    space = await make_space(space_repository, MEMBER.email)
    with pytest.raises(HTTPException) as exc:
        await space_handler.restart(space.id, OTHER_MEMBER)
    assert exc.value.status_code == 403


async def test_restart_clears_the_restart_required_flag(
    space_handler, space_repository
):
    space = await make_space(space_repository)
    space.restart_required = True
    await space_repository.update(space)

    await space_handler.restart(space.id, MEMBER)

    refreshed = await space_repository.get_by_id(space.id)
    assert refreshed.restart_required is False


async def test_restart_failure_is_502_and_keeps_the_flag(
    space_handler, space_repository, provisioner
):
    space = await make_space(space_repository)
    space.restart_required = True
    await space_repository.update(space)
    provisioner.fail_restart = True

    with pytest.raises(HTTPException) as exc:
        await space_handler.restart(space.id, MEMBER)

    assert exc.value.status_code == 502
    refreshed = await space_repository.get_by_id(space.id)
    assert refreshed.restart_required is True


async def test_resume_clears_the_restart_required_flag(space_handler, space_repository):
    # A fresh pod starts with the current Secret, so resuming applies any
    # pending patch just as well as a restart.
    space = await make_space(space_repository)
    space.restart_required = True
    await space_repository.update(space)
    await space_handler.pause(space.id, MEMBER)

    await space_handler.resume(space.id, MEMBER)

    refreshed = await space_repository.get_by_id(space.id)
    assert refreshed.restart_required is False


# ============== Regenerate applies via restart ==============


async def test_regenerate_restarts_to_apply_the_new_key(
    space_handler, space_repository, provisioner
):
    space = await make_space(space_repository)
    await space_handler.regenerate_token(space.id, MEMBER)
    assert provisioner.restarted == ["alpha"]
    refreshed = await space_repository.get_by_id(space.id)
    assert refreshed.restart_required is False


async def test_regenerate_flags_the_space_when_restart_fails(
    space_handler, space_repository, provisioner
):
    space = await make_space(space_repository)
    provisioner.fail_restart = True

    # The key is still rotated and returned — only the roll-out failed.
    rotated = await space_handler.regenerate_token(space.id, MEMBER)
    assert "authToken=sst_" in rotated.url

    refreshed = await space_repository.get_by_id(space.id)
    assert refreshed.restart_required is True


# ============== Update / update-all ==============


async def onboard_spaces(setup_repository, version: str = "2.0.0") -> None:
    await setup_repository.update_config(
        domain="spaces.test.org", supported_version=version
    )


async def test_update_space_converges_to_supported_version(
    space_handler, space_repository, setup_repository
):
    await onboard_spaces(setup_repository)
    space = await make_space(space_repository, version="1.0.0")

    updated = await space_handler.update_space(space.id)

    assert updated.version == "2.0.0"
    refreshed = await space_repository.get_by_id(space.id)
    assert refreshed.version == "2.0.0"
    assert refreshed.url == "https://alpha.spaces.test.org"


async def test_update_space_refuses_paused(
    space_handler, space_repository, setup_repository
):
    await onboard_spaces(setup_repository)
    space = await make_space(space_repository, version="1.0.0")
    await space_handler.pause(space.id, ADMIN)

    with pytest.raises(HTTPException) as exc:
        await space_handler.update_space(space.id)
    assert exc.value.status_code == 409


async def test_update_all_touches_only_outdated_spaces(
    space_handler, space_repository, setup_repository
):
    await onboard_spaces(setup_repository)
    outdated = await make_space(space_repository, subdomain="alpha", version="1.0.0")
    await make_space(space_repository, subdomain="beta", version="2.0.0")

    result = await space_handler.update_all()

    assert result.supported_version == "2.0.0"
    assert [(r.space_id, r.outcome) for r in result.results] == [
        (outdated.id, "updated")
    ]


async def test_update_all_reports_skipped_and_failed_per_space(
    space_handler, space_repository, setup_repository
):
    await onboard_spaces(setup_repository)
    paused = await make_space(space_repository, subdomain="alpha", version="1.0.0")
    await space_handler.pause(paused.id, ADMIN)
    # The mock provisioner fails subdomains containing "fail".
    await make_space(space_repository, subdomain="failbeta", version="1.0.0")
    await make_space(space_repository, subdomain="gamma", version="1.0.0")

    result = await space_handler.update_all()

    outcomes = {r.name: r.outcome for r in result.results}
    assert outcomes == {"Alpha": "skipped", "Failbeta": "failed", "Gamma": "updated"}
    failed = next(r for r in result.results if r.outcome == "failed")
    assert failed.detail  # the provision error rides along for the admin
