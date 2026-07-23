"""Space-facing credits API — the pinned contract, tested on the wire (C3.2).

Exercised over ASGI (not handler calls) because the consumer is a machine:
syft-space's ClusterCreditsClient parses these exact shapes — top-level 402
body, {"balance": …} reads, 200-on-replay semantics. Status codes and field
names here are frozen by that client.
"""

from __future__ import annotations

from uuid import uuid4

import httpx
import pytest_asyncio
from fastapi import FastAPI

from syft_station.components.credits.entities import (
    EntryType,
    SpaceCreditToken,
    Wallet,
)
from syft_station.components.credits.handlers import CreditsHandler
from syft_station.components.credits.repository import (
    CreditsLedger,
    SpaceCreditTokenRepository,
    WalletRepository,
)
from syft_station.components.credits.routes import build_credits_routes
from syft_station.components.credits.tokens import (
    generate_credit_token,
    hash_credit_token,
)
from syft_station.components.shared.database import AsyncDatabase

USER = "enduser@test.com"
SPACE_A = uuid4()
SPACE_B = uuid4()


def _debit_payload(transaction_id=None, amount=0.05, user=USER) -> dict:
    return {
        "transaction_id": str(transaction_id or uuid4()),
        "user_email": user,
        "amount": amount,
        "endpoint": "ask",
        "charge_unit": "per_query",
        "charge_quantity": 1,
    }


class CreditsTestbed:
    """One station app + two space tokens + direct DB access for seeding."""

    def __init__(self, db: AsyncDatabase, app: FastAPI, token_a: str, token_b: str):
        self.db = db
        self.app = app
        self.token_a = token_a
        self.token_b = token_b

    def client(self, token: str | None) -> httpx.AsyncClient:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        return httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app),
            base_url="http://station.test",
            headers=headers,
        )

    async def seed_balance(self, email: str, amount: float) -> None:
        async with CreditsLedger(self.db) as ledger:
            await ledger.balances.upsert_credit(email, amount)
            await ledger.commit()

    async def get_balance(self, email: str) -> float:
        async with CreditsLedger(self.db) as ledger:
            row = await ledger.balances.get(email)
            return row.balance if row else 0.0


@pytest_asyncio.fixture
async def testbed(db: AsyncDatabase) -> CreditsTestbed:
    wallets = WalletRepository(db)
    tokens = SpaceCreditTokenRepository(db)
    wallet = await wallets.create(
        Wallet(provider="xendit", currency="PHP", credentials={"api_key": "x"})
    )

    token_a, token_b = generate_credit_token(), generate_credit_token()
    for space_id, plaintext in ((SPACE_A, token_a), (SPACE_B, token_b)):
        await tokens.create(
            SpaceCreditToken(
                space_id=space_id,
                wallet_id=wallet.id,
                token_hash=hash_credit_token(plaintext),
            )
        )

    app = FastAPI()
    handler = CreditsHandler(db, wallets, tokens)
    app.include_router(build_credits_routes(handler), prefix="/api/v1")
    return CreditsTestbed(db, app, token_a, token_b)


# ============== Auth ==============


async def test_missing_and_malformed_auth_401(testbed: CreditsTestbed):
    async with testbed.client(None) as client:
        response = await client.get(
            "/api/v1/credits/balance", params={"user_email": USER}
        )
        assert response.status_code == 401

    async with testbed.client("sct_not_a_real_token") as client:
        response = await client.post("/api/v1/credits/debit", json=_debit_payload())
        assert response.status_code == 401


async def test_revoked_token_401(testbed: CreditsTestbed):
    await SpaceCreditTokenRepository(testbed.db).revoke_for_space(SPACE_A)
    async with testbed.client(testbed.token_a) as client:
        response = await client.post("/api/v1/credits/debit", json=_debit_payload())
        assert response.status_code == 401


async def test_token_bound_to_deleted_wallet_401(testbed: CreditsTestbed):
    wallets = WalletRepository(testbed.db)
    wallet = await wallets.get_active()
    await wallets.delete(wallet.id)
    async with testbed.client(testbed.token_a) as client:
        response = await client.get(
            "/api/v1/credits/balance", params={"user_email": USER}
        )
        assert response.status_code == 401


# ============== Debit ==============


async def test_debit_200_shape_and_movement(testbed: CreditsTestbed):
    await testbed.seed_balance(USER, 1.0)
    tx = uuid4()

    async with testbed.client(testbed.token_a) as client:
        response = await client.post(
            "/api/v1/credits/debit", json=_debit_payload(tx, amount=0.05)
        )

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "transaction_id": str(tx),
        "balance_after": 0.95,
        "currency": "PHP",
    }
    assert await testbed.get_balance(USER) == 0.95

    # The ledger row carries the caller's attribution.
    async with CreditsLedger(testbed.db) as ledger:
        entry = await ledger.entries.get(tx, EntryType.DEBIT.value)
        assert entry is not None
        assert entry.space_id == SPACE_A
        assert entry.endpoint == "ask"
        assert entry.currency == "PHP"


async def test_debit_replay_never_debits_twice(testbed: CreditsTestbed):
    await testbed.seed_balance(USER, 1.0)
    payload = _debit_payload(uuid4(), amount=0.25)

    async with testbed.client(testbed.token_a) as client:
        first = await client.post("/api/v1/credits/debit", json=payload)
        replay = await client.post("/api/v1/credits/debit", json=payload)

    assert first.status_code == 200 and replay.status_code == 200
    assert replay.json()["transaction_id"] == payload["transaction_id"]
    assert await testbed.get_balance(USER) == 0.75  # moved exactly once


async def test_debit_402_top_level_body(testbed: CreditsTestbed):
    await testbed.seed_balance(USER, 0.01)
    tx = uuid4()

    async with testbed.client(testbed.token_a) as client:
        response = await client.post(
            "/api/v1/credits/debit", json=_debit_payload(tx, amount=0.05)
        )

    assert response.status_code == 402
    # Top-level shape — ClusterCreditsClient reads .json()["balance"] directly.
    assert response.json() == {
        "error": "insufficient_balance",
        "balance": 0.01,
        "required": 0.05,
    }
    assert await testbed.get_balance(USER) == 0.01
    async with CreditsLedger(testbed.db) as ledger:
        assert await ledger.entries.get(tx, EntryType.DEBIT.value) is None


async def test_debit_unknown_user_402_zero_balance(testbed: CreditsTestbed):
    async with testbed.client(testbed.token_a) as client:
        response = await client.post(
            "/api/v1/credits/debit", json=_debit_payload(user="nobody@test.com")
        )
    assert response.status_code == 402
    assert response.json()["balance"] == 0.0


async def test_debit_replay_of_another_spaces_transaction_403(
    testbed: CreditsTestbed,
):
    await testbed.seed_balance(USER, 1.0)
    payload = _debit_payload(uuid4())

    async with testbed.client(testbed.token_a) as client:
        assert (
            await client.post("/api/v1/credits/debit", json=payload)
        ).status_code == 200
    async with testbed.client(testbed.token_b) as client:
        response = await client.post("/api/v1/credits/debit", json=payload)

    assert response.status_code == 403
    assert await testbed.get_balance(USER) == 0.95


async def test_debit_rejects_non_positive_amount(testbed: CreditsTestbed):
    async with testbed.client(testbed.token_a) as client:
        response = await client.post(
            "/api/v1/credits/debit", json=_debit_payload(amount=0)
        )
    assert response.status_code == 422


# ============== Refund ==============


async def test_refund_restores_and_is_idempotent(testbed: CreditsTestbed):
    await testbed.seed_balance(USER, 1.0)
    tx = uuid4()

    async with testbed.client(testbed.token_a) as client:
        await client.post("/api/v1/credits/debit", json=_debit_payload(tx, amount=0.4))
        first = await client.post(
            "/api/v1/credits/refund", json={"transaction_id": str(tx)}
        )
        second = await client.post(
            "/api/v1/credits/refund", json={"transaction_id": str(tx)}
        )

    assert first.status_code == 200 and first.json() == {"refunded": True}
    assert second.status_code == 200  # idempotent — same outcome
    assert await testbed.get_balance(USER) == 1.0  # restored exactly once

    # The CANCELLED row copies the debit's attribution.
    async with CreditsLedger(testbed.db) as ledger:
        cancel = await ledger.entries.get(tx, EntryType.CANCELLED.value)
        assert cancel is not None
        assert cancel.space_id == SPACE_A
        assert cancel.amount == 0.4


async def test_refund_unknown_transaction_404(testbed: CreditsTestbed):
    async with testbed.client(testbed.token_a) as client:
        response = await client.post(
            "/api/v1/credits/refund", json={"transaction_id": str(uuid4())}
        )
    assert response.status_code == 404


async def test_refund_of_another_spaces_debit_403(testbed: CreditsTestbed):
    await testbed.seed_balance(USER, 1.0)
    tx = uuid4()

    async with testbed.client(testbed.token_a) as client:
        await client.post("/api/v1/credits/debit", json=_debit_payload(tx))
    async with testbed.client(testbed.token_b) as client:
        response = await client.post(
            "/api/v1/credits/refund", json={"transaction_id": str(tx)}
        )

    assert response.status_code == 403
    assert await testbed.get_balance(USER) == 0.95  # nothing restored


# ============== Balance ==============


async def test_balance_200(testbed: CreditsTestbed):
    await testbed.seed_balance(USER, 12.4)
    async with testbed.client(testbed.token_a) as client:
        response = await client.get(
            "/api/v1/credits/balance", params={"user_email": USER}
        )
    assert response.status_code == 200
    assert response.json() == {"balance": 12.4, "currency": "PHP"}


async def test_balance_unknown_user_is_zero(testbed: CreditsTestbed):
    async with testbed.client(testbed.token_a) as client:
        response = await client.get(
            "/api/v1/credits/balance", params={"user_email": "nobody@test.com"}
        )
    assert response.status_code == 200
    assert response.json()["balance"] == 0.0
