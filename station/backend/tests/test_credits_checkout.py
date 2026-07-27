"""Wallet setup, buyer checkout, and the Xendit webhook, tested on the wire.

Xendit's API is stubbed at the HTTP-transport layer (the client's
``_build_http_client`` seam), so the real client/gateway code runs —
payload shape, error handling, and session parsing included.
"""

from __future__ import annotations

import json
from uuid import UUID

import httpx
import pytest_asyncio
from fastapi import FastAPI
from sqlmodel import select

from syft_station.components.auth.session import get_current_user, require_admin
from syft_station.components.credits.entities import Invoice, InvoiceStatus
from syft_station.components.credits.gateway.xendit import XenditClient, XenditGateway
from syft_station.components.credits.handlers import (
    CheckoutHandler,
    CreditsHandler,
    EarningsHandler,
    WalletAdminHandler,
    WebhookHandler,
)
from syft_station.components.credits.provisioning import (
    SpaceCreditsService,
    WalletRollout,
)
from syft_station.components.credits.repository import (
    CreditsLedger,
    PayoutRepository,
    SpaceCreditTokenRepository,
    WalletRepository,
)
from syft_station.components.credits.routes import build_credits_routes
from syft_station.components.credits.tokens import hash_credit_token
from syft_station.components.shared.database import AsyncDatabase
from syft_station.components.spaces.entities import Space
from syft_station.components.spaces.repository import SpaceRepository
from tests.conftest import ADMIN, MEMBER

XENDIT_URL = "https://xendit.test"
CREDITS_URL = "http://station.test:8090"
PUBLIC_URL = "http://station.public"

SETUP_BODY = {
    "provider": "xendit",
    "currency": "PHP",
    "credentials": {"api_key": "xnd_test_key", "callback_token": "cb_secret"},
}


def xendit_ok(request: httpx.Request) -> httpx.Response:
    """Happy-path Xendit /sessions stub; echoes the reference back."""
    assert request.url.path == "/sessions"
    payload = json.loads(request.content)
    assert payload["mode"] == "PAYMENT_LINK" and payload["country"] == "PH"
    return httpx.Response(
        200,
        json={
            "payment_session_id": "ps-123",
            "reference_id": payload["reference_id"],
            "payment_link_url": f"https://checkout.xendit.test/{payload['reference_id']}",
        },
    )


def xendit_down(request: httpx.Request) -> httpx.Response:
    return httpx.Response(500, json={"message": "internal error"})


class RecordingPatcher:
    """SecretPatcher stub recording (subdomain, keys) per patch."""

    def __init__(self):
        self.patched: list[tuple[str, dict[str, str]]] = []

    async def update_space_secret(self, subdomain: str, data: dict[str, str]) -> None:
        self.patched.append((subdomain, data))


class CheckoutTestbed:
    def __init__(self, db: AsyncDatabase, app: FastAPI, patcher: RecordingPatcher):
        self.db = db
        self.app = app
        self.patcher = patcher
        self.wallets = WalletRepository(db)
        self.credit_tokens = SpaceCreditTokenRepository(db)
        self.spaces = SpaceRepository(db)
        self.stub = xendit_ok  # swap per-test to simulate provider failures

    def client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app),
            base_url="http://station.test",
        )

    async def setup_wallet(self) -> dict:
        async with self.client() as client:
            response = await client.put("/api/v1/credits/admin/wallet", json=SETUP_BODY)
            assert response.status_code == 200, response.text
            return response.json()

    async def get_balance(self, email: str) -> float:
        async with CreditsLedger(self.db) as ledger:
            row = await ledger.balances.get(email)
            return row.balance if row else 0.0

    async def get_invoice(self, invoice_id: str):
        async with CreditsLedger(self.db) as ledger:
            return await ledger.invoices.get(UUID(invoice_id))


@pytest_asyncio.fixture
async def testbed(db: AsyncDatabase) -> CheckoutTestbed:
    wallets = WalletRepository(db)
    tokens = SpaceCreditTokenRepository(db)
    patcher = RecordingPatcher()
    credits_service = SpaceCreditsService(wallets, tokens, CREDITS_URL, PUBLIC_URL)
    rollout = WalletRollout(SpaceRepository(db), patcher, credits_service)

    gateway = XenditGateway(XENDIT_URL)
    bed: CheckoutTestbed  # bound below; the stub closure reads it lazily

    def build_client(api_key: str) -> XenditClient:
        client = XenditClient(api_key, XENDIT_URL)
        client._build_http_client = lambda: httpx.AsyncClient(  # type: ignore[method-assign]
            base_url=XENDIT_URL, transport=httpx.MockTransport(lambda r: bed.stub(r))
        )
        return client

    gateway._build_client = build_client  # type: ignore[method-assign]
    gateways = {"xendit": gateway}

    app = FastAPI()
    app.include_router(
        build_credits_routes(
            CreditsHandler(db, wallets, tokens),
            WalletAdminHandler(wallets, gateways, rollout),
            CheckoutHandler(db, wallets, gateways),
            WebhookHandler(db, wallets, gateways),
            EarningsHandler(db, wallets, PayoutRepository(db), SpaceRepository(db)),
        ),
        prefix="/api/v1",
    )
    # Session plumbing is auth's concern, tested there — inject users here.
    app.dependency_overrides[get_current_user] = lambda: MEMBER
    app.dependency_overrides[require_admin] = lambda: ADMIN

    bed = CheckoutTestbed(db, app, patcher)
    return bed


# ============== Wallet setup (admin) ==============


async def test_setup_wallet_and_read_back_without_secrets(testbed: CheckoutTestbed):
    created = await testbed.setup_wallet()
    assert created["configured"] is True
    assert created["provider"] == "xendit" and created["currency"] == "PHP"
    assert "bundles" not in created  # the catalog lives with the spaces now
    assert "credentials" not in json.dumps(created)
    assert "xnd_test_key" not in json.dumps(created)

    async with testbed.client() as client:
        fetched = await client.get("/api/v1/credits/admin/wallet")
    assert fetched.json()["configured"] is True
    assert "xnd_test_key" not in fetched.text


async def test_setup_rejects_bad_input(testbed: CheckoutTestbed):
    async with testbed.client() as client:
        unsupported = await client.put(
            "/api/v1/credits/admin/wallet", json={**SETUP_BODY, "provider": "paypal"}
        )
        bad_currency = await client.put(
            "/api/v1/credits/admin/wallet", json={**SETUP_BODY, "currency": "USD"}
        )
        no_token = await client.put(
            "/api/v1/credits/admin/wallet",
            json={**SETUP_BODY, "credentials": {"api_key": "xnd"}},
        )
    assert unsupported.status_code == 422
    assert bad_currency.status_code == 422  # Xendit has no USD
    assert no_token.status_code == 422


async def test_replace_keeps_id_and_currency(testbed: CheckoutTestbed):
    await testbed.setup_wallet()
    original = await testbed.wallets.get_active()

    async with testbed.client() as client:
        replaced = await client.put(
            "/api/v1/credits/admin/wallet",
            json={
                **SETUP_BODY,
                "credentials": {"api_key": "xnd_rotated", "callback_token": "cb2"},
            },
        )
        currency_change = await client.put(
            "/api/v1/credits/admin/wallet", json={**SETUP_BODY, "currency": "SGD"}
        )

    assert replaced.status_code == 200
    assert currency_change.status_code == 409  # balances are denominated in PHP

    wallet = await testbed.wallets.get_active()
    assert wallet.id == original.id  # space tokens stay bound
    assert wallet.credentials["api_key"] == "xnd_rotated"


async def test_setup_attaches_unbound_spaces(testbed: CheckoutTestbed):
    """Spaces approved before the wallet existed get tokens + Secret keys;
    opted-out spaces are left alone."""
    unbound = await testbed.spaces.create(
        Space(name="Old", subdomain="old-space", owner_email="a@test.com")
    )
    opted_out = await testbed.spaces.create(
        Space(
            name="NoBill",
            subdomain="no-bill",
            owner_email="b@test.com",
            wallet_opt_out=True,
        )
    )

    result = await testbed.setup_wallet()
    assert result["spaces_attached"] == 1 and result["spaces_failed"] == 0

    # Binding minted + intent stored for the unbound space only.
    wallet = await testbed.wallets.get_active()
    binding = await testbed.credit_tokens.get_active_for_space(unbound.id)
    assert binding is not None and binding.wallet_id == wallet.id
    assert (await testbed.spaces.get_by_id(unbound.id)).wallet_id == wallet.id
    assert await testbed.credit_tokens.get_active_for_space(opted_out.id) is None

    # The Secret was patched with the grant (token verifies to the binding).
    [(subdomain, data)] = testbed.patcher.patched
    assert subdomain == "old-space"
    assert data["SYFT_CLUSTER_CREDITS_URL"] == CREDITS_URL
    assert data["SYFT_CLUSTER_CREDITS_CURRENCY"] == "PHP"
    hashed = hash_credit_token(data["SYFT_CLUSTER_CREDITS_TOKEN"])
    assert (await testbed.credit_tokens.get_active_by_hash(hashed)).id == binding.id

    # Re-saving the wallet is a no-op sweep — everyone is already attached.
    again = await testbed.setup_wallet()
    assert again["spaces_attached"] == 0


# ============== Buyer checkout ==============


async def test_wallet_info_unconfigured_and_configured(testbed: CheckoutTestbed):
    async with testbed.client() as client:
        before = await client.get("/api/v1/credits/wallet")
    assert before.json() == {
        "configured": False,
        "provider": None,
        "currency": None,
    }

    await testbed.setup_wallet()
    async with testbed.client() as client:
        after = await client.get("/api/v1/credits/wallet")
    body = after.json()
    assert body["configured"] is True
    assert body["currency"] == "PHP"
    assert "bundles" not in body


async def test_checkout_creates_invoice_then_session(testbed: CheckoutTestbed):
    await testbed.setup_wallet()

    async with testbed.client() as client:
        response = await client.post(
            "/api/v1/credits/checkout", json={"amount": 500, "label": "Basic"}
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["amount"] == 500.0 and body["currency"] == "PHP"
    assert body["checkout_url"].startswith("https://checkout.xendit.test/syft-")

    invoice = await testbed.get_invoice(body["invoice_id"])
    assert invoice.status == InvoiceStatus.PENDING.value
    assert invoice.user_email == MEMBER.email
    assert invoice.bundle_name == "Basic"  # label stored for display
    assert invoice.client_reference == f"syft-{body['invoice_id']}"
    assert invoice.checkout_url == body["checkout_url"]
    assert invoice.provider_session_id == "ps-123"


async def test_checkout_without_wallet_409_and_bad_amount_422(
    testbed: CheckoutTestbed,
):
    async with testbed.client() as client:
        no_wallet = await client.post("/api/v1/credits/checkout", json={"amount": 500})
    assert no_wallet.status_code == 409

    await testbed.setup_wallet()
    async with testbed.client() as client:
        bad_amount = await client.post("/api/v1/credits/checkout", json={"amount": 0})
    assert bad_amount.status_code == 422  # amount must be > 0


async def test_checkout_provider_failure_leaves_invoice_pending(
    testbed: CheckoutTestbed,
):
    await testbed.setup_wallet()
    testbed.stub = xendit_down

    async with testbed.client() as client:
        response = await client.post(
            "/api/v1/credits/checkout", json={"amount": 500, "label": "Basic"}
        )
    assert response.status_code == 502

    # The invoice survives PENDING with no checkout URL — a webhook can
    # still settle it if the session actually went through provider-side.
    async with testbed.db.get_session() as session:
        rows = list((await session.exec(select(Invoice))).all())
    assert len(rows) == 1
    assert rows[0].status == InvoiceStatus.PENDING.value
    assert rows[0].checkout_url == ""


# ============== Xendit webhook ==============


def paid_event(reference: str) -> dict:
    return {
        "event": "payment_session.completed",
        "data": {
            "reference_id": reference,
            "status": "COMPLETED",
            "updated": "2026-07-23T10:00:00+00:00",
        },
    }


async def checkout(
    testbed: CheckoutTestbed, amount: float = 500.0, label: str = "Basic"
) -> dict:
    async with testbed.client() as client:
        response = await client.post(
            "/api/v1/credits/checkout", json={"amount": amount, "label": label}
        )
        assert response.status_code == 200
        return response.json()


async def post_webhook(
    testbed: CheckoutTestbed, payload: dict, token: str = "cb_secret"
) -> httpx.Response:
    async with testbed.client() as client:
        return await client.post(
            "/api/v1/credits/webhooks/xendit",
            json=payload,
            headers={"x-callback-token": token},
        )


async def test_webhook_settles_and_credits_once(testbed: CheckoutTestbed):
    await testbed.setup_wallet()
    body = await checkout(testbed)
    reference = f"syft-{body['invoice_id']}"

    first = await post_webhook(testbed, paid_event(reference))
    duplicate = await post_webhook(testbed, paid_event(reference))

    assert first.json() == {"status": "ok"}
    assert duplicate.json() == {"status": "already_processed"}
    assert await testbed.get_balance(MEMBER.email) == 500.0  # credited once

    invoice = await testbed.get_invoice(body["invoice_id"])
    assert invoice.status == InvoiceStatus.PAID.value
    assert invoice.paid_at is not None
    assert invoice.webhook_payload["event"] == "payment_session.completed"


async def test_webhook_rejects_bad_token(testbed: CheckoutTestbed):
    await testbed.setup_wallet()
    body = await checkout(testbed)

    response = await post_webhook(
        testbed, paid_event(f"syft-{body['invoice_id']}"), token="wrong"
    )
    assert response.status_code == 403
    assert await testbed.get_balance(MEMBER.email) == 0.0


async def test_webhook_ack_paths_never_retry(testbed: CheckoutTestbed):
    """Unknown events / references are 200-acked so Xendit stops retrying."""
    await testbed.setup_wallet()

    unknown_event = await post_webhook(
        testbed, {"event": "payment.capture", "data": {"reference_id": "syft-x"}}
    )
    unknown_reference = await post_webhook(testbed, paid_event("syft-not-ours"))

    assert unknown_event.json() == {"status": "ignored"}
    assert unknown_reference.json() == {"status": "unknown_reference"}


async def test_webhook_expiry_closes_invoice_but_never_reopens_paid(
    testbed: CheckoutTestbed,
):
    await testbed.setup_wallet()
    body = await checkout(testbed)
    reference = f"syft-{body['invoice_id']}"

    await post_webhook(testbed, paid_event(reference))
    late_expiry = await post_webhook(
        testbed,
        {"event": "payment_session.expired", "data": {"reference_id": reference}},
    )

    assert late_expiry.json() == {"status": "already_processed"}
    invoice = await testbed.get_invoice(body["invoice_id"])
    assert invoice.status == InvoiceStatus.PAID.value


async def test_webhook_without_wallet_404(testbed: CheckoutTestbed):
    response = await post_webhook(testbed, paid_event("syft-x"))
    assert response.status_code == 404
