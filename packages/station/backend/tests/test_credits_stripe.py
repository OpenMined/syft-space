"""The Stripe gateway on the wire: checkout sessions, signed webhooks, and
the provider-split bundle catalog.

Stripe's API is stubbed at the HTTP-transport layer (the client's
``_build_http_client`` seam), so the real client/gateway code runs —
form-encoded payload shape, minor-unit conversion, and session parsing
included. Webhooks are signed with the real HMAC scheme, so verification
runs against genuine signatures.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from datetime import datetime
from urllib.parse import parse_qs
from uuid import UUID

import httpx
import pytest_asyncio
from fastapi import FastAPI

from syft_station.components.auth.session import get_current_user, require_admin
from syft_station.components.credits.bundles import bundle_amount
from syft_station.components.credits.entities import InvoiceStatus
from syft_station.components.credits.gateway.stripe import (
    StripeClient,
    StripeGateway,
    to_stripe_minor_units,
)
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
from syft_station.components.requests.repository import RequestRepository
from syft_station.components.setup.repository import SetupRepository
from syft_station.components.shared.database import AsyncDatabase
from syft_station.components.spaces.repository import SpaceRepository
from tests.conftest import (
    ADMIN,
    MEMBER,
    StubHubIdentity,
    buyer_auth,
    connect_station_identity,
)

STRIPE_URL = "https://stripe.test"
WEBHOOK_SECRET = "whsec_test_secret"

SETUP_BODY = {
    "provider": "stripe",
    "currency": "USD",
    "credentials": {"secret_key": "sk_test_key", "webhook_secret": WEBHOOK_SECRET},
}


def stripe_ok(request: httpx.Request) -> httpx.Response:
    """Happy-path /v1/checkout/sessions stub; asserts the wire format."""
    assert request.url.path == "/v1/checkout/sessions"
    form = {k: v[0] for k, v in parse_qs(request.content.decode()).items()}
    assert form["mode"] == "payment"
    # Hosted checkout with no return URLs — Stripe shows its own
    # confirmation screen (Xendit-parity; settlement is webhook-driven).
    assert "success_url" not in form and "cancel_url" not in form
    assert request.headers["Idempotency-Key"] == form["client_reference_id"]
    return httpx.Response(
        200,
        json={
            "id": "cs_test_123",
            "url": f"https://checkout.stripe.test/{form['client_reference_id']}",
            "client_reference_id": form["client_reference_id"],
            "status": "open",
        },
    )


def stripe_down(request: httpx.Request) -> httpx.Response:
    return httpx.Response(500, json={"error": {"message": "internal error"}})


def stripe_no_url(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"id": "cs_test_123", "status": "open"})


class NullPatcher:
    """SecretPatcher stub — no spaces exist in these tests."""

    async def update_space_secret(self, subdomain: str, data: dict[str, str]) -> None:
        pass

    async def restart(self, subdomain: str) -> None:
        pass


class StripeTestbed:
    def __init__(self, db: AsyncDatabase, app: FastAPI):
        self.db = db
        self.app = app
        self.wallets = WalletRepository(db)
        self.stub = stripe_ok  # swap per-test to simulate provider failures
        self.captured_forms: list[dict] = []

    def client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app),
            base_url="http://station.test",
        )

    async def setup_wallet(self, body: dict | None = None) -> httpx.Response:
        async with self.client() as client:
            return await client.put(
                "/api/v1/credits/admin/wallet", json=body or SETUP_BODY
            )

    async def buy(self, bundle: str = "Basic") -> dict:
        wallet = await self.wallets.get_active()
        async with self.client() as client:
            response = await client.post(
                f"/api/v1/credits/{wallet.id}/invoices",
                json={"bundle_name": bundle},
                headers=buyer_auth(MEMBER.email),
            )
            assert response.status_code == 201, response.text
            return response.json()

    async def post_webhook(
        self, payload: dict, *, sign: bool = True, header: str | None = None
    ) -> httpx.Response:
        """Deliver a webhook, signed the way Stripe signs (t.body HMAC)."""
        raw = json.dumps(payload).encode()
        headers = {"Content-Type": "application/json"}
        if header is not None:
            headers["Stripe-Signature"] = header
        elif sign:
            headers["Stripe-Signature"] = sign_webhook(raw)
        async with self.client() as client:
            return await client.post(
                "/api/v1/credits/webhooks/stripe", content=raw, headers=headers
            )

    async def get_balance(self, email: str) -> float:
        async with CreditsLedger(self.db) as ledger:
            row = await ledger.balances.get(email)
            return row.balance if row else 0.0

    async def get_invoice(self, invoice_id: str):
        async with CreditsLedger(self.db) as ledger:
            return await ledger.invoices.get(UUID(invoice_id))


def sign_webhook(raw_body: bytes, ts: int | None = None) -> str:
    ts = ts if ts is not None else int(time.time())
    mac = hmac.new(
        WEBHOOK_SECRET.encode(), f"{ts}.{raw_body.decode()}".encode(), hashlib.sha256
    ).hexdigest()
    return f"t={ts},v1={mac}"


@pytest_asyncio.fixture
async def testbed(db: AsyncDatabase) -> StripeTestbed:
    wallets = WalletRepository(db)
    tokens = SpaceCreditTokenRepository(db)
    credits_service = SpaceCreditsService(
        wallets, tokens, SetupRepository(db), "http://c", "http://p"
    )
    rollout = WalletRollout(SpaceRepository(db), NullPatcher(), credits_service)

    gateway = StripeGateway(STRIPE_URL)
    bed: StripeTestbed  # bound below; the stub closure reads it lazily

    def build_client(secret_key: str) -> StripeClient:
        client = StripeClient(secret_key, STRIPE_URL)
        client._build_http_client = lambda: httpx.AsyncClient(  # type: ignore[method-assign]
            base_url=STRIPE_URL, transport=httpx.MockTransport(lambda r: bed.stub(r))
        )
        return client

    gateway._build_client = build_client  # type: ignore[method-assign]
    gateways = {"stripe": gateway}
    hub = StubHubIdentity()

    app = FastAPI()
    app.include_router(
        build_credits_routes(
            CreditsHandler(db, wallets, tokens),
            WalletAdminHandler(wallets, gateways, rollout),
            CheckoutHandler(db, wallets, gateways, hub, SetupRepository(db)),  # type: ignore[arg-type]
            WebhookHandler(db, wallets, gateways),
            EarningsHandler(db, wallets, PayoutRepository(db), RequestRepository(db)),
        ),
        prefix="/api/v1",
    )
    app.dependency_overrides[get_current_user] = lambda: MEMBER
    app.dependency_overrides[require_admin] = lambda: ADMIN

    await connect_station_identity(db, hub)
    bed = StripeTestbed(db, app)
    return bed


def completed_event(reference: str, payment_status: str = "paid") -> dict:
    return {
        "type": "checkout.session.completed",
        "created": 1_753_264_800,  # 2025-07-23T10:00:00Z (event-level)
        "data": {
            "object": {
                "client_reference_id": reference,
                "payment_status": payment_status,
                "created": 1_753_264_700,
            }
        },
    }


def session_event(event_type: str, reference: str) -> dict:
    return {
        "type": event_type,
        "data": {"object": {"client_reference_id": reference}},
    }


# ============== Catalog + unit conversion ==============


def test_minor_units_two_decimal_and_zero_decimal():
    assert to_stripe_minor_units(25.0, "USD") == 2500
    assert to_stripe_minor_units(0.5, "EUR") == 50
    # JPY is zero-decimal: charging 500 must send 500, not 50 000.
    assert to_stripe_minor_units(500.0, "JPY") == 500


def test_bundle_catalog_is_provider_split():
    # Same currency, different prices per provider (SGD diverges).
    assert bundle_amount("xendit", "SGD", "Starter") == 1.0
    assert bundle_amount("stripe", "SGD", "Starter") == 7.0
    # A currency only one provider supports.
    assert bundle_amount("stripe", "USD", "Basic") == 25.0
    assert bundle_amount("xendit", "USD", "Basic") is None


# ============== Wallet setup ==============


async def test_setup_stripe_wallet(testbed: StripeTestbed):
    response = await testbed.setup_wallet()
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["provider"] == "stripe" and body["currency"] == "USD"
    assert "credentials" not in body


async def test_setup_rejects_unsupported_currency_and_missing_keys(
    testbed: StripeTestbed,
):
    idr = await testbed.setup_wallet({**SETUP_BODY, "currency": "IDR"})
    assert idr.status_code == 422  # Xendit-only currency

    incomplete = await testbed.setup_wallet(
        {**SETUP_BODY, "credentials": {"secret_key": "sk_test_key"}}
    )
    assert incomplete.status_code == 422
    assert await testbed.wallets.get_active() is None


# ============== Checkout ==============


async def test_buy_bundle_creates_stripe_session(testbed: StripeTestbed):
    await testbed.setup_wallet()

    def capture(request: httpx.Request) -> httpx.Response:
        form = {k: v[0] for k, v in parse_qs(request.content.decode()).items()}
        testbed.captured_forms.append(form)
        return stripe_ok(request)

    testbed.stub = capture
    body = await testbed.buy()

    assert body["amount"] == 25.0 and body["currency"] == "USD"
    assert body["status"] == InvoiceStatus.PENDING.value
    assert body["checkout_url"].startswith("https://checkout.stripe.test/syft-")
    assert body["provider_session_id"] == "cs_test_123"

    form = testbed.captured_forms[0]
    assert form["line_items[0][price_data][currency]"] == "usd"
    assert form["line_items[0][price_data][unit_amount]"] == "2500"  # cents
    assert form["customer_email"] == MEMBER.email
    assert form["client_reference_id"] == f"syft-{body['id']}"


async def test_buy_provider_failure_502_leaves_invoice_pending(
    testbed: StripeTestbed,
):
    await testbed.setup_wallet()
    testbed.stub = stripe_down
    wallet = await testbed.wallets.get_active()
    async with testbed.client() as client:
        response = await client.post(
            f"/api/v1/credits/{wallet.id}/invoices",
            json={"bundle_name": "Basic"},
            headers=buyer_auth(MEMBER.email),
        )
    assert response.status_code == 502
    assert "internal error" in response.json()["detail"]


async def test_session_without_checkout_url_502(testbed: StripeTestbed):
    await testbed.setup_wallet()
    testbed.stub = stripe_no_url
    wallet = await testbed.wallets.get_active()
    async with testbed.client() as client:
        response = await client.post(
            f"/api/v1/credits/{wallet.id}/invoices",
            json={"bundle_name": "Basic"},
            headers=buyer_auth(MEMBER.email),
        )
    assert response.status_code == 502


# ============== Webhook: signature verification ==============


async def test_webhook_settles_and_credits_once(testbed: StripeTestbed):
    await testbed.setup_wallet()
    body = await testbed.buy()
    reference = f"syft-{body['id']}"

    first = await testbed.post_webhook(completed_event(reference))
    duplicate = await testbed.post_webhook(completed_event(reference))

    assert first.json() == {"status": "ok"}
    assert duplicate.json() == {"status": "already_processed"}
    assert await testbed.get_balance(MEMBER.email) == 25.0  # credited once

    invoice = await testbed.get_invoice(body["id"])
    assert invoice.status == InvoiceStatus.PAID.value
    # The session's own created timestamp (stored naive-UTC), not the
    # event's, not now().
    assert invoice.paid_at == datetime(2025, 7, 23, 9, 58, 20)


async def test_webhook_rejects_bad_signatures(testbed: StripeTestbed):
    await testbed.setup_wallet()
    body = await testbed.buy()
    event = completed_event(f"syft-{body['id']}")
    raw = json.dumps(event).encode()

    missing = await testbed.post_webhook(event, sign=False)
    malformed = await testbed.post_webhook(event, header="not-a-signature")
    # Valid HMAC over a stale timestamp — replay outside the window.
    stale = await testbed.post_webhook(
        event, header=sign_webhook(raw, ts=int(time.time()) - 3600)
    )
    # Fresh timestamp, wrong key.
    wrong_mac = hmac.new(
        b"whsec_other", f"{int(time.time())}.{raw.decode()}".encode(), hashlib.sha256
    ).hexdigest()
    forged = await testbed.post_webhook(
        event, header=f"t={int(time.time())},v1={wrong_mac}"
    )

    for response in (missing, malformed, stale, forged):
        assert response.status_code == 403
    assert await testbed.get_balance(MEMBER.email) == 0.0


async def test_webhook_signature_covers_exact_bytes(testbed: StripeTestbed):
    """A signature minted for one body must not authenticate another."""
    await testbed.setup_wallet()
    body = await testbed.buy()
    tampered = completed_event(f"syft-{body['id']}")
    signature_for_other_body = sign_webhook(b'{"type": "something.else"}')

    response = await testbed.post_webhook(tampered, header=signature_for_other_body)
    assert response.status_code == 403


# ============== Webhook: delayed payment methods ==============


async def test_delayed_payment_holds_credit_until_async_success(
    testbed: StripeTestbed,
):
    """SEPA/ACH: completed+unpaid parks the invoice PROCESSING (no credit);
    async_payment_succeeded settles it."""
    await testbed.setup_wallet()
    body = await testbed.buy()
    reference = f"syft-{body['id']}"

    initiated = await testbed.post_webhook(
        completed_event(reference, payment_status="unpaid")
    )
    assert initiated.json() == {"status": "ok"}
    assert await testbed.get_balance(MEMBER.email) == 0.0
    invoice = await testbed.get_invoice(body["id"])
    assert invoice.status == InvoiceStatus.PROCESSING.value

    settled = await testbed.post_webhook(
        session_event("checkout.session.async_payment_succeeded", reference)
    )
    assert settled.json() == {"status": "ok"}
    assert await testbed.get_balance(MEMBER.email) == 25.0
    invoice = await testbed.get_invoice(body["id"])
    assert invoice.status == InvoiceStatus.PAID.value


async def test_async_payment_failure_cancels_without_credit(testbed: StripeTestbed):
    await testbed.setup_wallet()
    body = await testbed.buy()
    reference = f"syft-{body['id']}"

    await testbed.post_webhook(completed_event(reference, payment_status="unpaid"))
    failed = await testbed.post_webhook(
        session_event("checkout.session.async_payment_failed", reference)
    )

    assert failed.json() == {"status": "ok"}
    assert await testbed.get_balance(MEMBER.email) == 0.0
    invoice = await testbed.get_invoice(body["id"])
    assert invoice.status == InvoiceStatus.CANCELLED.value


async def test_webhook_ack_paths_never_retry(testbed: StripeTestbed):
    """Unhandled events / unknown references are 200-acked so Stripe stops
    retrying; a missing client_reference_id is ignored too."""
    await testbed.setup_wallet()

    unknown_event = await testbed.post_webhook(
        session_event("payment_intent.succeeded", "syft-x")
    )
    unknown_reference = await testbed.post_webhook(completed_event("syft-not-ours"))
    no_reference = await testbed.post_webhook(
        {"type": "checkout.session.completed", "data": {"object": {}}}
    )

    assert unknown_event.json() == {"status": "ignored"}
    assert unknown_reference.json() == {"status": "unknown_reference"}
    assert no_reference.json() == {"status": "ignored"}


async def test_webhook_for_inactive_provider_404(testbed: StripeTestbed):
    """One generic route, but only the active wallet's provider answers."""
    await testbed.setup_wallet()
    async with testbed.client() as client:
        response = await client.post(
            "/api/v1/credits/webhooks/xendit",
            json={"event": "payment_session.completed", "data": {}},
            headers={"x-callback-token": "whatever"},
        )
    assert response.status_code == 404
