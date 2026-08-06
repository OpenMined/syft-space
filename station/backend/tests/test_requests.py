"""Space request lifecycle: submit → approve → provision → active, and the
reject / retry / withdraw / conflict paths."""

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
from syft_station.components.requests.entities import RequestStatus
from syft_station.components.requests.handlers import RequestHandler
from syft_station.components.requests.schemas import (
    ApproveRequestBody,
    SubmitRequestBody,
    slugify,
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


def submit_body(subdomain: str = "alpha") -> SubmitRequestBody:
    return SubmitRequestBody(
        space_name="Alpha Lab",
        subdomain=subdomain,
        reason="RAG over our research corpus.",
    )


# ============== Submit / list ==============


async def test_submit_stores_reason(handler):
    request = await handler.submit(submit_body("alpha"), MEMBER)
    assert request.reason == "RAG over our research corpus."

    fetched = await handler.get_request(request.id, MEMBER)
    assert fetched.reason == "RAG over our research corpus."


async def test_submit_reason_is_optional(handler):
    request = await handler.submit(
        SubmitRequestBody(space_name="Alpha Lab", subdomain="alpha"), MEMBER
    )
    assert request.reason == ""


async def test_submit_and_owner_scoped_listing(handler):
    await handler.submit(submit_body("alpha"), MEMBER)
    await handler.submit(submit_body("beta"), OTHER_MEMBER)

    mine = await handler.list_requests(MEMBER)
    assert [r.subdomain for r in mine] == ["alpha"]

    everything = await handler.list_requests(ADMIN)
    assert {r.subdomain for r in everything} == {"alpha", "beta"}


async def test_admin_submission_gets_admin_origin(handler):
    request = await handler.submit(submit_body(), ADMIN)
    assert request.origin == "admin"


async def test_admin_can_submit_on_behalf_of_member(handler):
    body = SubmitRequestBody(
        space_name="For Bob", subdomain="for-bob", owner_email="bob@test.com"
    )
    request = await handler.submit(body, ADMIN)
    assert request.owner_email == "bob@test.com"
    assert request.origin == "admin"


async def test_member_cannot_set_another_owner(handler):
    body = SubmitRequestBody(
        space_name="Sneaky", subdomain="sneaky", owner_email="victim@test.com"
    )
    request = await handler.submit(body, MEMBER)
    assert request.owner_email == MEMBER.email  # override ignored for members


async def test_submit_duplicate_subdomain_conflicts(handler):
    await handler.submit(submit_body("alpha"), MEMBER)
    with pytest.raises(HTTPException) as exc:
        await handler.submit(submit_body("alpha"), OTHER_MEMBER)
    assert exc.value.status_code == 409


# ============== One space per owner ==============


async def test_second_request_by_same_owner_409(handler):
    await handler.submit(submit_body("alpha"), MEMBER)
    with pytest.raises(HTTPException) as exc:
        await handler.submit(submit_body("beta"), MEMBER)
    assert exc.value.status_code == 409
    assert "pending" in exc.value.detail


async def test_active_space_blocks_a_new_request(handler, setup_repository):
    await onboard(setup_repository)
    request = await handler.submit(submit_body("alpha"), MEMBER)
    await handler.approve(request.id, ApproveRequestBody())
    await handler.wait_for_provisioning()

    with pytest.raises(HTTPException) as exc:
        await handler.submit(submit_body("beta"), MEMBER)
    assert exc.value.status_code == 409
    assert "already has a space" in exc.value.detail


async def test_failed_request_still_holds_the_slot(handler, setup_repository):
    # A failed request is admin-retryable: letting the member submit a second
    # while the admin retries the first could yield two spaces.
    await onboard(setup_repository)
    request = await handler.submit(submit_body("fail-alpha"), MEMBER)
    await handler.approve(request.id, ApproveRequestBody())
    await handler.wait_for_provisioning()
    assert (await handler.get_request(request.id, MEMBER)).status == "failed"

    with pytest.raises(HTTPException) as exc:
        await handler.submit(submit_body("beta"), MEMBER)
    assert exc.value.status_code == 409
    assert "failed" in exc.value.detail


async def test_withdraw_frees_the_owner_slot(handler):
    request = await handler.submit(submit_body("alpha"), MEMBER)
    await handler.withdraw(request.id, MEMBER)

    replacement = await handler.submit(submit_body("beta"), MEMBER)
    assert replacement.status == "pending"


async def test_reject_frees_the_owner_slot(handler):
    request = await handler.submit(submit_body("alpha"), MEMBER)
    await handler.reject(request.id, "not now")

    replacement = await handler.submit(submit_body("beta"), MEMBER)
    assert replacement.status == "pending"


async def test_admin_on_behalf_hits_the_owners_slot(handler):
    body = SubmitRequestBody(
        space_name="For Bob", subdomain="for-bob", owner_email="bob@test.com"
    )
    await handler.submit(body, ADMIN)

    with pytest.raises(HTTPException) as exc:
        await handler.submit(
            SubmitRequestBody(
                space_name="Bob Again",
                subdomain="bob-again",
                owner_email="bob@test.com",
            ),
            ADMIN,
        )
    assert exc.value.status_code == 409
    assert "bob@test.com" in exc.value.detail


async def test_admins_own_request_does_not_block_on_behalf_submits(handler):
    await handler.submit(submit_body("admins-own"), ADMIN)

    request = await handler.submit(
        SubmitRequestBody(
            space_name="For Bob", subdomain="for-bob", owner_email="bob@test.com"
        ),
        ADMIN,
    )
    assert request.owner_email == "bob@test.com"


# ============== Get one (status polling) ==============


async def test_get_request_returns_own(handler):
    request = await handler.submit(submit_body("alpha"), MEMBER)
    fetched = await handler.get_request(request.id, MEMBER)
    assert fetched.id == request.id
    assert fetched.subdomain == "alpha"


async def test_get_request_admin_sees_any(handler):
    request = await handler.submit(submit_body("alpha"), MEMBER)
    fetched = await handler.get_request(request.id, ADMIN)
    assert fetched.id == request.id


async def test_get_request_non_owner_403(handler):
    request = await handler.submit(submit_body("alpha"), MEMBER)
    with pytest.raises(HTTPException) as exc:
        await handler.get_request(request.id, OTHER_MEMBER)
    assert exc.value.status_code == 403


async def test_get_request_unknown_404(handler):
    with pytest.raises(HTTPException) as exc:
        await handler.get_request(uuid4(), MEMBER)
    assert exc.value.status_code == 404


# ============== Approve / provision ==============


async def test_approve_provisions_to_active(handler, setup_repository):
    await onboard(setup_repository)
    request = await handler.submit(submit_body("alpha"), MEMBER)

    approved = await handler.approve(request.id, ApproveRequestBody())
    assert approved.status == RequestStatus.PROVISIONING.value
    assert approved.space_id is not None

    await handler.wait_for_provisioning()

    final = (await handler.list_requests(MEMBER))[0]
    assert final.status == RequestStatus.ACTIVE.value

    space = await handler.space_repository.get_by_id(approved.space_id)
    assert space.url == "https://alpha.spaces.test.org"
    assert space.version == "1.0.0"

    token = await handler.space_repository.get_token(space.id)
    assert token is not None and token.token.startswith("sst_")


async def test_approve_lets_admin_edit_name_and_subdomain(handler, setup_repository):
    await onboard(setup_repository)
    request = await handler.submit(submit_body("alpha"), MEMBER)

    approved = await handler.approve(
        request.id, ApproveRequestBody(space_name="Renamed", subdomain="gamma")
    )
    await handler.wait_for_provisioning()

    space = await handler.space_repository.get_by_id(approved.space_id)
    assert space.name == "Renamed"
    assert space.subdomain == "gamma"


async def test_approve_requires_onboarding(handler):
    request = await handler.submit(submit_body(), MEMBER)
    with pytest.raises(HTTPException) as exc:
        await handler.approve(request.id, ApproveRequestBody())
    assert exc.value.status_code == 409
    assert "not set up" in exc.value.detail


async def test_approve_conflicting_subdomain_409(handler, setup_repository):
    await onboard(setup_repository)
    first = await handler.submit(submit_body("alpha"), MEMBER)
    second = await handler.submit(submit_body("beta"), OTHER_MEMBER)
    await handler.approve(first.id, ApproveRequestBody())
    await handler.wait_for_provisioning()

    with pytest.raises(HTTPException) as exc:
        await handler.approve(second.id, ApproveRequestBody(subdomain="alpha"))
    assert exc.value.status_code == 409


async def test_approve_non_pending_409(handler, setup_repository):
    await onboard(setup_repository)
    request = await handler.submit(submit_body(), MEMBER)
    await handler.approve(request.id, ApproveRequestBody())
    with pytest.raises(HTTPException) as exc:
        await handler.approve(request.id, ApproveRequestBody())
    assert exc.value.status_code == 409


async def test_approve_unknown_request_404(handler, setup_repository):
    await onboard(setup_repository)
    with pytest.raises(HTTPException) as exc:
        await handler.approve(uuid4(), ApproveRequestBody())
    assert exc.value.status_code == 404


# ============== Failure / retry ==============


async def test_failing_provision_marks_failed_then_retry_succeeds(
    handler, setup_repository
):
    await onboard(setup_repository)
    request = await handler.submit(submit_body("will-fail"), MEMBER)
    await handler.approve(request.id, ApproveRequestBody())
    await handler.wait_for_provisioning()

    failed = (await handler.list_requests(MEMBER))[0]
    assert failed.status == RequestStatus.FAILED.value
    # The admin sees why it failed
    assert failed.reject_reason

    # Fix the subdomain via re-approve? No — retry re-runs as-is; flip the
    # stored subdomain first to simulate the underlying cause being fixed.
    stored = await handler.repository.get_by_id(request.id)
    stored.subdomain = "now-fine"
    await handler.repository.update(stored)
    space = await handler.space_repository.get_by_id(failed.space_id)
    space.subdomain = "now-fine"
    await handler.space_repository.update(space)

    retried = await handler.retry(request.id)
    assert retried.reject_reason is None  # stale failure cleared

    await handler.wait_for_provisioning()

    final = (await handler.list_requests(MEMBER))[0]
    assert final.status == RequestStatus.ACTIVE.value
    assert final.reject_reason is None


async def test_retry_only_from_failed(handler, setup_repository):
    await onboard(setup_repository)
    request = await handler.submit(submit_body(), MEMBER)
    with pytest.raises(HTTPException) as exc:
        await handler.retry(request.id)
    assert exc.value.status_code == 409


async def test_retry_reuses_space_and_token(handler, setup_repository):
    await onboard(setup_repository)
    request = await handler.submit(submit_body("fail-first"), MEMBER)
    approved = await handler.approve(request.id, ApproveRequestBody())
    await handler.wait_for_provisioning()

    token_before = await handler.space_repository.get_token(approved.space_id)
    await handler.retry(request.id)
    await handler.wait_for_provisioning()
    token_after = await handler.space_repository.get_token(approved.space_id)

    assert token_before.id == token_after.id  # same token row survives retries


# ============== Reject / withdraw ==============


async def test_reject_records_reason(handler):
    request = await handler.submit(submit_body(), MEMBER)
    rejected = await handler.reject(request.id, "not enough capacity")
    assert rejected.status == RequestStatus.REJECTED.value
    assert rejected.reject_reason == "not enough capacity"


async def test_withdraw_keeps_state_and_frees_subdomain(handler):
    request = await handler.submit(submit_body("alpha"), MEMBER)
    withdrawn = await handler.withdraw(request.id, MEMBER)
    assert withdrawn.status == RequestStatus.WITHDRAWN.value

    # Withdrawn requests stay visible to the admin...
    assert len(await handler.list_requests(ADMIN)) == 1
    # ...but no longer reserve the subdomain.
    again = await handler.submit(submit_body("alpha"), OTHER_MEMBER)
    assert again.subdomain == "alpha"


async def test_withdraw_someone_elses_request_403(handler):
    request = await handler.submit(submit_body(), MEMBER)
    with pytest.raises(HTTPException) as exc:
        await handler.withdraw(request.id, OTHER_MEMBER)
    assert exc.value.status_code == 403


async def test_withdraw_non_pending_409(handler, setup_repository):
    await onboard(setup_repository)
    request = await handler.submit(submit_body(), MEMBER)
    await handler.approve(request.id, ApproveRequestBody())
    with pytest.raises(HTTPException) as exc:
        await handler.withdraw(request.id, MEMBER)
    assert exc.value.status_code == 409


# ============== Delete (space teardown) ==============


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


async def test_delete_active_space_tears_down_and_frees_subdomain(
    rec_handler, rec_provisioner, setup_repository
):
    await onboard(setup_repository)
    request = await rec_handler.submit(submit_body("alpha"), MEMBER)
    approved = await rec_handler.approve(request.id, ApproveRequestBody())
    await rec_handler.wait_for_provisioning()

    deleted = await rec_handler.delete_space(request.id, MEMBER)
    assert deleted.status == RequestStatus.DELETED.value

    # The provisioner was asked to fully tear down the space's subdomain.
    assert rec_provisioner.deprovisioned == [("alpha", True)]
    # Space + token rows are gone from the registry...
    assert await rec_handler.space_repository.get_by_subdomain("alpha") is None
    assert await rec_handler.space_repository.get_token(approved.space_id) is None
    # ...and the subdomain is free to request again.
    again = await rec_handler.submit(submit_body("alpha"), OTHER_MEMBER)
    assert again.subdomain == "alpha"
    # Deletion also freed the owner's one-space slot.
    replacement = await rec_handler.submit(submit_body("beta"), MEMBER)
    assert replacement.status == RequestStatus.PENDING.value


async def test_delete_failed_space_cleans_up(
    rec_handler, rec_provisioner, setup_repository
):
    await onboard(setup_repository)
    request = await rec_handler.submit(submit_body("will-fail"), MEMBER)
    await rec_handler.approve(request.id, ApproveRequestBody())
    await rec_handler.wait_for_provisioning()
    assert (await rec_handler.list_requests(MEMBER))[0].status == (
        RequestStatus.FAILED.value
    )

    deleted = await rec_handler.delete_space(request.id, MEMBER)
    assert deleted.status == RequestStatus.DELETED.value
    assert rec_provisioner.deprovisioned == [("will-fail", True)]


async def test_delete_admin_can_delete_any(rec_handler, setup_repository):
    await onboard(setup_repository)
    request = await rec_handler.submit(submit_body("alpha"), MEMBER)
    await rec_handler.approve(request.id, ApproveRequestBody())
    await rec_handler.wait_for_provisioning()

    deleted = await rec_handler.delete_space(request.id, ADMIN)
    assert deleted.status == RequestStatus.DELETED.value


async def test_delete_non_owner_403(rec_handler, setup_repository):
    await onboard(setup_repository)
    request = await rec_handler.submit(submit_body("alpha"), MEMBER)
    await rec_handler.approve(request.id, ApproveRequestBody())
    await rec_handler.wait_for_provisioning()

    with pytest.raises(HTTPException) as exc:
        await rec_handler.delete_space(request.id, OTHER_MEMBER)
    assert exc.value.status_code == 403


async def test_delete_pending_request_409(rec_handler):
    request = await rec_handler.submit(submit_body("alpha"), MEMBER)
    with pytest.raises(HTTPException) as exc:
        await rec_handler.delete_space(request.id, MEMBER)
    assert exc.value.status_code == 409


async def test_delete_while_provisioning_409(rec_handler, setup_repository):
    await onboard(setup_repository)
    request = await rec_handler.submit(submit_body("alpha"), MEMBER)
    # Approve returns while provisioning is still in-flight (background task).
    await rec_handler.approve(request.id, ApproveRequestBody())
    try:
        with pytest.raises(HTTPException) as exc:
            await rec_handler.delete_space(request.id, MEMBER)
        assert exc.value.status_code == 409
    finally:
        await rec_handler.wait_for_provisioning()


async def test_delete_unknown_request_404(rec_handler):
    with pytest.raises(HTTPException) as exc:
        await rec_handler.delete_space(uuid4(), MEMBER)
    assert exc.value.status_code == 404


# ============== Slug helpers ==============


def test_slugify_produces_dns_labels():
    assert slugify("Alpha Lab!") == "alpha-lab"
    assert slugify("  --Weird__ Name--  ") == "weird-name"
    assert len(slugify("x" * 100)) <= 63


def test_submit_body_rejects_bad_slug():
    with pytest.raises(ValueError):
        SubmitRequestBody(space_name="A", subdomain="-bad-")
