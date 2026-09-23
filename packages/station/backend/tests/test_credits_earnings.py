"""Earnings aggregates, payout recording, admin reversal, buyer balance.

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
from syft_station.components.credits.repository import (
    CreditsLedger,
    PayoutRepository,
    SpaceCreditTokenRepository,
    WalletRepository,
)
from syft_station.components.credits.routes import build_credits_routes
from syft_station.components.requests.entities import (
    Request,
    RequestStatus,
    RequestType,
)
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

    async def seed_request(
        self,
        *,
        space_id: UUID,
        name: str,
        subdomain: str,
        owner: str = USER,
        deleted: bool = False,
    ) -> None:
        """The create_space request a space was born from — money views
        resolve name/owner here. `deleted` adds the approved delete_space
        request that marks it torn down, so attribution survives deletion."""
        repo = RequestRepository(self.db)
        await repo.create(
            Request(
                type=RequestType.CREATE_SPACE.value,
                status=RequestStatus.APPROVED.value,
                owner_email=owner,
                space_id=space_id,
                space_name=name,
                subdomain=subdomain,
            )
        )
        if deleted:
            await repo.create(
                Request(
                    type=RequestType.DELETE_SPACE.value,
                    status=RequestStatus.APPROVED.value,
                    owner_email=owner,
                    space_id=space_id,
                    space_name=name,
                    subdomain=subdomain,
                )
            )


@pytest_asyncio.fixture
async def testbed(db: AsyncDatabase) -> EarningsTestbed:
    wallets = WalletRepository(db)
    tokens = SpaceCreditTokenRepository(db)
    await wallets.create(
        Wallet(
            provider="xendit",
            currency="PHP",
            credentials={"api_key": "x"},
            hub_user_id=42,
            hub_pat="syft_pat_stub",
        )
    )

    hub = StubHubIdentity()
    app = FastAPI()
    app.include_router(
        build_credits_routes(
            CreditsHandler(db, wallets, tokens),
            WalletAdminHandler(wallets, {}, SpaceRepository(db)),
            CheckoutHandler(db, wallets, {}, hub, SetupRepository(db)),  # type: ignore[arg-type]
            WebhookHandler(db, wallets, {}),
            EarningsHandler(db, wallets, PayoutRepository(db), RequestRepository(db)),
        ),
        prefix="/api/v1",
    )
    await connect_station_identity(db, hub)
    app.dependency_overrides[get_current_user] = lambda: MEMBER
    app.dependency_overrides[require_admin] = lambda: ADMIN
    return EarningsTestbed(db, app)


# ============== Earnings aggregates ==============


async def test_earnings_reconcile_across_spaces_and_days(
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
        # The movements are seeded in the past, so widen the chart window.
        response = await client.get("/api/v1/credits/admin/earnings?days=365")

    assert response.status_code == 200
    body = response.json()
    assert body["currency"] == "PHP"
    assert body["totals"] == {
        "credits_sold": 500.0,
        "earned": 6.0,  # 1 + (2 − 2) + 5
        "paid_out": 0.0,
        "outstanding_balance": 500.0,
    }

    async with testbed.client() as client:
        page = (await client.get("/api/v1/credits/admin/earnings/spaces")).json()
    spaces = {row["space_id"]: row for row in page["items"]}
    assert spaces[str(SPACE_A)]["earned"] == 1.0
    assert spaces[str(SPACE_A)]["query_count"] == 1  # refunded query nets out
    assert spaces[str(SPACE_A)]["payable"] == 1.0
    assert spaces[str(SPACE_B)]["earned"] == 5.0

    # One series across every space: day 1 is A's two debits, day 2 is the
    # reversal netted against B's query.
    daily = {row["day"]: row["earned"] for row in body["daily"]}
    assert daily == {"2026-07-20": 3.0, "2026-07-21": 3.0}


async def test_earnings_empty_station(testbed: EarningsTestbed):
    async with testbed.client() as client:
        body = (await client.get("/api/v1/credits/admin/earnings")).json()
        page = (await client.get("/api/v1/credits/admin/earnings/spaces")).json()
    assert body["totals"]["earned"] == 0.0
    assert body["daily"] == []
    assert page["items"] == [] and page["total"] == 0


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
        page = (await client.get("/api/v1/credits/admin/earnings/spaces")).json()
    row = page["items"][0]
    assert row["paid_out"] == 10.0 and row["payable"] == 0.0
    # The headline is its own aggregate, not a sum over the page.
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
        page = (await client.get("/api/v1/credits/admin/earnings/spaces")).json()
    assert page["items"][0]["earned"] == 0.0  # the space lost the revenue


# ============== Outstanding balances ==============


async def test_outstanding_balances_lists_liability(testbed: EarningsTestbed):
    await testbed.seed_paid_invoice(500.0, user="rich@test.com")
    await testbed.seed_paid_invoice(100.0, user=USER)

    # rich@ bought 500 and spent nothing; USER bought 100 and spent 30.
    await testbed.seed_movement(space_id=SPACE_A, amount=30.0, user=USER)
    async with CreditsLedger(testbed.db) as ledger:
        assert await ledger.balances.atomic_deduct(USER, 30.0)
        await ledger.commit()

    async with testbed.client() as client:
        body = (await client.get("/api/v1/credits/admin/balances")).json()

    assert (body["total"], body["limit"], body["offset"]) == (2, 10, 0)
    assert body["items"][0] == {
        "user_email": "rich@test.com",
        "topped_up": 500.0,
        "spent": 0.0,
        "balance": 500.0,
    }
    assert body["items"][1] == {
        "user_email": USER,
        "topped_up": 100.0,
        "spent": 30.0,
        "balance": 70.0,
    }


# ============== Buyer balance (satellite token) ==============


async def test_buyer_balance_reflects_topups_and_spend(testbed: EarningsTestbed):
    await testbed.seed_paid_invoice(500.0)
    await testbed.seed_movement(space_id=SPACE_A, amount=2.5, endpoint="ask")
    async with CreditsLedger(testbed.db) as ledger:
        assert await ledger.balances.atomic_deduct(USER, 2.5)
        await ledger.commit()

    wallet = await WalletRepository(testbed.db).get_active()
    async with testbed.client() as client:
        body = (
            await client.get(
                f"/api/v1/credits/{wallet.id}/balance", headers=buyer_auth(USER)
            )
        ).json()

    assert body == {
        "wallet_id": str(wallet.id),
        "user_email": USER,
        "balance": 497.5,
        "currency": "PHP",
    }


async def test_buyer_balance_fresh_user_is_zero(testbed: EarningsTestbed):
    wallet = await WalletRepository(testbed.db).get_active()
    async with testbed.client() as client:
        body = (
            await client.get(
                f"/api/v1/credits/{wallet.id}/balance", headers=buyer_auth(USER)
            )
        ).json()
    assert body["balance"] == 0.0 and body["currency"] == "PHP"


# ============== Feeds + member earnings ==============


async def test_top_up_and_payout_feeds_are_their_own_pages(testbed: EarningsTestbed):
    await testbed.seed_paid_invoice(500.0)
    await testbed.seed_movement(space_id=SPACE_A, amount=10.0)
    async with testbed.client() as client:
        await client.post(
            "/api/v1/credits/admin/payouts",
            json={"space_id": str(SPACE_A), "amount": 4.0, "note": "wire #1"},
        )
        top_ups = (await client.get("/api/v1/credits/admin/top-ups")).json()
        payouts = (await client.get("/api/v1/credits/admin/payouts")).json()

    assert top_ups["total"] == 1
    assert top_ups["items"][0]["amount"] == 500.0
    assert top_ups["items"][0]["status"] == "paid"
    assert payouts["total"] == 1
    assert payouts["items"][0]["space_id"] == str(SPACE_A)
    assert payouts["items"][0]["note"] == "wire #1"


async def test_pages_window_their_rows(testbed: EarningsTestbed):
    for i in range(5):
        await testbed.seed_paid_invoice(10.0 + i, user=f"u{i}@test.com")

    async with testbed.client() as client:
        first = (await client.get("/api/v1/credits/admin/top-ups?limit=2")).json()
        second = (
            await client.get("/api/v1/credits/admin/top-ups?limit=2&offset=2")
        ).json()

    # total counts every matching row, not the page.
    assert first["total"] == second["total"] == 5
    assert len(first["items"]) == len(second["items"]) == 2
    assert {i["user_email"] for i in first["items"]}.isdisjoint(
        {i["user_email"] for i in second["items"]}
    )


async def test_member_earnings_mine_scoped_to_owned_spaces(testbed: EarningsTestbed):
    """The member headline is payable — earned minus what was already paid."""
    await testbed.seed_request(space_id=SPACE_A, name="My Lab", subdomain="my-lab")
    await testbed.seed_request(
        space_id=SPACE_B, name="Other", subdomain="other", owner="x@test.com"
    )
    await testbed.seed_movement(space_id=SPACE_A, amount=10.0)
    await testbed.seed_movement(space_id=SPACE_B, amount=99.0)  # not mine

    async with testbed.client() as client:
        await client.post(
            "/api/v1/credits/admin/payouts",
            json={"space_id": str(SPACE_A), "amount": 4.0},
        )
        body = (await client.get("/api/v1/credits/earnings/mine")).json()

    assert body["currency"] == "PHP"
    assert len(body["spaces"]) == 1  # the other member's space is invisible
    mine = body["spaces"][0]
    assert mine["name"] == "My Lab" and mine["subdomain"] == "my-lab"
    assert mine["earned"] == 10.0
    assert mine["paid_out"] == 4.0
    assert mine["payable"] == 6.0
    assert body["total_payable"] == 6.0 and body["total_earned"] == 10.0


async def test_member_earnings_empty_without_activity(testbed: EarningsTestbed):
    await testbed.seed_request(space_id=uuid4(), name="Quiet", subdomain="quiet")
    async with testbed.client() as client:
        body = (await client.get("/api/v1/credits/earnings/mine")).json()
    assert body["spaces"] == [] and body["total_payable"] == 0.0


# ============== Attribution survives deletion ==============


async def test_admin_earnings_attribute_live_spaces(testbed: EarningsTestbed):
    await testbed.seed_request(space_id=SPACE_A, name="Webbing", subdomain="webbing")
    await testbed.seed_movement(space_id=SPACE_A, amount=15.0)

    async with testbed.client() as client:
        body = (await client.get("/api/v1/credits/admin/earnings/spaces")).json()

    row = body["items"][0]
    assert row["name"] == "Webbing"
    assert row["owner_email"] == USER
    assert row["deleted"] is False


async def test_deleted_space_keeps_name_owner_and_flag(testbed: EarningsTestbed):
    await testbed.seed_request(
        space_id=SPACE_A,
        name="Webbing",
        subdomain="webbing",
        deleted=True,
    )
    await testbed.seed_movement(space_id=SPACE_A, amount=15.0)

    async with testbed.client() as client:
        body = (await client.get("/api/v1/credits/admin/earnings/spaces")).json()

    row = body["items"][0]
    assert row["name"] == "Webbing"
    assert row["subdomain"] == "webbing"
    assert row["owner_email"] == USER
    assert row["deleted"] is True
    assert row["payable"] == 15.0


async def test_member_mine_keeps_deleted_space_money(testbed: EarningsTestbed):
    """The member must keep seeing what they're owed after a teardown."""
    await testbed.seed_request(
        space_id=SPACE_A,
        name="Webbing",
        subdomain="webbing",
        deleted=True,
    )
    await testbed.seed_movement(space_id=SPACE_A, amount=15.0)

    async with testbed.client() as client:
        body = (await client.get("/api/v1/credits/earnings/mine")).json()

    assert len(body["spaces"]) == 1
    mine = body["spaces"][0]
    assert mine["name"] == "Webbing" and mine["deleted"] is True
    assert body["total_payable"] == 15.0


async def test_earnings_without_request_row_degrade_to_id_stub(
    testbed: EarningsTestbed,
):
    # Should never happen (every space is born from a request) — the money
    # must still show rather than hide behind a join miss.
    await testbed.seed_movement(space_id=SPACE_A, amount=5.0)

    async with testbed.client() as client:
        body = (await client.get("/api/v1/credits/admin/earnings/spaces")).json()

    row = body["items"][0]
    assert row["name"] == str(SPACE_A)[:8]
    assert row["deleted"] is True
