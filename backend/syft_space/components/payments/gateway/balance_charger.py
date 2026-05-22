"""Provider-agnostic charging adapter over BalanceService.

Once funds are on a wallet, every prepaid-balance gateway spends them the
same way — only the top-up rail differs. This class binds a (wallet,
request) pair to the underlying BalanceService so policy code never
threads credentials or wallet ids through every call.
"""

from uuid import UUID

from syft_space.components.payments.gateway.balance_service import (
    BalanceService,
    InsufficientBalanceError,
)
from syft_space.components.policy_types.interfaces import BalanceShortfallError


class WalletBalanceCharger:
    """Per-request charger bound to one wallet and the active endpoint.

    Implements the PrepaidBalanceCharger Protocol — the same shape covers
    every prepaid-balance provider.
    """

    def __init__(
        self,
        *,
        balance_service: BalanceService,
        wallet_id: UUID,
        wallet_type: str,
        currency: str,
        tenant_id: UUID,
        endpoint_id: UUID,
    ) -> None:
        self._balance_service = balance_service
        self._wallet_id = wallet_id
        self._wallet_type = wallet_type
        self._currency = currency
        self._tenant_id = tenant_id
        self._endpoint_id = endpoint_id

    @property
    def currency(self) -> str:
        return self._currency

    @property
    def wallet_type(self) -> str:
        return self._wallet_type

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
