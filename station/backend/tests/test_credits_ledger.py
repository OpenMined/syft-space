"""Credits ledger core — atomicity, idempotency, and token tests (step C3.1).

These exercise the repository primitives composed exactly the way the
credits handlers will compose them in C3.2/C3.4:

    debit  = atomic_deduct + insert DEBIT      (one transaction)
    refund = insert CANCELLED + atomic_restore (one transaction)
    settle = mark_paid + upsert_credit         (one transaction)

The money-safety properties under test:
- concurrent debits can never overdraw a balance
- a replayed debit / double refund hits UNIQUE(transaction_id, type) and
  rolls back whole — balance untouched
- duplicate webhook settlement is a no-op (status-guarded mark_paid)
"""

from __future__ import annotations

import asyncio
from uuid import UUID, uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from syft_station.components.credits.entities import (
    EntryType,
    Invoice,
    InvoiceStatus,
    LedgerEntry,
    Wallet,
)
from syft_station.components.credits.repository import (
    CreditsLedger,
    SpaceCreditTokenRepository,
    WalletRepository,
)
from syft_station.components.credits.tokens import (
    CREDIT_TOKEN_PREFIX,
    generate_credit_token,
    hash_credit_token,
)
from syft_station.components.shared.database import AsyncDatabase

USER = "buyer@test.com"
SPACE_ID = uuid4()


# ============== Helpers: the composed money operations ==============


async def seed_balance(db: AsyncDatabase, email: str, amount: float) -> None:
    async with CreditsLedger(db) as ledger:
        await ledger.balances.upsert_credit(email, amount)
        await ledger.commit()


async def get_balance(db: AsyncDatabase, email: str) -> float:
    async with CreditsLedger(db) as ledger:
        row = await ledger.balances.get(email)
        return row.balance if row else 0.0


async def debit(
    db: AsyncDatabase, email: str, amount: float, transaction_id: UUID
) -> bool:
    """The C3.2 debit shape: conditional deduct + DEBIT row, one transaction."""
    async with CreditsLedger(db) as ledger:
        ok = await ledger.balances.atomic_deduct(email, amount)
        if not ok:
            return False
        ledger.entries.insert(
            LedgerEntry(
                user_email=email,
                transaction_id=transaction_id,
                type=EntryType.DEBIT.value,
                space_id=SPACE_ID,
                endpoint="ask",
                amount=amount,
                currency="USD",
                charge_unit="per_query",
                charge_quantity=1,
            )
        )
        await ledger.commit()
        return True


async def refund(db: AsyncDatabase, email: str, amount: float, transaction_id: UUID):
    """The C3.2 refund shape: CANCELLED row + restore, one transaction."""
    async with CreditsLedger(db) as ledger:
        ledger.entries.insert(
            LedgerEntry(
                user_email=email,
                transaction_id=transaction_id,
                type=EntryType.CANCELLED.value,
                space_id=SPACE_ID,
                endpoint="ask",
                amount=amount,
                currency="USD",
                charge_unit="per_query",
                charge_quantity=1,
            )
        )
        await ledger.balances.atomic_restore(email, amount)
        await ledger.commit()


# ============== Balances ==============


async def test_upsert_credit_and_deduct(db: AsyncDatabase):
    await seed_balance(db, USER, 10.0)
    await seed_balance(db, USER, 2.5)  # second upsert adds to the same row
    assert await get_balance(db, USER) == 12.5

    async with CreditsLedger(db) as ledger:
        assert await ledger.balances.atomic_deduct(USER, 4.5) is True
        await ledger.commit()
    assert await get_balance(db, USER) == 8.0


async def test_deduct_insufficient_balance(db: AsyncDatabase):
    await seed_balance(db, USER, 1.0)
    async with CreditsLedger(db) as ledger:
        assert await ledger.balances.atomic_deduct(USER, 1.01) is False
        await ledger.commit()
    assert await get_balance(db, USER) == 1.0


async def test_deduct_unknown_user(db: AsyncDatabase):
    async with CreditsLedger(db) as ledger:
        assert await ledger.balances.atomic_deduct("nobody@test.com", 0.01) is False


async def test_concurrent_debits_never_overdraw(db: AsyncDatabase):
    """N racing debits against a balance that can afford only K ⇒ exactly
    K succeed. The conditional UPDATE is the whole concurrency story."""
    await seed_balance(db, USER, 5.0)

    results = await asyncio.gather(*(debit(db, USER, 1.0, uuid4()) for _ in range(10)))

    assert sum(results) == 5
    assert await get_balance(db, USER) == 0.0


# ============== Debit / refund idempotency ==============


async def test_replayed_debit_rolls_back_whole(db: AsyncDatabase):
    """Same transaction_id twice: the deduct inside the replay succeeds,
    but the DEBIT insert violates the unique constraint — the transaction
    rolls back and the balance must be untouched by the replay."""
    await seed_balance(db, USER, 10.0)
    tx = uuid4()
    assert await debit(db, USER, 3.0, tx) is True
    assert await get_balance(db, USER) == 7.0

    with pytest.raises(IntegrityError):
        await debit(db, USER, 3.0, tx)
    assert await get_balance(db, USER) == 7.0


async def test_double_refund_rolls_back_whole(db: AsyncDatabase):
    await seed_balance(db, USER, 10.0)
    tx = uuid4()
    assert await debit(db, USER, 3.0, tx) is True

    await refund(db, USER, 3.0, tx)
    assert await get_balance(db, USER) == 10.0

    with pytest.raises(IntegrityError):
        await refund(db, USER, 3.0, tx)
    assert await get_balance(db, USER) == 10.0  # restore rolled back too


async def test_ledger_entry_lookup(db: AsyncDatabase):
    await seed_balance(db, USER, 5.0)
    tx = uuid4()
    await debit(db, USER, 2.0, tx)

    async with CreditsLedger(db) as ledger:
        found = await ledger.entries.get(tx, EntryType.DEBIT.value)
        assert found is not None
        assert found.space_id == SPACE_ID
        assert found.endpoint == "ask"
        assert await ledger.entries.get(tx, EntryType.CANCELLED.value) is None


# ============== Invoice settlement ==============


def _invoice() -> Invoice:
    invoice_id = uuid4()
    return Invoice(
        id=invoice_id,
        user_email=USER,
        provider="xendit",
        client_reference=f"syft-{invoice_id}",
        bundle_name="starter",
        amount=25.0,
        currency="USD",
    )


async def test_mark_paid_credits_once(db: AsyncDatabase):
    """The C3.4 settle shape: duplicate webhook ⇒ mark_paid returns False
    and the caller never credits a second time."""
    invoice = _invoice()
    invoice_id, amount = invoice.id, invoice.amount  # before commit expires them
    async with CreditsLedger(db) as ledger:
        ledger.invoices.insert(invoice)
        await ledger.commit()

    for expected, attempt in ((True, "first"), (False, "duplicate")):
        async with CreditsLedger(db) as ledger:
            settled = await ledger.invoices.mark_paid(invoice_id, {"event": attempt})
            if settled:
                await ledger.balances.upsert_credit(USER, amount)
            await ledger.commit()
            assert settled is expected

    assert await get_balance(db, USER) == 25.0
    async with CreditsLedger(db) as ledger:
        row = await ledger.invoices.get(invoice_id)
        assert row.status == InvoiceStatus.PAID.value
        assert row.webhook_payload == {"event": "first"}  # duplicate never wrote
        assert row.paid_at is not None


async def test_late_event_cannot_reopen_paid_invoice(db: AsyncDatabase):
    invoice = _invoice()
    invoice_id = invoice.id
    async with CreditsLedger(db) as ledger:
        ledger.invoices.insert(invoice)
        await ledger.commit()
        assert await ledger.invoices.mark_paid(invoice_id, {}) is True
        await ledger.commit()

    async with CreditsLedger(db) as ledger:
        assert (
            await ledger.invoices.update_status(invoice_id, InvoiceStatus.EXPIRED.value)
            is False
        )
        row = await ledger.invoices.get(invoice_id)
        assert row.status == InvoiceStatus.PAID.value


async def test_checkout_metadata_only_while_pending(db: AsyncDatabase):
    invoice = _invoice()
    invoice_id, client_reference = invoice.id, invoice.client_reference
    async with CreditsLedger(db) as ledger:
        ledger.invoices.insert(invoice)
        await ledger.commit()
        assert (
            await ledger.invoices.set_checkout_metadata(
                invoice_id, "https://pay.example/x", "sess_1"
            )
            is True
        )
        await ledger.commit()
        assert await ledger.invoices.mark_paid(invoice_id, {}) is True
        await ledger.commit()
        # settled invoices are immutable
        assert (
            await ledger.invoices.set_checkout_metadata(
                invoice_id, "https://pay.example/y", "sess_2"
            )
            is False
        )

    async with CreditsLedger(db) as ledger:
        found = await ledger.invoices.get_by_client_reference(client_reference)
        assert found is not None
        assert found.checkout_url == "https://pay.example/x"


# ============== Tokens ==============


async def test_token_mint_and_verify(db: AsyncDatabase):
    repo = SpaceCreditTokenRepository(db)
    wallet_id = uuid4()
    space_id = uuid4()

    plaintext = generate_credit_token()
    assert plaintext.startswith(CREDIT_TOKEN_PREFIX)
    assert hash_credit_token(plaintext) == hash_credit_token(plaintext)

    from syft_station.components.credits.entities import SpaceCreditToken

    await repo.create(
        SpaceCreditToken(
            space_id=space_id,
            wallet_id=wallet_id,
            token_hash=hash_credit_token(plaintext),
        )
    )

    found = await repo.get_active_by_hash(hash_credit_token(plaintext))
    assert found is not None
    assert found.space_id == space_id
    assert found.wallet_id == wallet_id
    assert await repo.get_active_by_hash(hash_credit_token("sct_wrong")) is None

    binding = await repo.get_active_for_space(space_id)
    assert binding is not None and binding.id == found.id


async def test_token_revoke(db: AsyncDatabase):
    repo = SpaceCreditTokenRepository(db)
    space_id = uuid4()
    plaintext = generate_credit_token()

    from syft_station.components.credits.entities import SpaceCreditToken

    await repo.create(
        SpaceCreditToken(
            space_id=space_id,
            wallet_id=uuid4(),
            token_hash=hash_credit_token(plaintext),
        )
    )

    assert await repo.revoke_for_space(space_id) == 1
    assert await repo.get_active_by_hash(hash_credit_token(plaintext)) is None
    assert await repo.get_active_for_space(space_id) is None
    # revoking again touches nothing
    assert await repo.revoke_for_space(space_id) == 0


# ============== Wallet ==============


async def test_wallet_create_and_get_active(db: AsyncDatabase):
    repo = WalletRepository(db)
    assert await repo.get_active() is None

    wallet = await repo.create(
        Wallet(
            provider="xendit",
            currency="PHP",
            credentials={"api_key": "xnd_test", "callback_token": "cb_test"},
        )
    )

    active = await repo.get_active()
    assert active is not None
    assert active.id == wallet.id
    assert active.provider == "xendit"
    assert active.currency == "PHP"
    assert active.credentials["api_key"] == "xnd_test"
