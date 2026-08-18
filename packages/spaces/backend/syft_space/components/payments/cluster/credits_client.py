"""HTTP client for the cluster's credits API.

Transport only — debit / refund / balance against the cluster credits
service, authenticated with the space's service token. Fail-closed by
design: any transport failure raises, and the caller rejects the paid
query. See cluster.md "Credits API contract".
"""

import logging
from typing import Any
from uuid import UUID

import httpx

logger = logging.getLogger(__name__)

# Short timeout — this sits on the paid-query hot path.
_HTTP_TIMEOUT_SECONDS = 5.0


class ClusterCreditsError(RuntimeError):
    """Credits service unreachable or returned an unexpected response."""


class InsufficientCreditsError(Exception):
    """Debit rejected: the user's cluster balance can't cover the amount."""

    def __init__(self, balance: float, required: float):
        super().__init__(f"Balance {balance} below required {required}")
        self.balance = balance
        self.required = required


class ClusterCreditsClient:
    """Client for one cluster credits service, bound to one space token."""

    def __init__(self, base_url: str, service_token: str):
        self.base_url = base_url.rstrip("/")
        self._service_token = service_token

    def _build_http_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.base_url,
            timeout=_HTTP_TIMEOUT_SECONDS,
            headers={"Authorization": f"Bearer {self._service_token}"},
        )

    async def debit(
        self,
        *,
        transaction_id: UUID,
        user_email: str,
        amount: float,
        endpoint: str,
        charge_unit: str,
        charge_quantity: int,
    ) -> dict[str, Any]:
        """Atomically debit the user's cluster balance.

        ``transaction_id`` is the idempotency key — retries can't
        double-debit. Raises InsufficientCreditsError on 402.
        """
        try:
            async with self._build_http_client() as client:
                response = await client.post(
                    "/api/v1/credits/debit",
                    json={
                        "transaction_id": str(transaction_id),
                        "user_email": user_email,
                        "amount": amount,
                        "endpoint": endpoint,
                        "charge_unit": charge_unit,
                        "charge_quantity": charge_quantity,
                    },
                )
        except httpx.HTTPError as e:
            raise ClusterCreditsError(
                f"cluster credits service at {self.base_url} unavailable: {e}"
            ) from e

        if response.status_code == 402:
            data = response.json()
            raise InsufficientCreditsError(
                balance=data.get("balance", 0.0),
                required=data.get("required", amount),
            )
        if response.status_code != 200:
            raise ClusterCreditsError(
                f"credits debit failed ({response.status_code}): {response.text[:200]}"
            )
        return response.json()

    async def refund(self, transaction_id: UUID) -> None:
        """Reverse a debit (idempotent). 404 means nothing to reverse."""
        try:
            async with self._build_http_client() as client:
                response = await client.post(
                    "/api/v1/credits/refund",
                    json={"transaction_id": str(transaction_id)},
                )
        except httpx.HTTPError as e:
            raise ClusterCreditsError(
                f"cluster credits service at {self.base_url} unavailable: {e}"
            ) from e

        if response.status_code == 404:
            logger.warning(f"Refund for unknown transaction {transaction_id}")
            return
        if response.status_code != 200:
            raise ClusterCreditsError(
                f"credits refund failed ({response.status_code}): {response.text[:200]}"
            )

    async def get_balance(self, user_email: str) -> float:
        """Return the user's spendable cluster balance."""
        try:
            async with self._build_http_client() as client:
                response = await client.get(
                    "/api/v1/credits/balance", params={"user_email": user_email}
                )
                response.raise_for_status()
        except httpx.HTTPError as e:
            raise ClusterCreditsError(
                f"cluster credits service at {self.base_url} unavailable: {e}"
            ) from e
        return float(response.json()["balance"])
