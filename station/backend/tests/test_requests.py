"""Typed request lifecycle: create_space and delete_space through
submit → approve → provision/teardown, plus reject / retry / withdraw and
the one-space / subdomain conflict paths."""

from uuid import uuid4

import pytest
from fastapi import HTTPException

from syft_station.components.credits.provisioning import SpaceCreditsService
from syft_station.components.credits.repository import (
    SpaceCreditTokenRepository,
    WalletRepository,
)
from syft_station.components.provision.interfaces import ProvisionError, SpaceSpec
from syft_station.components.provision.mock import MockProvisioner
from syft_station.components.requests.entities import RequestStatus, RequestType
from syft_station.components.requests.handlers import RequestHandler
from syft_station.components.requests.schemas import (
    ApproveRequestBody,
    CreateSpacePayload,
    DeleteSpacePayload,
    SubmitRequestBody,
)
from syft_station.components.spaces.provisioning import SpaceConverger
from tests.conftest import ADMIN, MEMBER, OTHER_MEMBER


@pytest.fixture
def credits_service(db) -> SpaceCreditsService:
    """Real service over an empty wallets table — the no-wallet station."""
    return SpaceCreditsService(
        WalletRepository(db),
        SpaceCreditTokenRepository(db),
        "http://station.test",
        "http://station.public",
    )


@pytest.fixture
def handler(
    request_repository, space_repository, setup_repository, credits_service
) -> RequestHandler:
    provisioner = MockProvisioner()
    return RequestHandler(
        repository=request_repository,
        space_repository=space_repository,
        setup_repository=setup_repository,
        provisioner=provisioner,
        credits=credits_service,
        converger=SpaceConverger(
            space_repository, setup_repository, provisioner, credits_service
        ),
    )


async def onboard(setup_repository) -> None:
    await setup_repository.update_config(
        domain="spaces.test.org", supported_version="1.0.0"
    )


def create_body(subdomain: str = "alpha", owner_email: str | None = None):
    return SubmitRequestBody(
        payload=CreateSpacePayload(space_name="Alpha Lab", subdomain=subdomain),
        reason="RAG over our research corpus.",
        owner_email=owner_email,
    )


def delete_body(space_id, reason: str = ""):
    return SubmitRequestBody(
        payload=DeleteSpacePayload(), space_id=space_id, reason=reason
    )


async def provision_active(handler, setup_repository, owner=MEMBER, sub="alpha"):
    """submit create → approve → provision; returns the APPROVED request."""
    await onboard(setup_repository)
    request = await handler.submit(create_body(sub), owner)
    await handler.approve(request.id, ApproveRequestBody())
    await handler.wait_for_provisioning()
    return await handler.get_request(request.id, owner)


# ============== Submit (create) / list ==============


async def test_submit_creates_pending_create(handler):
    request = await handler.submit(create_body("alpha"), MEMBER)
    assert request.type == RequestType.CREATE_SPACE.value
    assert request.status == RequestStatus.PENDING.value
    assert request.subdomain == "alpha"


async def test_submit_and_owner_scoped_listing(handler):
    await handler.submit(create_body("alpha"), MEMBER)
    await handler.submit(create_body("beta"), OTHER_MEMBER)
    assert len(await handler.list_requests(MEMBER)) == 1
    assert len(await handler.list_requests(ADMIN)) == 2


async def test_submit_duplicate_subdomain_conflicts(handler):
    await handler.submit(create_body("alpha"), MEMBER)
    with pytest.raises(HTTPException) as exc:
        await handler.submit(create_body("alpha"), OTHER_MEMBER)
    assert exc.value.status_code == 409


async def test_second_open_create_by_same_owner_409(handler):
    await handler.submit(create_body("alpha"), MEMBER)
    with pytest.raises(HTTPException) as exc:
        await handler.submit(create_body("beta"), MEMBER)
    assert exc.value.status_code == 409


async def test_existing_space_blocks_a_new_create(handler, setup_repository):
    await provision_active(handler, setup_repository, sub="alpha")
    with pytest.raises(HTTPException) as exc:
        await handler.submit(create_body("beta"), MEMBER)
    assert exc.value.status_code == 409


async def test_admin_submits_create_on_behalf(handler):
    request = await handler.submit(
        create_body("for-bob", owner_email="bob@test.com"), ADMIN
    )
    assert request.owner_email == "bob@test.com"
    assert request.origin == "admin"


async def test_member_cannot_set_another_owner(handler):
    request = await handler.submit(
        create_body("mine", owner_email="victim@test.com"), MEMBER
    )
    assert request.owner_email == MEMBER.email  # override ignored for members


# ============== Get one ==============


async def test_get_request_non_owner_403(handler):
    request = await handler.submit(create_body("alpha"), MEMBER)
    with pytest.raises(HTTPException) as exc:
        await handler.get_request(request.id, OTHER_MEMBER)
    assert exc.value.status_code == 403


async def test_get_request_unknown_404(handler):
    with pytest.raises(HTTPException) as exc:
        await handler.get_request(uuid4(), MEMBER)
    assert exc.value.status_code == 404


# ============== Approve / provision (create) ==============


async def test_approve_provisions_to_approved(handler, setup_repository):
    await onboard(setup_repository)
    request = await handler.submit(create_body("alpha"), MEMBER)
    approved = await handler.approve(request.id, ApproveRequestBody())
    assert approved.status == RequestStatus.PROVISIONING.value
    assert approved.space_id is not None

    await handler.wait_for_provisioning()
    final = (await handler.list_requests(MEMBER))[0]
    assert final.status == RequestStatus.APPROVED.value

    space = await handler.space_repository.get_by_id(approved.space_id)
    assert space.url == "https://alpha.spaces.test.org"
    token = await handler.space_repository.get_token(space.id)
    assert token is not None and token.token.startswith("sst_")


async def test_approve_lets_admin_edit_name_and_subdomain(handler, setup_repository):
    await onboard(setup_repository)
    request = await handler.submit(create_body("alpha"), MEMBER)
    approved = await handler.approve(
        request.id, ApproveRequestBody(space_name="Renamed", subdomain="gamma")
    )
    await handler.wait_for_provisioning()
    space = await handler.space_repository.get_by_id(approved.space_id)
    assert space.name == "Renamed" and space.subdomain == "gamma"


async def test_approve_requires_onboarding(handler):
    request = await handler.submit(create_body(), MEMBER)
    with pytest.raises(HTTPException) as exc:
        await handler.approve(request.id, ApproveRequestBody())
    assert exc.value.status_code == 409


async def test_approve_conflicting_subdomain_409(handler, setup_repository):
    await provision_active(handler, setup_repository, sub="alpha")
    second = await handler.submit(create_body("beta"), OTHER_MEMBER)
    with pytest.raises(HTTPException) as exc:
        await handler.approve(second.id, ApproveRequestBody(subdomain="alpha"))
    assert exc.value.status_code == 409


async def test_approve_non_pending_409(handler, setup_repository):
    await onboard(setup_repository)
    request = await handler.submit(create_body(), MEMBER)
    await handler.approve(request.id, ApproveRequestBody())
    with pytest.raises(HTTPException) as exc:
        await handler.approve(request.id, ApproveRequestBody())
    assert exc.value.status_code == 409


async def test_approve_unknown_request_404(handler):
    with pytest.raises(HTTPException) as exc:
        await handler.approve(uuid4(), ApproveRequestBody())
    assert exc.value.status_code == 404


# ============== Fail / retry (create) ==============


async def test_failing_provision_marks_failed_then_retry_succeeds(
    handler, setup_repository
):
    await onboard(setup_repository)
    request = await handler.submit(create_body("will-fail"), MEMBER)
    await handler.approve(request.id, ApproveRequestBody())
    await handler.wait_for_provisioning()

    failed = (await handler.list_requests(MEMBER))[0]
    assert failed.status == RequestStatus.FAILED.value
    assert failed.resolution_note  # the admin sees why

    stored = await handler.repository.get_by_id(request.id)
    stored.subdomain = "now-fine"
    await handler.repository.update(stored)
    space = await handler.space_repository.get_by_id(failed.space_id)
    space.subdomain = "now-fine"
    await handler.space_repository.update(space)

    retried = await handler.retry(request.id)
    assert retried.resolution_note is None  # stale failure cleared
    await handler.wait_for_provisioning()

    final = (await handler.list_requests(MEMBER))[0]
    assert final.status == RequestStatus.APPROVED.value


async def test_retry_only_from_failed(handler, setup_repository):
    await onboard(setup_repository)
    request = await handler.submit(create_body(), MEMBER)
    with pytest.raises(HTTPException) as exc:
        await handler.retry(request.id)
    assert exc.value.status_code == 409


# ============== Reject / withdraw ==============


async def test_reject_records_reason(handler):
    request = await handler.submit(create_body(), MEMBER)
    rejected = await handler.reject(request.id, "not enough capacity")
    assert rejected.status == RequestStatus.REJECTED.value
    assert rejected.resolution_note == "not enough capacity"


async def test_withdraw_frees_the_slot(handler):
    request = await handler.submit(create_body("alpha"), MEMBER)
    withdrawn = await handler.withdraw(request.id, MEMBER)
    assert withdrawn.status == RequestStatus.WITHDRAWN.value
    assert len(await handler.list_requests(ADMIN)) == 1  # stays visible
    again = await handler.submit(create_body("alpha"), MEMBER)  # slot + subdomain freed
    assert again.status == RequestStatus.PENDING.value


async def test_withdraw_someone_elses_request_403(handler):
    request = await handler.submit(create_body(), MEMBER)
    with pytest.raises(HTTPException) as exc:
        await handler.withdraw(request.id, OTHER_MEMBER)
    assert exc.value.status_code == 403


async def test_withdraw_non_pending_409(handler, setup_repository):
    await onboard(setup_repository)
    request = await handler.submit(create_body(), MEMBER)
    await handler.approve(request.id, ApproveRequestBody())
    with pytest.raises(HTTPException) as exc:
        await handler.withdraw(request.id, MEMBER)
    assert exc.value.status_code == 409


# ============== Deletion flow ==============


class RecordingProvisioner:
    """Mock provisioner that records deprovision calls (subdomain, purge)."""

    def __init__(self):
        self.deprovisioned: list[tuple[str, bool]] = []

    async def provision(self, spec: SpaceSpec) -> str:
        if "fail" in spec.subdomain:
            raise ProvisionError("recording: fail")
        return f"https://{spec.subdomain}.{spec.domain}"

    async def deprovision(self, subdomain: str, purge: bool) -> None:
        self.deprovisioned.append((subdomain, purge))


@pytest.fixture
def rec_provisioner() -> RecordingProvisioner:
    return RecordingProvisioner()


@pytest.fixture
def rec_handler(
    request_repository,
    space_repository,
    setup_repository,
    rec_provisioner,
    credits_service,
) -> RequestHandler:
    return RequestHandler(
        repository=request_repository,
        space_repository=space_repository,
        setup_repository=setup_repository,
        provisioner=rec_provisioner,
        credits=credits_service,
        converger=SpaceConverger(
            space_repository, setup_repository, rec_provisioner, credits_service
        ),
    )


async def test_submit_delete_creates_pending(rec_handler, setup_repository):
    active = await provision_active(rec_handler, setup_repository)
    req = await rec_handler.submit(delete_body(active.space_id, "done"), MEMBER)
    assert req.type == RequestType.DELETE_SPACE.value
    assert req.status == RequestStatus.PENDING.value
    assert req.space_id == active.space_id


async def test_submit_delete_requires_space_id(rec_handler):
    with pytest.raises(HTTPException) as exc:
        await rec_handler.submit(
            SubmitRequestBody(payload=DeleteSpacePayload()), MEMBER
        )
    assert exc.value.status_code == 422


async def test_submit_delete_non_owner_403(rec_handler, setup_repository):
    active = await provision_active(rec_handler, setup_repository)
    with pytest.raises(HTTPException) as exc:
        await rec_handler.submit(delete_body(active.space_id), OTHER_MEMBER)
    assert exc.value.status_code == 403


async def test_submit_delete_duplicate_pending_409(rec_handler, setup_repository):
    active = await provision_active(rec_handler, setup_repository)
    await rec_handler.submit(delete_body(active.space_id), MEMBER)
    with pytest.raises(HTTPException) as exc:
        await rec_handler.submit(delete_body(active.space_id), MEMBER)
    assert exc.value.status_code == 409


async def test_pending_delete_holds_the_slot(rec_handler, setup_repository):
    active = await provision_active(rec_handler, setup_repository)
    await rec_handler.submit(delete_body(active.space_id), MEMBER)
    # The space still exists while deletion is pending, so no new create.
    with pytest.raises(HTTPException) as exc:
        await rec_handler.submit(create_body("beta"), MEMBER)
    assert exc.value.status_code == 409


async def test_approve_delete_tears_down_and_frees_slot(
    rec_handler, rec_provisioner, setup_repository
):
    active = await provision_active(rec_handler, setup_repository, sub="alpha")
    req = await rec_handler.submit(delete_body(active.space_id), MEMBER)
    done = await rec_handler.approve(req.id, ApproveRequestBody())
    assert done.status == RequestStatus.APPROVED.value
    assert rec_provisioner.deprovisioned == [("alpha", True)]
    assert await rec_handler.space_repository.get_by_subdomain("alpha") is None
    # Slot freed — the owner can request a new space.
    again = await rec_handler.submit(create_body("beta"), MEMBER)
    assert again.status == RequestStatus.PENDING.value


async def test_admin_declines_deletion_keeps_space(rec_handler, setup_repository):
    active = await provision_active(rec_handler, setup_repository)
    req = await rec_handler.submit(delete_body(active.space_id), MEMBER)
    declined = await rec_handler.reject(req.id, "export your data first")
    assert declined.status == RequestStatus.REJECTED.value
    assert declined.resolution_note == "export your data first"
    assert await rec_handler.space_repository.get_by_id(active.space_id) is not None


async def test_owner_withdraws_deletion_keeps_space(rec_handler, setup_repository):
    active = await provision_active(rec_handler, setup_repository)
    req = await rec_handler.submit(delete_body(active.space_id), MEMBER)
    cancelled = await rec_handler.withdraw(req.id, MEMBER)
    assert cancelled.status == RequestStatus.WITHDRAWN.value
    assert await rec_handler.space_repository.get_by_id(active.space_id) is not None


async def test_admin_delete_space_directly(
    rec_handler, rec_provisioner, setup_repository
):
    active = await provision_active(rec_handler, setup_repository, sub="alpha")
    done = await rec_handler.admin_delete_space(active.space_id, ADMIN)
    assert done.type == RequestType.DELETE_SPACE.value
    assert done.status == RequestStatus.APPROVED.value
    assert rec_provisioner.deprovisioned == [("alpha", True)]
    assert await rec_handler.space_repository.get_by_id(active.space_id) is None


async def test_admin_delete_unknown_space_404(rec_handler):
    with pytest.raises(HTTPException) as exc:
        await rec_handler.admin_delete_space(uuid4(), ADMIN)
    assert exc.value.status_code == 404
