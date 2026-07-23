"""Provisioning ↔ credits integration.

The wallet picker at approval, fresh-token-per-attempt minting into the
SpaceSpec, retry keeping the attachment intent, and revocation on delete.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import HTTPException

from syft_station.components.credits.entities import Wallet
from syft_station.components.credits.provisioning import SpaceCreditsService
from syft_station.components.credits.repository import (
    SpaceCreditTokenRepository,
    WalletRepository,
)
from syft_station.components.credits.tokens import hash_credit_token
from syft_station.components.provision.interfaces import ProvisionError, SpaceSpec
from syft_station.components.requests.handlers import RequestHandler
from syft_station.components.requests.schemas import (
    ApproveRequestBody,
    SubmitRequestBody,
)
from tests.conftest import ADMIN, MEMBER

CREDITS_URL = "http://station.test:8090"


class SpecRecordingProvisioner:
    """Records every provision spec; subdomains containing 'fail' fail."""

    def __init__(self):
        self.specs: list[SpaceSpec] = []
        self.deprovisioned: list[tuple[str, bool]] = []

    async def provision(self, spec: SpaceSpec) -> str:
        self.specs.append(spec)
        if "fail" in spec.subdomain:
            raise ProvisionError("recording: fail")
        return f"https://{spec.subdomain}.{spec.domain}"

    async def deprovision(self, subdomain: str, purge: bool) -> None:
        self.deprovisioned.append((subdomain, purge))


@pytest.fixture
def wallets(db) -> WalletRepository:
    return WalletRepository(db)


@pytest.fixture
def credit_tokens(db) -> SpaceCreditTokenRepository:
    return SpaceCreditTokenRepository(db)


@pytest.fixture
def credits_service(wallets, credit_tokens) -> SpaceCreditsService:
    return SpaceCreditsService(wallets, credit_tokens, CREDITS_URL)


@pytest.fixture
def provisioner() -> SpecRecordingProvisioner:
    return SpecRecordingProvisioner()


@pytest.fixture
def handler(
    request_repository,
    space_repository,
    setup_repository,
    provisioner,
    credits_service,
) -> RequestHandler:
    return RequestHandler(
        repository=request_repository,
        space_repository=space_repository,
        setup_repository=setup_repository,
        provisioner=provisioner,
        credits=credits_service,
    )


async def onboard(setup_repository) -> None:
    await setup_repository.update_config(
        domain="spaces.test.org", supported_version="1.0.0"
    )


async def make_wallet(wallets: WalletRepository, currency: str = "PHP") -> Wallet:
    return await wallets.create(
        Wallet(provider="xendit", currency=currency, credentials={"api_key": "x"})
    )


async def approve_space(handler, subdomain: str = "alpha", body=None):
    request = await handler.submit(
        SubmitRequestBody(space_name="Alpha Lab", subdomain=subdomain), MEMBER
    )
    approved = await handler.approve(request.id, body or ApproveRequestBody())
    await handler.wait_for_provisioning()
    return approved


# ============== Approve: the wallet picker ==============


async def test_approve_attaches_station_wallet_by_default(
    handler, provisioner, wallets, credit_tokens, setup_repository
):
    await onboard(setup_repository)
    wallet = await make_wallet(wallets)

    approved = await approve_space(handler)

    spec = provisioner.specs[0]
    assert spec.credits_url == CREDITS_URL
    assert spec.credits_currency == "PHP"
    assert spec.credits_token.startswith("sct_")

    # The minted plaintext in the Secret verifies back to this space+wallet.
    binding = await credit_tokens.get_active_by_hash(
        hash_credit_token(spec.credits_token)
    )
    assert binding is not None
    assert binding.space_id == approved.space_id
    assert binding.wallet_id == wallet.id

    # Intent persisted on the space registry.
    space = await handler.space_repository.get_by_id(approved.space_id)
    assert space.wallet_id == wallet.id


async def test_approve_without_station_wallet_provisions_bare(
    handler, provisioner, setup_repository
):
    await onboard(setup_repository)  # no wallet configured

    approved = await approve_space(handler)

    spec = provisioner.specs[0]
    assert spec.credits_token == "" and spec.credits_url == ""
    space = await handler.space_repository.get_by_id(approved.space_id)
    assert space.wallet_id is None


async def test_approve_can_opt_out_of_the_wallet(
    handler, provisioner, wallets, credit_tokens, setup_repository
):
    await onboard(setup_repository)
    await make_wallet(wallets)

    approved = await approve_space(
        handler, body=ApproveRequestBody(attach_wallet=False)
    )

    assert provisioner.specs[0].credits_token == ""
    space = await handler.space_repository.get_by_id(approved.space_id)
    assert space.wallet_id is None
    assert await credit_tokens.get_active_for_space(approved.space_id) is None


async def test_approve_with_unknown_wallet_id_404(handler, wallets, setup_repository):
    await onboard(setup_repository)
    await make_wallet(wallets)

    request = await handler.submit(
        SubmitRequestBody(space_name="Alpha Lab", subdomain="alpha"), MEMBER
    )
    with pytest.raises(HTTPException) as exc:
        await handler.approve(request.id, ApproveRequestBody(wallet_id=uuid4()))
    assert exc.value.status_code == 404

    # Fails the approve itself — the request is still approvable.
    assert (await handler.get_request(request.id, ADMIN)).status == "pending"


async def test_approve_with_explicit_wallet_id(
    handler, provisioner, wallets, setup_repository
):
    await onboard(setup_repository)
    wallet = await make_wallet(wallets)

    approved = await approve_space(
        handler, body=ApproveRequestBody(wallet_id=wallet.id)
    )
    space = await handler.space_repository.get_by_id(approved.space_id)
    assert space.wallet_id == wallet.id
    assert provisioner.specs[0].credits_currency == "PHP"


# ============== Retry: fresh token, same intent ==============


async def test_retry_remints_and_revokes_the_failed_attempts_token(
    handler, provisioner, wallets, credit_tokens, setup_repository
):
    await onboard(setup_repository)
    await make_wallet(wallets)

    request = await handler.submit(
        SubmitRequestBody(space_name="Fail Lab", subdomain="will-fail"), MEMBER
    )
    await handler.approve(request.id, ApproveRequestBody())
    await handler.wait_for_provisioning()
    first_token = provisioner.specs[0].credits_token
    assert first_token.startswith("sct_")

    await handler.retry(request.id)
    await handler.wait_for_provisioning()
    second_token = provisioner.specs[1].credits_token

    # Fresh plaintext each attempt; the failed attempt's token is dead.
    assert second_token.startswith("sct_") and second_token != first_token
    assert (
        await credit_tokens.get_active_by_hash(hash_credit_token(first_token)) is None
    )
    live = await credit_tokens.get_active_by_hash(hash_credit_token(second_token))
    assert live is not None

    # Retry preserved the attachment intent without re-asking.
    assert provisioner.specs[1].credits_currency == "PHP"


async def test_wallet_deleted_between_approve_and_provision_degrades_gracefully(
    handler, provisioner, wallets, setup_repository
):
    """Intent points at a wallet that vanished — provision bare, don't fail."""
    await onboard(setup_repository)
    wallet = await make_wallet(wallets)

    request = await handler.submit(
        SubmitRequestBody(space_name="Fail Lab", subdomain="will-fail"), MEMBER
    )
    await handler.approve(request.id, ApproveRequestBody())
    await handler.wait_for_provisioning()

    await wallets.delete(wallet.id)
    retried = await handler.retry(request.id)
    await handler.wait_for_provisioning()

    assert provisioner.specs[1].credits_token == ""
    assert (await handler.get_request(retried.id, ADMIN)).status == "failed"


# ============== Delete: revocation ==============


async def test_delete_revokes_credit_tokens(
    handler, provisioner, wallets, credit_tokens, setup_repository
):
    await onboard(setup_repository)
    await make_wallet(wallets)

    approved = await approve_space(handler)
    space_id = approved.space_id
    assert await credit_tokens.get_active_for_space(space_id) is not None

    request = await handler.list_requests(MEMBER)
    await handler.delete_space(request[0].id, MEMBER)

    assert await credit_tokens.get_active_for_space(space_id) is None
