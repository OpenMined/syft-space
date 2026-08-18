"""Charger for the managed cluster wallet.

Implements the PrepaidBalanceCharger Protocol — the same shape policies
already use for xendit/stripe — but the authoritative balance lives at
the cluster's credits service. After every confirmed remote call the
charger journals a record-only LedgerEntry locally (spend history +
payout cross-check); the journal is never read for money decisions.
"""

import logging
from uuid import UUID, uuid4

from syft_space.components.payments.cluster.credits_client import (
    ClusterCreditsClient,
    InsufficientCreditsError,
)
from syft_space.components.payments.gateway.balance_service import BalanceService
from syft_space.components.policy_types.interfaces import BalanceShortfallError

logger = logging.getLogger(__name__)


class ClusterCreditsCharger:
    """Per-request charger bound to one cluster wallet and endpoint."""

    def __init__(
        self,
        *,
        client: ClusterCreditsClient,
        balance_service: BalanceService,
        wallet_id: UUID,
        currency: str,
        tenant_id: UUID,
        endpoint_id: UUID,
        endpoint_slug: str,
    ) -> None:
        self._client = client
        self._balance_service = balance_service
        self._wallet_id = wallet_id
        self._currency = currency
        self._tenant_id = tenant_id
        self._endpoint_id = endpoint_id
        self._endpoint_slug = endpoint_slug

    @property
    def currency(self) -> str:
        return self._currency

    @property
    def wallet_type(self) -> str:
        return "cluster"

    async def get_balance(self, user_email: str) -> float:
        return await self._client.get_balance(user_email)

    async def reserve(
        self,
        *,
        user_email: str,
        amount: float,
        charge_unit: str,
        charge_quantity: int,
    ) -> UUID:
        transaction_id = uuid4()
        try:
            await self._client.debit(
                transaction_id=transaction_id,
                user_email=user_email,
                amount=amount,
                endpoint=self._endpoint_slug,
                charge_unit=charge_unit,
                charge_quantity=charge_quantity,
            )
        except InsufficientCreditsError as exc:
            raise BalanceShortfallError(
                balance=exc.balance, required=amount, currency=self._currency
            ) from exc

        # Journal after the confirmed debit. A journal failure must not
        # fail the query — the money already moved; the cluster ledger
        # stays authoritative and reconcilable by transaction_id.
        try:
            await self._balance_service.record_external_debit(
                wallet_id=self._wallet_id,
                tenant_id=self._tenant_id,
                user_email=user_email,
                endpoint_id=self._endpoint_id,
                transaction_id=transaction_id,
                amount=amount,
                currency=self._currency,
                charge_unit=charge_unit,
                charge_quantity=charge_quantity,
            )
        except Exception as e:
            logger.warning(f"Journal write failed for debit {transaction_id}: {e}")

        return transaction_id

    async def cancel(self, transaction_id: UUID) -> None:
        await self._client.refund(transaction_id)
        try:
            await self._balance_service.record_external_cancel(transaction_id)
        except Exception as e:
            logger.warning(f"Journal write failed for refund {transaction_id}: {e}")
