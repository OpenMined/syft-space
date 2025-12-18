"""Accounting policy type implementation."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field
from syft_accounting_sdk import UserClient

from syftai_space.components.policy_types.interfaces import (
    BasePolicyType,
    PolicyContext,
)
from syftai_space.components.shared.utils import ConfigSchemaGenerator


class PricingMode(str, Enum):
    """Pricing mode for accounting.

    PER_CALL: Fixed price per API call
    PER_TOKEN: Price based on token usage
    """

    PER_CALL = "per_call"


class AccountingConfig(BaseModel):
    """Configuration schema for accounting policy."""

    price: float = Field(
        ...,
        gt=0,
        description="Price per unit",
    )
    pricing_mode: PricingMode = Field(
        default=PricingMode.PER_CALL,
        description="Pricing mode: per_call (fixed per request) or per_token (based on token usage)",
    )


class AccountingCredentials(BaseModel):
    """Credentials for the accounting service."""

    email: str
    password: str
    url: str

    @classmethod
    def from_context(cls, context: PolicyContext) -> "AccountingCredentials":
        """Create credentials from the policy context."""
        try:
            return cls(
                email=context.metadata["accounting_email"],
                password=context.metadata["accounting_password"],
                url=context.metadata["accounting_url"],
            )
        except KeyError as e:
            raise ValueError(
                f"Missing accounting credential: {e.args[0]}. "
                "Ensure PaymentService is configured for this tenant."
            ) from e


class AccountingPolicy(BasePolicyType):
    """Accounting policy type.

    Tracks and bills API usage based on calls or tokens.
    Credentials for the accounting service are injected via PolicyContext.metadata["payment_service"].

    This policy is stateless - accounting records are managed by the external accounting SDK.
    """

    NAME = "accounting"

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize the accounting policy.

        Args:
            config: Configuration dictionary matching AccountingConfig schema
        """
        self.config = AccountingConfig(**config)

    @classmethod
    def name(cls) -> str:
        """Get the name of the policy type."""
        return cls.NAME

    @classmethod
    def description(cls) -> str:
        """Get the description of the policy type."""
        return "Track and bill API usage based on calls or tokens"

    @classmethod
    def icon(cls) -> str:
        """Get the icon for the policy type."""
        return "💰"

    @classmethod
    def configuration_schema(cls) -> dict[str, Any]:
        """Return configuration schema required by this policy type.

        Returns:
            Clean JSON schema with properties and required fields only
        """
        return AccountingConfig.model_json_schema(
            schema_generator=ConfigSchemaGenerator
        )

    def pre_hook(self, context: PolicyContext) -> PolicyContext:
        """Pre-hook to create a delegated transaction before endpoint execution.

        Credentials are read from context.metadata (accounting_email, accounting_password, accounting_url).

        Args:
            context: Policy context with request information

        Returns:
            Context with transaction_id and transaction_amount in metadata
        """
        accounting_credentials = AccountingCredentials.from_context(context)

        if self.config.pricing_mode != PricingMode.PER_CALL:
            raise ValueError("Only PER_CALL pricing mode is supported")

        if self.config.price == 0:
            # No transaction needed for free requests
            return context

        transaction_token = context.request.get("transaction_token")
        if not transaction_token:
            raise ValueError(
                "Transaction token is required. Please add it to the request."
            )

        accounting_client = UserClient(
            url=accounting_credentials.url,
            email=accounting_credentials.email,
            password=accounting_credentials.password,
        )

        # Calculate the amount to be charged
        amount = self.config.price

        try:
            transaction = accounting_client.create_delegated_transaction(
                senderEmail=context.sender_email,
                amount=amount,
                transaction_token=transaction_token,
                appEpPath=context.endpoint_slug,
            )
        except Exception as e:
            raise ValueError(f"Failed to create accounting transaction: {e}") from e

        context.metadata["transaction_id"] = transaction.id
        context.metadata["transaction_amount"] = amount
        return context

    def post_hook(self, context: PolicyContext) -> PolicyContext:
        """Post-hook to confirm the transaction after successful endpoint execution.

        Args:
            context: Policy context with request and response

        Returns:
            Unmodified context
        """
        if self.config.price == 0:
            # No transaction needed for free requests
            return context

        transaction_id = context.metadata.get("transaction_id")
        if not transaction_id:
            raise ValueError(
                "Transaction ID not found. The pre_hook may have failed or was skipped."
            )

        accounting_credentials = AccountingCredentials.from_context(context)
        accounting_client = UserClient(
            url=accounting_credentials.url,
            email=accounting_credentials.email,
            password=accounting_credentials.password,
        )

        try:
            accounting_client.confirm_transaction(id=transaction_id)
        except Exception as e:
            raise ValueError(f"Failed to confirm accounting transaction: {e}") from e

        return context

    @classmethod
    def enabled(cls) -> bool:
        """Check if this policy type is enabled.

        Returns:
            True (always enabled)
        """
        return True

    @classmethod
    def validate_config(cls, config: dict[str, Any]) -> dict[str, Any]:
        """Validate configuration against AccountingConfig schema.

        Args:
            config: Configuration dictionary to validate

        Returns:
            Validated configuration dictionary

        Raises:
            ValueError: If configuration is invalid
        """
        try:
            validated = AccountingConfig(**config)
            return validated.model_dump()
        except Exception as e:
            raise ValueError(f"Invalid accounting config: {e}") from e
