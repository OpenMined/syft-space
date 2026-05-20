"""Xendit charging adapter — concrete impl of policy_types.XenditCharger.

Bound at request time to a specific Xendit wallet (wallet_id, currency)
and the (tenant_id, endpoint_id) of the current query. Wraps the
BalanceService; policy code never sees the underlying transport.
"""

from uuid import UUID

from syft_space.components.payments.gateway.balance_service import (
    BalanceService,
    InsufficientBalanceError,
)
from syft_space.components.policy_types.interfaces import BalanceShortfallError


class XenditChargingAdapter:
    """Per-request charger for one Xendit wallet."""

    def __init__(
        self,
        *,
        balance_service: BalanceService,
        wallet_id: UUID,
        currency: str,
        tenant_id: UUID,
        endpoint_id: UUID,
    ) -> None:
        self._balance_service = balance_service
        self._wallet_id = wallet_id
        self._currency = currency
        self._tenant_id = tenant_id
        self._endpoint_id = endpoint_id

    @property
    def currency(self) -> str:
        return self._currency

    async def get_balance(self, user_email: str) -> float:
        return await self._balance_service.get_balance(
            wallet_id=self._wallet_id,
            tenant_id=self._tenant_id,
            user_email=user_email,
        )

    async def reserve(
        self,
        *,
        user_email: str,
        amount: float,
        charge_unit: str,
        charge_quantity: int,
    ) -> UUID:
        try:
            return await self._balance_service.reserve(
                wallet_id=self._wallet_id,
                tenant_id=self._tenant_id,
                user_email=user_email,
                endpoint_id=self._endpoint_id,
                amount=amount,
                currency=self._currency,
                charge_unit=charge_unit,
                charge_quantity=charge_quantity,
            )
        except InsufficientBalanceError as exc:
            balance = await self.get_balance(user_email)
            raise BalanceShortfallError(
                balance=balance, required=amount, currency=self._currency
            ) from exc

    async def cancel(self, transaction_id: UUID) -> None:
        await self._balance_service.cancel(transaction_id)
