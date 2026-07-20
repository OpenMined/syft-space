"""Space request lifecycle: submit → approve → provision → active, and the
reject / retry / withdraw / conflict paths."""

from uuid import uuid4

import pytest
from fastapi import HTTPException

from syft_station.components.provision.dev import DevProvisioner
from syft_station.components.requests.entities import RequestStatus
from syft_station.components.requests.handlers import RequestHandler
from syft_station.components.requests.schemas import (
    ApproveRequestBody,
    SubmitRequestBody,
    slugify,
)
from tests.conftest import ADMIN, MEMBER, OTHER_MEMBER


@pytest.fixture
def handler(request_repository, space_repository, setup_repository) -> RequestHandler:
    return RequestHandler(
        repository=request_repository,
        space_repository=space_repository,
        setup_repository=setup_repository,
        provisioner=DevProvisioner(),
    )


async def onboard(setup_repository) -> None:
    await setup_repository.update_config(
        domain="spaces.test.org", supported_version="1.0.0"
    )


def submit_body(subdomain: str = "alpha") -> SubmitRequestBody:
    return SubmitRequestBody(space_name="Alpha Lab", subdomain=subdomain)


# ============== Submit / list ==============


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


async def test_submit_duplicate_subdomain_conflicts(handler):
    await handler.submit(submit_body("alpha"), MEMBER)
    with pytest.raises(HTTPException) as exc:
        await handler.submit(submit_body("alpha"), OTHER_MEMBER)
    assert exc.value.status_code == 409


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

    # Fix the subdomain via re-approve? No — retry re-runs as-is; flip the
    # stored subdomain first to simulate the underlying cause being fixed.
    stored = await handler.repository.get_by_id(request.id)
    stored.subdomain = "now-fine"
    await handler.repository.update(stored)
    space = await handler.space_repository.get_by_id(failed.space_id)
    space.subdomain = "now-fine"
    await handler.space_repository.update(space)

    await handler.retry(request.id)
    await handler.wait_for_provisioning()

    final = (await handler.list_requests(MEMBER))[0]
    assert final.status == RequestStatus.ACTIVE.value


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


# ============== Slug helpers ==============


def test_slugify_produces_dns_labels():
    assert slugify("Alpha Lab!") == "alpha-lab"
    assert slugify("  --Weird__ Name--  ") == "weird-name"
    assert len(slugify("x" * 100)) <= 63


def test_submit_body_rejects_bad_slug():
    with pytest.raises(ValueError):
        SubmitRequestBody(space_name="A", subdomain="-bad-")
