"""Xendit Payment Sessions API client using httpx."""

from typing import Any

import httpx
from fastapi import HTTPException
from loguru import logger
from pydantic import BaseModel, ConfigDict


class XenditError(Exception):
    """Base exception for Xendit API errors."""

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        error_code: str | None = None,
    ):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        super().__init__(message)

    def to_http_exception(self) -> HTTPException:
        """Convert to FastAPI HTTPException."""
        return HTTPException(status_code=self.status_code, detail=self.message)


class XenditAuthError(XenditError):
    """Invalid API key (401)."""

    pass


class XenditValidationError(XenditError):
    """Request validation failed (400/422)."""

    pass


class XenditSessionResponse(BaseModel):
    """Xendit Payment Session API response model."""

    payment_session_id: str
    reference_id: str
    status: str
    amount: float
    payment_link_url: str
    currency: str | None = None

    model_config = ConfigDict(extra="allow")


class XenditClient:
    """Async httpx client for Xendit Payment Sessions API.

    Uses Basic auth with api_key as username, empty password.
    NOT a singleton — instantiated per-request from Wallet credentials.

    Usage:
        async with XenditClient(api_key, base_url) as client:
            session = await client.create_session(...)
    """

    def __init__(self, api_key: str, base_url: str = "https://api.xendit.co"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "XenditClient":
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            auth=(self.api_key, ""),
            timeout=30.0,
        )
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    def _handle_error(self, response: httpx.Response) -> None:
        """Raise typed error from Xendit API response."""
        try:
            body = response.json()
            message = body.get("message", response.text)
            error_code = body.get("error_code")
        except Exception:
            message = response.text
            error_code = None

        if response.status_code == 401:
            raise XenditAuthError(
                message=f"Xendit authentication failed: {message}",
                status_code=401,
                error_code=error_code,
            )
        if response.status_code in (400, 422):
            raise XenditValidationError(
                message=f"Xendit validation error: {message}",
                status_code=response.status_code,
                error_code=error_code,
            )
        raise XenditError(
            message=f"Xendit API error ({response.status_code}): {message}",
            status_code=response.status_code,
            error_code=error_code,
        )

    async def create_session(
        self,
        reference_id: str,
        amount: float,
        currency: str,
        country: str,
        description: str | None = None,
        payer_email: str | None = None,
        success_return_url: str | None = None,
        cancel_return_url: str | None = None,
        **kwargs: Any,
    ) -> XenditSessionResponse:
        """Create a Xendit Payment Session.

        Args:
            reference_id: Unique reference for idempotency / webhook join
            amount: Payment amount
            currency: Currency code (e.g., 'USD', 'IDR')
            country: ISO 3166-1 alpha-2 country code (e.g., 'ID', 'PH', 'SG')
            description: Optional session description
            payer_email: Payer's email (passed as customer object)
            success_return_url: Redirect URL on successful payment
            cancel_return_url: Redirect URL on cancelled payment
            **kwargs: Additional Xendit session params

        Returns:
            Parsed session response with payment_session_id, payment_link_url, etc.
        """
        assert self._client is not None, "Use 'async with XenditClient(...) as client:'"

        payload: dict[str, Any] = {
            "reference_id": reference_id,
            "amount": amount,
            "currency": currency,
            "country": country,
            "session_type": "PAY",
            "mode": "PAYMENT_LINK",
            "capture_method": "AUTOMATIC",
            **kwargs,
        }

        if description:
            payload["description"] = description
        if payer_email:
            # Use reference_id as customer reference to keep it unique per session
            payload["customer"] = {
                "reference_id": f"cust-{reference_id}",
                "type": "INDIVIDUAL",
                "email": payer_email,
                "individual_detail": {
                    "given_names": payer_email.split("@")[0],
                },
            }
        if success_return_url:
            payload["success_return_url"] = success_return_url
        if cancel_return_url:
            payload["cancel_return_url"] = cancel_return_url

        logger.debug(f"Creating Xendit session: reference_id={reference_id}")
        response = await self._client.post("/sessions", json=payload)

        if response.status_code not in (200, 201):
            self._handle_error(response)

        data = response.json()
        return XenditSessionResponse(**data)

    async def get_session(self, session_id: str) -> XenditSessionResponse:
        """Get a Xendit Payment Session by ID.

        Args:
            session_id: Xendit payment_session_id

        Returns:
            Parsed session response
        """
        assert self._client is not None, "Use 'async with XenditClient(...) as client:'"

        response = await self._client.get(f"/sessions/{session_id}")

        if response.status_code != 200:
            self._handle_error(response)

        data = response.json()
        return XenditSessionResponse(**data)
