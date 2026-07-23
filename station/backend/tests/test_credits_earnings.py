"""Earnings aggregates, payout recording, admin reversal, and /credits/me.

Every admin figure is derived from the ledger, so these tests seed raw
movements (debits, reversals, settled invoices) and assert the derived
numbers reconcile: earned = DEBIT − CANCELLED per space, payable = earned
− payouts, and reversals refund the user while shrinking the space's
earnings.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import httpx
import pytest_asyncio
from fastapi import FastAPI

from syft_station.components.auth.session import get_current_user, require_admin
from syft_station.components.credits.entities import (
    EntryType,
    Invoice,
    LedgerEntry,
    Wallet,
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
from syft_station.components.provision.mock import MockProvisioner
from syft_station.components.shared.database import AsyncDatabase
from syft_station.components.spaces.repository import SpaceRepository
from tests.conftest import ADMIN, MEMBER

SPACE_A = uuid4()
SPACE_B = uuid4()
USER = MEMBER.email


class EarningsTestbed:
    def __init__(self, db: AsyncDatabase, app: FastAPI):
        self.db = db
        self.app = app

    def client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app),
            base_url="http://station.test",
        )

    async def seed_movement(
        self,
        *,
        space_id: UUID,
        amount: float,
        endpoint: str = "ask",
        type_: str = EntryType.DEBIT.value,
        transaction_id: UUID | None = None,
        user: str = USER,
        created_at: datetime | None = None,
    ) -> UUID:
        transaction_id = transaction_id or uuid4()
        entry = LedgerEntry(
            user_email=user,
            transaction_id=transaction_id,
            type=type_,
            space_id=space_id,
            endpoint=endpoint,
            amount=amount,
            currency="PHP",
            charge_unit="per_query",
            charge_quantity=1,
        )
        if created_at is not None:
            entry.created_at = created_at
        async with CreditsLedger(self.db) as ledger:
            ledger.entries.insert(entry)
            await ledger.commit()
        return transaction_id

    async def seed_paid_invoice(self, amount: float, user: str = USER) -> None:
        invoice_id = uuid4()
        async with CreditsLedger(self.db) as ledger:
            ledger.invoices.insert(
                Invoice(
                    id=invoice_id,
                    user_email=user,
                    provider="xendit",
                    client_reference=f"syft-{invoice_id}",
                    bundle_name="Basic",
                    amount=amount,
                    currency="PHP",
                )
            )
            await ledger.commit()
            assert await ledger.invoices.mark_paid(invoice_id, {})
            await ledger.balances.upsert_credit(user, amount)
            await ledger.commit()

    async def get_balance(self, email: str) -> float:
        async with CreditsLedger(self.db) as ledger:
            row = await ledger.balances.get(email)
            return row.balance if row else 0.0


@pytest_asyncio.fixture
async def testbed(db: AsyncDatabase) -> EarningsTestbed:
    wallets = WalletRepository(db)
    tokens = SpaceCreditTokenRepository(db)
    await wallets.create(
        Wallet(provider="xendit", currency="PHP", credentials={"api_key": "x"})
    )

    rollout = WalletRollout(
        SpaceRepository(db),
        MockProvisioner(),
        SpaceCreditsService(wallets, tokens, "http://station.test"),
    )
    app = FastAPI()
    app.include_router(
        build_credits_routes(
            CreditsHandler(db, wallets, tokens),
            WalletAdminHandler(wallets, {}, rollout),
            CheckoutHandler(db, wallets, {}),
            WebhookHandler(db, wallets, {}),
            EarningsHandler(db, wallets, PayoutRepository(db)),
        ),
        prefix="/api/v1",
    )
    app.dependency_overrides[get_current_user] = lambda: MEMBER
    app.dependency_overrides[require_admin] = lambda: ADMIN
    return EarningsTestbed(db, app)


# ============== Earnings aggregates ==============


async def test_earnings_reconcile_across_spaces_endpoints_and_days(
    testbed: EarningsTestbed,
):
    await testbed.seed_paid_invoice(500.0)

    # Space A: two paid queries on different endpoints and days, one of
    # which is refunded — its money must vanish from every aggregate.
    day1 = datetime(2026, 7, 20, 10, 0, tzinfo=UTC)
    day2 = datetime(2026, 7, 21, 10, 0, tzinfo=UTC)
    await testbed.seed_movement(
        space_id=SPACE_A, amount=1.0, endpoint="ask", created_at=day1
    )
    refunded = await testbed.seed_movement(
        space_id=SPACE_A, amount=2.0, endpoint="search", created_at=day1
    )
    await testbed.seed_movement(
        space_id=SPACE_A,
        amount=2.0,
        endpoint="search",
        type_=EntryType.CANCELLED.value,
        transaction_id=refunded,
        created_at=day2,
    )
    # Space B: one paid query.
    await testbed.seed_movement(
        space_id=SPACE_B, amount=5.0, endpoint="ask", created_at=day2
    )

    async with testbed.client() as client:
        response = await client.get("/api/v1/credits/admin/earnings")

    assert response.status_code == 200
    body = response.json()
    assert body["currency"] == "PHP"
    assert body["totals"] == {
        "credits_sold": 500.0,
        "earned": 6.0,  # 1 + (2 − 2) + 5
        "paid_out": 0.0,
        "outstanding_balance": 500.0,
    }

    spaces = {row["space_id"]: row for row in body["spaces"]}
    assert spaces[str(SPACE_A)]["earned"] == 1.0
    assert spaces[str(SPACE_A)]["query_count"] == 1  # refunded query nets out
    assert spaces[str(SPACE_A)]["payable"] == 1.0
    assert spaces[str(SPACE_B)]["earned"] == 5.0

    endpoints = {(row["space_id"], row["endpoint"]): row for row in body["endpoints"]}
    assert endpoints[(str(SPACE_A), "ask")]["earned"] == 1.0
    assert endpoints[(str(SPACE_A), "search")]["earned"] == 0.0  # fully refunded
    assert endpoints[(str(SPACE_B), "ask")]["earned"] == 5.0

    daily = {(row["day"], row["space_id"]): row["earned"] for row in body["daily"]}
    assert daily[("2026-07-20", str(SPACE_A))] == 3.0  # both debits
    assert daily[("2026-07-21", str(SPACE_A))] == -2.0  # the reversal day
    assert daily[("2026-07-21", str(SPACE_B))] == 5.0


async def test_earnings_empty_station(testbed: EarningsTestbed):
    async with testbed.client() as client:
        body = (await client.get("/api/v1/credits/admin/earnings")).json()
    assert body["totals"]["earned"] == 0.0
    assert body["spaces"] == [] and body["daily"] == []


# ============== Payouts ==============


async def test_payout_capped_at_payable(testbed: EarningsTestbed):
    await testbed.seed_movement(space_id=SPACE_A, amount=10.0)

    async with testbed.client() as client:
        too_much = await client.post(
            "/api/v1/credits/admin/payouts",
            json={"space_id": str(SPACE_A), "amount": 10.01},
        )
        first = await client.post(
            "/api/v1/credits/admin/payouts",
            json={"space_id": str(SPACE_A), "amount": 6.0, "note": "wire #1"},
        )
        second_too_much = await client.post(
            "/api/v1/credits/admin/payouts",
            json={"space_id": str(SPACE_A), "amount": 5.0},
        )
        rest = await client.post(
            "/api/v1/credits/admin/payouts",
            json={"space_id": str(SPACE_A), "amount": 4.0},
        )

    assert too_much.status_code == 422
    assert first.status_code == 200
    assert first.json()["payable_after"] == 4.0
    assert second_too_much.status_code == 422  # only 4 left
    assert rest.status_code == 200
    assert rest.json()["payable_after"] == 0.0

    async with testbed.client() as client:
        earnings = (await client.get("/api/v1/credits/admin/earnings")).json()
    row = earnings["spaces"][0]
    assert row["paid_out"] == 10.0 and row["payable"] == 0.0
    assert earnings["totals"]["paid_out"] == 10.0


async def test_payout_for_space_with_no_earnings_422(testbed: EarningsTestbed):
    async with testbed.client() as client:
        response = await client.post(
            "/api/v1/credits/admin/payouts",
            json={"space_id": str(uuid4()), "amount": 1.0},
        )
    assert response.status_code == 422


# ============== Admin reversal ==============


async def test_reversal_refunds_user_and_shrinks_earnings(testbed: EarningsTestbed):
    await testbed.seed_paid_invoice(100.0)
    tx = await testbed.seed_movement(space_id=SPACE_A, amount=30.0)
    # seed_movement writes the ledger row only; mirror the balance deduct.
    async with CreditsLedger(testbed.db) as ledger:
        assert await ledger.balances.atomic_deduct(USER, 30.0)
        await ledger.commit()
    assert await testbed.get_balance(USER) == 70.0

    async with testbed.client() as client:
        first = await client.post(f"/api/v1/credits/admin/debits/{tx}/reverse")
        again = await client.post(f"/api/v1/credits/admin/debits/{tx}/reverse")
        unknown = await client.post(f"/api/v1/credits/admin/debits/{uuid4()}/reverse")

    assert first.status_code == 200 and first.json() == {"reversed": True}
    assert again.status_code == 200  # idempotent — restored exactly once
    assert unknown.status_code == 404
    assert await testbed.get_balance(USER) == 100.0

    async with testbed.client() as client:
        earnings = (await client.get("/api/v1/credits/admin/earnings")).json()
    assert earnings["spaces"][0]["earned"] == 0.0  # the space lost the revenue


# ============== Outstanding balances ==============


async def test_outstanding_balances_lists_liability(testbed: EarningsTestbed):
    await testbed.seed_paid_invoice(500.0, user="rich@test.com")
    await testbed.seed_paid_invoice(100.0, user=USER)

    async with testbed.client() as client:
        body = (await client.get("/api/v1/credits/admin/balances")).json()

    assert body["total"] == 600.0
    assert body["balances"][0] == {"user_email": "rich@test.com", "balance": 500.0}


# ============== Buyer /me ==============


async def test_my_credits_shows_balance_topups_and_spend(testbed: EarningsTestbed):
    await testbed.seed_paid_invoice(500.0)
    tx = await testbed.seed_movement(space_id=SPACE_A, amount=2.5, endpoint="ask")
    async with CreditsLedger(testbed.db) as ledger:
        assert await ledger.balances.atomic_deduct(USER, 2.5)
        await ledger.commit()

    async with testbed.client() as client:
        body = (await client.get("/api/v1/credits/me")).json()

    assert body["balance"] == 497.5
    assert body["currency"] == "PHP"
    assert len(body["top_ups"]) == 1
    assert body["top_ups"][0]["status"] == "paid"
    assert body["top_ups"][0]["amount"] == 500.0
    assert len(body["spend"]) == 1
    assert body["spend"][0]["transaction_id"] == str(tx)
    assert body["spend"][0]["endpoint"] == "ask"


async def test_my_credits_fresh_user_is_empty(testbed: EarningsTestbed):
    async with testbed.client() as client:
        body = (await client.get("/api/v1/credits/me")).json()
    assert body == {"balance": 0.0, "currency": "PHP", "top_ups": [], "spend": []}
